# Boîte aux lettres par API (v0.51.16)

L'appli de classe (en ligne) expose une boîte aux lettres que l'atelier
(local) appelle. L'atelier est toujours le client : un serveur en ligne ne
peut pas joindre le PC de l'enseignant.

## Authentification

En-tête `Authorization: Bearer <jeton>`.

- Le jeton se génère dans l'appli de classe (Système › Préférences ›
  Échanges), avec une **date d'expiration obligatoire** (défaut : le 1er
  août suivant ; deux ans au plus). Il n'est montré qu'une fois ; seule son
  empreinte SHA-256 est conservée. En générer un nouveau révoque l'actuel.
- Jeton absent, inconnu, révoqué ou expiré : `401`. Dix refus en dix minutes
  depuis une même adresse, ou plus de 120 appels par minute : `429`.
- Ces routes ignorent le mot de passe de l'appli (`SEQ_MDP`) : le jeton est
  leur seule clé, et il ne donne accès qu'à elles.
- En ligne, HTTPS obligatoire (l'atelier refuse une adresse `http://` autre
  que localhost).

## Routes

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/api/boite/v1/etat` | `{instance {id, nom, role}, attendu {paquet}, jeton {expire_le, jours_restants}}` |
| POST | `/api/boite/v1/paquets` | corps : le zip du paquet ; en-tête `X-Nom-Fichier` (encodé URL). Rangé dans le dossier d'entrée puis relevé selon le mode réglé. Réponse `{fichier, issue: traite\|en_attente\|doublon\|refuse, message}`. 512 Mo au plus. |
| GET | `/api/boite/v1/usages?apres=<n>` | `{usages: [{numero, nom, taille, cree_le}]}` — retours archivés de n° > n ; un nouveau retour est produit si l'usage a changé depuis le dernier envoi. |
| GET | `/api/boite/v1/usages/<n>` | le fichier JSON du retour d'usage n° n |

Les contrôles du protocole d'échange (`doc/format_paquet.md`,
`doc/format_usage.md`) s'appliquent : numéro attendu, émetteur lié, contenu
validé, accusés (un paquet accuse les retours reçus et inversement).

## Côté atelier

Adresse et jeton dans Système › Préférences › Échanges. Synchronisation au
démarrage, à chaque relève (5 min par défaut) et dès qu'un paquet est créé :
envoi des paquets non livrés et non acquittés, rapatriement des nouveaux
retours d'usage dans le dossier d'entrée, puis relève. Appli de classe
injoignable : erreur affichée (tuile Publication, écran Échanges), envois
gardés pour la synchronisation suivante. Alerte 15 jours avant l'expiration
du jeton.
