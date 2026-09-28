"""Tests v0.13.7.1 — Service `paquet_expose` et route /api/paquet/definitions.

Ces tests s'appuient sur la base de production telle qu'elle est sur le
poste de Laurent. Le contenu exact de `paquet_definitions` étant lié à
la dernière compilation du paquet .dtx, on teste plutôt les propriétés
structurelles (filtrage, types, format) que des valeurs précises.
"""
import json
import pytest

from services.paquet_expose import (
    FICHIERS_EXPOSES,
    TYPES_EXPOSES,
    MACROS_STRUCTURELLES,
    lister_definitions,
)


@pytest.fixture
def app_avec_paquet(app):
    """L'app standard plus la table paquet_definitions vide (créée à la
    main parce qu'elle est normalement peuplée par scripts/peuplement_*
    au moment de l'import du paquet .dtx ; les tests ne déclenchent pas
    ce script).
    """
    with app.json_store._conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS paquet_definitions (
                nom               TEXT PRIMARY KEY,
                type_latex        TEXT NOT NULL,
                args_spec         TEXT NOT NULL DEFAULT '',
                corps             TEXT NOT NULL DEFAULT '',
                corps_fin         TEXT NOT NULL DEFAULT '',
                texte_complet     TEXT NOT NULL,
                fichier_source    TEXT NOT NULL,
                ligne_debut       INTEGER NOT NULL,
                macros_appelees          TEXT NOT NULL DEFAULT '[]',
                environnements_utilises  TEXT NOT NULL DEFAULT '[]',
                statut_rendu_atome       TEXT NOT NULL DEFAULT 'reutilise',
                contenu_atome            TEXT NOT NULL DEFAULT ''
            );
        """)
        conn.commit()
    return app


@pytest.fixture
def client_avec_paquet(app_avec_paquet):
    return app_avec_paquet.test_client()


class TestPaquetExposeService:
    """Tests directs du service (sans Flask)."""

    def test_constantes_publiques(self):
        # Ces clés sont attendues par la note de redémarrage v0.13.7.1
        # et par les tests aval — ne pas changer sans révision conjointe
        # du frontend.
        assert 'seqenseigne-core.sty' in FICHIERS_EXPOSES
        assert 'seqenseigne-theme.sty' in FICHIERS_EXPOSES
        assert 'seqenseigne-core-exos.sty' in FICHIERS_EXPOSES
        assert 'seqenseigne-carte-automatisme.sty' in FICHIERS_EXPOSES
        # data/legacy/core-eval intentionnellement non exposés
        assert 'seqenseigne-data.sty' not in FICHIERS_EXPOSES
        assert 'seqenseigne-legacy.sty' not in FICHIERS_EXPOSES
        assert 'seqenseigne-core-eval.sty' not in FICHIERS_EXPOSES

        assert TYPES_EXPOSES == {'command', 'environment', 'tcolorbox'}

    def test_lister_definitions_structure_de_base(self, app_avec_paquet):
        """Avec une BdD vide (cas test), la structure reste cohérente :
        les fichiers exposés sont tous présents même sans définitions."""
        with app_avec_paquet.json_store._conn() as conn:
            res = lister_definitions(conn)
        assert "fichiers" in res
        assert isinstance(res["fichiers"], list)
        # Tous les fichiers exposés sont listés, dans l'ordre déclaré
        noms = [f["nom"] for f in res["fichiers"]]
        assert noms == list(FICHIERS_EXPOSES.keys())
        # Chaque fichier a la même structure
        for f in res["fichiers"]:
            assert "nom" in f and "label" in f
            assert "commands" in f and isinstance(f["commands"], list)
            assert "environments" in f and isinstance(f["environments"], list)
            assert "tcolorbox" in f and isinstance(f["tcolorbox"], list)
            assert f["label"] == FICHIERS_EXPOSES[f["nom"]]

    def test_lister_definitions_filtre_internes(self, app_avec_paquet):
        """Les macros internes (nom contenant '@') ne doivent jamais
        apparaître dans le résultat."""
        # Injecte une définition publique et une interne pour tester
        with app_avec_paquet.json_store._conn() as conn:
            conn.execute(
                "INSERT INTO paquet_definitions "
                "(nom, type_latex, args_spec, texte_complet, fichier_source, ligne_debut) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ('\\seqTestPublic', 'command', '[1]', '',
                 'seqenseigne-core.sty', 1),
            )
            conn.execute(
                "INSERT INTO paquet_definitions "
                "(nom, type_latex, args_spec, texte_complet, fichier_source, ligne_debut) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ('\\seq@test@interne', 'command', '', '',
                 'seqenseigne-core.sty', 2),
            )
            conn.commit()
            res = lister_definitions(conn)

        coeur = next(f for f in res["fichiers"]
                     if f["nom"] == 'seqenseigne-core.sty')
        noms_commands = [c["nom"] for c in coeur["commands"]]
        assert '\\seqTestPublic' in noms_commands
        assert '\\seq@test@interne' not in noms_commands

    def test_lister_definitions_filtre_types(self, app_avec_paquet):
        """Les types `cmdkey`, `counter`, `columntype`, `if` ne sont
        jamais exposés."""
        with app_avec_paquet.json_store._conn() as conn:
            for type_ in ('cmdkey', 'counter', 'columntype', 'if'):
                conn.execute(
                    "INSERT INTO paquet_definitions "
                    "(nom, type_latex, args_spec, texte_complet, "
                    " fichier_source, ligne_debut) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (f'\\seqType{type_}', type_, '', '',
                     'seqenseigne-core.sty', 1),
                )
            conn.commit()
            res = lister_definitions(conn)
        coeur = next(f for f in res["fichiers"]
                     if f["nom"] == 'seqenseigne-core.sty')
        # Aucune des 4 définitions ajoutées ne doit apparaître nulle part
        tous_noms = (
            [c["nom"] for c in coeur["commands"]]
            + [e["nom"] for e in coeur["environments"]]
            + [t["nom"] for t in coeur["tcolorbox"]]
        )
        for type_ in ('cmdkey', 'counter', 'columntype', 'if'):
            assert f'\\seqType{type_}' not in tous_noms

    def test_lister_definitions_ignore_fichiers_non_exposes(self, app_avec_paquet):
        """Les fichiers data/legacy/core-eval ne sont pas dans la
        sortie même s'ils contiennent des définitions publiques."""
        with app_avec_paquet.json_store._conn() as conn:
            conn.execute(
                "INSERT INTO paquet_definitions "
                "(nom, type_latex, args_spec, texte_complet, "
                " fichier_source, ligne_debut) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ('\\seqDataPublic', 'command', '', '',
                 'seqenseigne-data.sty', 1),
            )
            conn.commit()
            res = lister_definitions(conn)
        # data.sty n'est pas dans la sortie
        noms_fichiers = [f["nom"] for f in res["fichiers"]]
        assert 'seqenseigne-data.sty' not in noms_fichiers

    def test_lister_definitions_classification_par_type(self, app_avec_paquet):
        """commands, environments et tcolorbox sont rangés dans la
        bonne clé selon leur type_latex."""
        with app_avec_paquet.json_store._conn() as conn:
            conn.execute(
                "INSERT INTO paquet_definitions "
                "(nom, type_latex, args_spec, texte_complet, "
                " fichier_source, ligne_debut) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ('\\seqUneCommande', 'command', '[2]', '',
                 'seqenseigne-core.sty', 1),
            )
            conn.execute(
                "INSERT INTO paquet_definitions "
                "(nom, type_latex, args_spec, texte_complet, "
                " fichier_source, ligne_debut) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ('seqUnEnvironnement', 'environment', '[1]', '',
                 'seqenseigne-core.sty', 2),
            )
            conn.execute(
                "INSERT INTO paquet_definitions "
                "(nom, type_latex, args_spec, texte_complet, "
                " fichier_source, ligne_debut) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ('seqUneBoite', 'tcolorbox', '', '',
                 'seqenseigne-theme.sty', 3),
            )
            conn.commit()
            res = lister_definitions(conn)
        coeur = next(f for f in res["fichiers"]
                     if f["nom"] == 'seqenseigne-core.sty')
        theme = next(f for f in res["fichiers"]
                     if f["nom"] == 'seqenseigne-theme.sty')
        assert any(c["nom"] == '\\seqUneCommande'
                   for c in coeur["commands"])
        assert any(e["nom"] == 'seqUnEnvironnement'
                   for e in coeur["environments"])
        assert any(t["nom"] == 'seqUneBoite'
                   for t in theme["tcolorbox"])

    def test_lister_definitions_args_spec_preserve(self, app_avec_paquet):
        """args_spec doit être propagé tel quel (ou vide si null)."""
        with app_avec_paquet.json_store._conn() as conn:
            conn.execute(
                "INSERT INTO paquet_definitions "
                "(nom, type_latex, args_spec, texte_complet, "
                " fichier_source, ligne_debut) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ('\\seqAvecSpec', 'command', '[2][def]', '',
                 'seqenseigne-core.sty', 1),
            )
            conn.commit()
            res = lister_definitions(conn)
        coeur = next(f for f in res["fichiers"]
                     if f["nom"] == 'seqenseigne-core.sty')
        cmd = next(c for c in coeur["commands"]
                   if c["nom"] == '\\seqAvecSpec')
        assert cmd["args_spec"] == '[2][def]'


