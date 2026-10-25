r"""services/mer_tout_compiler.py — v0.53.3

D-TOUT — « Tout compiler » d'une séquence de mise en route (Mnn), onglet
« Rendu PDF » de l'atelier (demande de Laurent du 25 octobre 2026) : tous les
documents de la partie choisie (ou de toute la séquence, partie par partie)
compilés d'un coup, avec la progression et le statut de chaque document, puis
une archive ZIP des PDF nommés clairement.

Choix (nommés dans doc/redemarrage_v0_53_3.md) :

  - D-TOUT-LISTE — la liste des documents est calculée ici
    (`documents_a_compiler`), pas dans le navigateur : par partie, fiche de
    cours élève et complète (si la partie a sa fiche), exercices de séance
    élève et corrigé au format par défaut (4 par A4 ; les demi-A4 restent à 2,
    F1), chaque test court de la partie en sujets A et B, élève et corrigé,
    plan, dossier enseignant, activités complémentaires élève et corrigé (si
    la partie en a). Une partie sans exercice n'a pas de planche.
  - D-TOUT-LOT — même mécanisme que le rendu par lot de l'administration
    (`compilation_batch`) : un flux SSE (GET, EventSource), un événement par
    document, le cache de compilation (`cache_rendus`) réutilisé, abandon
    après N erreurs d'infrastructure consécutives (pdflatex absent, délai
    dépassé ; réglage `compilation_batch_max_erreurs_consecutives`) et
    annulation quand le navigateur ferme la connexion. Les .tex et .log des
    échecs sont gardés dans `cache_rendus/echecs_mer/` (lien « log » de
    l'interface) ; l'archive va dans `rapports/` (lien de téléchargement).
  - Noms des fichiers : `M03_p1_fiche_eleve.pdf`, `M03_p1_fiche_complete.pdf`,
    `M03_p1_seances_4parA4_eleve.pdf`, `M03_p1_seances_4parA4_corrige.pdf`,
    `M03_p1_test1_A_eleve.pdf`, `M03_p1_plan.pdf`,
    `M03_p1_dossier_enseignant.pdf`, `M03_p1_activites_eleve.pdf`…
    (`p1` = partie 1).
"""

from __future__ import annotations

import datetime as _dt
import re
import zipfile
from pathlib import Path

PAR_PAGE_DEFAUT = 4
ERREURS_INFRA = ("pdflatex introuvable", "timeout")


def documents_a_compiler(s: dict, partie: int | None) -> list[tuple[str, dict]]:
    """D-TOUT-LISTE — [(nom de fichier, options du document)] pour la partie
    `partie` ou, sans elle, pour toutes les parties de la séquence `s`
    (`mises_en_route_6e.lire_sequence_mer`)."""
    from services.mises_en_route_6e import partie_de
    code = s["code"]
    parties = [partie_de(s, partie)] if partie is not None else list(s["parties"])
    out: list[tuple[str, dict]] = []
    for p in parties:
        n = p["numero"]
        pre = f"{code}_p{n}"
        base = {"partie": n}
        if p.get("fiche"):
            out.append((f"{pre}_fiche_eleve.pdf", {**base, "document": "fiche_cours", "version": "eleve"}))
            out.append((f"{pre}_fiche_complete.pdf", {**base, "document": "fiche_cours",
                                                      "version": "corrigee"}))
        if p.get("exercices"):
            for v, lib in (("eleve", "eleve"), ("corrigee", "corrige")):
                out.append((f"{pre}_seances_{PAR_PAGE_DEFAUT}parA4_{lib}.pdf",
                            {**base, "document": "planche", "version": v,
                             "par_page": PAR_PAGE_DEFAUT}))
        for rang, _t in enumerate(p.get("tests") or [], 1):
            for sujet in ("A", "B"):
                for v, lib in (("eleve", "eleve"), ("corrigee", "corrige")):
                    out.append((f"{pre}_test{rang}_{sujet}_{lib}.pdf",
                                {**base, "document": "test_court", "test": rang,
                                 "sujet": sujet, "version": v}))
        out.append((f"{pre}_plan.pdf", {**base, "document": "plan"}))
        out.append((f"{pre}_dossier_enseignant.pdf", {**base, "document": "dossier"}))
        if p.get("activites"):
            for v, lib in (("eleve", "eleve"), ("corrigee", "corrige")):
                out.append((f"{pre}_activites_{lib}.pdf",
                            {**base, "document": "activite", "version": v}))
    return out


