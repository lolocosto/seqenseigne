# Redémarrage v0.27.0.2 — Plannings : affichage dans l'appli (et non dans le lecteur système)

Correctif ciblé : dans le Suivi de classe, les plannings (automatismes et
progression MER) s'ouvraient dans le lecteur PDF du système au lieu de s'afficher
dans l'iframe de l'appli.

## Cause

Les routes de planning renvoyaient le PDF avec un en-tête
`Content-Disposition: inline; filename=…`. La présence de cet en-tête (avec un
nom de fichier) pousse certains navigateurs à confier le PDF au lecteur externe
plutôt qu'à l'afficher dans l'iframe. Le rendu d'atome — qui, lui, s'affiche
correctement dans son onglet « Rendu PDF » — ne met **aucun**
`Content-Disposition` (juste `mimetype='application/pdf'`).

## Correctif

Les trois routes de planning renvoient désormais le PDF **sans**
`Content-Disposition`, comme le rendu d'atome :
- planning des automatismes (`routes/leitner.py`) ;
- planning MER d'une classe (`routes/progression_mer.py`) ;
- planning MER théorique (`routes/progression_mer.py`).

Le PDF s'affiche ainsi dans l'iframe de l'onglet (Suivi de classe › Mises en
route / Progression de MER).

Les documents des référentiels externes ne sont pas concernés (leur ouverture
dans le lecteur système convient) : leur route conserve son `Content-Disposition`
(inline pour les PDF, attachment pour les autres formats).

## Fichiers

- `routes/leitner.py` : planning automatismes sans `Content-Disposition`.
- `routes/progression_mer.py` : plannings MER (classe + théorique) sans
  `Content-Disposition`.

## Tests

- vitest : 193 passed (0 régression). Syntaxe OK. Vérifié : plus de
  `Content-Disposition` sur les plannings ; conservé sur les docs externes.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Se déploie par-dessus la
v0.27.0.1.

## Suite

- v0.27.1 : effet fin des indisponibilités sur la progression MER (absorber /
  décaler).
