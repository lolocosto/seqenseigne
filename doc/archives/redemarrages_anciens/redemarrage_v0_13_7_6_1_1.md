# Redémarrage v0.13.7.6.1.1 — Correctifs ciblés (carte + script méthodes)

## Contexte

Suite au déploiement de v0.13.7.6.1, trois retours d'usage. Deux sont
traités dans cette livraison ; un est reporté à v0.13.7.6.1.2.

## Cadrage validé

### Point 1 — Tableau « pas mieux » (REPORTÉ v0.13.7.6.1.2)

| Question | Réponse |
|---|---|
| État du JS livré chez Laurent | Bien à v0.13.7.6.1 (vérifié via LISEZ_MOI déployé) |
| État du HTML rendu | Les boutons stepper [−] [+] sont bien dans le DOM (capture DOM inspecteur) |
| Diagnostic | Thème système Firefox/Windows écrase les couleurs et textes des `<button>` natifs (même cause que le slider initial) |
| Solution prévue | v0.13.7.6.1.2 : forcer `appearance: none` + couleurs en valeurs absolues sans variables CSS |
| Capture jointe | Inspecteur DOM : DOM correct, rendu visuel cassé |

### Point 2 — Carte : iframe résiduelle

| Question | Réponse |
|---|---|
| Symptôme | Passage carte A compilée → carte B non compilée : PDF de A reste affiché |
| Cause | `verifierCacheEtAfficher` (v0.13.7.6.1) sortait silencieusement quand cache invalide, sans nettoyer l'UI |
| Portée correctif | Juste nettoyer l'iframe (pas étendu à clic sidebar ou zone erreur) |
| Comportement attendu | Remettre placeholder + masquer iframe + libérer blob URL + vider status |

### Point 3 — Méthodes orphelines

| Question | Réponse |
|---|---|
| Tables traitées | `objectifs_v2` uniquement (v1 reste orpheline) |
| Critère matching | Égalité stricte (TRIM) sur `methodes.titre == objectifs_v2.nom` + même (niveau, séquence) |
| Cas multiples candidats | Ne rien faire, lister en sortie (catégorie "ambigu") |
| Cas conflits (methode_id déjà posé) | Ne rien faire, lister en sortie |
| Sécurité avant modif | Modification directe avec sauvegarde `.bak` automatique |
| Workstream v1→v2 | Ajouté à v0.14 (admin refactor + cleanup) |

## Modifications

### Point 2 — `atelier_atomique.js`

`verifierCacheEtAfficher()` :
- Quand `resp.ok === false` (4xx/5xx) → appelle `_remettrePlaceholderRendu()` au lieu de retourner silencieusement
- Quand `data.cache_valide !== true` → appelle `_remettrePlaceholderRendu()` au lieu de retourner silencieusement
- En cas d'exception réseau → idem dans le `catch`

Nouvelle méthode `_remettrePlaceholderRendu()` :
- Masque l'iframe (`display: none`)
- Libère le `blob:` URL précédent via `URL.revokeObjectURL(iframe.src)` si c'en était un
- `iframe.removeAttribute('src')` pour purger le contenu
- Vide la zone d'erreur (`display: none`, `innerHTML = ''`)
- Vide le texte de status
- Réaffiche le placeholder

Cette méthode est aussi appelable manuellement si besoin futur (par
exemple à un clic dans la sidebar de liste — pas câblé pour cette
livraison, mais le code est prêt).

### Point 3 — `scripts/migrer_methodes_objectifs.py`

Le script existait déjà (v0.12.4) et faisait tout le travail demandé.
Seul ajout : option `--backup`.

Nouveau flag CLI :
```
--backup    Crée un fichier <db>.bak.<timestamp> avant l'application
            (uniquement actif avec --apply). Permet un rollback manuel
            après commit en cas de problème détecté plus tard.
```

Implémentation :
```python
if args.backup:
    from datetime import datetime
    import shutil
    horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
    chemin_bak = args.db.with_name(f"{args.db.name}.bak.{horodatage}")
    shutil.copy2(args.db, chemin_bak)
    print(f"Sauvegarde créée : {chemin_bak}")
```

`shutil.copy2` est utilisé pour préserver les métadonnées (mtime,
mode) — pratique si tu veux corréler la date du `.bak` avec la date
de l'exécution.

Le code retour est 3 (erreur SQL/IO) si la sauvegarde échoue (IOError,
disque plein, permission denied, etc.).

### Workstream v0.14 — Migration v1→v2 + suppression v1

Documenté pour mémoire :

**Périmètre** : retirer définitivement la table `objectifs` (v1) du
schéma SQLite.

**Préalables identifiés (5+ fichiers à réécrire)** :

| Fichier | Usage actuel | Migration cible |
|---|---|---|
| `services/latex_rendu_atome.py` (l. 599, 607) | `seqObjectifGetNom`, `seqObjectifGetFinCycle` lus depuis v1 | Réécrire sur v2 via jointure `objectifs_v2 → partie → sequence_par_niveau` |
| `services/edition_progression.py` (l. 84) | Lecture progression par (niveau, sequence, code) | Idem |
| `services/sequences_du_cycle.py` (l. 146) | Stats COUNT par séquence | Idem |
| `services/scanner_vers_v2.py` (l. 183, 435) | Migration v1→v2 elle-même | À garder pour l'exécution finale puis supprimer |
| `persistence/sqlite_store.py` (l. 57, 94, 207, 209, 294) | Tracking de migration | Garder la suppression de table |

