# Audit seqenseigne — Vulnérabilités, RGPD, RGAA

Audit réalisé sur le code source réel du projet (293 fichiers Python, 45 JS, 35
routes, base SQLite). Il vise à donner une image honnête de l'état actuel et une
liste d'actions **priorisées**, en tenant compte du contexte : application
**mono-utilisateur**, développée par un enseignant pour son usage, manipulant
des **données d'élèves mineurs**.

Chaque constat est classé : 🔴 critique · 🟠 important · 🟡 mineur · 🟢 conforme.

---

## Synthèse

| Axe | État global | Points saillants |
|-----|-------------|------------------|
| Vulnérabilités | Correct pour un usage local, risqué si exposé | Pas d'auth, `debug=True`, sinon bonnes pratiques SQL/LaTeX |
| RGPD | Données minimisées mais non protégées au repos | 550 élèves + 33 000 résultats, base non chiffrée, pas de registre |
| RGAA | Base saine, mais non conforme | `lang` OK, aucun ARIA, navigation clavier partielle |

Le message principal : **le risque dépend entièrement de l'exposition**. Tant que
l'appli tourne en local (localhost, un seul poste), la plupart des risques sont
théoriques. Le jour où elle est déployée sur un serveur accessible (le projet
Infomaniak évoqué), plusieurs points deviennent bloquants et doivent être traités
**avant** la mise en ligne.

---

## 1. Vulnérabilités

### 🟢 Injection SQL — non vulnérable
Toutes les requêtes examinées utilisent des **requêtes paramétrées** (`?`). Les
constructions dynamiques (`IN ({placeholders})`, `.format(",".join("?"*n))`)
n'injectent que des marqueurs `?`, jamais des valeurs utilisateur. Aucune
concaténation de valeur brute dans une requête n'a été trouvée. **C'est un vrai
point fort.**

### 🟢 Compilation LaTeX — bien maîtrisée
- `subprocess.run` est appelé avec une **liste d'arguments** (pas `shell=True`),
  sur un fichier au nom fixe (`atome.tex`), dans un répertoire temporaire isolé
  (`cwd=tmpdir`), avec un `timeout`.
- **`-shell-escape` / `write18` ne sont PAS activés** : le LaTeX compilé ne peut
  pas exécuter de commandes système. C'est le point critique d'une chaîne LaTeX,
  et il est correctement fermé.
- 🟡 Risque résiduel mineur : sans `shell-escape`, LaTeX peut tout de même lire
  des fichiers (`\input`, `\openin`). En mono-utilisateur avec du contenu que
  l'enseignant saisit lui-même, le risque est négligeable. À garder en tête si
  un jour du contenu LaTeX provenait de tiers.

### 🔴 Absence totale d'authentification
Aucune route n'est protégée (pas de login, pas de session, pas de
`@login_required`). N'importe qui pouvant joindre le serveur peut lire et
modifier **toutes** les données, y compris les résultats des 550 élèves.
- **En local (localhost)** : acceptable, l'accès est déjà restreint à la machine.
- **Sur un serveur exposé** : 🔴 **bloquant**. Il faut au minimum une
  authentification (même simple : un mot de passe unique + session) avant toute
  mise en ligne.

### 🔴 `debug=True` en dur
`app.py` lance `create_app().run(debug=True, port=5000)`. Le mode debug de Flask
expose le **débogueur interactif Werkzeug**, qui permet l'**exécution de code
Python arbitraire** depuis le navigateur en cas d'erreur.
- **En local** : gênant mais tolérable.
- **Sur un serveur** : 🔴 **faille critique d'exécution de code à distance**.
  À désactiver impérativement (piloter par variable d'environnement :
  `debug=os.environ.get("FLASK_DEBUG") == "1"`, défaut `False`).

### 🟠 XSS (cross-site scripting) — globalement couvert, à surveiller
L'UInjecte massivement du HTML via `innerHTML` (283 occurrences). Les données
utilisateur (noms de classes, libellés, motifs) sont **majoritairement
échappées** via `escapeHtml` / `_esc`. Les cas vérifiés (EdT, indisponibilités,
décalages) échappent correctement à l'affichage.
- 🟠 Le volume d'`innerHTML` rend une régression facile : il suffit d'un futur
  champ affiché sans `escapeHtml` pour introduire une faille. Un attaquant
  (ou un collègue malveillant, si multi-utilisateur un jour) pourrait stocker
  `<script>` dans un libellé.
- Recommandation : conserver la discipline « toute donnée dans `innerHTML` passe
  par `escapeHtml` », et à terme envisager des helpers qui rendent l'oubli
  impossible (création DOM via `textContent`).

### 🟠 Pas de protection CSRF
Les routes POST/PUT/DELETE (modification de données) n'ont pas de jeton CSRF.
En mono-utilisateur local, non exploitable. Multi-utilisateur/serveur : à ajouter
(Flask-WTF ou un jeton maison).

