# Redémarrage v0.13.5.1.5.1 — Patch UTF-8 côté lecture subprocess

Date : 10 mai 2026
Périmètre : 2 fichiers de test corrigés

---

## Pourquoi un patch ?

Après application de v0.13.5.1.5, le run pytest chez Laurent a montré
**14 tests rouges** (vs 20 avant le fix) :

- 13 dans `tests/test_migrer_methodes_objectifs.py`
- 1 dans `tests/test_verifier_md5.py` (`test_detection_troncature_en_milieu_de_fonction`)

**Plus aucun `UnicodeEncodeError`** (l'erreur d'origine est résolue), mais
les assertions `assert "À lier..." in r.stdout` plantent maintenant
parce que le texte récupéré est du *mojibake* :

```
'À lier (methode_id NULL → posé) :    3'   # attendu
'Ã€ lier (methode_id NULL â†’ posÃ©) :    3'  # reçu
```

## Diagnostic

Le tuyau a deux extrémités. v0.13.5.1.5 a réglé l'**écriture** (le script
écrit en UTF-8 quoi qu'il arrive) mais pas la **lecture** :

```python
subprocess.run(cmd, capture_output=True, text=True, ...)
```

Sans paramètre `encoding=`, `text=True` décode avec la locale du système.
Sur ton Windows français, cette locale est cp1252. Le script écrit donc
les octets UTF-8 `c3 a9` pour `é`, et le test les relit comme cp1252 et
voit `Ã©`. Tout en chaîne.

Et le 14e test (`test_detection_troncature_en_milieu_de_fonction`) avait
un défaut différent : un `write_text("def foo():\n...")` Windows
convertit chaque `\n` en `\r\n`, donc le fichier sur disque fait 2 octets
de plus que `len(contenu)` — le delta calculé devient `(-25)` au lieu de
`(-27)`. Bug de portabilité de mon test.

## Fix

### `tests/test_migrer_methodes_objectifs.py` — fonction `_executer_script`

Ajout de `encoding="utf-8"` dans le `subprocess.run` :

```python
return subprocess.run(
    cmd, cwd=str(racine), capture_output=True, text=True,
    input=input_stdin, encoding="utf-8",
)
```

Plus une docstring qui documente *pourquoi*, pour que ce fix ne soit pas
remis en cause par un futur refactor.

### `tests/test_verifier_md5.py` — `test_detection_troncature_en_milieu_de_fonction`

Passage en `write_bytes()` pour contrôler exactement les octets sur
disque, sans conversion `\n → \r\n` automatique sur Windows. MD5 calculé
directement sur les bytes via `hashlib.md5(contenu_complet)`.

## Validation

44 tests verts côté Linux sur les 2 fichiers patchés (les 24 de
`test_migrer_methodes_objectifs` + les 20 de `test_verifier_md5`).

Côté Windows, attendu :

```
2112 passed, 5 skipped, 0 failed
```

(soit +14 tests qui passent par rapport au run actuel chez toi, qui
montrait 14 failed / 2098 passed).

## Pourquoi `encoding="utf-8"` est-il pérenne ?

C'est le pattern **standard** pour des subprocess Python qui doivent
fonctionner identiquement sur Linux, macOS et Windows. La locale par
défaut diffère selon l'OS et même selon le compte utilisateur ; forcer
UTF-8 supprime cette variabilité.

Pattern à appliquer désormais à tout futur test qui invoque un script
Python via subprocess. Tu trouveras cette consigne dans `appli/doc/GOTCHAS.md`
quand on l'aura rédigé.

## Fichiers livrés (2)

| Fichier | Action |
|---|---|
| `appli/tests/test_migrer_methodes_objectifs.py` | Modifié (12 lignes ajoutées dans `_executer_script` : docstring + paramètre `encoding`) |
| `appli/tests/test_verifier_md5.py` | Modifié (test CRLF-safe via `write_bytes`) |

MD5 et tailles dans `MANIFEST.md5` à la racine.

## Suite

Une fois ces 14 tests verts confirmés chez toi, on enchaîne sur la
**v0.13.5.2** (transitions auto en_cours ↔ valide via hooks) comme
prévu, ou sur les chantiers d'hygiène (`CONVENTIONS.md` + `GOTCHAS.md`,
intégration dans `lancer.bat`) selon ton choix.