def nom_archive(sequence: str, partie: int | None, maintenant=None) -> str:
    t = (maintenant or _dt.datetime.now()).strftime("%Y-%m-%d_%H-%M-%S")
    return f"{sequence}_{'partie' + str(partie) if partie is not None else 'sequence'}_documents_{t}.zip"


def nom_sur(nom: str, extensions: tuple[str, ...]) -> bool:
    """Nom de fichier seul (pas de chemin), extension autorisée."""
    return bool(re.fullmatch(r"[A-Za-z0-9_.\-]+", nom or "")) and ".." not in nom \
        and nom.endswith(extensions)


def iter_tout_compiler(conn_factory, niveau: str, sequence: str, partie: int | None, *,
                       compiler, tikz_libraries=None, tblr_libraries=None,
                       dossier_echecs: Path, dossier_archives: Path,
                       max_erreurs_consecutives: int = 5, maintenant=None):
    """D-TOUT-LOT — génère les événements de « Tout compiler » :
      {kind: 'debut', total, documents: [noms]} ;
      {kind: 'document', index, total, nom, statut: succes|cache|echec, message, log} ;
      {kind: 'fin', ok, echecs, archive, url} ou {kind: 'abandon', message}.
    `compiler(tex) -> ResultatCompilation` (compilateur_pdf.compiler_atome
    avec le cache et le délai long, fourni par la route) ; `conn_factory()`
    ouvre une connexion à la base (context manager)."""
    from services.mises_en_route_6e import generer_document_mer, lire_sequence_mer
    with conn_factory() as conn:
        s = lire_sequence_mer(conn, niveau, sequence)
        docs = documents_a_compiler(s, partie)
    yield {"kind": "debut", "total": len(docs), "documents": [d[0] for d in docs]}
    dossier_echecs.mkdir(parents=True, exist_ok=True)
    for f in dossier_echecs.glob(f"{sequence}_*"):
        f.unlink()
    pdfs: list[tuple[str, bytes]] = []
    echecs, infra = 0, 0
    for i, (nom, opts) in enumerate(docs, 1):
        ev = {"kind": "document", "index": i, "total": len(docs), "nom": nom,
              "statut": "echec", "message": "", "log": ""}
        try:
            with conn_factory() as conn:
                tex = generer_document_mer(conn, niveau, sequence, options=opts,
                                           tikz_libraries=tikz_libraries,
                                           tblr_libraries=tblr_libraries)
        except Exception as e:                      # options ou contenu invalides
            echecs += 1
            ev["message"] = f"génération du .tex : {e}"
            yield ev
            continue
        r = compiler(tex)
        if r.ok:
            infra = 0
            pdf = r.pdf_bytes or (r.pdf_path.read_bytes() if r.pdf_path else b"")
            pdfs.append((nom, pdf))
            ev["statut"] = "cache" if r.depuis_cache else "succes"
            yield ev
            continue
        echecs += 1
        msg = r.erreurs[0].message if r.erreurs else "Erreur inconnue de compilation."
        ev["message"] = msg
        racine = nom[:-4]
        (dossier_echecs / f"{racine}.tex").write_text(tex, encoding="utf-8")
        (dossier_echecs / f"{racine}.log").write_text(r.log_complet or msg, encoding="utf-8")
        ev["log"] = f"{racine}.log"
        yield ev
        if any(x in msg.lower() for x in ERREURS_INFRA):
            infra += 1
            if infra >= max_erreurs_consecutives:
                yield {"kind": "abandon",
                       "message": f"{infra} erreurs d'infrastructure consécutives ({msg})"}
                return
        else:
            infra = 0
    dossier_archives.mkdir(parents=True, exist_ok=True)
    archive = dossier_archives / nom_archive(sequence, partie, maintenant)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for nom, pdf in pdfs:
            z.writestr(nom, pdf)
    yield {"kind": "fin", "ok": len(pdfs), "echecs": echecs, "archive": archive.name,
           "url": f"/api/v2/livret-sequence/mer/archive/{archive.name}"}
