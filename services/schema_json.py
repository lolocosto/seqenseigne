"""services/schema_json.py — v0.51.1

Validateur JSON Schema minimal (sous-ensemble de la norme 2020-12), pour
valider les fichiers d'échange sans dépendance supplémentaire (le Python
portable de l'appli locale n'embarque pas `jsonschema`).

Mots-clés pris en charge : type (chaîne ou liste), const, enum, properties,
required, additionalProperties (booléen), items, minItems, minLength,
pattern, minimum, $ref (« #/$defs/… »). Les autres mots-clés (title,
description, $schema, $id…) sont ignorés. Les tests vérifient en plus la
conformité avec la bibliothèque `jsonschema` quand elle est disponible.
"""

from __future__ import annotations

import re

_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def valider(valeur, schema: dict, racine: dict | None = None,
            chemin: str = "$") -> list[str]:
    racine = racine or schema
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/"):
            return [f"{chemin} : $ref non pris en charge ({ref})"]
        cible = racine
        for morceau in ref[2:].split("/"):
            cible = cible[morceau]
        return valider(valeur, cible, racine, chemin)
    erreurs: list[str] = []
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_TYPES[x](valeur) for x in types):
            return [f"{chemin} : type attendu {'/'.join(types)}"]
    if "const" in schema and valeur != schema["const"]:
        erreurs.append(f"{chemin} : valeur attendue {schema['const']!r}")
    if "enum" in schema and valeur not in schema["enum"]:
        erreurs.append(f"{chemin} : valeur {valeur!r} hors de {schema['enum']}")
    if isinstance(valeur, str):
        if "minLength" in schema and len(valeur) < schema["minLength"]:
            erreurs.append(f"{chemin} : chaîne trop courte")
        if "pattern" in schema and not re.search(schema["pattern"], valeur):
            erreurs.append(f"{chemin} : format invalide ({valeur!r})")
    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
        if "minimum" in schema and valeur < schema["minimum"]:
            erreurs.append(f"{chemin} : valeur inférieure à {schema['minimum']}")
    if isinstance(valeur, dict):
        props = schema.get("properties", {})
        for cle in schema.get("required", []):
            if cle not in valeur:
                erreurs.append(f"{chemin} : champ obligatoire « {cle} » manquant")
        if schema.get("additionalProperties") is False:
            for cle in valeur:
                if cle not in props:
                    erreurs.append(f"{chemin} : champ inconnu « {cle} »")
        for cle, sous in props.items():
            if cle in valeur:
                erreurs.extend(valider(valeur[cle], sous, racine, f"{chemin}.{cle}"))
    if isinstance(valeur, list):
        if "minItems" in schema and len(valeur) < schema["minItems"]:
            erreurs.append(f"{chemin} : au moins {schema['minItems']} élément(s)")
        if "items" in schema:
            for i, v in enumerate(valeur):
                erreurs.extend(valider(v, schema["items"], racine, f"{chemin}[{i}]"))
    return erreurs
