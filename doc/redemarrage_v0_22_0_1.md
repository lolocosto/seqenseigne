# Redémarrage v0.22.0.1 — Correctif : ImportError du planning d'automatismes

Correctif de bug sur la v0.22.0. Le PDF du planning d'automatismes plantait avec
`ImportError: cannot import name 'config' from 'services'`.

## Cause

Dans `routes/leitner.py`, la route PDF importait un module inexistant
(`from services import config as config_mod`). Le module de configuration
s'appelle `services.configuration` (classe `Configuration`), obtenu via une
instance mise en cache sur l'app — pattern déjà utilisé par les autres routes
PDF (`routes/evaluations.py`).

## Correctif

La route PDF utilise désormais le bon pattern : instancie `Configuration` (mise
en cache sur `current_app.configuration`) et passe `pdflatex` +
`timeout_compilation_court()` à `compiler_atome`, comme les autres routes de
compilation.

## Fichiers

- `routes/leitner.py` : import et paramètres de compilation corrigés.

## Tests

- Route PDF vérifiée : plus d'`ImportError` (répond proprement ; en
  environnement sans pdflatex, renvoie 503 au lieu de planter en 500). Avec
  MiKTeX en production, produit le PDF A3.
- vitest : 193 passed (0 régression).

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Se déploie par-dessus la
v0.22.0.

## Note

Le second point signalé (progression 2026-2027) n'est pas traité ici : il
nécessite de préciser le symptôme exact (la base de développement n'a pas les
créneaux de la progression concernée). À investiguer avec une description du
problème.
