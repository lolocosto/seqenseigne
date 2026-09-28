# Redémarrage v0.19.1.8 — Outil d'audit d'alignement référentiel ↔ progression + complétion des livrets

Outil de vérification (et de correction ciblée) pour consolider les
référentiels 2021-22 avant d'attaquer 2022-23. Livraison **outillage
uniquement** : aucun changement d'application.

## Outil — `outils/verifier_referentiels.py`

Deux volets.

**A. Structure (lecture seule).** Pour chaque progression liée à un
référentiel, vérifie l'alignement :
- les parties attendues (déduites des créneaux : couples (séquence,
  `partie_debut`)) correspondent à `referentiel_parties` ;
- chaque séquence des créneaux existe dans `referentiel_sequences` ;
- chaque partie attendue résout au moins un objectif
  (`referentiel_objectifs.partie_numero`).

**B. PDF — livrets de séquence.** Pour chaque référentiel :
- 14 livrets `livret_sequence__<niveau>__<seq>.pdf` attendus (un par séquence
  du niveau) ;
- présents dans `data/referentiels/<ref>/_verrouille/pdfs/` ?
- les manquants peuvent être **copiés** depuis un dossier d'archives
  (`--copier-livrets <dossier>` + `--apply`), où les livrets sont nommés
  `<préfixe> S<NN>_Livret.pdf` (le code séquence est extrait du nom et le
  fichier renommé vers la convention figée). En cas de doublon dans les
  archives, le fichier le plus récemment modifié est retenu.

Les **plans de travail** sont seulement **inventoriés** (nombre trouvé dans
les archives), **pas copiés** : le modèle ne prévoit pas encore de plan par
séquence (le type `livret_plans` est un document unitaire agrégé). Leur copie
fera l'objet de la livraison suivante (« plan de travail par séquence »).

Comportement par défaut : **lecture seule** (aucune écriture). La copie n'a
lieu qu'avec `--copier-livrets … --apply`.

Codes de sortie : 0 = aligné ; 1 = écarts (structure ou PDF manquants) ;
2 = base/dossier introuvable ; 3 = erreur. (Utile en script.)

### Usage

    # Audit complet des deux référentiels 2021 (lecture seule) :
    python -m outils.verifier_referentiels

    # Audit d'un référentiel précis :
    python -m outils.verifier_referentiels --ref N10_v2021

    # Copier les livrets manquants de N10 depuis les archives 5E2 :
    python -m outils.verifier_referentiels --ref N10_v2021 \
        --copier-livrets /chemin/vers/5E2 --apply

## Résultat de l'audit (validé sur copie de la base, imports 4e3+5e2 appliqués)

- **N11_v2021** : structure **alignée** ; livrets **14/14 présents** → rien à
  faire.
- **N10_v2021** : structure **alignée** ; livrets **0/14** (dossier
  `_verrouille` absent). La copie depuis les archives 5E2 rétablit les 14
  livrets (`5e2 S01_Livret.pdf` → `livret_sequence__N10__S01.pdf`, etc.),
  après quoi l'audit est tout vert.

À noter : 19 plans de travail sont présents dans chaque archive (séquences +
parties), inventoriés mais non copiés à ce stade.

## Changements (fichiers)

- `outils/verifier_referentiels.py` (nouveau).

Aucun code d'application modifié.

## Déploiement

1. Déployer ce delta ; `python -m outils.verifier_md5`.
2. Lancer l'audit (lecture seule) pour constater l'état :

       python -m outils.verifier_referentiels

3. Pour N10, copier les livrets manquants depuis tes archives 5E2 :

       python -m outils.verifier_referentiels --ref N10_v2021 \
           --copier-livrets <dossier_5E2_décompressé> --apply

   (Adapter le chemin du dossier d'archives.) Re-lancer l'audit sans option
   pour confirmer « ✓ tout est aligné ».

## Suite

- Livraison « modèle plan par séquence » : type de document *plan de travail
  par séquence/partie* (cibles + nommage `livret_plans__<niveau>__<seq>…`),
  puis extension de cet outil pour copier aussi les plans.
- Puis : progressions 2022-23 (3E3, 5E2…), sur le modèle des imports
  historiques.
