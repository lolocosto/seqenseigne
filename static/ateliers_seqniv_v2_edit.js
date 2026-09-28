/* static/ateliers_seqniv_v2_edit.js — édition de l'atelier Séquence (niveau).
 *
 * Fichier unique après nettoyage post-R4e4b. Il remplit directement le
 * conteneur #liv-atl-content-v2 avec une UI d'édition du modèle v2 :
 *   - parties (ajout, renumérotation, suppression, précédences)
 *   - objectifs (code, nom, méthode, critères F/A/E, réassignation de partie)
 *   - exos par série EA/F/A/E (ajout depuis catalogue, ↑↓, retrait)
 *   - série R (révisions depuis niveau/séquence précédents)
 *
 * Ce fichier a fusionné le défunt ateliers_seqniv_v2.js (R4e1 lecture
 * seule) : son CSS de base (.seqnivv2-*) est désormais injecté par
 * _injecterCSSBase(). La vue Lecture et les deux toggles Legacy/v2 et
 * Lecture/Édition ont été supprimés (on est toujours en édition v2).
 *
 * Hooks utilisés depuis l'extérieur (app.js) :
 *   - window.seqnivEditRafraichir  → appelé par initLivret() à chaque
 *     ouverture de l'atelier ou changement de portée séquence
 * Pas d'autres dépendances ; le fichier s'auto-branche sur DOMContentLoaded.
 */

