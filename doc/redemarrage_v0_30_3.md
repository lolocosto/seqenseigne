# Redémarrage v0.30.3 — Tuile « Atomes à finaliser » : action fine par type

Chaque nombre par type de la tuile devient cliquable et ouvre l'atelier
correspondant, toutes séquences, filtre « en cours » pré-activé. S'appuie sur le
mode « toutes les séquences » livré en v0.30.2.

## Contenu

Dans la tuile « Conception — atomes à finaliser » :
- **Clic sur l'en-tête d'un niveau** (comportement v0.30.1 conservé) : ouvre
  l'atelier de conception au niveau (portée Niveau).
- **Clic sur un nombre de type** (nouveau) : ex. « 279 exercices » de 3ème →
  ouvre l'atelier **exercices**, en portée Séquence, niveau 3ème, **toutes les
  séquences**, avec le **filtre « en cours »** pré-activé. On tombe directement
  sur les exercices à finaliser.

Chaque type est souligné en pointillé (affordance de lien) et gère
`stopPropagation` pour ne pas déclencher le clic du niveau.

## Mécanisme

Nouvelle fonction `ouvrirAtelierAtomesEnCours(niveau, typeAtome)` (`app.js`) :
- pose la portée Séquence avec `{niveau, sequence:''}` (toutes séquences) ;
- force `ATL_FILTRE_ETAT[<type>] = 'en_cours'` ;
- bascule sur l'onglet Ateliers puis `atelSwitch(<atelier>)`.

Mapping type → atelier : exercice, notion, methode → identiques ; carte →
`carte_automatisme` ; fiche → `fiche`. Mapping type → clé de filtre : fiche →
`fiche_resume`, les autres identiques.

## Fichiers

- `static/app.js` : `ouvrirAtelierAtomesEnCours`.
- `static/tableau_bord.js` : nombres par type rendus cliquables.

## Tests

- `node --check` (exit 0) + logique vérifiée : exercice N11 → portée séquence,
  séquence vide, filtre en_cours, atelier exercice ; carte N09 → atelier
  carte_automatisme. vitest : 193 passed. Page rendue OK.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Se déploie
par-dessus la v0.30.2.

## Suivi de séance (cadrage consigné, hors code)

Le retour terrain d'une collègue de maths a été consigné dans
`doc/reflexion_metier_enseignant_roadmap.md` (§8) : deux outils papier
complémentaires (fiche hebdo « suivi/manques » liste élèves × séances ; fiche
« plan de classe » placement + attitude), entièrement à base de **pictogrammes**
(peu de texte). Enseignements pour la future conception : deux vues distinctes,
saisie par pictogrammes, cadence hebdo par classe, attributs durables +
événements ponctuels. À cadrer précisément plus tard.
