# Redémarrage v0.51.16 — Échange automatique par API

## Décisions (validées)

- L'**atelier appelle toujours l'appli de classe** (une seule adresse, côté
  atelier ; `http://localhost:5001` en local). La destination est rangée
  dans une liste (une ligne aujourd'hui) : plusieurs applis de classe
  resteront possibles. Cible à terme : appli de classe multi-utilisateur
  (un compte par enseignant), un seul lien atelier ↔ classe.
- **Jeton** : date d'expiration obligatoire (défaut 1er août suivant),
  montré une seule fois, régénérable à tout moment (révoque l'actuel),
  empreinte seule conservée ; alerte 15 jours avant l'expiration. La
  protection du jeton (PC de l'atelier) incombe à celui qui administre
  l'atelier ; l'appli en limite la portée (boîte aux lettres seulement,
  aucune donnée d'élève) et les abus (limitation des appels, HTTPS en
  ligne, contrôles du protocole, mode confirmation).
- **Envoi immédiat** à la création d'un paquet, en plus de la relève
  périodique ; le paquet livré n'est plus téléchargé (sinon il l'est,
  comme avant).
- Paquet reçu par l'API : même traitement qu'un fichier déposé (mode
  confirmation ou automatique).
- **Secours** : boîte aux lettres par dossiers et import à la main gardés ;
  alerte « appli de classe actuellement injoignable » à l'écran.
- Au passage : l'appli de classe produit d'elle-même un nouveau retour
  d'usage quand l'atelier relève et que l'usage a changé (plus besoin du
  bouton, qui reste) ; un retour créé à la main n'est pas doublé.

## Code

- `services/api_boite.py`, `routes/api_boite.py` (classe : jeton, routes
  `/api/boite/v1/…`, `/api/jeton`) ; `services/auth.py` (routes à jeton hors
  mot de passe).
- `services/api_client.py`, `routes/api_client.py` (atelier : destination,
  test, synchronisation) ; `services/depot.py` (synchronisation à chaque
  relève) ; `routes/publication.py` (envoi immédiat, en-tête
  `X-Paquet-Envoi`) ; `routes/retour_usage.py`, `services/retour_usage.py`.
- `services/profils.py`, `app.py`.
- `static/echanges.js` (préférences, écran Échanges, alertes),
  `static/tableau_bord.js` (tuiles), `static/app.css`, `templates/index.html`.
- `doc/api_boite.md`.
- Tests : `tests/test_v0_51_16_api_boite.py` (dont un échange par HTTP réel
  en local).

## Mise en route

1. Appli de classe : Système › Préférences › Échanges › « Générer un
   nouveau jeton » ; copier le jeton.
2. Atelier : Système › Préférences › Échanges › adresse
   `http://localhost:5001`, coller le jeton, Enregistrer (le test se lance).
3. Les dossiers croisés de la boîte aux lettres (posés par la bascule)
   peuvent être vidés : l'API les remplace (les garder ne crée pas de
   doublon : un envoi déjà reçu est ignoré).