(function () {
  'use strict';

  let DATA = null;                   // dernière structure reçue
  let CHARGEMENT = false;
  let PARTIES_CACHE = [];            // [{id, numero}] pour les sélecteurs de réassignation

  // ── Helpers ───────────────────────────────────────────────────────────────

  function esc(s) {
    if (s === null || s === undefined) return '';
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function codeCoherent(code, numero) {
    // Mirror exact de services.v2_edition.code_coherent_avec_partie.
    if (!code || code.length !== 2) return true;
    if (!/^\d\d$/.test(code)) return true;
    return parseInt(code[0], 10) + 1 === numero;
  }

  async function apiJson(method, path, body) {
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    };
    if (body !== undefined) opts.body = JSON.stringify(body);
    const rep = await fetch(path, opts);
    let data = null;
    try { data = await rep.json(); } catch (_) { /* peut être vide */ }
    return { status: rep.status, ok: rep.ok, data: data };
  }

  function _container() {
    return document.getElementById('liv-atl-content-v2');
  }

  function _status(msg, err) {
    // Utilise l'élément #liv-atl-status présent dans la toolbar HTML de
    // l'atelier (templates/index.html). Historiquement ce script injectait
    // son propre #seqniv-edit-status à côté du toggle Lecture/Édition ;
    // ce toggle a disparu, on réutilise directement la zone prévue.
    const el = document.getElementById('liv-atl-status');
    if (!el) return;
    el.textContent = msg || '';
    el.style.color = err ? '#c0392b' : '#6da06d';
    if (msg) {
      setTimeout(() => {
        if (el.textContent === msg) el.textContent = '';
      }, err ? 6000 : 2500);
    }
  }

  // ── Rafraîchissement ─────────────────────────────────────────────────────
  //
  // Appelé depuis app.js via window.seqnivEditRafraichir() :
  //   - à l'ouverture de l'atelier livret (initLivret)
  //   - à chaque changement de filtre de portée séquence (initLivret est
  //     ré-invoquée par atelInvoquerInit, qui appelle seqnivEditRafraichir).
  //
  // La fonction lit ATL_FILTRE_NIVEAU et ATL_FILTRE_SEQ pour cibler la
  // séquence à charger.

  window.seqnivEditRafraichir = function () { _rafraichirEdition(); };

  async function _rafraichirEdition() {
    if (CHARGEMENT) return;

    // v0.10.1 : ne fetcher que si le conteneur du mode editv2 est visible
    // (sinon on duplique l'appel API avec le mode assemblage qui s'occupe
    // déjà du chargement). Le hook reste appelé inconditionnellement par
    // app.js > initLivret(), mais court-circuite ici si invisible.
    const cont = document.getElementById('liv-atl-content-v2');
    if (cont && cont.style.display === 'none') return;

    const niveau = window.ATL_FILTRE_NIVEAU || '';
    const seq = window.ATL_FILTRE_SEQ || '';
    if (!niveau || !seq) {
      _afficher('<div class="seqnivv2-vide">Choisir un niveau et une séquence.</div>');
      return;
    }

    CHARGEMENT = true;
    _afficher('<div class="seqnivv2-vide">Chargement…</div>');
    try {
      const rep = await apiJson('GET',
        `/api/v2/sequences-par-niveau/${encodeURIComponent(niveau)}/${encodeURIComponent(seq)}`);
      if (rep.status === 404) {
        _afficher(`
          <div class="seqnivv2-vide">
            <div style="font-size:24px;opacity:.4">📭</div>
            <p><strong>${esc(niveau)} / ${esc(seq)}</strong> n'est pas peuplé dans le modèle v2.</p>
            <p>Exécuter <code>peuplement_13_v2_depuis_base.py</code> avant l'édition.</p>
          </div>`);
        return;
      }
      if (!rep.ok) {
        _afficher(`<div class="seqnivv2-vide">Erreur HTTP ${rep.status}.</div>`);
        return;
      }
      DATA = rep.data;
      PARTIES_CACHE = (DATA.parties || []).map(p => ({ id: p.id, numero: p.numero }));
      _rendreEdition(DATA);
    } catch (err) {
      _afficher(`<div class="seqnivv2-vide">Erreur réseau : ${esc(err.message || err)}</div>`);
    } finally {
      CHARGEMENT = false;
    }
  }

  function _afficher(html) {
    const c = _container();
    if (c) c.innerHTML = html;
  }

  // ── Rendu complet en mode édition ────────────────────────────────────────

  function _rendreEdition(data) {
    const sn = data.sequence_par_niveau || {};
    const parties = data.parties || [];
    const themeCouleur = _couleurTheme(sn.theme_code_couleur);

    const themeBadge = sn.theme_code
      ? `<span class="seqnivv2-theme-badge" style="background:${themeCouleur}">
            ${esc(sn.theme_code)} — ${esc(sn.theme_nom || '')}
         </span>`
      : `<span class="seqnivv2-theme-badge seqnivv2-theme-badge--none">Aucun thème</span>`;

    const html = [];
    html.push(`
      <div class="seqnivv2-header">
        <div class="seqnivv2-header-main">
          <span class="seqnivv2-header-niv">${esc(sn.niveau || '')}</span>
          <span class="seqnivv2-header-code">${esc(sn.sequence_code || '')}</span>
          <span class="seqnivv2-header-nom">${esc(sn.sequence_nom || '')}</span>
        </div>
        <div class="seqnivv2-header-meta">
          ${themeBadge}
          <button class="seqniv-edit-btn seqniv-edit-btn--primary"
                  onclick="seqnivEditCreerPartie('${esc(sn.id)}')">
            + Nouvelle partie
          </button>
        </div>
      </div>
    `);

    if (parties.length === 0) {
      html.push(`<div class="seqnivv2-vide">Aucune partie. Clique sur <em>+ Nouvelle partie</em>.</div>`);
    } else {
      parties.forEach(p => html.push(_rendrePartie(p, parties)));
    }
    _afficher(html.join(''));
  }

  function _rendrePartie(p, toutes_parties) {
    // Boutons : renuméroter (input live), supprimer
    const precHtml = (p.precedences || []).map(pr => `
      <span class="seqniv-prec-chip">
        ← ${esc(pr.precedent_niveau)}/${esc(pr.precedent_seq)}
        <button class="seqniv-prec-supp"
                title="Supprimer cette précédence"
                onclick="seqnivEditSupprimerPrecedence('${esc(p.id)}','${esc(pr.precedent_niveau)}','${esc(pr.precedent_seq)}')">×</button>
      </span>
    `).join('');

    const precAdd = `
      <span class="seqniv-prec-add">
        <input type="text" placeholder="N10"
               id="seqniv-prec-niv-${esc(p.id)}"
               maxlength="3" size="4" class="seqniv-prec-input">
        <input type="text" placeholder="S01"
               id="seqniv-prec-seq-${esc(p.id)}"
               maxlength="3" size="4" class="seqniv-prec-input">
        <button class="seqniv-edit-btn seqniv-edit-btn--sm"
                onclick="seqnivEditAjouterPrecedence('${esc(p.id)}')">
          + précéd.
        </button>
      </span>`;

    const nbObj = (p.objectifs || []).length;
    const objs = (p.objectifs || [])
      .map(o => _rendreObjectif(o, p, toutes_parties))
      .join('');

    return `
      <details class="seqnivv2-section" open="">
        <summary class="seqnivv2-section-head">
          <span class="seqnivv2-section-title">
            Partie
            <input type="number" min="1" value="${esc(p.numero)}"
                   class="seqniv-num-input"
                   id="seqniv-num-${esc(p.id)}"
                   onchange="seqnivEditRenumeroter('${esc(p.id)}', this.value)">
          </span>
          <span class="seqnivv2-section-hint">${nbObj} objectif(s)</span>
          <button class="seqniv-edit-btn seqniv-edit-btn--danger seqniv-edit-btn--sm"
                  onclick="seqnivEditSupprimerPartie('${esc(p.id)}', ${nbObj})"
                  title="${nbObj > 0 ? 'La partie doit être vide' : 'Supprimer cette partie'}">
            Supprimer
          </button>
        </summary>
        <div class="seqnivv2-section-body">
          <div class="seqniv-prec-row">${precHtml}${precAdd}</div>
          ${objs || '<div class="seqnivv2-vide seqnivv2-vide--inline">Aucun objectif.</div>'}
        </div>
      </details>`;
  }

  function _rendreObjectif(o, partieCourante, toutes_parties) {
    const coherent = codeCoherent(o.code, partieCourante.numero);
    const alerteBadge = coherent
      ? ''
      : `<span class="seqniv-alert-badge"
               title="Code incohérent avec la convention : un objectif ${esc(o.code)} devrait être en partie ${parseInt(o.code[0],10)+1}">
            ⚠ convention
         </span>`;

    // Sélecteur de réassignation : les autres parties
    const options = toutes_parties
      .filter(p => p.id !== partieCourante.id)
      .map(p => `<option value="${esc(p.id)}">Partie ${esc(p.numero)}</option>`)
      .join('');
    const reassign = options
      ? `<span class="seqniv-reassign">
           <select id="seqniv-reassign-${esc(o.id)}" class="seqniv-reassign-sel">
             <option value="">Déplacer vers...</option>
             ${options}
           </select>
           <button class="seqniv-edit-btn seqniv-edit-btn--sm"
                   onclick="seqnivEditReassigner('${esc(o.id)}')">→</button>
         </span>`
      : '';

    // Marqueur "semi-protégé" pour l'objectif 01 (cours) : les éditions
    // de code/critères passent par un confirm() UI.
    const est_cours = (o.code === '01');
    const dataCours = est_cours ? 'data-cours="1"' : '';

    // Séries : édition inline (R4e4b) — chips avec ↑↓ × + bouton + par série
    const series = ['R', 'EA', 'F', 'A', 'E'].map(s => {
      const ex = (o.exos_par_serie && o.exos_par_serie[s]) || [];
      const nbExos = ex.length;

      const chips = ex.map((e, idx) => {
        const libelle = (e.exercice && e.exercice.fichier)
          ? e.exercice.fichier.replace(/\.tex$/i, '')
          : (e.exercice_id || '?').slice(0, 10);
        const btnUp = (idx > 0)
          ? `<button class="seqniv-chip-btn" title="Monter"
                     onclick="seqnivEditExoMonter('${esc(o.id)}', '${esc(s)}', '${esc(e.exercice_id)}')">↑</button>`
          : '<span class="seqniv-chip-btn seqniv-chip-btn--disabled">↑</span>';
        const btnDown = (idx < nbExos - 1)
          ? `<button class="seqniv-chip-btn" title="Descendre"
                     onclick="seqnivEditExoDescendre('${esc(o.id)}', '${esc(s)}', '${esc(e.exercice_id)}')">↓</button>`
          : '<span class="seqniv-chip-btn seqniv-chip-btn--disabled">↓</span>';
        const originSuffix = (s === 'R' && e.origin_niveau)
          ? ` <span class="seqniv-chip-origin">(${esc(e.origin_niveau)}/${esc(e.origin_seq)}/${esc(e.origin_serie)})</span>`
          : '';
        return `<span class="seqnivv2-exo-chip" title="origin_num=${esc(e.origin_num)} · ordre=${esc(e.ordre)}">
                  ${btnUp}${btnDown}
                  <span class="seqnivv2-exo-num">${esc(e.ordre)}</span>
                  <span class="seqnivv2-exo-lib">${esc(libelle)}</span>${originSuffix}
                  <button class="seqniv-chip-btn seqniv-chip-btn--danger" title="Retirer"
                          onclick="seqnivEditExoRetirer('${esc(o.id)}', '${esc(s)}', '${esc(e.exercice_id)}')">×</button>
                </span>`;
      }).join('');

      // Bouton "+ ajouter un exo" — le mécanisme diffère selon la série :
      //   - EA/F/A/E : <select> lazy-load depuis /api/v2/exos-disponibles
      //   - R        : 2 inputs (niveau/seq) puis <select> depuis
      //                /api/v2/exos-disponibles-revision
      const btnAjout = (s === 'R')
        ? `<span class="seqniv-ajout-R" id="seqniv-ajoutR-${esc(o.id)}">
             <input type="text" placeholder="N10" maxlength="3"
                    id="seqniv-ajoutR-niv-${esc(o.id)}" class="seqniv-prec-input">
             <input type="text" placeholder="S01" maxlength="3"
                    id="seqniv-ajoutR-seq-${esc(o.id)}" class="seqniv-prec-input">
             <button class="seqniv-edit-btn seqniv-edit-btn--sm"
                     onclick="seqnivEditChargerExosRevision('${esc(o.id)}')">
               Lister
             </button>
             <select id="seqniv-ajoutR-sel-${esc(o.id)}" class="seqniv-exo-sel"
                     style="display:none"
                     onchange="seqnivEditAjouterExoR('${esc(o.id)}', this.value)">
               <option value="">— Choisir un exo —</option>
             </select>
           </span>`
        : `<span class="seqniv-ajout-normale">
             <select id="seqniv-ajout-${esc(o.id)}-${esc(s)}" class="seqniv-exo-sel"
                     onchange="seqnivEditAjouterExo('${esc(o.id)}', '${esc(s)}', this.value)">
               <option value="">+ Ajouter...</option>
               <option value="__load__" data-load="1">— Charger le catalogue… —</option>
             </select>
           </span>`;

      return `<div class="seqnivv2-serie${chips ? '' : ' seqnivv2-serie--empty'}">
                <span class="seqnivv2-serie-code">${esc(s)}</span>
                <div class="seqnivv2-serie-exos">
                  ${chips || '<span class="seqnivv2-serie-hint">—</span>'}
                  ${btnAjout}
                </div>
              </div>`;
    }).join('');

    // Sélecteur méthode : alimenté paresseusement (1 fetch pour la séquence
    // entière, résultat mémorisé dans METHODES_CACHE), puis on renseigne
    // l'option sélectionnée si possible.
    const methode_id_courant = o.methode_id || '';
    const methode_titre_courant = o.methode_titre || '';
    const selectMethode = `
      <select id="seqniv-meth-${esc(o.id)}"
              class="seqniv-meth-sel"
              ${dataCours}
              data-current-id="${esc(methode_id_courant)}"
              data-current-titre="${esc(methode_titre_courant)}"
              onchange="seqnivEditChangerMethode('${esc(o.id)}', this.value)">
        <option value="">— Pas de méthode —</option>
        ${methode_id_courant
          ? `<option value="${esc(methode_id_courant)}" selected>
               ${esc(methode_titre_courant || methode_id_courant)} (courante)
             </option>`
          : ''}
        <option value="__load__" data-load="1">— Charger le catalogue… —</option>
      </select>`;

    // Les critères : 3 textareas repliés par défaut.
    const critereInput = (champ, label, valeur) => `
      <div class="seqniv-crit-edit-row">
        <label class="seqniv-crit-edit-label">${esc(label)}</label>
        <textarea class="seqniv-crit-edit-txt"
                  id="seqniv-crit-${esc(o.id)}-${esc(champ)}"
                  ${dataCours}
                  rows="2"
                  onblur="seqnivEditChangerCritere('${esc(o.id)}', '${esc(champ)}', this.value)"
                  >${esc(valeur || '')}</textarea>
      </div>`;

    // ── v0.6.4 : fin_cycle (case à cocher) ────────────────────────────────
    // Caractéristique du programme officiel — l'objectif est-il un attendu
    // de fin de cycle 4 ?
    const fin_cycle_checked = (o.fin_cycle || 'N') === 'O' ? 'checked' : '';
    const finCycleBloc = `
      <div class="seqniv-obj-meta">
        <label class="seqniv-obj-meta-label">Attendu de fin de cycle 4 :</label>
        <label class="seqniv-fin-cycle-toggle">
          <input type="checkbox"
                 id="seqniv-fc-${esc(o.id)}"
                 ${fin_cycle_checked}
                 onchange="seqnivEditChangerFinCycle('${esc(o.id)}', this.checked)">
          <span class="seqniv-fin-cycle-label">${fin_cycle_checked ? 'Oui' : 'Non'}</span>
        </label>
      </div>`;

    // ── v0.6.4 : notions associées (tags supprimables + select d'ajout) ───
    const notionsTags = (o.notions || []).map(n => `
      <span class="seqniv-notion-tag" data-notion-id="${esc(n.id)}">
        ${esc(n.titre || n.id)}
        <button type="button" class="seqniv-notion-tag-rm"
                title="Retirer cette notion"
                onclick="seqnivEditRetirerNotion('${esc(o.id)}', '${esc(n.id)}')">×</button>
      </span>`).join('');
    const notionsBloc = `
      <div class="seqniv-obj-meta">
        <label class="seqniv-obj-meta-label">Notions associées :</label>
        <div class="seqniv-notions-zone">
          <div id="seqniv-notions-tags-${esc(o.id)}" class="seqniv-notion-tags">
            ${notionsTags || '<span class="seqniv-notions-vide">— Aucune notion —</span>'}
          </div>
          <select id="seqniv-notion-sel-${esc(o.id)}" class="seqniv-notion-sel"
                  onchange="seqnivEditAjouterNotion('${esc(o.id)}', this.value)">
            <option value="">+ Ajouter une notion…</option>
            <option value="__load__" data-load="1">— Charger le catalogue… —</option>
          </select>
        </div>
      </div>`;

    return `
      <details class="seqnivv2-obj" open="">
        <summary class="seqnivv2-obj-head">
          <input type="text" value="${esc(o.code)}"
                 class="seqniv-code-input"
                 id="seqniv-code-${esc(o.id)}"
                 ${dataCours}
                 title="Code de l'objectif (${est_cours ? 'objectif 01 — Cours : édition avec confirmation' : 'éditable'})"
                 maxlength="4"
                 onchange="seqnivEditChangerCode('${esc(o.id)}', this.value)">
          <input type="text" value="${esc(o.nom || '')}"
                 class="seqniv-nom-input"
                 id="seqniv-nom-${esc(o.id)}"
                 placeholder="Nom de l'objectif"
                 onchange="seqnivEditChangerNom('${esc(o.id)}', this.value)">
          ${alerteBadge}
          ${reassign}
        </summary>
        <div class="seqnivv2-obj-body">
          <div class="seqniv-obj-meta">
            <label class="seqniv-obj-meta-label">Méthode liée :</label>
            ${selectMethode}
          </div>
          ${finCycleBloc}
          ${notionsBloc}
          <details class="seqniv-crit-edit">
            <summary class="seqniv-crit-edit-head">
              Critères d'évaluation ${est_cours ? '(objectif Cours — modification avec confirmation)' : ''}
            </summary>
            <div class="seqniv-crit-edit-body">
              ${critereInput('critere_F', 'F — Fondamental', o.critere_F)}
              ${critereInput('critere_A', 'A — Satisfaisant', o.critere_A)}
              ${critereInput('critere_E', 'E — Excellent',    o.critere_E)}
            </div>
          </details>
          <div class="seqnivv2-series">${series}</div>
        </div>
      </details>`;
  }

  // ── Handlers d'action (exposés window.seqnivEdit*) ───────────────────────

  async function seqnivEditCreerPartie(sn_id) {
    _status('Création…');
    const r = await apiJson('POST',
      `/api/v2/sequences-par-niveau/${encodeURIComponent(sn_id)}/parties`, {});
    if (r.ok) {
      _status('Partie créée', false);
      _rafraichirEdition();
    } else {
      _status('Erreur : ' + ((r.data && r.data.error) || r.status), true);
    }
  }
  window.seqnivEditCreerPartie = seqnivEditCreerPartie;

  async function seqnivEditRenumeroter(partie_id, numero) {
    const n = parseInt(numero, 10);
    if (!n || n < 1) { _status('Numéro invalide', true); return; }
    _status('Renumérotation…');
    const r = await apiJson('PATCH',
      `/api/v2/parties/${encodeURIComponent(partie_id)}`, { numero: n });
    if (r.ok) {
      _status('Renuméroté', false);
      _rafraichirEdition();
    } else {
      _status('Erreur : ' + ((r.data && r.data.error) || r.status), true);
      _rafraichirEdition(); // rollback visuel
    }
  }
  window.seqnivEditRenumeroter = seqnivEditRenumeroter;

  async function seqnivEditSupprimerPartie(partie_id, nbObj) {
    if (nbObj > 0) {
      _status(`Impossible : la partie contient ${nbObj} objectif(s). Les déplacer ou les supprimer d'abord.`, true);
      return;
    }
    if (!confirm('Supprimer définitivement cette partie ?')) return;
    _status('Suppression…');
    const r = await apiJson('DELETE',
      `/api/v2/parties/${encodeURIComponent(partie_id)}`);
    if (r.ok) {
      _status('Partie supprimée', false);
      _rafraichirEdition();
    } else {
      _status('Erreur : ' + ((r.data && r.data.error) || r.status), true);
    }
  }
  window.seqnivEditSupprimerPartie = seqnivEditSupprimerPartie;

  async function seqnivEditAjouterPrecedence(partie_id) {
    const niv = (document.getElementById(`seqniv-prec-niv-${partie_id}`) || {}).value;
    const seq = (document.getElementById(`seqniv-prec-seq-${partie_id}`) || {}).value;
    if (!niv || !seq) { _status('Niveau et séquence requis', true); return; }
    _status('Ajout…');
    const r = await apiJson('POST',
      `/api/v2/parties/${encodeURIComponent(partie_id)}/precedences`,
      { precedent_niveau: niv.trim().toUpperCase(), precedent_seq: seq.trim().toUpperCase() });
    if (r.ok) {
      _status('Précédence ajoutée', false);
      _rafraichirEdition();
    } else {
      _status('Erreur : ' + ((r.data && r.data.error) || r.status), true);
    }
  }
  window.seqnivEditAjouterPrecedence = seqnivEditAjouterPrecedence;

  async function seqnivEditSupprimerPrecedence(partie_id, niv, seq) {
    if (!confirm(`Supprimer la précédence ${niv}/${seq} ?`)) return;
    _status('Suppression…');
    const r = await apiJson('DELETE',
      `/api/v2/parties/${encodeURIComponent(partie_id)}/precedences/${encodeURIComponent(niv)}/${encodeURIComponent(seq)}`);
    if (r.ok) {
      _status('Précédence supprimée', false);
      _rafraichirEdition();
    } else {
      _status('Erreur : ' + ((r.data && r.data.error) || r.status), true);
    }
  }
  window.seqnivEditSupprimerPrecedence = seqnivEditSupprimerPrecedence;

  async function seqnivEditReassigner(objectif_id) {
    const sel = document.getElementById(`seqniv-reassign-${objectif_id}`);
    if (!sel || !sel.value) { _status('Choisir une partie cible', true); return; }
    _status('Déplacement…');
    const r = await apiJson('PATCH',
      `/api/v2/objectifs/${encodeURIComponent(objectif_id)}/partie`,
      { partie_id: sel.value });
    if (r.ok) {
      if (r.data && r.data.code_coherent === false) {
        _status('Déplacé (convention de code non respectée)', false);
      } else {
        _status('Objectif déplacé', false);
      }
      _rafraichirEdition();
    } else {
      _status('Erreur : ' + ((r.data && r.data.error) || r.status), true);
    }
  }
  window.seqnivEditReassigner = seqnivEditReassigner;

  // ── R4e3 : handlers d'édition d'un objectif ──────────────────────────────
  //
  // Cache du catalogue de méthodes : on fetch une fois par (niveau, seq)
  // et on mémorise. Le <select> dans _rendreObjectif utilise une option
  // spéciale "__load__" qui déclenche le fetch au premier clic.

  const METHODES_CACHE = {};  // clé: "niveau|seq" → [{id, titre, ...}]

  async function _chargerCatalogueMethodes() {
    const niveau = window.ATL_FILTRE_NIVEAU || '';
    const seq = window.ATL_FILTRE_SEQ || '';
    if (!niveau || !seq) return [];
    const cle = `${niveau}|${seq}`;
    if (METHODES_CACHE[cle]) return METHODES_CACHE[cle];
    const r = await apiJson('GET',
      `/api/v2/methodes?niveau=${encodeURIComponent(niveau)}&sequence=${encodeURIComponent(seq)}`);
    if (r.ok && r.data && Array.isArray(r.data.methodes)) {
      METHODES_CACHE[cle] = r.data.methodes;
      return r.data.methodes;
    }
    return [];
  }

  /** Confirm conditionnel pour l'objectif Cours (semi-protégé). */
  function _confirmCours(el, question) {
    if (!el || !el.dataset || !el.dataset.cours) return true;
    return confirm(`Objectif « Connaître le cours » (code 01) — ${question}\n\nContinuer ?`);
  }

  async function seqnivEditChangerCode(objectif_id, code) {
    const el = document.getElementById(`seqniv-code-${objectif_id}`);
    if (!_confirmCours(el, 'Modifier le code de cet objectif')) {
      _rafraichirEdition();  // rollback visuel
      return;
    }
    _status('Renommage code…');
    const r = await apiJson('PATCH',
      `/api/v2/objectifs/${encodeURIComponent(objectif_id)}/code`,
      { code: code });
    if (r.ok) {
      _status('Code modifié', false);
      _rafraichirEdition();
    } else {
      _status('Erreur : ' + ((r.data && r.data.error) || r.status), true);
      _rafraichirEdition();
    }
  }
  window.seqnivEditChangerCode = seqnivEditChangerCode;

  async function seqnivEditChangerNom(objectif_id, nom) {
    _status('Renommage…');
    const r = await apiJson('PATCH',
      `/api/v2/objectifs/${encodeURIComponent(objectif_id)}/nom`,
      { nom: nom });
    if (r.ok) {
      _status('Nom modifié', false);
      // Pas de _rafraichirEdition() ici pour ne pas casser le focus si
      // l'utilisateur édite encore. Le retour est déjà dans l'input.
    } else {
      _status('Erreur : ' + ((r.data && r.data.error) || r.status), true);
    }
  }
  window.seqnivEditChangerNom = seqnivEditChangerNom;

  async function seqnivEditChangerMethode(objectif_id, methode_id) {
    const sel = document.getElementById(`seqniv-meth-${objectif_id}`);
    if (!sel) return;

    // Valeur spéciale "__load__" : charger le catalogue et peupler le select.
    if (methode_id === '__load__') {
      _status('Chargement du catalogue…');
      const meths = await _chargerCatalogueMethodes();
      // Reconstruire les options
      const currentId = sel.getAttribute('data-current-id') || '';
      const currentTitre = sel.getAttribute('data-current-titre') || '';
      const opts = ['<option value="">— Pas de méthode —</option>'];
      meths.forEach(m => {
        const sel_attr = (m.id === currentId) ? ' selected' : '';
        opts.push(`<option value="${esc(m.id)}"${sel_attr}>${esc(m.titre)}</option>`);
      });
      // Si la méthode courante n'est pas dans le catalogue (autre séquence),
      // on la garde comme option additionnelle pour ne pas la perdre.
      if (currentId && !meths.some(m => m.id === currentId)) {
        opts.unshift(
          `<option value="${esc(currentId)}" selected>${esc(currentTitre || currentId)} (hors catalogue)</option>`
        );
      }
      sel.innerHTML = opts.join('');
      _status(`${meths.length} méthode(s) dans le catalogue`, false);
      return;
    }

    // Vraie mutation
    _status('Changement méthode…');
    const payload = methode_id ? { methode_id: methode_id } : { methode_id: null };
    const r = await apiJson('PATCH',
      `/api/v2/objectifs/${encodeURIComponent(objectif_id)}/methode`,
      payload);
    if (r.ok) {
      _status('Méthode modifiée', false);
      _rafraichirEdition();
    } else {
      _status('Erreur : ' + ((r.data && r.data.error) || r.status), true);
      _rafraichirEdition();
    }
  }
  window.seqnivEditChangerMethode = seqnivEditChangerMethode;

  async function seqnivEditChangerCritere(objectif_id, champ, valeur) {
    const el = document.getElementById(`seqniv-crit-${objectif_id}-${champ}`);
    if (!_confirmCours(el, `Modifier le critère ${champ.slice(-1)} de cet objectif`)) {
      _rafraichirEdition();
      return;
    }
    _status('Enregistrement critère…');
    const r = await apiJson('PATCH',
      `/api/v2/objectifs/${encodeURIComponent(objectif_id)}/criteres`,
      { [champ]: valeur });
    if (r.ok) {
      _status('Critère enregistré', false);
      // Pas de _rafraichirEdition() — l'utilisateur peut vouloir éditer
      // les critères consécutivement.
    } else {
      _status('Erreur : ' + ((r.data && r.data.error) || r.status), true);
    }
  }
  window.seqnivEditChangerCritere = seqnivEditChangerCritere;

  // ── v0.6.4 : fin_cycle (booléen) ────────────────────────────────────────

  async function seqnivEditChangerFinCycle(objectif_id, est_coche) {
    _status('Enregistrement…');
    const r = await apiJson('PATCH',
      `/api/v2/objectifs/${encodeURIComponent(objectif_id)}/fin-cycle`,
      { fin_cycle: est_coche ? 'O' : 'N' });
    if (r.ok) {
      _status('Fin de cycle mis à jour', false);
      // Mettre à jour le label "Oui"/"Non" sans rerender complet
      const checkbox = document.getElementById(`seqniv-fc-${objectif_id}`);
      if (checkbox) {
        const label = checkbox.parentElement.querySelector('.seqniv-fin-cycle-label');
        if (label) label.textContent = est_coche ? 'Oui' : 'Non';
      }
    } else {
      _status('Erreur : ' + ((r.data && r.data.error) || r.status), true);
      // Restaurer l'état précédent
      const checkbox = document.getElementById(`seqniv-fc-${objectif_id}`);
      if (checkbox) checkbox.checked = !est_coche;
    }
  }
  window.seqnivEditChangerFinCycle = seqnivEditChangerFinCycle;

  // ── v0.6.4 : notions associées (ajout/retrait) ──────────────────────────
  //
  // Le catalogue de notions est chargé paresseusement à la première
  // ouverture du <select>, et mémorisé par (niveau, sequence) pour ne
  // pas spammer l'API. Invalidé après chaque rafraîchissement complet
  // de l'édition.
  const NOTIONS_CACHE = new Map();   // clé : `${niveau}|${sequence}`

  function _niveauCourant() {
    return window.ATL_FILTRE_NIVEAU || '';
  }

  function _sequenceCourante() {
    return window.ATL_FILTRE_SEQ || '';
  }

  function _cleNotionsCache() {
    return `${_niveauCourant()}|${_sequenceCourante()}`;
  }

  async function _chargerCatalogueNotions(forcer = false) {
    const cle = _cleNotionsCache();
    if (!forcer && NOTIONS_CACHE.has(cle)) {
      return NOTIONS_CACHE.get(cle);
    }
    const niveau = _niveauCourant();
    const sequence = _sequenceCourante();
    if (!niveau || !sequence) return [];
    const url = `/api/v2/notions-de-sequence`
      + `?niveau=${encodeURIComponent(niveau)}`
      + `&sequence=${encodeURIComponent(sequence)}`;
    const r = await apiJson('GET', url);
    if (!r.ok) {
      _status('Erreur chargement notions : '
              + ((r.data && r.data.error) || r.status), true);
      return [];
    }
    const liste = (r.data && r.data.notions) || [];
    NOTIONS_CACHE.set(cle, liste);
    return liste;
  }

  async function seqnivEditAjouterNotion(objectif_id, valeur) {
    if (valeur === '__load__') {
      // L'utilisateur vient de cliquer "Charger le catalogue…"
      const sel = document.getElementById(`seqniv-notion-sel-${objectif_id}`);
      if (!sel) return;
      sel.disabled = true;
      const catalogue = await _chargerCatalogueNotions(true);
      // Reconstruire les options du <select>
      sel.innerHTML = '<option value="">+ Ajouter une notion…</option>'
        + catalogue.map(n =>
            `<option value="${escAttr(n.id)}">${escText(
              (n.num_connaissance ? `${n.num_connaissance} — ` : '') + (n.titre || n.id)
            )}</option>`
          ).join('');
      sel.disabled = false;
      sel.focus();
      return;
    }
    if (!valeur) return;

    _status('Association de la notion…');
    const r = await apiJson('POST',
      `/api/v2/objectifs/${encodeURIComponent(objectif_id)}/notions`,
      { notion_id: valeur });
    if (r.ok) {
      _status('Notion associée', false);
      // Re-render minimal : on ré-injecte les tags. Comme on n'a pas
      // d'utilitaire local de "patcher juste cette zone", on rerend
      // l'édition entière — c'est rapide et garde la cohérence.
      _rafraichirEdition();
    } else {
      _status('Erreur : ' + ((r.data && r.data.error) || r.status), true);
      // Reset le select à l'option par défaut
      const sel = document.getElementById(`seqniv-notion-sel-${objectif_id}`);
      if (sel) sel.value = '';
    }
  }
  window.seqnivEditAjouterNotion = seqnivEditAjouterNotion;

  async function seqnivEditRetirerNotion(objectif_id, notion_id) {
    _status('Dissociation…');
    const r = await apiJson('DELETE',
      `/api/v2/objectifs/${encodeURIComponent(objectif_id)}`
      + `/notions/${encodeURIComponent(notion_id)}`);
    if (r.ok) {
      _status('Notion dissociée', false);
      _rafraichirEdition();
    } else {
      _status('Erreur : ' + ((r.data && r.data.error) || r.status), true);
    }
  }
  window.seqnivEditRetirerNotion = seqnivEditRetirerNotion;

  // Helpers pour escaper les chaînes pour attributs / texte HTML.
  // (On a déjà `esc` en haut du fichier, mais on lui rajoute des variants
  // explicites pour la lisibilité.)
  function escAttr(s)  { return esc(String(s == null ? '' : s)); }
  function escText(s)  { return esc(String(s == null ? '' : s)); }

  // ── R4e4b : édition des exos par série ───────────────────────────────────
  //
  // Cache par (objectif, série) des exos disponibles, pour ne pas
  // spammer l'API à chaque rendu. Invalidé après chaque mutation.

  const EXOS_DISPO_CACHE = {};  // clé: "obj|serie" → [{id, nom, ...}]

  function _cleExosDispo(objectif_id, serie) {
    return `${objectif_id}|${serie}`;
  }

  function _invaliderCacheExosDispo(objectif_id, serie) {
    delete EXOS_DISPO_CACHE[_cleExosDispo(objectif_id, serie)];
  }

  async function _chargerExosDispo(objectif_id, serie) {
    const cle = _cleExosDispo(objectif_id, serie);
    if (EXOS_DISPO_CACHE[cle]) return EXOS_DISPO_CACHE[cle];

    const niveau = window.ATL_FILTRE_NIVEAU || '';
    const sequence = window.ATL_FILTRE_SEQ || '';
    if (!niveau || !sequence) return [];

    const r = await apiJson('GET',
      `/api/v2/exos-disponibles?niveau=${encodeURIComponent(niveau)}`
      + `&sequence=${encodeURIComponent(sequence)}`
      + `&serie_cible=${encodeURIComponent(serie)}`
      + `&objectif_id=${encodeURIComponent(objectif_id)}`);
    if (r.ok && r.data && Array.isArray(r.data.exos)) {
      EXOS_DISPO_CACHE[cle] = r.data.exos;
      return r.data.exos;
    }
    return [];
  }

  /** Handler du select d'ajout EA/F/A/E. Trois états :
   *   - value '__load__' : charge le catalogue et peuple le select
   *   - value ''          : no-op (option par défaut)
   *   - value = exo_id    : déclenche l'ajout
   */
  async function seqnivEditAjouterExo(objectif_id, serie, value) {
    const sel = document.getElementById(`seqniv-ajout-${objectif_id}-${serie}`);
    if (!sel) return;

    if (value === '__load__') {
      _status('Chargement du catalogue…');
      const exos = await _chargerExosDispo(objectif_id, serie);
      const opts = ['<option value="">+ Ajouter...</option>'];
      if (exos.length === 0) {
        opts.push('<option value="" disabled>Aucun exo dispo</option>');
      } else {
        exos.forEach(e => {
          const libelle = (e.fichier || '').replace(/\.tex$/i, '') || e.id;
          opts.push(`<option value="${esc(e.id)}">${esc(libelle)}</option>`);
        });
      }
      sel.innerHTML = opts.join('');
      _status(`${exos.length} exo(s) disponible(s)`, false);
      return;
    }

    if (!value) return;  // option vide

    _status('Ajout de l\u2019exo…');
    const r = await apiJson('POST',
      `/api/v2/objectifs/${encodeURIComponent(objectif_id)}/exos`,
      { serie: serie, exercice_id: value });
    if (r.ok) {
      _status('Exo ajouté', false);
      _invaliderCacheExosDispo(objectif_id, serie);
      _rafraichirEdition();
    } else {
      _status('Erreur : ' + ((r.data && r.data.error) || r.status), true);
      // On ré-ouvre le select sur l'option par défaut pour ne pas rester
      // bloqué sur un choix qui a échoué
      sel.value = '';
    }
  }
  window.seqnivEditAjouterExo = seqnivEditAjouterExo;

  /** Charge le catalogue revision depuis (niveau, seq) saisis, peuple le select. */
  async function seqnivEditChargerExosRevision(objectif_id) {
    const niv = (document.getElementById(`seqniv-ajoutR-niv-${objectif_id}`) || {}).value;
    const seq = (document.getElementById(`seqniv-ajoutR-seq-${objectif_id}`) || {}).value;
    if (!niv || !seq) {
      _status('Niveau et séquence requis', true);
      return;
    }
    _status('Chargement du catalogue révision…');
    const r = await apiJson('GET',
      `/api/v2/exos-disponibles-revision?niveau=${encodeURIComponent(niv.trim().toUpperCase())}`
      + `&sequence=${encodeURIComponent(seq.trim().toUpperCase())}`);
    const sel = document.getElementById(`seqniv-ajoutR-sel-${objectif_id}`);
    if (!sel) return;
    const opts = ['<option value="">— Choisir un exo —</option>'];
    if (r.ok && r.data && r.data.exos && r.data.exos.length) {
      r.data.exos.forEach(e => {
        const libelle = (e.fichier || '').replace(/\.tex$/i, '') || e.id;
        // On encode (niveau, seq, serie_code) dans la valeur pour que
        // le handler d'ajout ait tout sous la main sans fetch supplémentaire.
        const val = `${e.id}|${e.niveau}|${e.sequence}|${e.serie_code}`;
        opts.push(`<option value="${esc(val)}">${esc(libelle)} [${esc(e.serie_code)}]</option>`);
      });
      _status(`${r.data.exos.length} exo(s) disponibles en révision`, false);
    } else {
      opts.push('<option value="" disabled>Aucun exo trouvé</option>');
      _status('Aucun exo pour cette origine', true);
    }
    sel.innerHTML = opts.join('');
    sel.style.display = '';
  }
  window.seqnivEditChargerExosRevision = seqnivEditChargerExosRevision;

  /** Handler de sélection d'un exo en révision : décode le value et appelle l'API. */
  async function seqnivEditAjouterExoR(objectif_id, value) {
    if (!value) return;
    const parts = value.split('|');
    if (parts.length !== 4) {
      _status('Format invalide', true);
      return;
    }
    const [exo_id, origin_niveau, origin_seq, origin_serie] = parts;
    _status('Ajout en révision…');
    const r = await apiJson('POST',
      `/api/v2/objectifs/${encodeURIComponent(objectif_id)}/exos`,
      {
        serie: 'R',
        exercice_id: exo_id,
        origin_niveau: origin_niveau,
        origin_seq: origin_seq,
        origin_serie: origin_serie,
      });
    if (r.ok) {
      _status('Exo de révision ajouté', false);
      _rafraichirEdition();
    } else {
      _status('Erreur : ' + ((r.data && r.data.error) || r.status), true);
    }
  }
  window.seqnivEditAjouterExoR = seqnivEditAjouterExoR;

  async function seqnivEditExoRetirer(objectif_id, serie, exercice_id) {
    if (!confirm('Retirer cet exercice de la série ?')) return;
    _status('Retrait…');
    const r = await apiJson('DELETE',
      `/api/v2/objectifs/${encodeURIComponent(objectif_id)}`
      + `/exos/${encodeURIComponent(serie)}/${encodeURIComponent(exercice_id)}`);
    if (r.ok) {
      _status('Exo retiré', false);
      _invaliderCacheExosDispo(objectif_id, serie);
      _rafraichirEdition();
    } else {
      _status('Erreur : ' + ((r.data && r.data.error) || r.status), true);
    }
  }
  window.seqnivEditExoRetirer = seqnivEditExoRetirer;

  async function seqnivEditExoMonter(objectif_id, serie, exercice_id) {
    await _deplacerExo(objectif_id, serie, exercice_id, -1);
  }
  window.seqnivEditExoMonter = seqnivEditExoMonter;

  async function seqnivEditExoDescendre(objectif_id, serie, exercice_id) {
    await _deplacerExo(objectif_id, serie, exercice_id, +1);
  }
  window.seqnivEditExoDescendre = seqnivEditExoDescendre;

  /** Construit la nouvelle liste d'exercice_ids en permutant l'exo
   * cible d'une position, puis appelle l'API de réordonnancement. */
  async function _deplacerExo(objectif_id, serie, exercice_id, delta) {
    if (!DATA) return;
    // Trouver la liste actuelle des exos de (objectif, série) dans DATA
    let exosCourants = null;
    for (const p of (DATA.parties || [])) {
      for (const o of (p.objectifs || [])) {
        if (o.id === objectif_id) {
          exosCourants = (o.exos_par_serie && o.exos_par_serie[serie]) || [];
          break;
        }
      }
      if (exosCourants) break;
    }
    if (!exosCourants || exosCourants.length === 0) return;

    const ids = exosCourants.map(e => e.exercice_id);
    const idx = ids.indexOf(exercice_id);
    if (idx < 0) return;
    const newIdx = idx + delta;
    if (newIdx < 0 || newIdx >= ids.length) return;
    // Swap
    [ids[idx], ids[newIdx]] = [ids[newIdx], ids[idx]];

    _status('Réordonnancement…');
    const r = await apiJson('PATCH',
      `/api/v2/objectifs/${encodeURIComponent(objectif_id)}`
      + `/exos/${encodeURIComponent(serie)}/ordre`,
      { exercice_ids: ids });
    if (r.ok) {
      _status('Réordonné', false);
      _rafraichirEdition();
    } else {
      _status('Erreur : ' + ((r.data && r.data.error) || r.status), true);
      _rafraichirEdition();  // re-sync au cas où
    }
  }

  // ── Couleur thème (mirroir de R4e1) ──────────────────────────────────────

  const COULEUR_FAMILLE = {
    nombres: '#c0392b', donnees: '#2980b9', grandeurs: '#d35400',
    geometrie: '#8e44ad', algorithmique: '#e91e63', noir_gris: '#555555',
  };
  function _couleurTheme(famille) { return COULEUR_FAMILLE[famille] || '#777'; }

  // ── CSS ──────────────────────────────────────────────────────────────────

  function _injecterCSS() {
    if (document.getElementById('seqniv-edit-css')) return;
    const s = document.createElement('style');
    s.id = 'seqniv-edit-css';
    s.textContent = `
      .seqniv-edit-btn {
        font-size: 11px; padding: 3px 9px; border-radius: 3px;
        border: 1px solid var(--border, #d9d6c9); background: #fff;
        color: #333; cursor: pointer; line-height: 1.3;
      }
      .seqniv-edit-btn:hover { background: #f3f0e6; }
      .seqniv-edit-btn--primary {
        background: #3a3a38; color: #f0ede3; border-color: #3a3a38;
      }
      .seqniv-edit-btn--primary:hover { background: #555; }
      .seqniv-edit-btn--danger { color: #c0392b; border-color: #e7bcb5; }
      .seqniv-edit-btn--danger:hover { background: #fbeae6; }
      .seqniv-edit-btn--sm { padding: 1px 6px; font-size: 10px; }

      .seqniv-num-input {
        font-size: 12px; width: 48px; padding: 1px 4px;
        border: 1px solid #d9d6c9; border-radius: 3px; text-align: center;
        margin-left: 4px;
      }

      .seqniv-prec-chip {
        display: inline-flex; align-items: center; gap: 4px;
        font-size: 10px; background: #e7e3d4; color: #555;
        padding: 2px 6px; border-radius: 3px; margin-right: 4px;
      }
      .seqniv-prec-supp {
        background: transparent; border: 0; color: #c0392b; cursor: pointer;
        font-size: 12px; padding: 0 2px; line-height: 1;
      }
      .seqniv-prec-add {
        display: inline-flex; align-items: center; gap: 3px;
        margin-left: 6px;
      }
      .seqniv-prec-input {
        font-size: 10px; padding: 1px 4px; border: 1px solid #d9d6c9;
        border-radius: 3px; width: 40px;
      }

      .seqniv-reassign {
        display: inline-flex; align-items: center; gap: 3px;
        margin-left: auto;
      }
      .seqniv-reassign-sel {
        font-size: 10px; padding: 1px 4px;
        border: 1px solid #d9d6c9; border-radius: 3px; background: #fff;
      }

      .seqniv-alert-badge {
        font-size: 9px; color: #9a6e2a; background: #fbf3d9;
        padding: 1px 5px; border-radius: 3px; margin-left: 4px;
      }

      /* R4e3 — édition inline code/nom/méthode/critères */
      .seqniv-code-input {
        font-weight: 600; font-size: 11px;
        background: #3a3a38; color: #f0ede3;
        padding: 2px 5px; border-radius: 3px; width: 42px;
        text-align: center; border: 1px solid #3a3a38;
        font-family: ui-monospace, monospace;
      }
      .seqniv-code-input:focus {
        outline: 2px solid #ffb74d; outline-offset: 1px;
      }
      .seqniv-code-input[data-cours="1"] {
        background: #6a5a38; border-color: #6a5a38;
      }
      .seqniv-nom-input {
        flex: 1; font-weight: 500; font-size: 12px;
        padding: 2px 6px; border: 1px solid transparent;
        border-radius: 3px; background: transparent;
        min-width: 120px;
      }
      .seqniv-nom-input:hover { border-color: #e7e3d4; }
      .seqniv-nom-input:focus {
        border-color: #3a3a38; background: #fff; outline: none;
      }

      .seqniv-obj-meta {
        display: flex; align-items: center; gap: 8px;
        padding: 4px 0; font-size: 11px;
      }
      .seqniv-obj-meta-label {
        color: var(--text-secondary, #666); min-width: 80px;
      }
      .seqniv-meth-sel {
        flex: 1; font-size: 11px; padding: 2px 6px;
        border: 1px solid #d9d6c9; border-radius: 3px; background: #fff;
        max-width: 320px;
      }
      .seqniv-meth-sel[data-cours="1"] {
        background: #fdf6e3;
      }

      .seqniv-crit-edit {
        border: 1px solid var(--border-subtle, #e7e3d4);
        border-radius: 4px; margin-top: 2px;
      }
      .seqniv-crit-edit-head {
        padding: 5px 10px; cursor: pointer; font-size: 11px;
        color: var(--text-secondary, #666);
        list-style: none;
      }
      .seqniv-crit-edit-head::-webkit-details-marker { display: none; }
      .seqniv-crit-edit-head::before { content: "▸ "; color: #aaa; }
      .seqniv-crit-edit[open] .seqniv-crit-edit-head::before { content: "▾ "; }
      .seqniv-crit-edit-body {
        padding: 6px 10px 10px;
        display: flex; flex-direction: column; gap: 6px;
      }
      .seqniv-crit-edit-row {
        display: flex; align-items: flex-start; gap: 8px;
      }
      .seqniv-crit-edit-label {
        font-size: 10px; font-weight: 600; color: #555;
        width: 110px; flex-shrink: 0; padding-top: 4px;
      }
      .seqniv-crit-edit-txt {
        flex: 1; font-family: ui-monospace, monospace;
        font-size: 10px; padding: 4px 6px;
        border: 1px solid #d9d6c9; border-radius: 3px;
        background: #fff; line-height: 1.4; resize: vertical;
      }
      .seqniv-crit-edit-txt[data-cours="1"] { background: #fdf6e3; }
      .seqniv-crit-edit-txt:focus {
        outline: 1px solid #3a3a38; outline-offset: 0;
      }

      /* R4e4b — édition inline des exos */
      .seqniv-chip-btn {
        font-size: 9px; padding: 0 3px;
        background: transparent; border: 1px solid transparent;
        border-radius: 2px; color: #555; cursor: pointer;
        line-height: 1; min-width: 12px;
      }
      .seqniv-chip-btn:hover { background: #d9d6c9; border-color: #b0ac9c; }
      .seqniv-chip-btn--disabled {
        opacity: 0.25; cursor: default; display: inline-block;
        min-width: 12px; text-align: center; font-size: 9px; padding: 0 3px;
      }
      .seqniv-chip-btn--danger { color: #c0392b; }
      .seqniv-chip-btn--danger:hover { background: #fbeae6; border-color: #e7bcb5; }

      .seqniv-chip-origin {
        font-size: 9px; color: #6a5a38; font-style: italic;
      }

      .seqniv-ajout-normale,
      .seqniv-ajout-R {
        display: inline-flex; align-items: center; gap: 3px;
        margin-left: 6px;
      }
      .seqniv-exo-sel {
        font-size: 10px; padding: 1px 4px; border: 1px solid #d9d6c9;
        border-radius: 3px; background: #fff; max-width: 200px;
      }
    `;
    document.head.appendChild(s);
  }

  // ── Bootstrap ────────────────────────────────────────────────────────────

  function _init() {
    _injecterCSSBase();   // ex-R4e1 : styles .seqnivv2-* (base visuelle)
    _injecterCSS();       // styles .seqniv-edit-*, .seqniv-chip-*, etc.
    // Pas de toggle à injecter — on est toujours en édition.
    // Le premier rafraîchissement réel est déclenché par app.js lors de
    // l'ouverture de l'atelier livret (initLivret → seqnivEditRafraichir).
  }

  // ── CSS de base (fusionné depuis l'ex-ateliers_seqniv_v2.js R4e1) ────────
  //
  // On a gardé la même classe .seqnivv2-* pour ne pas casser les rendus
  // d'édition qui s'appuient dessus. Deux ajustements par rapport à la
  // version R4e1 :
  //   - #liv-atl-content-v2 est toujours visible (display: flex), alors
  //     que R4e1 le masquait par défaut (toggle Legacy/v2 supprimé)
  //   - les classes .seqnivv2-vue-toggle / .seqnivv2-vue-btn ne sont plus
  //     utilisées (toggles supprimés) ; elles restent pour l'instant
  //     dans la feuille au cas où un résidu en dépendrait.

  function _injecterCSSBase() {
    if (document.getElementById('seqnivv2-css')) return;
    const s = document.createElement('style');
    s.id = 'seqnivv2-css';
    s.textContent = `
      #liv-atl-content-v2 {
        display: flex;
        overflow-y: auto;
        flex: 1;
        padding: 18px 20px;
        flex-direction: column;
        gap: 12px;
      }
      .seqnivv2-header {
        display: flex; align-items: center; justify-content: space-between;
        gap: 12px; padding: 10px 14px;
        background: var(--bg-elevated, #f8f7f2);
        border: 1px solid var(--border, #d9d6c9);
        border-radius: 6px;
      }
      .seqnivv2-header-main { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
      .seqnivv2-header-niv {
        font-size: 11px; font-weight: 600; padding: 2px 6px;
        background: #3a3a38; color: #f0ede3; border-radius: 3px;
      }
      .seqnivv2-header-code { font-size: 14px; font-weight: 600; }
      .seqnivv2-header-nom  { font-size: 13px; color: var(--text-secondary, #555); }
      .seqnivv2-theme-badge {
        font-size: 11px; font-weight: 500; color: #fff;
        padding: 3px 8px; border-radius: 3px;
      }
      .seqnivv2-theme-badge--none { background: #bbb !important; color: #333; }

      .seqnivv2-section {
        border: 1px solid var(--border, #d9d6c9);
        border-radius: 6px; background: var(--bg, #fff);
      }
      .seqnivv2-section[open] .seqnivv2-section-head { border-bottom: 1px solid var(--border, #d9d6c9); }
      .seqnivv2-section-head {
        padding: 8px 12px; cursor: pointer; font-size: 12px;
        display: flex; align-items: center; gap: 10px;
        list-style: none;
      }
      .seqnivv2-section-head::-webkit-details-marker { display: none; }
      .seqnivv2-section-head::before { content: "▸"; color: #888; }
      .seqnivv2-section[open] .seqnivv2-section-head::before { content: "▾"; }
      .seqnivv2-section-title { font-weight: 600; flex: 1; }
      .seqnivv2-section-hint { font-size: 11px; color: var(--text-muted, #888); }
      .seqnivv2-section-body { padding: 10px 14px; display: flex; flex-direction: column; gap: 8px; }
      .seqnivv2-section-body--empty { color: var(--text-muted, #888); font-size: 12px; font-style: italic; }
      .seqnivv2-code {
        margin: 0 14px 10px; padding: 10px 12px;
        background: #2c2c2a; color: #d3d1c7; border-radius: 4px;
        font-size: 11px; white-space: pre; overflow-x: auto; line-height: 1.5;
      }

      .seqnivv2-prec-row { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 4px; }
      .seqnivv2-prec-badge {
        font-size: 10px; background: #e7e3d4; color: #555;
        padding: 2px 6px; border-radius: 3px;
      }

      .seqnivv2-obj {
        border: 1px solid var(--border-subtle, #e7e3d4);
        border-radius: 5px; background: var(--bg, #fff);
      }
      .seqnivv2-obj[open] .seqnivv2-obj-head { border-bottom: 1px solid var(--border-subtle, #e7e3d4); }
      .seqnivv2-obj-head {
        padding: 7px 10px; cursor: pointer; font-size: 12px;
        display: flex; align-items: center; gap: 8px; list-style: none;
      }
      .seqnivv2-obj-head::-webkit-details-marker { display: none; }
      .seqnivv2-obj-head::before { content: "▸"; color: #aaa; font-size: 10px; }
      .seqnivv2-obj[open] .seqnivv2-obj-head::before { content: "▾"; }
      .seqnivv2-obj-code {
        font-weight: 600; font-size: 11px;
        background: #3a3a38; color: #f0ede3;
        padding: 2px 6px; border-radius: 3px; min-width: 22px; text-align: center;
      }
      .seqnivv2-obj-nom { flex: 1; font-weight: 500; }
      .seqnivv2-obj-meth { font-size: 11px; color: var(--text-secondary, #666); }
      .seqnivv2-obj-meth--none { color: var(--text-muted, #999); font-style: italic; }
      .seqnivv2-obj-body { padding: 8px 12px; display: flex; flex-direction: column; gap: 10px; }

      .seqnivv2-crit { display: flex; flex-direction: column; gap: 4px; }
      .seqnivv2-crit-row { display: flex; align-items: flex-start; gap: 8px; font-size: 11px; }
      .seqnivv2-crit-badge {
        font-weight: 600; color: #fff; font-size: 10px;
        padding: 2px 6px; border-radius: 3px; min-width: 14px; text-align: center;
      }
      .seqnivv2-crit-txt { flex: 1; color: var(--text-primary, #333); line-height: 1.45; }
      .seqnivv2-crit-txt--empty { color: var(--text-muted, #aaa); font-style: italic; }

      .seqnivv2-series { display: flex; flex-direction: column; gap: 4px; }
      .seqnivv2-serie {
        display: flex; align-items: center; gap: 8px;
        padding: 5px 0; font-size: 11px; min-height: 22px;
      }
      .seqnivv2-serie--empty { color: var(--text-muted, #aaa); }
      .seqnivv2-serie-code {
        font-weight: 600; font-size: 10px;
        background: #e7e3d4; color: #3a3a38;
        padding: 2px 5px; border-radius: 3px; min-width: 18px; text-align: center;
      }
      .seqnivv2-serie--empty .seqnivv2-serie-code { background: #f3f0e6; color: #aaa; }
      .seqnivv2-serie-lib { min-width: 130px; color: var(--text-secondary, #666); }
      .seqnivv2-serie-hint { color: var(--text-muted, #ccc); }
      .seqnivv2-serie-exos { display: flex; flex-wrap: wrap; gap: 4px; flex: 1; }

      .seqnivv2-exo-chip {
        display: inline-flex; align-items: center; gap: 4px;
        background: #f6f3e9; border: 1px solid #e0dcc9;
        border-radius: 3px; padding: 1px 5px; font-size: 10px;
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      }
      .seqnivv2-exo-num { color: #999; }
      .seqnivv2-exo-lib { color: #333; }
      .seqnivv2-exo-origin {
        color: #9a6e2a; background: #fbf3d9;
        padding: 0 3px; border-radius: 2px; font-size: 9px;
      }

      .seqnivv2-vide {
        padding: 14px; text-align: center; color: var(--text-muted, #aaa);
        font-size: 12px; font-style: italic;
      }
      .seqnivv2-vide--inline { padding: 6px; text-align: left; }
    `;
    document.head.appendChild(s);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _init);
  } else {
    _init();
  }

  // Refonte v0.10 : le rafraîchissement à chaque changement de filtre de
  // portée séquence est déclenché directement par initLivret() côté app.js
  // (lui-même invoqué par atelInvoquerInit('livret') depuis
  // atelAppliquerSelectionsPortee). Plus besoin de listener 'change' ici.

})();
