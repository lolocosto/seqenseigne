# Redémarrage v0.37.1 — Outil d'import de plan lançable sous Windows

`outils/importer_plan_salle_tikz.py` échouait chez l'utilisateur
(`No module named 'services'`, puis `No module named 'outils'` avec `-m`) : le
Python portable (`..\outils\python\python.exe`, distribution embeddable) ne
met pas le dossier courant dans `sys.path`. Les autres outils (ex.
`verifier_md5.py`) n'importent rien de l'appli, d'où l'absence du problème.

Correctif : le script ajoute `appli/` (parent de `outils/`) à `sys.path`.
Lancement :

    ..\outils\python\python.exe outils\importer_plan_salle_tikz.py <plan.tex> --salle 302 [--apply]

Règle pour les futurs outils qui importent `services`/`persistence` : même
amorce `sys.path`, et documenter le lancement par chemin (pas `python -m`).
Test ajouté : lancement du script par son chemin dans un sous-processus.
