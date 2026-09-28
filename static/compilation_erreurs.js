/* ────────────────────────────────────────────────────────────────────────────
   compilation_erreurs.js — v0.13.6.5.1.1
   ──────────────────────────────────────────────────────────────────────────

   Composant UI partagé pour afficher les erreurs d'une compilation LaTeX,
   avec :
     - liste cliquable des erreurs (ligne + message + contexte)
     - bouton "Voir le .tex brut" qui ouvre une zone avec lignes numérotées
       et highlight des lignes fautives ; le clic sur une erreur scrolle
       vers sa ligne
     - bouton "Voir le log complet pdflatex"
     - prise en charge du **multi-cible** : un sélecteur en haut quand le
       document a plusieurs cibles, le panneau d'erreurs s'adapte à la
       sélection

   Le module n'a pas de couplage avec un atelier précis : il prend un
   "contexte" en argument qui décrit COMMENT charger le .tex et le log.

   Usage côté appelant :
     compErreursAfficher('mon-conteneur-id', {
       titre: 'Erreurs de compilation',
       sousTitre: 'Document : Livret de cours',
       cibles: [{cible_id, libelle, ok, type_echec, premieres_erreurs}, ...],
       texUrl: cibleId => `/api/.../tex?cible=${cibleId}`,
       logUrl: cibleId => `/api/.../log?cible=${cibleId}`,
     });
   ──────────────────────────────────────────────────────────────────────────── */

