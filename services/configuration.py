r"""
services/configuration.py — Configuration utilisateur de l'appli.

Mécanisme simple pour stocker les paramètres qui ne tiennent pas dans la
BDD métier (chemins système, préférences globales). Le fichier est
data/configuration.json, créé à la volée si absent.

Conçu pour être minimal : aucune dépendance, structure JSON plate, lecture
et écriture atomiques.

Exemples de clés :
  - chemin_racine_seqenseigne : v0.9 — racine commune (D:\\... ou E:\\...)
                             sous laquelle vivent toutes les ressources.
                             Sert d'ancrage à tous les autres chemins.
  - chemin_sources_livrets : Path du dossier racine des .tex sources
                             (pour rendu atomique : localisation des
                             NXX_SYY_params.tex, TEXINPUTS).
                             v0.9 : dérivé de `<racine>/sequences` si vide.
  - chemin_pdflatex       : override du pdflatex détecté automatiquement.
                             v0.9 : dérivé de `<racine>/outils/MikTex/...`
                             si vide.
  - chemin_paquet         : v0.9 — pré-remplissage Admin > Import mise en
                             forme. Dérivé de `<racine>/reference/paquet`.
  - chemin_reference_sequences : v0.9 — pré-remplissage Admin > Import
                             référence et Admin > Images. Dérivé de
                             `<racine>/reference/sequences`.
  - timeout_compilation_court_s : v0.10 — timeout pdflatex en secondes
                            pour les compilations courtes (atome isolé,
                            batch). Remplace l'ancienne clé
                            `timeout_compilation_s` qui reste lue en
                            fallback pour la compat ascendante.
  - timeout_compilation_long_s : v0.10 — timeout pdflatex en secondes
                            pour les compilations longues (documents
                            agrégés : récap cours, récap exos, plan de
                            travail). Défaut 300s.
  - compilation_batch_max_erreurs_consecutives : v0.8 — nombre maximum
                            d'erreurs d'infrastructure consécutives
                            (pdflatex introuvable, timeout, exception
                            Python) avant abandon global du batch.
                            Les échecs LaTeX classiques ne comptent pas.
"""

from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path


NOM_FICHIER_CONFIG = 'configuration.json'

# v0.9 — Sous-chemins relatifs à `chemin_racine_seqenseigne` utilisés pour
# construire les valeurs *dérivées* des chemins applicatifs. Centralisés
# ici (et pas éparpillés dans les helpers) pour que le déménagement vers
# une autre arborescence soit un changement à un seul endroit.
#
# La convention est : si l'utilisateur ne définit pas explicitement un
# chemin (chemin_*), il est calculé comme `<racine> / <sous_chemin>`.
# Si la racine n'est pas définie non plus, la valeur effective est vide
# (= pas configuré, comportement v0.8.x conservé).
SOUS_CHEMINS_RELATIFS = {
    'chemin_sources_livrets':       'sequences',
    'chemin_pdflatex':              'outils/MikTex/texmfs/install/miktex/bin/x64/pdflatex.exe',
    'chemin_paquet':                'reference/paquet',
    'chemin_reference_sequences':   'reference/sequences',
}

