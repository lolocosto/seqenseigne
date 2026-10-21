#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""outils/import_lot6e_mer.py — v0.53.0

Import des lots de **mise en route** de 6e (`reference\lot6e\Mnn\Mnn.json`),
appelé par `outils/import_lot6e.py` (même commande, même essai à blanc, même
`--apply`, même sauvegarde et même journal que les séquences S01 à S13).

Format du lot (fixé, BRIEF v0.53.0 § 3) :

    {"sequence": "M01", "titre": "Calcul mental", "theme": "A",
     "type": "mise_en_route", "macros_locales": "",
     "objectifs": [{"code": "M01-01", "intitule": "...",
                    "criteres": {"F": "...", "A": "..."}, "seances": 6}],
     "fiche_cours": {"titre": "...", "latex": "...", "latex_corrige": "..."},
     "exercices_seance": [{"seance": 1, "objectif": "M01-01", "titre": "...",
                           "enonce": "...", "corrige": "...", "remed_enonce": "",
                           "remed_corrige": "", "calculatrice": "interdite",
                           "ordinateur": "", "origine": "...", "notes": "..."}],
     "evaluations": [{"titre": "Test court --- ...", "sujet": "A",
                      "calculatrice": "interdite",
                      "bareme": [["M01-01", 5], ["M01-02", 5]], "total": 10,
                      "latex": "...", "bareme_detail": "...", "origine": "..."}],
     "evaluations_retirees": []}

Clés facultatives (v0.53.0) : `figures` d'un élément (comme les lots S),
`calculatrice_exercices` d'une évaluation (v0.52.9).

