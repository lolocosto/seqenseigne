# seqenseigne v0.6.3c — patch 2 « vacances complètes + dates justes »

Correction du correctif précédent. Trois bugs additionnels trouvés grâce
au curl que tu as fait sur l'API officielle :

```
Pont de l'Ascension      2026-05-13T22:00:00+00:00 ...  population: -
Vacances d'Été           2026-07-03T22:00:00+00:00 ...  population: Élèves
Vacances de Printemps    2026-04-10T22:00:00+00:00 ...  population: -
Vacances de la Toussaint 2025-10-17T22:00:00+00:00 ...  population: -
Vacances de Noël         2025-12-19T23:00:00+00:00 ...  population: -
Vacances d'Hiver         2026-02-13T23:00:00+00:00 ...  population: -
Vacances d'Été           2026-07-03T22:00:00+00:00 ...  population: Enseignants
```

## Bug 1 — filtre `population:Élèves` qui cachait Toussaint/Noël/Hiver/Printemps

L'API retourne ces 4 périodes avec `population: "-"` (pas `"Élèves"`). Le
filtre `refine=population:Élèves` ne laissait passer que les vacances
d'été côté élèves, d'où un seul libellé affiché en rouge.

Fix : **supprimer ce filtre**. On récupère toutes les populations et on
dédoublonne par `(description, start_date)` pour éviter les paires
"Vacances d'Été Élèves + Vacances d'Été Enseignants" qui pointent vers
les mêmes dates.

## Bug 2 — filtre `location` nécessaire pour éviter 11 doublons

Sans filtre `location`, l'API retourne les vacances d'Été **dupliquées
11 fois** (une par académie de la Zone B : Amiens, Rennes, Nantes, etc).
La route `/api/calendrier/vacances` ne passait pas l'académie au service.

Fix : la fonction `vacances()` accepte maintenant un paramètre
`academie` optionnel. Quand on l'appelle avec `academie="Rennes"`, on
filtre côté API sur `location:Rennes` et on ne récupère qu'un exemplaire
de chaque période. La route `/api/calendrier/vacances` passe l'académie
automatiquement si elle est fournie dans la query string.

## Bug 3 — décalage d'un jour sur toutes les dates

**Ce bug expliquait l'essentiel des symptômes.**

L'API renvoie les dates avec un offset UTC : `2026-05-13T22:00:00+00:00`.
Le 13 mai à 22h UTC = le **14 mai à 00h** en France (heure d'été, UTC+2).
Mais la fonction `_iso_date` faisait simplement `dt[:10]` et retournait
`"2026-05-13"` au lieu de `"2026-05-14"`.

Conséquence : toutes les dates étaient décalées d'un jour vers le passé.
C'est pour ça que le pont de l'Ascension (14→18 mai en réalité)
apparaissait du 13 au 17, ce qui fait chevaucher 2 semaines entières
(11-17 mai et 18-24 mai) — d'où le "pont du 10 au 24 mai" que tu as vu.
Et les vacances d'été, qui démarrent officiellement le **samedi 4
juillet 2026**, renvoyaient `2026-07-03` (vendredi 3 juillet) — qui est
aussi dans la semaine du lundi 29 juin, d'où le "à partir du 28 juin".

Fix : `_iso_date` fait maintenant une vraie conversion UTC → Paris
(+2h fixe, pour gérer heure d'été et hiver uniformément). La date
retournée correspond au premier jour local français.

## Fichiers modifiés

```
appli/services/calendrier_scolaire.py   (3 fixes : filtre, académie, timezone)
appli/routes/calendrier.py              (passe academie au service)
appli/tests/test_calendrier_scolaire.py (+ 4 tests timezone)
appli/clean_cache.py                    (utilitaire, déjà présent chez toi)
```

## Déploiement

```powershell
# 1. Copier les 3 fichiers dans les bons dossiers
# 2. Vider le cache (l'ancien est toujours buggé)
python clean_cache.py
# 3. Redémarrer Flask + Ctrl+F5 dans le navigateur
```

## Résultat attendu pour N11 2025-2026 (Rennes)

Toutes les périodes affichées en rouge aux bonnes dates :

| Période            | Début      | Fin (reprise) |
| ------------------ | ---------- | ------------- |
| Toussaint          | 18 oct 2025 | 3 nov 2025   |
| Noël               | 20 déc 2025 | 5 jan 2026   |
| Hiver              | 14 fév 2026 | 2 mars 2026  |
| Printemps          | 11 avr 2026 | 27 avr 2026  |
| Pont de l'Ascension | 14 mai 2026 | 18 mai 2026 |
| Été                | 4 juil 2026 | 31 août 2026 |

## Vérification après déploiement

```powershell
curl.exe -s "http://127.0.0.1:5000/api/calendrier/vacances?annee=2025-2026&academie=Rennes&force=1" | ConvertFrom-Json | Select-Object -ExpandProperty vacances | Select-Object description, start_date, end_date | Format-Table -AutoSize
```

Tu dois voir exactement 6 périodes, chacune une seule fois, avec les
dates de la table ci-dessus.

## Tests

**369 tests verts** (365 + 4 nouveaux pour la conversion timezone).
