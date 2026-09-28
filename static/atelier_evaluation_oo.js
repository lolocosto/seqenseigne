/**
 * static/atelier_evaluation_oo.js — v0.15
 *
 * Atelier Évaluation (portée Niveau), version OO.
 *
 * Hérite de AtelierAssemblage qui hérite d'AtelierEditeur. Remplace
 * l'ancien `static/atelier_evaluation.js` (variables globales
 * `ATL_EVAL_*` + fonctions globales `atelEval*`).
 *
 * Décisions de migration (cf. cadrage v0.15) :
 *
 *   - Compat HTML : les fonctions globales `window.atelEval*` sont
 *     conservées comme proxies vers les méthodes d'instance, pour ne
 *     pas avoir à modifier les `onclick` de index.html (aligné sur
 *     ce que fait déjà ATELIER_EXERCICE.nouvelItem() côté HTML, mais
 *     ici on garde la forme atelEvalX() qui est plus historique).
 *
 *   - IDs DOM : l'évaluation a sa propre convention `atl-eval-*` qui
 *     ne suit PAS strictement la convention `{prefixe}-list`,
 *     `{prefixe}-form`, etc. d'AtelierEditeur. On garde les IDs HTML
 *     existants : la classe utilise `document.getElementById('atl-eval-X')`
 *     directement, pas `this.$('X')`, pour éviter d'avoir à modifier
 *     le HTML.
 *
 *   - Compilation PDF : la machinerie de compilation héritée d'AtelierEditeur
 *     (verifierCacheEtAfficher, compilerRendu, etc.) ne peut pas être
 *     réutilisée telle quelle parce que le HTML de l'éval n'a pas la
 *     même structure d'IDs (pas de `atl-eval-rendu-status`, pas de
 *     `atl-eval-rendu-placeholder`, pas de `atl-eval-pdf-iframe`).
 *     On garde donc la machinerie de compilation locale, héritée
 *     telle quelle de l'ancien `atelier_evaluation.js`. Une éventuelle
 *     factorisation viendra plus tard, conjointement à une refonte
 *     du HTML.
 *
 *   - Snapshot modifié : l'évaluation utilise le mécanisme historique
 *     d'un flag `this._modifieFlag` géré manuellement (via les onchange
 *     du HTML qui appellent `atelEvalMarquerModifie`). On NE branche
 *     PAS le listener délégué du parent AtelierEditeur (qui exige un
 *     `<form id="{prefixe}-form">`, qu'on n'a pas ici). C'est pourquoi
 *     on redéfinit `modifie` localement.
 *
 *   - Bascule de validation : `AtelierEditeur.basculerValidation` cible
 *     `/api/atomes/{type}/{id}/etat` (mécanisme unifié des atomes).
 *     L'évaluation a sa propre route `/api/evaluations/{id}/valider`
 *     et `/devalider` avec gestion d'erreurs pédagogiques typée. On
 *     redéfinit.
 *
 * Modèle de transitions (cf. services/evaluations.py) :
 *   en_cours → valide  : contrôlé côté backend (≥1 exo + barèmes
 *                        cohérents avec mode_notation)
 *   valide → en_cours  : libre (cohérent avec etats_edition des atomes)
 */


class AtelierEvaluation extends AtelierAssemblage {
  constructor() {
    super({
      id:                   'evaluation',
      prefixe:              'atl-eval',
      estPluriel:           true,
      persistanceImmediate: false,
      endpointBase:         '/api/evaluations',
      endpointRenduPdf:     '/api/evaluations',
      labelExistant:        'Évaluation',
      labelNouveau:         'Nouvelle évaluation',
      typeApi:              'evaluation',
      typeBadge:            'evaluation',
      confirmSuppression:   "Supprimer cette évaluation ?",
      messageEnregistre:    'Évaluation enregistrée.',
      messageSupprime:      'Évaluation supprimée.',
    });

    // ── État local de l'atelier ────────────────────────────────────────────
    // Avant v0.15 : variables globales ATL_EVAL_*. Désormais : attributs
    // d'instance. Les wrappers `window.atelEval*` continuent d'exister
    // pour la compat des onclick=… dans index.html, et délèguent à
    // l'instance unique.

    this.liste            = [];     // évals du niveau courant (LISTE plurielle)
    this.itemActif        = null;   // évaluation actuellement éditée (cf. AtelierEditeur)
    this.exos             = [];     // exos liés à l'éval active (enrichis)
    this.objs             = [];     // objectifs liés à l'éval active
    this.couverture       = null;   // { objectifs, exercices, cellules }
    this.exosDispo        = {};     // exos disponibles par séquence (sélecteur)
    this.objsDispo        = {};     // objectifs disponibles par séquence
    this.filtreEtat       = '';     // '' (tous) | 'en_cours' | 'valide'
    this._baremesModifies = false;  // v0.16.5 — drapeau barèmes (cf. modifie)
    this.tabCourant       = 'edition';  // 'edition' | 'rendu'
    this.lignesFautives   = [];     // pour highlight dans .tex brut
  }

  // ── Getter/setter `modifie` — CONCEPTION Y (v0.16.5, 2b-2) ──────────────
  //
  // Deux sources INDÉPENDANTES de « modifié », additives :
  //   1. Le snapshot de la base (AtelierEditeur) sur les CHAMPS STABLES
  //      (titre, mode, afficher-barème, langue) — cf. collecterFormulaire.
  //   2. Le drapeau `_baremesModifies` sur les BARÈMES — qui sont attachés à
  //      des exos dont la présence relève de la STRUCTURE (persistée
  //      immédiatement). Les mettre dans le snapshot ferait diverger celui-ci
  //      à chaque ajout/retrait d'exo, ce qui effacerait la trace d'un champ
  //      modifié. En les sortant, une opération de structure ne « nettoie »
  //      jamais l'état modifié : la garde de sortie reste fiable.
  //
  // Le `<form id="atl-eval-form">` (v0.16.5) permet à _installerListenerForm
  // de la base de capter les input/change des champs stables.

  get modifie() {
    return super.modifie || this._baremesModifies;
  }

  set modifie(val) {
    // Délègue au setter parent (gère le snapshot des champs stables). Le
    // drapeau barèmes est réinitialisé ici quand on repasse « propre ».
    super.modifie = val;
    if (!val) this._baremesModifies = false;
  }

  // ── Helpers locaux ─────────────────────────────────────────────────────