class TestPaquetRoute:
    """Tests HTTP de la route."""

    def test_route_status_200(self, client_avec_paquet):
        rep = client_avec_paquet.get('/api/paquet/definitions')
        assert rep.status_code == 200

    def test_route_structure_minimale(self, client_avec_paquet):
        rep = client_avec_paquet.get('/api/paquet/definitions')
        data = rep.get_json()
        assert "fichiers" in data
        assert isinstance(data["fichiers"], list)
        # Les 4 fichiers exposés sont présents, dans l'ordre
        noms = [f["nom"] for f in data["fichiers"]]
        assert noms == [
            'seqenseigne-core.sty',
            'seqenseigne-theme.sty',
            'seqenseigne-core-exos.sty',
            'seqenseigne-carte-automatisme.sty',
        ]


# ── v0.13.7.2.1 — Filtre des macros structurelles ──────────────────────────

class TestPaquetStructurellesService:
    """Tests du filtrage des macros structurelles côté service."""

    def test_constantes_structurelles(self):
        """Les macros emblématiques sont bien listées comme structurelles."""
        # Échantillon : doit contenir au moins ces macros critiques.
        assert 'seqExercice' in MACROS_STRUCTURELLES
        assert 'seqNotion' in MACROS_STRUCTURELLES
        assert 'seqMethode' in MACROS_STRUCTURELLES
        assert '\\seqCorrige' in MACROS_STRUCTURELLES
        assert '\\seqRemediation' in MACROS_STRUCTURELLES
        assert '\\seqCadreReponse' in MACROS_STRUCTURELLES
        assert '\\seqCarteAuto' in MACROS_STRUCTURELLES
        assert 'seqBoiteContenuFlashcard' in MACROS_STRUCTURELLES

    def test_filtre_defaut_exclut_structurelles(self, app_avec_paquet):
        """Sans paramètre, lister_definitions exclut les macros structurelles."""
        with app_avec_paquet.json_store._conn() as conn:
            # Inject une struct et une non-struct dans le même fichier
            conn.execute(
                "INSERT INTO paquet_definitions "
                "(nom, type_latex, args_spec, texte_complet, fichier_source, ligne_debut) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ('seqExercice', 'environment', '[1][]', '',
                 'seqenseigne-core-exos.sty', 1),
            )
            conn.execute(
                "INSERT INTO paquet_definitions "
                "(nom, type_latex, args_spec, texte_complet, fichier_source, ligne_debut) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ('seqDefinition', 'environment', '[2]', '',
                 'seqenseigne-core.sty', 1),
            )
            conn.commit()
            res = lister_definitions(conn)

        # seqDefinition est dans le bloc Cœur, environnements
        coeur = next(f for f in res["fichiers"]
                     if f["nom"] == 'seqenseigne-core.sty')
        envs_coeur = [e["nom"] for e in coeur["environments"]]
        assert 'seqDefinition' in envs_coeur, "macro non-structurelle doit être présente"

        # seqExercice (structurelle) doit être absente
        exos = next(f for f in res["fichiers"]
                    if f["nom"] == 'seqenseigne-core-exos.sty')
        envs_exos = [e["nom"] for e in exos["environments"]]
        assert 'seqExercice' not in envs_exos, "macro structurelle doit être filtrée par défaut"

    def test_inclure_structurelles_true_affiche_tout(self, app_avec_paquet):
        """Avec inclure_structurelles=True, tout est exposé."""
        with app_avec_paquet.json_store._conn() as conn:
            conn.execute(
                "INSERT INTO paquet_definitions "
                "(nom, type_latex, args_spec, texte_complet, fichier_source, ligne_debut) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ('seqExercice', 'environment', '[1][]', '',
                 'seqenseigne-core-exos.sty', 1),
            )
            conn.commit()
            res = lister_definitions(conn, inclure_structurelles=True)

        exos = next(f for f in res["fichiers"]
                    if f["nom"] == 'seqenseigne-core-exos.sty')
        envs_exos = [e["nom"] for e in exos["environments"]]
        assert 'seqExercice' in envs_exos


