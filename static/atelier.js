/**
 * static/atelier.js — v0.15
 *
 * Classe de base pour TOUS les ateliers de seqenseigne.
 *
 * Hiérarchie OO (état réel au 21 mai 2026) :
 *
 *   Atelier  (cette classe)
 *   └── AtelierEditeur  (modifications persistantes : modifie/enregistré
 *       │                + rendu PDF unifié depuis v0.14.4)
 *       ├── AtelierExercice    (atome, formulaire)
 *       ├── AtelierNotion      (atome, formulaire)
 *       ├── AtelierMethode     (atome, formulaire)
 *       ├── AtelierFiche       (atome, formulaire)
 *       ├── AtelierCarte       (atome, formulaire)
 *       └── AtelierAssemblage  (parent des ateliers de composition)
 *           ├── AtelierEvaluation   (v0.15, portée Niveau)
 *           ├── AtelierLivret       (à venir v0.15.1, portée Séquence)
 *           └── AtelierProgression  (à venir v0.17+, portée Niveau)
 *
 * Historique :
 *   - v0.13.6.6 : pose initiale d'Atelier et AtelierEditeur. Migration
 *     pilote de Carte et Exercice (via une classe intermédiaire
 *     AtelierAtomique qui sera supprimée plus tard).
 *   - v0.13.6.6 → v0.13.6.17 : migration progressive des 5 atomes
 *     (Notion, Méthode, Exercice, Fiche, Carte) en sous-classes
 *     d'AtelierAtomique.
 *   - v0.14.4 : suppression d'AtelierAtomique. Sa machinerie de rendu
 *     PDF (devenue commune aux 5 atomes après les unifications
 *     v0.14.1–v0.14.3) est remontée dans AtelierEditeur. Les 5 atomes
 *     héritent désormais directement d'AtelierEditeur.
 *   - v0.15 : création de la classe AtelierAssemblage et migration
 *     d'AtelierEvaluation. Les ateliers historiques non OO restants
 *     (Livret seqniv, Progression) seront migrés en v0.15.1 et v0.17+.
 *
 * Objectif structurel : remplacer le dispatch par chaîne de caractères
 * dans `atelier_atome_generique.js` (`type='exercice'|'notion'|...`)
 * par une vraie hiérarchie OO. Chaque atelier devient une instance
 * d'une sous-classe ; les méthodes communes vivent dans la classe
 * parente.
 *
 * Cette classe (Atelier) contient les utilitaires partagés par TOUS,
 * sans hypothèse sur la présence d'une sidebar, d'un item actif, ou
 * d'un formulaire.
 */

class Atelier {
  /**
   * @param {Object} config
   * @param {string} config.id           — identifiant unique de l'atelier
   *                                         (ex: 'carte', 'exercice')
   * @param {string} config.prefixe      — préfixe DOM pour ses sous-éléments
   *                                         (ex: 'atl-carte', 'atl-exercice')
   * @param {string} [config.titreToolbar] — titre par défaut de la toolbar
   *                                          quand aucun item n'est ouvert
   */
  constructor(config) {
    if (!config || !config.id || !config.prefixe) {
      throw new Error('Atelier : config.id et config.prefixe sont requis');
    }
    this.config = config;
    this.id = config.id;
    this.prefixe = config.prefixe;
  }

  // ── Cycle de vie ──────────────────────────────────────────────────────────

  /**
   * À appeler une fois au démarrage de l'appli pour brancher les
   * événements. Hook ; ne fait rien par défaut. Surchargé par les
   * sous-classes qui ont besoin d'écouter des événements globaux
   * (filtres niveau/séquence, etc.).
   */
  init() {
    // Hook vide
  }

  /**
   * À appeler quand l'utilisateur entre dans cet atelier (via le menu
   * principal ou via un lien). Affiche le panneau racine de l'atelier
   * et déclenche le chargement initial. Hook ; les sous-classes peuvent
   * surcharger pour charger des données.
   */
  async ouvrir() {
    // Hook vide
  }

  /**
   * À appeler quand l'utilisateur quitte cet atelier. Hook pour
   * cleanup, save pending, etc.
   */
  fermer() {
    // Hook vide
  }

  // ── Filtres niveau / séquence (transverse à tous les ateliers) ────────────

  /** Niveau filtré actuellement (lit window.ATL_FILTRE_NIVEAU). */
  get niveauFiltre() {
    return window.ATL_FILTRE_NIVEAU || '';
  }

  /** Séquence filtrée actuellement (lit window.ATL_FILTRE_SEQ). */
  get sequenceFiltre() {
    return window.ATL_FILTRE_SEQ || '';
  }

  // ── Helpers DOM ───────────────────────────────────────────────────────────

  /**
   * Raccourci document.getElementById(this.prefixe + '-' + suffixe).
   *
   * Exemple : pour un atelier de préfixe 'atl-carte', this.$('list')
   * retourne l'élément #atl-carte-list. Centralise la convention de
   * nommage qu'on retrouve partout dans le code.
   */
  $(suffixe) {
    return document.getElementById(this.prefixe + '-' + suffixe);
  }

  /** Définit le display d'un sous-élément. */
  setDisplay(suffixe, value) {
    const el = this.$(suffixe);
    if (el) el.style.display = value;
  }

  /**
   * Affiche un toast notification à l'utilisateur. Niveau 'info' par
   * défaut, 'erreur' pour les messages d'erreur. Délègue à la fonction
   * globale showToast() si elle existe, sinon utilise console.
   */
  toast(message, niveau = 'info') {
    if (typeof window.showToast === 'function') {
      window.showToast(message, niveau === 'erreur');
    } else if (niveau === 'erreur') {
      console.error('[' + this.id + ']', message);
    } else {
      console.log('[' + this.id + ']', message);
    }
  }