# Clés connues avec leur valeur par défaut
CLES_DEFAUT = {
    # v0.9 — Racine commune sous laquelle vivent toutes les ressources
    # seqenseigne (sources livrets, paquet .sty, MiKTeX portable, etc.).
    # Quand renseignée, sert de point d'ancrage à tous les chemins
    # applicatifs qui ne sont pas explicitement overridés. Cas d'usage
    # concret : passer du PC maison (D:\Enseignement\seqenseigne) au PC
    # du travail (E:\Enseignement\seqenseigne) en changeant un seul
    # champ au lieu de 4.
    'chemin_racine_seqenseigne': '',
    'chemin_sources_livrets': '',     # vide = dérivé de la racine si possible
    'chemin_pdflatex':        '',     # vide = dérivé de la racine puis détection auto
    # v0.9 — Pré-remplissage des champs Admin (Import paquet, Import
    # référence/Images). Ces clés ne sont *pas* utilisées en compilation,
    # uniquement pour suggérer une valeur dans l'UI Admin.
    'chemin_paquet':                '',
    'chemin_reference_sequences':   '',
    'timeout_compilation_s':  30,     # déprécié v0.10 — conservé pour
                                      # compat ascendante : lu en fallback
                                      # de timeout_compilation_court_s.
    # v0.10 — Dichotomie de timeouts : compiler un atome isolé prend
    # quelques secondes, mais un récap cours de tout un niveau peut
    # facilement excéder une minute (~120 atomes, beaucoup de TikZ).
    # On distingue donc :
    #   - court : atomes individuels (route /api/render/atome) et batch
    #             (qui compile en boucle des atomes individuels).
    #   - long  : documents agrégés (récap cours aujourd'hui ; récap exos,
    #             plan de travail, etc. plus tard).
    # Migration douce : si timeout_compilation_court_s est absent, la
    # méthode Configuration.timeout_compilation_court() lit l'ancienne
    # clé timeout_compilation_s. Idem si l'utilisateur n'a jamais ouvert
    # l'UI Admin depuis la mise à jour.
    'timeout_compilation_court_s': 30,
    'timeout_compilation_long_s':  300,
    # v0.8 — Compilateur batch : limite d'erreurs d'infra consécutives.
    'compilation_batch_max_erreurs_consecutives': 5,
    # v0.8.5 — Bibliothèques tikz à charger inconditionnellement dans le
    # préambule de chaque atome compilé. Liste séparée par des virgules,
    # chaque entrée correspond à un argument valide de \usetikzlibrary.
    #
    # Pourquoi paramétrable : seqenseigne.sty charge plein de bibliothèques
    # tikz quand il est utilisé en entier. Notre préambule reconstruit n'en
    # charge que ce qui est nécessaire pour les macros détectées dans
    # l'atome — sauf que certaines bibliothèques sont utilisées via des
    # styles tikz (`\node[decision]` → shape diamond → shapes.geometric)
    # ou via des clés (`>=Latex` → arrows.meta), ce qu'on ne sait pas
    # détecter par analyse de macros. Cette liste sert de filet de sécurité.
    #
    # Défaut : couvre les usages courants en pédagogie collège.
    #   - babel             : neutralise les shorthands de babel-french
    #                         pendant les tikzpicture (sinon erreur
    #                         « + or - expected » sur tkz-euclide).
    #   - shapes.geometric  : formes diamond, ellipse, regular polygon...
    #   - arrows.meta       : flèches modernes (Latex, Stealth, etc.)
    #   - positioning       : `right=of A`, `below=2cm of B`, etc.
    #   - calc              : coordonnées calculées `($(A)+(1,0)$)`
    'tikz_libraries': 'babel,shapes.geometric,arrows.meta,positioning,calc',
    # v0.9.1 — Bibliothèques tabularray à charger systématiquement.
    # Même mécanisme que tikz_libraries : émet un `\UseTblrLibrary{lib}`
    # par entrée juste après `\usepackage{tabularray}`.
    #
    # Pourquoi paramétrable : depuis tabularray v2025A (CTAN 2025-03-11),
    # certaines clés autrefois centrales ont migré vers des bibliothèques :
    #   - `measure=vbox/vstore` → bibliothèque `varwidth`
    #   - `\toprule/\midrule/\bottomrule` → bibliothèque `booktabs` (déjà
    #     historiquement requise)
    # En contexte livret complet, seqenseigne.sty charge ces libs ; en
    # compilation isolée, on doit les reproduire ici.
    #
    # Défaut : couvre les usages courants observés sur le corpus.
    #   - booktabs : règles \toprule, \midrule, \bottomrule.
    #   - varwidth : clé `measure=vbox` utilisée notamment dans les
    #                tableaux à 2 colonnes XX[2,c] des séquences de
    #                géométrie (N11/S11, N12/S11). Détecté sur N11/S11/M05.
    'tblr_libraries': 'booktabs,varwidth',
    # v0.9.3 — Hauteur des textareas LaTeX dans les ateliers, en lignes.
    # Remplace l'autosize (v0.6.4) qui faisait grandir les textareas avec
    # le contenu et créait une hauteur imprévisible quand un atome avait
    # beaucoup de variables. Hauteur fixe + scroll est plus prévisible
    # et permet de saisir confortablement du LaTeX en volume sans que
    # l'écran défile à chaque saut de ligne.
    #
    # Défaut 25 lignes (~ 350 px en monospace 12px) : couvre la majorité
    # des atomes sans scroll. Paramétrable via Préférences car la bonne
    # hauteur dépend de la résolution écran (PC fixe vs portable).
    'atl_textarea_lignes': 25,
    # v0.10.1 — Critères pré-remplis pour l'objectif "Connaître les notions
    # et les méthodes" créé via le bouton "+ Activer l'objectif Connaître"
    # de l'atelier d'assemblage. Modifiables dans
    # Préférences > Atelier d'assemblage de séquence.
    #
    # Convention F/A/E :
    #   F = Fondamental    → niveau de maîtrise "À consolider"
    #   A = Avancé         → niveau de maîtrise "Satisfaisant"
    #   E = Exploration    → niveau de maîtrise "Très bon"
    'atelier_assemblage_criteres_connaitre': {
        'nom':       'Connaître les notions et les méthodes',
        'critere_F': 'A noté la trace écrite en classe.',
        'critere_A': 'A complété les fiches de résumé.',
        'critere_E': "Sait résumer le cours à l'oral.",
    },
}


