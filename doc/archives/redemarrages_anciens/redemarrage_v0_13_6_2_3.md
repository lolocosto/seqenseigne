# Redémarrage v0.13.6.2.3

**Session du 12 mai 2026 — Peuplement cartes d'automatisme N10**

---

## Contexte

Suite directe de **v0.13.6.2.2** (chaîne carte fonctionnelle validée
par Laurent). Cette session porte sur le **peuplement BDD** de cartes
d'automatisme pour le niveau N10 (5ème), toutes séquences S01 à S14.

À l'entrée de session : 1 seule carte existait (`crt_756ac269b576`,
N10/S01/num=1, "Ecriture décimale <-> Ecriture fractionnaire", `valide`,
créée par Laurent en validation manuelle).

---

## Demande et scoping

Demande initiale : étendre les 17 propositions de cartes N10/S01
(rédigées dans `propositions_cartes_N10_S01.md` lors de la session
précédente) aux 13 autres séquences de N10, et insérer toutes les cartes
directement en BDD à l'état `valide`.

Trois questions de scoping (validées par Laurent) :

1. **Périmètre** : toutes les 14 séquences, malgré que la majorité
   des notions/méthodes soient encore à l'état `en_cours` (Laurent les
   considère correctes, il n'a juste pas eu le temps de tout valider
   formellement).
2. **Validation** : insertion directe à l'état `valide`, sans relecture
   préalable par Laurent. Il corrigera à l'usage.
3. **Densité** : à la discrétion de Claude, varie selon la richesse
   pédagogique de chaque séquence.

Laurent a aussi signalé un besoin de **fonctionnalité multisélection
+ menu contextuel** pour valider plus rapidement notions/méthodes/cartes
en lot. À ajouter en roadmap longue, à rediscuter en session dédiée.

---

## Réalisé

### Module de données

`appli/scripts/cartes_n10_data.py` (~1500 lignes) :
- 122 cartes définies en Python pur (dict)
- Format `{sequence, nom, type_pedago, type_tech, lien, recto, verso, variables}`
- Lien défini en tuple `(lien_type, num)` — pas d'ID `no_xxx`/`me_xxx`
  codé en dur (résolu dynamiquement par le script)
- Constante `TOUTES_CARTES_N10` + `COMPTE_PAR_SEQUENCE`
- 14 sous-listes nommées `CARTES_S01` à `CARTES_S14`

Décompte par séquence :

| Séquence | Cartes | | Séquence | Cartes |
|---|---|---|---|---|
| S01 | 17 | | S08 |  8 |
| S02 |  7 | | S09 |  3 |
| S03 | 10 | | S10 | 14 |
| S04 | 10 | | S11 |  7 |
| S05 |  8 | | S12 | 13 |
| S06 |  7 | | S13 |  6 |
| S07 |  7 | | S14 |  5 |

Total : **122 cartes ajoutées**, soit **123 en BDD** avec la carte
existante.

Répartition pédagogique : 42 def, 32 propriété, 34 calcul, 11 procédure,
4 reconnaissance. Répartition technique : 90 fixe, 33 paramétrée.

### Script de peuplement

`appli/scripts/peupler_cartes_n10.py` :
- CLI avec `--dry-run`, `--force`, `--db <path>`
- Pour chaque carte : résout `lien_id` via `(niveau, sequence, num)`,
  appelle `services.cartes_automatisme.creer_carte`, puis `valider_carte`
- Idempotent : skip si une carte avec le même `(niveau, sequence, nom)`
  existe déjà
- Rapport final par séquence : `créées | sautées | erreurs`

### Tests

`appli/tests/test_v0_13_6_2_3_peuplement_cartes_n10.py` :
- 1 test paramétré par carte × 5 contrôles (champs requis, types
  valides, recto/verso non vides, paramétrée ⇒ variables, format lien)
- 1 test global unicité des noms par séquence
- 1 test cohérence `COMPTE_PAR_SEQUENCE` vs listes
- 3 tests d'intégration : peuplement BDD jetable, idempotence, dry-run

**739 tests passent**. Suite complète : **3111 passed, 5 skipped**
(= 2372 baseline + 739 nouveaux). Zéro régression.

