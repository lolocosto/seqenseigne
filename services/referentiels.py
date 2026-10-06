"""services/referentiels.py — Logique métier des référentiels de niveau.

Un référentiel est la version figée d'un programme d'un niveau (thèmes,
séquences, objectifs) pour une année scolaire donnée. Voir table SQL
`referentiel_niveaux` : id, niveau, version, date_debut, date_fin,
description, etat.

Modèle d'état (v0.15.3) :

    en_cours → valide → verrouille → utilise
                        └─ annule (référentiels écartés au verrouillage
                           d'un concurrent du même niveau)

- `en_cours` : au moins un atome non validé OU au moins un PDF non OK.
                État initial. Transition auto vers `valide` gérée par
                l'app (cf. services.referentiel_validation).
- `valide`   : tous les atomes sont validés ET tous les PDF sont OK.
                Transition auto vers `en_cours` si modif, ou vers
                `verrouille` manuellement par l'utilisateur.
- `verrouille` : le JSON et les PDFs ont été produits ; le référentiel
                est prêt à être utilisé dans une progression. Bouton
                « Déverrouiller » côté UI (retour à `valide`).
- `utilise`  : associé à ≥ 1 progression. Transition auto gérée par
                l'app dès que ce lien existe. Atelier de construction
                des progressions à venir (chantier suivi de classe).
- `annule`   : état terminal caché de l'UI. Préservé pour traçabilité
                des concurrents écartés lors du verrouillage d'un
                autre référentiel du même niveau.

Anciens noms (≤ v0.15.2) : `fige` (intermédiaire entre `valide` et
`verrouille`) a été fusionné dans `verrouille` lors de la migration
v0.15.3 (cf. persistence.sqlite_store._migrer_schema_post_ddl).
Voir doc/scoping_v0_13_5_referentiels.md pour le contexte historique.

Aucune dépendance Flask.
"""
from __future__ import annotations

import datetime
import sqlite3
import string


# ── v0.13.5.1.4 — Détection des objectifs « Cours » ─────────────────────────
#
# Convention métier : l'objectif "Cours" d'une partie a le code formé du
# chiffre `numero_partie - 1` suivi de '1' :
#   partie 1 → code '01'
#   partie 2 → code '11'
#   partie 3 → code '21'
# Ces objectifs sont structurellement à part : pas de méthode, pas de
# fiche de résumé, pas d'exos rattachés. Dans l'arbre du tableau de bord,
# on n'affiche pour eux que leur titre — les sections vides
# (Méthode/Fiche/F/A/E) sont supprimées.
#
# (Convention dupliquée depuis services/livret_plans_de_travail.py pour
# éviter une dépendance entre services. Si la convention évoluait, les
# deux fichiers devraient bouger ensemble.)
def _est_objectif_cours(code_obj: str, numero_partie: int) -> bool:
    if not code_obj:
        return False
    return code_obj == f"{numero_partie - 1}1"



# ── Helpers de lecture (existants depuis v0.6.x) ──────────────────────────────

def lister_par_niveau(store, niveau: str) -> list[dict]:
    """
    Retourne les référentiels d'un niveau, triés par version décroissante
    (le plus récent en tête). Chaque entrée porte id, niveau, version,
    description, etat.

    `store` doit exposer `lister_referentiels(niveau=...)`.

    v0.15.2.8 — Auto-validation lazy : pour chaque référentiel
    `en_cours` ou `valide` (donc non terminal), on recalcule l'état en
    fonction des critères de validation (cf.
    `services.referentiel_validation.maj_etat_lazy`). Si un atome ou un
    document a changé depuis la dernière lecture, l'état est mis à jour
    en BDD avant d'être renvoyé.
    """
    if not niveau:
        return []
    # v0.15.2.8 — maj lazy AVANT de lire la liste, pour que les états
    # renvoyés à l'UI reflètent l'éligibilité courante. On groupe les
    # majs dans une seule connexion (économise les ouvertures).
    from services.referentiel_validation import maj_etat_lazy
    with store._conn() as conn:
        # v0.48.2 — Les référentiels externes n'ont pas d'éligibilité calculée.
        rows = conn.execute(
            "SELECT id, etat FROM referentiel_niveaux WHERE niveau = ? "
            "AND COALESCE(source, 'interne') <> 'externe'",
            (niveau,),
        ).fetchall()
        for r in rows:
            if r['etat'] in ('en_cours', 'valide'):
                try:
                    maj_etat_lazy(conn, r['id'])
                except Exception:
                    # Ne jamais bloquer la lecture sur une erreur de
                    # calcul d'éligibilité (par sécurité).
                    pass

    # v0.48.2 — Référentiels INTERNES seulement (les externes ont leur propre
    # écran et sont ajoutés explicitement pour la progression, cf. route).
    refs = [r for r in store.lister_referentiels(niveau)
            if (r.get("source") or "interne") != "externe"]
    # Tri par version décroissante (versions numériques lexico : '2024' > '2023')
    refs.sort(key=lambda r: r.get("version", ""), reverse=True)
    return [
        {
            "id":          r.get("id"),
            "niveau":      r.get("niveau"),
            "version":     r.get("version"),
            "description": r.get("description", ""),
            "etat":        r.get("etat", ""),
            "date_debut":  r.get("date_debut"),
            "date_fin":    r.get("date_fin"),
            # v0.48.4 — type (principal / MER), source et nom calculé.
            "type_ref":    r.get("type_ref") or "principal",
            "source":      r.get("source") or "interne",
            "nom":         _nom(r),
        }
        for r in refs
    ]


