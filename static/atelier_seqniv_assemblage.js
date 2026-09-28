/**
 * static/atelier_seqniv_assemblage.js — v0.16.7
 *
 * Atelier d'assemblage d'une séquence-dans-niveau (drag-and-drop pour
 * organiser parties, objectifs, méthodes, exos). Seul mode d'édition
 * disponible depuis v0.12.3.1 (l'éditeur formulaire historique
 * `ateliers_seqniv_v2_edit.js` a été supprimé après que toutes ses
 * fonctionnalités essentielles aient été portées ici en v0.12.3.0).
 *
 * v0.16.7 — Migration OO STRUCTURELLE. Le fichier était un IIFE procédural
 * (état module `DATA/OBJ_OUVERT/DRAG/…`, ~30 fonctions internes, 43 hooks
 * `window.seqnivAsm*`). Il devient une classe `AtelierSeqnivAssemblage extends
 * AtelierAssemblage`, instance unique `window.ATELIER_SEQNIV`, comme
 * l'évaluation (`window.ATELIER_EVALUATION`).
 *
 * **Comportement strictement identique** à v0.16.6 :
 *   - persistance immédiate (drag-drop = PATCH immédiat) ; pas de bouton
 *     Enregistrer, pas de concept de « modifié » (estPluriel=false,
 *     persistanceImmediate=true) ;
 *   - pas d'enregistrement dans la garde de sortie (rien à protéger — le
 *     seqniv procédural ne s'y enregistrait pas non plus). Le branchement de
 *     l'appareil verrou/mixte (comme l'évaluation) viendra APRÈS, dans une
 *     version dédiée, maintenant que la classe est en place ;
 *   - 3 modes de sidebar (aucun objectif ouvert / objectif « exo » ouvert /
 *     objectif Connaître ouvert) préservés ;
 *   - DnD multi-source/cible inchangé.
 *
 * Transformations mécaniques de la migration :
 *   - état module → champs d'instance (`this.data`, `this.objOuvert`,
 *     `this._drag`, `this._chargement`, `this._critDefauts`, `this._onglet`,
 *     `this._livretBlobUrl`, `this._livretDernierLog`) ;
 *   - fonctions internes `_*` → méthodes privées (même nom) ;
 *   - hooks `window.seqnivAsm*` → méthodes + wrappers globaux `window.atelSeqniv*`
 *     (style `atelEval*`) installés en bas de fichier ;
 *   - HTML généré : les handlers onclick / ondrag / onblur appellent
 *     désormais `ATELIER_SEQNIV.methode(...)` directement (plus de nom nu).
 *
 * Hook public conservé (compat app.js) :
 *   - window.seqnivAssemblageRafraichir() — appelé par app.js.initLivret()
 *     à chaque ouverture / changement de séquence. Délègue à
 *     ATELIER_SEQNIV.rafraichir().
 *
 * Logique pure : déléguée à window.SeqnivPur (module testé sous Vitest,
 * v0.16.6). La constante module `_PUR` ci-dessous capture window.SeqnivPur ;
 * elle est lue à l'évaluation du script (seqniv_pur.js est chargé AVANT, cf.
 * index.html).
 */

