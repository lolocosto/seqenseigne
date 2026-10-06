/**
 * static/atelier_progression.js — v0.19.1.0
 *
 * Atelier d'assemblage d'une PROGRESSION annuelle.
 *
 * Refonte v0.19.1 : la progression devient un atelier d'assemblage, aligné
 * sur l'atelier Séquence-niveau (AtelierSeqnivAssemblage). Comme lui :
 *   - estPluriel = false : une seule progression à la fois, déterminée par
 *     les 4 sélecteurs du bandeau (année / établissement / niveau /
 *     référentiel support), et non par une liste en barre latérale.
 *   - persistanceImmediate = true : les opérations de structure (poser /
 *     retirer / dater un créneau) sont persistées au vol via les routes
 *     créneau existantes. Pas de bouton « Enregistrer » global. Quand des
 *     champs de saisie bufferisés apparaîtront (v0.19.1.1+), on réintroduira
 *     un bouton local comme dans le seqniv (régime mixte).
 *
 * Correspondances conceptuelles (cf. cadrage v0.19.1) :
 *   assemblage de séquence          ↔  construction de progression
 *   parties de séquence (sidebar)   ↔  parties du référentiel (sidebar)
 *   objectifs posés dans une partie ↔  créneaux posés sur le calendrier
 *   méthodes du niveau (source)     ↔  parties du référentiel (source)
 *
 * v0.19.1.0 (cette livraison) : ossature OO, bandeau 4 sélecteurs, barre
 * latérale listant TOUTES les parties du référentiel (avec badges des
 * semaines où elles sont placées), calendrier dans le panneau principal,
 * sélection / édition / suppression de créneau. AJOUT par CLIC sur une
 * partie → créneau SANS date (l'enseignant date ensuite). Le drag-and-drop
 * parties → calendrier et le changement de référentiel (avec purge) arrivent
 * en v0.19.1.1.
 *
 * Hiérarchie :
 *   Atelier → AtelierEditeur → AtelierAssemblage → AtelierProgression
 *
 * Les helpers de calendrier purs (dates, vacances, fériés) restent des
 * fonctions globales d'app.js (_lundisEntre, _bornesAnneeScolaire,
 * _vacancesDeLaSemaine, _feriesDeLaSemaine, _dateCourte, _jourSemaine,
 * _dateToISO, MOIS_FR) : la classe les consomme.
 */

