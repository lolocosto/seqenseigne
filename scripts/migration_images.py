"""
scripts/migration_images.py — v0.7 (élargi v0.10.4.1)

Centralise toutes les images de l'arborescence de référence
(`reference/sequences/N\\d{2}/{exercices,notions,methodes,documents_annuels}/`)
dans le dossier plat `appli/data/images/`, selon les conventions :

  - Exercices         : <code_exercice>[_<suffixe libre>].png
                        (ex: N11S03E02_enonce.png)
  - Notions/methodes  : <basename_du_tex>[_<suffixe libre>].png
                        (ex: N10_S01_Notion_01_fig1.png)

v0.10.4.1 — La regex de filtrage des dossiers de niveau a été élargie
de `^N1[012]$` (limité à N10/N11/N12) à `^N\\d{2}$`. Cela couvre
maintenant N09 (cycle 3) et restera valide pour N13/N14 (lycée) sans
modification ultérieure.

Toutes les images sont converties en `.png` (les `.jpg` passent par Pillow).
Les `\\includegraphics{...}` des `.tex` source sont mis à jour pour
pointer vers les nouveaux noms (sans extension, comme c'est l'usage LaTeX).

Architecture en 2 phases :

  1) `analyser(...)` — produit un PLAN en mémoire, sans toucher au disque.
     Le plan détaille pour chaque image trouvée :
       - source       : chemin absolu de l'image
       - nom_cible    : nom de fichier dans appli/data/images/
       - type_op      : copie | conversion_jpg | skip_identique | conflit
       - hash_source  : SHA256 du contenu (pour dédoublonnage)
       - tex_utilisateurs / reecritures_tex : .tex à mettre à jour

  2) `appliquer(plan, dry_run)` — exécute le plan. En `dry_run=True`,
     n'écrit rien mais simule. Sinon : copie/convertit les images,
     ré-écrit les .tex.

Usage CLI (mode autonome) :
  python migration_images.py --reference ../reference/sequences \\
                             --images   ../appli/data/images --dry-run
  python migration_images.py --reference ../reference/sequences \\
                             --images   ../appli/data/images --apply

Usage programmatique (utilisé par la route admin web) :
  from scripts.migration_images import analyser, appliquer, formatter_rapport
  plan = analyser(racine_reference, dossier_images)
  rapport = appliquer(plan, dry_run=True)   # aperçu
  rapport = appliquer(plan, dry_run=False)  # exécution
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path


def _pillow_disponible() -> bool:
    """Pillow est utilisé seulement pour convertir .jpg → .png. Import
    paresseux pour que l'analyse fonctionne même sans Pillow installé."""
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


# Sous-dossiers de chaque niveau (N09, N10, N11, N12, …) à scanner.
# Filtrage par regex `^N\d{2}$` côté _scanner_images / _scanner_tex_source.
# v0.7.1 : ajout de livrets_de_sequence/ pour récupérer les images
# centralisées dans son sous-dossier Images/, référencées par les
# notions/méthodes via la macro \dirPrefix.
SOUS_DOSSIERS_NIVEAU = (
    'exercices', 'notions', 'methodes', 'documents_annuels',
    'livrets_de_sequence',
)

# Extensions d'images à migrer.
EXT_IMAGE_SOURCE = ('.png', '.jpg', '.jpeg', '.PNG', '.JPG', '.JPEG')

# Regex pour trouver \includegraphics[opts]{nom} dans un .tex.
RE_INCLUDEGRAPHICS = re.compile(
    r'\\includegraphics(?P<opts>\[[^\]]*\])?\{(?P<nom>[^}]+)\}'
)


# ── Plan d'opération ──────────────────────────────────────────────────────────