class Configuration:
    """Accès en lecture/écriture au fichier de configuration de l'appli."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.fichier = self.data_dir / NOM_FICHIER_CONFIG

    # ── Lecture ──────────────────────────────────────────────────────────

    def charger(self) -> dict:
        """Retourne le dict de configuration courante, avec défauts appliqués."""
        if not self.fichier.is_file():
            return dict(CLES_DEFAUT)
        try:
            contenu = self.fichier.read_text(encoding='utf-8')
            data = json.loads(contenu)
            if not isinstance(data, dict):
                return dict(CLES_DEFAUT)
        except (json.JSONDecodeError, OSError):
            return dict(CLES_DEFAUT)

        # Fusion : défauts complétés par les clés trouvées
        result = dict(CLES_DEFAUT)
        for k, v in data.items():
            if k in CLES_DEFAUT:
                result[k] = v
        return result

    def get(self, cle: str, defaut=None):
        """Lit une clé. defaut est retourné uniquement si la clé est inconnue
        de CLES_DEFAUT (clé non enregistrée)."""
        config = self.charger()
        if cle in config:
            return config[cle]
        return defaut

    # ── Écriture ─────────────────────────────────────────────────────────

    def enregistrer(self, updates: dict) -> dict:
        """Applique une mise à jour partielle. Seules les clés connues de
        CLES_DEFAUT sont retenues (évite les pollutions). Retourne la
        config après mise à jour."""
        current = self.charger()
        for k, v in updates.items():
            if k in CLES_DEFAUT:
                current[k] = v
        self._ecrire_atomique(current)
        return current

    def _ecrire_atomique(self, data: dict) -> None:
        """Écriture atomique via un fichier temporaire + rename."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        texte = json.dumps(data, indent=2, ensure_ascii=False)
        # Écrire dans le même dossier pour que rename soit atomique
        fd, tmp_path = tempfile.mkstemp(
            prefix='.cfg_', suffix='.json', dir=self.data_dir,
        )
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(texte)
            os.replace(tmp_path, self.fichier)
        except Exception:
            # Nettoyage si échec
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # ── Helpers typés ────────────────────────────────────────────────────

    # v0.9 — Résolution générique d'un chemin avec dérivation depuis la
    # racine commune. Logique en deux temps :
    #   1. Si la valeur explicite (chemin_*) est non vide, on l'utilise
    #      telle quelle (= override par champ, demandé par Laurent).
    #   2. Sinon, si la racine est définie ET qu'on connaît un sous-chemin
    #      relatif pour cette clé, on dérive `<racine> / <sous_chemin>`.
    #   3. Sinon on renvoie la chaîne vide (= pas configuré).
    #
    # Centralisé dans une méthode interne pour garantir que tous les
    # accesseurs (sources, pdflatex, paquet, ref) appliquent exactement
    # la même règle, et que les tests d'un seul peuvent valider la logique.
    def _resoudre_chemin(self, cle: str) -> str:
        """Retourne la valeur effective d'un chemin, override ou dérivée.

        Renvoie une chaîne (jamais None) ; vide si rien n'est résolvable.

        Le résultat préserve le séparateur fourni par l'utilisateur dans
        la racine : racine `/home/x/seq` → dérivés en slash forward,
        racine `D:\\seq` → dérivés en backslash. Cette règle évite que
        Path() (qui réécrit en séparateur natif sous Windows) ne mutile
        une racine POSIX en `\\home\\x\\seq\\...`, illisible côté UI et
        non-substring de la racine d'origine.

        La validation d'existence (is_dir/is_file) est faite par les
        helpers spécialisés qui retournent Path | None.
        """
        config = self.charger()
        # 1. Override explicite
        valeur = (config.get(cle) or '').strip()
        if valeur:
            return valeur
        # 2. Dérivation depuis la racine
        racine = (config.get('chemin_racine_seqenseigne') or '').strip()
        sous_chemin = SOUS_CHEMINS_RELATIFS.get(cle)
        if racine and sous_chemin:
            # Détection du séparateur dominant dans la racine. On considère
            # qu'une racine est "Windows" dès qu'elle contient au moins un
            # backslash (ce qui couvre `D:\seq`, `D:\seq\sous` et même les
            # chemins UNC `\\serveur\partage`). Sinon on reste en POSIX.
            sep = '\\' if '\\' in racine else '/'
            # Le sous_chemin est codé en POSIX dans SOUS_CHEMINS_RELATIFS ;
            # on le retraduit dans le séparateur retenu pour produire un
            # chemin homogène. On strip aussi le séparateur final éventuel
            # de la racine pour éviter les doubles séparateurs.
            sous = sous_chemin.replace('/', sep)
            racine_stripped = racine.rstrip('/\\')
            return racine_stripped + sep + sous
        # 3. Rien
        return ''

    def chemin_racine_seqenseigne(self) -> Path | None:
        """v0.9 — Racine commune (D:\\... ou E:\\...). None si non définie
        ou inexistante sur le disque."""
        val = (self.get('chemin_racine_seqenseigne', '') or '').strip()
        if not val:
            return None
        p = Path(val)
        return p if p.is_dir() else None

    def chemin_sources_livrets(self) -> Path | None:
        """Retourne le chemin des sources livrets, ou None si non configuré.

        v0.9 : dérivé de `chemin_racine_seqenseigne / sequences` si l'override
        explicite n'est pas défini.
        """
        val = self._resoudre_chemin('chemin_sources_livrets')
        if not val:
            return None
        p = Path(val)
        return p if p.is_dir() else None

    def chemin_pdflatex(self) -> str | None:
        """Override explicite du pdflatex. None = détection auto.

        v0.9 : dérivé de `chemin_racine_seqenseigne / outils/MikTex/...` si
        l'override explicite n'est pas défini. Le fichier est testé pour
        existence (cas typique : chemin Windows depuis racine USB qui n'est
        pas branchée → on retourne None et la détection auto prend le relais).
        """
        val = self._resoudre_chemin('chemin_pdflatex')
        if not val:
            return None
        # Pour pdflatex on veut un fichier, pas un dossier ; et on ne
        # bloque pas si is_file() est False parce que ça pourrait être
        # un binaire dans le PATH (le compilateur sait gérer les deux
        # cas). On retourne donc la chaîne brute si elle est non vide.
        return val

    def chemin_paquet(self) -> str:
        """v0.9 — Chemin du dossier paquet seqenseigne (.sty), pour
        pré-remplir l'UI Admin > Import mise en forme. Chaîne vide si
        non résolvable. Pas de validation existence : c'est un champ
        de pré-remplissage, l'utilisateur peut le surcharger."""
        return self._resoudre_chemin('chemin_paquet')

    def chemin_reference_sequences(self) -> str:
        """v0.9 — Chemin de l'arborescence de référence, pour pré-remplir
        l'UI Admin > Import référence et Admin > Images. Chaîne vide si
        non résolvable."""
        return self._resoudre_chemin('chemin_reference_sequences')

    def timeout_compilation_court(self) -> int:
        """v0.10 — Timeout en secondes pour compilations courtes (atome
        isolé, batch). Défaut 30. Lit la clé `timeout_compilation_court_s`
        avec fallback sur l'ancienne clé `timeout_compilation_s` pour les
        configurations existantes qui n'ont pas encore été migrées.

        Implémentation : on lit le fichier brut sur disque pour distinguer
        "clé explicitement enregistrée" de "valeur par défaut". `self.get()`
        ne le permet pas car il fusionne avec CLES_DEFAUT — donc dès que
        `timeout_compilation_court_s` est dans les defaults, le fallback
        ne se déclencherait jamais.
        """
        brut = self._lire_brut()
        if 'timeout_compilation_court_s' in brut:
            val = brut['timeout_compilation_court_s']
        elif 'timeout_compilation_s' in brut:
            # Migration : ancienne clé écrite par une version antérieure.
            val = brut['timeout_compilation_s']
        else:
            val = 30
        try:
            return max(1, int(val))
        except (TypeError, ValueError):
            return 30

    def _lire_brut(self) -> dict:
        """Lit le fichier de config brut, sans fusion avec les defaults.
        Retourne {} si le fichier est absent ou invalide. Usage interne."""
        if not self.fichier.is_file():
            return {}
        try:
            contenu = self.fichier.read_text(encoding='utf-8')
            data = json.loads(contenu)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def timeout_compilation_long(self) -> int:
        """v0.10 — Timeout en secondes pour compilations longues
        (documents agrégés : récap cours, récap exos, plan de travail).
        Défaut 300."""
        val = self.get('timeout_compilation_long_s', 300)
        try:
            return max(1, int(val))
        except (TypeError, ValueError):
            return 300

    def timeout_compilation(self) -> int:
        """Alias de timeout_compilation_court(), conservé pour compat
        ascendante avec les rares appelants qui auraient ce nom en dur.
        Préférer timeout_compilation_court() dans le code nouveau."""
        return self.timeout_compilation_court()

    def compilation_batch_max_erreurs_consecutives(self) -> int:
        """v0.8 — Nombre max d'erreurs infra consécutives avant abandon (défaut 5)."""
        val = self.get('compilation_batch_max_erreurs_consecutives', 5)
        try:
            return max(1, int(val))
        except (TypeError, ValueError):
            return 5

    def tikz_libraries(self) -> list[str]:
        """v0.8.5 — Liste des bibliothèques tikz à charger systématiquement.

        La valeur stockée est une chaîne séparée par des virgules. Cet
        accesseur la parse en liste, en éliminant les entrées vides et
        les espaces parasites. Garanti déterministe (pas de set →
        l'ordre des `\\usetikzlibrary` est l'ordre saisi par
        l'utilisateur).
        """
        val = self.get('tikz_libraries', '')
        if not isinstance(val, str):
            return []
        # Sépare sur la virgule, trim chaque entrée, élimine les vides
        # et déduplique en conservant l'ordre de la première occurrence.
        seen: set[str] = set()
        out: list[str] = []
        for entree in val.split(','):
            lib = entree.strip()
            if lib and lib not in seen:
                seen.add(lib)
                out.append(lib)
        return out

    def tblr_libraries(self) -> list[str]:
        """v0.9.1 — Liste des bibliothèques tabularray à charger systématiquement.

        Pendant frontal exact de tikz_libraries() : même format CSV en
        config, même parsing (trim + dédup + ordre préservé), même usage
        (filet de sécurité pour les libs qui ne se détectent pas par
        analyse de macros).

        Cas d'usage qui a motivé l'ajout : depuis tabularray v2025A, la
        clé `measure=vbox` requiert `\\UseTblrLibrary{varwidth}`, sinon
        erreur « Unknown inner key name 'measure' ». Détecté sur
        N11/S11/Méthode 05.
        """
        val = self.get('tblr_libraries', '')
        if not isinstance(val, str):
            return []
        seen: set[str] = set()
        out: list[str] = []
        for entree in val.split(','):
            lib = entree.strip()
            if lib and lib not in seen:
                seen.add(lib)
                out.append(lib)
        return out

    def atl_textarea_lignes(self) -> int:
        """v0.9.3 — Nombre de lignes affichées par les textareas LaTeX
        dans les ateliers (variables, énoncé, corrigé, corps notion/méthode,
        items de section).

        Le textarea garde cette hauteur quel que soit le contenu ; le
        défilement interne prend le relais quand le contenu déborde.
        Plancher défensif à 5 lignes pour éviter des textareas
        inutilisables si la config est mal saisie.
        """
        val = self.get('atl_textarea_lignes', 25)
        try:
            n = int(val)
        except (TypeError, ValueError):
            return 25
        return max(5, n)

    def atelier_assemblage_criteres_connaitre(self) -> dict:
        """v0.10.1 — Valeurs pré-remplies des critères F/A/E de l'objectif
        "Connaître les notions et les méthodes" lors de son activation depuis
        l'atelier d'assemblage. Le frontend appelle l'API /configuration et
        applique ces valeurs au moment du clic sur "+ Activer Connaître".

        Retourne toujours un dict avec 4 clés (nom, critere_F/A/E),
        complété par les défauts si la config est partielle ou absente.
        """
        defauts = {
            'nom':       'Connaître les notions et les méthodes',
            'critere_F': 'A noté la trace écrite en classe.',
            'critere_A': 'A complété les fiches de résumé.',
            'critere_E': "Sait résumer le cours à l'oral.",
        }
        val = self.get('atelier_assemblage_criteres_connaitre', None)
        if not isinstance(val, dict):
            return defauts
        out = dict(defauts)
        for k in ('nom', 'critere_F', 'critere_A', 'critere_E'):
            v = val.get(k)
            if isinstance(v, str) and v.strip():
                out[k] = v
        return out