  _esc(s) {
    if (s === null || s === undefined) return '';
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  _toast(message, erreur = false) {
    if (typeof window.atelToast === 'function') {
      window.atelToast(message, erreur);
    } else {
      console[erreur ? 'error' : 'log'](message);
    }
  }

  /** Niveau filtre courant (depuis le sélecteur de portée global). */
  _niveau() {
    return (typeof window.ATL_FILTRE_NIVEAU !== 'undefined')
      ? window.ATL_FILTRE_NIVEAU : '';
  }

  /**
   * Wrapper API qui throw correctement sur 4xx/5xx.
   *
   * Pourquoi un helper local et pas le `api()` global ?
   *   Le `api()` global de app.js fait juste `fetch().then(r => r.json())`
   *   SANS vérifier `r.ok`. Sur 4xx, le JSON d'erreur arrive comme un
   *   succès, le `catch` du caller ne se déclenche jamais, et l'état
   *   JS part en vrille (bug v0.13.5.2.4 : « validation échoue
   *   silencieusement »).
   *
   *   Refactorer `api()` toucherait toutes les autres ateliers, c'est
   *   hors périmètre v0.15. À traiter en v0.16+ (audit JS).
   */
  async _api(path, opts = {}) {
    const r = await fetch(path, {
      headers: { 'Content-Type': 'application/json' },
      ...opts,
    });
    let payload = null;
    const txt = await r.text();
    if (txt) {
      try { payload = JSON.parse(txt); }
      catch (e) { payload = { _raw: txt }; }
    }

    if (!r.ok) {
      const err = new Error(`HTTP ${r.status} sur ${path}`);
      err.status  = r.status;
      err.code    = (payload && payload.code)    || null;
      err.message = (payload && payload.error)   || err.message;
      err.details = (payload && payload.details) || {};
      err.payload = payload;
      // v0.16.4 — L'éval validée est verrouillée côté backend (409). Tant que
      // l'UI éval n'est pas grisée (prévu en 2b-2), on affiche ici un message
      // explicite pour que l'utilisateur comprenne (au lieu d'un « Échec… »
      // générique émis par les catch appelants).
      if (r.status === 409 && err.code === 'item_verrouille') {
        this._toast(
          "Évaluation validée (lecture seule). Repassez-la en cours pour la modifier.",
          true,
        );
      }
      throw err;
    }

    return payload;
  }

  /** Construit le label métier d'un exo "N10/S01/F01" pour affichage. */
  _labelExo(eb) {
    const niveau   = eb.niveau   || '';
    const sequence = eb.sequence || '';
    const serie    = eb.serie_code || '';
    const num      = eb.num != null ? String(eb.num).padStart(2, '0') : '';
    const code = serie + num;
    const id = [niveau, sequence, code].filter(Boolean).join('/');
    return id || eb.exercice_id || '?';
  }

  /** Retrouve le label d'un exo par son ID BDD (pour les messages d'erreur). */
  _labelExoParId(exoIdBdd) {
    const eb = this.exos.find(e => e.exercice_id === exoIdBdd);
    return eb ? this._labelExo(eb) : exoIdBdd;
  }


  // ── Initialisation et chargement ───────────────────────────────────────

  /**
   * Appelé par atelInvoquerInit() au switch sur l'onglet Évaluation
   * et au changement de filtre de niveau (cf. app.js).
   */
  async init() {
    this.itemActif    = null;
    this.exos         = [];
    this.objs         = [];
    this.couverture   = null;
    this._baremesModifies = false;
    this.tabCourant   = 'edition';
    await Promise.all([
      this._rechargerListe(),
      this._rechargerExosDispos(),
      this._rechargerObjsDispos(),
    ]);
    this._rendreSidebar();
    this._rendreVueComplete();
  }

  async _rechargerListe() {
    const niveau = this._niveau();
    if (!niveau) { this.liste = []; return; }
    try {
      const data = await this._api(
        `/api/evaluations?niveau=${encodeURIComponent(niveau)}`,
      );
      this.liste = (data && data.evaluations) || [];
    } catch (e) {
      console.error('Échec chargement évaluations :', e);
      this.liste = [];
    }
  }

  /**
   * Charge le détail complet d'une éval (en parallèle : éval, exos,
   * objectifs, couverture). Si une étape échoue, on n'écrase pas
   * itemActif (résilience au bug d'écran zombi).
   */
  async _chargerActif(evalId) {
    try {
      const [evResp, exosResp, objsResp, couvResp] = await Promise.all([
        this._api(`/api/evaluations/${encodeURIComponent(evalId)}`),
        this._api(`/api/evaluations/${encodeURIComponent(evalId)}/exos`),
        this._api(`/api/evaluations/${encodeURIComponent(evalId)}/objectifs`),
        this._api(`/api/evaluations/${encodeURIComponent(evalId)}/couverture`),
      ]);
      this.itemActif    = evResp.evaluation;
      this.exos         = exosResp.exos      || [];
      this.objs         = objsResp.objectifs || [];
      this.couverture   = couvResp;
      // v0.16.5 — On ne (ré)initialise PAS l'état modifié ici. Selon
      // l'appelant : sélection/création → snapshot propre APRÈS le rendu du
      // form ; rechargement après opération de structure → on PRÉSERVE l'état
      // modifié (la garde de sortie doit rester fiable). Cf. cadrage 2b-2 §3.4.
      return true;
    } catch (e) {
      console.error('Échec chargement détail éval :', e);
      this._toast('Échec du chargement de l\'évaluation.', true);
      return false;
    }
  }

  async _rechargerExosDispos() {
    const niveau = this._niveau();
    if (!niveau) { this.exosDispo = {}; return; }
    try {
      const data = await this._api(
        `/api/evaluations/niveau/${encodeURIComponent(niveau)}/exos-disponibles`,
      );
      this.exosDispo = (data && data.par_sequence) || {};
    } catch (e) {
      console.error('Échec chargement exos dispos :', e);
      this.exosDispo = {};
    }
  }

  async _rechargerObjsDispos() {
    const niveau = this._niveau();
    if (!niveau) { this.objsDispo = {}; return; }
    try {
      const data = await this._api(
        `/api/evaluations/niveau/${encodeURIComponent(niveau)}/objectifs-disponibles`,
      );
      this.objsDispo = (data && data.par_sequence) || {};
    } catch (e) {
      console.error('Échec chargement objectifs dispos :', e);
      this.objsDispo = {};
    }
  }


  // ── Rendu : sidebar (liste des évals avec filtre par état) ─────────────

  _rendreSidebar() {
    const cont = document.getElementById('atl-eval-list');
    if (!cont) return;

    const items = this.liste.filter(ev => {
      if (!this.filtreEtat) return true;
      return (ev.etat_code || 'en_cours') === this.filtreEtat;
    });

    if (items.length === 0) {
      const message = this.liste.length === 0
        ? 'Aucune évaluation pour ce niveau.<br>Cliquez sur <strong>+ Créer</strong>.'
        : 'Aucune évaluation ne correspond au filtre.';
      cont.innerHTML = `<div style="padding:14px;font-size:12px;
          color:var(--text-muted);text-align:center">${message}</div>`;
      return;
    }

    cont.innerHTML = items.map(ev => {
      const actif = this.itemActif && ev.id === this.itemActif.id;
      const titre = ev.titre || '(sans titre)';
      const etat  = ev.etat_code || 'en_cours';
      const badge = etat === 'valide'
        ? `<span class="atl-list-item-etat atome-etat--valide">Validé</span>`
        : '';
      const cls = 'atl-item' + (actif ? ' active' : '');
      const numero = ev.numero != null
        ? `<span class="atl-item-id">#${ev.numero}</span>` : '';
      return `<div class="${cls}" onclick="atelEvalSelectionner('${this._esc(ev.id)}')">
        ${numero}
        <span class="atl-item-titre" style="flex:1;min-width:0;overflow:hidden;
              text-overflow:ellipsis;white-space:nowrap">${this._esc(titre)}</span>
        ${badge}
      </div>`;
    }).join('');
  }

  filtrerEtat(btn, etat) {
    this.filtreEtat = etat || '';
    if (btn && btn.parentElement) {
      btn.parentElement.querySelectorAll('.exo-etat').forEach(b => {
        b.classList.toggle('active', b === btn);
      });
    }
    this._rendreSidebar();
  }


  // ── Rendu : vue complète de la zone droite ──────────────────────────────

  _rendreVueComplete() {
    const empty   = document.getElementById('atl-eval-empty');
    const tabs    = document.getElementById('atl-eval-tabs');
    const tabE    = document.getElementById('atl-eval-tab-edition');
    const tabR    = document.getElementById('atl-eval-tab-rendu');

    if (!this.itemActif) {
      if (empty) empty.style.display = '';
      if (tabs)  tabs.style.display  = 'none';
      if (tabE)  tabE.style.display  = 'none';
      if (tabR)  tabR.style.display  = 'none';
      this._majToolbar();
      return;
    }

    if (empty) empty.style.display = 'none';
    if (tabs)  tabs.style.display  = '';

    if (this.tabCourant === 'rendu') {
      if (tabE) tabE.style.display = 'none';
      if (tabR) tabR.style.display = '';
    } else {
      if (tabE) tabE.style.display = '';
      if (tabR) tabR.style.display = 'none';
    }

    this._remplirFormulaire();
    // v0.16.5 — Pose le listener input/change sur #atl-eval-form (méthode
    // héritée, idempotente) pour que les champs stables mettent à jour la
    // toolbar via le snapshot de la base.
    this._installerListenerForm();
    this._rendreExos();
    this._rendreObjs();
    this._rendreCouverture();
    this._remplirSelecteurExos();
    this._remplirSelecteurObjectifs();
    this._majToolbar();
  }

  /**
   * Implémentation du hook abstrait `rendreContenuPrincipal` de la
   * classe parente AtelierAssemblage. Pour l'évaluation, c'est juste
   * une délégation à `_rendreVueComplete` qui fait tout le travail.
   */
  rendreContenuPrincipal(_item) {
    this._rendreVueComplete();
  }

  _remplirFormulaire() {
    const ev = this.itemActif;
    if (!ev) return;

    const elT = document.getElementById('atl-eval-titre');
    if (elT) elT.value = ev.titre || '';

    const elM = document.getElementById('atl-eval-mode');
    if (elM) elM.value = ev.mode_notation || 'note';

    const elC = document.getElementById('atl-eval-afficher-bareme');
    if (elC) elC.checked = !!ev.afficher_bareme_dans_exos;

    const elL = document.getElementById('atl-eval-langue-points');
    if (elL) {
      let v = '';
      // v0.16.1 — Le backend renvoie item_langue_francaise déjà parsé en
      // objet ({points: N}) ou null. On l'utilise directement. Filet de
      // robustesse : si une str arrive (ancien format), on la parse.
      let obj = ev.item_langue_francaise || null;
      if (typeof obj === 'string') {
        try { obj = JSON.parse(obj); } catch (e) { obj = null; }
      }
      if (obj && typeof obj.points === 'number') v = obj.points;
      elL.value = v;
    }
    // v0.16.3 — Met à jour l'indicateur « désactivé » selon la valeur chargée.
    this.majLangueIndic();
  }


  // ── Rendu : toolbar (badges + boutons) ──────────────────────────────────

  /**
   * v0.16.3 — Met à jour l'indicateur visuel de l'item « langue française ».
   * L'item est optionnel : un total de 0 pt signifie « désactivé » (la ligne
   * n'est pas émise dans le barème auto). On le signale explicitement à côté
   * du champ pour que ce ne soit pas une surprise.
   */
  majLangueIndic() {
    const input = document.getElementById('atl-eval-langue-points');
    const indic = document.getElementById('atl-eval-langue-indic');
    if (!input || !indic) return;
    const v = input.value.trim();
    if (v === '') {
      indic.textContent = '';
      return;
    }
    const n = parseFloat(v);
    if (!isNaN(n) && Math.abs(n) < 1e-9) {
      indic.textContent = '(désactivé : non compté dans le barème)';
    } else {
      indic.textContent = '';
    }
  }

  _majToolbar() {
    const badgeMod   = document.getElementById('atl-eval-badge-modifie');
    const badgeEtat  = document.getElementById('atl-eval-etat-badge');
    const btnValider = document.getElementById('atl-eval-btn-valider');
    const btnLatex   = document.getElementById('atl-eval-btn-latex');
    const btnSuppr   = document.getElementById('atl-eval-btn-suppr');
    const btnSave    = document.getElementById('atl-eval-btn-save');
    const title      = document.getElementById('atl-eval-toolbar-title');

    if (!this.itemActif) {
      if (badgeMod)   badgeMod.style.display   = 'none';
      if (badgeEtat)  badgeEtat.style.display  = 'none';
      if (btnValider) btnValider.style.display = 'none';
      if (btnLatex)   btnLatex.style.display   = 'none';
      if (btnSuppr)   btnSuppr.style.display   = 'none';
      if (btnSave)    btnSave.style.display    = 'none';
      if (title)      title.textContent        = 'Atelier Évaluation';
      return;
    }

    const ev = this.itemActif;
    if (title) {
      const t = ev.titre || '(sans titre)';
      title.textContent = `Évaluation #${ev.numero || '?'} — ${t}`;
    }

    if (badgeMod) badgeMod.style.display = this.modifie ? '' : 'none';

    const etat = ev.etat_code || 'en_cours';
    if (badgeEtat) {
      badgeEtat.style.display = '';
      badgeEtat.className = `atome-etat-badge atome-etat--${etat}`;
      badgeEtat.textContent = etat === 'valide' ? 'Validé' : 'En cours';
    }
    if (btnValider) {
      btnValider.style.display = '';
      btnValider.textContent = etat === 'valide' ? 'Repasser en cours' : 'Valider';
      btnValider.title = etat === 'valide'
        ? 'Revenir à l\'état « En cours » pour modifier'
        : 'Vérifier les barèmes et passer en état « Validé »';
    }
    if (btnLatex) btnLatex.style.display = '';
    if (btnSuppr) btnSuppr.style.display = '';
    if (btnSave)  btnSave.style.display  = '';

    // v0.16.5 (2b-2) — Verrou « validé = lecture seule » pour l'évaluation.
    // Le <form id="atl-eval-form"> existant permet de réutiliser la méthode
    // héritée d'AtelierEditeur : elle grise les champs ET les boutons de
    // structure (ajout/retrait exo & objectif) qui sont dans le form. Le
    // bouton « Repasser en cours », les onglets et « Compiler » sont hors
    // form → restent actifs. Backend déjà protégé (409) depuis v0.16.4.
    this._appliquerVerrouLectureSeule(etat === 'valide');
  }

  /**
   * Surcharge la méthode hérité d'AtelierEditeur pour utiliser nos IDs
   * locaux (atl-eval-*) qui ne suivent pas la convention
   * `{prefixe}-toolbar-title`, etc.
   */
  majToolbar() {
    this._majToolbar();
  }


  // ── Rendu : liste des exos liés (avec champs de barème) ─────────────────

  _rendreExos() {
    const cont = document.getElementById('atl-eval-exos-liste');
    if (!cont) return;

    if (this.exos.length === 0) {
      cont.innerHTML = '<div style="font-size:12px;color:var(--text-muted);'
        + 'font-style:italic">Aucun exercice attaché.</div>';
      return;
    }

    const mode = (this.itemActif && this.itemActif.mode_notation) || 'note';

    cont.innerHTML = this.exos.map((eb, idx) => {
      const exoId = eb.exercice_id;
      const tf    = eb.type_format || 'standard';
      const label = this._labelExo(eb);
      // v0.15.1.1 — Le backend renvoie `titre` (cf. lister_exos_evaluation
      // dans services/evaluations.py — `nom` a été renommé en `titre` en
      // v0.13.6.12). L'ancien atelier_evaluation.js lisait `eb.nom` qui
      // était systématiquement undefined, d'où "(sans titre)" pour tous
      // les exos. Idem au niveau du sélecteur d'ajout.
      const titre = eb.titre || '';
      const num   = idx + 1;

      let inputsBareme = '';
      if (mode === 'note' || mode === 'note_criteres') {
        if (tf === 'qcm') {
          inputsBareme = `
            <label style="font-size:11px">OK
              <input type="number" step="0.5" min="0" style="width:54px"
                value="${eb.bareme_qcm_ok ?? ''}"
                data-exo-id="${this._esc(exoId)}" data-bareme-champ="bareme_qcm_ok"
                oninput="atelEvalMarquerModifie()">
            </label>
            <label style="font-size:11px">Partiel
              <input type="number" step="0.5" min="0" style="width:54px"
                value="${eb.bareme_qcm_partiel ?? ''}"
                data-exo-id="${this._esc(exoId)}" data-bareme-champ="bareme_qcm_partiel"
                oninput="atelEvalMarquerModifie()">
            </label>
            <label style="font-size:11px">KO
              <input type="number" step="0.5" min="0" style="width:54px"
                value="${eb.bareme_qcm_ko ?? ''}"
                data-exo-id="${this._esc(exoId)}" data-bareme-champ="bareme_qcm_ko"
                oninput="atelEvalMarquerModifie()">
            </label>`;
        } else {
          inputsBareme = `
            <label style="font-size:11px">Pts
              <input type="number" step="0.5" min="0" style="width:64px"
                value="${eb.bareme_points ?? ''}"
                data-exo-id="${this._esc(exoId)}" data-bareme-champ="bareme_points"
                oninput="atelEvalMarquerModifie()">
            </label>`;
        }
      } else if (mode === 'criteres' || mode === 'aucun') {
        inputsBareme = '<span style="font-size:11px;color:var(--text-muted);font-style:italic">'
          + 'pas de barème en mode ' + this._esc(mode) + '</span>';
      }

      // v0.18.2 — Le label exo est un lien deeplink : clic simple = ouvrir
      // l'exercice EN PLACE dans son atelier, Ctrl/⌘+clic = nouvel onglet.
      // niveau/séquence portés par l'objet exo (eb.niveau / eb.sequence).
      const labelHtml = (typeof window.lienAtomeHTML === 'function')
        ? window.lienAtomeHTML(
            'exercice', exoId, eb.niveau || '', eb.sequence || '',
            this._esc(label),
            'style="font-family:monospace;color:var(--primary);font-size:11px;'
            + 'min-width:90px;text-decoration:none"')
        : `<span style="font-family:monospace;color:var(--text-muted);font-size:11px;min-width:90px">${this._esc(label)}</span>`;

      return `<div class="atl-item-row"
                   style="display:flex;align-items:center;gap:10px;
                          padding:6px 8px;border:1px solid var(--border);
                          border-radius:4px;background:var(--bg-card)">
        <span style="font-weight:600;color:var(--text-muted);min-width:24px">${num}.</span>
        ${labelHtml}
        <span style="flex:1;font-size:13px">${this._esc(titre || '(sans titre)')}</span>
        ${tf === 'qcm' ? '<span style="padding:1px 6px;background:#e9d8fd;color:#553c9a;border-radius:3px;font-size:10px;font-weight:600">QCM</span>' : ''}
        ${inputsBareme}
        <button class="btn-sm" onclick="atelEvalDeplacerExo('${this._esc(exoId)}', -1)"
                title="Monter" style="padding:2px 6px">↑</button>
        <button class="btn-sm" onclick="atelEvalDeplacerExo('${this._esc(exoId)}', 1)"
                title="Descendre" style="padding:2px 6px">↓</button>
        <button class="btn-danger btn-sm"
                onclick="atelEvalRetirerExo('${this._esc(exoId)}')"
                title="Retirer">✕</button>
      </div>`;
    }).join('');
  }


  // ── Rendu : liste des objectifs liés ────────────────────────────────────

  _rendreObjs() {
    const cont = document.getElementById('atl-eval-objs-liste');
    if (!cont) return;

    if (this.objs.length === 0) {
      cont.innerHTML = '<div style="font-size:12px;color:var(--text-muted);'
        + 'font-style:italic">Aucun objectif déclaré.</div>';
      return;
    }

    cont.innerHTML = this.objs.map(o => {
      return `<div style="display:flex;align-items:center;gap:8px;
                          padding:4px 8px;border:1px solid var(--border);
                          border-radius:4px;background:var(--bg-card);font-size:12px">
        <span style="font-family:monospace;color:var(--text-muted);min-width:90px">
          ${this._esc(o.sequence_code)}·p${o.partie_numero}·${this._esc(o.code)}
        </span>
        <span style="flex:1">${this._esc(o.nom)}</span>
        <button class="btn-danger btn-sm"
                onclick="atelEvalRetirerObjectif('${this._esc(o.id)}')"
                title="Retirer">✕</button>
      </div>`;
    }).join('');
  }


  // ── Rendu : matrice de couverture ───────────────────────────────────────

  _rendreCouverture() {
    const zone = document.getElementById('atl-eval-couverture-zone');
    if (!zone) return;

    if (!this.couverture
        || this.couverture.objectifs.length === 0
        || this.couverture.exercices.length === 0) {
      zone.innerHTML = '<div style="font-size:12px;color:var(--text-muted);'
        + 'font-style:italic">Ajoutez des objectifs et des exercices pour '
        + 'voir la matrice de couverture.</div>';
      return;
    }

    const objs = this.couverture.objectifs;
    const exos = this.couverture.exercices;
    const cellulesSet = new Set(
      this.couverture.cellules.map(c => `${c.objectif_id}::${c.exercice_id}`),
    );

    let html = '<table style="border-collapse:collapse;font-size:11px;width:auto">';
    html += '<thead><tr>';
    html += '<th style="padding:4px 8px;border:1px solid var(--border);'
      + 'background:var(--surface-light);text-align:left;position:sticky;left:0">Objectif</th>';
    exos.forEach((ex) => {
      const lbl = this._labelExo(ex);
      html += `<th style="padding:4px 8px;border:1px solid var(--border);
                          background:var(--surface-light);text-align:center;
                          font-weight:600;min-width:50px"
                   title="${this._esc(ex.titre || ex.exercice_id || ex.id)}">
        ${this._esc(lbl)}
      </th>`;
    });
    html += '</tr></thead><tbody>';

    objs.forEach(o => {
      html += '<tr>';
      html += `<td style="padding:4px 8px;border:1px solid var(--border);
                          background:var(--bg-card);position:sticky;left:0">
        <span style="font-family:monospace;color:var(--text-muted)">
          ${this._esc(o.sequence_code)}·p${o.partie_numero}·${this._esc(o.code)}
        </span>
        &nbsp; ${this._esc(o.nom)}
      </td>`;
      exos.forEach(ex => {
        const key = `${o.id}::${ex.id || ex.exercice_id}`;
        const ok  = cellulesSet.has(key);
        html += `<td style="padding:4px 8px;border:1px solid var(--border);
                            text-align:center;
                            background:${ok ? '#d4edda' : 'transparent'}">
          ${ok ? '<span style="color:#155724;font-weight:600">●</span>' : ''}
        </td>`;
      });
      html += '</tr>';
    });
    html += '</tbody></table>';
    zone.innerHTML = html;
  }


  // ── Sélecteurs d'ajout ──────────────────────────────────────────────────

  _remplirSelecteurExos() {
    const selSeq = document.getElementById('atl-eval-add-exo-seq');
    if (!selSeq) return;
    const sequences = Object.keys(this.exosDispo).sort();
    selSeq.innerHTML = '<option value="">— Séquence —</option>'
      + sequences.map(s => `<option value="${this._esc(s)}">${this._esc(s)}</option>`).join('');
    const selExo = document.getElementById('atl-eval-add-exo-id');
    if (selExo) {
      selExo.innerHTML = '<option value="">— Exercice —</option>';
      selExo.disabled = true;
    }
    const btn = document.getElementById('atl-eval-add-exo-btn');
    if (btn) btn.disabled = true;
  }

  filtrerExosAjoutables() {
    const selSeq = document.getElementById('atl-eval-add-exo-seq');
    const selExo = document.getElementById('atl-eval-add-exo-id');
    const btn    = document.getElementById('atl-eval-add-exo-btn');
    if (!selSeq || !selExo) return;
    const seq = selSeq.value;
    if (!seq) {
      selExo.innerHTML = '<option value="">— Exercice —</option>';
      selExo.disabled  = true;
      if (btn) btn.disabled = true;
      return;
    }
    const exos = this.exosDispo[seq] || [];
    const dejaAttaches = new Set(this.exos.map(e => e.exercice_id));
    const dispos = exos.filter(e => !dejaAttaches.has(e.id));
    selExo.innerHTML = '<option value="">— Exercice —</option>'
      + dispos.map(e => {
          const lbl = this._labelExo(e);
          // v0.15.1.1 — `titre` (et non `nom`, cf. note dans _rendreExos).
          const titre = e.titre || '(sans titre)';
          const tf  = e.type_format === 'qcm' ? ' [QCM]' : '';
          return `<option value="${this._esc(e.id)}">${this._esc(lbl)} — ${this._esc(titre)}${tf}</option>`;
        }).join('');
    selExo.disabled = dispos.length === 0;
    if (btn) btn.disabled = dispos.length === 0;
  }

  _remplirSelecteurObjectifs() {
    const sel = document.getElementById('atl-eval-add-obj-id');
    if (!sel) return;
    const sequences = Object.keys(this.objsDispo).sort();
    const dejaAttaches = new Set(this.objs.map(o => o.id));
    let html = '<option value="">— Objectif —</option>';
    sequences.forEach(seq => {
      const objs = (this.objsDispo[seq] || []).filter(
        o => !dejaAttaches.has(o.id),
      );
      if (objs.length === 0) return;
      html += `<optgroup label="${this._esc(seq)}">`;
      objs.forEach(o => {
        html += `<option value="${this._esc(o.id)}">`
          + `p${o.partie_numero}·${this._esc(o.code)} — ${this._esc(o.nom)}`
          + `</option>`;
      });
      html += '</optgroup>';
    });
    sel.innerHTML = html;
  }


  // ── Sous-onglets ────────────────────────────────────────────────────────

  basculerOnglet(nom) {
    this.tabCourant = nom;
    const btnE = document.getElementById('atl-eval-tab-btn-edition');
    const btnR = document.getElementById('atl-eval-tab-btn-rendu');
    if (btnE) btnE.classList.toggle('active', nom === 'edition');
    if (btnR) btnR.classList.toggle('active', nom === 'rendu');
    const tabE = document.getElementById('atl-eval-tab-edition');
    const tabR = document.getElementById('atl-eval-tab-rendu');
    if (tabE) tabE.style.display = nom === 'edition' ? '' : 'none';
    if (tabR) tabR.style.display = nom === 'rendu'   ? '' : 'none';

    // v0.17.1 — La mini-toolbar de rendu (bouton « Compiler le rendu » +
    // « LaTeX généré » + statut) est générée par la base
    // (_assurerToolbarRendu) depuis v0.17.0. L'évaluation surcharge
    // basculerOnglet et ne passait donc PAS par verifierCacheEtAfficher/
    // compilerRendu de la base à l'ouverture de l'onglet Rendu → le bouton
    // « Compiler » avait disparu. On régénère ici à l'ouverture du Rendu.
    if (nom === 'rendu') {
      this._assurerToolbarRendu();
      this.majToolbar();  // synchronise la visibilité du bouton LaTeX
    }
  }


  // ── Actions : sélection, création, suppression ──────────────────────────

  async selectionner(evalId) {
    if (this.modifie) {
      if (!confirm('Des modifications non enregistrées seront perdues. Continuer ?')) {
        return;
      }
    }
    this._afficherErreursValidation([]);
    await this._chargerActif(evalId);
    this._rendreSidebar();
    this._rendreVueComplete();
    // v0.16.5 — Snapshot propre APRÈS remplissage du form (sélection = on
    // repart d'un état non modifié).
    this._baremesModifies = false;
    this.modifie = false;
  }

  /**
   * Surcharge `nouvelItem()` d'AtelierEditeur : la méthode parente
   * exige un filtre niveau+séquence, mais l'évaluation est de portée
   * Niveau seul. On redéfinit pour autoriser la création sans filtre
   * séquence.
   */
  async nouvelItem() {
    const niveau = this._niveau();
    if (!niveau) {
      this._toast('Sélectionnez un niveau d\'abord.', true);
      return;
    }
    if (this.modifie) {
      if (!confirm('Des modifications non enregistrées seront perdues. Continuer ?')) {
        return;
      }
    }
    try {
      const data = await this._api('/api/evaluations', {
        method: 'POST',
        body: JSON.stringify({
          niveau,
          titre: 'Nouvelle évaluation',
          mode_notation: 'note',
        }),
      });
      await this._rechargerListe();
      await this._chargerActif(data.evaluation.id);
      this._rendreSidebar();
      this._rendreVueComplete();
      // v0.16.5 — nouvelle éval = état propre après rendu.
      this._baremesModifies = false;
      this.modifie = false;
      const elT = document.getElementById('atl-eval-titre');
      if (elT) { elT.focus(); elT.select(); }
    } catch (e) {
      console.error('Échec création éval :', e);
      this._toast('Échec de la création.', true);
    }
  }

  /**
   * Surcharge `supprimer()` d'AtelierEditeur : on utilise notre
   * `_api()` local (qui throw correctement sur 4xx/5xx).
   */
  async supprimer() {
    if (!this.itemActif) return;
    const nom = this.itemActif.titre || '(sans titre)';
    if (!confirm(`Supprimer définitivement l'évaluation « ${nom} » ?`)) return;
    try {
      await this._api(
        `/api/evaluations/${encodeURIComponent(this.itemActif.id)}`,
        { method: 'DELETE' },
      );
      this.itemActif = null;
      this._baremesModifies = false;
      this.modifie = false;
      await this._rechargerListe();
      this._rendreSidebar();
      this._rendreVueComplete();
      this._toast('Évaluation supprimée.');
    } catch (e) {
      console.error('Échec suppression :', e);
      this._toast('Échec de la suppression.', true);
    }
  }


  // ── Workflow d'édition : modifier (marquer modifié) + enregistrer ───────

  /**
   * v0.16.5 — Marque l'état « modifié ». Appelé par l'oninput des inputs
   * barème (hors snapshot) et, par commodité, par quelques champs stables du
   * template (redondant avec le listener form, sans effet néfaste). Lève le
   * drapeau barèmes `_baremesModifies` (cf. getter `modifie` conception Y).
   */
  marquerModifie() {
    if (!this._baremesModifies) {
      this._baremesModifies = true;
      this._majToolbar();
    }
  }

  /**
   * v0.16.2 (étape 2a) — `sauvegarder({silencieuse})` surcharge la version
   * d'AtelierEditeur (la route PATCH éval renvoie `{evaluation: …}`, pas
   * l'item nu attendu par la base). v0.16.5 (2b-2) — pousse aussi les barèmes
   * en un appel groupé (régime mixte) et reprend un état propre.
   *
   * @param {{silencieuse?: boolean}} options
   * @returns {Promise<boolean>} true si la sauvegarde a réussi.
   */
  async sauvegarder(options = {}) {
    if (!this.itemActif) return false;
    const silencieuse = !!options.silencieuse;

    const champs = this.collecterFormulaire();
    if (champs === null) return false;
    const evalId = this.itemActif.id;

    try {
      // 1. Champs stables (titre, mode, afficher-barème, langue).
      const data = await this._api(
        `/api/evaluations/${encodeURIComponent(evalId)}`,
        { method: 'PATCH', body: JSON.stringify(champs) },
      );
      // 2. Barèmes : push GROUPÉ de TOUS les barèmes présents (idempotent),
      //    via l'endpoint dédié (v0.16.3). Régime mixte 2b-2.
      const baremes = this._collecterBaremes();
      if (baremes.length > 0) {
        await this._api(
          `/api/evaluations/${encodeURIComponent(evalId)}/baremes`,
          { method: 'PATCH', body: JSON.stringify({ baremes }) },
        );
      }
      this.itemActif = data.evaluation;
      const idx = this.liste.findIndex(e => e.id === this.itemActif.id);
      if (idx !== -1) this.liste[idx] = this.itemActif;
      this._rendreSidebar();
      this._rendreExos();
      // v0.16.5 — état propre : snapshot des champs + reset drapeau barèmes.
      this._baremesModifies = false;
      this.modifie = false;          // reprend le snapshot + majToolbar
      // v0.16.2 — invalide le cache PDF/.tex après modification.
      this._texChargeId = null;
      if (!silencieuse) this._toast('Évaluation enregistrée.');
      return true;
    } catch (e) {
      console.error('Échec sauvegarde :', e);
      const msg = (e && e.message) || 'Échec de la sauvegarde.';
      this._toast(msg, true);
      return false;
    }
  }

  /**
   * v0.16.5 — Capture les CHAMPS STABLES de l'évaluation (hors barèmes, hors
   * structure). Sert de signature de snapshot pour le getter `modifie` de la
   * base. Retourne null si le DOM n'est pas prêt (pas d'item actif).
   */
  collecterFormulaire() {
    if (!this.itemActif) return null;
    const elT = document.getElementById('atl-eval-titre');
    const elM = document.getElementById('atl-eval-mode');
    const elA = document.getElementById('atl-eval-afficher-bareme');
    const elL = document.getElementById('atl-eval-langue-points');
    if (!elT || !elM || !elA || !elL) return null;
    const lang = elL.value.trim();
    return {
      titre: elT.value.trim(),
      mode_notation: elM.value,
      afficher_bareme_dans_exos: elA.checked ? 1 : 0,
      // Le backend attend un OBJET {points} ou '' (cf. fix v0.16.1).
      item_langue_francaise: lang === '' ? '' : { points: parseFloat(lang) },
    };
  }

  /**
   * v0.16.5 — Lit TOUS les barèmes saisis dans le DOM (inputs marqués
   * data-exo-id + data-bareme-champ), regroupés par exercice, pour le push
   * groupé à l'Enregistrer. Valeur vide → null (barème effacé).
   */
  _collecterBaremes() {
    const parExo = {};
    document.querySelectorAll('#atl-eval-form [data-exo-id][data-bareme-champ]')
      .forEach((el) => {
        const exoId = el.getAttribute('data-exo-id');
        const champ = el.getAttribute('data-bareme-champ');
        const v = String(el.value || '').trim();
        let val = v === '' ? null : parseFloat(v);
        if (typeof val === 'number' && isNaN(val)) val = null;
        if (!parExo[exoId]) parExo[exoId] = { exercice_id: exoId };
        parExo[exoId][champ] = val;
      });
    return Object.values(parExo);
  }

  async enregistrer() {
    // Conserve le nom historique appelé par window.atelEvalEnregistrer.
    await this.sauvegarder();
  }


  // ── Actions : exos ──────────────────────────────────────────────────────

  /**
   * Implémente `ajouterElement` du parent AtelierAssemblage pour le
   * cas type='exo'. Garde aussi une méthode `ajouterExo()` directe
   * (le pattern d'override est moins utile en l'absence de classe
   * sœur — Évaluation est l'unique consommateur pour l'instant).
   */
  async ajouterElement(type, _payload) {
    if (type === 'exo')      return this.ajouterExo();
    if (type === 'objectif') return this.ajouterObjectif();
    return super.ajouterElement(type, _payload);
  }

  /**
   * v0.16.5 — Garde appelée avant toute opération de STRUCTURE (ajout/retrait
   * d'exo ou d'objectif). Ces opérations rechargent l'évaluation depuis la
   * BDD et re-remplissent le formulaire → elles écraseraient une saisie de
   * champ non enregistrée. On bloque donc tant qu'il y a des modifications en
   * attente, en invitant à enregistrer d'abord.
   *
   * @returns {boolean} true si l'opération peut continuer.
   */
  _garderAvantStructure() {
    if (this.modifie) {
      this._toast(
        'Enregistrez vos modifications avant de modifier la structure '
        + '(exercices, objectifs).',
        true,
      );
      return false;
    }
    return true;
  }

  async ajouterExo() {
    if (!this.itemActif) return false;
    if (!this._garderAvantStructure()) return false;
    const selExo = document.getElementById('atl-eval-add-exo-id');
    if (!selExo || !selExo.value) return false;
    const exoId = selExo.value;
    try {
      await this._api(
        `/api/evaluations/${encodeURIComponent(this.itemActif.id)}/exos`,
        { method: 'POST', body: JSON.stringify({ exercice_id: exoId }) },
      );
      await this._chargerActif(this.itemActif.id);
      this._rendreVueComplete();
      return true;
    } catch (e) {
      console.error('Échec ajout exo :', e);
      this._toast('Échec de l\'ajout de l\'exercice.', true);
      return false;
    }
  }

  async retirerElement(type, id) {
    if (type === 'exo')      return this.retirerExo(id);
    if (type === 'objectif') return this.retirerObjectif(id);
    return super.retirerElement(type, id);
  }

  async retirerExo(exoId) {
    if (!this.itemActif) return false;
    if (!this._garderAvantStructure()) return false;
    if (!confirm('Retirer cet exercice de l\'évaluation ?')) return false;
    try {
      await this._api(
        `/api/evaluations/${encodeURIComponent(this.itemActif.id)}/exos/${encodeURIComponent(exoId)}`,
        { method: 'DELETE' },
      );
      await this._chargerActif(this.itemActif.id);
      this._rendreVueComplete();
      return true;
    } catch (e) {
      console.error('Échec retrait exo :', e);
      this._toast('Échec du retrait.', true);
      return false;
    }
  }

  // v0.16.5 (2b-2) — sauverBareme (PATCH immédiat par champ) SUPPRIMÉE. Les
  // barèmes entrent désormais dans le régime mixte : marqués modifiés via
  // _baremesModifies (oninput), puis poussés en un appel groupé à
  // l'Enregistrer (cf. sauvegarder + _collecterBaremes).

  async deplacerElement(type, id, delta) {
    if (type === 'exo') return this.deplacerExo(id, delta);
    return super.deplacerElement(type, id, delta);
  }

  async deplacerExo(exoId, delta) {
    if (!this.itemActif) return false;
    if (!this._garderAvantStructure()) return false;
    const idx = this.exos.findIndex(e => e.exercice_id === exoId);
    if (idx === -1) return false;
    const nouv = idx + delta;
    if (nouv < 0 || nouv >= this.exos.length) return false;
    const ordre = this.exos.map(e => e.exercice_id);
    [ordre[idx], ordre[nouv]] = [ordre[nouv], ordre[idx]];
    try {
      await this._api(
        `/api/evaluations/${encodeURIComponent(this.itemActif.id)}/exos/reordonner`,
        { method: 'POST', body: JSON.stringify({ ordre }) },
      );
      await this._chargerActif(this.itemActif.id);
      this._rendreExos();
      this._rendreCouverture();
      return true;
    } catch (e) {
      console.error('Échec réordonnancement :', e);
      this._toast('Échec du réordonnancement.', true);
      return false;
    }
  }


  // ── Actions : objectifs ─────────────────────────────────────────────────

  async ajouterObjectif() {
    if (!this.itemActif) return false;
    if (!this._garderAvantStructure()) return false;
    const sel = document.getElementById('atl-eval-add-obj-id');
    if (!sel || !sel.value) return false;
    const objId = sel.value;
    try {
      await this._api(
        `/api/evaluations/${encodeURIComponent(this.itemActif.id)}/objectifs`,
        { method: 'POST', body: JSON.stringify({ objectif_id: objId }) },
      );
      await this._chargerActif(this.itemActif.id);
      this._rendreVueComplete();
      return true;
    } catch (e) {
      console.error('Échec ajout objectif :', e);
      const msg = (e && e.message) || 'Échec de l\'ajout de l\'objectif.';
      this._toast(msg, true);
      return false;
    }
  }

  async retirerObjectif(objId) {
    if (!this.itemActif) return false;
    if (!this._garderAvantStructure()) return false;
    if (!confirm('Retirer cet objectif de la couverture déclarée ?')) return false;
    try {
      await this._api(
        `/api/evaluations/${encodeURIComponent(this.itemActif.id)}/objectifs/${encodeURIComponent(objId)}`,
        { method: 'DELETE' },
      );
      await this._chargerActif(this.itemActif.id);
      this._rendreVueComplete();
      return true;
    } catch (e) {
      console.error('Échec retrait objectif :', e);
      this._toast('Échec du retrait.', true);
      return false;
    }
  }


  // ── Actions : validation pédagogique (bascule) ──────────────────────────

  /**
   * Surcharge `basculerValidation()` d'AtelierEditeur. La parente
   * cible `/api/atomes/{typeApi}/{id}/etat` (mécanisme unifié des
   * atomes), mais l'évaluation a sa propre route avec gestion d'erreurs
   * pédagogiques structurées (raisons typées par code).
   */
  async basculerValidation() {
    if (!this.itemActif) return;

    // Masquer les erreurs précédentes
    this._afficherErreursValidation([]);

    const etat = this.itemActif.etat_code || 'en_cours';
    const path = etat === 'valide'
      ? `/api/evaluations/${encodeURIComponent(this.itemActif.id)}/devalider`
      : `/api/evaluations/${encodeURIComponent(this.itemActif.id)}/valider`;

    try {
      const data = await this._api(path, { method: 'POST' });
      this.itemActif = data.evaluation;
      const idx = this.liste.findIndex(e => e.id === this.itemActif.id);
      if (idx !== -1) this.liste[idx] = this.itemActif;
      this._rendreSidebar();
      this._majToolbar();
      this._toast(etat === 'valide' ? 'Évaluation dévalidée.' : 'Évaluation validée.');
    } catch (e) {
      // ATTENTION : ne PAS écraser itemActif en cas d'erreur de validation
      // (bug v0.13.5.2.4 : l'écran restait zombi). On garde l'éval active
      // telle quelle et on affiche juste les raisons.
      if (e && e.code === 'validation_pedagogique_echouee'
          && e.details && Array.isArray(e.details.raisons)) {
        this._afficherErreursValidation(e.details.raisons);
        this._toast('Validation impossible — voir les raisons affichées.', true);
      } else {
        console.error('Échec bascule validation :', e);
        const msg = (e && e.message) || 'Échec de la bascule.';
        this._toast(msg, true);
      }
    }
  }

  _afficherErreursValidation(raisons) {
    const el = document.getElementById('atl-eval-erreurs-validation');
    if (!el) return;
    if (!raisons || raisons.length === 0) {
      el.style.display = 'none';
      el.innerHTML = '';
      return;
    }
    let html = '<strong>Validation impossible :</strong>'
             + '<ul style="margin:6px 0 0 18px;padding:0">';
    raisons.forEach(r => {
      let msg;
      switch (r.code) {
        case 'aucun_exercice':
          msg = 'Aucun exercice attaché à l\'évaluation.';
          break;
        case 'bareme_manquant':
          msg = `Exercice ${this._labelExoParId(r.exercice_id)} : barème en points manquant (mode ${r.mode_notation}).`;
          break;
        case 'bareme_qcm_manquant':
          msg = `Exercice ${this._labelExoParId(r.exercice_id)} (QCM) : barème(s) manquant(s) : ${r.champs.join(', ')}.`;
          break;
        case 'bareme_negatif':
          msg = `Exercice ${this._labelExoParId(r.exercice_id)} : barème négatif (${r.champ}=${r.valeur}).`;
          break;
        case 'bareme_zero':
          msg = `Exercice ${this._labelExoParId(r.exercice_id)} : barème à 0 point (${r.champ}). Un exercice ajouté doit être noté — retirez-le ou attribuez-lui des points.`;
          break;
        default:
          msg = `Code ${r.code} : ${JSON.stringify(r)}`;
      }
      html += `<li>${this._esc(msg)}</li>`;
    });
    html += '</ul>';
    el.innerHTML = html;
    el.style.display = '';
  }


  // ── Onglet Rendu PDF — compilation + .tex brut ──────────────────────────
  //
  // v0.16.2 (étape 2a) — compilerRendu, _afficherErreurCompilation,
  // toggleTexBrut, _afficherTexBrut et scrollToLigneTex ont été SUPPRIMÉS :
  // c'étaient des copies de AtelierEditeur avec des IDs en dur. L'évaluation
  // en hérite désormais, après alignement des IDs du template sur la
  // convention this.$() (pdf-iframe, rendu-status, rendu-erreur,
  // rendu-loading, rendu-placeholder) et configuration de
  // `endpointRenduPdf: '/api/evaluations'` (le rendu hérité tape donc bien
  // /api/evaluations/<id>/rendu-pdf et /rendu-tex).
  //
  // Bénéfice : l'évaluation passe au viewer pdf.js (v0.16) sans code dédié.
  //
  // NB : le scroll vers une ligne fautive s'appelle `scrollVersLigneTex`
  // dans la base (le wrapper window.atelEvalScrollToLigneTex délègue à ce
  // nom — cf. bas de fichier). `voirLatex` est conservé ci-dessous car il
  // n'existe pas dans la base (ouvre la modale LaTeX commune).

  async voirLatex() {
    if (!this.itemActif) return;
    try {
      const r = await fetch(
        `/api/evaluations/${encodeURIComponent(this.itemActif.id)}/rendu-tex`,
        { method: 'GET' },
      );
      if (!r.ok) {
        const data = await r.json().catch(() => ({}));
        this._toast(data.error || `Erreur HTTP ${r.status}`, true);
        return;
      }
      const tex = await r.text();
      if (typeof window.atelierAfficherLatex === 'function') {
        window.atelierAfficherLatex('evaluation', tex);
      } else {
        // Fallback (atelier_commun.js non chargé)
        this._toast('Module commun manquant : LaTeX dans la console.', true);
        console.log(tex);
      }
    } catch (e) {
      console.error('Erreur GET rendu-tex :', e);
      this._toast('Erreur réseau lors de la récupération du LaTeX.', true);
    }
  }
}


// ─────────────────────────────────────────────────────────────────────────
// Instanciation unique et wrappers globaux pour compat HTML
// ─────────────────────────────────────────────────────────────────────────
//
// Les `onclick="atelEvalXxx()"` du index.html sont conservés : les
// wrappers ci-dessous délèguent à l'instance unique `ATELIER_EVALUATION`.
//
// Décision (cadrage v0.15 Q3) : on garde les wrappers parce que ça évite
// de toucher au HTML, qui pourra être refondu dans un chantier UI
// dédié plus tard.

window.ATELIER_EVALUATION = new AtelierEvaluation();

// Init de l'atelier (appelé par atelInvoquerInit dans app.js)
window.atelEvalInit = function() {
  return window.ATELIER_EVALUATION.init();
};

// Filtres et navigation sidebar
window.atelEvalFiltrerEtat = function(btn, etat) {
  return window.ATELIER_EVALUATION.filtrerEtat(btn, etat);
};
window.atelEvalSelectionner = function(evalId) {
  return window.ATELIER_EVALUATION.selectionner(evalId);
};
window.atelEvalNouveau = function() {
  return window.ATELIER_EVALUATION.nouvelItem();
};
window.atelEvalSupprimer = function() {
  return window.ATELIER_EVALUATION.supprimer();
};

// Sous-onglets
window.atelEvalTab = function(nom) {
  return window.ATELIER_EVALUATION.basculerOnglet(nom);
};

// Workflow d'édition
window.atelEvalMarquerModifie = function() {
  return window.ATELIER_EVALUATION.marquerModifie();
};
window.atelEvalEnregistrer = function() {
  return window.ATELIER_EVALUATION.enregistrer();
};
window.atelEvalMajLangueIndic = function() {
  return window.ATELIER_EVALUATION.majLangueIndic();
};

// Actions exos
window.atelEvalFiltrerExosAjoutables = function() {
  return window.ATELIER_EVALUATION.filtrerExosAjoutables();
};
window.atelEvalAjouterExo = function() {
  return window.ATELIER_EVALUATION.ajouterExo();
};
window.atelEvalRetirerExo = function(exoId) {
  return window.ATELIER_EVALUATION.retirerExo(exoId);
};
// v0.16.5 — window.atelEvalSauverBareme supprimé (barèmes en régime mixte).
window.atelEvalDeplacerExo = function(exoId, delta) {
  return window.ATELIER_EVALUATION.deplacerExo(exoId, delta);
};

// Actions objectifs
window.atelEvalAjouterObjectif = function() {
  return window.ATELIER_EVALUATION.ajouterObjectif();
};
window.atelEvalRetirerObjectif = function(objId) {
  return window.ATELIER_EVALUATION.retirerObjectif(objId);
};

// Validation pédagogique
window.atelEvalBasculerValidation = function() {
  return window.ATELIER_EVALUATION.basculerValidation();
};

// Rendu PDF
window.atelEvalCompilerRendu = function() {
  return window.ATELIER_EVALUATION.compilerRendu();
};
window.atelEvalToggleTexBrut = function() {
  return window.ATELIER_EVALUATION.toggleTexBrut();
};
window.atelEvalScrollToLigneTex = function(ligne) {
  // v0.16.2 — délègue à la méthode héritée d'AtelierEditeur, qui se nomme
  // scrollVersLigneTex (l'ancienne copie locale scrollToLigneTex a été
  // supprimée). Le wrapper garde son nom historique pour ne pas toucher
  // au HTML.
  return window.ATELIER_EVALUATION.scrollVersLigneTex(ligne);
};
window.atelEvalVoirLatex = function() {
  return window.ATELIER_EVALUATION.voirLatex();
};