(function () {
  'use strict';

  // ── État local par instance ────────────────────────────────────────────────
  //
  // Multi-instances : chaque conteneur a son état dans CTX_PAR_CONT.
  // L'état stocke : contexte de chargement, cible sélectionnée, lignes
  // fautives mémorisées pour le scroll, et drapeaux de chargement.

  const CTX_PAR_CONT = {};

  // ── Échappement HTML basique ────────────────────────────────────────────────

  function _esc(s) {
    const div = document.createElement('div');
    div.textContent = String(s == null ? '' : s);
    return div.innerHTML;
  }

  // ── Point d'entrée : rendre le panneau ──────────────────────────────────────

  function compErreursAfficher(conteneurId, contexte) {
    const cont = document.getElementById(conteneurId);
    if (!cont) return;

    // Filtre les cibles : on n'affiche que celles qui ont des erreurs
    // (les cibles OK n'ont rien à montrer dans ce panneau).
    const cibles = (contexte.cibles || []).filter(c => c.ok === false);
    if (cibles.length === 0) {
      cont.innerHTML = `
        <div class="comp-err-vide">
          <p>Aucune erreur à afficher.</p>
        </div>`;
      return;
    }

    // Mémoriser le contexte pour les actions ultérieures
    CTX_PAR_CONT[conteneurId] = {
      contexte:        contexte,
      cibleSelection:  cibles[0].cible_id,
      lignesFautives:  {},  // cible_id → Set(numéros)
      texCharge:       {},  // cible_id → bool
      logCharge:       {},
    };

    cont.innerHTML = _rendreSquelette(conteneurId, contexte, cibles);
    _rendrePanneauCible(conteneurId, cibles[0].cible_id);
  }

  // Squelette : header (titre, sélecteur de cible) + corps placeholder
  function _rendreSquelette(conteneurId, contexte, cibles) {
    const titre = contexte.titre || 'Erreurs de compilation';
    const sousTitre = contexte.sousTitre || '';

    // Sélecteur de cible : visible seulement si >1 cible KO
    const selecteur = cibles.length > 1 ? `
      <div class="comp-err-cibles">
        <label style="font-size:11px;color:var(--text-muted);margin-right:8px">
          Cible :
        </label>
        <select onchange="compErreursChangerCible('${conteneurId}', this.value)"
                style="font-size:12px;padding:2px 6px">
          ${cibles.map(c => `
            <option value="${_esc(c.cible_id)}">
              ${_esc(c.libelle || c.cible_id)} (${c.nb_erreurs || 0} erreur${(c.nb_erreurs||0) > 1 ? 's' : ''})
            </option>`).join('')}
        </select>
      </div>` : '';

    return `
      <div class="comp-err-panel"
           style="border:1px solid #fca5a5;border-radius:6px;
                  background:#fff5f5;padding:10px 14px">
        <div class="comp-err-header"
             style="display:flex;align-items:center;flex-wrap:wrap;
                    gap:10px;margin-bottom:8px">
          <div style="flex:1">
            <div style="font-weight:600;color:#7f1d1d">
              ⚠ ${_esc(titre)}
            </div>
            ${sousTitre ? `<div style="font-size:11px;color:#9c4747">${_esc(sousTitre)}</div>` : ''}
          </div>
          ${selecteur}
        </div>
        <div id="${conteneurId}__corps"></div>
      </div>`;
  }

  // ── Rendu du panneau pour une cible donnée ──────────────────────────────────

  function _rendrePanneauCible(conteneurId, cibleId) {
    const corps = document.getElementById(`${conteneurId}__corps`);
    const etat = CTX_PAR_CONT[conteneurId];
    if (!corps || !etat) return;

    const contexte = etat.contexte;
    const cible = (contexte.cibles || []).find(c => c.cible_id === cibleId);
    if (!cible) {
      corps.innerHTML = '<p>Cible introuvable.</p>';
      return;
    }

    etat.cibleSelection = cibleId;

    // Type d'échec
    const typeEchec = cible.type_echec || 'latex';
    const labelEchec = {
      'producteur':     'Erreur dans la génération du .tex (avant compilation)',
      'latex':          'Erreur de compilation LaTeX',
      'infrastructure': 'Erreur d\'infrastructure (pdflatex absent ou timeout)',
      'orchestration':  'Erreur d\'orchestration',
    }[typeEchec] || 'Erreur';

    // Liste des erreurs
    const erreurs = cible.premieres_erreurs || [];
    const lignesHtml = erreurs.map((e) => {
      const ligne = e.ligne != null ? `L.${e.ligne}` : '—';
      const ctx = e.contexte
        ? `<div class="comp-err-ctx"
                style="font-family:monospace;font-size:11px;color:#555;
                       padding:2px 8px;margin-top:2px">
             ${_esc(e.contexte)}
           </div>`
        : '';
      const clickable = e.ligne != null && typeEchec === 'latex'
        ? `onclick="compErreursScrollTo('${conteneurId}', '${_esc(cibleId)}', ${e.ligne})"`
        : '';
      const cls = e.ligne != null && typeEchec === 'latex'
                  ? 'comp-err-item clickable' : 'comp-err-item';
      const style = (e.ligne != null && typeEchec === 'latex')
        ? 'cursor:pointer;'
        : '';
      return `
        <li class="${cls}" ${clickable}
            style="${style}padding:6px 10px;border-bottom:1px solid #fee;list-style:none">
          <div style="display:flex;gap:8px;align-items:baseline">
            <span style="font-weight:600;color:#7c2d12;min-width:50px">${ligne}</span>
            <span style="font-size:12px;color:#1a1a1a">${_esc(e.message || '')}</span>
          </div>
          ${ctx}
        </li>`;
    }).join('');

    // Boutons .tex/log uniquement si la compilation est arrivée jusqu'à
    // latex (type_echec='latex'). Pour les erreurs producteur ou infra,
    // il n'y a pas forcément de .tex / log à montrer.
    const boutonsAvances = typeEchec === 'latex' ? `
      <div class="comp-err-actions" style="margin-top:10px;display:flex;gap:8px">
        <button class="btn-sm"
                onclick="compErreursToggleTex('${conteneurId}')"
                style="font-size:11px">
          <span id="${conteneurId}__tex-label">Voir le .tex brut</span>
        </button>
        <button class="btn-sm"
                onclick="compErreursToggleLog('${conteneurId}')"
                style="font-size:11px">
          <span id="${conteneurId}__log-label">Voir le log complet</span>
        </button>
      </div>
      <div id="${conteneurId}__tex" style="display:none;margin-top:8px"></div>
      <div id="${conteneurId}__log" style="display:none;margin-top:8px"></div>` : '';

    const lignesContenu = lignesHtml || `
      <li class="comp-err-item" style="padding:8px;color:var(--text-muted)">
        <em>Aucune erreur détaillée.</em>
      </li>`;

    corps.innerHTML = `
      <div class="comp-err-meta" style="font-size:11px;color:#7c2d12;margin-bottom:6px">
        ${_esc(labelEchec)} —
        ${cible.nb_erreurs || erreurs.length} erreur${(cible.nb_erreurs || erreurs.length) > 1 ? 's' : ''}.
      </div>
      <ul class="comp-err-list"
          style="margin:0;padding:0;background:white;
                 border:1px solid #fecaca;border-radius:4px;overflow:hidden">
        ${lignesContenu}
      </ul>
      ${boutonsAvances}
    `;
  }

  // ── Changer de cible (callback du <select>) ─────────────────────────────────

  function compErreursChangerCible(conteneurId, cibleId) {
    _rendrePanneauCible(conteneurId, cibleId);
  }

  // ── Toggle .tex brut ────────────────────────────────────────────────────────

  async function compErreursToggleTex(conteneurId) {
    const etat = CTX_PAR_CONT[conteneurId];
    if (!etat) return;
    const cibleId = etat.cibleSelection;
    const zone = document.getElementById(`${conteneurId}__tex`);
    const label = document.getElementById(`${conteneurId}__tex-label`);
    if (!zone || !label) return;

    if (zone.style.display === 'none') {
      zone.style.display = '';
      label.textContent = 'Masquer le .tex brut';
      if (!etat.texCharge[cibleId]) {
        zone.innerHTML = `
          <div style="padding:10px;color:var(--text-muted)">
            Chargement du .tex…
          </div>`;
        try {
          const url = etat.contexte.texUrl(cibleId);
          const rep = await fetch(url);
          if (rep.ok) {
            const tex = await rep.text();
            _afficherTex(conteneurId, cibleId, tex);
            etat.texCharge[cibleId] = true;
          } else {
            zone.innerHTML = `
              <div style="padding:10px;color:#7c2d12">
                Impossible de charger le .tex brut (${rep.status}).
              </div>`;
          }
        } catch (e) {
          zone.innerHTML = `
            <div style="padding:10px;color:#7c2d12">
              Erreur réseau : ${_esc(String(e))}
            </div>`;
        }
      }
    } else {
      zone.style.display = 'none';
      label.textContent = 'Voir le .tex brut';
    }
  }

  // ── Toggle log pdflatex ────────────────────────────────────────────────────

  async function compErreursToggleLog(conteneurId) {
    const etat = CTX_PAR_CONT[conteneurId];
    if (!etat) return;
    const cibleId = etat.cibleSelection;
    const zone = document.getElementById(`${conteneurId}__log`);
    const label = document.getElementById(`${conteneurId}__log-label`);
    if (!zone || !label) return;

    if (zone.style.display === 'none') {
      zone.style.display = '';
      label.textContent = 'Masquer le log complet';
      if (!etat.logCharge[cibleId]) {
        zone.innerHTML = `
          <div style="padding:10px;color:var(--text-muted)">
            Chargement du log…
          </div>`;
        try {
          const url = etat.contexte.logUrl(cibleId);
          const rep = await fetch(url);
          if (rep.ok) {
            const log = await rep.text();
            zone.innerHTML = `
              <pre style="background:#1e1e1e;color:#d4d4d4;font-size:11px;
                          padding:10px;max-height:400px;overflow:auto;
                          margin:0;border-radius:4px;
                          font-family:monospace;white-space:pre-wrap">${_esc(log)}</pre>`;
            etat.logCharge[cibleId] = true;
          } else {
            zone.innerHTML = `
              <div style="padding:10px;color:#7c2d12">
                Impossible de charger le log (${rep.status}).
              </div>`;
          }
        } catch (e) {
          zone.innerHTML = `
            <div style="padding:10px;color:#7c2d12">
              Erreur réseau : ${_esc(String(e))}
            </div>`;
        }
      }
    } else {
      zone.style.display = 'none';
      label.textContent = 'Voir le log complet';
    }
  }

  // ── Affichage du .tex avec lignes numérotées + highlight ───────────────────

  function _afficherTex(conteneurId, cibleId, tex) {
    const etat = CTX_PAR_CONT[conteneurId];
    if (!etat) return;
    const zone = document.getElementById(`${conteneurId}__tex`);
    if (!zone) return;

    // Lignes fautives à highlight = celles présentes dans premieres_erreurs
    const cible = (etat.contexte.cibles || [])
                    .find(c => c.cible_id === cibleId);
    const lignesFautives = new Set();
    (cible?.premieres_erreurs || []).forEach(e => {
      if (e.ligne != null) lignesFautives.add(e.ligne);
    });
    etat.lignesFautives[cibleId] = lignesFautives;

    const lignes = tex.split('\n').map((ligne, i) => {
      const numero = i + 1;
      const faute = lignesFautives.has(numero);
      const styleFaute = faute
        ? 'background:#fee2e2;border-left:3px solid #dc2626'
        : 'border-left:3px solid transparent';
      return `
        <div id="${conteneurId}__tex-l${numero}"
             style="display:flex;${styleFaute};font-family:monospace;font-size:11px">
          <span style="display:inline-block;width:40px;text-align:right;
                       padding:1px 8px 1px 4px;color:#888;user-select:none;
                       background:#f5f5f5;border-right:1px solid #ddd">${numero}</span>
          <span style="padding:1px 8px;white-space:pre">${_esc(ligne) || ' '}</span>
        </div>`;
    }).join('');

    zone.innerHTML = `
      <div style="background:white;border:1px solid #fecaca;
                  border-radius:4px;max-height:400px;overflow:auto">
        ${lignes}
      </div>`;
  }

  // ── Scroll vers une ligne fautive du .tex ──────────────────────────────────

  async function compErreursScrollTo(conteneurId, cibleId, ligne) {
    const etat = CTX_PAR_CONT[conteneurId];
    if (!etat) return;

    // Ouvrir/charger la zone .tex si pas encore fait
    const zone = document.getElementById(`${conteneurId}__tex`);
    if (!zone) return;
    if (zone.style.display === 'none' || !etat.texCharge[cibleId]) {
      await compErreursToggleTex(conteneurId);
    }

    const elt = document.getElementById(`${conteneurId}__tex-l${ligne}`);
    if (elt) {
      elt.scrollIntoView({ behavior: 'smooth', block: 'center' });
      // Flash temporaire
      const oldStyle = elt.style.boxShadow;
      elt.style.boxShadow = 'inset 0 0 0 2px #dc2626';
      setTimeout(() => { elt.style.boxShadow = oldStyle; }, 1500);
    }
  }

  // ── Fermer le panneau (caller-side) ────────────────────────────────────────

  function compErreursFermer(conteneurId) {
    const cont = document.getElementById(conteneurId);
    if (cont) cont.innerHTML = '';
    delete CTX_PAR_CONT[conteneurId];
  }

  // ── Exposition globale ─────────────────────────────────────────────────────

  window.compErreursAfficher      = compErreursAfficher;
  window.compErreursChangerCible  = compErreursChangerCible;
  window.compErreursToggleTex     = compErreursToggleTex;
  window.compErreursToggleLog     = compErreursToggleLog;
  window.compErreursScrollTo      = compErreursScrollTo;
  window.compErreursFermer        = compErreursFermer;
})();