def _nom(r: dict) -> str:
    from services.referentiel_principal_externe import nom_calcule
    return nom_calcule(r)


def recommande(store, niveau: str) -> dict | None:
    """
    Retourne le référentiel à proposer par défaut lors de la création d'une
    nouvelle progression pour ce niveau : le plus récent toutes états
    confondus.

    À durcir en v0.13.5.4 pour ne renvoyer que les états `fige` et
    `verrouille` (les coquilles `en_cours`/`valide` ne sont pas
    utilisables, et les `annule` sont écartées).

    Retourne None si aucun référentiel n'existe pour ce niveau.
    """
    refs = lister_par_niveau(store, niveau)
    return refs[0] if refs else None


# ── v0.13.5.1 — Création/suppression/figeage minimal ──────────────────────────

def calculer_annee_scolaire(maintenant: datetime.date | None = None) -> str:
    """
    Calcule l'année civile de début de l'année scolaire en cours.

    Convention française : l'année scolaire 2025-2026 commence en
    septembre 2025. On considère qu'à partir du mois d'août inclus
    (préparation de rentrée), on est dans l'année scolaire suivante.

    Exemples :
      - 7 mai 2026 → '2025' (année scolaire 2025-2026)
      - 1er août 2026 → '2026' (année scolaire 2026-2027)
      - 15 février 2027 → '2026' (année scolaire 2026-2027)

    `maintenant` est injectable pour faciliter les tests.
    """
    if maintenant is None:
        maintenant = datetime.date.today()
    if maintenant.month >= 8:
        return str(maintenant.year)
    return str(maintenant.year - 1)


def calculer_suffixe_disponible(conn: sqlite3.Connection,
                                 niveau: str, annee: str) -> str:
    """
    Calcule le premier suffixe alphabétique disponible pour un nouveau
    référentiel (niveau, année). Tous états confondus (annule et
    verrouille inclus).

    Ordre : '' (vide), 'b', 'c', 'd', …, 'z'.

    Retourne le suffixe à utiliser. Lève RuntimeError si aucun suffixe
    n'est disponible (cas extrême, > 25 référentiels même année + niveau).

    Le format de version est `<annee><suffixe>`, ex. '2025', '2025b',
    '2025c'. La PK de référentiel est `<annee>_<niveau><suffixe>`.
    """
    pattern = annee + '%'
    rows = conn.execute(
        "SELECT version FROM referentiel_niveaux "
        "WHERE niveau = ? AND version LIKE ?",
        (niveau, pattern),
    ).fetchall()
    suffixes_pris = set()
    for r in rows:
        v = r["version"] if isinstance(r, sqlite3.Row) else r[0]
        # On extrait le suffixe = ce qui vient après l'année.
        # Sécurité : on s'assure que la version commence par `annee`.
        if v.startswith(annee):
            suffixes_pris.add(v[len(annee):])

    # '' (vide) est testé en premier, puis b, c, …, z.
    candidats = [''] + list(string.ascii_lowercase[1:])
    for cand in candidats:
        if cand not in suffixes_pris:
            return cand
    raise RuntimeError(
        f"Aucun suffixe disponible pour {niveau} année {annee} "
        f"(>25 référentiels, cas extrême non prévu)."
    )


def calculer_nom_auto(conn: sqlite3.Connection, niveau: str,
                       maintenant: datetime.date | None = None) -> dict:
    """
    Calcule le nom et la version d'un nouveau référentiel pour le niveau
    donné, en se basant sur l'année scolaire courante et le premier
    suffixe alphabétique disponible.

    Retourne un dict {id, niveau, version, annee, suffixe} :
      - id      = `<annee>_<niveau><suffixe>` (PK)
      - version = `<annee><suffixe>`
      - annee   = `<annee>` seule (4 chiffres)
      - suffixe = '' ou 'b'/'c'/…
    """
    annee = calculer_annee_scolaire(maintenant)
    suffixe = calculer_suffixe_disponible(conn, niveau, annee)
    version = f"{annee}{suffixe}"
    ref_id = f"{annee}_{niveau}{suffixe}"
    return {
        "id":      ref_id,
        "niveau":  niveau,
        "version": version,
        "annee":   annee,
        "suffixe": suffixe,
    }