---

## Découvertes techniques

### Conventions xint réelles (rectifiées en cours de session)

À la rédaction initiale du MD S01 j'avais utilisé `\xinttheiiexpr ... \relax`
pour afficher. **C'était inhabituel dans ton code** : tes exercices N10
utilisent en réalité :

- `\xintiieval{nomvar}` pour afficher un entier
- `\xintfloateval{nomvar}` pour afficher un flottant
- Souvent enrobé de `\num{...}` (siunitx) pour le formatage français

J'ai rectifié les 17 propositions S01 + utilisé cette syntaxe correcte
pour toutes les nouvelles cartes S02-S14.

Préfixe de variable choisi : `N10S<seq>C<num>_<role>` — `C` pour Carte,
miroir des préfixes `A/F/E` des exos. Évite toute collision sur une
future planche A4 mixte.

### Bug format `num_connaissance` vs `num_methode`

Découvert en dry-run : **67 erreurs « Lien introuvable » uniquement sur
les notions**, aucune sur les méthodes.

**Cause** : dans ta BDD,
- `notions.num_connaissance` est en **TEXT zero-padded** (`'01'`, `'02'`, ..., `'13'`)
- `methodes.num_methode` est en **INTEGER**

Le `WHERE num_connaissance = 1` ne matche pas `'01'` à cause du
padding zéro.

**Fix** dans `resoudre_lien_id` :
```python
WHERE (num_connaissance = ? OR num_connaissance = ?)
# binding : (lien_num, f"{lien_num:02d}")
```
Même protection symétrique appliquée à `num_methode` au cas où l'import
évoluerait.

**À noter pour roadmap** : ce genre d'hétérogénéité de format selon les
imports est exactement le terrain du chantier infra-de-test prévu
post v0.13.6. Un test d'intégrité de schéma qui vérifie le type SQLite
de chaque colonne attraperait ce genre de divergence avant qu'elle ne
pollue les services.

---

## Validation finale

- Dry-run sur sandbox : 122 cartes, 0 erreur, tous liens résolus
- Run réel : 122 créées + validées, 0 erreur, toutes en état `valide`
- Re-run : 0 créée, 122 sautées (idempotence parfaite)
- Pytest complet : 3111 passed, 5 skipped, 0 régression
- Échantillon visuel des cartes paramétrées : syntaxe xint cohérente
  avec les exos existants

---

## Notes pour le futur

### À corriger à l'usage (zones de flou signalées dans le README)

- **S07** : très peu de cartes calcul car les probas se prêtent mal au
  xint pur (comptages qualitatifs principalement)
- **S08** : pas de carte calcul d'échelle (valeurs dépendent trop de
  ton angle)
- **S10/C13** : « Durée entre 2 horaires » utilise une syntaxe
  ternaire xint (`cond ? a : b`). Doit être vérifié sur ton MiKTeX
- **S11** : aucune carte « construction » par choix (geste, pas savoir)

### Roadmap mise à jour

Nouveau item à ajouter dans la liste roadmap longue :
- **Multisélection + menu contextuel pour validation rapide** :
  notions, méthodes, cartes. Atelier admin et/ou atelier de chaque
  type. À spécifier en session dédiée. **Priorité montante** maintenant
  qu'on a 122 cartes fraîchement insérées à relire.

### Position dans l'ordre de travail courant

Cette session est **transversale** au chantier en cours (étape 2 :
atelier assemblage séquence-dans-niveau). C'est de la donnée pure, pas
de la fonctionnalité. Ne consomme aucun budget de l'étape 2 ni des
suivantes. Reprise normale de l'étape 2 à la prochaine session.

---

## Style de livraison

Cohérent avec les conventions du projet :
- Pas de modification de fichiers existants (purement additif)
- Tests pytest exhaustifs avec zéro régression
- Idempotence du script de peuplement
- BDD originale sauvegardée dans `appli/data/seqenseigne_avant_peuplement.db.bak`
- Pas de migration de schéma (alpha mode, BDD libre)

Pas de Git utilisé — livraison ZIP unique avec MANIFEST.md5.