class TestPaquetStructurellesRoute:
    """Tests du paramètre ?inclure_structurelles=1 côté route HTTP."""

    def _seed_struct(self, app_avec_paquet):
        with app_avec_paquet.json_store._conn() as conn:
            conn.execute(
                "INSERT INTO paquet_definitions "
                "(nom, type_latex, args_spec, texte_complet, fichier_source, ligne_debut) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ('seqExercice', 'environment', '[1][]', '',
                 'seqenseigne-core-exos.sty', 1),
            )
            conn.commit()

    def test_route_sans_param_filtre(self, app_avec_paquet, client_avec_paquet):
        self._seed_struct(app_avec_paquet)
        rep = client_avec_paquet.get('/api/paquet/definitions')
        assert rep.status_code == 200
        data = rep.get_json()
        exos = next(f for f in data["fichiers"]
                    if f["nom"] == 'seqenseigne-core-exos.sty')
        envs_exos = [e["nom"] for e in exos["environments"]]
        assert 'seqExercice' not in envs_exos

    def test_route_param_1_affiche_tout(self, app_avec_paquet, client_avec_paquet):
        self._seed_struct(app_avec_paquet)
        rep = client_avec_paquet.get(
            '/api/paquet/definitions?inclure_structurelles=1'
        )
        assert rep.status_code == 200
        data = rep.get_json()
        exos = next(f for f in data["fichiers"]
                    if f["nom"] == 'seqenseigne-core-exos.sty')
        envs_exos = [e["nom"] for e in exos["environments"]]
        assert 'seqExercice' in envs_exos

    def test_route_param_0_filtre(self, app_avec_paquet, client_avec_paquet):
        """?inclure_structurelles=0 doit filtrer (équivalent à pas de param)."""
        self._seed_struct(app_avec_paquet)
        rep = client_avec_paquet.get(
            '/api/paquet/definitions?inclure_structurelles=0'
        )
        data = rep.get_json()
        exos = next(f for f in data["fichiers"]
                    if f["nom"] == 'seqenseigne-core-exos.sty')
        envs_exos = [e["nom"] for e in exos["environments"]]
        assert 'seqExercice' not in envs_exos
