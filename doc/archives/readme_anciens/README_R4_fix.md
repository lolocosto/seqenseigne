# seqenseigne — R4-fix : Restauration des onglets Thème et Séquence (cycle)

Correctif d'urgence suite à deux écrasements successifs :
- **R4c** a livré un `app.js` complet qui a écrasé le tien patché en R2/R3
- **R4d** a livré un `index.html` complet qui a écrasé le tien modifié en R2/R3

Résultat : chez toi après déploiement de R4c + R4d, les onglets **Thème** et
**Séquence (cycle)** n'étaient plus visibles dans l'UI Ateliers, alors
qu'ils fonctionnaient jusqu'à R3.

## Ce que ce ZIP contient

**2 fichiers** à remplacer :

| Fichier | Rôle |
|---|---|
| `appli/static/app.js` | Ton app.js actuel + patch `atelSwitch` pour gérer `theme` et `seqcycle` (lignes ajoutées dans `atelSwitch`) |
| `appli/templates/index.html` | Ton index.html actuel + bouton Thème + bouton Séquence (cycle) + panneaux des deux ateliers + 2 scripts JS |

Les 4 modifs R4d sont **préservées** : le libellé « Séquence (niveau) »
est bien là, idem pour les 3 autres modifs cosmétiques de R4d.

## Déploiement

```powershell
# Extraire le ZIP dans appli/ (il ne touche que 2 fichiers : app.js et index.html)

# Ctrl+F5 dans le navigateur (Flask recharge les templates auto, mais le JS a un cache)

# Vérifier visuellement : Ateliers → 6 boutons dans la sous-nav
# (Exercice, Notion, Méthode, Séquence (niveau), Thème, Séquence (cycle))
# Cliquer sur Thème → les données doivent s'afficher
# Cliquer sur Séquence (cycle) → idem
```

Pas besoin de relancer Flask.

## Contrôles post-déploiement

```powershell
# Les 6 boutons doivent être présents
Select-String -Path templates\index.html -Pattern "atl-btn-" | Measure-Object | Select-Object -ExpandProperty Count
# Attendu : 6

# atelSwitch doit contenir theme et seqcycle
Select-String -Path static\app.js -Pattern "'theme','seqcycle'"
# Attendu : 1 ligne trouvée
```

## Leçon apprise — engagement pour la suite

À partir de maintenant, je ne livrerai **plus jamais** un fichier existant
(`app.js`, `index.html`, `app.py`, etc.) dans sa totalité. Pour tout fichier
qui existe déjà chez toi, je livrerai **un patch explicite** avec un bloc
« recherche » et un bloc « remplacement », à appliquer ligne par ligne.

La règle déjà mise en place pour les tests à R4c (« on ne livre que les
vrais nouveaux fichiers de test, pas les tests existants qu'on modifie »)
s'étend maintenant à **tous les fichiers existants**.

Seuls les **nouveaux** fichiers (préfixés `test_RX_*`, nouveaux services,
nouvelles routes…) seront livrés complets.
