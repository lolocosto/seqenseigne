# Redémarrage v0.47.3 — Liste des classes de la Progression de MER

Retour d'usage : Planification › Progression de MER, établissement « Collège
les Hautes Ourmes » + niveau N09 → la liste des classes ne proposait pas les
6E3 / 6E8 (présentes dans Paramétrage avec les mêmes critères).

Cause : le sélecteur Classe (partagé) n'était refiltré qu'en Compétences /
Début de séance / Observation / Travail. Dans les ateliers de Planification
qui ont aussi ce sélecteur (Progression de MER, Mises en route), changer de
niveau ou d'établissement — ou ouvrir l'atelier — laissait la liste filtrée
selon les critères de l'onglet précédent (ici : les classes de N11).

Correctif (`static/app.js`) : `_refiltrerClassesSiBesoin()` appelé à
l'ouverture de tout atelier dont la déclaration comporte le sélecteur Classe,
et en tête de `onNiveauChangeGlobal` / `onEtabChangeGlobal` ; si la classe
choisie ne correspond plus aux critères, elle est désélectionnée.

Vérifié dans un navigateur sur une copie de la base de l'utilisateur (supprimée ensuite) :
Progression de MER, N09 → 6E3, 6E8 (avant : 4E4, 4e3). vitest 225 réussis, pytest sans échec.
