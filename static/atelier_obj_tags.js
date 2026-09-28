/**
 * static/atelier_obj_tags.js — v0.13.6.10
 *
 * Tags d'affichage des liens des atomes dans la sidebar.
 *
 * v0.13.6.10 — Refonte :
 *   - Renommé : atelObjLiesEnTags → atelLiensEnTags
 *   - Entrée : tableau d'OBJETS typés (et non plus de strings) :
 *       [{type:'obj', niveau, sequence, code}, ...]
 *       [{type:'part', niveau, sequence, numero}, ...]
 *   - Sortie : tableau de strings affichables.
 *
 * Format des tags selon la position relative au filtre courant
 * (window.ATL_FILTRE_NIVEAU / window.ATL_FILTRE_SEQ) :
 *
 *   Lien vers un objectif (type='obj') :
 *     - Local (même niveau, même séquence)  : « obj 02 »
 *     - Hors séquence, même niveau          : « S03 obj 02 »
 *     - Hors niveau                         : « N11 S03 obj 02 »
 *
 *   Lien vers une partie (type='part', R/EA) :
 *     - Local                                : « part 01 »
 *     - Hors séquence, même niveau           : « S03 part 02 »
 *     - Hors niveau                          : « N11 S03 part 02 »
 *
 * Truncate à 3 tags maximum + « +N » si plus.
 *
 * Implémentation : fichier chargé APRÈS app.js dans index.html ; les
 * fonctions sont posées sur window. La carte d'automatisme n'utilise
 * pas (encore) ce mécanisme — elle affiche « n NN » / « m MM » selon
 * son lien direct vers notion/méthode. Sera homogénéisée au chantier C.
 */

(function _installerAtelTags() {

  /**
   * Construit la liste des placedTags à partir d'un tableau de liens
   * structurés `{type, niveau, sequence, code|numero}`.
   *
   * @param {Array<Object>} liens  liste de liens (peut être vide/null)
   * @returns {string[]}  liste de tags affichables, max 3 + indicateur +N
   */
  window.atelLiensEnTags = function (liens) {
    const arr = liens || [];
    if (arr.length === 0) return [];

    const nivCourant = window.ATL_FILTRE_NIVEAU || '';
    const seqCourante = window.ATL_FILTRE_SEQ || '';

    const tags = arr.slice(0, 3).map(l => _formaterLien(l, nivCourant, seqCourante));

    const reste = arr.length - 3;
    if (reste > 0) tags.push(`+${reste}`);
    return tags;
  };

  /**
   * Formate un lien individuel en tag affichable.
   *
   * Choisit le préfixe selon `type` ('obj' ou 'part') et la position
   * relative au filtre courant.
   *
   * Robustesse : si le lien n'est pas un objet ou n'a pas les champs
   * attendus, on retourne une chaîne vide (silencieux côté UI).
   */
  function _formaterLien(lien, nivCourant, seqCourante) {
    if (!lien || typeof lien !== 'object') return '';
    const niv = lien.niveau || '';
    const seq = lien.sequence || '';

    let suffixe;
    if (lien.type === 'obj') {
      suffixe = `obj ${lien.code || ''}`;
    } else if (lien.type === 'part') {
      const num = String(lien.numero || '').padStart(2, '0');
      suffixe = `part ${num}`;
    } else {
      // Type inconnu : fallback minimal silencieux
      suffixe = lien.code || lien.numero || '';
    }

    if (niv === nivCourant && seq === seqCourante) {
      return suffixe;
    }
    if (niv === nivCourant) {
      return `${seq} ${suffixe}`;
    }
    return `${niv} ${seq} ${suffixe}`;
  }

  // Expose le helper privé pour permettre aux ateliers de formatter un
  // lien unique sans passer par la liste complète.
  window.atelLienEnTag = _formaterLien;

})();
