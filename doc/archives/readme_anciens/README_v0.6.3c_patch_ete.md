# seqenseigne v0.6.3c — patch « vacances d'été + pont de l'Ascension »

Correctif pour le calendrier visuel livré en v0.6.3c. Deux problèmes
corrigés.

## Problème 1 — Les vacances d'été débordaient largement sur mai-juin

Symptôme observé : dans le calendrier, les semaines de mai, juin et
juillet apparaissaient en rouge avec le label « Vacances d'été ».

Cause : l'API officielle `fr-en-calendrier-scolaire` ne renvoie PAS les
grandes vacances (elles n'ont pas de date de fin puisqu'elles enchaînent
sur l'année suivante). Le code de synthèse (`_ajouter_vacances_ete`)
prenait `max(end_date) + 1 jour` comme début des vacances d'été. Or
l'API renvoie `end_date` = jour de reprise des cours (ex: lundi 27 avril
pour les vacances de printemps Zone B 2026). Le code synthétisait donc
« Vacances d'été du 28 avril au 31 août », ce qui masquait tout le
dernier trimestre en rouge.

Correction : utiliser une **table de dates officielles** publiées au JO
(arrêtés du 7 décembre 2022 et du 22 octobre 2025), avec fallback
algorithmique (premier samedi ≥ 4 juillet) pour les années non listées.

Table disponible pour les années 2023-2024, 2024-2025, 2025-2026,
2026-2027, pour les 3 zones (A, B, C).

Pour Zone B 2025-2026 : les vacances d'été commencent désormais le
**samedi 4 juillet 2026**, date officielle.

## Problème 2 — Le pont de l'Ascension manquait

L'API ne renvoie pas non plus le pont de l'Ascension (jour férié + jours
ouvrés libérés = typiquement 4 jours consécutifs en mai). Le pont
apparaissait donc comme des jours de cours.

Correction : synthèse via une **table dure** `PONT_ASCENSION` pour les
années connues. Pour 2025-2026 : **jeudi 14 mai → lundi 18 mai 2026**
(jeudi Ascension + vendredi + samedi libérés, reprise lundi).

## Fichiers modifiés

```
appli/services/calendrier_scolaire.py   (table officielle + fallback algorithmique + pont Ascension)
appli/tests/test_calendrier_scolaire.py (tests adaptés + nouveau test pont)
```

## Déploiement

```powershell
# 1. Copier les 2 fichiers
# 2. VIDER LE CACHE des vacances (indispensable sinon l'ancienne synthèse
#    buggée sera servie depuis cache_api) :

cd D:\Enseignement\seqenseigne\appli
python -c "import sqlite3; c=sqlite3.connect('data/seqenseigne.db'); c.execute(\"DELETE FROM cache_api WHERE cle LIKE 'vacances:%'\"); c.commit()"

# 3. Redémarrer Flask + Ctrl+F5 dans le navigateur
```

Après ça, le calendrier de la progression N11 2025-2026 (Rennes Zone B)
affichera :

- semaines du 18 oct au 2 nov → « Vacances de la Toussaint » (rouge)
- semaines du 20 déc au 4 jan  → « Vacances de Noël » (rouge)
- semaines du 14 fév au 1ᵉʳ mars → « Vacances d'Hiver » (rouge)
- semaines du 11 avril au 26 avril → « Vacances de Printemps » (rouge)
- semaine du 14 au 17 mai → « Pont de l'Ascension » (rouge)
- à partir du 4 juillet → « Vacances d'été » (rouge, jusqu'au 31 août)

Les semaines de mai et juin (hors pont) redeviennent des **semaines de
classe normales**, comme attendu.

## Tests

**365 tests verts** (4 tests calendrier adaptés + 1 nouveau pour le pont
d'Ascension).

Nouveaux tests dans `test_calendrier_scolaire.py` :
- `test_ete_utilise_table_officielle_zone_B` : vérifie que Zone B
  2025-2026 → début 4 juillet 2026 (pas un calcul depuis end_date)
- `test_pont_ascension_synthetise` : vérifie l'ajout du pont 14 → 18 mai
- `test_pas_de_doublon_si_ete_deja_present` : si l'API renvoie un jour
  elle-même les vacances d'été, pas de doublon
- `test_fallback_annee_inconnue` : année hors table → 1er samedi ≥ 4 juillet

## Roadmap des dates officielles

Les dates 2027-2028 seront publiées au JO fin 2026 (habituellement en
octobre). Quand elles sortent, il suffit d'ajouter une ligne dans les
dicts `VACANCES_ETE_DEBUT` et `PONT_ASCENSION` du fichier
`services/calendrier_scolaire.py`. Le fallback algorithmique protège
toutes les années futures en attendant.