Décisions (doc/redemarrage_v0_53_0.md, services/mises_en_route_6e.py) :

  - I-MR1 Référentiel : la section « Mises en route (M2026_N09) » de
    `outils/ref6e_v2.md` (nom, thème, objectifs, séances) fait foi, comme
    `objectifs_6e.json` pour les séquences S ; un intitulé ou un nombre de
    séances différent dans le lot est signalé (référentiel retenu). Les
    critères F et A viennent du lot. Séquence absente du référentiel : le
    lot est retenu (signalé).
  - I-MR2 Séquence du cycle 3 `Mnn` (numéro 200 + n), séquence-niveau
    N09/Mnn, une partie, objectifs `01`… sans objectif « Cours » (MR1b),
    nombre de séances de chaque objectif.
  - I-MR3 Fiche de cours : fiche sans objectif de la séquence (MR3), version
    complète par `\seqACompleter` comme au principal. `latex_corrige` (MR4) :
    vide ou égal à `latex` : rien ; fiche entière (elle a ses
    `\seqSectionFicheSix`) : seconde fiche « … (version complète) », utilisée
    pour la version corrigée ; sinon c'est une note de corrigé (réponses à
    compléter, conseils) : dernière section de la fiche, sans titre, dans
    `\seqLocExplication{…}` (visible en version complète seulement, comme
    le corrigé rédigé d'un exercice). Une seconde fiche que le lot n'a plus
    est retirée (sauf validée : signalé).
  - I-MR4 Exercices de séance : série MR, numéro = séance (MR01 = séance 1),
    reliés à leur objectif (série MR ; un lien MR vers un autre objectif est
    retiré quand l'exercice change d'objectif). Un exercice validé n'est
    jamais réécrit ; un MR de la base sans séance dans le lot est signalé,
    jamais supprimé.
  - I-MR5 Tests courts : comme les évaluations des lots S (sujets A et B,
    numéros EV jamais réattribués R2, retrait R1, évaluation validée
    intouchée R4) ; total attendu : 10 (signalé sinon).
  - I-MR6 `macros_locales` : les macros qu'il définit doivent être fournies
    par le module `seqenseigne-style6e` (les définitions du lot ne sont pas
    importées) ; une macro absente du module est signalée (anomalie), une
    macro déjà fournie est notée (information).
  - Le contrôle MR6 (`mises_en_route_6e.valider_sequence_mer`) termine le
    compte rendu de la séquence (dès l'essai à blanc).
"""

from __future__ import annotations

import re
from pathlib import Path

REF6E_V2 = Path(__file__).resolve().parent / "ref6e_v2.md"
TOTAL_TEST_COURT = 10
CLES_OBLIGATOIRES = ("sequence", "titre", "objectifs", "fiche_cours", "exercices_seance")

_RE_TITRE = re.compile(r"^### (M\d\d) — (.+?) \((\d+) exercices?")
_RE_THEME = re.compile(r"^\*Thème ([A-Z]) — ")
_RE_OBJ = re.compile(r"^- (M\d\d-\d\d) · (.+?) \((\d+(?:[.,]\d+)?) séances?\)")


def referentiel_mer(chemin: Path = REF6E_V2) -> dict:
    """{Mnn: {code, nom, theme, exercices, objectifs: [{code, intitule,
    seances}]}} d'après la section « Mises en route » de ref6e_v2.md ; {}
    si le fichier manque."""
    try:
        lignes = Path(chemin).read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    out, cur, dedans = {}, None, False
    for ligne in lignes:
        if ligne.startswith("## "):
            dedans = ligne.startswith("## Mises en route")
            cur = None
            continue
        if not dedans:
            continue
        m = _RE_TITRE.match(ligne)
        if m:
            cur = out.setdefault(m.group(1), {"code": m.group(1), "nom": m.group(2).strip(),
                                              "theme": "", "exercices": int(m.group(3)),
                                              "objectifs": []})
            continue
        if cur is None:
            continue
        m = _RE_THEME.match(ligne)
        if m:
            cur["theme"] = m.group(1)
            continue
        m = _RE_OBJ.match(ligne)
        if m:
            cur["objectifs"].append({"code": m.group(1), "intitule": m.group(2).strip(),
                                     "seances": float(m.group(3).replace(",", "."))})
    return out


_RE_DEF = re.compile(r"\\(?:newcommand|providecommand|renewcommand|DeclareRobustCommand)\*?"
                     r"\s*\{?\s*\\([A-Za-z@]+)|\\def\s*\\([A-Za-z@]+)|"
                     r"\\(?:newenvironment|NewDocumentEnvironment)\s*\{([A-Za-z@]+)\}|"
                     r"\\NewDocumentCommand\s*\{?\s*\\([A-Za-z@]+)")


def macros_definies(texte: str) -> list[str]:
    """Noms (sans barre oblique) des macros et environnements définis par
    `macros_locales` (commentaires ignorés)."""
    sans = "\n".join(l.split("%", 1)[0] if not l.lstrip().startswith("%") else ""
                     for l in (texte or "").splitlines())
    out = []
    for m in _RE_DEF.finditer(sans):
        nom = next(g for g in m.groups() if g)
        if nom not in out:
            out.append(nom)
    return out


def est_lot_mer(lot: dict) -> bool:
    from services.mises_en_route_6e import est_sequence_mer
    return est_sequence_mer(lot.get("sequence"))


def controler_format(lot: dict) -> list[str]:
    """Écarts au format fixé (clés obligatoires, types) ; [] si conforme."""
    err = [f"clé « {k} » absente" for k in CLES_OBLIGATOIRES if k not in lot]
    if lot.get("type") not in (None, "mise_en_route"):
        err.append(f"type {lot.get('type')!r} (attendu « mise_en_route »)")
    for k in ("objectifs", "exercices_seance", "evaluations", "evaluations_retirees"):
        if k in lot and not isinstance(lot[k], list):
            err.append(f"« {k} » n'est pas une liste")
    if "fiche_cours" in lot and not isinstance(lot["fiche_cours"], dict):
        err.append("« fiche_cours » n'est pas un objet")
    for i, e in enumerate(lot.get("exercices_seance") or [], start=1):
        if not isinstance(e, dict) or "seance" not in e or "objectif" not in e:
            err.append(f"exercice de séance n° {i} sans « seance » ou « objectif »")
    return err


def _sequence_cycle(conn, imp, code: str, nom: str, theme_id: str | None, rapport) -> None:
    """I-MR2 — séquence du cycle 3 `Mnn` (numéro 200 + n)."""
    from services.mises_en_route_6e import NUMERO_CYCLE_BASE, numero_mer
    numero = NUMERO_CYCLE_BASE + numero_mer(code)
    r = conn.execute("SELECT * FROM sequences_du_cycle WHERE cycle_code=? AND code=?",
                     (imp.CYCLE, code)).fetchone()
    if r is None:
        conn.execute("INSERT INTO sequences_du_cycle (id, cycle_code, code, numero, nom, "
                     "theme_id) VALUES (?,?,?,?,?,?)",
                     (imp._nid("sc"), imp.CYCLE, code, numero, nom, theme_id))
        etat = "créée"
    elif (r["numero"], r["nom"], r["theme_id"]) != (numero, nom, theme_id):
        conn.execute("UPDATE sequences_du_cycle SET numero=?, nom=?, theme_id=? WHERE id=?",
                     (numero, nom, theme_id, r["id"]))
        etat = "mise à jour"
    else:
        etat = "inchangée"
    rapport.cycle.append(f"mise en route {code} {nom} : {etat}")


MARQUE_SECTION = "\\seqSectionFicheSix"


def est_fiche_entiere(latex: str) -> bool:
    """MR4 — `latex_corrige` est une fiche entière (sections) plutôt qu'une
    note de corrigé."""
    return MARQUE_SECTION in (latex or "")


def sections_fiche_cours(imp, latex: str, note: str = "") -> list[dict]:
    r"""Sections de la fiche de cours ; `note` (MR4, note de corrigé) : une
    dernière section sans titre, `\seqLocExplication{note}`."""
    sections = imp.sections_fiche(latex or "")
    if (note or "").strip():
        sections.append({"titre": "", "items": ["\\seqLocExplication{" + note.strip() + "}"]})
    return sections


def _fiche_sans_objectif(conn, imp, seq: str, titre: str, latex: str, complete: bool,
                         note: str = ""):
    """(id, état) de la fiche de cours (complete=False) ou de sa version
    complète (MR4) de la séquence."""
    from services import fiches_resume as svc
    from services.mises_en_route_6e import SUFFIXE_COMPLETE
    sections = sections_fiche_cours(imp, latex, note)
    titre = titre + (SUFFIXE_COMPLETE if complete else "")
    cible = None
    for r in conn.execute("SELECT id, titre, etat_code FROM fiches_resume WHERE niveau=? AND "
                          "sequence=? AND objectif_id IS NULL ORDER BY num_fiche, id",
                          (imp.NIVEAU, seq)).fetchall():
        if (r["titre"] or "").endswith(SUFFIXE_COMPLETE) == complete:
            cible = r
            break
    if cible is None:
        f = svc.creer_fiche(conn, niveau=imp.NIVEAU, sequence=seq, titre=titre,
                            sections=sections)
        fid, etat = f["id"], "créée"
    else:
        fid = cible["id"]
        actuelle = svc.lire_fiche(conn, fid)
        if (actuelle["titre"] == titre and [(s["titre"], s["items"]) for s in actuelle["sections"]]
                == [(s["titre"], s["items"]) for s in sections]):
            return fid, "inchangée"
        if cible["etat_code"] == "valide":
            return fid, "validée, non modifiée"
        svc.modifier_fiche(conn, fid, titre=titre, sections=sections)
        etat = "mise à jour"
    if "mtime" in imp._cols(conn, "fiches_resume"):
        conn.execute("UPDATE fiches_resume SET mtime=? WHERE id=?", (imp._maintenant(), fid))
    return fid, etat


def _retirer_fiche_complete(conn, imp, seq: str, rapport) -> None:
    """I-MR3 — plus de `latex_corrige` distinct dans le lot : la fiche
    « version complète » de la base est retirée (sauf validée)."""
    from services import fiches_resume as svc
    from services.mises_en_route_6e import SUFFIXE_COMPLETE
    for r in conn.execute("SELECT id, titre, etat_code FROM fiches_resume WHERE niveau=? AND "
                          "sequence=? AND objectif_id IS NULL", (imp.NIVEAU, seq)).fetchall():
        if not (r["titre"] or "").endswith(SUFFIXE_COMPLETE):
            continue
        if r["etat_code"] == "valide":
            rapport.anomalie(f"{seq} : fiche « {r['titre']} » validée, gardée alors que le lot "
                             "n'a plus de version complète distincte")
            continue
        svc.supprimer_fiche(conn, r["id"])
        rapport.seq(seq)["lignes"].append(f"fiche « {r['titre']} » retirée (le lot n'a plus "
                                          "de version complète distincte)")
        rapport.journal["import"].append({"cle": f"{imp.NIVEAU}/{seq}/fiche_complete",
                                          "id": r["id"], "retiree": True})


def importer_lot_mer(conn, imp, lot: dict, themes: dict, ref_mer: dict, rapport) -> set:
    """Importe un lot de mise en route ; retourne les figures utilisées.
    `imp` : le module outils/import_lot6e (fonctions communes)."""
    from services import mises_en_route_6e as mer
    seq = lot["sequence"]
    figures: set = set()
    sr = rapport.seq(seq)
    ecarts = controler_format(lot)
    if ecarts:
        rapport.anomalie(f"{seq} : lot non conforme au format des mises en route "
                         f"({' ; '.join(ecarts)}), non importé")
        return figures
    ref = ref_mer.get(seq)
    if ref is None:
        rapport.infos.append(f"{seq} : mise en route absente de ref6e_v2.md, le lot fait foi")
    nom = (ref or {}).get("nom") or lot.get("titre") or seq
    theme = (ref or {}).get("theme") or lot.get("theme") or ""
    if ref and lot.get("titre") and lot["titre"] != nom:
        rapport.infos.append(f"{seq} : titre du lot « {lot['titre']} » ≠ référentiel « {nom} » "
                             "(référentiel retenu)")
    if ref and lot.get("theme") and lot["theme"] != theme:
        rapport.anomalie(f"{seq} : thème {lot['theme']} dans le lot, {theme} dans le "
                         "référentiel (référentiel retenu)")
    if theme not in themes:
        rapport.anomalie(f"{seq} : thème {theme!r} inconnu du cycle 3, séquence sans thème")
    sr["lignes"].append(f"mise en route {nom} (lot : « {lot.get('titre', '')} »)")
    definies = macros_definies(lot.get("macros_locales") or "")       # I-MR6
    if definies:
        from services.style6e import MACROS as MACROS_STYLE6E
        absentes = [m for m in definies if m not in MACROS_STYLE6E]
        if absentes:
            rapport.anomalie(f"{seq} : macros_locales définit {', '.join(absentes)}, absente(s) "
                             "du module seqenseigne-style6e (non importées : à verser dans le "
                             "module)")
        fournies = [m for m in definies if m in MACROS_STYLE6E]
        if fournies:
            rapport.infos.append(f"{seq} : macros_locales du lot fournies par le module "
                                 f"seqenseigne-style6e : {', '.join(fournies)}")
    elif (lot.get("macros_locales") or "").strip() and \
            re.search(r"\\(?:newcommand|providecommand|def)\b", lot["macros_locales"]):
        rapport.anomalie(f"{seq} : macros_locales illisible, à vérifier")
    _sequence_cycle(conn, imp, seq, nom, themes.get(theme), rapport)
    sn = imp._seq_niveau(conn, seq, rapport)
    if sn is None:
        return figures
    pid = imp._partie(conn, sn["id"], 1, seq, rapport)

    # Objectifs (I-MR1, I-MR2).
    ref_objs = {o["code"]: o for o in (ref or {}).get("objectifs", [])}
    objectifs_ids: dict = {}
    vus_obj = set()
    for o in lot.get("objectifs") or []:
        code = (o.get("code") or "").strip()
        if not re.fullmatch(rf"{seq}-\d\d", code):
            rapport.anomalie(f"{seq} : code d'objectif {code!r} invalide (attendu {seq}-nn), "
                             "ignoré")
            continue
        if ref and code not in ref_objs:
            rapport.anomalie(f"{seq} : objectif {code} absent de ref6e_v2.md, ignoré avec ses "
                             "exercices")
            continue
        r = ref_objs.get(code, {})
        intitule = r.get("intitule") or (o.get("intitule") or "").strip()
        seances = r.get("seances") if r else o.get("seances")
        if r and (o.get("intitule") or intitule) != intitule:
            rapport.infos.append(f"{code} : intitulé du lot différent du référentiel "
                                 "(référentiel retenu)")
        if r and o.get("seances") not in (None, "") and float(o["seances"]) != r["seances"]:
            rapport.anomalie(f"{code} : {o['seances']} séance(s) dans le lot, "
                             f"{mer._fmt(r['seances'])} dans le référentiel (référentiel retenu)")
        crit = o.get("criteres") or {}
        d = {"nom": intitule, "critere_F": (crit.get("F") or "").strip(),
             "critere_A": (crit.get("A") or "").strip(), "critere_E": ""}
        oid, etat = imp._objectif(conn, sn["id"], pid, code[-2:], d, rapport, code)
        try:
            nb = float(seances or 0)
        except (TypeError, ValueError):
            nb = 0.0
        if float(conn.execute("SELECT nb_seances FROM objectifs WHERE id=?",
                              (oid,)).fetchone()[0] or 0) != nb:
            conn.execute("UPDATE objectifs SET nb_seances=? WHERE id=?", (nb, oid))
            if etat == "inchangé":
                etat = "mis à jour"
        ro = rapport.obj(seq, code, intitule)
        ro["objectif"] = etat
        objectifs_ids[code] = oid
        vus_obj.add(code)
    for code in ref_objs:
        if code not in vus_obj:
            rapport.anomalie(f"{code} : objectif du référentiel sans contenu dans le lot")

    # Fiche de cours (I-MR3).
    fc = lot.get("fiche_cours") or {}
    titre_fc = (fc.get("titre") or "").strip() or f"{mer.libelle_mer(seq)} --- {nom}"
    if (fc.get("latex") or "").strip():
        corr = (fc.get("latex_corrige") or "").strip()
        if corr == fc["latex"].strip():
            corr = ""
        entiere = bool(corr) and est_fiche_entiere(corr)
        note = "" if entiere else corr
        fid, etat = _fiche_sans_objectif(conn, imp, seq, titre_fc, fc["latex"], False, note)
        sr["lignes"].append(f"fiche de cours « {titre_fc} » : {etat}"
                            + (" (note de corrigé en version complète)" if note else ""))
        if etat == "validée, non modifiée":
            rapport.anomalie(f"{seq} : fiche de cours validée dans l'atelier, non modifiée")
        if entiere:
            fid2, etat2 = _fiche_sans_objectif(conn, imp, seq, titre_fc, corr, True)
            sr["lignes"].append(f"fiche de cours, version complète rédigée à part : {etat2}")
        else:
            _retirer_fiche_complete(conn, imp, seq, rapport)
        figures |= imp._figures(lot, fc) | imp._figures(lot, {"latex": corr})
    else:
        rapport.anomalie(f"{seq} : pas de fiche de cours dans le lot")

    # Exercices de séance (I-MR4).
    liens: dict = {}
    seances_vues: dict = {}
    for e in lot.get("exercices_seance") or []:
        try:
            n = int(e.get("seance"))
        except (TypeError, ValueError):
            rapport.anomalie(f"{seq} : exercice « {e.get('titre', '')} » sans numéro de séance, "
                             "ignoré")
            continue
        oc = (e.get("objectif") or "").strip()
        if n in seances_vues:
            rapport.anomalie(f"{seq} séance {n} en double ({e.get('titre', '')}), second ignoré")
            continue
        if oc not in objectifs_ids:
            rapport.anomalie(f"{seq} séance {n} : objectif {oc!r} inconnu, exercice ignoré")
            continue
        seances_vues[n] = oc
        marques = imp.marqueurs_lot(e, f"{seq} MR{n:02d}", rapport)
        imp._compter_marqueurs(rapport, seq, marques)
        eid, etat = imp._exercice(conn, seq, mer.SERIE_MR, n, e, marques)
        Rapport = type(rapport)
        Rapport.compter(rapport.obj(seq, oc), "exercices de séance MR", etat)
        if etat == "validé, non modifié":
            rapport.anomalie(f"{imp.NIVEAU}/{seq}/MR{n:02d} validé dans l'atelier : contenu du "
                             "lot non appliqué")
        oid = objectifs_ids[oc]
        conn.execute("DELETE FROM objectif_exos WHERE exercice_id=? AND serie=? AND "
                     "objectif_id<>?", (eid, mer.SERIE_MR, oid))
        liens.setdefault((oid, mer.SERIE_MR), []).append(eid)
        figures |= imp._figures(lot, e)
        rapport.journal["import"].append({"cle": f"{imp.NIVEAU}/{seq}/MR{n:02d}", "id": eid,
                                          "objectif": oc, "seance": n,
                                          "origine": e.get("origine", ""),
                                          "notes": e.get("notes", "")})
    if seances_vues:
        attendu = set(range(1, max(seances_vues) + 1))
        trous = sorted(attendu - set(seances_vues))
        if trous:
            rapport.anomalie(f"{seq} : séance(s) sans exercice : {', '.join(map(str, trous))}")
    n_liens = imp._lier_objectifs(conn, liens)
    if n_liens:
        sr["lignes"].append(f"exercices de séance : {n_liens} lien(s) objectif créé(s)")
    for (num,) in conn.execute("SELECT num FROM exercices WHERE niveau=? AND sequence=? AND "
                               "serie_code=? ORDER BY num", (imp.NIVEAU, seq, mer.SERIE_MR)):
        if num not in seances_vues:
            rapport.anomalie(f"{imp.NIVEAU}/{seq}/MR{int(num):02d} en base sans séance dans le "
                             "lot (gardé)")
    sr["lignes"].append(f"exercices de séance : {len(seances_vues)} (MR01 à "
                        f"MR{max(seances_vues or [0]):02d})")

    # Tests courts (I-MR5).
    for ev in lot.get("evaluations") or []:
        tot = ev.get("total")
        if tot not in (None, "") and float(tot) != TOTAL_TEST_COURT:
            rapport.anomalie(f"{seq} « {ev.get('titre', '')} » sujet {ev.get('sujet', '?')} : "
                             f"total {tot}, un test court est sur {TOTAL_TEST_COURT}")
        figures |= imp._figures(lot, ev)
    imp.importer_evaluations(conn, lot, objectifs_ids, rapport)

    # Contrôle MR6.
    v = mer.valider_sequence_mer(conn, imp.NIVEAU, seq)
    sr["lignes"].append("contrôle de la séquence : "
                        + ("complète" if v["valide"] else "à compléter — "
                           + " ; ".join(v["erreurs"]))
                        + ("" if not v["avertissements"]
                           else " (attention : " + " ; ".join(v["avertissements"]) + ")"))
    return figures


def figures_du_lot(imp, lot: dict) -> set:
    """Figures des éléments d'un lot de mise en route (pour --apply)."""
    noms: set = set()
    fc = lot.get("fiche_cours") or {}
    noms |= imp._figures(lot, fc) | imp._figures(lot, {"latex": fc.get("latex_corrige") or ""})
    for e in lot.get("exercices_seance") or []:
        noms |= imp._figures(lot, e)
    for ev in lot.get("evaluations") or []:
        noms |= imp._figures(lot, ev)
    return noms
