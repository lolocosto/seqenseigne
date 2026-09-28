/**
 * static/atelier_filtres_hook.js — v0.13.6.17
 *
 * Synchronisation des ateliers OO avec les variables globales de filtre
 * (window.ATL_FILTRE_NIVEAU / window.ATL_FILTRE_SEQ).
 *
 * Contexte du bug initial (v0.13.6.10) : avant cette version, les
 * ateliers OO (notion, méthode, exercice, fiche, carte) avaient leurs
 * propres propriétés `this.niveauFiltre` / `this.sequenceFiltre` qui
 * n'étaient JAMAIS mises à jour. Quand l'utilisateur changeait de niveau
 * via la barre de portée, app.js mettait à jour `ATL_FILTRE_NIVEAU`
 * mais ne rechargeait pas la liste OO. Symptôme : la liste restait
 * figée sur le premier niveau chargé, donnant l'impression de liste
 * vide pour les autres niveaux.
 *
 * Fix v0.13.6.10 :
 *   1. Les ateliers OO lisent maintenant `window.ATL_FILTRE_*` (cf.
 *      atelier_editeur.js).
 *   2. Ce fichier installe un hook sur `atelExposerFiltres` (la fonction
 *      d'app.js appelée quand le filtre change) pour déclencher un
 *      rechargement des ateliers OO existants.
 *   3. Plus aucun filtrage côté JS sur niveau/sequence — le serveur fait
 *      tout (filtre uniforme dans routes/atomes.py et routes/fiches_resume.py).
 *
 * v0.13.6.17 — Optimisation : on ne recharge plus **tous** les ateliers
 * OO à chaque changement de filtre (auparavant : 5 GET en parallèle :
 * notion + méthode + exercice + fiche + carte). Seul l'atelier actuellement
 * actif est rechargé. Les autres seront rechargés à la demande quand
 * l'utilisateur basculera dessus (cf. atelInvoquerInit dans app.js).
 *
 * Pattern monkey-patch : on wrappe `window.atelExposerFiltres` (définie
 * dans app.js) pour appeler l'original puis recharger l'atelier actif.
 * Ainsi pas besoin de toucher au gros app.js.
 */

(function _installerHookFiltres() {

  // Mapping panel → instance d'atelier OO. Les panels OO sont 5 ; les
  // autres panels (livret, theme, etc.) ont leur propre logique de
  // rechargement déclenchée par atelInvoquerInit. Un panel inconnu ne
  // déclenche aucun rechargement, ce qui est le comportement souhaité.
  const PANEL_VERS_ATELIER = {
    'exercice':          'ATELIER_EXERCICE',
    'notion':            'ATELIER_NOTION',
    'methode':           'ATELIER_METHODE',
    'fiche':             'ATELIER_FICHE',
    'carte_automatisme': 'ATELIER_CARTE',
  };

  function _rechargerAtelierActif() {
    const panel = window.ATL_PANEL_ACTIF;
    const nomAtelier = PANEL_VERS_ATELIER[panel];
    if (!nomAtelier) return;  // panel non-OO ou indéterminé
    const at = window[nomAtelier];
    if (at && typeof at.chargerListe === 'function') {
      // Pas de await : on lance et on retourne ; les erreurs réseau
      // sont déjà gérées par chargerListe (toast).
      at.chargerListe();
    }
  }

  // Attendre que app.js ait fini de charger pour wrapper atelExposerFiltres.
  // On utilise DOMContentLoaded comme point de synchro fiable.
  function _installer() {
    if (typeof window.atelExposerFiltres !== 'function') {
      // app.js pas encore chargé ; ré-essayer plus tard
      setTimeout(_installer, 50);
      return;
    }
    if (window.__atelHookFiltresInstalle__) return;
    window.__atelHookFiltresInstalle__ = true;

    const _exposerOriginal = window.atelExposerFiltres;
    window.atelExposerFiltres = function () {
      // Appel original : met à jour window.ATL_FILTRE_NIVEAU/SEQ
      const r = _exposerOriginal.apply(this, arguments);
      // Puis on demande à l'atelier OO actif de se recharger.
      // v0.13.6.17 — Plus de rechargement de TOUS les ateliers OO ;
      // seul l'actif. Les autres se rechargeront quand on basculera
      // dessus (via atelInvoquerInit dans atelSwitch).
      _rechargerAtelierActif();
      return r;
    };
  }

  // Lancement dès que possible
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _installer);
  } else {
    _installer();
  }
})();