**Étapes** :
1. v0.14.x.a : réécrire les 5 services pour lire `objectifs_v2`
2. v0.14.x.b : exécuter `scanner_vers_v2` une dernière fois sur la BDD prod
3. v0.14.x.c : vérifier qu'aucun objectif v1 n'est plus accédé en runtime (logs, tests)
4. v0.14.x.d : `DROP TABLE objectifs` + nettoyage schema.sql
5. v0.14.x.e : retirer `scanner_vers_v2.py` du build (ou garder pour audit)

**Risque** : non-trivial. Touche au rendu PDF (latex_rendu_atome). À
mener avec tests massifs de non-régression.

## Fichiers livrés

```
MODIFIÉS
  appli/static/atelier_atomique.js              (point 2)
  appli/scripts/migrer_methodes_objectifs.py    (point 3 : --backup, v0.13.7.6.1.1)
  appli/tests/test_migrer_methodes_objectifs.py (4 nouveaux tests TestBackup)

NOUVEAUX
  appli/doc/redemarrage_v0_13_7_6_1_1.md        (ce document)
```

## Vérifs

- pytest : **3360 passed, 5 skipped, 0 failed** (3356 baseline + 4 nouveaux)
- `node --check` sur atelier_atomique.js : OK
- `python -c "import ast; ast.parse(...)"` sur le script : OK
- `python -m scripts.migrer_methodes_objectifs --help` : `--backup` listé dans l'aide

## Scénarios à valider chez toi

### A — Iframe résiduelle (point 2)

1. Ouvrir atelier Carte d'automatisme.
2. Choisir une carte A, basculer onglet Rendu PDF.
3. Cliquer « Compiler le rendu » — un PDF s'affiche.
4. Cliquer dans la sidebar sur une carte B qui n'a jamais été compilée.
5. Basculer sur l'onglet Rendu PDF de B.
6. **Vérifier** : le PDF de la carte A n'est plus visible. À la place,
   le placeholder « Cliquer sur Compiler le rendu… » est affiché.
7. **Vérifier** : le statut « ✓ PDF servi depuis le cache » de A a
   disparu.

### B — Rattachement méthodes ↔ objectifs

1. Ouvrir un terminal dans le dossier `appli/`.
2. Lancer le dry-run :
   ```
   python -m scripts.migrer_methodes_objectifs --verbose
   ```
3. **Vérifier** : récap par catégorie (`a_lier`, `deja_ok`, `conflit`,
   `ambigu`, `sans_match`, `cours_ignores`). Note le nombre `a_lier`.
4. Si tu veux filtrer (ex. juste N10) :
   ```
   python -m scripts.migrer_methodes_objectifs --niveau N10 --verbose
   ```
5. Application avec backup :
   ```
   python -m scripts.migrer_methodes_objectifs --apply --backup
   ```
6. Taper `OUI` à la confirmation.
7. **Vérifier** dans la sortie :
   - Ligne « Sauvegarde créée : data/seqenseigne.db.bak.YYYYMMDD_HHMMSS »
   - Ligne « Migration appliquée : N objectif(s) liés. »
8. **Vérifier** dans le dossier `data/` que le fichier `.bak` existe.
9. **Vérifier** dans l'appli que tes méthodes apparaissent maintenant
   bien liées à leurs objectifs (atelier d'assemblage, livret de
   séquence, etc.).
10. Si problème détecté plus tard :
    ```
    cp data/seqenseigne.db.bak.YYYYMMDD_HHMMSS data/seqenseigne.db
    ```
    (Arrêter Flask d'abord, redémarrer après.)

### C — Tableau (REPORTÉ v0.13.7.6.1.2)

Pas de test à faire dans cette livraison. Le bug reste identique :
boutons stepper invisibles dans la modale tableau, à corriger dans la
livraison suivante.

## Prochaine étape : v0.13.7.6.1.2

Patch CSS « force-everything » pour le générateur de tableau :
- `.ed-latex-tab-stepper-btn { appearance: none; -webkit-appearance: none; -moz-appearance: none; }`
- Couleurs en valeurs absolues : `background: #ffffff; color: #222222; border-color: #cccccc;` (pas de variables CSS)
- Test que les boutons « − » et « + » s'affichent visiblement et que le « ×N » est lisible
- Possible aussi : remplacer les `<button>` par des `<a>` ou `<span role=button>` pour échapper totalement à l'apparence native

Sans nouveau retour, ces patches sont à l'aveugle. Une vérification
visuelle par capture sera nécessaire après déploiement.

## Prochaine étape après v0.13.7.6.1.2

v0.13.7.6.2 — extension de l'auto-chargement aux 4 autres ateliers
à rendu PDF (Exercice, Notion, Méthode, Fiche), création du module
commun `rendu_pdf_commun.js`, et suppression des fonctions globales
`rendreAtome*` (cf. roadmap v0.13.7.6.1).