@dataclass
class Operation:
    """Une opération unitaire sur une image source."""
    source: Path                    # chemin absolu de l'image source
    nom_cible: str                  # nom dans data/images/ (toujours .png)
    type_op: str                    # 'copie' | 'conversion_jpg' | 'skip_identique' | 'conflit'
    hash_source: str = ''           # SHA256 du contenu source
    raison: str = ''                # message court pour le rapport
    tex_utilisateurs: list[Path] = field(default_factory=list)
    # Liste de (chemin_tex, ancien_nom_dans_includegraphics, nouveau_nom_sans_ext)
    reecritures_tex: list[tuple[Path, str, str]] = field(default_factory=list)


@dataclass
class Plan:
    """Plan complet d'une migration."""
    racine_reference: Path
    dossier_images: Path
    operations: list[Operation] = field(default_factory=list)
    images_introuvables: list[tuple[Path, str]] = field(default_factory=list)
    conflits: list[str] = field(default_factory=list)
    # Images sur disque mais qu'aucun .tex ne référence (potentiels déchets).
    orphelines: list[Path] = field(default_factory=list)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _hash_fichier(p: Path) -> str:
    """SHA256 du contenu binaire."""
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _basename_sans_ext(nom: str) -> str:
    """Renvoie le stem (gère .png, .jpg, .jpeg ; retire le chemin éventuel
    d'un \\includegraphics{sous/dossier/img})."""
    return Path(nom).stem


def _extraire_inclusions_tex(chemin_tex: Path) -> list[str]:
    """Liste les noms d'image référencés par \\includegraphics dans le .tex."""
    try:
        contenu = chemin_tex.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return []
    return [m.group('nom') for m in RE_INCLUDEGRAPHICS.finditer(contenu)]


def _calculer_nom_cible(image_source: Path,
                        tex_utilisateur: Path | None) -> str:
    """
    Calcule le nom cible dans data/images/, toujours en .png.

    - Si on connaît le .tex qui utilise l'image, on respecte la convention :
      <basename_du_tex>[_<suffixe>].png
      Le suffixe est dérivé du nom actuel de l'image si différent du
      basename ; sinon l'image prend exactement le nom du .tex.

    - Si on ne connaît pas le .tex utilisateur, on garde le stem d'origine
      en .png (cas de fallback ; figurera dans le rapport pour arbitrage).
    """
    nom_source_stem = image_source.stem
    if tex_utilisateur is None:
        return f"{nom_source_stem}.png"

    base_tex = tex_utilisateur.stem

    # Cas 1 : nom de l'image = nom du .tex → on garde tel quel.
    if nom_source_stem == base_tex:
        return f"{base_tex}.png"

    # Cas 2 : nom commence par <base_tex>_ → conforme à la convention.
    if nom_source_stem.startswith(base_tex + '_'):
        return f"{nom_source_stem}.png"

    # Cas 3 : nom commence par <base_tex> sans underscore → on en insère un.
    if nom_source_stem.startswith(base_tex):
        suffixe = nom_source_stem[len(base_tex):]
        return f"{base_tex}_{suffixe}.png"

    # Cas 4 : nom totalement différent → on préfixe avec base_tex.
    return f"{base_tex}_{nom_source_stem}.png"


# ── Scan de l'arborescence ───────────────────────────────────────────────────

def _scanner_images_source(racine_reference: Path) -> list[Path]:
    """Liste toutes les images des sous-dossiers concernés des niveaux."""
    images = []
    if not racine_reference.is_dir():
        return images
    for niveau_dir in sorted(racine_reference.iterdir()):
        if not niveau_dir.is_dir() or not re.match(r'^N\d{2}$', niveau_dir.name):
            continue
        for sous in SOUS_DOSSIERS_NIVEAU:
            base = niveau_dir / sous
            if not base.is_dir():
                continue
            for ext in EXT_IMAGE_SOURCE:
                images.extend(base.rglob(f'*{ext}'))
    return sorted(set(images))


