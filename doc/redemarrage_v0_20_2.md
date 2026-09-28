# Redémarrage v0.20.2 — EdT : tri, demi-largeur A/B, séparation groupe/usage

Trois corrections/évolutions de l'écran EdT (v0.20.1) suite aux retours d'usage.

## 1. Tri des créneaux par heure de début

Grille horaire et EdT trient désormais les créneaux par **heure de début
croissante** (au lieu de l'ordre d'insertion). Un créneau ajouté après coup
(ex. M5 12:35–12:50) se place au bon endroit (entre M4 et S1), pas en fin de
journée.

- `services/grille_horaire.lister` : `ORDER BY heure_debut, ordre, code`.
- L'EdT s'appuie sur cet ordre (il consomme la grille telle que listée).

## 2. Demi-cases A/B en demi-LARGEUR

Les créneaux différenciés semaine A / B s'affichent maintenant **côte à côte**
(A à gauche, B à droite, séparés d'un trait), et non plus l'un au-dessus de
l'autre. Cela traduit mieux l'idée « une semaine puis l'autre » plutôt que
« deux moitiés de séance ». Une case « toutes semaines » (AB) reste pleine.

## 3. Séparation groupe / usage

L'ancien champ `usage` mélangeait deux notions. Il est scindé en deux :

- **groupe** (à QUI on fait cours) : `classe_entiere` (défaut), `demi_classe_A`,
  `demi_classe_B`, `groupe_option`, `groupe_horaire_ordinaire`, `autre`
  (précisé au libellé).
- **usage** (CE QU'ON fait) : `cours` (défaut), `vie_de_classe`,
  `co_animation`, `autre` (précisé au libellé).

**Comptage pour les progressions** : une séance compte si `groupe=classe_entiere`
**et** `usage=cours` (un cours en classe entière). Une vie de classe, une
co-animation, un groupe, etc. ne comptent pas.

Le popover d'édition a désormais deux sélecteurs distincts (Groupe, Usage).

### Migration des données existantes

Nouvelle colonne `groupe` (migration de schéma idempotente, ajoutée au premier
lancement). Les cases déjà saisies gardent `groupe='classe_entiere'` par défaut
tant qu'on ne les reventile pas.

Un script **à lancer soi-même** reventile l'existant d'après l'ancien `usage`
et le libellé :

```
python -m outils.migrer_edt_groupe_usage            # aperçu (dry-run)
python -m outils.migrer_edt_groupe_usage --apply    # applique
```

Règles : ancien `groupe_horaire_ordinaire`/`groupe_option`/`demi_classe_*` →
groupe correspondant + usage `cours` ; libellé « Co-animation… » → usage
`co_animation` ; « Vie de classe » → `vie_de_classe` ; « Concertation… » →
usage `autre` ; sinon `cours`. Idempotent ; tester sur copie d'abord.

## Fichiers

- `persistence/sqlite_store.py` : colonne `groupe` (migration idempotente).
- `services/edt.py` : constantes `GROUPES`/`USAGES` redéfinies,
  `GROUPES_COMPTES`/`USAGES_COMPTES`, helper `est_compte`, `groupe` dans
  ajouter/modifier/lister, comptage sur groupe+usage.
- `services/grille_horaire.py` : tri par heure de début.
- `routes/edt.py` : expose `groupes`/`groupes_comptes`, passe `groupe`.
- `routes/projection.py`, `routes/affectation.py` : filtre `est_compte`.
- `static/edt.js` : demi-largeur A/B, sélecteur Groupe + Usage, comptage
  groupe+usage.
- `outils/migrer_edt_groupe_usage.py` (nouveau) : reventilation.
- `tests/test_v0_19_1_17_edt.py` : adapté au modèle groupe/usage.

## Tests

- pytest ciblé (edt + grille + projection + affectation) : 29 passed, 0
  régression.
- vitest : 187 passed. Syntaxe edt.js OK.
- Vérifié : tri (M5 bien placé), comptage (seul cours classe entière compté),
  validations groupe/usage, reventilation testée sur une copie de la base réelle
  (concertation/vie de classe/co-animation/CEC correctement répartis).

## Déploiement

1. Décompresser ; `python -m outils.verifier_md5`.
2. Lancer le serveur une fois (ajoute la colonne `groupe`).
3. `python -m outils.migrer_edt_groupe_usage --apply` pour reventiler l'EdT déjà
   saisi.

Note : un doublon a été repéré dans l'EdT réel (lun S1 B en double) — sans
incidence sur la migration, mais à nettoyer manuellement dans l'UI si c'est une
erreur de saisie.

## Suite

- Raffinement visuel de l'EdT si souhaité.
- v0.21.x : utilisation des automatismes (ordonnancement Leitner).