def creer_coquille(conn: sqlite3.Connection, niveau: str,
                    description: str = '',
                    maintenant: datetime.date | None = None,
                    type_ref: str = 'principal') -> dict:
    """
    Crée un nouveau référentiel à l'état `en_cours`, sous forme de
    coquille (uniquement la ligne dans `referentiel_niveaux`, aucune
    autre table peuplée).

    Le contenu sera peuplé au moment du figeage (v0.13.5.3).

    Retourne le dict du référentiel créé : {id, niveau, version, etat,
    description, date_debut, date_fin}.

    Lève ValueError si le niveau est vide.
    """
    if not niveau or not niveau.strip():
        raise ValueError("Le niveau est obligatoire pour créer un référentiel.")
    niveau = niveau.strip()

    nom = calculer_nom_auto(conn, niveau, maintenant)
    # v0.48.4 — Type du référentiel : principal (progression principale) ou
    # MER (progression de mise en route seulement).
    if type_ref not in ('principal', 'mer'):
        raise ValueError(f"Type de référentiel invalide : {type_ref!r}")

    conn.execute(
        "INSERT INTO referentiel_niveaux "
        "(id, niveau, version, date_debut, date_fin, description, etat, type_ref) "
        "VALUES (?, ?, ?, NULL, NULL, ?, 'en_cours', ?)",
        (nom["id"], nom["niveau"], nom["version"], description, type_ref),
    )
    conn.commit()
    return {
        "id":          nom["id"],
        "niveau":      nom["niveau"],
        "version":     nom["version"],
        "etat":        "en_cours",
        "description": description,
        "date_debut":  None,
        "date_fin":    None,
    }


