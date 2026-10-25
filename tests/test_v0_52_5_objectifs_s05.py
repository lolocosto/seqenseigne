"""tests/test_v0_52_5_objectifs_s05.py — v0.52.5

1. `outils/objectifs_6e.json` complété pour S04 à S10 (doc/redemarrage_v0_52_5.md) :
   il doit rester la transcription exacte du référentiel validé
   (`outils/ref6e_v2.md`, copie de col6/ref6e_v2.md), sinon l'import crée
   des objectifs ou des critères que Laurent n'a pas validés.
2. Un lot S05 s'importe (avant v0.52.5 : « séquence absente de
   objectifs_6e.json, lot non importé »).
3. Module seqenseigne-style6e v0.6 : macros du lot S05 versées dans le .dtx,
   le .sty régénéré et la liste MACROS.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import pytest

from outils import import_lot6e as imp
from services import style6e
from tests.test_v0_52_0_import_lot6e import base  # noqa: F401  (fixture)

APPLI = Path(__file__).resolve().parent.parent
MD = APPLI / "outils" / "ref6e_v2.md"
CRITERE_E = "Utilise ce savoir-faire pour résoudre un problème."


# ── Lecture indépendante du markdown ─────────────────────────────────────────

def _sans_echappement(t: str) -> str:
    return re.sub(r"\\([\\`*_{}\[\]()#+\-.!|])", r"\1", t)


def _lire_markdown() -> dict:
    """{séquence: [(numéro, libellé, [(code, nom, F, A)])]} des sections S01 à
    S13 (les mises en route M01 à M07 sont une autre livraison)."""
    texte = MD.read_text(encoding="utf-8")
    debut = texte.index("\n## S01 — ")
    fin = texte.index("\n## Mises en route")
    out: dict = {}
    for bloc in re.split(r"\n(?=## S\d\d — )", texte[debut:fin])[1:]:
        tete = re.match(r"## (S\d\d) — (.+)", bloc)
        seq = tete.group(1)
        nom = re.sub(r"\s*\((nouvelle|recréée)\)\s*$", "", tete.group(2)).strip()
        parties: list = []
        cur = None
        lignes = bloc.splitlines()
        for i, l in enumerate(lignes):
            m = re.match(r"^### Partie (\d+) — (.+)$", l)
            if m:
                cur = (int(m.group(1)), m.group(2).strip(), [])
                parties.append(cur)
                continue
            m = re.match(rf"^\*\*{seq}-(\d\d) · (.+?)\*\*", l)
            if m:
                if cur is None:                       # décision O2
                    cur = (1, nom, [])
                    parties.append(cur)
                f, a = re.match(r"^- F : « (.+?) » · A : « (.+) »\s*$", lignes[i + 2]).groups()
                cur[2].append((m.group(1), _sans_echappement(m.group(2).strip()),
                               _sans_echappement(f), _sans_echappement(a)))
        out[seq] = parties
    return out


def _lire_json() -> dict:
    ref = imp.charger_referentiel()
    return {seq: [(p["numero"], p["libelle"],
                   [(o["code"], o["nom"], o["critere_F"], o["critere_A"]) for o in p["objectifs"]])
                  for p in ps]
            for seq, ps in ref["parties"].items()}


# ── 1. objectifs_6e.json ↔ référentiel validé ────────────────────────────────

def test_objectifs_6e_json_transcrit_exactement_le_referentiel_valide_de_s01_a_s13():
    """Parties, codes, intitulés et critères F/A : ceux du markdown validé,
    sans écart ni oubli (un écart créerait en base un objectif non validé)."""
    attendu = _lire_markdown()
    assert sorted(attendu) == [f"S{i:02d}" for i in range(1, 14)]
    assert _lire_json() == attendu


def test_toutes_les_sequences_du_referentiel_ont_leurs_parties_sinon_l_import_refuse_le_lot():
    ref = imp.charger_referentiel()
    for s in ref["sequences"]:
        parties = ref["parties"].get(s["code"])
        assert parties, f"{s['code']} : l'importeur refuserait le lot"
        assert all(p["objectifs"] and p["libelle"] for p in parties)


def test_critere_e_commun_du_referentiel_et_objectif_cours_connaitre_le_cours():
    """ref6e_v2 : « Le critère E vaut Utilise ce savoir-faire… » ; objectif
    Cours : nom par défaut « Connaître le cours » (décision M6, v0.52.4)."""
    ref = imp.charger_referentiel()
    assert {o["critere_E"] for ps in ref["parties"].values() for p in ps
            for o in p["objectifs"]} == {CRITERE_E}
    assert ref["objectif_cours"]["nom"] == "Connaître le cours"


def test_aucun_objectif_ne_prend_le_code_reserve_a_l_objectif_cours_de_sa_partie():
    """Le code (n-1)1 de chaque partie est créé par l'import pour l'objectif
    Cours : un objectif du référentiel qui le porterait serait écrasé."""
    ref = imp.charger_referentiel()
    for seq, ps in ref["parties"].items():
        for p in ps:
            for o in p["objectifs"]:
                assert o["code"] != f"{p['numero'] - 1}1", (seq, o["code"])
                assert int(o["code"][0]) + 1 == p["numero"], (seq, o["code"])


def test_mises_en_route_absentes_car_livrees_a_part():
    ref = imp.charger_referentiel()
    assert not any(k.startswith("M") for k in ref["parties"])
    assert [s["code"] for s in ref["sequences"]] == [f"S{i:02d}" for i in range(1, 14)]


def test_s05_garde_ses_objectifs_codes_et_libelles_apres_le_decoupage_de_la_geometrie():
    """Découpage du 19 octobre 2026 (décision de Laurent) : S05 garde les
    premiers éléments (partie 1) et reçoit la médiatrice (partie 2,
    S05-42 → S05-12, S05-43 → S05-13) ; échappements Markdown retirés."""
    ps = imp.charger_referentiel()["parties"]["S05"]
    assert [p["libelle"] for p in ps] == ["Premiers éléments", "Médiatrice"]
    assert [[o["code"] for o in p["objectifs"]] for p in ps] == [["02", "03", "04"], ["12", "13"]]
    assert ps[1]["objectifs"][0]["nom"] == "Construire la médiatrice d'un segment"
    s05_03 = ps[0]["objectifs"][1]
    assert s05_03["critere_F"] == "Distingue [AB], (AB) et [AB)."   # échappements retirés


DECOUPAGE = {"S05-42": "S05-12", "S05-43": "S05-13", "S05-12": "S06-02", "S05-32": "S06-03",
             "S05-22": "S07-02", "S05-23": "S07-03", "S05-24": "S07-04", "S05-25": "S07-05",
             "S05-33": "S08-02", "S05-44": "S08-12"}


def test_decoupage_de_la_geometrie_en_quatre_sequences_du_theme_c_sans_perte_d_objectif():
    """Les 13 objectifs de l'ancienne S05 « Géométrie plane » se retrouvent,
    mêmes intitulés et critères, dans S05 à S08 (thème C) ; la table de
    correspondance du markdown donne chaque ancien code."""
    ref = imp.charger_referentiel()
    seqs = {s["code"]: s for s in ref["sequences"]}
    assert [(c, seqs[c]["nom"], seqs[c]["theme"]) for c in ("S05", "S06", "S07", "S08", "S09")] == [
        ("S05", "Points, segments, droites", "C"), ("S06", "Cercles", "C"), ("S07", "Angles", "C"),
        ("S08", "Triangles", "C"), ("S09", "Symétrie axiale", "C")]
    assert [seqs[c]["theme"] for c in ("S10", "S11", "S12", "S13")] == ["D", "D", "E", "F"]
    geo = {f"{s}-{o['code']}": (p["numero"], p["libelle"]) for s in ("S05", "S06", "S07", "S08")
           for p in ref["parties"][s] for o in p["objectifs"]}
    assert len(geo) == 13
    assert set(DECOUPAGE.values()) | {"S05-02", "S05-03", "S05-04"} == set(geo)
    assert geo["S08-12"] == (2, "Droites remarquables") and geo["S08-02"] == (1, "Triangles")
    assert geo["S06-03"] == (1, "Cercles")                    # partie unique (décision O2)
    texte = MD.read_text(encoding="utf-8")
    table = texte[texte.index("## Table de correspondance"):]
    for ancien, neuf in DECOUPAGE.items():
        assert f"| {ancien} | {neuf} |" in table


def test_positions_relatives_restent_en_revisions_pas_de_nouvelle_partie():
    """Décision du 19 octobre 2026 : le découpage n'ajoute pas de partie
    « Positions relatives de deux droites » (vue en CM1-CM2)."""
    ref = imp.charger_referentiel()
    assert not any("osition" in p["libelle"] for ps in ref["parties"].values() for p in ps)
    assert sum(len(ps) for ps in ref["parties"].values()) == 20


# ── 2. Import d'un lot S05 ───────────────────────────────────────────────────

def _lot_s05(dossier: Path, macro_inconnue=False) -> Path:
    """Lot S05 minimal : un objectif de la partie 2 (médiatrice, S05-12
    depuis le découpage de la géométrie)."""
    d = dossier / "S05"
    (d / "figures").mkdir(parents=True)
    corps = (r"\seqLocCadreTrace[4cm]{\begin{tikzpicture}\seqLocSiCorrige{\begin{scope}"
             r"[seqLocCorr]\draw (0,0)--(1,0);\end{scope}}{}\end{tikzpicture}}"
             r" Mesure \seqLocAngle{ABC}. \begin{tikzpicture}\seqLocRapporteur{(0,0)}{0}"
             r"\end{tikzpicture}")
    if macro_inconnue:
        corps += r" \seqLocInconnue{x}"
    lot = {
        "sequence": "S05", "titre": "Points, segments, droites", "theme": "C", "ancien_code": "S01",
        "objectifs": [
            {"code": "S05-12", "partie": 2, "intitule": "Construire la médiatrice d'un segment",
             "activites": [{"num": 1, "titre": "Mesurer", "latex": "Observe.", "figures": []}],
             "fiche_resume": {"titre": "La médiatrice",
                              "latex": "\\seqSectionFicheSix{1. Rapporteur}\nTexte."},
             "exercices": [
                 {"num": 1, "serie": "F", "titre": "Mesure", "enonce": corps, "corrige": "",
                  "remed_enonce": "", "remed_corrige": "", "figures": []},
                 {"num": 1, "serie": "A", "titre": "Lecture fausse", "enonce": "A1",
                  "corrige": "", "remed_enonce": "", "remed_corrige": "", "figures": []}]}],
    }
    (d / "S05.json").write_text(json.dumps(lot, ensure_ascii=False), encoding="utf-8")
    return dossier


def test_import_d_un_lot_s05_passe_avec_les_objectifs_cours_de_ses_deux_parties(base, tmp_path):  # noqa: F811
    lots = _lot_s05(tmp_path / "lots")
    r = imp.essai_a_blanc(base, imp.charger_lots(lots), imp.charger_referentiel(),
                          base.parent / "images")
    assert not any("lot non importé" in a for a in r.anomalies)
    assert not any("absentes du module" in a for a in r.anomalies)
    assert imp.main(["--db", str(base), "--lots", str(lots), "--apply", "--yes"]) == 0
    c = sqlite3.connect(base)
    c.row_factory = sqlite3.Row
    rows = c.execute(
        "SELECT p.numero, o.code, o.nom, o.critere_F FROM objectifs o "
        "JOIN sequence_parties p ON p.id = o.partie_id "
        "JOIN sequences_par_niveau sn ON sn.id = p.sequence_par_niveau_id "
        "WHERE sn.niveau='N09' AND sn.sequence_code='S05' ORDER BY o.code").fetchall()
    c.close()
    codes = {r["code"]: r for r in rows}
    for n in range(1, 3):                                   # objectif Cours de chaque partie
        assert codes[f"{n - 1}1"]["nom"] == "Connaître le cours"
        assert codes[f"{n - 1}1"]["numero"] == n
    # v0.52.8 (O1) : critères de S05-12 du 20 octobre (équerre ou compas).
    assert codes["12"]["critere_F"] == ("Construit la médiatrice d'un segment, à la règle "
                                        "graduée et à l'équerre ou au compas.")
    assert codes["12"]["numero"] == 2
    # Objectifs Cours des deux parties + objectif du lot (un objectif du
    # référentiel sans contenu dans le lot n'est pas créé, il est signalé).
    assert sorted(codes) == ["01", "11", "12"]


def test_second_import_s05_ne_change_rien(base, tmp_path):  # noqa: F811
    lots = _lot_s05(tmp_path / "lots")
    assert imp.main(["--db", str(base), "--lots", str(lots), "--apply", "--yes"]) == 0
    c = sqlite3.connect(base)
    avant = [c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
             for t in ("objectifs", "exercices", "objectif_exos", "fiches_resume")]
    c.close()
    r = imp.Rapport()
    c = sqlite3.connect(base)
    imp.executer(c, imp.charger_lots(lots), imp.charger_referentiel(), r,
                 base.parent / "images", ecrire_fichiers=False)
    apres = [c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
             for t in ("objectifs", "exercices", "objectif_exos", "fiches_resume")]
    c.rollback()
    c.close()
    assert apres == avant
    t = r.texte()
    assert "objectif créé" not in t and "objectif mis à jour" not in t
    assert not re.search(r"\b[1-9]\d* lien\(s\) créé", t)


def test_import_signale_une_macro_locale_que_le_module_ne_fournit_pas(base, tmp_path):  # noqa: F811
    """Sans le module à jour, tous les documents de la séquence échoueraient
    à la compilation : l'essai à blanc le dit avant l'import."""
    lots = _lot_s05(tmp_path / "lots", macro_inconnue=True)
    r = imp.essai_a_blanc(base, imp.charger_lots(lots), imp.charger_referentiel(),
                          base.parent / "images")
    assert any("absentes du module" in a and "seqLocInconnue" in a for a in r.anomalies)
    assert not any("absentes du module" in a and "seqLocAngle" in a for a in r.anomalies)


# ── 3. Module seqenseigne-style6e v0.6 ───────────────────────────────────────

DTX = APPLI / "paquet" / "seqenseigne-style6e.dtx"
STY = APPLI / "paquet" / "seqenseigne-style6e.sty"
MACROS_S05 = ("seqLocCadreTrace", "seqLocAngle", "seqLocRapporteur")


def _code(src: str) -> str:
    return "\n".join(l for l in src.splitlines() if not l.startswith("%"))


@pytest.mark.skipif(not DTX.is_file(), reason="module 6e absent du dossier paquet/")
def test_macros_du_lot_s05_dans_le_module_v0_6_car_les_enonces_du_lot_les_appellent():
    dtx, sty = DTX.read_text(encoding="utf-8"), STY.read_text(encoding="utf-8")
    # v0.52.7 : le module est passé en v0.7 ; v0.52.8 : v0.8 ; les macros v0.6 restent.
    # v0.53.0 : module v0.9 (\seqLocItemCM, lot M01), qui garde tout ce qui précède.
    assert "v0.11 seqenseigne" in dtx and "v0.11 seqenseigne" in sty   # v0.53.1 : v0.10 ; v0.53.3 : v0.11
    for m in MACROS_S05:
        assert m in style6e.MACROS
        assert style6e.correspondances()["\\" + m] == "seqenseigne-style6e"
        defi = re.compile(r"\\(?:NewDocumentCommand|newcommand)\{\\" + m + r"\}")
        assert defi.search(_code(dtx)) and defi.search(sty), m
        assert rf"\DescribeMacro{{\{m}}}" in dtx                 # documentée
        assert re.search(r"\\changes\{v0\.6\}\{[^}]*\}\{\\cs\{" + m + r"\}", dtx), m
    # 4 du lot S05 + page de garde par partie (2, C2) + 7 du lot S04.
    assert dtx.count(r"\changes{v0.6}") == 13


@pytest.mark.skipif(not DTX.is_file(), reason="module 6e absent du dossier paquet/")
def test_style_tikz_seqloccorr_dans_le_module_mais_pas_dans_macros():
    """Décision S1 : un style TikZ s'écrit [seqLocCorr], jamais \\seqLocCorr ;
    le mettre dans MACROS ne ferait détecter aucun usage."""
    dtx, sty = DTX.read_text(encoding="utf-8"), STY.read_text(encoding="utf-8")
    ligne = r"\tikzset{seqLocCorr/.style={color=seqSixRouge, line width=0.8pt}}"
    assert ligne in _code(dtx) and ligne in sty
    assert "seqLocCorr" in style6e.STYLES_TIKZ and "seqLocCorr" not in style6e.MACROS
    assert re.search(r"\\changes\{v0\.6\}\{[^}]*\}\{Style TikZ \\texttt\{seqLocCorr\}", dtx)


@pytest.mark.skipif(not DTX.is_file(), reason="module 6e absent du dossier paquet/")
def test_sty_livre_contient_le_code_du_dtx_ligne_a_ligne():
    """Le .sty livré est celui que `tex seqenseigne.ins` produit du .dtx :
    chaque ligne de code du .dtx (hors commentaires de docstrip) s'y trouve,
    dans le même ordre."""
    dtx = DTX.read_text(encoding="utf-8")
    debut = dtx.index("%<*package>\n\\RequirePackage")
    code = [l for l in dtx[debut:].splitlines()
            if l and not l.startswith("%") and not l.startswith("\\endinput")]
    sty = [l for l in STY.read_text(encoding="utf-8").splitlines() if l and not l.startswith("%")]
    i = 0
    for l in sty:
        if i < len(code) and l == code[i]:
            i += 1
    assert i == len(code), code[i]


# ── 4. Page de garde du livret par partie (C1 à C3, demande de Laurent) ─────

def _seq(nom="Géométrie plane", couleur="geometrie", libelles=("Premiers éléments", "Cercles")):
    return {"code": "S05", "nom": nom, "theme_couleur": couleur, "parties": [
        {"numero": 1, "libelle": libelles[0], "objectifs": [
            {"code": "02", "nom": "Tracer"}, {"code": "03", "nom": "Noter"}]},
        {"numero": 2, "libelle": libelles[1], "objectifs": [{"code": "12", "nom": "Cercle"}]},
        {"numero": 3, "libelle": "", "objectifs": []}]}


def test_page_de_garde_range_les_objectifs_sous_le_titre_de_leur_partie():
    """Laurent : la liste des objectifs à la suite ne montrait pas les parties."""
    from services.livret_sequence_6e import couverture
    tex = couverture(_seq())
    assert r"\seqCouvertureLivretSix*{Géométrie plane}" in tex
    i = tex.index
    assert i(r"\seqPartieCouvertureSix{Partie 1 --- Premiers éléments}{S05-02/{Tracer},"
             r"S05-03/{Noter}}") < i(r"\seqPartieCouvertureSix{Partie 2 --- Cercles}"
                                     r"{S05-12/{Cercle}}")
    assert "Partie 3" not in tex            # partie sans objectif de capacité : rien


def test_trait_de_la_page_de_garde_a_la_couleur_du_theme_de_la_sequence():
    from services.couleurs_themes import famille_par_slug
    from services.livret_sequence_6e import couverture
    hexa = famille_par_slug("geometrie")["hex_principal"].lstrip("#").upper()
    assert couverture(_seq()).startswith(r"\definecolor{seqSixTheme}{HTML}{" + hexa + "}")
    # Thème sans couleur connue : bleu du module (pas de \definecolor).
    assert r"\definecolor" not in couverture(_seq(couleur=""))


def test_partie_sans_libelle_ou_qui_repete_le_nom_de_la_sequence_titree_partie_n():
    """L'atelier ne stocke pas de libellé ; une séquence à partie unique a le
    nom de la séquence pour libellé (décision O2) : inutile de le répéter."""
    from services.livret_sequence_6e import couverture
    tex = couverture(_seq(nom="Pré-algèbre", libelles=("Pré-algèbre", "")))
    assert r"\seqPartieCouvertureSix{Partie 1}{" in tex
    assert r"\seqPartieCouvertureSix{Partie 2}{" in tex


def test_libelles_des_parties_lus_dans_objectifs_6e_pour_son_niveau_seulement():
    from services.livret_sequence_6e import libelles_parties
    assert libelles_parties("N09", "S05")[2] == "Médiatrice"           # découpage du 19 octobre
    assert libelles_parties("N09", "S08")[2] == "Droites remarquables"
    assert libelles_parties("N10", "S05") == {}         # autre niveau : « Partie n »
    assert libelles_parties("N09", "S99") == {}


@pytest.mark.skipif(not DTX.is_file(), reason="module 6e absent du dossier paquet/")
def test_forme_sans_etoile_de_la_page_de_garde_inchangee_pour_les_tex_existants():
    """Les .tex déjà produits (aperçus des lots, documents figés) appellent
    \\seqCouvertureLivretSix{titre}{liste} : même rendu qu'en v0.5."""
    sty = STY.read_text(encoding="utf-8")
    assert r"\NewDocumentCommand{\seqCouvertureLivretSix}{s m m}" in sty
    assert (r"\IfBooleanTF{#1}{\par\smallskip#3}{%" "\n"
            r"  \begin{itemize}[itemsep=0pt,topsep=2pt]" "\n"
            r"    \foreach \seq@c/\seq@t in {#3}{\item\textit{\seq@c\ : \seq@t}}") in sty
    assert r"\colorlet{seqSixTheme}{seqSixBleu}" in sty
    assert "seqPartieCouvertureSix" in style6e.MACROS