def _scanner_tex_source(racine_reference: Path) -> list[Path]:
    """Liste tous les .tex dans les sous-dossiers concernés des niveaux."""
    fichiers = []
    if not racine_reference.is_dir():
        return fichiers
    for niveau_dir in sorted(racine_reference.iterdir()):
        if not niveau_dir.is_dir() or not re.match(r'^N\d{2}$', niveau_dir.name):
            continue
        for sous in SOUS_DOSSIERS_NIVEAU:
            base = niveau_dir / sous
            if not base.is_dir():
                continue
            fichiers.extend(base.rglob('*.tex'))
    return sorted(set(fichiers))


def _index_inverse_tex(tex_files: list[Path]) -> dict[str, list[Path]]:
    """Construit un index : stem_d_image_référencée → liste de .tex utilisateurs.

    v0.7.1 : la liste de .tex utilisateurs est triée par chemin pour
    garantir un résultat déterministe quand plusieurs .tex partagent une
    image (cas typique : pavage_tomettes.jpg utilisée par N10/S11/M05 et
    N11/S11/M06). Le 1er .tex de la liste triée fait office d'utilisateur
    « principal » et donne son nom à l'image cible.
    """
    index: dict[str, list[Path]] = {}
    for tex in tex_files:
        for nom in _extraire_inclusions_tex(tex):
            stem = _basename_sans_ext(nom)
            index.setdefault(stem, []).append(tex)
    # Tri déterministe par chemin (ordre alphabétique).
    for stem in index:
        index[stem] = sorted(set(index[stem]))
    return index


def _index_hashes_cible(dossier_images: Path) -> dict[str, str]:
    """Construit un index hash → nom_de_fichier sur le dossier cible.
    Permet de détecter qu'une image source a déjà été migrée sous un
    nom différent (cas où le .tex a été réécrit lors d'une passe
    précédente, et l'image source est devenue « orpheline » du point
    de vue de l'index inverse)."""
    index: dict[str, str] = {}
    if not dossier_images.is_dir():
        return index
    for f in dossier_images.iterdir():
        if not f.is_file() or f.suffix.lower() != '.png':
            continue
        try:
            index[_hash_fichier(f)] = f.name
        except OSError:
            continue
    return index


# ── Analyse ──────────────────────────────────────────────────────────────────