(function () {
  'use strict';

  class AtelierProgression extends AtelierAssemblage {
    constructor() {
      super({
        id:                   'prog',
        prefixe:              'prog',
        estPluriel:           false,
        persistanceImmediate: true,
        endpointBase:         '/api/progression',
        labelExistant:        'Progression',
        labelNouveau:         'Progression',
      });

      // ── État d'instance ──────────────────────────────────────────────────
      this.data        = null;   // progression courante (ou null)
      this.parties     = [];     // parties du référentiel support (sidebar)
      this._modeSeances = 'par_objectif'; // mode de séances du référentiel
      this._seancesParSerie = []; // matrice séances (mode par_serie)
      this.creneauSel  = null;   // id du créneau sélectionné
      this._chargement = false;

      // Données des sélecteurs (chargées une fois par progInit).
      this._annees      = [];    // [{code, libelle, archive}]
      this._anneeDefaut = '';
      this._etabs       = [];    // [{id, nom, academie, etat, ...}]
      this._refsCache   = {};    // { niveau: [refs verrouille/utilise] }

      // Cache calendrier (vacances + fériés) — clé année+académie.
      this._calAnnee    = null;
      this._calAcademie = null;
      this._calVacances = null;
      this._calFeries   = {};
      this._calIndispos = [];

      // v0.21.5 — Vue « réalisée » par classe.
      this._vueClasseId = '';    // '' = vue commune prévue ; sinon id de classe
      this._decalages   = [];    // décalages de la classe en vue
      this._classesNiveau = [];  // classes du niveau/année (pour le sélecteur)
    }

    // ── Helpers DOM ──────────────────────────────────────────────────────────

    _el(id) { return document.getElementById(id); }
    _esc(s) { return (window.escapeHtml ? window.escapeHtml(s) : String(s == null ? '' : s)); }

    _status(msg, err) {
      const el = this._el('prog-status');
      if (!el) return;
      el.textContent = msg || '';
      el.style.color = err ? 'var(--danger)' : 'var(--success)';
      if (msg) {
        setTimeout(() => { if (el.textContent === msg) el.textContent = ''; },
                   err ? 6000 : 2500);
      }
    }

    _sel(id) { const e = this._el(id); return e ? e.value : ''; }

    // ── Cycle de vie : init des sélecteurs ───────────────────────────────────

    async init() {
      // Charge années + établissements (une fois), peuple les sélecteurs,
      // puis tente de charger la progression du quadruplet courant.
      const [annees, etabsResp] = await Promise.all([
        api('/api/annees-scolaires').catch(
          () => ({annee_courante: '', annees_scolaires: []})),
        api('/api/etablissements').catch(() => ({etablissements: []})),
      ]);
      this._annees      = annees.annees_scolaires || [];
      this._anneeDefaut = annees.annee_courante || '';
      this._etabs       = etabsResp.etablissements || [];

      this._peuplerSelectAnnees();
      this._peuplerSelectEtabs();
      await this._peuplerSelectReferentiels();
      await this.rafraichir();
    }

    _peuplerSelectAnnees() {
      const sel = this._el('prog-sel-annee');
      if (!sel) return;
      const actives   = this._annees.filter(a => !a.archive);
      const archivees = this._annees.filter(a =>  a.archive);
      let html = actives.map(a => {
        const marque = (a.code === this._anneeDefaut) ? ' (courante)' : '';
        return `<option value="${a.code}">${this._esc(a.libelle)}${marque}</option>`;
      }).join('');
      if (archivees.length) {
        html += `<optgroup label="— Archivées —">`
              + archivees.map(a =>
                  `<option value="${a.code}">${this._esc(a.libelle)}</option>`).join('')
              + `</optgroup>`;
      }
      sel.innerHTML = html || '<option value="">— Aucune année —</option>';
      if (this._anneeDefaut) sel.value = this._anneeDefaut;
    }

    _peuplerSelectEtabs() {
      const sel = this._el('prog-sel-etab');
      if (!sel) return;
      if (!this._etabs.length) {
        sel.innerHTML = '<option value="">— Aucun établissement —</option>';
        return;
      }
      sel.innerHTML = this._etabs.map(e =>
        `<option value="${e.id}">${this._esc(e.nom)}</option>`).join('');
    }

    /**
     * Peuple le 4e sélecteur (référentiel support) : uniquement les
     * référentiels du niveau courant en état `verrouille` ou `utilise`
     * (D2). Cache par niveau.
     */
    async _peuplerSelectReferentiels() {
      const sel = this._el('prog-sel-ref');
      if (!sel) return;
      const niveau = this._sel('prog-sel-niveau');
      let refs = this._refsCache[niveau];
      if (!refs) {
        try {
          const resp = await api(
            `/api/referentiels?niveau=${encodeURIComponent(niveau)}`
            + `&etats=verrouille,utilise&externes=1&type=principal`);   // v0.48.2 : + externes ; v0.48.4 : principal seulement
          refs = resp.referentiels || [];
          this._refsCache[niveau] = refs;
        } catch (e) { refs = []; }
      }
      if (!refs.length) {
        sel.innerHTML = '<option value="">— Aucun référentiel exploitable —</option>';
        return;
      }
      sel.innerHTML = refs.map(r => {
        const lib = r.description ? ` — ${this._esc(r.description)}` : '';
        const etat = r.etat === 'utilise' ? ' (utilisé)' : '';
        // v0.48.2 — Référentiel principal externe : nom calculé + mention.
        const nom = r.source === 'externe' ? `${this._esc(r.nom || r.id)} (externe)` : this._esc(r.id);
        return `<option value="${r.id}">${nom}${lib}${etat}</option>`;
      }).join('');
    }

    // ── Handlers des sélecteurs ──────────────────────────────────────────────

    async onNiveauChange() {
      // Le niveau change → recharger la liste des référentiels exploitables.
      await this._peuplerSelectReferentiels();
      await this.rafraichir();
    }

    async onSelecteurChange() {
      // Année ou établissement change → recharger la progression du quadruplet.
      await this.rafraichir();
    }

    async onReferentielChange() {
      // v0.22.1 — Changement de référentiel support d'une progression existante.
      // Si une progression est chargée (en_cours) et que le référentiel choisi
      // diffère du sien, on propose de basculer (avec purge des créneaux, après
      // confirmation). Sinon, comportement d'origine : (re)charger / créer.
      const selRef = this._el('prog-sel-ref');
      const nouveauRef = selRef ? selRef.value : '';
      if (this.data && this.data.id && nouveauRef
          && this.data.referentiel_id
          && nouveauRef !== this.data.referentiel_id) {
        if (this.data.etat !== 'en_cours') {
          this._status('Le référentiel ne peut être changé que sur une '
            + 'progression « en cours ».', true);
          // Remettre le sélecteur sur le référentiel actuel.
          selRef.value = this.data.referentiel_id;
          return;
        }
        const nbCr = (this.data.creneaux || []).length;
        const detailCr = nbCr ? ' (' + nbCr + ' créneau(x))' : '';
        const ok = window.confirm(
          'Attention : changer le référentiel support va effacer TOUS les '
          + 'créneaux existants de cette progression' + detailCr + '. '
          + 'Cette action est irréversible.\n\n'
          + 'Confirmez-vous le changement de référentiel ?');
        if (!ok) {
          selRef.value = this.data.referentiel_id;
          return;
        }
        try {
          const res = await api(
            `/api/progression_id/${encodeURIComponent(this.data.id)}/referentiel`,
            { method: 'POST',
              body: JSON.stringify({ referentiel_id: nouveauRef }) });
          if (res && res.error) {
            this._status('Erreur : ' + res.error, true);
            selRef.value = this.data.referentiel_id;
            return;
          }
          this.data = res;
          this._status('Référentiel changé — créneaux purgés.');
          await this._apresChargement();
        } catch (e) {
          this._status('Erreur : ' + (e.message || e), true);
          selRef.value = this.data.referentiel_id;
        }
        return;
      }
      await this.rafraichir();
    }

    /**
     * Cœur du cycle de vie (équivalent de `rafraichir` du seqniv) : lit les
     * 4 sélecteurs, charge la progression du triplet si elle existe, sinon
     * la crée à partir du référentiel choisi, puis rend l'UI.
     */
    async rafraichir() {
      if (this._chargement) return;
      this._chargement = true;
      try {
        const annee  = this._sel('prog-sel-annee');
        const etabId = this._sel('prog-sel-etab');
        const niveau = this._sel('prog-sel-niveau');
        const refId  = this._sel('prog-sel-ref');

        if (!annee || !etabId || !niveau) {
          this._afficherVide('Choisir une année, un établissement et un niveau.');
          return;
        }

        // Chercher une progression existante pour le triplet.
        let resp;
        try {
          resp = await api(
            `/api/progression/${encodeURIComponent(niveau)}/rechercher`
            + `?annee=${encodeURIComponent(annee)}`
            + `&etablissement_id=${encodeURIComponent(etabId)}`);
        } catch (e) {
          this._afficherVide('Erreur de communication avec le serveur.');
          return;
        }

        if (resp && resp.error) {
          this._afficherVide(resp.code === 'doublon_base'
            ? 'Incohérence en base : plusieurs progressions pour ce triplet.'
            : resp.error);
          return;
        }

        if (resp.trouve) {
          this.data = resp.progression;
          // Aligner le sélecteur de référentiel sur celui de la progression.
          if (this.data.referentiel_id) {
            const selRef = this._el('prog-sel-ref');
            if (selRef && selRef.value !== this.data.referentiel_id) {
              // Si le référentiel de la progression n'est pas dans la liste
              // (cas limite), on l'ajoute pour le rendre visible.
              if (![...selRef.options].some(o => o.value === this.data.referentiel_id)) {
                const opt = document.createElement('option');
                opt.value = this.data.referentiel_id;
                opt.textContent = this.data.referentiel_id + ' (lié)';
                selRef.appendChild(opt);
              }
              selRef.value = this.data.referentiel_id;
            }
          }
          await this._apresChargement();
        } else {
          // Pas de progression : si un référentiel est choisi, on crée (D6).
          if (!refId) {
            this._afficherVide(
              'Aucune progression. Choisir un référentiel support pour la créer.');
            return;
          }
          await this._creerProgression(niveau, annee, etabId, refId);
        }
      } finally {
        this._chargement = false;
      }
    }

    async _creerProgression(niveau, annee, etabId, refId) {
      const etab = this._etabs.find(e => e.id === etabId);
      const body = {
        annee, etablissement: etab ? etab.nom : '',
        etablissement_id: etabId, referentiel_id: refId, creneaux: [],
      };
      try {
        const resp = await api(`/api/progression/${encodeURIComponent(niveau)}`, {
          method: 'POST', body: JSON.stringify(body),
        });
        if (resp && resp.error) { this._status('Erreur : ' + resp.error, true); return; }
        this._status('Progression créée.');
        // Recharger pour récupérer l'id + les données complètes.
        await this.rafraichir();
      } catch (e) {
        this._status('Erreur de création : ' + (e.message || e), true);
      }
    }

    // ── Rendu ────────────────────────────────────────────────────────────────

    _afficherVide(msg) {
      this.data = null;
      this.parties = [];
      this.creneauSel = null;
      const empty = this._el('prog-empty');
      const content = this._el('prog-content');
      if (empty) {
        empty.style.display = '';
        const p = this._el('prog-empty-msg');
        if (p) p.textContent = msg || 'Choisir une progression.';
      }
      if (content) content.style.display = 'none';
      const badge = this._el('prog-etat-badge');
      if (badge) badge.style.display = 'none';
      this._renderSidebar();
      this._renderBoutonsEtat(null);
      /* v0.32.12 — panneau « Livrets distribués » retiré (doublon Conception) */
    }

    async _apresChargement() {
      this._el('prog-empty').style.display = 'none';
      this._el('prog-content').style.display = '';
      this.creneauSel = null;
      this._el('prog-creneau-form').style.display = 'none';
      if(typeof progSyncPoignee==='function')progSyncPoignee();
      await this._chargerParties();
      this._renderSidebar();
      this._renderBadgeEtat();
      this._renderBoutonsEtat(this.data.etat);
      // v0.21.5 — Vue par classe : reset sur « commune prévue » au chargement
      // d'une progression, peupler le sélecteur de classe, MAJ bandeau.
      this._vueClasseId = '';
      this._decalages = [];
      await this._peuplerSelectClasses();
      this._majBandeauVue();
      this._renderDecalages();
      await this._renderCalendrier();
      /* v0.32.12 — panneau « Livrets distribués » retiré (doublon Conception) */
    }

    /** Charge les parties du référentiel support (barre latérale). */
    async _chargerParties() {
      const refId = this.data && this.data.referentiel_id;
      if (!refId) {
        this.parties = []; this._modeSeances = 'par_objectif';
        this._seancesParSerie = []; return;
      }
      try {
        const resp = await api(
          `/api/referentiels/${encodeURIComponent(refId)}/parties`);
        this.parties = (resp && resp.parties) || [];
        this._modeSeances = (resp && resp.ref && resp.ref.mode_seances)
          || 'par_objectif';
        this._seancesParSerie = (resp && resp.seances_par_serie) || [];
      } catch (e) {
        this.parties = []; this._modeSeances = 'par_objectif';
        this._seancesParSerie = [];
      }
    }

    /**
     * v0.19.1.4 — Construit les deux matrices de séances (cibles TB et S)
     * pour une (séquence, partie) en mode 'par_serie'. Retourne
     * { TB: {R,F,A,E}, S: {R,F,A,E} } avec nb_seances (ou null si absent).
     */
    _matricesSeances(seqCode, partieNumero) {
      const out = { TB: {}, S: {} };
      for (const r of (this._seancesParSerie || [])) {
        if (r.seq_code === seqCode && r.partie_numero === partieNumero) {
          if (out[r.niveau_cible]) out[r.niveau_cible][r.serie] = r.nb_seances;
        }
      }
      return out;
    }

    /**
     * Pour chaque partie, retrouve les numéros de semaine où elle est placée
     * (un créneau couvre une partie d'une séquence). Renvoie une Map
     * `${seq}|${partie}` → [n° semaine, ...].
     */
    _semainesParPartie() {
      const map = {};
      if (!this.data) return map;
      const annee = this.data.annee || '';
      const {debut, fin} = window._bornesAnneeScolaire(annee);
      const lundis = window._lundisEntre(debut, fin);
      for (const c of (this.data.creneaux || [])) {
        // Numéro de partie (numérique) : un créneau couvre une partie d'une
        // séquence. On indexe par partie_debut (== partie_fin), retombant sur
        // 1 si absent. La clé doit matcher `${p.seq_code}|${p.partie_numero}`
        // de la barre latérale.
        const pnum = (c.partie_debut != null) ? c.partie_debut
                   : (c.partie_fin != null) ? c.partie_fin : 1;
        const cle = `${c.sequence}|${pnum}`;
        // Tout créneau (même non daté) marque la partie comme « placée » :
        // on crée l'entrée. Le numéro de semaine n'est ajouté que si daté.
        if (!map[cle]) map[cle] = [];
        if (c.date_debut) {
          const idx = lundis.findIndex(l => {
            const vendredi = window._jourSemaine(l, 4);
            return c.date_debut <= vendredi && (c.date_fin || c.date_debut) >= l;
          });
          if (idx >= 0) map[cle].push(idx + 1);
        }
      }
      for (const k in map) map[k] = [...new Set(map[k])].sort((a, b) => a - b);
      return map;
    }

    _renderSidebar() {
      const body = this._el('prog-sidebar-body');
      const hint = this._el('prog-sidebar-hint');
      if (!body) return;
      if (!this.data) {
        body.innerHTML = '<div style="padding:12px;font-size:12px;color:var(--text-muted)">'
          + 'Sélectionnez une progression.</div>';
        if (hint) hint.textContent = '';
        return;
      }
      if (!this.parties.length) {
        body.innerHTML = '<div style="padding:12px;font-size:12px;color:var(--text-muted)">'
          + 'Le référentiel support ne contient aucune partie de séquence.</div>';
        if (hint) hint.textContent = '';
        return;
      }
      const semaines = this._semainesParPartie();
      if (hint) {
        const placees = Object.keys(semaines).length;
        hint.textContent = `${placees}/${this.parties.length} placées`;
      }
      body.innerHTML = this.parties.map(p => {
        const cle = `${p.seq_code}|${p.partie_numero}`;
        const placee = Object.prototype.hasOwnProperty.call(semaines, cle);
        const sems = semaines[cle] || [];
        // Code séquence + n° partie en identifiant monospace compact.
        const id = `${this._esc(p.seq_code)}·P${p.partie_numero}`;
        const meta = `${p.nb_objectifs} obj.`
          + (p.nb_seances_prevues ? ` · ${p.nb_seances_prevues} séance(s)` : '');
        // Pastille d'état (1re ligne, à droite) : alignée sur .atl-list-item-etat
        let etatPill = '';
        if (placee && sems.length) {
          etatPill = `<span class="atl-list-item-etat atome-etat--valide">placée</span>`;
        } else if (placee) {
          etatPill = `<span class="atl-list-item-etat atome-etat--en_cours">à dater</span>`;
        }
        // Badges des semaines (2e ligne), style .atl-item-meta.
        const badges = sems.length
          ? `<div class="prog-partie-badges">`
            + sems.map(s => `<span class="atl-item-meta">sem. ${s}</span>`).join('')
            + `</div>`
          : '';
        return `<div class="atl-item${placee ? ' active' : ''}"
                     onclick="ATELIER_PROGRESSION.cliquerPartieSidebar('${this._esc(p.seq_code)}', ${p.partie_numero})">
          <span class="atl-item-id atl-item-id--compact">${id}</span>
          <span class="atl-item-titre">${this._esc(p.seq_nom)}</span>
          ${etatPill}
          <span class="atl-item-meta">${meta}</span>
          ${badges}
        </div>`;
      }).join('');
    }

    // v0.22.0.2 — Clic sur une partie dans la barre latérale.
    // Si un créneau existe déjà pour cette partie (placée, même « à dater »),
    // on le SÉLECTIONNE (ouvre le détail pour le dater / éditer / retirer),
    // sinon on le crée (poserPartie). Corrige le piège où un créneau « à
    // dater » (sans date, absent du calendrier) restait inaccessible.
    cliquerPartieSidebar(seqCode, partieNumero) {
      const c = (this.data && this.data.creneaux || []).find(x => {
        const pnum = (x.partie_debut != null) ? x.partie_debut
                   : (x.partie_fin != null) ? x.partie_fin : 1;
        return x.sequence === seqCode && pnum === partieNumero;
      });
      if (c) {
        this.selectionnerCreneau(c.id);
        // Faire défiler jusqu'au panneau de détail pour le voir.
        const form = this._el('prog-creneau-form');
        if (form && form.scrollIntoView) {
          form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
        return;
      }
      this.poserPartie(seqCode, partieNumero);
    }

    _renderBadgeEtat() {
      const badge = this._el('prog-etat-badge');
      if (!badge) return;
      if (!this.data) { badge.style.display = 'none'; return; }
      const etat = this.data.etat || 'en_cours';
      const conf = {
        'en_cours':   '✏️ En cours',
        'valide':     '✓ Validée',
        'verrouille': '🔒 Verrouillée',
        'utilise':    '🔒 Verrouillée',
      }[etat] || etat;
      badge.style.display = '';
      badge.textContent = conf;
      badge.className = 'atome-etat-badge prog-etat-' + etat;
    }

    _renderBoutonsEtat(etat) {
      const btnV = this._el('prog-btn-valider');
      const btnE = this._el('prog-btn-encours');
      if (!btnV || !btnE) return;
      const academieAbsente = this.data && !this.data.etab_academie;
      if (!etat || academieAbsente) {
        btnV.style.display = 'none';
        btnE.style.display = 'none';
        return;
      }
      if (etat === 'valide') {
        btnV.style.display = 'none'; btnE.style.display = '';
      } else if (etat === 'en_cours') {
        btnV.style.display = ''; btnE.style.display = 'none';
      } else { // verrouille / utilise
        btnV.style.display = 'none'; btnE.style.display = 'none';
      }
    }

    // ── Calendrier ───────────────────────────────────────────────────────────

    async _chargerCalendrierSiBesoin() {
      if (!this.data) return;
      const annee    = this.data.annee;
      const academie = this.data.etab_academie || '';
      if (this._calAnnee === annee && this._calAcademie === academie
          && this._calVacances !== null) return;
      this._calAnnee = annee;
      this._calAcademie = academie;
      this._calVacances = [];
      this._calFeries = {};
      this._calIndispos = [];
      try {
        const r = await api(
          `/api/calendrier/jours-feries?annee_scolaire=${encodeURIComponent(annee)}`);
        this._calFeries = r.feries || {};
      } catch (e) { /* fériés indisponibles */ }
      if (academie) {
        try {
          const r = await api(
            `/api/calendrier/vacances?annee=${encodeURIComponent(annee)}`
            + `&academie=${encodeURIComponent(academie)}`);
          this._calVacances = r.vacances || [];
        } catch (e) { /* vacances indisponibles */ }
      }
      // v0.21.4 — Indisponibilités (affichées sur le calendrier). Toutes celles
      // de l'année/établissement (portée « moi » ou « classes »).
      const etabId = this.data.etab_id || this._sel('prog-sel-etab');
      if (etabId) {
        try {
          const r = await api(
            `/api/indisponibilites?annee=${encodeURIComponent(annee)}`
            + `&etablissement_id=${encodeURIComponent(etabId)}`);
          this._calIndispos = r.indisponibilites || [];
        } catch (e) { /* indispos indisponibles */ }
      }
    }

    // ─────────────────────────────────────────────────────────────────────
    // v0.21.5 — Vue « progression annuelle réalisée » par classe.
    // ─────────────────────────────────────────────────────────────────────

    async _peuplerSelectClasses() {
      const sel = this._el('prog-vue-classe');
      if (!sel || !this.data) return;
      const annee = this.data.annee;
      const niveau = this.data.niveau;
      try {
        const r = await api('/api/classes?annee=' + encodeURIComponent(annee));
        const classes = (r && (r.classes || r)) || [];
        this._classesNiveau = classes.filter(c => c.niveau === niveau);
      } catch (e) { this._classesNiveau = []; }
      const cour = this._vueClasseId;
      sel.innerHTML = '<option value="">— Aucune (commune prévue) —</option>'
        + this._classesNiveau.map(c =>
          `<option value="${this._esc(c.id)}"${c.id === cour ? ' selected' : ''}>`
          + `${this._esc(c.nom)}</option>`).join('');
      sel.value = cour;
    }

    async onVueClasseChange() {
      const sel = this._el('prog-vue-classe');
      this._vueClasseId = sel ? sel.value : '';
      await this._chargerDecalages();
      this._majBandeauVue();
      await this._renderCalendrier();
      this._renderDecalages();
    }

    async _chargerDecalages() {
      this._decalages = [];
      this._realise = null;           // v0.27.3 — données décalées du serveur
      if (!this._vueClasseId || !this.data) return;
      try {
        const r = await api('/api/classes/' + this._vueClasseId
          + '/decalages-progression?annee=' + encodeURIComponent(this.data.annee));
        this._decalages = (r && r.decalages) || [];
      } catch (e) { this._decalages = []; }
      // v0.27.3 — Le calcul métier (créneaux décalés + semaines neutralisées)
      // est fait CÔTÉ SERVEUR. Le client ne fait que l'afficher.
      try {
        this._realise = await api('/api/classes/' + this._vueClasseId
          + '/progression-realisee?annee=' + encodeURIComponent(this.data.annee));
        this._neutrSet = new Set(
          (this._realise.semaines_neutralisees || []).map(s => s.lundi));
        this._neutrMotifs = {};
        (this._realise.semaines_neutralisees || []).forEach(s => {
          this._neutrMotifs[s.lundi] = s.motif;
        });
      } catch (e) {
        this._realise = null; this._neutrSet = new Set(); this._neutrMotifs = {};
      }
    }

    _majBandeauVue() {
      const titre = this._el('prog-vue-titre');
      if (titre) {
        titre.textContent = this._vueClasseId
          ? 'Progression annuelle réalisée'
          : 'Progression annuelle commune prévue';
      }
      const dec = this._el('prog-decalages');
      if (dec) dec.style.display = this._vueClasseId ? '' : 'none';
    }

    _renderDecalages() {
      const zone = this._el('prog-decalages');
      if (!zone) return;
      if (!this._vueClasseId) { zone.innerHTML = ''; return; }
      const _jjmm = iso => {
        const m = String(iso || '').match(/^(\d{4})-(\d{2})-(\d{2})/);
        return m ? `${m[3]}/${m[2]}/${m[1]}` : (iso || '');
      };
      const lignes = this._decalages.map(d => `
        <span style="display:inline-flex;align-items:center;gap:4px;background:#fff;
          border:1px solid #d1c4e9;border-radius:4px;padding:2px 6px;font-size:12px;
          margin:2px 4px 2px 0">
          À partir du ${_jjmm(d.a_partir_de)} : +${d.nb_semaines} sem.
          ${d.motif ? '· ' + this._esc(d.motif) : ''}
          <button class="btn-sm" style="color:var(--danger);padding:0 4px"
            onclick="ATELIER_PROGRESSION.supprimerDecalage('${this._esc(d.id)}')"
            title="Supprimer ce décalage" aria-label="Supprimer ce décalage">×</button>
        </span>`).join('');
      zone.innerHTML = `
        <div style="font-size:12px;font-weight:600;margin-bottom:4px">Décalages de la classe</div>
        <div>${lignes || '<span style="font-size:12px;color:#999">Aucun décalage. '
          + 'Utilisez le bouton « décaler » sur une indisponibilité du calendrier.</span>'}</div>`;
    }

    async supprimerDecalage(did) {
      if (!confirm('Supprimer ce décalage ?')) return;
      try {
        const r = await fetch('/api/decalages-progression/' + did, { method: 'DELETE' });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        await this._chargerDecalages();
        this._renderDecalages();
        await this._renderCalendrier();
      } catch (e) { this._status('Erreur : ' + e.message, true); }
    }

    async decalerDepuisIndispo(indispoId, aPartirDe, nbSemaines) {
      if (!this._vueClasseId) {
        this._status('Sélectionnez d\'abord une classe (vue réalisée).', true);
        return;
      }
      const n = parseInt(nbSemaines, 10) || 1;
      try {
        const r = await fetch('/api/classes/' + this._vueClasseId
          + '/decalages-progression', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            annee: this.data.annee, a_partir_de: aPartirDe, nb_semaines: n,
            motif: 'Indisponibilité', indispo_id: indispoId,
          }),
        });
        const d = await r.json();
        if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status));
        await this._chargerDecalages();
        this._renderDecalages();
        await this._renderCalendrier();
        this._status('Décalage créé.');
      } catch (e) { this._status('Erreur : ' + e.message, true); }
    }

    // v0.27.4 — Le calcul du nombre de semaines touchées par une
    // indisponibilité est désormais côté serveur (services/indisponibilites.
    // semaines_touchees) et exposé via l'API (ind.semaines_touchees).

    async _renderCalendrier() {
      const root = this._el('prog-calendrier');
      if (!root) return;
      if (!this.data) { root.innerHTML = ''; return; }

      await this._chargerCalendrierSiBesoin();

      const academieAbsente = !this.data.etab_academie;
      const alerte = this._el('prog-alerte-etab');
      if (alerte) alerte.style.display = academieAbsente ? '' : 'none';
      if (academieAbsente) {
        root.innerHTML = '<div style="padding:16px;font-size:12px;color:var(--text-muted);'
          + 'text-align:center">Calendrier indisponible sans académie.</div>';
        return;
      }

      const {debut, fin} = window._bornesAnneeScolaire(this.data.annee);
      const lundis = window._lundisEntre(debut, fin);
      const lignes = lundis.map((l, i) => this._ligneSemaine(l, i + 1)).join('');

      root.innerHTML = `
        <div class="cal-legend" style="display:flex;gap:10px;font-size:10px;
             padding:4px 8px;color:var(--text-muted);flex-wrap:wrap">
          <span><span class="cal-dot" style="background:#fce8e6"></span>Vacances</span>
          <span><span class="cal-dot" style="background:#fef7e0"></span>Férié</span>
          <span><span class="cal-dot" style="background:#ede7f6"></span>Indisponibilité</span>
          <span><span class="cal-dot" style="background:#e8f0fe"></span>Créneau</span>
        </div>
        <div class="cal-grid">${lignes}</div>`;
    }

    _creneauxDeLaSemaine(lundiISO) {
      if (!this.data) return [];
      // v0.19.1.6 — Un créneau qui enjambe une période de vacances ne s'affiche
      // pas sur les semaines ENTIÈREMENT en vacances.
      if (this._semaineEntierementEnVacances(lundiISO)) return [];
      // v0.27.2 — Une semaine NEUTRALISÉE par un décalage est transparente
      // (comme les vacances) : les créneaux l'enjambent sans s'y afficher.
      if (this._semaineNeutralisee(lundiISO)) return [];
      const vendrediIso = window._jourSemaine(lundiISO, 4);
      return this._creneauxAffichage().filter(c => {
        if (!c.date_debut || !c.date_fin) return false;
        return c.date_debut <= vendrediIso && c.date_fin >= lundiISO;
      });
    }

    // v0.27.3 — Données calculées par le serveur (aucun recalcul JS).
    _semaineNeutralisee(lundiISO) {
      return !!(this._neutrSet && this._neutrSet.has(lundiISO));
    }

    _motifNeutralisation(lundiISO) {
      return (this._neutrMotifs && this._neutrMotifs[lundiISO]) || 'Décalage';
    }

    // v0.21.5 — Créneaux tels qu'affichés : décalés si une classe est en vue
    // (« progression réalisée »), sinon les créneaux communs (« prévue »).
    _creneauxAffichage() {
      // v0.27.3 — Créneaux décalés calculés CÔTÉ SERVEUR. En vue classe, on
      // utilise ceux-là ; sinon les créneaux communs (progression prévue).
      if (this._vueClasseId && this._realise && this._realise.creneaux) {
        return this._realise.creneaux;
      }
      return (this.data && this.data.creneaux) || [];
    }

    /** Vrai si le jour ISO tombe dans une période de vacances (fin exclusive). */
    _jourEnVacances(iso) {
      for (const v of (this._calVacances || [])) {
        if (!v.start_date || !v.end_date) continue;
        if (v.start_date <= iso && iso < v.end_date) return true;
      }
      return false;
    }

    /**
     * Vrai si TOUS les jours de classe de la semaine (lundi→vendredi) sont en
     * vacances. Les jours fériés ne sont PAS considérés comme des vacances :
     * une semaine travaillée avec un férié reste une semaine de classe.
     */
    _semaineEntierementEnVacances(lundiISO) {
      for (let i = 0; i < 5; i++) {
        const iso = window._jourSemaine(lundiISO, i);
        if (!this._jourEnVacances(iso)) return false;
      }
      return true;
    }

    _vacancesDeLaSemaine(lundiISO) {
      const vacs = this._calVacances || [];
      const vendrediIso = window._jourSemaine(lundiISO, 4);
      for (const v of vacs) {
        if (!v.start_date || !v.end_date) continue;
        // end_date = jour de reprise (fin exclusive).
        if (v.start_date <= vendrediIso && v.end_date > lundiISO) {
          return v.description;
        }
      }
      return null;
    }

    _feriesDeLaSemaine(lundiISO) {
      const feries = [];
      const map = this._calFeries || {};
      for (let i = 0; i < 7; i++) {
        const iso = window._jourSemaine(lundiISO, i);
        if (map[iso]) feries.push({date: iso, nom: map[iso]});
      }
      return feries;
    }

    // v0.21.4 — Indisponibilités qui intersectent la semaine (lundi→vendredi).
    _indisposDeLaSemaine(lundiISO) {
      const vendrediIso = window._jourSemaine(lundiISO, 4);
      return (this._calIndispos || []).filter(ind => {
        const deb = ind.date_debut || '';
        const fin = ind.date_fin || deb;
        if (!deb) return false;
        // intersection [deb, fin] ∩ [lundi, vendredi]
        return deb <= vendrediIso && fin >= lundiISO;
      });
    }

    _ligneSemaine(lundiISO, _noSemaine) {
      const vac     = this._vacancesDeLaSemaine(lundiISO);
      const feries  = this._feriesDeLaSemaine(lundiISO);
      const creneaux = this._creneauxDeLaSemaine(lundiISO);
      const d = new Date(lundiISO + 'T00:00:00');
      const estDebutMois = d.getDate() <= 7;
      const classes = ['cal-row'];
      if (vac) classes.push('cal-row-vacances');

      const creneauxHtml = creneaux.map(c => {
        const sel = this.creneauSel === c.id ? ' cal-creneau-selected' : '';
        const partie = c.partie ? ` · ${this._esc(c.partie)}` : '';
        return `<div class="cal-creneau${sel}"
          onclick="ATELIER_PROGRESSION.selectionnerCreneau('${this._esc(c.id)}')"
          title="${this._esc(c.sequence)}${this._esc(partie)}">
          <strong>${this._esc(c.sequence)}</strong>${partie}
        </div>`;
      }).join('');

      const feriesHtml = feries.map(f =>
        `<span class="cal-ferie" title="${this._esc(f.nom)}">🔸 ${this._esc(f.nom)}</span>`
      ).join('');
      const vacHtml = vac ? `<div class="cal-vacances-label">🌴 ${this._esc(vac)}</div>` : '';
      // v0.27.2 — Marqueur d'une semaine neutralisée par un décalage.
      const neutrHtml = this._semaineNeutralisee(lundiISO)
        ? `<div style="background:#ede7f6;color:#5e35b1;border:1px solid #d1c4e9;`
          + `border-radius:3px;padding:1px 6px;font-size:11px;display:inline-block">`
          + `⤵ Décalage : ${this._esc(this._motifNeutralisation(lundiISO))}</div>`
        : '';

      // v0.21.4 — Indisponibilités de la semaine.
      const indispos = this._indisposDeLaSemaine(lundiISO);
      // Date ISO (aaaa-mm-jj) → jj/mm (calendrier par semaine, année implicite).
      const _jjmm = iso => {
        const m = String(iso || '').match(/^\d{4}-(\d{2})-(\d{2})/);
        return m ? `${m[2]}/${m[1]}` : (iso || '');
      };
      const indisposHtml = indispos.map(ind => {
        let quand;
        if (ind.type === 'seances') {
          // une seule journée + plage de créneaux
          quand = `${_jjmm(ind.date_debut)} ${this._esc(ind.creneau_debut)}→${this._esc(ind.creneau_fin)}`;
        } else if (!ind.date_fin || ind.date_debut === ind.date_fin) {
          quand = _jjmm(ind.date_debut);
        } else {
          quand = `${_jjmm(ind.date_debut)}→${_jjmm(ind.date_fin)}`;
        }
        const port = (ind.portee === 'classes') ? ' (classe)' : '';
        const motif = this._esc(ind.motif) || 'Indisponibilité';
        const txt = `${quand} · ${motif}${port}`;
        // v0.21.5 — En vue « réalisée » (classe sélectionnée), proposer de
        // décaler la progression de cette classe à partir du DÉBUT de l'indispo.
        // nb_semaines pré-calculé (semaines civiles touchées), modifiable.
        let action = '';
        if (this._vueClasseId) {
          // Un décalage existe-t-il déjà pour cette indisponibilité ?
          const dejaDecale = (this._decalages || []).some(
            d => d.indispo_id === ind.id);
          if (dejaDecale) {
            action = ` <span style="font-size:10px;color:#276749" title="Un décalage existe déjà pour cette indisponibilité (voir « Décalages de la classe »)">✓ décalé</span>`;
          } else {
            // v0.27.4 — Valeur par défaut du décalage : calculée CÔTÉ SERVEUR
            // (ind.semaines_touchees), plus recalculée en JS.
            const nbdef = ind.semaines_touchees || 1;
            const idb = `dec-nb-${this._esc(ind.id)}`;
            action = ` <label style="font-size:10px;color:#5e35b1">décaler
              <input id="${idb}" type="number" min="1" value="${nbdef}"
                style="width:52px;font-size:11px" title="Nombre de semaines (modifiable)">
              sem.</label>
              <button class="btn-sm" style="font-size:10px;padding:0 4px"
                onclick="ATELIER_PROGRESSION.decalerDepuisIndispo('${this._esc(ind.id)}','${this._esc(ind.date_debut)}',document.getElementById('${idb}').value)"
                title="Décaler la progression de cette classe à partir du ${_jjmm(ind.date_debut)}">↪ décaler</button>`;
          }
        }
        return `<span class="cal-indispo" title="${txt}"
          style="display:inline-block;background:#ede7f6;color:#5e35b1;
          border:1px solid #d1c4e9;border-radius:3px;padding:1px 5px;
          font-size:10px;margin:1px 2px 0 0">⛔ ${txt}${action}</span>`;
      }).join('');

      return `
        ${estDebutMois ? `<div class="cal-mois-sep">${window.MOIS_FR[d.getMonth()]} ${d.getFullYear()}</div>` : ''}
        <div class="${classes.join(' ')}">
          <div class="cal-date">${window._dateCourte(lundiISO)}</div>
          <div class="cal-contenu">
            ${vacHtml}
            ${neutrHtml}
            ${feriesHtml ? `<div class="cal-feries">${feriesHtml}</div>` : ''}
            ${indisposHtml ? `<div class="cal-indispos">${indisposHtml}</div>` : ''}
            ${creneauxHtml}
          </div>
        </div>`;
    }

    // ── Opérations créneau (persistance immédiate) ───────────────────────────

    /**
     * v0.19.1.0 — Ajout par CLIC sur une partie : crée un créneau SANS date
     * (Q-F : option b). L'enseignant le date ensuite via le formulaire de
     * détail. Refusé si la progression n'est pas modifiable.
     */
    // v0.22.2 — Premier lundi « disponible » pour poser une nouvelle partie :
    // le premier lundi de l'année scolaire si rien n'est encore daté, sinon le
    // premier lundi (non entièrement en vacances) STRICTEMENT après la fin du
    // dernier créneau daté. Retourne un ISO (aaaa-mm-jj) ou null.
    _prochainLundiDisponible() {
      if (!this.data) return null;
      const {debut, fin} = window._bornesAnneeScolaire(this.data.annee);
      const lundis = window._lundisEntre(debut, fin);
      if (!lundis.length) return null;
      // Dernière date de fin parmi les créneaux datés.
      let derniereFin = '';
      for (const c of (this.data.creneaux || [])) {
        const f = c.date_fin || c.date_debut;
        if (f && f > derniereFin) derniereFin = f;
      }
      for (const l of lundis) {
        if (this._semaineEntierementEnVacances(l)) continue;
        if (!derniereFin || l > derniereFin) return l;
      }
      // Aucun lundi après la dernière fin : prendre le dernier lundi utile.
      return lundis[lundis.length - 1];
    }

    // v0.22.2 — Période du dernier créneau daté (pour l'hériter).
    _periodeDerniereSequence() {
      let derniereFin = '';
      let periode = '';
      for (const c of (this.data && this.data.creneaux || [])) {
        const f = c.date_fin || c.date_debut;
        if (f && f >= derniereFin) { derniereFin = f; periode = c.periode || ''; }
      }
      return periode;
    }

    async poserPartie(seqCode, partieNumero) {
      if (!this.data) return;
      if (!this._estModifiable()) {
        this._status('Progression non modifiable dans cet état.', true);
        return;
      }
      const niveau = this._sel('prog-sel-niveau');
      const partieLib = partieNumero > 1 ? `${partieNumero}e partie` : '';
      // v0.22.2 — Positionner d'emblée au premier lundi disponible et hériter
      // de la période du créneau précédent.
      const debut = this._prochainLundiDisponible();
      const periode = this._periodeDerniereSequence();
      const body = {
        annee: this.data.annee,
        progression_id: this.data.id,
        sequence: seqCode,
        partie_debut: partieNumero,
        partie_fin: partieNumero,
        partie: partieLib,
        periode: periode, date_debut: debut, date_fin: debut,
      };
      try {
        const res = await api(
          `/api/progression/${encodeURIComponent(niveau)}/creneau-ajouter`,
          { method: 'POST', body: JSON.stringify(body) });
        if (res && res.error) { this._status('Erreur : ' + res.error, true); return; }
        this._status(debut ? 'Créneau ajouté au ' + this._dateFrCourte(debut)
                           : 'Créneau ajouté — à dater.');
        await this._rechargerProgression();
      } catch (e) {
        this._status('Erreur : ' + (e.message || e), true);
      }
    }

    _dateFrCourte(iso) {
      const m = String(iso || '').match(/^\d{4}-(\d{2})-(\d{2})/);
      return m ? `${m[2]}/${m[1]}` : (iso || '');
    }

    selectionnerCreneau(id) {
      this.creneauSel = id;
      const c = (this.data.creneaux || []).find(x => x.id === id);
      this._renderCalendrier();
      if (!c) { this._el('prog-creneau-form').style.display = 'none';
      if(typeof progSyncPoignee==='function')progSyncPoignee(); return; }
      this._el('prog-creneau-form').style.display = '';
      if(typeof progSyncPoignee==='function')progSyncPoignee();
      this._el('prog-form-titre').textContent =
        `${c.sequence}${c.partie ? ' · ' + c.partie : ''}`;
      this._el('prog-form-periode').value = c.periode || '';
      this._el('prog-form-debut').value   = c.date_debut || '';
      this._el('prog-form-fin').value     = c.date_fin   || '';
      // v0.22.2 — Positionner le sélecteur de date de FIN sur la date de début
      // (via `min`) : le calendrier natif s'ouvre au bon mois, évitant de faire
      // défiler jusqu'au semestre 2, et empêche une fin antérieure au début.
      const finEl = this._el('prog-form-fin');
      if (finEl) finEl.min = c.date_debut || '';
      this._renderObjectifsCreneau(c);
      this._renderSeancesCreneau(c);
      // v0.32.6 — Documents à distribuer sur ce créneau.
      if (typeof progDocsCharger === 'function') progDocsCharger();
    }

    // v0.22.2 — Quand la date de début change, recaler le `min` (et donc la
    // position d'ouverture) du sélecteur de date de fin.
    _syncMinFin() {
      const debutEl = this._el('prog-form-debut');
      const finEl = this._el('prog-form-fin');
      if (debutEl && finEl) finEl.min = debutEl.value || '';
    }

    /**
     * v0.19.1.4 — En mode 'par_serie', affiche les DEUX matrices de séances
     * (cible « Très bon » et « Satisfaisant ») de la partie du créneau, en
     * lecture seule (decision C). En mode 'par_objectif', masque le bloc.
     */
    _renderSeancesCreneau(c) {
      const bloc = this._el('prog-seances-bloc');
      if (!bloc) return;
      if (this._modeSeances !== 'par_serie' || !c) {
        bloc.style.display = 'none';
        return;
      }
      const pnum = (c.partie_debut != null) ? c.partie_debut
                 : (c.partie_fin != null) ? c.partie_fin : 1;
      const m = this._matricesSeances(c.sequence, pnum);
      // Libellés de série affichés.
      const SERIES = [
        ['R', 'Auto-éval / révisions'],
        ['F', 'Fondamentale'],
        ['A', 'Avancée'],
        ['E', 'Exploration'],
      ];
      const ligne = (cible, libelle) => {
        const cells = SERIES.map(([s]) => {
          const v = m[cible] ? m[cible][s] : undefined;
          const txt = (v === undefined || v === null)
            ? '<span style="color:var(--text-muted)">—</span>'
            : this._fmtSeances(v);
          return `<td style="text-align:center;padding:3px 6px">${txt}</td>`;
        }).join('');
        // Total = somme des séries renseignées de la cible.
        const total = SERIES.reduce((acc, [s]) => {
          const v = m[cible] ? m[cible][s] : undefined;
          return acc + (typeof v === 'number' ? v : 0);
        }, 0);
        return `<tr>
          <td style="padding:3px 6px;font-weight:500">${libelle}</td>
          ${cells}
          <td style="text-align:center;padding:3px 6px;font-weight:600">${this._fmtSeances(total)}</td>
        </tr>`;
      };
      bloc.style.display = '';
      bloc.innerHTML = `
        <div style="font-size:12px;font-weight:500;margin-bottom:6px">Séances par série
          <span style="font-weight:400;color:var(--text-muted)">(modèle historique)</span>
        </div>
        <table style="width:100%;border-collapse:collapse;font-size:11px">
          <thead>
            <tr style="color:var(--text-secondary)">
              <th style="text-align:left;padding:3px 6px">Cible</th>
              ${SERIES.map(([, l]) => `<th style="padding:3px 6px;font-weight:500">${l}</th>`).join('')}
              <th style="padding:3px 6px">Total</th>
            </tr>
          </thead>
          <tbody>
            ${ligne('TB', 'Très bon')}
            ${ligne('S', 'Satisfaisant')}
          </tbody>
        </table>`;
    }

    /** Formate un nombre de séances : entier sans décimale, sinon virgule. */
    _fmtSeances(v) {
      if (typeof v !== 'number') return String(v);
      return (Number.isInteger(v) ? String(v) : String(v).replace('.', ','));
    }

    _renderObjectifsCreneau(c) {
      const div = this._el('prog-objectifs-list');
      if (!div) return;
      const objs = (c && c.objectifs) || [];
      if (!objs.length) {
        div.innerHTML = '<span style="color:var(--text-muted)">'
          + 'Aucun objectif pour cette partie dans le référentiel lié.</span>';
        return;
      }
      div.innerHTML = objs.map(o => {
        const nb = (o.nb_seances && Number(o.nb_seances) > 0)
          ? `<span style="font-size:10px;color:var(--text-muted);margin-left:6px">`
            + `${o.nb_seances} séance(s)</span>` : '';
        const fc = o.fin_cycle
          ? '<span style="font-size:9px;font-weight:600;color:var(--warning-text);'
            + 'margin-left:6px;border:1px solid var(--warning-text);border-radius:3px;'
            + 'padding:0 3px">fin de cycle</span>' : '';
        return `<div style="padding:4px 0;border-bottom:1px solid var(--border-light)">
          <span style="font-size:10px;font-weight:600;color:var(--primary);margin-right:6px">obj.${this._esc(o.code)}</span>
          <span>${this._esc(o.nom || '')}</span>${nb}${fc}</div>`;
      }).join('');
    }

    async sauvegarderCreneau() {
      if (!this.creneauSel || !this.data) return;
      if (!this._estModifiable()) return;
      const niveau = this._sel('prog-sel-niveau');
      const periode = this._sel('prog-form-periode') || null;
      const debut   = this._sel('prog-form-debut')   || null;
      const fin     = this._sel('prog-form-fin')     || null;
      try {
        const res = await api(
          `/api/progression/${encodeURIComponent(niveau)}/creneau/${encodeURIComponent(this.creneauSel)}`,
          { method: 'PATCH', body: JSON.stringify({
              progression_id: this.data.id,
              annee: this.data.annee, periode, date_debut: debut, date_fin: fin }) });
        if (res && res.error) { this._status('Erreur : ' + res.error, true); return; }
        this._status('Créneau mis à jour.');
        await this._rechargerProgression();
        // Re-sélectionner pour garder le détail ouvert.
        if (this.creneauSel) this.selectionnerCreneau(this.creneauSel);
      } catch (e) {
        this._status('Erreur : ' + (e.message || e), true);
      }
    }

    async supprimerCreneau() {
      if (!this.creneauSel || !this.data) return;
      if (!this._estModifiable()) return;
      const c = (this.data.creneaux || []).find(x => x.id === this.creneauSel);
      if (!c) return;
      if (!confirm(`Retirer le créneau « ${c.sequence}${c.partie ? ' · ' + c.partie : ''} » du calendrier ?`)) return;
      const niveau = this._sel('prog-sel-niveau');
      try {
        const res = await api(
          `/api/progression/${encodeURIComponent(niveau)}/creneau/${encodeURIComponent(this.creneauSel)}`,
          { method: 'DELETE', body: JSON.stringify({
              progression_id: this.data.id, annee: this.data.annee }) });
        if (res && res.error) { this._status('Erreur : ' + res.error, true); return; }
        this.creneauSel = null;
        this._el('prog-creneau-form').style.display = 'none';
      if(typeof progSyncPoignee==='function')progSyncPoignee();
        this._status('Créneau retiré.');
        await this._rechargerProgression();
      } catch (e) {
        this._status('Erreur : ' + (e.message || e), true);
      }
    }

    /** Recharge la progression courante par son id et re-rend l'UI. */
    async _rechargerProgression() {
      if (!this.data || !this.data.id) return;
      try {
        const prog = await api(
          `/api/progression_id/${encodeURIComponent(this.data.id)}`);
        if (prog && !prog.error) this.data = prog;
      } catch (e) { /* garder l'ancien état */ }
      this._renderSidebar();
      this._renderBadgeEtat();
      this._renderBoutonsEtat(this.data.etat);
      await this._renderCalendrier();
    }

    _estModifiable() {
      const etat = this.data && this.data.etat;
      const academieAbsente = this.data && !this.data.etab_academie;
      return etat === 'en_cours' && !academieAbsente;
    }

    // ── État de la progression ───────────────────────────────────────────────

    async changerEtat(nouvelEtat) {
      if (!this.data) return;
      try {
        const resp = await fetch(
          `/api/progression_id/${encodeURIComponent(this.data.id)}/etat`,
          { method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({etat: nouvelEtat}) });
        if (!resp.ok) {
          const data = await resp.json().catch(() => ({error: `HTTP ${resp.status}`}));
          this._status(data.error || 'Erreur', true);
          return;
        }
        this.data = await resp.json();
        this._renderBadgeEtat();
        this._renderBoutonsEtat(this.data.etat);
        await this._renderCalendrier();
      } catch (e) {
        this._status('Erreur réseau : ' + e.message, true);
      }
    }

    // ── Livrets distribués (lecture seule) ───────────────────────────────────

    async _chargerDocuments() {
      const div = this._el('prog-docs-list');
      if (!div) return;
      const refId = this.data && this.data.referentiel_id;
      if (!refId) {
        div.innerHTML = '<span style="color:var(--text-muted)">'
          + 'Cette progression n\'est liée à aucun référentiel.</span>';
        return;
      }
      div.innerHTML = '<span style="color:var(--text-muted)">Chargement…</span>';
      try {
        const resp = await api(
          `/api/referentiels/${encodeURIComponent(refId)}/documents`);
        const docs = (resp && resp.documents) || [];
        if (!docs.length) {
          div.innerHTML = '<span style="color:var(--text-muted)">'
            + 'Aucun livret défini dans ce référentiel.</span>';
          return;
        }
        const LABELS = {
          livret_sequence:         'Livret de séquence',
          livret_plans_de_travail: 'Livret des plans de travail',
          livret_fiches_resume:    'Livret des fiches de résumé',
          recap_livrets:           'Récapitulatif des livrets',
        };
        const badge = (etat) => {
          const map = {
            ok:          ['Compilé',      'var(--success)'],
            perime:      ['À recompiler', 'var(--warning-text)'],
            ko:          ['Échec',        'var(--danger)'],
            en_cours:    ['Compilation…', 'var(--text-secondary)'],
            non_compile: ['Non compilé',  'var(--text-muted)'],
          };
          const [txt, col] = map[etat] || [etat || '—', 'var(--text-muted)'];
          return `<span style="font-size:11px;color:${col}">${txt}</span>`;
        };
        div.innerHTML = docs.map(d => {
          const nom = LABELS[d.type_document] || d.type_document;
          return `<div style="display:flex;align-items:center;gap:10px;padding:6px 0;
            border-bottom:1px solid var(--border-light)">
            <span style="flex:1">${this._esc(nom)}</span>${badge(d.etat_effectif)}</div>`;
        }).join('');
      } catch (e) {
        div.innerHTML = '<span style="color:var(--danger)">'
          + 'Erreur de chargement des livrets.</span>';
      }
    }

    // ── Divers ───────────────────────────────────────────────────────────────

    allerGestionEtabs() {
      // v0.19.1.2 — Naviguer vers Gestion > Établissement via la nav à 2
      // barres (active le bon bouton). Fallback sur l'ancien chemin.
      if (typeof window.sousOnglet === 'function') window.sousOnglet('parametrage');
      setTimeout(() => {
        if (typeof window.suiviSwitch === 'function') window.suiviSwitch('etab');
        else if (typeof window.gestionSousOnglet === 'function')
          window.gestionSousOnglet('etabs');
      }, 50);
    }
  }

  // Instance unique, exposée comme les autres ateliers OO.
  window.ATELIER_PROGRESSION = new AtelierProgression();

  // Hook public appelé par app.js (sousOnglet('progression')).
  window.progInit = function () {
    return window.ATELIER_PROGRESSION.init();
  };

})();
