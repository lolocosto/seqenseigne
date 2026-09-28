# Redémarrage v0.24.2 — Planning : espacement date/enveloppes corrigé

Correctif de mise en page du planning des automatismes. Purement le générateur
LaTeX (un fichier).

## Le point

Avec l'interligne ×1,5 global (v0.24.1), l'espace entre une date et ses
enveloppes était aussi grand que l'espace jusqu'à la date suivante : les
enveloppes semblaient se rapporter à la date du dessous.

## Le correctif

- **Interligne serré à l'intérieur** de chaque case (date + ses enveloppes) :
  `\linespread{1}` dans la `\parbox` et `\\[1pt]` entre la date et les
  enveloppes → les enveloppes restent visuellement collées à LEUR date.
- **Air entre les rangées** géré séparément par un `\baselineskip` large (34 pt)
  au niveau du paragraphe → les rangées de dates sont bien aérées.
- Le `\linespread{1.5}` global (qui créait l'ambiguïté) est retiré.

Résultat : date encadrée + enveloppes groupées, avec de l'espace entre les
lignes de dates, sans confusion d'appartenance.

## Fichiers

- `services/planning_automatismes_tex.py` : `_case_jour` (linespread 1 interne),
  espacement de rangée via `\baselineskip`, suppression du linespread global.

## Tests

- vitest : 193 passed (0 régression).
- Compilation réelle vérifiée : A3 paysage, 0 débordement, date collée à ses
  enveloppes, air entre rangées.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Purement génération PDF.

## Suite

Cadrage en cours : référentiels externes (champ type principal/MER, structure
séquences + docs, sous-onglet « Référentiel externe » dans Conception →
Niveau, formats PDF affichés / autres téléchargeables).