# ── 5. Macros du lot S04 (pré-algèbre) dans le module v0.6 ──────────────────

MACROS_S04 = ("seqLocBloc", "seqLocAccolade", "seqLocBalance", "seqLocSac", "seqLocMasse",
              "seqLocObjet")


@pytest.mark.skipif(not DTX.is_file(), reason="module 6e absent du dossier paquet/")
def test_macros_du_lot_s04_dans_le_module_v0_6_car_les_enonces_du_lot_les_appellent():
    dtx, sty = DTX.read_text(encoding="utf-8"), STY.read_text(encoding="utf-8")
    for m in MACROS_S04:
        assert m in style6e.MACROS
        defi = re.compile(r"\\(?:NewDocumentCommand|newcommand)\{\\" + m + r"\}")
        assert defi.search(_code(dtx)) and defi.search(sty), m
        assert rf"\DescribeMacro{{\{m}}}" in dtx
        assert re.search(r"\\changes\{v0\.6\}\{[^}]*\}\{\\cs\{" + m + r"\}", dtx), m
    for st in ("seqLocBarre", "seqLocBarreR", "seqLocBarreV", "seqLocBarreQ"):
        assert st in style6e.STYLES_TIKZ and st not in style6e.MACROS
        assert st + "/.style=" in sty
    # \seqLocAccolade décore avec brace : la bibliothèque est chargée par le module.
    assert r"\usetikzlibrary{decorations.pathreplacing}" in sty
