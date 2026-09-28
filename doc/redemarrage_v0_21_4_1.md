# Redémarrage v0.21.4.1 — Indispos au calendrier : afficher les dates

Ajustement d'affichage sur la v0.21.4. Purement front (un fichier).

## Le point

Sur le calendrier de la Progression (organisé par semaine), une indisponibilité
n'affichait sa date que pour les plages de plusieurs journées. Pour les indispos
« séances » et les journées uniques, la date manquait.

## Le correctif

Chaque pastille d'indisponibilité affiche désormais **toujours** sa/ses date(s),
au format **jj/mm** (l'année est implicite dans le calendrier) :

| Type | Affichage |
|------|-----------|
| Séances (une journée, plage de créneaux) | `11/09 S1→S4 · Cohésion 6e` |
| Journée unique | `22/09 · Sortie Nantes (classe)` |
| Plage de journées | `09/11→13/11 · Voyage (classe)` |

## Fichiers

- `static/atelier_progression.js` : composition de l'étiquette d'indisponibilité
  dans `_ligneSemaine` (date FR jj/mm + créneaux pour le type séances + motif +
  portée).

## Tests

- vitest : 193 passed (0 régression). Syntaxe OK. Affichage vérifié sur les
  trois cas.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Purement front.

## Suite

- v0.21.5 : vue « progression annuelle réalisée » par classe + bouton de
  décalage depuis une indisponibilité.