### 🟡 Réponses d'erreur détaillées
~69 réponses renvoient `str(e)` (le message d'exception) au client. Pratique en
dev, mais peut divulguer des détails internes (chemins, structure) sur un serveur.
À filtrer en production (message générique + log serveur).

### 🟡 Uploads de fichiers
Des routes acceptent des fichiers (`request.files` : imports CSV d'élèves, etc.).
Vérifier : taille maximale (`MAX_CONTENT_LENGTH` non configuré → risque de déni
de service par gros fichier), et que le contenu est traité comme données (les CSV
le sont : `.decode()` + parsing, pas d'exécution). 🟢 Pas de `save()` de fichier
arbitraire sur le disque repéré.

### 🟡 Pas de HTTPS ni cookies sécurisés
Aucune configuration TLS / `SESSION_COOKIE_SECURE`. Sans session ni auth
aujourd'hui, sans objet. À prévoir avec l'authentification, lors d'un déploiement.

---

## 2. RGPD

L'application traite des **données personnelles de mineurs** : 550 élèves (nom,
prénom, dates d'entrée/sortie) et ~33 000 résultats d'évaluation (niveau de
maîtrise par objectif). C'est le régime le plus sensible du RGPD.

### 🟢 Minimisation des données — bien respectée
Les données stockées sont **strictement limitées au nécessaire** : nom, prénom,
appartenance à une classe, dates, résultats scolaires. **Pas** de date de
naissance, adresse, coordonnées, identifiant national, ni donnée « sensible » au
sens de l'article 9 (santé, origine…). C'est exactement l'esprit de la
minimisation. Très bon point.

### 🟢 Droit à l'effacement — techniquement possible
Des fonctions de suppression d'élève existent (`supprimer_eleve`,
`DELETE FROM eleves`), et la suppression en cascade (eleves_classes, suivi,
niveaux) est gérée. Le droit à l'effacement est donc réalisable, même si non
outillé en un clic « effacer tout ce qui concerne l'élève X ».

### 🔴 Base de données non chiffrée au repos
`data/seqenseigne.db` est un fichier SQLite **en clair**. Toute personne ayant
accès au fichier (vol/perte du portable, sauvegarde non protégée, accès serveur)
lit directement les noms et résultats des 550 élèves.
- **Recommandation forte** : chiffrer soit le **support** (BitLocker/LUKS sur le
  disque — le plus simple et déjà peut-être en place sur ton poste), soit la
  **base** (SQLCipher). Le chiffrement disque est la mesure minimale attendue
  pour des données de mineurs sur un poste mobile.

### 🟠 Absence de cadre RGPD documenté
En tant que traitement de données d'élèves, même à titre d'outil personnel
d'enseignant, plusieurs obligations formelles s'appliquent en principe :
- **Base légale** : le traitement doit s'appuyer sur une base (mission de service
  public / intérêt légitime pédagogique). À clarifier avec le chef
  d'établissement / le DPO académique.
- **Information des personnes** : les représentants légaux des élèves devraient
  être informés de l'existence du traitement (souvent couvert par les mentions
  générales de l'établissement, à vérifier).
- **Registre des traitements** : l'établissement tient un registre ; cet outil
  devrait y figurer ou être couvert.
- **Durée de conservation** : définir quand les données élèves sont purgées
  (ex. fin de cycle, ou N années après le départ). Aujourd'hui, rien n'impose
  ni n'automatise une purge → risque de conservation indéfinie.
- **Point d'attention** : c'est un sujet à traiter **avec le DPO de l'académie**,
  pas seul. La bonne nouvelle est que la minimisation déjà en place facilite
  grandement la mise en conformité.

### 🟠 Exports de données
Des fonctions d'export existent (bouton « Exporter »). Un export contient des
données personnelles → il doit être manipulé avec les mêmes précautions
(stockage chiffré, pas d'envoi par mail non sécurisé, suppression après usage).
À documenter comme consigne d'usage.

### 🟡 Traçabilité des accès
Aucun journal des accès/modifications aux données élèves. En mono-utilisateur,
peu utile ; deviendrait pertinent en multi-utilisateur.

---

## 3. RGAA (accessibilité)

Le RGAA (Référentiel Général d'Amélioration de l'Accessibilité) s'applique aux
services publics. Une application de l'Éducation nationale, si elle était
diffusée, y serait soumise. État actuel : **base saine mais non conforme**, car
l'UI dynamique n'expose pas de sémantique accessible.

### 🟢 Langue de la page
`<html lang="fr">` est présent. Critère de base respecté.

### 🟢 Pas d'images
L'interface est en HTML/CSS/emojis, sans balises `<img>` — donc pas de problème
d'alternatives textuelles d'images. (Note : les emojis utilisés comme icônes
fonctionnelles — ⛔, 🌴, 🔸 — devraient idéalement être accompagnés d'un texte,
ce qui est souvent le cas.)

### 🔴 Absence totale d'ARIA et de rôles
Aucun attribut `aria-*` ni `role` dans tout le projet. Les composants dynamiques
(popovers, onglets, calendrier, listes éditables, glisser-déposer) ne sont donc
pas annoncés correctement par un lecteur d'écran. C'est le principal écart RGAA.
- Exemples concrets : le popover d'édition de l'EdT n'a pas `role="dialog"` ;
  les barres d'onglets (Suivi annuel / EdT / Progression…) ne sont pas balisées
  en `role="tablist"` / `role="tab"` ; les statuts (« ✓ enregistré ») ne sont pas
  dans une zone `aria-live`.

### 🟠 Boutons à icône seule
Des boutons d'action n'ont qu'une icône (`×` supprimer, `↑`/`↓` réordonner). Ils
portent un `title` (infobulle), ce qui aide partiellement, mais le RGAA demande
un **nom accessible** explicite : ajouter `aria-label="Supprimer"` (le `title`
seul n'est pas fiable selon les lecteurs d'écran).

### 🟠 Navigation clavier partielle
La navigation clavier existe par endroits (quelques `keydown`), mais les
interactions cœur — **glisser-déposer** des parties sur le calendrier, popovers,
cases cliquables de l'EdT — reposent sur la souris (`onclick` sur des `<div>`).
Ces éléments ne sont ni focusables (`tabindex`) ni actionnables au clavier. Pour
la conformité, toute action souris doit avoir un équivalent clavier.

### 🟠 Association labels / champs
66 `<input>` pour 98 `<label>`, dont seulement 13 avec `for=` explicite et
quelques-uns par imbrication. Beaucoup de labels sont probablement associés par
imbrication (`<label>Texte <input></label>`), ce qui est valide, mais il faut
**vérifier que chaque champ a bien un label associé** (par `for`/`id` ou
imbrication) — plusieurs champs générés dynamiquement en JS n'en ont pas
visiblement.

### 🟡 Contrastes et tailles
Plusieurs textes utilisent `font-size:10px`/`11px` et des gris clairs
(`color:#999`, `#c0c0c0`) qui risquent de ne pas respecter le ratio de contraste
minimal (4.5:1) ni la lisibilité. À vérifier avec un outil de contraste.

---

## Plan d'action priorisé

### Avant tout déploiement sur un serveur exposé (bloquant)
1. 🔴 Désactiver `debug=True` (piloter par variable d'environnement, défaut off).
2. 🔴 Ajouter une **authentification** (au minimum un mot de passe + session).
3. 🔴 **Chiffrement au repos** des données élèves (disque chiffré a minima).
4. 🟠 HTTPS + cookies sécurisés + protection CSRF.
5. 🟠 Messages d'erreur génériques côté client (ne pas renvoyer `str(e)`).

### Conformité RGPD (à mener avec le DPO académique)
6. 🟠 Clarifier base légale + information des familles + inscription au registre.
7. 🟠 Définir et outiller une **durée de conservation** (purge des données
   élèves après N années / fin de cycle).
8. 🟡 Consigne d'usage pour les exports (stockage chiffré, suppression).

### Accessibilité RGAA (progressif, si diffusion envisagée)
9. 🟠 Ajouter `aria-label` sur tous les boutons à icône seule.
10. 🔴/🟠 Baliser les composants dynamiques : onglets (`role="tab"`/`tablist`),
    popovers (`role="dialog"`), zones de statut (`aria-live="polite"`).
11. 🟠 Équivalents clavier pour le glisser-déposer et les zones cliquables
    (`tabindex`, gestion de la touche Entrée/Espace).
12. 🟡 Vérifier contrastes et tailles de police minimales.

### Bonnes pratiques continues (déjà bien engagées)
- Maintenir la discipline « données utilisateur toujours échappées avant
  `innerHTML` ».
- Conserver la minimisation des données (ne pas ajouter de données personnelles
  non strictement nécessaires).
- Garder `-shell-escape` désactivé dans la compilation LaTeX.

---

## Conclusion

Le projet est **solide sur les fondamentaux techniques** (pas d'injection SQL,
chaîne LaTeX bien fermée, données minimisées) — ce qui est remarquable pour un
projet développé par un enseignant. Les écarts constatés relèvent surtout de
l'**absence de couche de production** (authentification, chiffrement, mode debug)
et de conformité **formelle** (cadre RGPD, sémantique RGAA), pas de failles de
conception profondes.

La ligne de partage est nette : **en usage local mono-poste, le risque réel est
faible**. Le travail de mise en conformité devient nécessaire, et par endroits
bloquant, **le jour d'un déploiement serveur** — ce qui tombe bien, puisque c'est
précisément à ce moment-là (projet Infomaniak) qu'il faudra reprendre ce document
point par point, en commençant par les trois 🔴 : debug, authentification,
chiffrement.