def supprimer(conn: sqlite3.Connection, ref_id: str) -> None:
    """
    Supprime un référentiel `en_cours` (uniquement). Les autres états
    (valide, fige, verrouille, annule) sont conservés pour traçabilité.

    Lève ValueError si le référentiel n'existe pas ou si son état n'est
    pas `en_cours`.
    """
    row = conn.execute(
        "SELECT etat FROM referentiel_niveaux WHERE id = ?", (ref_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Référentiel introuvable : {ref_id}")
    etat = row["etat"] if isinstance(row, sqlite3.Row) else row[0]
    if etat != "en_cours":
        raise ValueError(
            f"Seuls les référentiels `en_cours` peuvent être supprimés. "
            f"État actuel : {etat}."
        )
    conn.execute("DELETE FROM referentiel_niveaux WHERE id = ?", (ref_id,))
    conn.commit()


def lister_concurrents_a_annuler(conn: sqlite3.Connection,
                                   ref_id: str) -> list[dict]:
    """
    Pour un référentiel candidat au figeage, retourne la liste des
    référentiels du même niveau-année à suffixe alphabétiquement
    antérieur, en état `en_cours` ou `valide`. Ce sont eux qui seront
    passés à `annule` si le figeage est confirmé.

    Retourne [] si aucun concurrent.

    Lève ValueError si le référentiel candidat n'existe pas.
    """
    row = conn.execute(
        "SELECT niveau, version FROM referentiel_niveaux WHERE id = ?",
        (ref_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Référentiel introuvable : {ref_id}")
    niveau = row["niveau"] if isinstance(row, sqlite3.Row) else row[0]
    version = row["version"] if isinstance(row, sqlite3.Row) else row[1]

    # On sépare l'année (4 chiffres) du suffixe pour comparer les suffixes.
    if len(version) < 4 or not version[:4].isdigit():
        # Format de version inattendu (référentiel historique) — pas
        # de concurrent à écarter.
        return []
    annee = version[:4]
    suffixe = version[4:]

    pattern = annee + '%'
    rows = conn.execute(
        "SELECT id, niveau, version, etat, description "
        "FROM referentiel_niveaux "
        "WHERE niveau = ? AND version LIKE ? AND id != ? "
        "AND etat IN ('en_cours', 'valide') "
        "ORDER BY version",
        (niveau, pattern, ref_id),
    ).fetchall()
    concurrents = []
    for r in rows:
        v = r["version"]
        if not v.startswith(annee):
            continue
        sx = v[len(annee):]
        # sx alphabétiquement antérieur à suffixe (string compare classique :
        # '' < 'b' < 'c' < …).
        if sx < suffixe:
            concurrents.append({
                "id":          r["id"],
                "niveau":      r["niveau"],
                "version":     r["version"],
                "etat":        r["etat"],
                "description": r["description"] or "",
            })
    return concurrents


def verrouiller_minimal(conn: sqlite3.Connection, ref_id: str,
                          force_confirme: bool = False,
                          maintenant: datetime.date | None = None) -> dict:
    """
    Transition d'état `valide → verrouille` (v0.15.3, renommée depuis
    `figer_minimal` introduite en v0.13.5.1) :
      - Vérifie que le référentiel existe et est en état `valide`.
      - Identifie les concurrents à annuler.
      - Si concurrents non vides ET `force_confirme=False` : retourne
        `{confirmation_requise: True, concurrents: [...]}` sans rien
        modifier (l'UI doit redemander avec force_confirme=True).
      - Sinon : passe les concurrents à `annule` et le référentiel à
        `verrouille`, pose `date_debut`.

    NB cette fonction ne fait QUE la transition d'état. La production
    du JSON et la copie des PDF dans le dossier `_verrouille/` sont à
    la charge du service appelant (cf. `services.referentiel_figeage`).

    Lève ValueError si le référentiel est introuvable ou pas en `valide`.
    """
    row = conn.execute(
        "SELECT id, niveau, version, etat FROM referentiel_niveaux "
        "WHERE id = ?",
        (ref_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Référentiel introuvable : {ref_id}")
    if row["etat"] != "valide":
        raise ValueError(
            f"Le référentiel doit être à l'état `valide` pour être verrouillé. "
            f"État actuel : {row['etat']}."
        )

    concurrents = lister_concurrents_a_annuler(conn, ref_id)
    if concurrents and not force_confirme:
        return {
            "confirmation_requise": True,
            "concurrents":          concurrents,
        }

    if maintenant is None:
        maintenant = datetime.date.today()
    date_debut = maintenant.isoformat()

    # Annulation des concurrents
    for c in concurrents:
        conn.execute(
            "UPDATE referentiel_niveaux SET etat = 'annule' WHERE id = ?",
            (c["id"],),
        )
    # Passage à verrouille
    conn.execute(
        "UPDATE referentiel_niveaux SET etat = 'verrouille', date_debut = ? "
        "WHERE id = ?",
        (date_debut, ref_id),
    )
    conn.commit()

    return {
        "confirmation_requise": False,
        "ref": {
            "id":         row["id"],
            "niveau":     row["niveau"],
            "version":    row["version"],
            "etat":       "verrouille",
            "date_debut": date_debut,
        },
        "concurrents_annules": concurrents,
    }


# v0.15.3 — Alias rétro-compat. À supprimer en v0.16 quand plus aucun
# appelant externe ne référence `figer_minimal`. En interne, tout le code
# nouveau utilise `verrouiller_minimal`.
figer_minimal = verrouiller_minimal


def deverrouiller(conn: sqlite3.Connection, ref_id: str) -> dict:
    """v0.15.3 — Transition d'état `verrouille → valide`.

    Action utilisateur (bouton « Déverrouiller » côté UI). Permet de
    revenir à `valide` pour modifier le référentiel après une erreur.

    Le dossier `_verrouille/<ref_id>/` est conservé pendant le déverrouillage
    (au cas où l'utilisateur veuille re-verrouiller à l'identique). Il est
    écrasé au prochain verrouillage.

    Lève :
      ValueError — référentiel introuvable, ou état différent de
                   `verrouille` (par exemple `utilise` : pas de
                   déverrouillage tant que des progressions y sont liées).
    """
    row = conn.execute(
        "SELECT id, niveau, version, etat FROM referentiel_niveaux "
        "WHERE id = ?",
        (ref_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Référentiel introuvable : {ref_id}")
    if row["etat"] != "verrouille":
        raise ValueError(
            f"Le référentiel doit être à l'état `verrouille` pour être "
            f"déverrouillé. État actuel : {row['etat']}."
        )

    conn.execute(
        "UPDATE referentiel_niveaux SET etat = 'valide' WHERE id = ?",
        (ref_id,),
    )
    # v0.19.1.3 — Purge du snapshot des parties : un référentiel `valide`
    # n'a pas de photo en base (sa structure repart vivre dans le modèle
    # actif, éditable). Le dossier _verrouille/ est conservé (cf. docstring).
    from services.referentiel_figeage import purger_snapshot_referentiel
    purger_snapshot_referentiel(conn, ref_id)
    conn.commit()
    return {
        "ref": {
            "id":      row["id"],
            "niveau":  row["niveau"],
            "version": row["version"],
            "etat":    "valide",
        },
    }


# ── v0.13.5.1 — Helper UI : arbre du niveau pour le tableau de bord ──────────

def arbre_du_niveau(conn: sqlite3.Connection, niveau: str) -> dict:
    """
    Retourne l'arbre **séquence → partie → objectif → atomes** pour
    visualiser dans l'atelier Référentiel l'état des atomes du niveau.

    Lit les tables actives (pas les referentiel_*) puisqu'un référentiel
    en_cours/valide est juste une coquille — c'est la BDD active qui
    fait foi pendant la phase de préparation.

    Structure retournée :
        {
          "niveau": "N11",
          "sequences": [
            {"code", "numero", "nom", "theme_couleur",
             "parties": [
               {"numero", "nb_seances_R_AE",
                "objectifs": [
                  {"code", "nom", "fin_cycle",
                   "atomes": [
                     {"type", "id", "code", "titre", "etat_code"},
                     ...]}, ...]}, ...]}, ...],
          "stats": {"total", "valides", "en_cours"},
        }

    Atomes types : 'notion', 'methode', 'exo', 'fiche'.
    Code court : C01 (notion), M01 (methode), F01/A02/E03 (exo), FR01 (fiche).
    """
    # On joint sequences_du_cycle en filtrant sur le cycle du niveau,
    # via param_niveaux. Sans ce filtre, les codes 'S01', 'S02'… qui
    # existent dans plusieurs cycles produiraient des duplications
    # (cf. N11 → C04 mais le code S01 existe aussi en C03).
    seqs = conn.execute("""
        SELECT sn.id AS sn_id, sn.sequence_code AS code,
               sdc.numero, sdc.nom,
               t.code_couleur AS theme_couleur
        FROM sequences_par_niveau sn
        JOIN param_niveaux pn ON pn.code = sn.niveau
        JOIN sequences_du_cycle sdc
            ON sdc.code = sn.sequence_code
           AND sdc.cycle_code = pn.cycle_code
        LEFT JOIN themes t ON t.id = sdc.theme_id
        WHERE sn.niveau = ?
        ORDER BY sdc.numero, sn.sequence_code
    """, (niveau,)).fetchall()

    sequences = []
    total = 0
    valides = 0

    for sq in seqs:
        sn_id = sq["sn_id"]
        seq_code = sq["code"]

        parties_rows = conn.execute("""
            SELECT id, numero, nb_seances_R_AE
            FROM sequence_parties
            WHERE sequence_par_niveau_id = ?
            ORDER BY numero
        """, (sn_id,)).fetchall()

        parties = []
        for p in parties_rows:
            partie_id = p["id"]

            # v0.13.5.1.1 — Exos R (Révision) et EA (Exercice d'Approche)
            # rattachés directement à la partie (pas à un objectif).
            # Les R viennent typiquement d'un autre niveau (origin_*) ;
            # les EA sont des exos natifs de la séquence.
            #
            # v0.13.5.1.2 — Évolution du modèle d'affichage :
            #   - Pour R : on affiche l'ident complet "<niveau>/<seq>/<serie><num>"
            #     (issu des origin_*) qui pointe sans ambiguïté vers l'exo source.
            #   - Pour EA : on affiche le code court "EA<ordre>" (rangement local
            #     de l'enseignant dans la partie).
            # Pour la navigation (cliquabilité), on porte aussi nav_niveau /
            # nav_seq pour pouvoir ouvrir l'atelier Exercice dans le bon
            # contexte — pour R, c'est origin_niveau/origin_seq ; pour EA,
            # c'est le niveau/séquence courants.
            rae_rows = conn.execute("""
                SELECT pera.type, pera.ordre,
                       e.id AS exo_id, e.titre, e.serie_code, e.num,
                       e.etat_code,
                       pera.origin_niveau, pera.origin_seq,
                       pera.origin_serie, pera.origin_num
                FROM partie_exos_revision_approche pera
                JOIN exercices e ON e.id = pera.exercice_id
                WHERE pera.partie_id = ?
                ORDER BY pera.type, pera.ordre
            """, (partie_id,)).fetchall()
            atomes_rae = []
            for x in rae_rows:
                if x["type"] == "R":
                    # Ident complet pour les R : <niveau>/<seq>/<serie><num>
                    on = x["origin_niveau"] or "?"
                    os_ = x["origin_seq"] or "?"
                    osr = x["origin_serie"] or "?"
                    onum = x["origin_num"]
                    onum_str = f"{int(onum):02d}" if onum is not None else "??"
                    libelle = f"{on}/{os_}/{osr}{onum_str}"
                    nav_niveau = x["origin_niveau"] or niveau
                    nav_seq    = x["origin_seq"] or seq_code
                else:
                    # EA : code court fondé sur l'ordre dans la partie
                    libelle = f"EA{int(x['ordre']):02d}"
                    nav_niveau = niveau
                    nav_seq    = seq_code
                atomes_rae.append({
                    "type":       "exo",
                    "sous_type":  x["type"],   # 'R' ou 'EA'
                    "id":         x["exo_id"],
                    "code":       libelle,
                    "titre":      x["titre"] or "",
                    "etat_code":  x["etat_code"] or "en_cours",
                    "nav_niveau": nav_niveau,
                    "nav_seq":    nav_seq,
                })

            objs_rows = conn.execute("""
                SELECT id, code, nom, methode_id, fin_cycle
                FROM objectifs
                WHERE partie_id = ?
                ORDER BY code
            """, (partie_id,)).fetchall()

            objectifs = []
            for o in objs_rows:
                obj_id = o["id"]

                # v0.13.5.1.4 — Objectif Cours : pas de méthode, pas de
                # fiche, pas d'exos. On expose juste le titre + un flag
                # `est_cours=True` que le frontend utilise pour ne pas
                # afficher les lignes vides (Méthode (manquante), Fiche
                # (manquante), Série F/A/E (aucun)).
                est_cours = _est_objectif_cours(o["code"], p["numero"])
                if est_cours:
                    objectifs.append({
                        "id":        obj_id,
                        "code":      o["code"],
                        "nom":       o["nom"] or "",
                        "fin_cycle": bool(o["fin_cycle"])
                                      if o["fin_cycle"] is not None else False,
                        "est_cours": True,
                        "methode":   None,
                        "fiche":     None,
                        "notions":   [],
                        "exos_F":    [],
                        "exos_A":    [],
                        "exos_E":    [],
                    })
                    continue

                # v0.13.5.1.2 — On structure les atomes de l'objectif en
                # sous-sections typées (au lieu d'une liste plate) pour
                # que le frontend puisse les afficher selon une mise en
                # page fixe : ligne 1 = méthode + fiche, lignes notions,
                # ligne F, ligne A, ligne E.
                #
                # nav_niveau / nav_seq sont posés sur chaque atome pour
                # supporter l'ouverture en deeplink dans l'atelier
                # d'atome correspondant — ici, c'est toujours le niveau
                # et la séquence courants (les exos R sont rangés à la
                # partie, pas à un objectif, donc pas de cas emprunté).
                methode = None
                fiche   = None
                notions = []
                exos_F  = []
                exos_A  = []
                exos_E  = []

                # Méthode liée à l'objectif (cardinalité 1-1)
                if o["methode_id"]:
                    me = conn.execute("""
                        SELECT id, titre, num_methode, etat_code
                        FROM methodes WHERE id = ?
                    """, (o["methode_id"],)).fetchone()
                    if me:
                        num = me["num_methode"]
                        code = (f"M{int(num):02d}"
                                if num is not None else "M??")
                        methode = {
                            "type":       "methode",
                            "id":         me["id"],
                            "code":       code,
                            "titre":      me["titre"] or "",
                            "etat_code":  me["etat_code"] or "en_cours",
                            "nav_niveau": niveau,
                            "nav_seq":    seq_code,
                        }

                # Notions liées à l'objectif (N-N via objectif_notions)
                notions_rows = conn.execute("""
                    SELECT n.id, n.titre, n.num_connaissance, n.etat_code
                    FROM notions n
                    JOIN objectif_notions on1
                        ON on1.notion_id = n.id
                    WHERE on1.objectif_id = ?
                    ORDER BY n.num_connaissance, n.id
                """, (obj_id,)).fetchall()
                for n in notions_rows:
                    num = n["num_connaissance"]
                    code = f"C{str(num).zfill(2)}" if num else "C??"
                    notions.append({
                        "type":       "notion",
                        "id":         n["id"],
                        "code":       code,
                        "titre":      n["titre"] or "",
                        "etat_code":  n["etat_code"] or "en_cours",
                        "nav_niveau": niveau,
                        "nav_seq":    seq_code,
                    })

                # Exos liés (via objectif_exos), ventilés par série F/A/E
                exos_rows = conn.execute("""
                    SELECT e.id, e.titre, e.serie_code, e.num,
                           e.etat_code, oe.serie, oe.ordre
                    FROM objectif_exos oe
                    JOIN exercices e ON e.id = oe.exercice_id
                    WHERE oe.objectif_id = ?
                    ORDER BY oe.serie, oe.ordre
                """, (obj_id,)).fetchall()
                for e in exos_rows:
                    serie_code_court = e["serie_code"] or "?"
                    code = (serie_code_court +
                            (f"{int(e['num']):02d}"
                             if e["num"] is not None else "??"))
                    atome_exo = {
                        "type":       "exo",
                        "id":         e["id"],
                        "code":       code,
                        "titre":      e["titre"] or "",
                        "etat_code":  e["etat_code"] or "en_cours",
                        "nav_niveau": niveau,
                        "nav_seq":    seq_code,
                    }
                    if e["serie"] == "F":
                        exos_F.append(atome_exo)
                    elif e["serie"] == "A":
                        exos_A.append(atome_exo)
                    elif e["serie"] == "E":
                        exos_E.append(atome_exo)
                    # Les autres séries (R, EA, autres) n'apparaissent pas
                    # ici — ce sont les exos rattachés à la partie
                    # (cf. atomes_rae plus haut).

                # Fiche de résumé (via objectif_id) — on prend la première
                # si plusieurs (cas atypique non prévu par le modèle métier
                # mais on reste défensif).
                fiche_row = conn.execute("""
                    SELECT id, titre, num_fiche, etat_code
                    FROM fiches_resume
                    WHERE objectif_id = ?
                    ORDER BY num_fiche, id
                    LIMIT 1
                """, (obj_id,)).fetchone()
                if fiche_row:
                    num = fiche_row["num_fiche"]
                    code = (f"FR{int(num):02d}"
                            if num is not None else "FR??")
                    fiche = {
                        "type":       "fiche",
                        "id":         fiche_row["id"],
                        "code":       code,
                        "titre":      fiche_row["titre"] or "",
                        "etat_code":  fiche_row["etat_code"] or "en_cours",
                        "nav_niveau": niveau,
                        "nav_seq":    seq_code,
                    }

                # Comptage : tous les atomes "porteurs" (methode + fiche +
                # notions + exos F/A/E) entrent dans les stats globales
                # du niveau.
                tous_atomes = (
                    ([methode] if methode else [])
                    + ([fiche] if fiche else [])
                    + notions + exos_F + exos_A + exos_E
                )
                for a in tous_atomes:
                    total += 1
                    if a["etat_code"] == "valide":
                        valides += 1

                objectifs.append({
                    "id":        obj_id,
                    "code":      o["code"],
                    "nom":       o["nom"] or "",
                    "fin_cycle": bool(o["fin_cycle"])
                                  if o["fin_cycle"] is not None else False,
                    "est_cours": False,
                    "methode":   methode,
                    "fiche":     fiche,
                    "notions":   notions,
                    "exos_F":    exos_F,
                    "exos_A":    exos_A,
                    "exos_E":    exos_E,
                })

            # Comptage des R/EA dans les stats globales du niveau
            for a in atomes_rae:
                total += 1
                if a["etat_code"] == "valide":
                    valides += 1

            # v0.13.6.3 — Cartes d'automatisme rattachées à la partie
            #
            # Modèle de rattachement : carte → (notion|méthode) → objectif
            # → partie. Le lien est porté par cartes_automatisme.lien_id
            # qui pointe soit vers notions.id, soit vers methodes.id.
            #
            # Une carte dont la notion n'est pas (encore) rattachée à un
            # objectif n'apparaît pas dans le référentiel : c'est le
            # comportement attendu (le référentiel reflète le programme
            # effectif, càd les atomes rattachés à un objectif).
            # Idem pour les cartes méthode dont la méthode n'a pas
            # d'objectif.
            atomes_cartes = _lister_cartes_de_partie(
                conn, niveau, seq_code, partie_id
            )
            for a in atomes_cartes:
                total += 1
                if a["etat_code"] == "valide":
                    valides += 1

            parties.append({
                "id":              partie_id,
                "numero":          p["numero"],
                "nb_seances_R_AE": p["nb_seances_R_AE"] or 0,
                "atomes_rae":      atomes_rae,
                "atomes_cartes":   atomes_cartes,
                "objectifs":       objectifs,
            })

        sequences.append({
            "code":          seq_code,
            "numero":        sq["numero"],
            "nom":           sq["nom"] or "",
            "theme_couleur": sq["theme_couleur"] or "",
            "parties":       parties,
        })

    # v0.13.6.3 — Évaluations du niveau (rattachées au niveau, pas à
    # une séquence) avec leurs exos.
    evaluations = _lister_evaluations_du_niveau(conn, niveau)
    for ev in evaluations:
        for ex in ev["exos"]:
            total += 1
            if ex["etat_code"] == "valide":
                valides += 1

    return {
        "niveau":      niveau,
        "evaluations": evaluations,
        "sequences":   sequences,
        "stats": {
            "total":    total,
            "valides":  valides,
            "en_cours": total - valides,
        },
    }


# ── v0.13.6.3 — Helpers de lecture cartes & évaluations ──────────────────────


def _lister_cartes_de_partie(conn: sqlite3.Connection, niveau: str,
                             seq_code: str, partie_id: str) -> list[dict]:
    """Liste les cartes d'automatisme rattachées à une partie de séquence.

    v0.13.6.13 : la jointure passe désormais par la table de liaison
    `objectif_cartes` qui matérialise explicitement le lien carte →
    objectif. Avant : on reconstituait le lien via lien_type/lien_id
    sur cartes_automatisme + objectif_notions ou objectifs.methode_id.

    Le SELECT DISTINCT évite tout doublon si une même carte est liée à
    plusieurs objectifs d'une même partie (anticipé pour le 1:N futur
    côté carte, non observé aujourd'hui).

    Tri : par num croissant, comme dans la sidebar de l'atelier carte.
    Code court affiché : 'CA<num>' (Carte d'Automatisme).
    """
    rows = conn.execute("""
        SELECT DISTINCT c.id, c.num, c.titre, c.type_pedago, c.type_tech,
                        c.etat_code
          FROM cartes_automatisme c
          JOIN objectif_cartes oc
            ON oc.carte_id = c.id
          JOIN objectifs o
            ON o.id = oc.objectif_id
         WHERE c.niveau = ?
           AND c.sequence = ?
           AND o.partie_id = ?
      ORDER BY c.num, c.id
    """, (niveau, seq_code, partie_id)).fetchall()

    cartes = []
    for r in rows:
        num = r["num"]
        code = f"CA{int(num):02d}" if num is not None else "CA??"
        cartes.append({
            "type":        "carte",
            "id":          r["id"],
            "code":        code,
            "titre":       r["titre"] or "",
            "type_pedago": r["type_pedago"] or "",
            "type_tech":   r["type_tech"] or "",
            "etat_code":   r["etat_code"] or "en_cours",
            "nav_niveau":  niveau,
            "nav_seq":     seq_code,
        })
    return cartes


def _lister_evaluations_du_niveau(conn: sqlite3.Connection,
                                  niveau: str) -> list[dict]:
    """Liste les évaluations du niveau avec leurs exos.

    Structure retournée par éval :
        {
          "id", "numero", "titre", "etat_code", "ordre",
          "exos": [
            {"type": "exo", "id", "code", "titre", "etat_code",
             "nav_niveau", "nav_seq"},
            ...
          ]
        }

    Le `code` d'un exo d'éval est son code natif `<serie_code><num>`,
    pour cohérence avec les chips dans les séquences. L'éventuelle
    ouverture en deeplink réutilise atelier='exercice' (cible
    classique).
    """
    evs = conn.execute("""
        SELECT id, numero, titre, etat_code, ordre, mode_notation
          FROM evaluations
         WHERE niveau = ?
      ORDER BY ordre, numero, id
    """, (niveau,)).fetchall()

    result = []
    for ev in evs:
        exos = conn.execute("""
            SELECT e.id, e.titre, e.niveau, e.sequence, e.serie_code, e.num,
                   e.etat_code, ee.ordre, ee.bareme_points
              FROM evaluation_exercices ee
              JOIN exercices e ON e.id = ee.exercice_id
             WHERE ee.evaluation_id = ?
          ORDER BY ee.ordre, e.id
        """, (ev["id"],)).fetchall()
        exos_dicts = []
        for e in exos:
            serie = e["serie_code"] or "?"
            num = e["num"]
            code_court = (
                f"{serie}{int(num):02d}" if num is not None else f"{serie}??"
            )
            # Pour la navigation (deeplink), on utilise le niveau et la
            # séquence de l'exo source — un exo dans une éval reste
            # un exo de la séquence qui le contient.
            nav_niveau = e["niveau"] or niveau
            nav_seq    = e["sequence"] or ""
            exos_dicts.append({
                "type":       "exo",
                "id":         e["id"],
                "code":       code_court,
                "titre":      e["titre"] or "",
                "etat_code":  e["etat_code"] or "en_cours",
                "nav_niveau": nav_niveau,
                "nav_seq":    nav_seq,
            })
        result.append({
            "id":            ev["id"],
            "numero":        ev["numero"],
            "titre":         ev["titre"] or "",
            "etat_code":     ev["etat_code"] or "en_cours",
            "ordre":         ev["ordre"],
            "mode_notation": ev["mode_notation"] or "",
            "exos":          exos_dicts,
        })
    return result
