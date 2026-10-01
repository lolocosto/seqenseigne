# Redémarrage v0.41.3 — Nettoyage (fin de la revue des dettes)

Quatrième et dernière livraison de la revue des dettes (v0.41.x).

## Contenu

- **Outil obsolète supprimé** : `outils/migrer_edt_groupe_usage.py` (v0.20.2),
  inutilisable depuis le schéma de l'EdT v0.38. Suppression manuelle :
  `MANIFEST_SUPPRESSIONS.md` (et sur GitHub). Le commentaire de migration qui
  le citait dans `persistence/sqlite_store.py` est mis à jour.
- **Libellés LaTeX des niveaux** : l'audit a montré que la dette annoncée
  (`_NOM_COURT_NIVEAU` de `livret_sequence.py`) était déjà soldée depuis
  v0.13.1 (`param_niveaux.lire_nom_court_latex`). En revanche, la table
  `{'N09': '6\ieme{}', …}` était recopiée à l'identique dans **7 modules**
  (livret_cartes_recap, livret_cartes_planches, livret_recap_exos,
  livret_fiches, livret_recap_cours, livret_corriges, livret_plans_de_travail).
  Elle devient une constante unique `param_niveaux.LIBELLES_NIVEAUX_LATEX`,
  importée sous les mêmes noms qu'avant : rendu LaTeX inchangé. Constante
  plutôt que lecture en base pour rester identique même sur une base où
  `param_niveaux` n'est pas peuplée.
- **Tests du parseur sur le paquet réel** :
  `tests/test_paquet_parseur.py::TestIntegration` cherche maintenant
  `seqenseigne-core.sty` dans `appli/../reference/paquet` (ou
  `reference/paquet/paquet`) au lieu d'un chemin absolu d'un ancien
  environnement. Ignorés sur un clone GitHub.
- **`doc/ETAT_COURANT.md` remis au propre** : chantiers terminés, règles à
  respecter issues de la revue, dettes restantes (mineures).

## Tests

- pytest `tests/test_v0_41_3_nettoyage.py` (10) : valeurs historiques de la
  table, partage par les 7 modules, plus aucune copie, outil supprimé.
- Suite complète : pytest 0 échec ; vitest 220 réussis.
- Contrôle local à faire : `pytest tests/test_paquet_parseur.py -rs` ne doit
  plus afficher « Paquet LaTeX non disponible » si `seqenseigne-core.sty` est
  bien dans `reference/paquet`.
