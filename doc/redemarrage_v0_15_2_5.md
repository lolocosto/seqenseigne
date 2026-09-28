# Redémarrage v0.15.2.5 — Retrait de la cible « toutes séquences »

## Contexte

v0.15.2.4 a été déployée et testée par Laurent :
**3503 passed, 6 skipped in 586.53s (0:09:46)** — tests OK.

Mais en pratique, sur la compilation des planches N10 :

- La cible `'unique'` (toutes séquences) s'exécutait **en premier**.
- La barre de progression restait bloquée à **0/15** pendant >5 minutes.
- Elle échouait finalement à cause du timeout de 300s.
- Les 14 cibles par séquence qui suivaient compilaient correctement
  (~25-30s chacune).

Le retour terrain invalide la décision Q2 de la session précédente
(« garder aussi une cible unique »). Action immédiate demandée par
Laurent : **retirer la cible unique**.

## Changement

### `services/referentiel_documents_compilation.py` — `lister_cibles_document`

Branche `livret_cartes_planches` : suppression de la cible `'unique'`.
Ne reste que les N cibles par séquence (une par séquence ayant au moins
une carte `etat_code='valide'`).

Le **générateur** `generer_livret_cartes_planches(sequence=None, ...)`
conserve son support de toutes-séquences : utilisable par script ad hoc
si un PDF complet est ponctuellement requis (compilation manuelle hors
contrainte de timeout). Seul l'orchestrateur n'expose plus cette cible.

## Tests

### Adaptations dans `tests/test_v0_15_2_4_planches_decoupage_sequence.py`

3 tests adaptés (mêmes intentions, contraintes mises à jour) :

- `test_cibles_planches_vide_aucune_cible` (anciennement
  `…_renvoie_seulement_unique`) → 0 cible si aucune carte valide.
- `test_cibles_planches_une_par_sequence` (anciennement
  `…_unique_plus_une_par_sequence`) → N cibles, aucune `'unique'`.
- `test_cibles_planches_ignore_cartes_non_valides` → assertion
  `cibles[0]['cible_id'] == 'unique'` retirée.
- `test_producteur_propage_sequence` : la cible synthétique sans
  `'sequence'` exerce désormais le **contrat interne du générateur**
  (rétrocompat de la fonction), pas une cible exposée par l'orchestrateur.
  Docstring mise à jour.

### Nouveau fichier `tests/test_v0_15_2_5_planches_pas_de_cible_unique.py`

2 tests nommés protègent explicitement la décision :

- `test_planches_aucune_cible_unique_meme_avec_cartes` — vérifie qu'avec
  des cartes valides, aucune cible ne porte `cible_id='unique'` ni
  `nom_fichier='livret_cartes_planches.pdf'` nu, et que toutes ont une
  clé `'sequence'` explicite.
- `test_planches_nom_fichier_toujours_suffixe_par_sequence` — tous les
  `nom_fichier` suivent le motif `livret_cartes_planches__Nxx__Syy.pdf`.

Ces tests servent de **garde-fou nommé** : si quelqu'un réintroduit plus
tard une cible 'unique' sans la cadrer (mode async, timeout relâché),
ils échouent et expliquent pourquoi via leurs docstrings.

## État des tests

**v0.15.2.5 : 3505 passed, 6 skipped, 0 failed** (+2 par rapport à
v0.15.2.4).

## Effet attendu côté UI

Pour un référentiel N10 complet, le document `livret_cartes_planches`
exposera désormais **14 cibles** (1 par séquence) au lieu de 15.
Plus de blocage à 0/N pendant 5min : la barre avance d'un cran toutes
les ~25-30s.

---

## Question UX laissée ouverte pour prochaine session

> *« Il faut trouver un moyen d'informer l'utilisateur de ce qui se passe
> en temps quasi réel (log de compilation affiché ?) ; Presque : du moment
> que "quelque chose bouge", c'est bon... »*

Même avec le découpage par séquence, **une cible prend 25-30s** : trop
long sans signal de vie. Plusieurs pistes à arbitrer :

### Piste A — Afficher la cible en cours plus visiblement

