# Redémarrage v0.51.10 — Échanges : retours du premier essai

Premier essai réel de l'auteur (v0.51.9) : 12 référentiels publiés, paquet
déposé dans le dossier d'entrée, relève côté appli en ligne → « 0
référentiel(s) importé(s) sur 12 ». Cause : les deux applis tournaient sur
**la même base** (`data\`, même instance des deux côtés) ; les référentiels
y étaient déjà, tous « identiques » — rien à importer, c'est normal. Le vrai
échange se fait avec l'appli en ligne sur sa base (`lancer.bat classe
--base-classe`), puis après la bascule.

## Décisions (demandes de l'auteur)

- Les réglages quittent les tuiles : **Système › Préférences › Échanges**
  (les deux profils) — nom de l'instance, appli liée (« Délier »), dossiers
  d'entrée et de sortie, mode de traitement, période de relève. Les tuiles
  gardent l'état (dossier, envois, relève, « Traiter », journal, identité en
  lecture seule).
- Atelier : plus de bouton « Importer un retour d'usage » — on se limite à
  relever la boîte aux lettres (l'import manuel d'un paquet reste possible
  côté appli en ligne, Système › Administration).
- Appli en ligne : pas de retour d'usage tant qu'aucun référentiel n'a été
  importé (bouton remplacé par une mention).
- Base partagée : la relève le dit (« n importé(s), m identique(s) — base
  partagée avec l'atelier… »), et le bloc identité affiche un avertissement
  (`base_partagee` dans `/api/echanges/etat`).

## Code

- `services/depot.py` (résumé d'un paquet : identiques, base partagée),
  `services/echanges.py` (`base_partagee`).
- `static/echanges.js` : `prefEchangesCharger`, `prefEchangesEnregistrer`,
  `prefEchangesDelier` ; tuiles sans réglages ; avertissement de base
  partagée. `static/app.js` (`_prefInitialiser`), `templates/index.html`
  (catégorie « Échanges »), `static/tableau_bord.js`, `static/app.css`.
- Tests : `tests/test_v0_51_10_echanges_reglages.py`.

## À noter

- « 40 partie(s) dont la durée saisie diffère des objectifs » au paquet :
  information (référentiels internes figés avant la règle des durées) ; la
  durée publiée est la somme des objectifs. À reprendre avec la passe
  « durées » sur le figeage des internes.
