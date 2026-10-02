# Redémarrage v0.42.1 — Sélecteurs des nouveaux sous-onglets

- **Suivi** : Début de séance, Observation et Compétences ont les mêmes
  sélecteurs — Année, Établissement, Niveau, Classe. La classe choisie est
  partagée entre les trois (même `<select id="classe-sel">`) ; choisir une
  classe ne fait plus quitter le sous-onglet courant. Un changement d'année ou
  d'établissement recharge la liste des classes dans les trois.
- **Paramétrage › Observables** : Niveau seul (les observables sont définis
  par niveau, indépendamment de l'établissement).
- Autres sous-onglets inchangés.

Tests : vitest `suivi_navigation.test.js` (+2) ; parcours navigateur
(sélecteurs visibles et remplis, classe partagée Début de séance ↔ Observation).
