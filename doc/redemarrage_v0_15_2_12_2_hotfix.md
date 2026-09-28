# Hotfix v0.15.2.12.2 — Regex import : tolérance espace

## Symptôme (terrain Laurent)

```
PS> ..\outils\python\python.exe .\outils\importer_referentiel_externe.py \
        --ref-id N11_v2025 --pdfs-source ..\Livrets\ --data-dir ./data
✅ Référentiel N11_v2025 (N11) importé.
   PDFs copiés : 0
   ⚠ PDFs non mappés (14) :
     - 4e3 S01_Livret.pdf
     - 4e3 S02_Livret.pdf
     ...
```

Tes PDFs utilisent un **espace** comme séparateur (`4e3 S01_Livret.pdf`)
là où ma regex d'origine exigeait un underscore (`4e3_S01_Livret.pdf`).

## Correctif

`outils/importer_referentiel_externe.py` — regex assouplie :

```python
# Avant
_RE_LIVRET_SEQUENCE = re.compile(r'^[^/]*_S(\d{2})_Livret\.pdf$', re.IGNORECASE)

# Après (non-greedy : accepte n'importe quel séparateur ou aucun)
_RE_LIVRET_SEQUENCE = re.compile(r'^[^/]*?S(\d{2})_Livret\.pdf$', re.IGNORECASE)
```

D�sormais reconnus :

| Pattern | Exemple |
|---|---|
| Underscore (origine) | `4e3_S01_Livret.pdf` |
| **Espace (ton cas)** | `4e3 S01_Livret.pdf` |
| Tiret | `classe-S14_Livret.pdf` |
| Pas de préfixe | `S05_Livret.pdf` |

Pas de faux positifs introduits :
- `progression.pdf` → toujours rejeté
- `S1_Livret.pdf` (1 seul chiffre) → toujours rejeté
- `4e3_S01_autrechose.pdf` (mauvais suffixe) → toujours rejeté

## Tests

3 nouveaux tests dans `tests/test_v0_15_2_10_importer_referentiel_externe.py` :
- espace séparateur
- tiret séparateur
- pas de préfixe

Total : 17 tests dans ce fichier (+3 par rapport à v0.15.2.10).

## Application

```powershell
..\outils\python\python.exe -m pytest tests/test_v0_15_2_10_importer_referentiel_externe.py -q
# Attendu : 17 passed
```

Puis tu peux relancer l'import :

```powershell
..\outils\python\python.exe .\outils\importer_referentiel_externe.py `
    --ref-id N11_v2025 `
    --pdfs-source ..\Livrets\ `
    --data-dir ./data
# Attendu : PDFs copiés : 14
```

(L'idempotence du dossier `_fige/` fait que tu peux relancer
autant de fois que nécessaire — le dossier précédent est effacé puis
recréé.)
