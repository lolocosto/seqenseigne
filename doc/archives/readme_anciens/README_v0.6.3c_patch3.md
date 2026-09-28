# seqenseigne v0.6.3c — patch 3 « semaines de classe lun-ven »

Correction de deux bugs de rendu dans le calendrier visuel côté frontend.

## Bug 1 — 2 semaines de trop (celle d'avant et celle d'après)

Exemple observé pour les vacances de la Toussaint (18 oct → 3 nov) :
les semaines du 13 oct **et** du 3 nov apparaissaient en rouge, alors
que les vacances ne commencent que le samedi 18 et se terminent le
dimanche 2. Donc seules les semaines du 20 et 27 oct devraient être
marquées.

Cause : `_vacancesDeLaSemaine` testait le chevauchement avec la semaine
complète **lundi-dimanche**. Dès qu'une vacance touchait le samedi (ou
le dimanche, ou la date de reprise qui est un lundi), la semaine
entière était colorée.

Fix : tester le chevauchement avec la **semaine de classe lundi-vendredi**
uniquement. Les élèves ne sont pas en cours le week-end, donc une
vacance qui n'intersecte que le samedi ou le dimanche ne compte pas
comme "semaine de vacances" au sens scolaire. Même logique pour le
placement des créneaux sur la grille.

Règle précise : une semaine est en vacances si
`vacances.start_date ≤ vendredi_de_la_semaine` ET
`vacances.end_date (= jour de reprise) > lundi_de_la_semaine`.
La comparaison sur `end_date` est stricte (`>`, pas `≥`) parce que
`end_date` est le jour de reprise (exclusif).

Vérification sur Toussaint 2025 Zone B (18 oct → 3 nov) :
- Semaine du 13 oct (13-17 oct) : `18-10 ≤ 17-10` faux → **pas de vacances** ✓
- Semaine du 20 oct (20-24 oct) : conditions vraies → vacances ✓
- Semaine du 27 oct (27-31 oct) : conditions vraies → vacances ✓
- Semaine du 3 nov (3-7 nov) : `03-11 > 03-11` faux → **pas de vacances** ✓

Même gain côté pont de l'Ascension 2026 (14 → 18 mai) :
- Semaine du 11 mai : vacances (le pont va du 14 au 17 compris)
- Semaine du 18 mai : pas de vacances (reprise = lundi 18 au matin)

## Bug 2 — Semaines qui commençaient le dimanche

Cause : `_lundisEntre` générait les dates avec `toISOString().slice(0,10)`.
`toISOString()` convertit vers UTC. En France UTC+2 l'été, un objet Date
représentant "1er septembre 2025 00:00 heure locale" devient
"2025-08-31 22:00:00 UTC" en ISO. `.slice(0, 10)` donnait alors
`"2025-08-31"` — qui est un dimanche.

Fix : ne jamais utiliser `toISOString()`. J'ai ajouté une fonction
`_dateToISO(d)` qui formate en heure locale via
`getFullYear` / `getMonth` / `getDate`, et je l'ai appliquée partout où
on générait une date ISO à partir d'un objet `Date`.

Vérification : les lundis générés pour septembre-novembre 2025 sont
maintenant bien le 1er sept (lundi), 8 sept (lundi), 15 sept (lundi)…
etc. 100 % des dates testées sont des lundis.

## Fichier modifié

```
appli/static/app.js   (3 fonctions touchées + 1 nouvelle : _dateToISO,
                       _jourSemaine, _lundisEntre, _vacancesDeLaSemaine,
                       _feriesDeLaSemaine, _creneauxDeLaSemaine)
```

Aucune modification backend cette fois. Pas besoin de vider de cache.

## Déploiement

```powershell
# Copier static/app.js
# Ctrl+F5 dans le navigateur (pas besoin de redémarrer Flask, c'est du JS)
```

## Résultat attendu

Pour une progression 2025-2026 (Zone B, Rennes) :

| Semaines en rouge | Période |
| --- | --- |
| 20 oct, 27 oct          | Vacances de la Toussaint |
| 22 déc, 29 déc          | Vacances de Noël |
| 16 fév, 23 fév          | Vacances d'Hiver |
| 13 avr, 20 avr          | Vacances de Printemps |
| 11 mai                   | Pont de l'Ascension |
| 6 juillet → 31 août     | Vacances d'été |

Toutes les semaines affichées doivent commencer par un **lundi**.

## Tests

Aucun test backend à ajouter ni à modifier (c'est du frontend).
Les 369 tests backend restent verts.