L'orchestrateur tient déjà un `statut_progression` (cf.
`referentiel_documents_compilation.py`) qui inclut la cible en cours
(libellé + n°/total). L'UI poll ce statut. Si l'affichage est trop discret,
le rendre **prééminent** (ex. encart fixe « Compilation : Planches
N10/S07 — étape 7/14 (~28s) ») suffit peut-être au besoin « quelque chose
bouge ».

**Coût** : faible (UI uniquement). **Granularité** : 1 tick / cible
(~25-30s). Suffisant ?

### Piste B — Tail du log pdflatex en direct

Le compilateur écrit `_artefacts/<doc_id>/<cible_key>.log` pendant la
compilation. Une route `GET /compiler/log_tail` qui retourne les N
dernières lignes du log de la cible en cours, polled à 1Hz par l'UI,
donnerait un signal **continu** :

```
[28] Overfull \hbox (4.2pt too wide) in paragraph at lines 423--425
[29] Underfull \hbox (badness 1234) ...
```

Les `[N]` sont les numéros de pages produites — c'est un excellent indicateur
de vie pour pdflatex.

**Coût** : moyen (route nouvelle + UI + polling). **Granularité** :
quasi-temps-réel.

**Question technique** : sur Windows, MiKTeX écrit-il le `.log` au fur
et à mesure ou en bloc à la fin ? À vérifier (probablement au fur et à
mesure, mais avec un buffer à flusher).

### Piste C — Compteur de pages produites

Plus simple que tailler le log : grep régulièrement le `.log` pour la
dernière occurrence de `\[(\d+)\]` (un crochet `[N]` par page TeX). Expose
`{cible_en_cours: "N10/S07", page_en_cours: 28, pages_totales_estim: 32}`.

**Coût** : faible (parsing simple côté service). **Granularité** :
1 tick / page (≈1s).

### Piste D — Diagnostic upstream : pourquoi 25-30s par séquence ?

Une séquence ~8-9 planches × 2 pages × 16 cellules = ~270 tcolorbox.
À 100ms/tcolorbox, ça fait 27s. tcolorbox + tabularray sont notoirement
lents. Pistes :

- Désactiver les `tblr` libraries inutiles (`booktabs`, `varwidth` :
  utilisées ?).
- Vérifier si `vwcol` engendre la lenteur (cf. apprentissages : le
  bug `[lines=N]` était lié à vwcol).
- Passer à `lualatex` qui parallélise mieux ? (impact MiKTeX Portable
  + 3-pass à mesurer).

**Coût** : ouverte, possiblement importante. **Bénéfice** : tout le
monde y gagne (récap, planches, livrets sequence).

---

## Recommandation pour cadrer la prochaine session

Je suggère cet ordre, du plus économique au plus structurant :

1. **A** (UI : afficher la cible en cours) — premier essai à faible coût.
   Si « 14 ticks à 25s » est jugé acceptable, on s'arrête là.
2. Sinon **C** (compteur de pages) — ratio coût/granularité imbattable.
3. **B** (tail log) — si on veut vraiment voir le détail (debug, erreurs
   visibles côté UI dès qu'elles arrivent).
4. **D** (perf upstream) — chantier propre, à découpler. Vaut la peine
   d'être chiffré : si on peut diviser par 2-3, ça change tout.

À arbitrer en début de session prochaine, en parallèle des chantiers
péremption (2) et figeage (3) déjà cadrés dans
`redemarrage_prochaine_session.md`.

---

## Fichiers livrés

Tous complets, conformément à la convention :

| Fichier | Type |
|---|---|
| `appli/services/referentiel_documents_compilation.py` | Modifié |
| `appli/tests/test_v0_15_2_4_planches_decoupage_sequence.py` | Modifié |
| `appli/tests/test_v0_15_2_5_planches_pas_de_cible_unique.py` | Nouveau |
| `appli/doc/redemarrage_v0_15_2_5.md` | Nouveau (ce document) |

Pas de `.dtx`/`.sty` ni de modification du générateur ni de l'orchestrateur :
le contrat interne reste celui de v0.15.2.4, seule la liste des cibles
exposées par l'orchestrateur change.

## Vérification du delta

```powershell
.\outils\python\python.exe outils\verifier_md5.py --racine . --manifest MANIFEST.md5
.\outils\python\python.exe -m pytest -q
# Attendu : 3505 passed, 6 skipped, 0 failed
```