  // ── Échappement HTML (méthodes statiques) ─────────────────────────────────

  /** Échappement HTML basique : transforme <, >, &, " en entités. */
  static escHtml(s) {
    const div = document.createElement('div');
    div.textContent = String(s == null ? '' : s);
    return div.innerHTML;
  }

  /** Échappement pour attribut HTML : escape les quotes en plus. */
  static escAttr(s) {
    return Atelier.escHtml(s).replace(/"/g, '&quot;');
  }

  // ── Persistance localStorage des préférences UI ───────────────────────────
  //
  // Préfixée par this.id pour ne pas collisionner entre ateliers.
  //
  // Exemples d'usage :
  //   this.lirePref('bucket-F-replie', false)
  //   this.ecrirePref('niveau-actif', 'N10')

  lirePref(cle, defaut = null) {
    try {
      const v = window.localStorage.getItem('atl.' + this.id + '.' + cle);
      if (v === null) return defaut;
      return JSON.parse(v);
    } catch (_e) {
      return defaut;
    }
  }

  ecrirePref(cle, valeur) {
    try {
      window.localStorage.setItem(
        'atl.' + this.id + '.' + cle,
        JSON.stringify(valeur),
      );
    } catch (_e) {
      // localStorage plein, désactivé, etc. — on ignore
    }
  }

  // ── Helper de rendu d'item (anciennement atelAsmItemHtml mal nommé) ───────

  /**
   * Rend le HTML d'un item de liste pour les sidebars d'ateliers.
   *
   * Méthode statique car elle peut être appelée hors contexte d'une
   * instance d'atelier (par exemple depuis un atelier d'assemblage qui
   * rend un objectif lié à un exo appartenant à un atelier différent).
   *
   * Le nom historique `atelAsmItemHtml` (asm = assemblage) était un
   * abus : ce helper est en réalité utilisé par tous les types
   * d'ateliers. Renommé en `rendreItemHtml`. Les classes CSS .asm-item
   * sont conservées pour la rétrocompat des styles.
   *
   * @param {Object} parts
   * @param {boolean} parts.actif       — si true, ajoute la classe `active`
   * @param {string} [parts.onclick]    — JS exécuté au clic (ex: "ATELIER_CARTE.ouvrirItem('id')")
   * @param {string} [parts.oncontextmenu] — JS exécuté au click droit (v0.13.6.8)
   * @param {boolean} [parts.selected]  — si true, ajoute la classe `selected` (v0.13.6.8)
   * @param {string} [parts.dataId]     — attribut data-item-id, utile pour
   *                                       trouver l'item dans la sidebar (v0.13.6.8)
   * @param {string} [parts.badge]      — HTML d'un badge à gauche
   * @param {string} [parts.id]         — identifiant compact (ex: "N11/S04/F01")
   * @param {string|Object} parts.titre — string OU {html, derive: bool} (italique si derive)
   * @param {string[]} [parts.placedTags] — tags affichés à droite avant la pastille
   * @param {string} [parts.etatCode]   — "valide" | "en_cours" (pastille ronde)
   * @param {string} [parts.titleAttr]  — tooltip natif (sinon dérivé du titre)
   * @returns {string} HTML d'un item de sidebar
   */
  static rendreItemHtml(parts) {
    const classes = ['asm-item', 'asm-item--clickable'];
    if (parts.actif)    classes.push('active');
    if (parts.selected) classes.push('asm-item--selected');
    const cls = classes.join(' ');
    const onclick = parts.onclick || '';
    const oncontextmenu = parts.oncontextmenu
      ? ` oncontextmenu="${Atelier.escAttr(parts.oncontextmenu)}"`
      : '';
    const dataIdAttr = parts.dataId
      ? ` data-item-id="${Atelier.escAttr(parts.dataId)}"`
      : '';
    const badge = parts.badge || '';
    const id = parts.id
      ? `<span class="atl-item-id">${Atelier.escHtml(parts.id)}</span>`
      : '';

    let libHtml;
    let titleAttr = parts.titleAttr || '';
    if (parts.titre && typeof parts.titre === 'object') {
      const cls2 = 'asm-item-lib' +
        (parts.titre.derive ? ' atl-item-titre--derive' : '');
      libHtml = `<span class="${cls2}">${parts.titre.html || ''}</span>`;
      if (!titleAttr && parts.titre.html) {
        titleAttr = parts.titre.html.replace(/<[^>]+>/g, '');
      }
    } else {
      const t = parts.titre || '';
      libHtml = `<span class="asm-item-lib">${Atelier.escHtml(t)}</span>`;
      if (!titleAttr) titleAttr = t;
    }

    const tags = parts.placedTags || [];
    const tagsHtml = tags.length === 0 ? '' :
      `<span class="asm-item-placed-tag">${tags.map(Atelier.escHtml).join(' ')}</span>`;

    const etat = parts.etatCode === 'valide' ? 'valide' : 'en_cours';
    const tipEtat = etat === 'valide' ? 'Validé' : 'En cours';
    const pastille =
      `<span class="asm-item-etat-badge atome-etat--${etat}" title="${tipEtat}"></span>`;

    const titleHtml = titleAttr ? ` title="${Atelier.escAttr(titleAttr)}"` : '';

    return `<div class="${cls}" onclick="${onclick}"${oncontextmenu}${dataIdAttr}${titleHtml}>`
         + (badge ? badge : '')
         + id
         + libHtml
         + tagsHtml
         + pastille
         + `</div>`;
  }
}

// Exposition globale
window.Atelier = Atelier;
