# Hotfix v0.15.2.12.1 — Fichier de test manquant dans la livraison v0.15.2.12

## Symptôme

```
FAILED tests/test_v0_15_2_9_figeage_route.py::test_figer_succes_change_etat_et_ecrit_trace - assert 2 == 1
```

## Cause

Le bump `version_schema` 1 → 2 a eu lieu en v0.15.2.11. Le test
`test_figer_succes_change_etat_et_ecrit_trace` assertait `version_schema == 1`
et a été mis à jour à `== 2` dans le même delta.

Lors de la livraison v0.15.2.12, j'ai oublié de réinclure ce fichier
dans le manifest. Si tu as appliqué directement v0.15.2.12 sans
v0.15.2.11, ton fichier de test est resté à la version v0.15.2.10 et
casse.

## Correctif

Hotfix livrant uniquement `tests/test_v0_15_2_9_figeage_route.py`.
Pas de code applicatif touché.

## Vérification

```powershell
..\outils\python\python.exe -m pytest tests/ -q
# Attendu : 3631 passed, X skipped, 0 failed
```

(Les skipped chez toi vs chez moi peuvent différer selon
l'environnement Windows/MiKTeX.)