def analyser(racine_reference: Path, dossier_images: Path) -> Plan:
    """
    Construit le plan complet sans toucher au disque.

    Stratégie :
      1. Indexer tous les .tex et leurs \\includegraphics.
      2. Pour chaque image source, identifier le .tex utilisateur principal
         (voisin direct si possible, premier sinon).
      3. Calculer le nom cible et détecter les collisions par hash :
         - Hash identique → skip (dupliqué).
         - Hash différent → conflit ; on garde la 1ère, on suffixe la 2nde.
      4. Recenser les réécritures de \\includegraphics nécessaires.
      5. Lister les images référencées mais introuvables sur le disque.
    """
    racine_reference = Path(racine_reference).resolve()
    dossier_images = Path(dossier_images).resolve()

    plan = Plan(racine_reference=racine_reference,
                dossier_images=dossier_images)

    images = _scanner_images_source(racine_reference)
    tex_files = _scanner_tex_source(racine_reference)
    index_tex = _index_inverse_tex(tex_files)
    # Index hash → nom dans le dossier cible (pour détecter les images
    # déjà migrées sous un autre nom).
    index_hashes_cible = _index_hashes_cible(dossier_images)

    # Map nom_cible → (Operation, hash) pour détecter les collisions.
    cibles: dict[str, tuple[Operation, str]] = {}

    for img in images:
        stem = img.stem

        # 0) Court-circuit idempotence : si une image avec exactement le
        #    même hash existe déjà dans le dossier cible (même sous un nom
        #    différent), c'est qu'elle a déjà été migrée. On marque
        #    skip_identique sans recalculer le nom cible.
        h = _hash_fichier(img)
        if h in index_hashes_cible:
            nom_deja_present = index_hashes_cible[h]
            op = Operation(
                source=img,
                nom_cible=nom_deja_present,
                type_op='skip_identique',
                hash_source=h,
                raison=f'Déjà migrée sous le nom {nom_deja_present}',
            )
            plan.operations.append(op)
            continue

        ext_source = img.suffix.lower()

        # 0bis) Idempotence pour les JPG : la conversion JPG→PNG change
        # le hash binaire (Pillow ré-encode). Pour détecter qu'une
        # conversion est déjà faite, on calcule le nom cible PNG attendu
        # et on regarde s'il existe déjà sur disque. v0.7.1 : raffinement
        # important pour le cas \dirPrefix/Images/X.jpg où après une 1ère
        # passe, les .tex pointent vers le nouveau nom et l'index_tex ne
        # liste plus l'image source comme étant utilisée.
        if ext_source in ('.jpg', '.jpeg'):
            # On va d'abord faire le calcul complet du nom cible (étapes
            # 1 et 2 ci-dessous) puis tester l'idempotence. Pour ne pas
            # dupliquer le code, on laisse le pipeline normal s'exécuter
            # et on intercepte au niveau du test « cible existe déjà ».
            pass

        # 1) Trouver le .tex utilisateur "principal".
        candidats = index_tex.get(stem, [])
        tex_principal: Path | None = None
        if candidats:
            voisins = [t for t in candidats if t.parent == img.parent]
            tex_principal = voisins[0] if voisins else candidats[0]
        else:
            for t in tex_files:
                if t.parent == img.parent and stem.startswith(t.stem):
                    tex_principal = t
                    break

        # 2) Calculer le nom cible.
        nom_cible = _calculer_nom_cible(img, tex_principal)

        # 3) Type d'opération (le hash et ext_source sont déjà calculés).
        type_op = 'conversion_jpg' if ext_source in ('.jpg', '.jpeg') else 'copie'

        op = Operation(
            source=img,
            nom_cible=nom_cible,
            type_op=type_op,
            hash_source=h,
        )

        # 4) Recenser les .tex utilisateurs et réécritures.
        nouveau_stem = Path(nom_cible).stem
        utilisateurs_uniques: list[Path] = []
        for tex in candidats:
            if tex not in utilisateurs_uniques:
                utilisateurs_uniques.append(tex)
        if not utilisateurs_uniques and tex_principal is not None:
            utilisateurs_uniques.append(tex_principal)
        op.tex_utilisateurs = utilisateurs_uniques

        # Image orpheline : présente sur disque mais aucun .tex ne la référence.
        # On évite de marquer comme orpheline les images dont la migration
        # est déjà aboutie (cible présente avec le bon hash) : elles seront
        # détectées comme skip_identique plus bas.
        cible_potentielle = dossier_images / nom_cible
        cible_existe_avec_meme_hash = False
        if cible_potentielle.is_file():
            try:
                cible_existe_avec_meme_hash = (
                    _hash_fichier(cible_potentielle) == h
                )
            except OSError:
                pass
        if not utilisateurs_uniques and not cible_existe_avec_meme_hash:
            plan.orphelines.append(img)

        for tex in utilisateurs_uniques:
            for ref in _extraire_inclusions_tex(tex):
                if _basename_sans_ext(ref) == stem:
                    op.reecritures_tex.append((tex, ref, nouveau_stem))

        # 5) Détection de collision sur le nom cible.
        if nom_cible in cibles:
            op_existante, hash_existant = cibles[nom_cible]
            if hash_existant == h:
                op.type_op = 'skip_identique'
                op.raison = (f'Identique à {op_existante.source.name} '
                             f'(hash {h[:8]})')
                plan.operations.append(op)
                continue
            # Conflit : on suffixe en _v2/_v3/...
            stem_cible = Path(nom_cible).stem
            ext_cible = '.png'
            idx = 2
            while f'{stem_cible}_v{idx}{ext_cible}' in cibles:
                idx += 1
            nom_cible_alt = f'{stem_cible}_v{idx}{ext_cible}'

            # Idempotence : le conflit a peut-être déjà été résolu lors d'une
            # passe précédente. On vérifie si _v2/_v3/... existe sur disque
            # avec le bon hash → on prend ce nom-là plutôt que d'incrémenter.
            for try_idx in range(2, idx + 5):
                candidat = dossier_images / f'{stem_cible}_v{try_idx}{ext_cible}'
                if candidat.is_file():
                    try:
                        if _hash_fichier(candidat) == h:
                            nom_cible_alt = candidat.name
                            break
                    except OSError:
                        continue

            op.nom_cible = nom_cible_alt
            op.type_op = 'conflit'
            op.raison = (f'Collision avec {op_existante.source} '
                         f'(hashes différents). Renommé en {nom_cible_alt}.')
            plan.conflits.append(
                f'{img} et {op_existante.source} → cible initiale '
                f'{nom_cible} (hash {h[:8]} vs {hash_existant[:8]}). '
                f'Second renommé en {nom_cible_alt}.'
            )
            nouveau_stem_alt = Path(nom_cible_alt).stem
            op.reecritures_tex = [
                (tex, ref, nouveau_stem_alt)
                for (tex, ref, _) in op.reecritures_tex
            ]
            # Si le _v2 cible existe déjà avec le bon hash et que le .tex
            # pointe déjà vers _v2 (donc plus de réécriture nécessaire), on
            # peut transformer ce conflit en skip silencieux.
            cible_alt_disque = dossier_images / nom_cible_alt
            if (cible_alt_disque.is_file()
                    and not op.reecritures_tex
                    and not utilisateurs_uniques):
                try:
                    if _hash_fichier(cible_alt_disque) == h:
                        op.type_op = 'skip_identique'
                        op.raison = (f'Conflit déjà résolu '
                                     f'(cible {nom_cible_alt} OK)')
                        # On ne le compte plus dans les conflits :
                        plan.conflits.pop()
                except OSError:
                    pass
            cibles[nom_cible_alt] = (op, h)
            plan.operations.append(op)
            continue

        # 6) Idempotence : si la cible existe déjà sur disque, soit avec
        #    le même hash (copie), soit en cas de conversion JPG (le hash
        #    diffère naturellement, on tolère), on skip.
        cible_disque = dossier_images / nom_cible
        if cible_disque.is_file() and nom_cible not in cibles:
            try:
                hash_cible = _hash_fichier(cible_disque)
                if hash_cible == h:
                    op.type_op = 'skip_identique'
                    op.raison = 'Déjà présent à la cible avec hash identique'
                    cibles[nom_cible] = (op, h)
                    plan.operations.append(op)
                    continue
                if op.type_op == 'conversion_jpg':
                    # Le PNG cible existe déjà — c'est le résultat d'une
                    # conversion antérieure. On skip pour l'idempotence.
                    op.type_op = 'skip_identique'
                    op.raison = ('PNG cible déjà présent (conversion JPG '
                                 'déjà effectuée)')
                    cibles[nom_cible] = (op, hash_cible)
                    plan.operations.append(op)
                    continue
            except OSError:
                pass

        # 6bis) v0.7.1 — Idempotence renforcée pour les images orphelines
        # après réécriture : quand une image a été migrée vers
        # <tex_principal>_<stem>.png lors d'une 1ère passe et que les .tex
        # ont été réécrits pour pointer vers ce nouveau nom, l'image
        # source n'a plus de tex utilisateur dans l'index inverse. Le
        # bloc 6 ci-dessus rate alors le cas (le nom_cible recalculé sans
        # utilisateur n'existe pas en cible). Solution : scanner le
        # dossier cible à la recherche d'un fichier dont le nom se termine
        # par _<stem_source>.png. Si trouvé, c'est probablement la même
        # image migrée précédemment.
        if not utilisateurs_uniques:
            suffixe_cherche = f'_{stem}.png'
            for nom_existant in index_hashes_cible.values():
                if nom_existant.endswith(suffixe_cherche):
                    op.type_op = 'skip_identique'
                    op.nom_cible = nom_existant
                    op.raison = (f'Probablement déjà migrée sous le nom '
                                 f'{nom_existant} (suffixe matche)')
                    plan.operations.append(op)
                    break
            else:
                cibles[nom_cible] = (op, h)
                plan.operations.append(op)
            continue

        cibles[nom_cible] = (op, h)
        plan.operations.append(op)

    # 6) Images référencées mais introuvables.
    stems_disponibles = {img.stem for img in images}
    for tex in tex_files:
        for ref in _extraire_inclusions_tex(tex):
            stem = _basename_sans_ext(ref)
            if stem in stems_disponibles:
                continue
            # Pas trouvée comme source ; vérifier si déjà migrée.
            if (dossier_images / f'{stem}.png').exists():
                continue
            plan.images_introuvables.append((tex, ref))

    return plan


