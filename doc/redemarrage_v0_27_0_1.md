# Redémarrage v0.27.0.1 — Référentiels externes : aperçu PDF inline + séquences plus visibles

Deux ajustements de l'atelier « Référentiel externe ». Purement front.

## 1. PDF affichés dans l'appli (plus en onglet externe)

Cause identifiée : les documents PDF étaient rendus avec un lien `target="_blank"`
(ouverture dans un nouvel onglet). Corrigé : un clic sur un document PDF l'affiche
désormais dans une **zone d'aperçu inline** (iframe) sous la liste, avec un bouton
« Fermer l'aperçu ». Les formats non affichables (ODT, DOCX…) restent en
**téléchargement** (`download`). La route sert déjà les PDF en
`Content-Disposition: inline`, donc l'iframe les affiche.

## 2. Séquences mieux distinguées des parties

Chaque séquence est présentée dans un **bloc encadré** avec un **bandeau
violet** (fond `#ede7f6`) : libellé « SÉQUENCE », code et nom en **14 px gras**.
Les parties sont dans le corps du bloc, en dessous, en police plus petite. La
hiérarchie séquence → parties est ainsi nette au premier coup d'œil.

## Fichiers

- `static/referentiel_externe.js` : docs PDF → `rxtApercu` (inline) au lieu de
  `target="_blank"` ; non-PDF → `download` ; `rxtRenderSeq` (bandeau coloré) ;
  `rxtApercu` / `rxtFermerApercu`.
- `templates/index.html` : zone d'aperçu `rxt-apercu` (iframe) sous la liste.

## Tests

- vitest : 193 passed (0 régression). Syntaxe OK. Zone d'aperçu présente, plus
  de `target="_blank"` sur les docs externes.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Purement front. Se déploie
par-dessus la v0.27.0.

## Suite

- v0.27.1 : effet fin des indisponibilités sur la progression MER (choix
  absorber / décaler).
