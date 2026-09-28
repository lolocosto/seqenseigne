# Chantier 14 — Snapshot complet (sessions 1, 2, 3)

Extraction du zip dans `D:\Enseignement\seqenseigne\` (ta racine projet
habituelle). L'archive respecte l'arborescence cible ; les fichiers
existants seront écrasés par les versions livrées.

## Arborescence du zip

```
appli/
  app.py                                       ← modifié (session 3)
  services/
    paquet_parseur.py                          ← session 1, mis à jour en session 2 (correctif archi)
    paquet_regles_atome.py                     ← session 1
    latex_rendu_atome.py                       ← session 2, correctif session 2
    compilateur_pdf.py                         ← session 3, correctif détection MiKTeX
    configuration.py                           ← session 3
  scripts/
    peuplement_14_paquet_vers_base.py          ← session 1
    peuplement_14_verif_couverture.py          ← session 1, mis à jour en correctif session 2
    peuplement_14_rapport_dette.py             ← session 1 bis
  routes/
    rendu_atome.py                             ← session 3
  tests/
    test_paquet_parseur.py                     ← session 1
    test_paquet_peuplement.py                  ← session 1
    test_paquet_verification.py                ← session 1
    test_latex_rendu_atome.py                  ← session 2
    test_compilateur_pdf.py                    ← session 3, mis à jour au correctif MiKTeX
    test_configuration.py                      ← session 3
    test_route_rendu_atome.py                  ← session 3
  doc/
    chantier_14_session_1.md
    chantier_14_session_2.md
    chantier_14_session_2_correctif.md
    chantier_14_session_3.md
    chantier_14_dette_coherence.md

reference/paquet/
  seqenseigne-theme.sty                        ← session 1 : ajout de \boiteJauneModere et \seqTitreTabV
```

## Procédure après extraction

```powershell
cd D:\Enseignement\seqenseigne\appli

# 1. Vérifier que les 162 tests du chantier 14 passent
..\outils\python\python.exe -m pytest tests\test_paquet_parseur.py tests\test_paquet_peuplement.py tests\test_paquet_verification.py tests\test_latex_rendu_atome.py tests\test_compilateur_pdf.py tests\test_configuration.py tests\test_route_rendu_atome.py -v

# 2. Peupler la base avec les définitions du paquet
..\outils\python\python.exe scripts\peuplement_14_paquet_vers_base.py --paquet ..\reference\paquet

# 3. Vérifier la couverture des atomes (optionnel, pour info)
..\outils\python\python.exe scripts\peuplement_14_verif_couverture.py

# 4. Lancer l'appli
.\lancer.bat
```

## Configuration de base (une seule fois)

Dans un autre terminal PowerShell :

```powershell
Invoke-RestMethod -Uri http://localhost:5000/api/configuration `
    -Method Post -ContentType 'application/json' `
    -Body '{"chemin_sources_livrets": "D:\\Enseignement\\seqenseigne\\sequences"}'
```

(Adapte le chemin si tes sources sont ailleurs.)

Le `chemin_pdflatex` est auto-détecté chez toi grâce au correctif MiKTeX
(convention `texmfs\install\miktex\bin\x64\`), donc pas besoin de le
configurer.

## Tester la compilation

```powershell
Invoke-WebRequest -Uri http://localhost:5000/api/atomes/exercice/ex_c604c3d2/rendu-pdf `
    -Method Post -OutFile atome.pdf
```

(Remplace `ex_c604c3d2` par un id d'exercice valide chez toi.)

## État global

- 162 tests chantier 14 verts
- 340 définitions du paquet en base
- Couverture : 5 macros non-couvertes résiduelles (voir doc de dette)
- Route `POST /api/atomes/<type>/<id>/rendu-pdf` opérationnelle
- Cache PDF dans `data/cache_rendus/` (à ajouter au `.gitignore`)

## Sessions suivantes

- Session 4 (UI) : bouton « Voir le rendu » dans les ateliers Notion /
  Méthode / Exercice avec affichage inline du PDF et des erreurs de
  compilation.