# ── Application ──────────────────────────────────────────────────────────────

def appliquer(plan: Plan, dry_run: bool = True) -> dict:
    """
    Exécute le plan. Si dry_run=True, n'écrit rien mais simule.

    Retourne un dict-rapport (cf. docstring du module).
    """
    rapport = {
        'images_copiees': 0,
        'images_converties': 0,
        'images_skip': 0,
        'conflits': 0,
        'tex_modifies': 0,
        'reecritures': 0,
        'introuvables': len(plan.images_introuvables),
        'orphelines': len(plan.orphelines),
        'lignes_log': [],
    }
    log = rapport['lignes_log'].append

    if not dry_run:
        plan.dossier_images.mkdir(parents=True, exist_ok=True)

    # 1) Copie / conversion des images.
    for op in plan.operations:
        cible = plan.dossier_images / op.nom_cible

        if op.type_op == 'skip_identique':
            rapport['images_skip'] += 1
            log(f'[SKIP   ] {op.source.name} ({op.raison})')
            continue

        if op.type_op == 'conflit':
            rapport['conflits'] += 1
            log(f'[CONFLIT] {op.source} → {op.nom_cible} : {op.raison}')

        try:
            if op.type_op == 'conversion_jpg':
                rapport['images_converties'] += 1
                log(f'[CONV   ] {op.source.name} → {op.nom_cible}')
                if not dry_run:
                    _convertir_jpg_vers_png(op.source, cible)
            else:
                rapport['images_copiees'] += 1
                log(f'[COPIE  ] {op.source.name} → {op.nom_cible}')
                if not dry_run:
                    shutil.copy2(op.source, cible)
        except Exception as e:
            log(f'[ERREUR ] {op.source} : {type(e).__name__}: {e}')
            # On continue avec les autres images plutôt que d'avorter tout.

    # 2) Réécriture des .tex (groupés par chemin).
    par_tex: dict[Path, list[tuple[str, str]]] = {}
    for op in plan.operations:
        for (tex, ancien, nouveau) in op.reecritures_tex:
            par_tex.setdefault(tex, []).append((ancien, nouveau))

    for tex, paires in par_tex.items():
        try:
            contenu = tex.read_text(encoding='utf-8')
        except OSError as e:
            log(f'[ERREUR ] Lecture {tex} : {e}')
            continue
        contenu_original = contenu

        n_changements = 0
        for ancien, nouveau in paires:
            if ancien == nouveau:
                continue
            ancien_esc = re.escape(ancien)

            def _rempl(m: re.Match, _nouveau=nouveau) -> str:
                opts = m.group('opts') or ''
                return f'\\includegraphics{opts}{{{_nouveau}}}'

            pat = re.compile(
                r'\\includegraphics(?P<opts>\[[^\]]*\])?\{'
                + ancien_esc + r'\}'
            )
            contenu, n = pat.subn(_rempl, contenu)
            n_changements += n

        if n_changements > 0 and contenu != contenu_original:
            rapport['tex_modifies'] += 1
            rapport['reecritures'] += n_changements
            log(f'[TEX    ] {tex} : {n_changements} \\includegraphics réécrits')
            if not dry_run:
                tex.write_text(contenu, encoding='utf-8')

    # 3) Images introuvables.
    if plan.images_introuvables:
        log('')
        log('Images référencées dans des .tex mais introuvables :')
        for tex, ref in plan.images_introuvables[:50]:
            log(f'  - {tex} → \\includegraphics{{{ref}}}')
        if len(plan.images_introuvables) > 50:
            log(f'  … et {len(plan.images_introuvables) - 50} autres.')

    # 4) Images orphelines (sur disque, aucun .tex ne les référence).
    if plan.orphelines:
        log('')
        log('Images orphelines (présentes mais référencées par aucun .tex) :')
        for img in plan.orphelines[:50]:
            log(f'  - {img}')
        if len(plan.orphelines) > 50:
            log(f'  … et {len(plan.orphelines) - 50} autres.')

    return rapport