(function () {
  'use strict';

  // ── Logique pure (déléguée à window.SeqnivPur, testée sous Vitest) ─────────
  const _PUR = (typeof window !== 'undefined' && window.SeqnivPur) || null;

  // ── Helper réseau commun (sans état) ───────────────────────────────────────
  async function apiJson(method, path, body) {
    const opts = {
      method,
      headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
    };
    if (body !== undefined) opts.body = JSON.stringify(body);
    const rep = await fetch(path, opts);
    let data = null;
    try { data = await rep.json(); } catch (_) {}
    return {status: rep.status, ok: rep.ok, data: data};
  }

  class AtelierSeqnivAssemblage extends AtelierAssemblage {
    constructor() {
      super({
        id:                   'seqniv',
        // Préfixe DOM historique de la sidebar (#liv-atl-sidebar-body, etc.).
        prefixe:              'liv-atl',
        estPluriel:           false,
        // v0.16.9 — Régime MIXTE. Les champs de saisie de l'objectif OUVERT
        // (nom, critères F/A/E, fin-cycle, nb_seances) sont bufferisés dans
        // un <form id="liv-atl-form"> et persistés au clic « Enregistrer »
        // (snapshot via collecterFormulaire, badge « modifié », garde de
        // sortie héritée). Les OPÉRATIONS DE STRUCTURE (drag-drop, création/
        // suppression de parties/objectifs/liens) ET les séances des objets
        // FERMÉS / des parties restent en persistance immédiate (PATCH au vol).
        // Une garde _garderAvantStructure() empêche de perdre une saisie non
        // enregistrée en changeant d'objectif ou en touchant la structure.
        persistanceImmediate: false,
        endpointBase:         '/api/v2/sequences-par-niveau',
        labelExistant:        'Séquence',
        labelNouveau:         'Séquence',
        confirmSuppression:   '',
        messageEnregistre:    '',
        messageSupprime:      '',
      });

      // ── État d'instance (ex-variables module de l'IIFE) ──────────────────
      this.data         = null;   // GET /api/v2/sequences-par-niveau/<niveau>/<seq>
      this.objOuvert    = null;   // id de l'objectif en édition
      this._drag        = null;   // {kind: 'methode'|'exo'|'partie'|'obj', ...}
      this._chargement  = false;
      this._critDefauts = null;   // {nom, F, A, E} — préférences chargées 1 fois
      this._onglet      = 'edition';  // 'edition' | 'rendu'

      // v0.11.2 — Gestion du blob PDF du livret (libéré entre deux compils).
      this._livretBlobUrl    = null;
      this._livretDernierLog = '';
    }

    // ── Helpers DOM / état ───────────────────────────────────────────────────

    _status(msg, err) {
      const el = document.getElementById('liv-atl-status');
      if (!el) return;
      el.textContent = msg || '';
      el.style.color = err ? '#c0392b' : '#6da06d';
      if (msg) {
        setTimeout(() => {
          if (el.textContent === msg) el.textContent = '';
        }, err ? 6000 : 2000);
      }
    }

    _container() {
      // v0.11.3 — Le contenu d'assemblage (header, parties, etc.) est désormais
      // injecté dans le sous-onglet Édition. Le sous-onglet Rendu PDF a sa
      // propre logique (cf. _assurerOngletRendu plus bas).
      return document.getElementById('asm-tab-edition');
    }
    _sidebarBody() {
      return document.getElementById('liv-atl-sidebar-body');
    }
    _sidebarTitre() {
      return document.getElementById('liv-atl-sidebar-titre');
    }
    _sidebarHint() {
      return document.getElementById('liv-atl-sidebar-hint');
    }

    _sn() {
      return (this.data && this.data.sequence_par_niveau) || null;
    }

    _esc(s) { return _PUR.esc(s); }
    _escAttr(s) { return _PUR.escAttr(s); }

    // ── v0.11.3 — Bascule d'onglets Édition / Rendu PDF ────────────────────
    //
    // L'atelier d'assemblage est découpé en deux onglets de premier niveau :
    // - Édition : la machinerie d'assemblage (parties, objectifs, exercices…)
    // - Rendu PDF : bouton compiler, bouton .tex, zone de rendu (iframe ou
    //   message d'erreur)
    //
    // Le contenu de l'onglet Rendu PDF est généré paresseusement à la première
    // ouverture (et garde son état pour les ouvertures suivantes — un PDF
    // déjà compilé reste affiché).
    //
    // v0.15.4 — Le cadre « Éléments à inclure » (toggles Cours/Exos/Fiches/…)
    // qui vivait en tête de l'onglet Édition a été supprimé. Cette
    // configuration a migré dans le référentiel quelques versions plus tôt ;
    // le bloc en double n'avait plus d'utilité. Les options envoyées au
    // backend de compilation prennent désormais leurs valeurs par défaut
    // (tout inclus), cf. `_livretSeqOptions` plus bas.

    basculerOnglet(tab) {
      if (tab !== 'edition' && tab !== 'rendu') return;
      this._onglet = tab;
      const cEd = document.getElementById('asm-tab-edition');
      const cRd = document.getElementById('asm-tab-rendu');
      const bEd = document.getElementById('asm-tab-btn-edition');
      const bRd = document.getElementById('asm-tab-btn-rendu');
      if (cEd) cEd.style.display = (tab === 'edition') ? '' : 'none';
      if (cRd) cRd.style.display = (tab === 'rendu') ? 'flex' : 'none';
      if (bEd) bEd.classList.toggle('active', tab === 'edition');
      if (bRd) bRd.classList.toggle('active', tab === 'rendu');
      if (tab === 'rendu') {
        this._assurerOngletRendu();
      }
    }

    // Génère paresseusement le contenu de l'onglet Rendu PDF à la première
    // ouverture. Si déjà rempli, ne touche pas (préserve un PDF déjà chargé).
    _assurerOngletRendu() {
      const c = document.getElementById('asm-tab-rendu');
      if (!c) return;
      if (c.dataset.initialise === '1') {
        return;
      }
      c.innerHTML = `
        <div class="livret-seq-actions">
          <button class="btn-prim" id="livret-seq-btn-pdf"
                  onclick="ATELIER_SEQNIV.livretSeqGenererPdf()">
            🔧 Compiler le livret
          </button>
          <button class="btn-prim" id="livret-seq-btn-plan"
                  onclick="ATELIER_SEQNIV.livretSeqCompilerPlanTravail()"
                  title="Compile le plan de travail de cette séquence (une page par partie de la séquence). Pour le livret annuel agrégeant toutes les séquences du niveau, voir l'atelier « Plans de travail » de la portée Niveau.">
            🗓 Compiler le plan de travail
          </button>
          <button class="btn-sec" id="livret-seq-btn-tex"
                  onclick="ATELIER_SEQNIV.livretSeqVoirTex()">
            LaTeX généré
          </button>
        </div>
        <div class="livret-seq-rendu" id="livret-seq-rendu">
          <div class="livret-seq-empty" id="livret-seq-empty">
            Cliquez sur <strong>Compiler le livret</strong> pour générer le PDF.
          </div>
          <div class="livret-seq-loader" id="livret-seq-loader" style="display:none">
            <div class="livret-seq-spinner"></div>
            <div class="livret-seq-loader-msg">Compilation en cours&hellip;</div>
            <div class="livret-seq-loader-hint">
              La génération peut prendre 10 à 30&nbsp;secondes
              (compilation LaTeX en double passe).
            </div>
          </div>
          <div class="livret-seq-erreur" id="livret-seq-erreur" style="display:none"></div>
          <div class="livret-seq-tex-out" id="livret-seq-tex-out" style="display:none"></div>
          <div class="livret-seq-pdf-wrapper" id="livret-seq-pdf-wrapper" style="display:none">
            <iframe class="livret-seq-pdf-iframe" id="livret-seq-pdf-iframe"></iframe>
          </div>
        </div>
      `;
      c.dataset.initialise = '1';
    }

    // Réinitialise l'onglet Rendu PDF (vide son contenu, libère le blob).
    // Appelée quand on change de séquence pour ne pas garder un PDF stale.
    _reinitialiserOngletRendu() {
      const c = document.getElementById('asm-tab-rendu');
      if (!c) return;
      // Libérer le blob URL si présent.
      try { this._livretSeqLiberer(); } catch (_) {}
      c.innerHTML = '';
      delete c.dataset.initialise;
    }

    // ── Hook public appelé par app.js ────────────────────────────────────────

    async rafraichir(options = {}) {
      if (this._chargement) return;
      // v0.17.5 — Opération de structure : préserver la position de défilement
      // (sinon le panneau remonte en haut à chaque action). On capture AVANT
      // tout, et on évite le placeholder « Chargement… » qui écraserait le
      // contenu (et provoquerait un saut visuel).
      const preserverScroll = !!options.preserverScroll;
      if (preserverScroll) this._capturerScroll();

      const niveau = window.ATL_FILTRE_NIVEAU || '';
      const seq    = window.ATL_FILTRE_SEQ    || '';
      if (!niveau || !seq) {
        this._afficher('<div class="asm-vide">Choisir un niveau et une séquence.</div>');
        this._afficherSidebarVide('Choisir une séquence');
        return;
      }

      this._chargement = true;
      if (!preserverScroll) this._afficher('<div class="asm-vide">Chargement…</div>');
      try {
        // 1. Charger les critères par défaut depuis Préférences (une seule fois)
        if (this._critDefauts === null) await this._chargerCriteresDefaut();

        // 2. Charger la structure complète de la séquence
        const rep = await apiJson('GET',
          `/api/v2/sequences-par-niveau/${encodeURIComponent(niveau)}/${encodeURIComponent(seq)}`);

        if (rep.status === 404) {
          this._afficher(`
            <div class="asm-vide">
              <p><strong>${this._esc(niveau)} / ${this._esc(seq)}</strong> n'est pas peuplée dans le modèle v2.</p>
              <p>Lance <code>peuplement_13_v2_depuis_base.py</code> avant édition.</p>
            </div>`);
          this._afficherSidebarVide('Séquence non peuplée');
          return;
        }
        if (!rep.ok) {
          this._afficher(`<div class="asm-vide">Erreur HTTP ${rep.status}.</div>`);
          this._afficherSidebarVide('Erreur');
          return;
        }
        this.data = rep.data;
        this.objOuvert = (this.data.etat_ui && this.data.etat_ui.objectif_ouvert_id) || null;

        this._rendreCentre();
        this._rendreSidebar();

        // v0.16.9 — Régime mixte : si un objectif est ouvert, son <form>
        // #liv-atl-form vient d'être rendu. On (ré)installe le listener
        // input/change et on prend un snapshot propre (état non modifié).
        // Si aucun objectif ouvert, collecterFormulaire() renverra null →
        // modifie reste false.
        this._listenerInstalle = false;  // le form a été recréé par le rendu
        this._installerListenerForm();
        this.modifie = false;            // prend le snapshot du form courant

        // v0.16.9 — Verrou « validé = lecture seule » : applique l'état sur le
        // bandeau (boutons valider/structure) + grise le form si validé.
        this._appliquerEtatSequence();

        // v0.11.3 — Au CHANGEMENT de séquence, on remet l'onglet Rendu PDF à
        // zéro et on revient à l'onglet Édition. Lors d'une opération de
        // STRUCTURE (preserverScroll), on ne touche ni à l'onglet ni au scroll
        // (on restaure la position de défilement capturée).
        if (preserverScroll) {
          this._restaurerScroll();
        } else {
          this._reinitialiserOngletRendu();
          this.basculerOnglet('edition');
        }
      } catch (err) {
        this._afficher(`<div class="asm-vide">Erreur réseau : ${this._esc(err.message || err)}</div>`);
      } finally {
        this._chargement = false;
      }
    }

    _afficher(html) {
      const c = this._container();
      if (c) c.innerHTML = html;
    }

    _afficherSidebarVide(msg) {
      const sb = this._sidebarBody();
      if (sb) sb.innerHTML = `<div class="asm-sidebar-empty">${this._esc(msg)}</div>`;
      const t = this._sidebarTitre();
      if (t) t.textContent = 'Séquence';
      const h = this._sidebarHint();
      if (h) h.textContent = '';
    }

    async _chargerCriteresDefaut() {
      // Récupère les valeurs de Préférences. Si la clé n'existe pas, on
      // tombe sur les fallbacks codés en dur (cf. cahier des charges Q5).
      try {
        const rep = await apiJson('GET', '/api/configuration');
        const cfg = (rep.ok && rep.data) || {};
        const vals = cfg.atelier_assemblage_criteres_connaitre || {};
        this._critDefauts = {
          nom:       vals.nom       || 'Connaître les notions et les méthodes',
          critere_F: vals.critere_F || 'A noté la trace écrite en classe.',
          critere_A: vals.critere_A || 'A complété les fiches de résumé.',
          critere_E: vals.critere_E || "Sait résumer le cours à l'oral.",
        };
      } catch (_) {
        this._critDefauts = {
          nom:       'Connaître les notions et les méthodes',
          critere_F: 'A noté la trace écrite en classe.',
          critere_A: 'A complété les fiches de résumé.',
          critere_E: "Sait résumer le cours à l'oral.",
        };
      }
    }

    // ── Rendu de la zone centrale : header + parties ─────────────────────────

    _rendreCentre() {
      const sn      = this._sn();
      const parties = (this.data.parties || []);
      const precs   = (this.data.precedences || []);

      const themeBadge = sn.theme_code
        ? `<span class="asm-theme-badge" style="background:${this._couleurTheme(sn.theme_code_couleur)};color:white">
              ${this._esc(sn.theme_code)} — ${this._esc(sn.theme_nom || '')}
           </span>`
        : '';

      const html = [];
      html.push(`
        <div class="asm-header">
          <span class="asm-header-niv">${this._esc(sn.niveau || '')}</span>
          <span class="asm-header-code">${this._esc(sn.sequence_code || '')}</span>
          <span class="asm-header-nom">${this._esc(sn.sequence_nom || '')}</span>
          ${themeBadge}
        </div>
        ${this._rendreBlocPrecedences(precs)}
        <div class="asm-parties" id="asm-parties-list">
          ${parties.length === 0
              ? '<div class="asm-vide">Aucune partie. Crée une première partie ci-dessous.</div>'
              : parties.map(p => this._rendrePartie(p)).join('')
          }
          <button class="asm-btn-nouvelle-partie"
                  onclick="ATELIER_SEQNIV.nouvellePartie()">
            + Nouvelle partie
          </button>
        </div>
      `);
      this._afficher(html.join(''));

      // Brancher le drag-and-drop des parties après injection HTML
      this._brancherDragParties();
    }


    _couleurTheme(code) {
      return _PUR.couleurTheme(code);
    }

    // ── v0.10.2 — Bloc Précédences ───────────────────────────────────────────
    //
    // Affiché juste sous le header de séquence. Liste les précédences (pills
    // avec ✕), bouton "+ Ajouter" qui révèle un mini-formulaire avec deux
    // sélecteurs (niveau + séquence). Validation → POST API.

    _rendreBlocPrecedences(precs) {
      const pills = (precs || []).map(p => {
        const lib = `${this._esc(p.precedent_niveau)} / ${this._esc(p.precedent_seq)}`;
        return `
          <span class="asm-prec-pill">
            <span class="asm-prec-pill-lib">${lib}</span>
            <button class="asm-prec-pill-rm"
                    onclick="ATELIER_SEQNIV.retirerPrecedence('${this._escAttr(p.precedent_niveau)}', '${this._escAttr(p.precedent_seq)}')"
                    title="Retirer cette précédence">×</button>
          </span>`;
      }).join('');

      return `
        <div class="atl-cadre atl-cadre--compact asm-prec-bloc">
          <div class="asm-prec-bloc-row">
            <span class="asm-prec-bloc-titre">Précédences :</span>
            <div class="asm-prec-pills">
              ${pills || '<span class="asm-prec-vide">Aucune.</span>'}
            </div>
            <button class="asm-prec-btn-ajouter"
                    onclick="ATELIER_SEQNIV.togglePrecPopover()"
                    title="Ajouter une précédence">+ Ajouter</button>
          </div>
          <div class="asm-prec-popover" id="asm-prec-popover" style="display:none">
            <div class="asm-prec-popover-row">
              <label>Niveau&nbsp;:</label>
              <select id="asm-prec-sel-niveau"
                      onchange="ATELIER_SEQNIV.chargerSeqsPrec()">
                <option value="">— choisir —</option>
                <option value="N09">N09 (6ème)</option>
                <option value="N10">N10 (5ème)</option>
                <option value="N11">N11 (4ème)</option>
                <option value="N12">N12 (3ème)</option>
              </select>
            </div>
            <div class="asm-prec-popover-row">
              <label>Séquence&nbsp;:</label>
              <select id="asm-prec-sel-seq" disabled>
                <option value="">— choisir un niveau d'abord —</option>
              </select>
            </div>
            <div class="asm-prec-popover-actions">
              <button class="btn-prim asm-prec-btn-valider"
                      onclick="ATELIER_SEQNIV.validerPrecedence()">Ajouter</button>
              <button class="asm-prec-btn-annuler"
                      onclick="ATELIER_SEQNIV.togglePrecPopover()">Annuler</button>
            </div>
          </div>
        </div>`;
    }

    // Toggle d'ouverture du popover. Si on l'ouvre, réinitialise les selects.
    togglePrecPopover() {
      const pop = document.getElementById('asm-prec-popover');
      if (!pop) return;
      const ouvert = pop.style.display !== 'none';
      if (ouvert) {
        pop.style.display = 'none';
      } else {
        pop.style.display = '';
        const selN = document.getElementById('asm-prec-sel-niveau');
        const selS = document.getElementById('asm-prec-sel-seq');
        if (selN) selN.value = '';
        if (selS) {
          selS.innerHTML = '<option value="">— choisir un niveau d\'abord —</option>';
          selS.disabled = true;
        }
      }
    }

    // Lit le sélecteur de niveau et alimente celui des séquences en
    // conséquence (via /api/cycles/<code>/sequences). Convention :
    //   - N07/N08/N09 (cycle 3) → cycle C03
    //   - N10/N11/N12 (cycle 4) → cycle C04
    // Si N09 n'a pas encore de séquences-niveau peuplées, le sélecteur
    // affichera quand même les séquences C03 (le découpage du cycle 3).
    // (Mapping étendu si d'autres niveaux/cycles arrivent un jour.)
    async chargerSeqsPrec() {
      const selN = document.getElementById('asm-prec-sel-niveau');
      const selS = document.getElementById('asm-prec-sel-seq');
      if (!selN || !selS) return;
      const niveau = selN.value || '';
      if (!niveau) {
        selS.innerHTML = '<option value="">— choisir un niveau d\'abord —</option>';
        selS.disabled = true;
        return;
      }
      // Mapping niveau → cycle. N07/N08/N09 → C03, N10+ → C04.
      let cycle = 'C04';
      if (niveau >= 'N07' && niveau <= 'N09') cycle = 'C03';
      selS.innerHTML = '<option value="">Chargement…</option>';
      selS.disabled = true;
      try {
        const rep = await apiJson('GET', `/api/cycles/${encodeURIComponent(cycle)}/sequences`);
        if (!rep.ok) {
          selS.innerHTML = '<option value="">Erreur de chargement</option>';
          return;
        }
        const seqs = (rep.data && rep.data.sequences) || [];
        if (seqs.length === 0) {
          selS.innerHTML = `<option value="">Cycle ${cycle} non importé</option>`;
          return;
        }
        // Trier par numéro
        seqs.sort((a, b) => (a.numero || 0) - (b.numero || 0));
        let opts = '<option value="">— choisir —</option>';
        for (const s of seqs) {
          opts += `<option value="${this._escAttr(s.code)}">${this._esc(s.code)} — ${this._esc(s.nom || '')}</option>`;
        }
        selS.innerHTML = opts;
        selS.disabled = false;
      } catch (err) {
        selS.innerHTML = '<option value="">Erreur réseau</option>';
      }
    }

    async validerPrecedence() {
      // v0.16.9 — garde régime mixte : pas d'opération de structure
      // tant qu'une saisie de l'objectif ouvert n'est pas enregistrée.
      if (!this._garderAvantStructure()) return;
      const selN = document.getElementById('asm-prec-sel-niveau');
      const selS = document.getElementById('asm-prec-sel-seq');
      if (!selN || !selS) return;
      const pn = selN.value || '';
      const ps = selS.value || '';
      if (!pn || !ps) {
        this._status('Choisis un niveau et une séquence.', true);
        return;
      }
      const sn = this._sn();
      if (!sn) return;
      const rep = await apiJson('POST',
        `/api/v2/sequences-par-niveau/${encodeURIComponent(sn.id)}/precedences`,
        {precedent_niveau: pn, precedent_seq: ps});
      if (!rep.ok) {
        const code = (rep.data && rep.data.code) || '';
        let msg = (rep.data && rep.data.error) || `HTTP ${rep.status}`;
        if (code === 'precedence_seq_deja_presente') msg = 'Cette précédence est déjà déclarée.';
        if (code === 'precedence_invalide') msg = 'Précédence invalide (champs vides ou pointeur circulaire).';
        this._status(msg, true);
        return;
      }
      this._status('Précédence ajoutée.', false);
      await this.rafraichir({preserverScroll: true});
    }

    async retirerPrecedence(precNiveau, precSeq) {
      // v0.16.9 — garde régime mixte : pas d'opération de structure
      // tant qu'une saisie de l'objectif ouvert n'est pas enregistrée.
      if (!this._garderAvantStructure()) return;
      const sn = this._sn();
      if (!sn) return;
      const rep = await apiJson('DELETE',
        `/api/v2/sequences-par-niveau/${encodeURIComponent(sn.id)}/precedences/${encodeURIComponent(precNiveau)}/${encodeURIComponent(precSeq)}`);
      if (!rep.ok) {
        this._status(`Erreur retrait : ${(rep.data && rep.data.error) || rep.status}`, true);
        return;
      }
      this._status('Précédence retirée.', false);
      await this.rafraichir({preserverScroll: true});
    }

    // ── Rendu d'une partie (carte) ───────────────────────────────────────────

    _rendrePartie(p) {
      const ra = p.exos_revision_approche || {R: [], EA: []};
      const objs = (p.objectifs || []);
      // v0.10.5.1 (bug Q-8) : la zone Révision est disponible dès que la
      // séquence-niveau a au moins une précédence déclarée. L'ancienne
      // règle "pas de révision en N10" empêchait de poser des exos R même
      // après ajout d'une précédence sur N09 → N10.
      const precedences = (this.data && this.data.precedences) || [];
      const revisionDisponible = precedences.length > 0;
      const codeConnaitre = `${p.numero - 1}1`;
      const aDejaConnaitre = objs.some(o => o.code === codeConnaitre);

      // v0.12.1 — Total en lecture seule des séances prévues pour cette
      // partie : R+AE de la partie + somme des nb_seances de tous ses
      // objectifs (cours et exos confondus). Recalculé à chaque rendu,
      // donc toujours cohérent avec la dernière saisie. Affiché à côté
      // du titre "Partie N" pour avoir une vue rapide "combien de
      // semaines ça tient".
      const totalSeances = this._calculerTotalSeancesPartie(p);
      const totalLib = totalSeances === 0
        ? ''
        : `total : ${this._fmtSeancesAffichage(totalSeances)} séance${totalSeances > 1 ? 's' : ''}`;

      return `
        <div class="asm-partie"
             data-partie-id="${this._escAttr(p.id)}"
             data-partie-num="${p.numero}"
             draggable="true"
             ondragstart="ATELIER_SEQNIV.dragStartPartie(event, '${this._escAttr(p.id)}')"
             ondragend="ATELIER_SEQNIV.dragEnd(event)">
          <div class="asm-partie-head">
            <span class="asm-partie-handle" title="Glisser pour réordonner">⋮⋮</span>
            <span class="asm-partie-titre">Partie ${p.numero}</span>
            ${totalLib ? `<span class="asm-partie-total" title="Total des séances prévues pour cette partie (R+AE + cours + exos)">${totalLib}</span>` : ''}
            <div class="asm-partie-meta">
              <label class="asm-seances-label" title="Nombre de séances prévues pour les exercices Révision et Approche de cette partie">
                <span class="asm-seances-libelle">R+AE :</span>
                <input type="number"
                       class="asm-seances-input"
                       min="0" max="999" step="0.5"
                       value="${this._fmtSeances(p.nb_seances_R_AE)}"
                       placeholder="0"
                       onblur="ATELIER_SEQNIV.changerSeancesPartie('${this._escAttr(p.id)}', this.value)"
                       onkeydown="if(event.key==='Enter'){this.blur();}">
                <span class="asm-seances-unite">séance(s)</span>
              </label>
              <button class="asm-btn-suppr-partie"
                      onclick="ATELIER_SEQNIV.supprimerPartie('${this._escAttr(p.id)}', ${objs.length}, ${ra.R.length + ra.EA.length})"
                      title="Supprimer cette partie">
                Supprimer
              </button>
            </div>
          </div>
          <div class="asm-partie-body">
            ${this._rendreZoneCartes(p)}
            ${this._rendreZoneRA(p, revisionDisponible)}
            ${this._rendreZoneObjs(p, objs, aDejaConnaitre, codeConnaitre)}
          </div>
        </div>
      `;
    }

    // ── v0.13.6.3.2 — Zone Cartes d'automatisme (lecture seule) ───────────────
    //
    // Affiche les cartes d'automatisme rattachées à la partie via leur
    // notion/méthode (chaîne carte → notion|méthode → objectif → partie).
    // Position : avant la zone R/AE, comme dans l'atelier Référentiel.
    // Lecture seule : pas de drag-and-drop ; chips cliquables ouvrant
    // l'atelier Carte sur la carte précise (deeplink v0.13.6.3).

    _rendreZoneCartes(p) {
      const cartes = p.cartes || [];
      const titreContenu = cartes.length === 0
        ? `<span class="asm-ra-titre-disabled-hint">— (aucune)</span>`
        : '';
      const corps = cartes.length === 0
        ? '<div class="asm-ra-vide">Aucune carte d\'automatisme rattachée aux notions et méthodes de cette partie.</div>'
        : `<div class="asm-cartes-chips">${cartes.map(c => this._rendreChipCarte(c)).join('')}</div>`;

      return `
        <div class="asm-zone-cartes">
          <div class="asm-ra-col disabled" style="cursor:default">
            <div class="asm-ra-titre">
              Cartes d'automatisme${titreContenu}
            </div>
            ${corps}
          </div>
        </div>`;
    }

    _rendreChipCarte(c) {
      // v0.18.2 — Utilise le helper global lienAtomeHTML : clic simple ouvre
      // EN PLACE, Ctrl/⌘+clic ouvre dans un nouvel onglet (cohérent avec la
      // Recherche, le Rendu par lot et les autres atomes de l'assemblage).
      // niveau/séquence = ceux du DATA courant (les cartes sont de la séquence
      // courante).
      const sn = (this.data && this.data.sequence_par_niveau) || {};
      const niveau = sn.niveau || '';
      const seq    = sn.sequence_code || '';
      const styleBadge = c.etat_code === 'valide'
        ? 'background:#c8e6c9;color:#1b5e20;border-color:#a5d6a7'
        : 'background:#eeeeee;color:#444;border-color:#cfcfcf';
      const tooltip = this._esc(c.nom || '').replace(/"/g, '&quot;');
      const code = this._esc(c.code || '');
      const styleBase = 'display:inline-flex;align-items:center;padding:2px 7px;'
        + 'border:1px solid;border-radius:3px;font-size:11px;'
        + 'text-decoration:none;line-height:1.4;white-space:nowrap;margin:2px';
      const attrs = `title="${tooltip}" style="${styleBase};${styleBadge}"`;
      if (c.id && niveau && seq && typeof window.lienAtomeHTML === 'function') {
        return window.lienAtomeHTML('carte', c.id, niveau, seq, code, attrs);
      }
      return `<span ${attrs}>${code}</span>`;
    }

    // ── v0.17.5 — Classe d'état d'un atome placé (panneau central) ───────────
    // Validé → suffixe `--valide` (vert pâle via CSS) ; en cours → rien
    // (apparence transparente par défaut). `prefixeClasse` ex. 'asm-exo-chip'.
    _classeEtatAtome(etatCode, prefixeClasse) {
      return etatCode === 'valide' ? ` ${prefixeClasse}--valide` : '';
    }

    // ── Zone Révision/Approche (en haut de partie) ───────────────────────────

    _rendreZoneRA(p, revisionDisponible) {
      const ra = p.exos_revision_approche || {R: [], EA: []};
      const colR = revisionDisponible
        ? `
          <div class="asm-ra-col"
               data-zone="R" data-partie-id="${this._escAttr(p.id)}"
               ondragover="ATELIER_SEQNIV.dragOver(event, this)"
               ondragleave="ATELIER_SEQNIV.dragLeave(event, this)"
               ondrop="ATELIER_SEQNIV.dropRA(event, '${this._escAttr(p.id)}', 'R')">
            <div class="asm-ra-titre">Révision</div>
            ${this._rendreChipsRA(p.id, 'R', ra.R)}
          </div>`
        : `
          <div class="asm-ra-col disabled" title="Aucune précédence déclarée pour cette séquence">
            <div class="asm-ra-titre">
              Révision
              <span class="asm-ra-titre-disabled-hint">— aucune précédence</span>
            </div>
            <div class="asm-ra-vide">Indisponible. Pour activer, déclarer une précédence en haut de l'écran.</div>
          </div>`;

      const colEA = `
        <div class="asm-ra-col"
             data-zone="EA" data-partie-id="${this._escAttr(p.id)}"
             ondragover="ATELIER_SEQNIV.dragOver(event, this)"
             ondragleave="ATELIER_SEQNIV.dragLeave(event, this)"
             ondrop="ATELIER_SEQNIV.dropRA(event, '${this._escAttr(p.id)}', 'EA')">
          <div class="asm-ra-titre">Approche</div>
          ${this._rendreChipsRA(p.id, 'EA', ra.EA)}
        </div>`;

      return `<div class="asm-zone-ra">${colR}${colEA}</div>`;
    }

    _rendreChipsRA(partieId, type, exos) {
      if (!exos || exos.length === 0) {
        return '<div class="asm-ra-vide">Glisse un exercice ici.</div>';
      }
      return exos.map(e => {
        const ex = e.exercice || {};
        const lib = ex.fichier ? ex.fichier.replace(/\.tex$/i, '') : (e.exercice_id || '?').slice(0, 12);
        const originSuffix = (type === 'R' && e.origin_niveau)
          ? ` <span class="asm-item-placed-tag">${this._esc(e.origin_niveau)}/${this._esc(e.origin_seq)}</span>`
          : '';
        const etatChip = this._classeEtatAtome(
          (e.exercice || {}).etat_code, 'asm-exo-chip');
        // v0.18.3 — Ouverture de l'exercice (double-clic ; Ctrl/⌘+double-clic =
        // nouvel onglet). On vise la séquence d'ORIGINE : pour un exo de
        // révision (R) c'est origin_niveau/origin_seq (autre séquence) ; pour
        // un exo d'approche (EA) l'origine est NULL en base (= séquence
        // courante), on retombe sur le niveau/séquence de l'exercice lui-même.
        const ouvNiveau = e.origin_niveau || ex.niveau || '';
        const ouvSeq    = e.origin_seq    || ex.sequence || '';
        const dbl = `ATELIER_SEQNIV.editerAtome('exercice', `
          + `'${this._escAttr(e.exercice_id)}', event, `
          + `'${this._escAttr(ouvNiveau)}', '${this._escAttr(ouvSeq)}')`;
        return `
          <span class="asm-exo-chip${etatChip}"
                draggable="true"
                ondblclick="${dbl}"
                title="Double-clic pour éditer l'exercice (Ctrl+double-clic : nouvel onglet)"
                ondragstart="ATELIER_SEQNIV.dragStartExoRA(event, '${this._escAttr(partieId)}', '${this._escAttr(type)}', '${this._escAttr(e.exercice_id)}')"
                ondragend="ATELIER_SEQNIV.dragEnd(event)">
            <span class="asm-exo-chip-num">${e.ordre}</span>
            <span>${this._esc(lib)}</span>
            ${originSuffix}
            <button class="asm-exo-chip-rm"
                    onclick="event.stopPropagation();ATELIER_SEQNIV.retirerExoRA('${this._escAttr(partieId)}', '${this._escAttr(type)}', '${this._escAttr(e.exercice_id)}')"
                    title="Retirer">×</button>
          </span>`;
      }).join('');
    }

    // ── Zone des objectifs ───────────────────────────────────────────────────

    _rendreZoneObjs(p, objs, aDejaConnaitre, codeConnaitre) {
      const objsHtml = objs.map(o => this._rendreObj(p, o)).join('');

      const btnConnaitre = !aDejaConnaitre
        ? `<button class="asm-btn-connaitre"
                   onclick="ATELIER_SEQNIV.activerConnaitre('${this._escAttr(p.id)}')"
                   title="Crée l'objectif Connaître les notions et les méthodes (code ${codeConnaitre})">
              + Activer l'objectif Connaître (${codeConnaitre})
           </button>`
        : '';

      // Zone de drop générique pour les méthodes
      const zoneDrop = `
        <div class="asm-obj-vide-zone"
             data-zone="methode" data-partie-id="${this._escAttr(p.id)}"
             ondragover="ATELIER_SEQNIV.dragOver(event, this)"
             ondragleave="ATELIER_SEQNIV.dragLeave(event, this)"
             ondrop="ATELIER_SEQNIV.dropMethode(event, '${this._escAttr(p.id)}')">
          ${btnConnaitre}
          <span>Glisse une méthode pour créer un objectif</span>
        </div>`;

      return `
        <div class="asm-zone-objs" data-partie-id="${this._escAttr(p.id)}">
          ${objsHtml}
          ${zoneDrop}
        </div>`;
    }

    // ── Rendu d'un objectif (fermé / ouvert) ─────────────────────────────────

    _rendreObj(p, o) {
      const ouvert = (this.objOuvert === o.id);
      return ouvert ? this._rendreObjOuvert(p, o) : this._rendreObjFerme(p, o);
    }

    _rendreObjFerme(p, o) {
      const codeConnaitre = `${p.numero - 1}1`;
      const estConnaitre = (o.code === codeConnaitre);
      const codeClass = estConnaitre ? 'asm-obj-code asm-obj-code--connaitre' : 'asm-obj-code';
      const nbExos = ['R','EA','F','A','E'].reduce((acc, s) => {
        const arr = (o.exos_par_serie && o.exos_par_serie[s]) || [];
        return acc + arr.length;
      }, 0);
      // v0.12.1 — Pour les objectifs "cours" (code 01/11/21), le résumé
      // reste toujours vide : ces objectifs n'ont par construction pas
      // d'exos rattachés, et leur méthode liée éventuelle n'apporte rien
      // d'utile dans le bandeau. Le titre "Cours" se suffit à lui-même.
      let resume;
      if (estConnaitre) {
        resume = '';
      } else {
        const meth = o.methode_titre ? ` · méthode : ${this._esc(o.methode_titre)}` : '';
        resume = nbExos > 0
          ? `${nbExos} exo(s)${meth}`
          : (meth ? meth.slice(3) : 'aucun exo');
      }
      const libSeances = estConnaitre ? 'Cours :' : 'Exos :';

      return `
        <div class="asm-obj closed"
             data-obj-id="${this._escAttr(o.id)}"
             data-obj-est-cours="${estConnaitre ? '1' : '0'}"
             draggable="${estConnaitre ? 'false' : 'true'}"
             ondragstart="${estConnaitre ? '' : `ATELIER_SEQNIV.dragStartObj(event, '${this._escAttr(o.id)}')`}"
             ondragover="ATELIER_SEQNIV.dragOverObj(event, this)"
             ondragleave="ATELIER_SEQNIV.dragLeaveObj(event, this)"
             ondrop="ATELIER_SEQNIV.dropObj(event, this)"
             ondragend="ATELIER_SEQNIV.dragEnd(event)">
          <div class="asm-obj-head" onclick="ATELIER_SEQNIV.ouvrirObj('${this._escAttr(o.id)}')">
            ${estConnaitre
              ? '<span class="asm-obj-handle asm-obj-handle--fixe" title="Le Cours reste en première position"></span>'
              : '<span class="asm-obj-handle" title="Glisser pour réordonner ou changer de partie">⋮⋮</span>'}
            <span class="${codeClass}">${this._esc(o.code)}</span>
            <span class="asm-obj-titre">${this._esc(o.nom || '(sans nom)')}</span>
            <span class="asm-obj-resume">${this._esc(resume)}</span>
            <div class="asm-obj-actions" onclick="event.stopPropagation()">
              <label class="asm-seances-label" title="Nombre de séances prévues pour cet objectif">
                <span class="asm-seances-libelle">${libSeances}</span>
                <input type="number"
                       class="asm-seances-input"
                       min="0" max="999" step="0.5"
                       value="${this._fmtSeances(o.nb_seances)}"
                       placeholder="0"
                       onclick="event.stopPropagation()"
                       onblur="ATELIER_SEQNIV.changerSeancesObj('${this._escAttr(o.id)}', this.value)"
                       onkeydown="if(event.key==='Enter'){this.blur();}">
                <span class="asm-seances-unite">séance(s)</span>
              </label>
              <button class="asm-obj-btn" onclick="ATELIER_SEQNIV.ouvrirObj('${this._escAttr(o.id)}')">
                Ouvrir
              </button>
              <button class="asm-obj-btn asm-obj-btn--danger"
                      onclick="ATELIER_SEQNIV.supprimerObj('${this._escAttr(o.id)}', '${this._escAttr(o.code)}', ${nbExos})">
                ✕
              </button>
            </div>
          </div>
        </div>`;
    }

    _rendreObjOuvert(p, o) {
      const codeConnaitre = `${p.numero - 1}1`;
      const estConnaitre = (o.code === codeConnaitre);
      const codeClass = estConnaitre ? 'asm-obj-code asm-obj-code--connaitre' : 'asm-obj-code';
      const nbExos = ['R','EA','F','A','E'].reduce((acc, s) => {
        const arr = (o.exos_par_serie && o.exos_par_serie[s]) || [];
        return acc + arr.length;
      }, 0);

      // Libellés F/A/E avec niveaux de maîtrise associés
      const labelsCriteres = {
        F: "F — À consolider",
        A: "A — Satisfaisant",
        E: "E — Très bon",
      };
      const critsHtml = ['F', 'A', 'E'].map(c => `
        <div class="asm-crit-row">
          <span class="asm-crit-label asm-crit-label--${c}">${this._esc(labelsCriteres[c])}</span>
          <textarea class="asm-crit-textarea"
                    rows="2"
                    data-obj-id="${this._escAttr(o.id)}"
                    data-champ="critere_${c}">${this._esc(o['critere_' + c] || '')}</textarea>
        </div>`).join('');

      // Méthode liée (en lecture, retirable + éditable). v0.10.3 : bouton
      // "Éditer la méthode" qui ouvre l'atelier dédié.
      const methEtat = this._classeEtatAtome(o.methode_etat_code, 'asm-obj-methode-tag');
      const methBloc = o.methode_id
        ? `
          <div class="asm-obj-methode-row">
            <span>Méthode liée :</span>
            <span class="asm-obj-methode-tag${methEtat}">${this._esc(o.methode_titre || o.methode_id)}</span>
            <button class="asm-obj-btn"
                    onclick="ATELIER_SEQNIV.editerAtome('methode', '${this._escAttr(o.methode_id)}', event)"
                    title="Ouvrir l'atelier Méthode pour éditer">Éditer</button>
            <button class="asm-obj-btn"
                    onclick="ATELIER_SEQNIV.retirerMethode('${this._escAttr(o.id)}')"
                    title="Délier la méthode">Délier</button>
          </div>`
        : '';

      // v0.10.3 — Zone "Notions" en première position. Toujours présente
      // (les obj Connaître ont aussi des notions associées). Drag depuis la
      // sidebar (mode obj exo ouvert OU obj Connaître ouvert — mais ce
      // dernier a la sidebar vide).
      const notions = (o.notions || []);
      const chipsNotions = notions.map(n => {
        const lib = n.titre || n.fichier || n.id;
        const etatChip = this._classeEtatAtome(n.etat_code, 'asm-exo-chip');
        return `
          <span class="asm-exo-chip${etatChip}"
                ondblclick="ATELIER_SEQNIV.editerAtome('notion', '${this._escAttr(n.id)}', event)"
                title="Double-clic pour éditer la notion">
            <span class="asm-item-badge asm-item-badge--N">N</span>
            <span>${this._esc(lib)}</span>
            <button class="asm-exo-chip-rm"
                    onclick="event.stopPropagation();ATELIER_SEQNIV.retirerNotion('${this._escAttr(o.id)}', '${this._escAttr(n.id)}')"
                    title="Retirer">×</button>
          </span>`;
      }).join('');
      const zoneNotions = `
        <div class="asm-obj-exos">
          <div class="asm-obj-exos-titre">Notions</div>
          <div class="asm-obj-exos-zone"
               data-obj-id="${this._escAttr(o.id)}" data-zone="notion-obj"
               ondragover="ATELIER_SEQNIV.dragOver(event, this)"
               ondragleave="ATELIER_SEQNIV.dragLeave(event, this)"
               ondrop="ATELIER_SEQNIV.dropNotion(event, '${this._escAttr(o.id)}')">
            ${chipsNotions || '<span class="asm-obj-exos-vide">Glisse une notion ici.</span>'}
          </div>
        </div>`;

      // v0.10.5 — Pour l'obj Connaître : zone Fiches de résumé en plus
      // de la zone Notions. Les chips sont peuplés asynchrone par
      // _rendreSidebarObjConnaitreOuvert (qui appelle déjà l'API).
      const zoneFiches = estConnaitre ? `
        <div class="asm-obj-exos">
          <div class="asm-obj-exos-titre">Fiches de résumé du livret</div>
          <div class="asm-obj-exos-zone"
               id="asm-fiches-zone-${this._escAttr(o.id)}"
               data-obj-id="${this._escAttr(o.id)}" data-zone="fiche-obj"
               ondragover="ATELIER_SEQNIV.dragOver(event, this)"
               ondragleave="ATELIER_SEQNIV.dragLeave(event, this)"
               ondrop="ATELIER_SEQNIV.dropFiche(event, '${this._escAttr(o.id)}')">
            <span class="asm-obj-exos-vide">Glisse une fiche de résumé ici. Elle sera incluse dans le livret de séquence.</span>
          </div>
        </div>` : '';

      // v0.10.5.3 — Pour l'obj Connaître : seulement la zone Fiches de
      // résumé (la zone Notions a été retirée car les notions sont déjà
      // attachées à la partie via les obj exo, le lien Connaître → notion
      // ne sert à rien dans la chaîne de rendu actuelle ni pour le futur
      // plan de travail).
      // Pour les obj exo : zone Notions + F + A + E (la zone Notions y
      // est utile pour construire les plans de travail).
      let zonesContenu = estConnaitre ? zoneFiches : zoneNotions;
      if (!estConnaitre) {
        const zonesExos = ['F', 'A', 'E'].map(s => {
          const exos = (o.exos_par_serie && o.exos_par_serie[s]) || [];
          const chips = exos.map(e => {
            const ex = e.exercice || {};
            const lib = ex.fichier ? ex.fichier.replace(/\.tex$/i, '') : (e.exercice_id || '?').slice(0, 12);
            const etatChip = this._classeEtatAtome(ex.etat_code, 'asm-exo-chip');
            return `
              <span class="asm-exo-chip${etatChip}"
                    draggable="true"
                    ondblclick="ATELIER_SEQNIV.editerAtome('exercice', '${this._escAttr(e.exercice_id)}', event)"
                    ondragstart="ATELIER_SEQNIV.dragStartExoObj(event, '${this._escAttr(o.id)}', '${this._escAttr(s)}', '${this._escAttr(e.exercice_id)}')"
                    ondragend="ATELIER_SEQNIV.dragEnd(event)"
                    title="Double-clic pour éditer l'exercice">
                <span class="asm-exo-chip-num">${e.ordre}</span>
                <span>${this._esc(lib)}</span>
                <button class="asm-exo-chip-rm"
                        onclick="event.stopPropagation();ATELIER_SEQNIV.retirerExoObj('${this._escAttr(o.id)}', '${this._escAttr(s)}', '${this._escAttr(e.exercice_id)}')"
                        title="Retirer">×</button>
              </span>`;
          }).join('');
          return `
            <div class="asm-obj-exos">
              <div class="asm-obj-exos-titre">Série ${s}</div>
              <div class="asm-obj-exos-zone"
                   data-obj-id="${this._escAttr(o.id)}" data-serie="${this._escAttr(s)}"
                   ondragover="ATELIER_SEQNIV.dragOver(event, this)"
                   ondragleave="ATELIER_SEQNIV.dragLeave(event, this)"
                   ondrop="ATELIER_SEQNIV.dropExoObj(event, '${this._escAttr(o.id)}', '${this._escAttr(s)}')">
                ${chips || '<span class="asm-obj-exos-vide">Glisse un exercice de la série ' + s + ' ici.</span>'}
              </div>
            </div>`;
        }).join('');
        zonesContenu = zoneNotions + zonesExos;
      }

      return `
        <div class="asm-obj open"
             data-obj-id="${this._escAttr(o.id)}"
             data-obj-est-cours="${estConnaitre ? '1' : '0'}">
          <form id="liv-atl-form" onsubmit="return false">
          <div class="asm-obj-head">
            ${estConnaitre
              ? '<span class="asm-obj-handle asm-obj-handle--fixe" title="Le Cours reste en première position"></span>'
              : `<span class="asm-obj-handle"
                  draggable="true"
                  ondragstart="ATELIER_SEQNIV.dragStartObj(event, '${this._escAttr(o.id)}')"
                  ondragend="ATELIER_SEQNIV.dragEnd(event)"
                  title="Glisser pour réordonner ou changer de partie">⋮⋮</span>`}
            <span class="${codeClass}">${this._esc(o.code)}</span>
            <input type="text"
                   class="asm-obj-nom-input"
                   data-obj-id="${this._escAttr(o.id)}"
                   data-champ="nom"
                   value="${this._escAttr(o.nom || '')}"
                   placeholder="Nom de l'objectif">
            <div class="asm-obj-actions">
              <label class="asm-seances-label" title="Nombre de séances prévues pour cet objectif">
                <span class="asm-seances-libelle">${estConnaitre ? 'Cours :' : 'Exos :'}</span>
                <input type="number"
                       class="asm-seances-input"
                       data-obj-id="${this._escAttr(o.id)}"
                       data-champ="nb_seances"
                       min="0" max="999" step="0.5"
                       value="${this._fmtSeances(o.nb_seances)}"
                       placeholder="0"
                       onkeydown="if(event.key==='Enter'){event.preventDefault();}">
                <span class="asm-seances-unite">séance(s)</span>
              </label>
              ${estConnaitre ? '' : `
              <label class="asm-obj-fincycle-label"
                     title="Cocher si cet objectif est un attendu de fin de cycle">
                <input type="checkbox"
                       class="asm-obj-fincycle-input"
                       data-obj-id="${this._escAttr(o.id)}"
                       data-champ="fin_cycle"
                       ${o.fin_cycle === 'O' ? 'checked' : ''}>
                <span class="asm-obj-fincycle-libelle">Fin de cycle</span>
              </label>`}
              <button type="button" class="asm-obj-btn" data-verrou-exempt
                      onclick="ATELIER_SEQNIV.fermerObj()">
                Fermer
              </button>
              <button type="button" class="asm-obj-btn asm-obj-btn--danger" data-verrou-exempt
                      onclick="ATELIER_SEQNIV.supprimerObj('${this._escAttr(o.id)}', '${this._escAttr(o.code)}', ${nbExos})">
                ✕
              </button>
            </div>
          </div>
          <div class="asm-crits">${critsHtml}</div>
          </form>
          <div class="asm-obj-body">
            ${methBloc}
            ${zonesContenu}
          </div>
        </div>`;
    }

    // ── Sidebar : méthodes ou exercices selon objet ouvert ───────────────────

    // ── Sidebar v0.10.3 — sections selon état ────────────────────────────────
    //
    // Trois états possibles selon ce qui est ouvert au centre :
    //
    //   1. Aucun objectif ouvert (this.objOuvert === null) :
    //      Sections : Méthodes, Exos EA, Exos R (par précédence).
    //      Drag : méthodes vers parties (création obj exo) ;
    //             exos EA vers zone Approche d'une partie ;
    //             exos R vers zone Révision d'une partie.
    //
    //   2. Objectif "exo" ouvert (this.objOuvert pointe sur un obj non-Connaître) :
    //      Sections : Notions, Exos F, Exos A, Exos E.
    //      Drag : notions et exos vers les zones de l'objectif ouvert.
    //
    //   3. Objectif "Connaître" ouvert (this.objOuvert pointe sur un obj de code 'X1') :
    //      Sidebar VIDE — l'objectif Connaître ne reçoit ni méthode ni exo,
    //      seulement des critères et (à venir) des notions.
    //
    // Les listes affichent un badge d'affectation à droite : le ou les codes
    // des objectifs dans lesquels l'élément est placé (pour exos et notions),
    // ou "P{N}" pour les exos R/EA déjà placés sur une partie.

    _rendreSidebar() {
      const sb = this._sidebarBody();
      if (!sb) return;
      // v0.17.3 — Aperçu PDF au survol des atomes du catalogue (lignes
      // draggables instrumentées avec data-atome-type/id dans _renduItem).
      // Listener délégué sur le conteneur stable, idempotent.
      this._installerApercuSurvol(sb);
      if (!this.objOuvert) {
        this._rendreSidebarObjsFermes();
        return;
      }
      // Un objectif est ouvert : déterminer s'il s'agit du "Connaître" ou
      // d'un objectif "exo" classique.
      const obj = this._trouverObj(this.objOuvert);
      if (!obj) {
        this._rendreSidebarObjsFermes();
        return;
      }
      const partie = this._trouverPartiePourObj(this.objOuvert);
      const codeConnaitre = partie ? `${partie.numero - 1}1` : '';
      const estConnaitre = obj.code === codeConnaitre;
      if (estConnaitre) {
        this._rendreSidebarObjConnaitreOuvert();
      } else {
        this._rendreSidebarObjExoOuvert();
      }
    }

    // v0.16.6 — Délègue au module pur (testé). NB : cette fonction était définie
    // DEUX FOIS dans le fichier procédural (doublon mort, la 2e écrasait la 1re) ;
    // le doublon a été supprimé en v0.16.6.
    _trouverPartiePourObj(objId) {
      return _PUR.trouverPartiePourObj(this.data, objId);
    }

    // ── Helpers : repérer ce qui est déjà placé ──────────────────────────────

    _placementsExos() {
      return _PUR.placementsExos(this.data);
    }

    _placementsExosRA() {
      return _PUR.placementsExosRA(this.data);
    }

    _placementsNotions() {
      return _PUR.placementsNotions(this.data);
    }

    _placementsMethodes() {
      return _PUR.placementsMethodes(this.data);
    }

    // Construit le HTML d'une section repliable de la sidebar.
    // header = label, count, etc. ; body = HTML déjà construit pour le contenu.
    _renduSection(serieKey, label, count, bodyHtml, opts = {}) {
      const closed = opts.closedByDefault ? ' collapsed' : '';
      return `
        <div class="asm-cat${closed}" data-serie="${this._escAttr(serieKey)}">
          <div class="asm-cat-head" onclick="this.parentElement.classList.toggle('collapsed')">
            <span>${this._esc(label)}</span>
            <span class="asm-cat-count">${count}</span>
          </div>
          <div class="asm-cat-body">${bodyHtml}</div>
        </div>`;
    }

    // Construit une ligne de la sidebar pour un atome (méthode/notion/exo).
    // - badge      : caractère(s) court(s) à gauche (M, N, F, A, E, EA, R)
    // - badgeClass : suffixe de classe pour la couleur (M/N/F/A/E/EA/R)
    // - lib        : libellé court
    // - placedTags : tableau de strings (codes obj ou P{N}) ; si non vide,
    //                affiché à droite en grisé.
    // - dragData   : objet {kind, ...payload} pour DRAG (null si non draggable).
    // - dblclickHandler : nom de la fonction à appeler en double-clic
    //                     ('ATELIER_SEQNIV.editerAtome(...)' par exemple), ou null.
    // - editButton : HTML du bouton "Éditer" optionnel à coller à droite.
    _renduItem({
      badge, badgeClass, lib, libTitle = null, placedTags = [],
      dragData = null, dblclickHandler = null, editButton = '',
      etatCode = null,  // v0.10.4 — code d'état d'édition de l'atome
    }) {
      const cls = ['asm-item'];
      if (placedTags.length > 0) cls.push('placed-marker');
      const tagsHtml = placedTags.length === 0 ? '' :
        `<span class="asm-item-placed-tag">${placedTags.map(t => this._esc(t)).join(' ')}</span>`;
      let dragAttrs = '';
      if (dragData) {
        // Encoder dragData en JSON et le déposer dans data-drag-payload
        // pour récupération propre dans le dragstart.
        const payload = JSON.stringify(dragData).replace(/"/g, '&quot;');
        dragAttrs = `draggable="true"
                     data-drag-payload="${payload}"
                     ondragstart="ATELIER_SEQNIV.dragStartFromSidebar(event)"
                     ondragend="ATELIER_SEQNIV.dragEnd(event)"`;
      }
      const dblclick = dblclickHandler
        ? `ondblclick="${dblclickHandler}"` : '';
      const titleAttr = libTitle != null ? `title="${this._escAttr(libTitle)}"` : '';
      // v0.17.3 — Attributs d'aperçu au survol : on dérive (type, id) d'atome
      // compilable depuis dragData (kind → type). Seules les lignes draggables
      // (atomes du catalogue) sont concernées dans cette livraison.
      let apercuAttrs = '';
      if (dragData) {
        const map = {
          methode:       ['methode',  dragData.methode_id],
          notion:        ['notion',   dragData.notion_id],
          fiche:         ['fiche',    dragData.fiche_id],
          exo_catalogue: ['exercice', dragData.exo_id],
        };
        const paire = map[dragData.kind];
        if (paire && paire[1]) {
          apercuAttrs = `data-atome-type="${this._escAttr(paire[0])}" `
            + `data-atome-id="${this._escAttr(paire[1])}"`;
        }
      }
      // v0.10.4 — Pastille d'état d'édition (verte si validé, grise sinon)
      const etatHtml = etatCode
        ? `<span class="asm-item-etat-badge atome-etat--${this._escAttr(etatCode)}"
                title="${etatCode === 'valide' ? 'Validé' : 'En cours'}"></span>`
        : '';
      return `
        <div class="${cls.join(' ')}" ${dragAttrs} ${dblclick} ${apercuAttrs}>
          <span class="asm-item-badge asm-item-badge--${this._escAttr(badgeClass)}">${this._esc(badge)}</span>
          <span class="asm-item-lib" ${titleAttr}>${this._esc(lib)}</span>
          ${etatHtml}
          ${tagsHtml}
          ${editButton}
        </div>`;
    }

    // ── Sidebar mode 1 : aucun objectif ouvert ──────────────────────────────

    async _rendreSidebarObjsFermes() {
      const sn = this._sn();
      if (!sn) return;
      this._sidebarTitre().textContent = 'Séquence';
      this._sidebarHint().textContent  = `${sn.niveau} ${sn.sequence_code}`;

      const sb = this._sidebarBody();
      sb.innerHTML = '<div class="asm-sidebar-empty">Chargement…</div>';

      // 1. Charger en parallèle : méthodes, exos EA de la séquence courante,
      //    et exos A des séquences précédentes (pour les R).
      const precs = (this.data.precedences || []);
      const promesseMethodes = apiJson('GET',
        `/api/v2/methodes?niveau=${encodeURIComponent(sn.niveau)}&sequence=${encodeURIComponent(sn.sequence_code)}`);
      const promesseEA = apiJson('GET',
        `/api/v2/exos-disponibles?niveau=${encodeURIComponent(sn.niveau)}` +
        `&sequence=${encodeURIComponent(sn.sequence_code)}&serie_cible=AE`);
      const promessesR = precs.map(p =>
        apiJson('GET',
          `/api/v2/exos-disponibles?niveau=${encodeURIComponent(p.precedent_niveau)}` +
          `&sequence=${encodeURIComponent(p.precedent_seq)}&serie_cible=A`),
      );
      const [repMethodes, repEA, ...reponsesR] = await Promise.all(
        [promesseMethodes, promesseEA, ...promessesR],
      );

      // Calculer les placements pour les badges
      const placeesM = this._placementsMethodes();
      const placeesEAR = this._placementsExosRA();

      let html = '';

      // ── Section Méthodes ──────────────────────────────────────────────
      {
        const methodes = (repMethodes.ok && repMethodes.data && repMethodes.data.methodes) || [];
        const items = methodes.map(m => {
          const lib = m.titre || m.fichier || m.id;
          const placee = placeesM.get(m.id);
          return this._renduItem({
            badge: 'M', badgeClass: 'M',
            lib, libTitle: lib,
            placedTags: placee ? [placee] : [],
            // Méthode placée : non draggable. Sinon, drag vers une partie.
            dragData: placee ? null : {kind: 'methode', methode_id: m.id, libelle: lib},
            // Bouton Éditer toujours présent
            editButton: `<button class="asm-item-edit"
                                 onclick="event.stopPropagation();ATELIER_SEQNIV.editerAtome('methode', '${this._escAttr(m.id)}', event)"
                                 title="Éditer la méthode">✎</button>`,
            etatCode: m.etat_code || 'en_cours',
          });
        }).join('');
        const corps = methodes.length > 0
          ? items
          : '<div class="asm-sidebar-empty" style="padding:6px 4px">— aucune —</div>';
        html += this._renduSection('M', 'Méthodes', methodes.length, corps);
      }

      // ── Section Exos EA ───────────────────────────────────────────────
      {
        const exos = (repEA.ok && repEA.data && repEA.data.exos) || [];
        const items = exos.map(e => {
          const lib = e.fichier ? e.fichier.replace(/\.tex$/i, '') : (e.id || '?').slice(0, 12);
          const placeStr = placeesEAR.get(e.id);
          return this._renduItem({
            badge: 'AE', badgeClass: 'AE',
            lib, libTitle: lib,
            placedTags: placeStr ? [placeStr] : [],
            dragData: placeStr ? null
              : {kind: 'exo_catalogue', exo_id: e.id, serie: 'AE', libelle: lib,
                 source_niveau: sn.niveau, source_sequence: sn.sequence_code},
            dblclickHandler: `ATELIER_SEQNIV.editerAtome('exercice', '${this._escAttr(e.id)}', event)`,
            etatCode: e.etat_code || 'en_cours',
          });
        }).join('');
        const corps = exos.length > 0
          ? items
          : '<div class="asm-sidebar-empty" style="padding:6px 4px">— aucun —</div>';
        html += this._renduSection('AE', 'Exos d\'approche (AE)', exos.length, corps);
      }

      // ── Sections Exos R par précédence ────────────────────────────────
      if (precs.length === 0) {
        html += `
          <div class="asm-cat collapsed" data-serie="R-vide">
            <div class="asm-cat-head" onclick="this.parentElement.classList.toggle('collapsed')">
              <span>Exos de révision (R)</span>
              <span class="asm-cat-count">0</span>
            </div>
            <div class="asm-cat-body">
              <div class="asm-sidebar-empty" style="padding:6px 4px">
                Aucune précédence déclarée.
              </div>
            </div>
          </div>`;
      } else {
        for (let i = 0; i < precs.length; i++) {
          const prec = precs[i];
          const repR = reponsesR[i];
          const exos = (repR && repR.ok && repR.data && repR.data.exos) || [];
          const label = `R · ${prec.precedent_niveau}/${prec.precedent_seq}`;
          const items = exos.map(e => {
            const lib = e.fichier ? e.fichier.replace(/\.tex$/i, '') : (e.id || '?').slice(0, 12);
            const placeStr = placeesEAR.get(e.id);
            return this._renduItem({
              badge: 'R', badgeClass: 'R',
              lib, libTitle: lib,
              placedTags: placeStr ? [placeStr] : [],
              dragData: placeStr ? null
                : {kind: 'exo_catalogue', exo_id: e.id, serie: 'R', libelle: lib,
                   source_niveau: prec.precedent_niveau, source_sequence: prec.precedent_seq},
              dblclickHandler: `ATELIER_SEQNIV.editerAtome('exercice', '${this._escAttr(e.id)}', event)`,
              etatCode: e.etat_code || 'en_cours',
            });
          }).join('');
          const corps = exos.length > 0
            ? items
            : '<div class="asm-sidebar-empty" style="padding:6px 4px">— aucun —</div>';
          html += this._renduSection(`R-${i}`, label, exos.length, corps);
        }
      }

      sb.innerHTML = html;
    }

    // ── Sidebar mode 2 : objectif "exo" ouvert ───────────────────────────────

    async _rendreSidebarObjExoOuvert() {
      const sn = this._sn();
      if (!sn) return;
      this._sidebarTitre().textContent = 'Objectif ouvert';
      this._sidebarHint().textContent  = '';

      const sb = this._sidebarBody();
      sb.innerHTML = '<div class="asm-sidebar-empty">Chargement…</div>';

      // Notions de la séquence + exos F/A/E
      const series = ['F', 'A', 'E'];
      const promesseNotions = apiJson('GET',
        `/api/v2/notions-de-sequence?niveau=${encodeURIComponent(sn.niveau)}&sequence=${encodeURIComponent(sn.sequence_code)}`);
      const promessesExos = series.map(s =>
        apiJson('GET',
          `/api/v2/exos-disponibles?niveau=${encodeURIComponent(sn.niveau)}` +
          `&sequence=${encodeURIComponent(sn.sequence_code)}&serie_cible=${encodeURIComponent(s)}`),
      );
      const [repNotions, ...reponsesExos] = await Promise.all(
        [promesseNotions, ...promessesExos],
      );

      const placeesN = this._placementsNotions();
      const placeesExos = this._placementsExos();

      let html = '';

      // ── Section Notions ───────────────────────────────────────────────
      {
        const notions = (repNotions.ok && repNotions.data && repNotions.data.notions) || [];
        const items = notions.map(n => {
          const lib = n.titre || n.fichier || n.id;
          const codes = placeesN.get(n.id) || [];
          return this._renduItem({
            badge: 'N', badgeClass: 'N',
            lib, libTitle: lib,
            placedTags: codes,
            dragData: {kind: 'notion', notion_id: n.id, libelle: lib},
            dblclickHandler: `ATELIER_SEQNIV.editerAtome('notion', '${this._escAttr(n.id)}', event)`,
            etatCode: n.etat_code || 'en_cours',
          });
        }).join('');
        const corps = notions.length > 0
          ? items
          : '<div class="asm-sidebar-empty" style="padding:6px 4px">— aucune —</div>';
        html += this._renduSection('N', 'Notions', notions.length, corps);
      }

      // ── Sections Exos F/A/E ───────────────────────────────────────────
      for (let i = 0; i < series.length; i++) {
        const s = series[i];
        const exos = (reponsesExos[i].ok && reponsesExos[i].data && reponsesExos[i].data.exos) || [];
        const items = exos.map(e => {
          const lib = e.fichier ? e.fichier.replace(/\.tex$/i, '') : (e.id || '?').slice(0, 12);
          const codes = placeesExos.get(e.id) || [];
          return this._renduItem({
            badge: s, badgeClass: s,
            lib, libTitle: lib,
            placedTags: codes,
            dragData: {kind: 'exo_catalogue', exo_id: e.id, serie: s, libelle: lib,
                       source_niveau: sn.niveau, source_sequence: sn.sequence_code},
            dblclickHandler: `ATELIER_SEQNIV.editerAtome('exercice', '${this._escAttr(e.id)}', event)`,
            etatCode: e.etat_code || 'en_cours',
          });
        }).join('');
        const corps = exos.length > 0
          ? items
          : '<div class="asm-sidebar-empty" style="padding:6px 4px">— aucun —</div>';
        html += this._renduSection(s, `Exos série ${s}`, exos.length, corps);
      }

      sb.innerHTML = html;
    }

    // ── Sidebar mode 3 : objectif Connaître ouvert ───────────────────────────

    async _rendreSidebarObjConnaitreOuvert() {
      this._sidebarTitre().textContent = 'Fiches de résumé';
      this._sidebarHint().textContent = 'de la partie';
      const sb = this._sidebarBody();
      sb.innerHTML = '<div class="asm-sidebar-empty">Chargement…</div>';

      // v0.10.5 — Trouver la partie de l'objectif ouvert
      const partie = this._trouverPartiePourObj(this.objOuvert);
      if (!partie) {
        sb.innerHTML = '<div class="asm-sidebar-empty">Partie introuvable.</div>';
        return;
      }
      // Lister les fiches dont l'objectif lié est dans cette partie
      const repFiches = await apiJson(
        'GET',
        `/api/parties/${encodeURIComponent(partie.id)}/fiches-disponibles`,
      );
      // Lister les fiches déjà attachées à ce Connaître
      const repAttachees = await apiJson(
        'GET',
        `/api/objectifs-v2/${encodeURIComponent(this.objOuvert)}/fiches`,
      );
      const fiches = (repFiches.ok && repFiches.data && repFiches.data.fiches) || [];
      const attachees = (repAttachees.ok && repAttachees.data && repAttachees.data.fiches) || [];
      const idsAttachees = new Set(attachees.map(f => f.id));

      // ── Sidebar ─────────────────────────────────────────────────────────
      if (fiches.length === 0) {
        sb.innerHTML = `
          <div class="asm-sidebar-empty">
            Aucune fiche de résumé pour les objectifs de cette partie.
            Pour en créer, ouvrir l'atelier <em>Fiche de résumé</em>.
          </div>`;
      } else {
        const items = fiches.map(f => {
          const lib = f.titre || `Fiche ${f.num_fiche}` || f.id;
          const placedTags = idsAttachees.has(f.id) ? ['attachée'] : [];
          const dragData = idsAttachees.has(f.id)
            ? null  // déjà attachée → non draggable
            : {kind: 'fiche', fiche_id: f.id, libelle: lib};
          return this._renduItem({
            badge: 'F', badgeClass: 'M',
            lib, libTitle: lib + (f.objectif_code ? ` (obj ${f.objectif_code})` : ''),
            placedTags,
            dragData,
            dblclickHandler: `ATELIER_SEQNIV.editerFiche('${this._escAttr(f.id)}', event)`,
            etatCode: f.etat_code || 'en_cours',
          });
        }).join('');
        sb.innerHTML = items;
      }

      // ── Zone d'attachement dans l'obj Connaître ouvert ──────────────────
      // Peuple les chips des fiches déjà attachées avec un bouton de retrait.
      const zoneAttach = document.getElementById(
        `asm-fiches-zone-${this.objOuvert}`,
      );
      if (zoneAttach) {
        if (attachees.length === 0) {
          zoneAttach.innerHTML = '<span class="asm-obj-exos-vide">Glisse une fiche de résumé ici. Elle sera incluse dans le livret de séquence.</span>';
        } else {
          zoneAttach.innerHTML = attachees.map(f => {
            const lib = f.titre || `Fiche ${f.num_fiche}` || f.id;
            const etatChip = this._classeEtatAtome(f.etat_code, 'asm-exo-chip');
            return `
              <span class="asm-exo-chip${etatChip}"
                    ondblclick="ATELIER_SEQNIV.editerFiche('${this._escAttr(f.id)}', event)"
                    title="Double-clic pour éditer la fiche">
                <span class="asm-item-badge asm-item-badge--M">F</span>
                <span>${this._esc(lib)}</span>
                <button class="asm-exo-chip-rm"
                        onclick="event.stopPropagation();ATELIER_SEQNIV.retirerFiche('${this._escAttr(this.objOuvert)}', '${this._escAttr(f.id)}')"
                        title="Détacher la fiche">×</button>
              </span>`;
          }).join('');
        }
      }
    }

    // v0.10.5 — Édition rapide d'une fiche : bascule vers l'atelier Fiche
    // et y charge la fiche. Symétrique de editerAtome pour les
    // notions/méthodes/exos.
    // v0.18.2.1 — Aligné sur editerAtome (type 'fiche') pour bénéficier du
    // Ctrl/⌘+(double-)clic = nouvel onglet, comme les autres atomes référencés.
    // `event` optionnel : sans lui, ouverture en place (appel programmatique).
    editerFiche(ficheId, event) {
      this.editerAtome('fiche', ficheId, event);
    }

    // ── Drag handlers : sources ──────────────────────────────────────────────

    dragStartMethode(ev, methodeId, libelle) {
      this._drag = {kind: 'methode', methode_id: methodeId, libelle: libelle};
      try { ev.dataTransfer.effectAllowed = 'move'; ev.dataTransfer.setData('text/plain', methodeId); } catch (_) {}
      ev.target.classList.add('dragging');
    }

    dragStartExoCatalogue(ev, exoId, serie, libelle) {
      this._drag = {kind: 'exo_catalogue', exo_id: exoId, serie: serie, libelle: libelle};
      try { ev.dataTransfer.effectAllowed = 'move'; ev.dataTransfer.setData('text/plain', exoId); } catch (_) {}
      ev.target.classList.add('dragging');
    }

    dragStartExoRA(ev, partieId, type, exoId) {
      this._drag = {kind: 'exo_ra_existant', partie_id: partieId, type: type, exo_id: exoId};
      try { ev.dataTransfer.effectAllowed = 'move'; ev.dataTransfer.setData('text/plain', exoId); } catch (_) {}
      ev.stopPropagation();
      ev.target.classList.add('dragging');
    }

    dragStartExoObj(ev, objId, serie, exoId) {
      this._drag = {kind: 'exo_obj_existant', obj_id: objId, serie: serie, exo_id: exoId};
      try { ev.dataTransfer.effectAllowed = 'move'; ev.dataTransfer.setData('text/plain', exoId); } catch (_) {}
      ev.stopPropagation();
      ev.target.classList.add('dragging');
    }

    dragStartPartie(ev, partieId) {
      this._drag = {kind: 'partie', partie_id: partieId};
      try { ev.dataTransfer.effectAllowed = 'move'; ev.dataTransfer.setData('text/plain', partieId); } catch (_) {}
      ev.target.classList.add('dragging');
    }

    dragStartObj(ev, objId) {
      this._drag = {kind: 'obj', obj_id: objId};
      try { ev.dataTransfer.effectAllowed = 'move'; ev.dataTransfer.setData('text/plain', objId); } catch (_) {}
      ev.stopPropagation();
      ev.target.classList.add('dragging');
    }

    dragEnd(ev) {
      if (ev && ev.target && ev.target.classList) ev.target.classList.remove('dragging');
      // Nettoie les overlay drag-over restants
      document.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
      document.querySelectorAll('.drag-over-partie').forEach(el => el.classList.remove('drag-over-partie'));
      this._drag = null;
    }

    // v0.10.3 — Handler unifié pour les drag depuis la sidebar (méthode,
    // notion, exo). Le payload est sérialisé dans data-drag-payload de
    // l'élément, ce qui évite d'avoir 4-5 handlers spécifiques avec des
    // signatures différentes.
    dragStartFromSidebar(ev) {
      const el = ev.currentTarget;
      if (!el) return;
      const raw = el.dataset.dragPayload || el.getAttribute('data-drag-payload');
      if (!raw) return;
      let payload;
      try { payload = JSON.parse(raw); } catch (e) { return; }
      this._drag = payload;
      try {
        ev.dataTransfer.effectAllowed = 'move';
        ev.dataTransfer.setData('text/plain', payload.methode_id || payload.notion_id || payload.exo_id || '');
      } catch (_) {}
      el.classList.add('dragging');
    }

    // v0.10.3 — Édition rapide d'un atome (notion, méthode, exercice) :
    // bascule vers son atelier dédié et le sélectionne. Réutilise la
    // fonction utilitaire compilBatchOuvrirAtelier déjà présente dans
    // app.js (initialement écrite pour le rapport de compilation par lot,
    // mais réutilisable telle quelle).
    // v0.18.2 — Ouvre l'atome. Si `event` est fourni et Ctrl/⌘/Shift+clic
    // (ou clic-molette), ouvre dans un NOUVEL ONGLET ; sinon en place.
    // niveau/seq optionnels : si omis, on prend la séquence courante de
    // l'assemblage (les exos de Révision peuvent provenir d'une autre
    // séquence → passer leur origin_niveau/origin_seq explicitement).
    //
    // v0.18.2.1 — Correctif : ici les handlers sont des onclick/ondblclick
    // posés sur des <span>/<div> (PAS des <a href>). On ne peut donc pas
    // déléguer à ouvrirAtomeDepuisEvent en comptant sur le navigateur pour
    // suivre un lien : il faut ouvrir le nouvel onglet nous-mêmes via
    // window.open quand c'est un clic « nouvel onglet ».
    editerAtome(type, id, event, niveau, sequence) {
      if (typeof window.compilBatchOuvrirAtelier !== 'function') {
        this._status("Fonction d'ouverture d'atelier indisponible.", true);
        return;
      }
      const sn = (this.data && this.data.sequence_par_niveau) || {};
      const niv = niveau || sn.niveau || '';
      const seq = sequence || sn.sequence_code || '';

      // Clic « nouvel onglet » : Ctrl (Win/Linux), ⌘ (Mac), Shift, ou molette.
      const veutNouvelOnglet = event && (event.ctrlKey || event.metaKey
                               || event.shiftKey || event.button === 1);
      if (veutNouvelOnglet && typeof window.deeplinkAtomeURL === 'function') {
        const url = window.deeplinkAtomeURL(type, id, niv, seq);
        if (url) {
          if (event && typeof event.preventDefault === 'function') {
            event.preventDefault();
          }
          window.open(url, '_blank', 'noopener');
          return;
        }
        // Pas d'URL possible (niveau/seq manquants) : on retombe en place.
      }

      // Clic simple (ou appel programmatique) : ouverture en place.
      window.compilBatchOuvrirAtelier(type, id, niv, seq);
    }

    // ── Drag handlers : zones de destination génériques ──────────────────────

    dragOver(ev, zone) {
      if (!this._drag) return;
      // Filtre : selon le type de zone et le type de drag, on autorise ou non
      const dz = zone.dataset.zone;
      const okR  = (dz === 'R'  && this._drag.kind === 'exo_catalogue' && this._drag.serie === 'R');
      // v0.18.3 — `dz` est le RÔLE de la zone ('EA' = approche, inchangé) ;
      // `_drag.serie` est la SÉRIE de l'exo catalogue, unifiée en 'AE'.
      const okEA = (dz === 'EA' && this._drag.kind === 'exo_catalogue' && this._drag.serie === 'AE');
      const okM  = (dz === 'methode' && this._drag.kind === 'methode');
      // Zone exos d'un objectif (data-serie présent F/A/E)
      const okExoObj = (zone.dataset.serie && this._drag.kind === 'exo_catalogue'
                        && ['F', 'A', 'E'].includes(this._drag.serie)
                        && zone.dataset.serie === this._drag.serie);
      // v0.10.3 : zone notion d'un objectif (data-zone='notion-obj')
      const okNotionObj = (dz === 'notion-obj' && this._drag.kind === 'notion');
      // v0.10.5 : zone fiche d'un objectif Connaître (data-zone='fiche-obj')
      const okFicheObj = (dz === 'fiche-obj' && this._drag.kind === 'fiche');
      if (!(okR || okEA || okM || okExoObj || okNotionObj || okFicheObj)) return;
      ev.preventDefault();
      try { ev.dataTransfer.dropEffect = 'move'; } catch (_) {}
      zone.classList.add('drag-over');
    }

    dragLeave(ev, zone) {
      zone.classList.remove('drag-over');
    }

    // ── Drop : méthode → partie (création d'objectif) ────────────────────────

    async dropMethode(ev, partieId) {
      // v0.16.9 — garde régime mixte : pas d'opération de structure
      // tant qu'une saisie de l'objectif ouvert n'est pas enregistrée.
      if (!this._garderAvantStructure()) return;
      ev.preventDefault();
      document.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
      if (!this._drag || this._drag.kind !== 'methode') return;
      const methodeId = this._drag.methode_id;
      const libelle = this._drag.libelle;
      this._drag = null;

      // 1. Créer un nouvel objectif via les routes existantes : il n'y a pas
      //    de fonction directe « créer objectif simple ». Utilise le helper
      //    de création par lien méthode : on passe par /api/v2/parties/<id>/
      //    objectif-connaitre pour Connaître, mais pour les méthodes on doit
      //    créer un objectif vide puis lui assigner la méthode.
      //    Comme la route existante `lier_methode_a_objectif` exige un objet
      //    pré-existant, on contourne en utilisant la route legacy qu'on n'a
      //    pas. À la place, j'appelle un endpoint dédié POST
      //    /api/v2/parties/<id>/objectif-via-methode (TODO : créer route).
      //
      //    À ce stade de v0.10.1, je préfère ne pas inventer une nouvelle
      //    route à la volée. Solution propre : créer l'objectif via la route
      //    historique `creer_objectif` si elle existe ; sinon, demander.
      //
      //    Workaround temporaire : déléguer au backend via un POST sur la
      //    route activate-connaitre, mais en lui passant un nom différent...
      //    NON : ça créerait quand même un Connaître.
      //
      //    Choix pragmatique : on ajoute discrètement, dans la suite de cette
      //    livraison, une mini-route POST /api/v2/parties/<id>/objectif (qui
      //    crée un objectif minimal avec code auto-incrémenté + assignation
      //    de méthode). Voir backend.

      const rep = await apiJson('POST',
        `/api/v2/parties/${encodeURIComponent(partieId)}/objectif`,
        {methode_id: methodeId, nom: libelle});
      if (!rep.ok) {
        this._status(`Échec création objectif : ${(rep.data && rep.data.error) || rep.status}`, true);
        return;
      }
      this._status(`Méthode placée : ${libelle}`, false);
      // L'objectif vient d'être créé : on l'ouvre directement
      const nouvelObj = rep.data;
      await this._setObjOuvert(nouvelObj.id);
      await this.rafraichir({preserverScroll: true});
    }

    // ── Drop : exo catalogue → zone R/EA d'une partie ────────────────────────

    async dropRA(ev, partieId, type) {
      // v0.16.9 — garde régime mixte : pas d'opération de structure
      // tant qu'une saisie de l'objectif ouvert n'est pas enregistrée.
      if (!this._garderAvantStructure()) return;
      ev.preventDefault();
      document.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
      if (!this._drag) return;

      if (this._drag.kind === 'exo_catalogue') {
        // Pour la révision (R), il faut indiquer origin_*. La barre de
        // gauche en mode "objectif fermé" = méthodes uniquement, donc on
        // ne peut pas drop d'exo catalogue ici dans ce cas. Mais quand un
        // objectif est ouvert, la sidebar est en mode exos et permet de
        // glisser jusqu'aux zones R/EA des parties.
        const exoId = this._drag.exo_id;
        const sn = this._sn();
        const body = {type: type, exercice_id: exoId};
        if (type === 'R') {
          // L'origine n'est pas forcément le n-1, mais c'est la convention.
          // On extrait du payload : si l'exo est dans la séquence courante,
          // c'est anormal pour de la révision. Laisse origin_* à null —
          // l'UI v2 affiche tel quel.
          // Fallback : si l'exo vient d'un autre niveau, on suppose qu'il
          // est connu via DATA.parties (peu probable). On laisse vide.
        }
        const rep = await apiJson('POST',
          `/api/v2/parties/${encodeURIComponent(partieId)}/exos-revision-approche`,
          body);
        if (!rep.ok) {
          const code = (rep.data && rep.data.code) || '';
          if (code === 'exo_revision_approche_deja_present') {
            this._status('Cet exercice est déjà dans cette zone.', true);
          } else {
            this._status(`Erreur ajout exo : ${(rep.data && rep.data.error) || rep.status}`, true);
          }
          this._drag = null;
          return;
        }
        this._status('Exo ajouté.', false);
        this._drag = null;
        await this.rafraichir({preserverScroll: true});
      } else if (this._drag.kind === 'exo_ra_existant') {
        // Cross-zone drag (R↔EA) ou cross-partie : non géré v0.10.1
        this._status('Déplacement entre zones non disponible. Retire et redépose.', true);
        this._drag = null;
      }
    }

    // ── Drop : exo catalogue → zone série d'un objectif ouvert ───────────────

    async dropExoObj(ev, objId, serie) {
      // v0.16.9 — garde régime mixte : pas d'opération de structure
      // tant qu'une saisie de l'objectif ouvert n'est pas enregistrée.
      if (!this._garderAvantStructure()) return;
      ev.preventDefault();
      document.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
      if (!this._drag || this._drag.kind !== 'exo_catalogue') {
        this._drag = null;
        return;
      }
      const exoId = this._drag.exo_id;
      this._drag = null;

      const rep = await apiJson('POST',
        `/api/v2/objectifs/${encodeURIComponent(objId)}/exos`,
        {serie: serie, exercice_id: exoId});
      if (!rep.ok) {
        const code = (rep.data && rep.data.code) || '';
        if (code === 'exo_deja_present') {
          this._status('Cet exercice est déjà dans cette série.', true);
        } else {
          this._status(`Erreur ajout exo : ${(rep.data && rep.data.error) || rep.status}`, true);
        }
        return;
      }
      this._status('Exo ajouté.', false);
      await this.rafraichir({preserverScroll: true});
    }

    // v0.10.3 — Drop d'une notion sur un objectif (zone "notion-obj")
    async dropNotion(ev, objId) {
      // v0.16.9 — garde régime mixte : pas d'opération de structure
      // tant qu'une saisie de l'objectif ouvert n'est pas enregistrée.
      if (!this._garderAvantStructure()) return;
      ev.preventDefault();
      document.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
      if (!this._drag || this._drag.kind !== 'notion') {
        this._drag = null;
        return;
      }
      const notionId = this._drag.notion_id;
      this._drag = null;
      const rep = await apiJson('POST',
        `/api/v2/objectifs/${encodeURIComponent(objId)}/notions`,
        {notion_id: notionId});
      if (!rep.ok) {
        const code = (rep.data && rep.data.code) || '';
        if (code === 'notion_deja_presente') {
          this._status('Cette notion est déjà dans cet objectif.', true);
        } else {
          this._status(`Erreur ajout notion : ${(rep.data && rep.data.error) || rep.status}`, true);
        }
        return;
      }
      this._status('Notion ajoutée.', false);
      await this.rafraichir({preserverScroll: true});
    }

    // v0.10.5 — Drop d'une fiche sur l'obj Connaître (zone "fiche-obj")
    async dropFiche(ev, objId) {
      // v0.16.9 — garde régime mixte : pas d'opération de structure
      // tant qu'une saisie de l'objectif ouvert n'est pas enregistrée.
      if (!this._garderAvantStructure()) return;
      ev.preventDefault();
      document.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
      if (!this._drag || this._drag.kind !== 'fiche') {
        this._drag = null;
        return;
      }
      const ficheId = this._drag.fiche_id;
      this._drag = null;
      const rep = await apiJson('POST',
        `/api/objectifs-v2/${encodeURIComponent(objId)}/fiches`,
        {fiche_id: ficheId});
      if (!rep.ok) {
        const code = (rep.data && rep.data.code) || '';
        if (code === 'fiche_deja_presente') {
          this._status('Cette fiche est déjà attachée à cet objectif.', true);
        } else {
          this._status(`Erreur ajout fiche : ${(rep.data && rep.data.error) || rep.status}`, true);
        }
        return;
      }
      this._status('Fiche attachée.', false);
      // Re-rendu : la sidebar et la zone fiches
      await this.rafraichir({preserverScroll: true});
      // Re-rendre la sidebar pour mettre à jour le tag "attachée"
      if (this.objOuvert) this._rendreSidebar();
    }

    // v0.10.5 — Détacher une fiche d'un objectif Connaître
    async retirerFiche(objId, ficheId) {
      // v0.16.9 — garde régime mixte : pas d'opération de structure
      // tant qu'une saisie de l'objectif ouvert n'est pas enregistrée.
      if (!this._garderAvantStructure()) return;
      const rep = await apiJson(
        'DELETE',
        `/api/objectifs-v2/${encodeURIComponent(objId)}/fiches/${encodeURIComponent(ficheId)}`,
      );
      if (!rep.ok) {
        this._status('Erreur retrait fiche.', true);
        return;
      }
      this._status('Fiche détachée.', false);
      await this.rafraichir({preserverScroll: true});
      if (this.objOuvert) this._rendreSidebar();
    }

    // ── Suppression / retrait ────────────────────────────────────────────────

    async retirerExoRA(partieId, type, exoId) {
      // v0.16.9 — garde régime mixte : pas d'opération de structure
      // tant qu'une saisie de l'objectif ouvert n'est pas enregistrée.
      if (!this._garderAvantStructure()) return;
      const rep = await apiJson('DELETE',
        `/api/v2/parties/${encodeURIComponent(partieId)}/exos-revision-approche/${encodeURIComponent(type)}/${encodeURIComponent(exoId)}`);
      if (!rep.ok) {
        this._status('Erreur retrait exo', true);
        return;
      }
      this._status('Exo retiré.', false);
      await this.rafraichir({preserverScroll: true});
    }

    async retirerExoObj(objId, serie, exoId) {
      // v0.16.9 — garde régime mixte : pas d'opération de structure
      // tant qu'une saisie de l'objectif ouvert n'est pas enregistrée.
      if (!this._garderAvantStructure()) return;
      const rep = await apiJson('DELETE',
        `/api/v2/objectifs/${encodeURIComponent(objId)}/exos/${encodeURIComponent(serie)}/${encodeURIComponent(exoId)}`);
      if (!rep.ok) {
        this._status('Erreur retrait exo', true);
        return;
      }
      this._status('Exo retiré.', false);
      await this.rafraichir({preserverScroll: true});
    }

    // v0.10.3 — Retirer une notion d'un objectif
    async retirerNotion(objId, notionId) {
      // v0.16.9 — garde régime mixte : pas d'opération de structure
      // tant qu'une saisie de l'objectif ouvert n'est pas enregistrée.
      if (!this._garderAvantStructure()) return;
      const rep = await apiJson('DELETE',
        `/api/v2/objectifs/${encodeURIComponent(objId)}/notions/${encodeURIComponent(notionId)}`);
      if (!rep.ok) {
        this._status('Erreur retrait notion', true);
        return;
      }
      this._status('Notion retirée.', false);
      await this.rafraichir({preserverScroll: true});
    }

    async retirerMethode(objId) {
      // v0.16.9 — garde régime mixte : pas d'opération de structure
      // tant qu'une saisie de l'objectif ouvert n'est pas enregistrée.
      if (!this._garderAvantStructure()) return;
      const rep = await apiJson('PATCH',
        `/api/v2/objectifs/${encodeURIComponent(objId)}/methode`,
        {methode_id: null});
      if (!rep.ok) {
        this._status('Erreur dissociation méthode', true);
        return;
      }
      this._status('Méthode dissociée.', false);
      await this.rafraichir({preserverScroll: true});
    }

    async supprimerObj(objId, code, nbExos) {
      // v0.16.9 — garde régime mixte : pas d'opération de structure
      // tant qu'une saisie de l'objectif ouvert n'est pas enregistrée.
      if (!this._garderAvantStructure()) return;
      const msg = nbExos > 0
        ? `Supprimer l'objectif ${code} ?\nIl contient ${nbExos} exercice(s) qui seront détachés.`
        : `Supprimer l'objectif ${code} ?`;
      if (!confirm(msg)) return;

      // Pas de DELETE direct sur objectif dans l'API v2 — on contourne en
      // utilisant la route /objectifs/<id> via DELETE. Si elle n'existe
      // pas, le backend devra la fournir.
      const rep = await apiJson('DELETE',
        `/api/v2/objectifs/${encodeURIComponent(objId)}`);
      if (!rep.ok) {
        this._status(`Suppression non disponible : ${(rep.data && rep.data.error) || rep.status}. Utilise l'éditeur v2.`, true);
        return;
      }
      if (this.objOuvert === objId) await this._setObjOuvert(null);
      this._status('Objectif supprimé.', false);
      await this.rafraichir({preserverScroll: true});
    }

    async supprimerPartie(partieId, nbObjs, nbExos) {
      // v0.16.9 — garde régime mixte : pas d'opération de structure
      // tant qu'une saisie de l'objectif ouvert n'est pas enregistrée.
      if (!this._garderAvantStructure()) return;
      if (nbObjs > 0) {
        alert(`Cette partie contient ${nbObjs} objectif(s). Vide-la avant de la supprimer.`);
        return;
      }
      if (!confirm(`Supprimer cette partie ?${nbExos > 0 ? `\n${nbExos} exo(s) de révision/approche seront aussi retirés.` : ''}`)) return;

      const rep = await apiJson('DELETE',
        `/api/v2/parties/${encodeURIComponent(partieId)}`);
      if (!rep.ok) {
        this._status(`Erreur suppression partie : ${(rep.data && rep.data.error) || rep.status}`, true);
        return;
      }
      this._status('Partie supprimée.', false);
      await this.rafraichir({preserverScroll: true});
    }

    // ── Ouvrir / fermer objectif ─────────────────────────────────────────────

    async ouvrirObj(objId) {
      if (this.objOuvert === objId) return;
      // v0.16.9 — Garde : ne pas perdre une saisie non enregistrée de
      // l'objectif actuellement ouvert en en ouvrant un autre.
      if (!this._garderAvantStructure()) return;
      await this._setObjOuvert(objId);
      await this.rafraichir();
      // v0.17.6 — Amener l'objectif ouvert sous les yeux (sinon le re-render
      // renvoie en haut du panneau, gênant pour un objectif en bas de page).
      requestAnimationFrame(() => this._scrollVersObjectif(objId));
    }

    async fermerObj() {
      if (!this.objOuvert) return;
      if (!this._garderAvantStructure()) return;
      // v0.17.6 — Mémoriser l'objectif fermé pour le ramener sous les yeux
      // après re-render (sinon retour tout en haut du panneau).
      const objFerme = this.objOuvert;
      await this._setObjOuvert(null);
      await this.rafraichir();
      requestAnimationFrame(() => this._scrollVersObjectif(objFerme));
    }

    async _setObjOuvert(objId) {
      this.objOuvert = objId;
      const sn = this._sn();
      if (!sn) return;
      await apiJson('PUT',
        `/api/v2/sequences-par-niveau/${encodeURIComponent(sn.id)}/etat-ui`,
        {objectif_ouvert_id: objId});
    }

    // ── v0.16.9 — Régime mixte : snapshot de l'objectif ouvert ───────────────
    //
    // collecterFormulaire() lit les champs de saisie de l'objectif OUVERT
    // (présents dans #liv-atl-form) : nom, critères F/A/E, fin-cycle, séances.
    // La classe de base compare ce JSON au snapshot pris à l'ouverture pour
    // calculer `modifie` (badge + bouton Enregistrer + garde de sortie).
    // Retourne null si aucun objectif n'est ouvert (→ modifie reste false).
    collecterFormulaire() {
      if (!this.objOuvert) return null;
      const form = document.getElementById('liv-atl-form');
      if (!form) return null;
      const champ = (nom) => form.querySelector(`[data-champ="${nom}"]`);
      const nomEl  = champ('nom');
      const fEl    = champ('critere_F');
      const aEl    = champ('critere_A');
      const eEl    = champ('critere_E');
      const seancesEl = champ('nb_seances');
      const fcEl   = champ('fin_cycle');
      return {
        obj_id:     this.objOuvert,
        nom:        nomEl ? nomEl.value : '',
        critere_F:  fEl ? fEl.value : '',
        critere_A:  aEl ? aEl.value : '',
        critere_E:  eEl ? eEl.value : '',
        // Séance : chaîne brute (le backend tolère ''/virgule). '' → 0 à l'envoi.
        nb_seances: seancesEl ? (seancesEl.value || '') : '',
        // fin-cycle absent pour l'objectif Cours (case non rendue) → null.
        fin_cycle:  fcEl ? (fcEl.checked ? 'O' : 'N') : null,
      };
    }

    // Garde : refuse une opération de structure (ou un changement d'objectif)
    // s'il y a une saisie non enregistrée. Identique à l'éval.
    _garderAvantStructure() {
      if (this.modifie) {
        this.toast(
          'Enregistrez vos modifications (Entrée ou bouton Enregistrer) '
          + 'avant de modifier la structure ou de changer d\'objectif.',
          'erreur',
        );
        return false;
      }
      return true;
    }

    // Enregistre les champs de l'objectif ouvert (PATCH groupés), puis reprend
    // un état propre (snapshot + reset du badge). Surcharge la base.
    async sauvegarder(options = {}) {
      const silencieuse = !!(options && options.silencieuse);
      const champs = this.collecterFormulaire();
      if (champs === null) return false;
      const objId = champs.obj_id;
      try {
        // 1. Nom
        await apiJson('PATCH',
          `/api/v2/objectifs/${encodeURIComponent(objId)}/nom`,
          {nom: champs.nom || ''});
        // 2. Critères (groupés)
        await apiJson('PATCH',
          `/api/v2/objectifs/${encodeURIComponent(objId)}/criteres`,
          {critere_F: champs.critere_F || '',
           critere_A: champs.critere_A || '',
           critere_E: champs.critere_E || ''});
        // 3. Séances de l'objectif ouvert (régime mixte : ici, pas immédiat)
        await apiJson('PATCH',
          `/api/v2/objectifs/${encodeURIComponent(objId)}/seances`,
          {nb_seances: champs.nb_seances === '' ? 0 : champs.nb_seances});
        // 4. Fin-cycle (seulement si la case existe — pas sur l'objectif Cours)
        if (champs.fin_cycle !== null) {
          await apiJson('PATCH',
            `/api/v2/objectifs/${encodeURIComponent(objId)}/fin-cycle`,
            {fin_cycle: champs.fin_cycle});
        }
      } catch (e) {
        this.toast('Échec de l\'enregistrement de l\'objectif.', 'erreur');
        return false;
      }
      // Mise à jour locale de DATA pour cohérence d'un éventuel re-rendu.
      const o = this._trouverObj(objId);
      if (o) {
        o.nom = champs.nom || '';
        o.critere_F = champs.critere_F || '';
        o.critere_A = champs.critere_A || '';
        o.critere_E = champs.critere_E || '';
        o.nb_seances = champs.nb_seances === '' ? 0 : parseFloat(
          String(champs.nb_seances).replace(',', '.')) || 0;
        if (champs.fin_cycle !== null) o.fin_cycle = champs.fin_cycle;
      }
      // État propre : reprend le snapshot et rafraîchit la toolbar (badge).
      this.modifie = false;
      // Le total de séances de la partie peut avoir changé.
      const partieId = this._trouverPartieDeObj(objId);
      if (partieId) this._rafraichirTotalPartie(partieId);
      if (!silencieuse) this.toast('Objectif enregistré.');
      return true;
    }

    // ── v0.16.9 — État validable de la séquence + verrou UI ──────────────────

    // Surcharge : pilote le bouton « Enregistrer l'objectif » selon `modifie`.
    // Appelée par le listener form de la base (via _installerListenerForm) à
    // chaque saisie, et par sauvegarder()/rafraichir() (reset).
    // Surcharge : pilote le bandeau (badges + boutons) à l'identique des
    // autres ateliers (cf. AtelierEditeur.majToolbar). Le seqniv n'a pas
    // d'`itemActif` ni de formulaire CRUD classique : on substitue
    // « une séquence est chargée » (this._sn()) à `itemActif`, et
    // « un objectif est ouvert » (this.objOuvert) à `aFormulaireOuvert()`.
    // Les classes/libellés/IDs sont ceux des ateliers d'atomes et de l'éval
    // (atl-badge-modifie, atome-etat-badge, liv-atl-btn-valider/-save).
    majToolbar() {
      const snCharge = !!this._sn();
      const valide   = (this._etatSequence() === 'valide');

      // Badge « modifié » (saisie de l'objectif ouvert non enregistrée).
      const badgeModifie = this.$('badge-modifie');
      if (badgeModifie) {
        badgeModifie.style.display = this.modifie ? 'inline-block' : 'none';
      }

      // Badge d'état (même rendu que les atomes : classes atome-etat-badge).
      const badgeEtat = this.$('etat-badge');
      if (badgeEtat) {
        if (snCharge) {
          badgeEtat.style.display = 'inline-block';
          if (valide) {
            badgeEtat.textContent = 'Validé';
            badgeEtat.className = 'atome-etat-badge valide';
          } else {
            badgeEtat.textContent = 'En cours';
            badgeEtat.className = 'atome-etat-badge en_cours';
          }
        } else {
          badgeEtat.style.display = 'none';
        }
      }

      // Bouton bascule Valider / Repasser en cours.
      const btnValider = this.$('btn-valider');
      if (btnValider) {
        if (snCharge) {
          btnValider.style.display = 'inline-block';
          btnValider.textContent = valide ? 'Repasser en cours' : 'Valider';
        } else {
          btnValider.style.display = 'none';
        }
      }

      // Verrou « validé = lecture seule » : grise le form de l'objectif
      // ouvert + neutralise la structure (classe sur le conteneur central).
      this._appliquerVerrouLectureSeule(valide);
      const centre = this._container();
      if (centre) centre.classList.toggle('asm-verrou-structure', valide);

      // Bouton Enregistrer : visible si un objectif est ouvert, désactivé si
      // rien de modifié (exactement comme la base : display + disabled).
      const btnSave = this.$('btn-save');
      if (btnSave) {
        btnSave.style.display = (this.objOuvert && !valide) ? 'inline-block' : 'none';
        btnSave.disabled = !this.modifie;
      }
    }

    _etatSequence() {
      const sn = this._sn();
      return (sn && sn.etat_code) || 'en_cours';
    }

    // Applique l'état courant sur l'UI : libellé/visibilité du bouton de
    // validation, et verrou lecture seule du form de l'objectif ouvert.
    // Quand la séquence est validée, on grise le form (champs de saisie) ET
    // on neutralise les contrôles de structure via la classe CSS sur le
    // conteneur (cf. .asm-verrou-structure dans le CSS) ; le bouton de
    // dévalidation reste évidemment actif.
    // v0.16.9 — L'application de l'état sur l'UI (badges, boutons, verrou
    // lecture seule, verrou structure) est entièrement faite par majToolbar()
    // — alignée sur le bandeau des autres ateliers. On délègue.
    _appliquerEtatSequence() {
      this.majToolbar();
    }

    async validerSequence() {
      const sn = this._sn();
      if (!sn) return;
      // Garde : ne pas valider avec une saisie non enregistrée en attente.
      if (!this._garderAvantStructure()) return;
      const rep = await apiJson('PATCH',
        `/api/v2/sequences-par-niveau/${encodeURIComponent(sn.id)}/etat`,
        {etat_code: 'valide'});
      if (!rep.ok) {
        const data = rep.data || {};
        if (data.code === 'validation_pedagogique_echec') {
          const raisons = (data.raisons || []);
          const apercu = raisons.slice(0, 6).join(' • ');
          this.toast(
            'Séquence non validable : ' + apercu
            + (raisons.length > 6 ? ` (+${raisons.length - 6} autre(s))` : ''),
            'erreur',
          );
        } else {
          this.toast('Erreur de validation : '
            + (data.error || `HTTP ${rep.status}`), 'erreur');
        }
        return;
      }
      this.toast('Séquence validée (lecture seule).');
      await this.rafraichir();
    }

    async devaliderSequence() {
      const sn = this._sn();
      if (!sn) return;
      const rep = await apiJson('PATCH',
        `/api/v2/sequences-par-niveau/${encodeURIComponent(sn.id)}/etat`,
        {etat_code: 'en_cours'});
      if (!rep.ok) {
        this.toast('Erreur : ' + ((rep.data && rep.data.error) || rep.status), 'erreur');
        return;
      }
      this.toast('Séquence repassée en cours.');
      await this.rafraichir();
    }

    // Bouton unique bascule selon l'état courant.
    basculerEtatSequence() {
      if (this._etatSequence() === 'valide') return this.devaliderSequence();
      return this.validerSequence();
    }

    // ── Helpers de persistance immédiate (objets FERMÉS) ─────────────────────
    // Conservés pour la saisie immédiate hors form. Le nom/critères/fin-cycle
    // ne sont plus édités hors objectif ouvert ; changerSeancesObj reste
    // utilisé par les inputs séances des objectifs FERMÉS (immédiat).

    async changerNom(objId, nouveauNom) {
      const rep = await apiJson('PATCH',
        `/api/v2/objectifs/${encodeURIComponent(objId)}/nom`,
        {nom: nouveauNom || ''});
      if (!rep.ok) { this._status('Erreur sauvegarde nom', true); return; }
      this._status('Nom enregistré.', false);
      // Mise à jour locale silencieuse (pas de re-rendu)
      const o = this._trouverObj(objId);
      if (o) o.nom = nouveauNom || '';
    }

    async changerCritere(objId, champ, valeur) {
      const o = this._trouverObj(objId);
      const body = {
        critere_F: o.critere_F || '',
        critere_A: o.critere_A || '',
        critere_E: o.critere_E || '',
      };
      body[champ] = valeur || '';
      const rep = await apiJson('PATCH',
        `/api/v2/objectifs/${encodeURIComponent(objId)}/criteres`, body);
      if (!rep.ok) { this._status('Erreur sauvegarde critère', true); return; }
      this._status('Critère enregistré.', false);
      if (o) o[champ] = valeur || '';
    }

    // ── v0.12.0 — Plan de travail générique : nb de séances ──────────────────
    //
    // Formatage et persistance des nombres de séances saisis dans les
    // bandeaux de partie et d'objectif. Le backend accepte int, float et
    // string (y compris virgule décimale FR), donc on n'a pas besoin de
    // convertir côté JS — on envoie la valeur brute du <input>.

    _fmtSeances(n) {
      return _PUR.fmtSeances(n);
    }

    // v0.12.1 — Formatage pour affichage en lecture seule (total partie).
    // Différent de _fmtSeances : on retourne toujours une chaîne (jamais
    // vide), avec virgule décimale française pour le confort de lecture.
    // Ex : 1.5 → "1,5", 2 → "2", 0.5 → "0,5".
    _fmtSeancesAffichage(n) {
      return _PUR.fmtSeancesAffichage(n);
    }

    // v0.12.1 — Total des séances prévues pour une partie : R+AE de la
    // partie + somme des nb_seances de tous les objectifs (cours et
    // exos). Robustesse : tolère les valeurs absentes (champ pas encore
    // remonté du backend) en les traitant comme 0.
    _calculerTotalSeancesPartie(p) {
      return _PUR.calculerTotalSeancesPartie(p);
    }

    async changerSeancesPartie(partieId, valeur) {
      // Chaîne vide = 0 (input vidé par l'utilisateur). Le backend tolère
      // string et accepte 0.
      const v = (valeur === '' || valeur === null) ? 0 : valeur;
      const rep = await apiJson('PATCH',
        `/api/v2/parties/${encodeURIComponent(partieId)}/seances`,
        {nb_seances: v});
      if (!rep.ok) {
        this._status('Erreur sauvegarde séances (partie)', true);
        return;
      }
      this._status('Séances enregistrées.', false);
      // Mise à jour locale silencieuse (pas de re-rendu)
      const partie = this._trouverPartie(partieId);
      if (partie) partie.nb_seances_R_AE = (rep.data && rep.data.nb_seances_R_AE) || 0;
      // v0.12.1 — Rafraîchir le total partie (DOM ciblé, sans re-rendu)
      this._rafraichirTotalPartie(partieId);
    }

    async changerSeancesObj(objId, valeur) {
      const v = (valeur === '' || valeur === null) ? 0 : valeur;
      const rep = await apiJson('PATCH',
        `/api/v2/objectifs/${encodeURIComponent(objId)}/seances`,
        {nb_seances: v});
      if (!rep.ok) {
        this._status('Erreur sauvegarde séances (objectif)', true);
        return;
      }
      this._status('Séances enregistrées.', false);
      const o = this._trouverObj(objId);
      if (o) o.nb_seances = (rep.data && rep.data.nb_seances) || 0;
      // v0.12.1 — L'objectif appartient à une partie : on rafraîchit le
      // total de cette partie. Recherche linéaire sur DATA.parties pour
      // localiser la partie qui contient cet objectif.
      const partieId = this._trouverPartieDeObj(objId);
      if (partieId) this._rafraichirTotalPartie(partieId);
    }

    // v0.12.3.0 — Toggle « Fin de cycle » (attribut booléen sur les
    // objectifs exo, code 02 et plus). Pas exposé sur l'objectif Cours
    // (codes 01/11/21...). Sauvegarde silencieuse via PATCH ; pas de
    // re-rendu pour préserver l'état UI environnant.
    async changerFinCycle(objId, estCoche) {
      const rep = await apiJson('PATCH',
        `/api/v2/objectifs/${encodeURIComponent(objId)}/fin-cycle`,
        {fin_cycle: estCoche ? 'O' : 'N'});
      if (!rep.ok) {
        this._status(`Erreur sauvegarde fin de cycle : ${(rep.data && rep.data.error) || rep.status}`, true);
        // Restaurer l'état précédent dans le DOM
        const cb = document.querySelector(
          `.asm-obj.open[data-obj-id="${objId}"] .asm-obj-fincycle-input`
        );
        if (cb) cb.checked = !estCoche;
        return;
      }
      this._status(estCoche ? 'Marqué fin de cycle.' : 'Fin de cycle retiré.', false);
      // Mettre à jour DATA pour cohérence (en cas de re-rendu ultérieur)
      const o = this._trouverObj(objId);
      if (o) o.fin_cycle = estCoche ? 'O' : 'N';
    }

    // v0.12.1 — Rafraîchit le label "total : N séance(s)" d'une partie
    // dans le DOM, sans re-rendre la partie entière (préservation du
    // focus). Si le span n'existait pas (total à 0), on le crée. S'il
    // existe et que le total redevient 0, on le retire.
    _rafraichirTotalPartie(partieId) {
      const partie = this._trouverPartie(partieId);
      if (!partie) return;
      const total = this._calculerTotalSeancesPartie(partie);
      const elPartie = document.querySelector(
        `.asm-partie[data-partie-id="${partieId}"]`
      );
      if (!elPartie) return;
      const head = elPartie.querySelector('.asm-partie-head');
      if (!head) return;
      let elTotal = head.querySelector('.asm-partie-total');
      if (total === 0) {
        if (elTotal) elTotal.remove();
        return;
      }
      const txt = `total : ${this._fmtSeancesAffichage(total)} séance${total > 1 ? 's' : ''}`;
      if (elTotal) {
        elTotal.textContent = txt;
      } else {
        // Insérer juste après .asm-partie-titre
        const elTitre = head.querySelector('.asm-partie-titre');
        if (!elTitre) return;
        const nouv = document.createElement('span');
        nouv.className = 'asm-partie-total';
        nouv.title = 'Total des séances prévues pour cette partie (R+AE + cours + exos)';
        nouv.textContent = txt;
        elTitre.insertAdjacentElement('afterend', nouv);
      }
    }

    _trouverPartieDeObj(objId) {
      return _PUR.trouverPartieDeObj(this.data, objId);
    }

    _trouverPartie(partieId) {
      return _PUR.trouverPartie(this.data, partieId);
    }

    _trouverObj(objId) {
      return _PUR.trouverObj(this.data, objId);
    }

    // ── Activation de l'objectif Connaître ───────────────────────────────────

    async activerConnaitre(partieId) {
      // v0.16.9 — garde régime mixte : pas d'opération de structure
      // tant qu'une saisie de l'objectif ouvert n'est pas enregistrée.
      if (!this._garderAvantStructure()) return;
      const c = this._critDefauts || {};
      const rep = await apiJson('POST',
        `/api/v2/parties/${encodeURIComponent(partieId)}/objectif-connaitre`,
        {
          nom: c.nom,
          critere_F: c.critere_F,
          critere_A: c.critere_A,
          critere_E: c.critere_E,
        });
      if (!rep.ok) {
        this._status(`Erreur : ${(rep.data && rep.data.error) || rep.status}`, true);
        return;
      }
      this._status('Objectif Connaître créé.', false);
      await this.rafraichir({preserverScroll: true});
    }

    // ── Création d'une nouvelle partie ───────────────────────────────────────

    async nouvellePartie() {
      // v0.16.9 — garde régime mixte : pas d'opération de structure
      // tant qu'une saisie de l'objectif ouvert n'est pas enregistrée.
      if (!this._garderAvantStructure()) return;
      const sn = this._sn();
      if (!sn) return;
      const rep = await apiJson('POST',
        `/api/v2/sequences-par-niveau/${encodeURIComponent(sn.id)}/parties`, {});
      if (!rep.ok) {
        this._status(`Erreur création partie : ${(rep.data && rep.data.error) || rep.status}`, true);
        return;
      }
      this._status('Partie créée.', false);
      await this.rafraichir({preserverScroll: true});
    }

    // ── v0.12.3.0 — Drag & drop pour réordonner les objectifs ────────────────
    //
    // Comportement attendu (cf. doc/redemarrage_v0_12_3_0.md) :
    //
    //   - Glisser un objectif sur un autre objectif :
    //       même partie  → réordonnement intra-partie (recalcul des codes)
    //       autre partie → déplacement vers cette partie à la position de la cible
    //
    //   - L'objectif Connaître/Cours (code 0X1) :
    //       n'est pas draggable (data-obj-est-cours="1" + draggable="false")
    //       ne peut pas être survolé/écrasé (refus visuel : pas de classe drag-over)
    //
    //   - Déterminer si on insère AVANT ou APRÈS l'objectif cible : on regarde
    //     la position verticale de la souris dans le rectangle de l'objectif.
    //     Au-dessus de la moitié → insertion avant. En dessous → après.
    //
    // Le helper backend `deplacer_objectif_avec_position` (route
    // /api/v2/objectifs/<id>/deplacer) gère atomiquement les deux cas
    // (inter-partie + intra-partie) avec recalcul des codes.

    // v0.16.6 — (doublon de _trouverPartiePourObj supprimé ; voir la
    // définition unique plus haut qui délègue à window.SeqnivPur.)

    // Helper : indices d'un objectif dans sa partie (en excluant le Cours
    // pour la position visible, mais on garde l'index global pour l'API).
    _indexObjDansPartie(partie, objId) {
      return _PUR.indexObjDansPartie(partie, objId);
    }

    dragOverObj(ev, el) {
      if (!this._drag || this._drag.kind !== 'obj') return;
      if (this._drag.obj_id === el.dataset.objId) return;
      // L'objectif Cours ne peut pas être écrasé (rester en position 0).
      if (el.dataset.objEstCours === '1') {
        // On accepte toutefois le drop juste après le Cours : indicateur visuel
        // « below » uniquement. Au-dessus du Cours, refus.
        const rect = el.getBoundingClientRect();
        const moitie = rect.top + rect.height / 2;
        if (ev.clientY < moitie) {
          // Au-dessus du Cours : interdit.
          return;
        }
        ev.preventDefault();
        el.classList.remove('drag-over-obj-above');
        el.classList.add('drag-over-obj-below');
        return;
      }
      ev.preventDefault();
      const rect = el.getBoundingClientRect();
      const moitie = rect.top + rect.height / 2;
      if (ev.clientY < moitie) {
        el.classList.add('drag-over-obj-above');
        el.classList.remove('drag-over-obj-below');
      } else {
        el.classList.add('drag-over-obj-below');
        el.classList.remove('drag-over-obj-above');
      }
    }

    dragLeaveObj(ev, el) {
      el.classList.remove('drag-over-obj-above');
      el.classList.remove('drag-over-obj-below');
    }

    async dropObj(ev, el) {
      // v0.16.9 — garde régime mixte : pas d'opération de structure
      // tant qu'une saisie de l'objectif ouvert n'est pas enregistrée.
      if (!this._garderAvantStructure()) return;
      if (!this._drag || this._drag.kind !== 'obj') return;
      ev.preventDefault();
      ev.stopPropagation();
      el.classList.remove('drag-over-obj-above');
      el.classList.remove('drag-over-obj-below');

      const objGlissé = this._drag.obj_id;
      const objCible  = el.dataset.objId;
      this._drag = null;
      if (objGlissé === objCible) return;

      const partieCible = this._trouverPartiePourObj(objCible);
      const partieSource = this._trouverPartiePourObj(objGlissé);
      if (!partieCible || !partieSource) {
        this._status('Erreur interne : partie introuvable.', true);
        return;
      }

      // Déterminer la position d'insertion : avant ou après la cible
      // selon la position verticale de la souris.
      const rect = el.getBoundingClientRect();
      const moitie = rect.top + rect.height / 2;
      const insererApres = ev.clientY >= moitie;

      // Calculer la position dans la partie cible. On part de l'index actuel
      // de la cible, on ajoute 1 si on insère après. Et si l'objectif glissé
      // est déjà dans la même partie ET avant la cible, on ajuste : son
      // retrait décale les indices.
      const objsCible = partieCible.objectifs || [];
      const indexCible = objsCible.findIndex(o => o.id === objCible);
      if (indexCible < 0) {
        this._status('Erreur interne : objectif cible introuvable.', true);
        return;
      }
      let position = insererApres ? indexCible + 1 : indexCible;

      // Cas intra-partie : si l'objectif glissé est dans la même partie ET
      // à un index < indexCible, son retrait fera baisser tous les indices
      // suivants de 1. La position d'insertion doit être réduite de 1.
      if (partieSource.id === partieCible.id) {
        const indexSrc = objsCible.findIndex(o => o.id === objGlissé);
        if (indexSrc >= 0 && indexSrc < indexCible) {
          position -= 1;
        }
      }

      const rep = await apiJson('PATCH',
        `/api/v2/objectifs/${encodeURIComponent(objGlissé)}/deplacer`,
        {partie_cible_id: partieCible.id, position_dans_cible: position});
      if (!rep.ok) {
        const code = (rep.data && rep.data.code) || '';
        const msg = (rep.data && (rep.data.message || rep.data.error)) || rep.status;
        this._status(`Erreur déplacement (${code}) : ${msg}`, true);
        return;
      }
      this._status('Objectif déplacé.', false);
      await this.rafraichir({preserverScroll: true});
    }

    // ── Drag & drop pour réordonner les parties ──────────────────────────────
    //
    // Stratégie : on ajoute un dragover sur chaque partie qui surligne au-
    // dessus/au-dessous selon la position du curseur, et on appelle l'API
    // /parties/ordre au drop.
    //
    // v0.16.7 — Les listeners sont attachés via addEventListener (pas via
    // attributs HTML), donc on lie des fonctions fléchées capturant `this`
    // (l'instance) ; `event.currentTarget` donne la carte de partie.

    _brancherDragParties() {
      const liste = document.getElementById('asm-parties-list');
      if (!liste) return;
      const cartes = liste.querySelectorAll('.asm-partie');
      cartes.forEach(carte => {
        carte.addEventListener('dragover',  (ev) => this._dragOverPartie(ev, carte));
        carte.addEventListener('drop',      (ev) => this._dropPartie(ev, carte));
        carte.addEventListener('dragleave', (ev) => this._dragLeavePartie(ev, carte));
      });
    }

    _dragOverPartie(ev, carte) {
      if (!this._drag || this._drag.kind !== 'partie') return;
      if (carte.dataset.partieId === this._drag.partie_id) return;
      ev.preventDefault();
      carte.classList.add('drag-over-partie');
    }

    _dragLeavePartie(ev, carte) {
      carte.classList.remove('drag-over-partie');
    }

    async _dropPartie(ev, carte) {
      if (!this._drag || this._drag.kind !== 'partie') return;
      ev.preventDefault();
      ev.stopPropagation();
      carte.classList.remove('drag-over-partie');

      const partieGlissee = this._drag.partie_id;
      const partieCible   = carte.dataset.partieId;
      this._drag = null;
      if (partieGlissee === partieCible) return;

      // Construire le nouvel ordre : on retire partieGlissee, on l'insère
      // à la position de partieCible.
      const ordreActuel = (this.data.parties || []).map(p => p.id);
      const sansGlissee = ordreActuel.filter(id => id !== partieGlissee);
      const indexCible = sansGlissee.indexOf(partieCible);
      const nouvelOrdre = [
        ...sansGlissee.slice(0, indexCible),
        partieGlissee,
        ...sansGlissee.slice(indexCible),
      ];

      const sn = this._sn();
      const rep = await apiJson('PATCH',
        `/api/v2/sequences-par-niveau/${encodeURIComponent(sn.id)}/parties/ordre`,
        {partie_ids: nouvelOrdre});
      if (!rep.ok) {
        this._status(`Erreur réordonnancement : ${(rep.data && rep.data.error) || rep.status}`, true);
        return;
      }
      this._status('Parties réordonnées.', false);
      await this.rafraichir({preserverScroll: true});
    }

    // ── v0.11.2 — Compilation du livret de séquence ──────────────────────────
    //
    // Le blob PDF est mémorisé dans this._livretBlobUrl (libéré entre deux
    // compils pour ne pas accumuler de mémoire).

    _livretSeqOptions() {
      // Lit l'état des toggles et construit le dict d'options pour l'API.
      // Cf. services.livret_sequence.normaliser_options pour la structure.
      function getCheck(id) {
        const e = document.getElementById(id);
        return e ? !!e.checked : true;
      }
      return {
        cours: {
          inclure: getCheck('livret-seq-cours'),
          fiches_resume: {
            inclure: getCheck('livret-seq-fiches'),
            a_completer: getCheck('livret-seq-a-completer'),
          },
        },
        exercices: {
          inclure: getCheck('livret-seq-exercices'),
          serie_A: getCheck('livret-seq-serie-a'),
        },
      };
    }

    _livretSeqMasquerTout() {
      ['livret-seq-empty', 'livret-seq-loader', 'livret-seq-erreur',
       'livret-seq-tex-out', 'livret-seq-pdf-wrapper'].forEach(id => {
        const e = document.getElementById(id);
        if (e) e.style.display = 'none';
      });
    }

    _livretSeqAfficherLoader() {
      this._livretSeqMasquerTout();
      const e = document.getElementById('livret-seq-loader');
      if (e) e.style.display = '';
    }

    _livretSeqAfficherEmpty() {
      this._livretSeqMasquerTout();
      const e = document.getElementById('livret-seq-empty');
      if (e) e.style.display = '';
    }

    _livretSeqAfficherErreur(message, logComplet) {
      this._livretSeqMasquerTout();
      this._livretDernierLog = logComplet || '';
      const e = document.getElementById('livret-seq-erreur');
      if (!e) return;
      e.style.display = '';
      e.textContent = '';
      const pre = document.createElement('pre');
      pre.style.whiteSpace = 'pre-wrap';
      pre.style.fontFamily = 'inherit';
      pre.style.margin = '0';
      pre.textContent = message;
      e.appendChild(pre);
      // Bouton de téléchargement du log si disponible (cf. recap_cours pour
      // le pattern : un <pre> de plusieurs centaines de Ko serait pénible
      // à afficher, on offre le téléchargement à la place).
      if (logComplet) {
        const btn = document.createElement('button');
        btn.className = 'btn-sm';
        btn.style.marginTop = '10px';
        btn.textContent = 'Télécharger le log complet';
        const self = this;
        btn.onclick = function () {
          const blob = new Blob([logComplet], { type: 'text/plain' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          const sn = self._sn();
          a.href = url;
          a.download = `livret_${sn.niveau}_${sn.sequence_code}_log.txt`;
          a.click();
          URL.revokeObjectURL(url);
        };
        e.appendChild(btn);
      }
    }

    _livretSeqAfficherPdf(blobUrl) {
      this._livretSeqMasquerTout();
      const wrapper = document.getElementById('livret-seq-pdf-wrapper');
      const iframe = document.getElementById('livret-seq-pdf-iframe');
      if (wrapper) wrapper.style.display = '';
      // v0.16.10 — Affichage via le viewer pdf.js embarqué (hérité
      // d'AtelierEditeur), au lieu de `iframe.src = blobUrl`. Sur poste
      // verrouillé (Firefox établissement), l'affichage natif d'un blob PDF
      // dans une iframe est détourné vers une fenêtre externe ; le viewer
      // pdf.js dessine le PDF dans un <canvas>, garantissant le rendu inline
      // quel que soit le navigateur. Même mécanisme que les ateliers d'atomes
      // et l'évaluation (cf. _afficherPdfDansViewer).
      if (iframe) this._afficherPdfDansViewer(iframe, blobUrl);
    }

    _livretSeqAfficherTex(tex) {
      // v0.17.2 — Affichage dans la modale commune (atelierAfficherLatex),
      // comme tous les autres ateliers. Le .tex vient du serveur (fetch dans
      // livretSeqVoirTex) — séparation des rôles respectée.
      if (typeof window.atelierAfficherLatex === 'function') {
        window.atelierAfficherLatex('livret_sequence', tex);
      } else {
        this.toast('Module commun manquant : LaTeX dans la console.', 'erreur');
        console.log(tex);
      }
    }

    _livretSeqLiberer() {
      if (this._livretBlobUrl) {
        URL.revokeObjectURL(this._livretBlobUrl);
        this._livretBlobUrl = null;
      }
    }

    // Action publique : compiler le PDF
    async livretSeqGenererPdf() {
      const sn = this._sn();
      if (!sn || !sn.niveau || !sn.sequence_code) {
        this._livretSeqAfficherErreur('Aucune séquence sélectionnée.');
        return;
      }
      const url = `/api/v2/livret-sequence/${encodeURIComponent(sn.niveau)}/`
                + `${encodeURIComponent(sn.sequence_code)}/rendu-pdf`;
      this._livretSeqAfficherLoader();
      try {
        const r = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ options: this._livretSeqOptions() }),
        });
        if (!r.ok) {
          const data = await r.json().catch(() => null);
          if (data) {
            let msg = data.message || data.error || 'Compilation échouée.';
            if (Array.isArray(data.erreurs) && data.erreurs.length > 0) {
              const erreurs = data.erreurs.slice(0, 3).map(er =>
                `  • Ligne ${er.ligne || '?'} : ${er.message}`
              ).join('\n');
              msg += '\n\nDétail :\n' + erreurs;
            }
            this._livretSeqAfficherErreur(msg, data.log_complet);
          } else {
            this._livretSeqAfficherErreur(`Erreur HTTP ${r.status}.`);
          }
          return;
        }
        // Succès : libérer l'ancien blob, créer le nouveau
        this._livretSeqLiberer();
        const blob = await r.blob();
        this._livretBlobUrl = URL.createObjectURL(blob);
        this._livretSeqAfficherPdf(this._livretBlobUrl);
      } catch (err) {
        this._livretSeqAfficherErreur(`Erreur réseau : ${err.message || err}`);
      }
    }

    // Action publique : voir le .tex source (sans compilation)
    async livretSeqVoirTex() {
      const sn = this._sn();
      if (!sn || !sn.niveau || !sn.sequence_code) {
        this._livretSeqAfficherErreur('Aucune séquence sélectionnée.');
        return;
      }
      const url = `/api/v2/livret-sequence/${encodeURIComponent(sn.niveau)}/`
                + `${encodeURIComponent(sn.sequence_code)}/rendu-tex`;
      this._livretSeqAfficherLoader();
      try {
        const r = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ options: this._livretSeqOptions() }),
        });
        if (!r.ok) {
          const data = await r.json().catch(() => ({}));
          this._livretSeqAfficherErreur(
            `Erreur ${r.status} : ${data.error || data.message || 'inconnue'}`
          );
          return;
        }
        const tex = await r.text();
        this._livretSeqAfficherTex(tex);
      } catch (err) {
        this._livretSeqAfficherErreur(`Erreur réseau : ${err.message || err}`);
      }
    }

    // v0.12.1.2 — Action : compiler le plan de travail de la séquence
    // courante (une page par partie de la séquence, sans page de titre).
    // Pour le livret annuel agrégeant toutes les séquences du niveau,
    // voir l'atelier « Plans de travail » de la portée Niveau.
    // Affiche le PDF dans la même iframe que le livret de séquence.
    async livretSeqCompilerPlanTravail() {
      const sn = this._sn();
      if (!sn || !sn.niveau || !sn.sequence_code) {
        this._livretSeqAfficherErreur('Aucune séquence sélectionnée.');
        return;
      }
      const url = `/api/plans-de-travail/${encodeURIComponent(sn.niveau)}`
                + `/${encodeURIComponent(sn.sequence_code)}/pdf`;
      this._livretSeqAfficherLoader();
      try {
        const r = await fetch(url, { method: 'POST' });
        if (!r.ok) {
          const data = await r.json().catch(() => null);
          if (data) {
            let msg = data.message || data.error || 'Compilation échouée.';
            if (Array.isArray(data.erreurs) && data.erreurs.length > 0) {
              const erreurs = data.erreurs.slice(0, 3).map(er =>
                `  • Ligne ${er.ligne || '?'} : ${er.message}`
              ).join('\n');
              msg += '\n\nDétail :\n' + erreurs;
            }
            this._livretSeqAfficherErreur(msg, data.log_complet);
          } else {
            this._livretSeqAfficherErreur(`Erreur HTTP ${r.status}.`);
          }
          return;
        }
        // Succès : libérer l'ancien blob, afficher le nouveau PDF dans
        // la même iframe (le wrapper #livret-seq-pdf-wrapper sert pour
        // le livret de séquence ET pour le plan de travail).
        this._livretSeqLiberer();
        const blob = await r.blob();
        this._livretBlobUrl = URL.createObjectURL(blob);
        this._livretSeqAfficherPdf(this._livretBlobUrl);
      } catch (err) {
        this._livretSeqAfficherErreur(`Erreur réseau : ${err.message || err}`);
      }
    }
  }

  // ── Instanciation + exposition globale ─────────────────────────────────────
  //
  // Instance unique, cohérent avec window.ATELIER_EVALUATION. Le seqniv n'a
  // PAS de bouton Enregistrer ni de garde de sortie (persistance immédiate),
  // donc il ne s'enregistre PAS dans window.ATELIER_REGISTRE — comme le
  // faisait (ne faisait pas) le code procédural historique. Ce branchement
  // viendra avec l'appareil verrou/mixte d'une version ultérieure.

  window.AtelierSeqnivAssemblage = AtelierSeqnivAssemblage;
  window.ATELIER_SEQNIV = new AtelierSeqnivAssemblage();

  // ── Wrappers globaux ───────────────────────────────────────────────────────
  //
  // Hook public historique appelé par app.js.initLivret() — CONSERVÉ tel quel
  // pour ne pas toucher app.js. Délègue à l'instance.
  window.seqnivAssemblageRafraichir = function () {
    return window.ATELIER_SEQNIV.rafraichir();
  };

  // Wrappers `atelSeqniv*` (style atelEval*). Le HTML généré par cet atelier
  // appelle désormais ATELIER_SEQNIV.methode(...) directement (décision P3
  // v0.16.7), donc ces wrappers ne sont là QUE pour d'éventuels appelants
  // externes / cohérence avec la convention de nommage des autres ateliers OO.
  const A = window.ATELIER_SEQNIV;
  window.atelSeqnivBasculerOnglet      = (...a) => A.basculerOnglet(...a);
  window.atelSeqnivTogglePrecPopover   = (...a) => A.togglePrecPopover(...a);
  window.atelSeqnivChargerSeqsPrec     = (...a) => A.chargerSeqsPrec(...a);
  window.atelSeqnivValiderPrecedence   = (...a) => A.validerPrecedence(...a);
  window.atelSeqnivRetirerPrecedence   = (...a) => A.retirerPrecedence(...a);
  window.atelSeqnivNouvellePartie      = (...a) => A.nouvellePartie(...a);
  window.atelSeqnivSupprimerPartie     = (...a) => A.supprimerPartie(...a);
  window.atelSeqnivActiverConnaitre    = (...a) => A.activerConnaitre(...a);
  window.atelSeqnivOuvrirObj           = (...a) => A.ouvrirObj(...a);
  window.atelSeqnivFermerObj           = (...a) => A.fermerObj(...a);
  window.atelSeqnivSupprimerObj        = (...a) => A.supprimerObj(...a);
  window.atelSeqnivChangerNom          = (...a) => A.changerNom(...a);
  window.atelSeqnivChangerCritere      = (...a) => A.changerCritere(...a);
  window.atelSeqnivChangerSeancesObj   = (...a) => A.changerSeancesObj(...a);
  window.atelSeqnivChangerSeancesPartie= (...a) => A.changerSeancesPartie(...a);
  window.atelSeqnivChangerFinCycle     = (...a) => A.changerFinCycle(...a);
  window.atelSeqnivEditerAtome         = (...a) => A.editerAtome(...a);
  window.atelSeqnivEditerFiche         = (...a) => A.editerFiche(...a);
  window.atelSeqnivRetirerExoObj       = (...a) => A.retirerExoObj(...a);
  window.atelSeqnivRetirerExoRA        = (...a) => A.retirerExoRA(...a);
  window.atelSeqnivRetirerNotion       = (...a) => A.retirerNotion(...a);
  window.atelSeqnivRetirerMethode      = (...a) => A.retirerMethode(...a);
  window.atelSeqnivRetirerFiche        = (...a) => A.retirerFiche(...a);
  // DnD
  window.atelSeqnivDragStartMethode    = (...a) => A.dragStartMethode(...a);
  window.atelSeqnivDragStartExoCatalogue = (...a) => A.dragStartExoCatalogue(...a);
  window.atelSeqnivDragStartExoRA      = (...a) => A.dragStartExoRA(...a);
  window.atelSeqnivDragStartExoObj     = (...a) => A.dragStartExoObj(...a);
  window.atelSeqnivDragStartPartie     = (...a) => A.dragStartPartie(...a);
  window.atelSeqnivDragStartObj        = (...a) => A.dragStartObj(...a);
  window.atelSeqnivDragStartFromSidebar= (...a) => A.dragStartFromSidebar(...a);
  window.atelSeqnivDragEnd             = (...a) => A.dragEnd(...a);
  window.atelSeqnivDragOver            = (...a) => A.dragOver(...a);
  window.atelSeqnivDragLeave           = (...a) => A.dragLeave(...a);
  window.atelSeqnivDragOverObj         = (...a) => A.dragOverObj(...a);
  window.atelSeqnivDragLeaveObj        = (...a) => A.dragLeaveObj(...a);
  window.atelSeqnivDropObj             = (...a) => A.dropObj(...a);
  window.atelSeqnivDropMethode         = (...a) => A.dropMethode(...a);
  window.atelSeqnivDropRA              = (...a) => A.dropRA(...a);
  window.atelSeqnivDropExoObj          = (...a) => A.dropExoObj(...a);
  window.atelSeqnivDropNotion          = (...a) => A.dropNotion(...a);
  window.atelSeqnivDropFiche           = (...a) => A.dropFiche(...a);
  // Livret PDF
  window.atelSeqnivLivretGenererPdf    = (...a) => A.livretSeqGenererPdf(...a);
  window.atelSeqnivLivretVoirTex       = (...a) => A.livretSeqVoirTex(...a);
  window.atelSeqnivLivretPlanTravail   = (...a) => A.livretSeqCompilerPlanTravail(...a);

})();
