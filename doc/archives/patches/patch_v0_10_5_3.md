# patch v0.10.5.3 — Zone notions retirée de l'objectif Connaître

**Date** : 2 mai 2026

**Périmètre** : un seul retour utilisateur — la zone de drop notions
dans l'objectif Connaître ouvert ne sert à rien et est retirée de l'UI.

**Score tests** : 1656/1656 + 4 skipped historiques. Aucune régression.

---

## Le changement

**Avant** : ouvrir l'obj Connaître d'une partie dans l'atelier
d'assemblage affichait deux zones :
1. « Notions » (zone de drop)
2. « Fiches de résumé du livret » (zone de drop, v0.10.5)

**Après** : seule la zone « Fiches de résumé du livret » reste visible.

### Pour les obj exo (02, 03, 04…)

**Inchangé**. Les zones Notions + F + A + E restent affichées comme
avant. La zone Notions des obj exo sera utilisée pour construire les
plans de travail (v0.10.6).

---

## Justification

La table `objectif_notions` permettait jusqu'ici de relier une notion
à un objectif Connaître. Mais cette liaison n'est utilisée nulle part
dans la chaîne de rendu actuelle :

- **Pas dans le rendu LaTeX** des atomes (`services/latex_rendu_atome.py`
  ne lit pas `objectif_notions`)
- **Pas dans les récaps** (cours, exos, …)
- **Pas dans la compilation par lot** ni dans les exports

Le seul usage qui aurait pu justifier le drop sur le Connaître était
la traçabilité « pédagogique » du lien partie → notions. Mais comme
les notions sont **déjà** attachées à la partie via les obj exo (qui
gardent leur zone notions), le lien obj Connaître → notion est
redondant.

**Pour les obj exo** : la liaison reste très utile — elle permettra
de construire les plans de travail élève (v0.10.6) qui listent les
notions à étudier en lien avec chaque exercice.

---

## BDD

**Aucune migration**. Les liaisons existantes dans `objectif_notions`
qui ciblent des obj Connaître restent en BDD telles quelles. Elles
sont juste invisibles dans l'UI :

- Si tu avais déjà attaché des notions à un Connaître, elles ne sont
  pas supprimées.
- Si tu veux les nettoyer manuellement, tu peux le faire via SQL
  direct (à ta charge).
- L'API `POST /api/v2/objectifs/<id>/notions` continue de fonctionner
  pour les obj Connaître — c'est juste qu'il n'y a plus d'accès UI.

Cette approche conservative est volontaire : on ne casse rien en
silence.

---

## Fichiers modifiés

```
static/atelier_seqniv_assemblage.js  — _rendreObjOuvert : zonesContenu
                                       devient estConnaitre ? zoneFiches
                                       : zoneNotions (au lieu d'inclure
                                       les deux pour le Connaître)
```

C'est tout. Une seule ligne effective de modification.

---

## Test manuel après déploiement

1. Atelier > Séquence (assemblage), ouvrir une séquence.
2. Ouvrir l'obj Connaître d'une partie (ex. obj 11 de P1).
3. Vérifier que :
   - La zone « Fiches de résumé du livret » est présente
   - La zone « Notions » a disparu
4. Ouvrir un obj exo (ex. obj 12) dans la même partie.
5. Vérifier que :
   - La zone « Notions » est toujours présente
   - Les zones F, A, E sont toujours présentes
   - On peut toujours drag-and-drop des notions depuis la sidebar

---

## À venir

- **v0.10.6** : badge « modifié » sur les ateliers de la portée
  Séquence + modale de garde de sortie « Sauvegarder / Ne pas
  sauvegarder / Annuler ». Sujet transversal qui mérite sa session
  dédiée. (Q1-A à Q1-D verrouillées dans la session courante.)