def _convertir_jpg_vers_png(source: Path, cible: Path) -> None:
    """Convertit un JPEG en PNG via Pillow.

    Si Pillow n'est pas disponible, fallback en copie brute (le fichier
    reste binairement un JPEG mais portera l'extension .png — le rapport
    le mentionne).
    """
    if not _pillow_disponible():
        shutil.copy2(source, cible)
        return
    from PIL import Image
    with Image.open(source) as img:
        if img.mode == 'CMYK':
            img = img.convert('RGB')
        img.save(cible, 'PNG', optimize=True)


# ── Formatage humain ─────────────────────────────────────────────────────────

def formatter_rapport(plan: Plan, rapport: dict, dry_run: bool) -> str:
    """Formatte le rapport en texte lisible (CLI ou réponse JSON.log)."""
    titre = '=== Migration images — '
    titre += '(SIMULATION dry-run)' if dry_run else '(EXÉCUTION)'
    titre += ' ==='

    lignes = [
        titre,
        f'Source : {plan.racine_reference}',
        f'Cible  : {plan.dossier_images}',
        '',
        f'Images copiées      : {rapport["images_copiees"]}',
        f'Images converties   : {rapport["images_converties"]}',
        f'Images sautées      : {rapport["images_skip"]} (doublons identiques)',
        f'Conflits résolus    : {rapport["conflits"]} (suffixés _v2, _v3, …)',
        f'Fichiers .tex modifiés      : {rapport["tex_modifies"]}',
        f'\\includegraphics réécrits   : {rapport["reecritures"]}',
        f'Images introuvables : {rapport["introuvables"]}',
        f'Images orphelines   : {rapport["orphelines"]} '
        f'(à arbitrer manuellement)',
        '',
    ]
    if plan.conflits:
        lignes.append('Liste des conflits à arbitrer :')
        for c in plan.conflits:
            lignes.append(f'  - {c}')
        lignes.append('')
    lignes.append('--- Détail par fichier ---')
    lignes.extend(rapport['lignes_log'])
    return '\n'.join(lignes)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Migration des images vers appli/data/images/'
    )
    parser.add_argument('--reference', required=True, type=Path,
                        help='Racine de reference/sequences/')
    parser.add_argument('--images', required=True, type=Path,
                        help='Dossier cible (typiquement appli/data/images/)')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true',
                      help='Simulation sans rien écrire')
    mode.add_argument('--apply', action='store_true',
                      help='Exécute réellement la migration')

    args = parser.parse_args(argv)

    plan = analyser(args.reference, args.images)
    rapport = appliquer(plan, dry_run=args.dry_run)
    print(formatter_rapport(plan, rapport, dry_run=args.dry_run))

    if rapport['conflits'] > 0:
        return 1
    if rapport['introuvables'] > 0:
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
