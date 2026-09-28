# Redémarrage v0.13.6.8.2.1

**Session du 15 mai 2026 — Restauration des wrappers `valider_carte`/`devalider_carte`**

---

## Diagnostic

Après installation de v0.13.6.8.2, **10 tests ont échoué** dans 3
fichiers de tests et 1 script :

- `tests/test_v0_13_6_2_3_peuplement_cartes_n10.py` (2 échecs)
- `tests/test_v0_13_6_3_2_assemblage_cartes.py` (3 échecs)
- `tests/test_v0_13_6_3_referentiel_eval_cartes.py` (5 échecs)
- `scripts/peupler_cartes_n10.py` (cause les 2 premiers échecs)

Symptôme uniforme :
```
AttributeError: module 'services.cartes_automatisme' has no
attribute 'valider_carte'. Did you mean: 'lire_carte'?
```

**Cause** : v0.13.6.8.2 avait supprimé `valider_carte()` et
`devalider_carte()` du service carte, mais ces fonctions étaient
encore utilisées par 4 fichiers qui n'étaient pas dans mon code
source de référence (`/home/claude/work/`).

**Ma faute** : avant la rupture, j'avais cherché les usages de
`valider_carte` dans `/home/claude/work/` mais j'aurais dû élargir
à `scripts/` et m'attendre à des tests plus récents que ma copie.

---

## Décision : restaurer les wrappers dépréciés

Plutôt que d'adapter les 4 fichiers (qui auraient nécessité un
aller-retour), tu as choisi l'**option 1** : restaurer
`valider_carte()` et `devalider_carte()` comme **wrappers minimaux
dépréciés** qui délèguent au nouveau mécanisme unifié.

Bénéfices :
- Les 10 tests passent immédiatement
- La rationalisation backend de v0.13.6.8.2 reste effective
  (un seul code path en interne, même via les wrappers)
- Le frontend reste sur le mécanisme unifié

Coût accepté :
- 2 fonctions « zombie » à nettoyer en v0.14 (avec adaptation
  des 4 fichiers)

---

## Implémentation

### `services/cartes_automatisme.py`

Ajout en fin de fichier (après l'enregistrement du hook) :

```python
def valider_carte(conn, carte_id) -> dict:
    """[DEPRECATED v0.13.6.8.2.1] Wrapper vers changer_etat_atome."""
    from services.etats_edition import changer_etat_atome
    changer_etat_atome(conn, 'carte', carte_id, 'valide')
    conn.commit()
    return lire_carte(conn, carte_id)


def devalider_carte(conn, carte_id) -> dict:
    """[DEPRECATED v0.13.6.8.2.1] Wrapper vers changer_etat_atome."""
    from services.etats_edition import changer_etat_atome
    changer_etat_atome(conn, 'carte', carte_id, 'en_cours')
    conn.commit()
    return lire_carte(conn, carte_id)


# Alias pour les imports rétrocompat
from services.etats_edition import ValidationPedagogiqueErreur
```

---

## Différences subtiles avec l'ancien comportement

### Idempotence à la place de DejaValide/DejaEnCours

Ancien comportement :
```python
valider_carte(conn, id)
valider_carte(conn, id)  # → DejaValide
```

Nouveau comportement :
```python
valider_carte(conn, id)
valider_carte(conn, id)  # OK, idempotent (re-applique l'UPDATE + hook)
```

Pourquoi ce choix ? Le nouveau mécanisme générique `changer_etat_atome`
est volontairement tolérant : passer à l'état courant n'est pas une
erreur. C'est aussi ce qui permet au `test_peuplement_idempotent`
de relancer le script deux fois sans plantage.

**Vérifié** : aucun des 4 fichiers en échec ne dépendait de
`DejaValide`/`DejaEnCours`. Donc cette différence n'a pas d'impact.

### ValidationPedagogiqueErreur : maintenant celle d'etats_edition

Ancien comportement :
```python
from services.cartes_automatisme import ValidationPedagogiqueErreur
# c'était une classe spécifique au module carte
```

Nouveau comportement :
```python
from services.cartes_automatisme import ValidationPedagogiqueErreur
# c'est maintenant un alias vers etats_edition.ValidationPedagogiqueErreur
```

Le code `except ValidationPedagogiqueErreur` continue de fonctionner
parce que `cartes_automatisme.ValidationPedagogiqueErreur` IS
(identité Python) `etats_edition.ValidationPedagogiqueErreur`.

Vérifié dans la sandbox :
```python
>>> ValidationPedagogiqueErreur is VPE_official
True
```

---

## Validation chez toi

1. Relance `pytest tests/` → les 10 erreurs précédentes doivent
   disparaître. Total attendu : ≈ 3229 passed (3219 OK +
   10 nouvellement OK).
2. Le script `peupler_cartes_n10.py` fonctionne dans les deux
   modes (premier run + relance idempotente).
3. Tout le reste comme v0.13.6.8.2 :
   - Bascule de validation depuis tous les ateliers
   - Multi-sélection
   - Toast d'erreur explicite si validation pédagogique échoue

---

## Fichiers livrés

| Fichier | Statut |
|---|---|
| `appli/services/cartes_automatisme.py` | enrichi (wrappers dépréciés ajoutés) |

Décompresser à la racine de `seqenseigne/`. F5.

C'est un **patch minimal** : seul `services/cartes_automatisme.py`
change. Les 7 autres fichiers de v0.13.6.8.2 restent en place.

---

## Leçon retenue (suite des v0.13.6.8 → 8.2 → 8.2.1)

**Avant une rupture (suppression d'API publique), élargir la recherche
au-delà du code source de référence.** Dans mon cas, j'aurais dû :
1. Demander explicitement à Laurent un `grep -rn "valider_carte"
   appli/` avant de proposer la suppression
2. Ou bien proposer dès le départ l'approche « wrappers dépréciés »
   comme transition douce

La rupture nette était belle en théorie mais m'a coûté 1 livraison
supplémentaire. L'approche par wrappers aurait été 30 secondes de
plus à coder mais aurait évité l'aller-retour.

C'est noté pour les prochains chantiers de rationalisation
(notamment l'unification du mécanisme d'état pour les assemblages
quand on attaquera l'atelier d'assemblage de séquence-dans-niveau).

---

## Suite

Inchangée :
- v0.13.6.9 : chantier A — homogénéisation `placedTags`
- v0.13.6.10 : chantier B — bouton « reprendre titre objectif »
- v0.13.6.11+ : chantier C — refonte modèle carte
- v0.13.6.12+ : chantier D — suppression sélecteur objectif fiche
- v0.13.7+ : chantier F — sections configurables

À noter dans la roadmap **v0.14** : nettoyage des wrappers dépréciés
`valider_carte()` / `devalider_carte()` + adaptation des 4 fichiers :
- `scripts/peupler_cartes_n10.py`
- `tests/test_v0_13_6_2_3_peuplement_cartes_n10.py`
- `tests/test_v0_13_6_3_2_assemblage_cartes.py`
- `tests/test_v0_13_6_3_referentiel_eval_cartes.py`
