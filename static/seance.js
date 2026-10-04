// ============================================================================
// static/seance.js — v0.43.0 (v0.43.1 : séances du jour ; v0.44.0 : documents ;
// v0.46.0 : en-tête de séance partagé avec l'Observation, static/observation.js)
// Suivi › Début de séance : séance en cours (ou prochaine, ou dernière du
// jour), mise en route affichée au professeur, absents notés d'un clic sur le
// plan de classe de la semaine (sinon liste alphabétique).
// Backend : /api/seance/en-cours, /api/seance, /api/seance/absence.
// Classe : sélecteur partagé du Suivi (#classe-sel).
// ============================================================================

const SC = { date: null, creneau: null, classe: null, donnees: null, occupe: false, jour: [] };

const _SC_JOURS = { lun: 'lundi', mar: 'mardi', mer: 'mercredi', jeu: 'jeudi', ven: 'vendredi', sam: 'samedi' };
const _SC_STATUT = { en_cours: 'en cours', a_venir: 'pas encore commencée', terminee: 'terminée' };

function _scE(s) { return escapeHtml(String(s == null ? '' : s)); }
function _scAnnee() { return (typeof ANNEE_ACTIVE !== 'undefined' && ANNEE_ACTIVE) || ''; }
// v0.43.1 — Classe de la séance affichée : celle choisie dans la liste des
// séances du jour (même si le sélecteur Classe, filtré par niveau, ne la
// propose pas), sinon celle du sélecteur.
function _scClasse() {
  if (SC.classe) return SC.classe;
  const s = document.getElementById('classe-sel'); return s ? s.value : '';
}
function _scSelectionnerClasse(cid) {
  SC.classe = cid;
  const sel = document.getElementById('classe-sel');
  if (sel && [...sel.options].some(o => o.value === cid)) {
    sel.value = cid;
    if (typeof currentCid !== 'undefined') currentCid = cid;
  }
}
function _scAujourdhui() {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}
function _scDateFr(iso) { const [a, m, j] = iso.split('-'); return `${j}/${m}`; }

async function _scApi(url, opts) {
  const r = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...(opts || {}) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || ('Erreur ' + r.status));
  return d;
}

// Entrée dans le sous-onglet : séance en cours toutes classes confondues ; la
// classe de cette séance devient la classe sélectionnée.
async function scInit() {
  SC.date = _scAujourdhui();
  const inp = document.getElementById('sc-date');
  if (inp) inp.value = SC.date;
  await scSeanceEnCours();
}

async function scSeanceEnCours() {
  SC.date = _scAujourdhui();
  const inp = document.getElementById('sc-date');
  if (inp) inp.value = SC.date;
  let s = null;
  try {
    s = (await _scApi('/api/seance/en-cours?annee=' + encodeURIComponent(_scAnnee()))).seance;
  } catch (e) { /* pas de séance */ }
  await _scChargerJour();
  if (s) {
    _scSelectionnerClasse(s.classe_id);
    SC.creneau = s.creneau;
    await scCharger();
  } else {
    await scClasseChangee();
  }
}

// v0.43.1 — Toutes les séances du jour (toutes classes), toujours affichées.
async function _scChargerJour() {
  try {
    SC.jour = (await _scApi(`/api/seance/jour?annee=${encodeURIComponent(_scAnnee())}`
      + `&date=${SC.date}`)).seances || [];
  } catch (e) { SC.jour = []; }
  _scRendreJour();
}

function _scRendreJour() {
  const ch = document.getElementById('sc-choix');
  if (!ch) return;
  if (!SC.jour.length) {
    ch.innerHTML = `<span class="sc-jour-vide">Aucun cours le ${_scDateFr(SC.date)}.</span>`;
    return;
  }
  const cid = _scClasse();
  ch.innerHTML = '<span class="sc-jour">' + SC.jour.map(x => {
    const actif = x.classe_id === cid && x.creneau === SC.creneau;
    return `<button class="sc-jour-btn${actif ? ' actif' : ''} sc-st-${x.statut || ''}"
      onclick="scChoisirSeanceDuJour('${x.classe_id}', '${_scE(x.creneau)}')"
      title="${_scE(x.heure_debut)}–${_scE(x.heure_fin)}">${_scE(x.creneau)} · ${_scE(x.classe)}</button>`;
  }).join('') + '</span>';
}

async function scChoisirSeanceDuJour(cid, creneau) {
  _scSelectionnerClasse(cid);
  SC.creneau = creneau;
  await scCharger();
}

// Classe ou jour changés : séance en cours / prochaine / dernière de la classe
// ce jour-là (aujourd'hui), ou la première du jour choisi.
async function scClasseChangee() {
  SC.creneau = null;
  const sel = document.getElementById('classe-sel');
  SC.classe = sel ? sel.value : null;     // le sélecteur reprend la main
  const cid = _scClasse();
  if (!cid) { _scVide('Choisissez une classe.'); return; }
  if (SC.date === _scAujourdhui()) {
    try {
      const s = (await _scApi(`/api/seance/en-cours?annee=${encodeURIComponent(_scAnnee())}`
        + `&classe_id=${encodeURIComponent(cid)}`)).seance;
      if (s) SC.creneau = s.creneau;
    } catch (e) {}
  }
  await scCharger();
}

async function scChoisirJour() {
  SC.date = document.getElementById('sc-date').value || _scAujourdhui();
  await _scChargerJour();
  await scClasseChangee();
}

async function scChoisirSeance(creneau) {
  SC.creneau = creneau;
  await scCharger();
}

function _scVide(msg) {
  SC.donnees = null;
  const t = document.getElementById('sc-titre'); if (t) t.innerHTML = '';
  const c = document.getElementById('sc-corps'); if (c) c.innerHTML = `<p class="sc-vide">${_scE(msg)}</p>`;
  const o = document.getElementById('ov-corps'); if (o) o.innerHTML = `<p class="sc-vide">${_scE(msg)}</p>`;
  const w = document.getElementById('tw-corps'); if (w) w.innerHTML = `<p class="sc-vide">${_scE(msg)}</p>`;
  _scRendreJour();
}

async function scCharger() {
  const cid = _scClasse();
  if (!cid) { _scVide('Choisissez une classe.'); return; }
  if (!SC.creneau) {
    // Pas de séance retenue (autre jour, ou plus rien aujourd'hui) : la
    // première séance du jour choisi.
    let jour = [];
    try {
      jour = (await _scApi(`/api/seance/jour?annee=${encodeURIComponent(_scAnnee())}`
        + `&classe_id=${encodeURIComponent(cid)}&date=${SC.date}`)).seances || [];
    } catch (e) {}
    if (!jour.length) {
      _scVide(`Pas de cours en classe entière pour cette classe le ${_scDateFr(SC.date)}.`);
      return;
    }
    SC.creneau = jour[0].creneau;
  }
  try {
    SC.donnees = await _scApi(`/api/seance?annee=${encodeURIComponent(_scAnnee())}`
      + `&classe_id=${encodeURIComponent(cid)}&date=${SC.date}&creneau=${encodeURIComponent(SC.creneau)}`);
  } catch (e) { _scVide(e.message); return; }
  _scRendre();
  // v0.46.0 — Même séance pour l'Observation ; v0.47.0 — et le Travail.
  if (typeof ovCharger === 'function') await ovCharger();
  if (typeof twCharger === 'function') await twCharger();
}

function _scRendre() {
  const d = SC.donnees;
  if (!d) return;
  const s = d.seance;
  // Libellé du sélecteur sans l'établissement entre parenthèses.
  const nomClasse = s.classe || '';
  document.getElementById('sc-titre').innerHTML = `
    <strong>${_scE(nomClasse)}</strong> — ${_SC_JOURS[s.jour] || s.jour} ${_scDateFr(s.date)},
    ${_scE(s.creneau)} (${_scE(s.heure_debut)}–${_scE(s.heure_fin)})
    <span class="sc-statut sc-statut-${s.statut}">${_SC_STATUT[s.statut] || ''}</span>`;
  _scRendreJour();
  document.getElementById('sc-corps').innerHTML = `
    <div class="sc-bloc">
      <div class="sc-bloc-titre">Mise en route</div>
      <div class="sc-mer">${_scTexteMiseEnRoute(d.mise_en_route)}</div>
    </div>
    <div class="sc-bloc">
      <div class="sc-bloc-titre">Absents <span id="sc-compte" class="sc-compte"></span></div>
      <p class="sc-aide">Un clic sur un élève le marque absent ; un second clic annule. Enregistré aussitôt.</p>
      <div class="sc-absents">
        <div id="sc-zone-plan" class="sc-zone-plan"></div>
        <div id="sc-zone-liste" class="sc-zone-liste"></div>
      </div>
    </div>
    <div class="sc-bloc" id="sc-bloc-docs"></div>`;
  _scRendreAbsents();
  _scRendreDocuments();
}

function _scTexteMiseEnRoute(m) {
  // v0.43.2 — Mise en route non faite (exception à la date de la séance).
  if (m && m.non_faite) {
    return `<label class="sc-nonfaite"><input type="checkbox" checked onchange="scMerNonFaite(false)">
      Mise en route non faite</label>
      <span class="sc-sans">${_scE(m.non_faite.motif)} — reportée à la séance suivante.</span>`;
  }
  const caseNF = (m && m.active && m.type) ? `
    <div class="sc-nonfaite-ligne">
      <label class="sc-nonfaite"><input type="checkbox" onchange="scMerNonFaite(true)"> Mise en route non faite</label>
      <input id="sc-nf-comm" class="sc-nf-comm" placeholder="Commentaire (facultatif)">
    </div>` : '';
  if (m && m.active && !m.type && m.date_debut && SC.donnees && SC.donnees.seance.date < m.date_debut) {
    return `<span class="sc-sans">Mises en route à partir du ${_scDateFr(m.date_debut)}.</span>`;
  }
  return _scTexteMerPrevue(m) + caseNF;
}

async function scMerNonFaite(nonFaite) {
  const d = SC.donnees;
  if (!d) return;
  const comm = document.getElementById('sc-nf-comm');
  try {
    await _scApi('/api/seance/mer-non-faite', { method: 'PUT', body: JSON.stringify({
      annee: _scAnnee(), classe_id: _scClasse(), date: d.seance.date, creneau: d.seance.creneau,
      non_faite: nonFaite, commentaire: comm ? comm.value : '' }) });
  } catch (e) {
    if (typeof showToast === 'function') showToast(e.message, true); else alert(e.message);
  }
  await scCharger();     // la mise en route (et la suite) a changé
}

function _scTexteMerPrevue(m) {
  if (!m || !m.type) return '<span class="sc-sans">Pas de mise en route pour cette séance.</span>';
  if (m.type === 'mer_auto') {
    const env = (m.enveloppes || []).join(', ');
    return `Automatismes (Leitner), séance ${m.rang} : <strong>enveloppe${m.enveloppes.length > 1 ? 's' : ''} ${_scE(env)}</strong>.`;
  }
  return `Progression de MER : <strong>séance n° ${m.rang}</strong>.`;
}

function _scRendreAbsents() {
  const d = SC.donnees;
  const abs = new Set(d.absents);
  const compte = document.getElementById('sc-compte');
  if (compte) compte.textContent = `${abs.size} / ${d.eleves.length}`;
  const zp = document.getElementById('sc-zone-plan');
  const zl = document.getElementById('sc-zone-liste');
  const chip = e => `<button class="sc-eleve${abs.has(e.id) ? ' sc-absent' : ''}" onclick="scBasculer('${e.id}')"
      aria-pressed="${abs.has(e.id)}">${_scE(e.etiquette)}</button>`;
  if (!d.plan) {
    zp.innerHTML = '';
    zp.style.display = 'none';
    zl.innerHTML = `<div class="sc-liste-titre">Classe (ordre alphabétique)</div>
      <div class="sc-liste sc-liste-large">${d.eleves.map(chip).join('')}</div>`;
    return;
  }
  zp.style.display = '';
  const S = window.SallesPur, p = d.plan;
  const noms = {}; d.eleves.forEach(e => { noms[e.id] = e; });
  const parNum = {}; p.placements.forEach(x => { parNum[x.numero] = x; });
  const c = S.cadre(p.places, 40);
  const largTab = Math.min(300, c.w * 0.5), xTab = c.x + (c.w - largTab) / 2;
  const places = p.places.map(pl => {
    const occ = parNum[pl.numero];
    const e = occ ? noms[occ.eleve_id] : null;
    const rect = `<rect x="${-S.L / 2}" y="${-S.H / 2}" width="${S.L}" height="${S.H}" rx="2"
        transform="translate(${pl.x} ${pl.y}) rotate(${pl.angle || 0})"></rect>`;
    if (p.reservations.includes(pl.numero)) {
      return `<g class="sc-place sc-aesh">${rect}<text x="${pl.x}" y="${pl.y}">AESH</text></g>`;
    }
    if (!e) return `<g class="sc-place sc-libre">${rect}</g>`;
    const lib = e.etiquette, i = lib.indexOf(' ');
    const coupe = t => (t.length > 10 ? t.slice(0, 8) + '…' : t);
    const [l1, l2] = i > 0 ? [lib.slice(0, i), lib.slice(i + 1)] : [lib, ''];
    return `<g class="sc-place sc-occupee${abs.has(e.id) ? ' sc-absent' : ''}" onclick="scBasculer('${e.id}')">
      <title>${_scE(e.prenom)} ${_scE(e.nom)}</title>${rect}
      <text x="${pl.x}" y="${pl.y - 6}">${_scE(coupe(l1))}</text>
      <text x="${pl.x}" y="${pl.y + 8}">${_scE(coupe(l2))}</text></g>`;
  }).join('');
  zp.innerHTML = `<div class="sc-liste-titre">Plan de classe — salle ${_scE(p.salle.nom)}</div>
    <svg id="sc-svg" viewBox="${c.x} ${c.y - 30} ${c.w} ${c.h + 30}" preserveAspectRatio="xMidYMin meet">
      <g class="sal-tableau"><rect x="${xTab}" y="${c.y - 24}" width="${largTab}" height="8" rx="2"></rect>
      <text x="${xTab + largTab / 2}" y="${c.y - 4}">Tableau</text></g>${places}</svg>`;
  const places_ids = new Set(p.placements.map(x => x.eleve_id));
  const non = d.eleves.filter(e => !places_ids.has(e.id));
  zl.innerHTML = non.length
    ? `<div class="sc-liste-titre">Non placés (${non.length})</div><div class="sc-liste">${non.map(chip).join('')}</div>`
    : '';
}

async function scBasculer(eid) {
  const d = SC.donnees;
  if (!d || SC.occupe) return;
  SC.occupe = true;
  const absent = !d.absents.includes(eid);
  try {
    const r = await _scApi('/api/seance/absence', { method: 'PUT', body: JSON.stringify({
      annee: _scAnnee(), classe_id: _scClasse(), eleve_id: eid, date: d.seance.date,
      creneau: d.seance.creneau, absent }) });
    d.absents = r.absents;
  } catch (e) {
    if (typeof showToast === 'function') showToast(e.message, true); else alert(e.message);
  }
  SC.occupe = false;
  _scRendreAbsents();
  // Les absents changent la liste « À rattraper » des séances suivantes ;
  // pour celle-ci, un élève absent n'y figure plus : recharger les documents.
  await _scRechargerDocuments();
}

// ── v0.44.0 — Documents ─────────────────────────────────────────────────────

const _SC_CATEG = { pedagogique: 'pédagogique', administratif: 'administratif', sortie: 'sortie' };

async function _scRechargerDocuments() {
  const d = SC.donnees;
  if (!d) return;
  try {
    const r = await _scApi(`/api/seance?annee=${encodeURIComponent(_scAnnee())}`
      + `&classe_id=${encodeURIComponent(_scClasse())}&date=${d.seance.date}&creneau=${encodeURIComponent(d.seance.creneau)}`);
    d.documents = r.documents;
    d.seance_suivante = r.seance_suivante;
  } catch (e) {}
  _scRendreDocuments();
}

function _scRendreDocuments() {
  const zone = document.getElementById('sc-bloc-docs');
  const d = SC.donnees;
  if (!zone || !d || !d.documents) return;
  const noms = {}; d.eleves.forEach(e => { noms[e.id] = e; });
  const nv = d.documents.nouveaux;
  const ligneDoc = x => `
    <li class="sc-doc${x.distribue ? ' sc-doc-ok' : ''}">
      <label><input type="checkbox" ${x.distribue ? 'checked' : ''}
        onchange="scDistribuer('${x.id}', this.checked)"> ${_scE(x.libelle)}</label>
      ${x.origine === 'ponctuel' ? `<span class="sc-doc-tag">${_scE(_SC_CATEG[x.categorie] || x.categorie)}</span>` : ''}
      ${x.reporte ? `<span class="sc-doc-tag sc-doc-report">reporté du ${_scDateFr(x.cible_date)}</span>` : ''}
      ${x.distribue ? `<select class="sc-doc-retour" title="Retour attendu (suivi dans l'onglet Travail)"
          onchange="scDocRetour('${x.id}', this.value)">
          <option value=""${!x.retour ? ' selected' : ''}>pas de retour</option>
          <option value="3"${x.retour === 'rapporter' && x.delai_jours === 3 ? ' selected' : ''}>à rapporter sous 3 jours</option>
          <option value="7"${x.retour === 'rapporter' && x.delai_jours !== 3 ? ' selected' : ''}>à rapporter sous 1 semaine</option>
        </select>` : ''}
      ${x.origine === 'ponctuel' ? `<button class="btn-lien sc-doc-suppr" onclick="scSupprimerDocument('${x.id}')" title="Supprimer ce document ajouté à la volée">supprimer</button>` : ''}
    </li>`;
  const suiv = d.seance_suivante;
  const rat = d.documents.a_rattraper;
  zone.innerHTML = `
    <div class="sc-bloc-titre">Documents</div>
    <div class="sc-docs">
      <div class="sc-docs-col">
        <div class="sc-liste-titre">Nouveaux documents (cocher une fois distribués à la classe)</div>
        ${nv.length ? `<ul class="sc-doc-liste">${nv.map(ligneDoc).join('')}</ul>`
                    : '<p class="sc-aide">Aucun document prévu pour cette séance.</p>'}
        <details class="sc-doc-ajout">
          <summary>+ Ajouter un document</summary>
          <div class="sc-doc-form">
            <input id="sc-doc-lib" placeholder="Libellé (ex : mot du professeur principal)">
            <select id="sc-doc-cat">
              <option value="administratif">administratif</option>
              <option value="sortie">sortie</option>
              <option value="pedagogique">pédagogique</option>
            </select>
            <label><input type="radio" name="sc-doc-pour" value="cette" checked> cette séance</label>
            ${suiv ? `<label><input type="radio" name="sc-doc-pour" value="prochaine"> prochaine séance
              (${_scDateFr(suiv.date)}, ${_scE(suiv.creneau)})</label>` : ''}
            <button class="btn-sm btn-prim" onclick="scAjouterDocument()">Ajouter</button>
          </div>
        </details>
      </div>
      <div class="sc-docs-col">
        <div class="sc-liste-titre">À rattraper (élèves absents quand le document a été distribué)</div>
        ${rat.length ? rat.map(r => `
          <div class="sc-rat">
            <div class="sc-rat-nom">${_scE((noms[r.eleve_id] || {}).etiquette || r.eleve_id)}</div>
            <ul class="sc-doc-liste">${r.documents.map(x => `
              <li class="sc-doc${x.donne ? ' sc-doc-ok' : ''}"><label><input type="checkbox" ${x.donne ? 'checked' : ''}
                onchange="scDonner('${x.id}', '${r.eleve_id}', this.checked)"> ${_scE(x.libelle)}</label>
                <span class="sc-doc-tag">du ${_scDateFr(x.distribue_date)}</span>
                ${x.retour ? `<span class="sc-doc-tag sc-doc-retour-tag">${{ faire: 'travail à faire', rendre: 'travail à rendre', rapporter: 'à rapporter' }[x.retour]}</span>` : ''}</li>`).join('')}
            </ul>
          </div>`).join('')
          : '<p class="sc-aide">Rien à rattraper.</p>'}
      </div>
    </div>`;
}

async function _scDocAction(url, opts) {
  try { await _scApi(url, opts); }
  catch (e) { if (typeof showToast === 'function') showToast(e.message, true); else alert(e.message); }
  await _scRechargerDocuments();
}

function _scSeanceCourante() {
  const s = SC.donnees.seance;
  return { annee: _scAnnee(), classe_id: _scClasse(), date: s.date, creneau: s.creneau };
}

function scDistribuer(id, distribue) {
  return _scDocAction(`/api/seance/document/${id}/distribue`, { method: 'PUT',
    body: JSON.stringify({ ..._scSeanceCourante(), distribue }) });
}

function scDonner(id, eleveId, donne) {
  return _scDocAction(`/api/seance/document/${id}/donne`, { method: 'PUT',
    body: JSON.stringify({ ..._scSeanceCourante(), eleve_id: eleveId, donne }) });
}

function scAjouterDocument() {
  const lib = document.getElementById('sc-doc-lib').value.trim();
  if (!lib) { document.getElementById('sc-doc-lib').focus(); return; }
  const pour = (document.querySelector('input[name="sc-doc-pour"]:checked') || {}).value || 'cette';
  return _scDocAction('/api/seance/document', { method: 'POST', body: JSON.stringify({
    ..._scSeanceCourante(), libelle: lib, categorie: document.getElementById('sc-doc-cat').value, pour }) });
}

// v0.47.0 — Document à rapporter (délai en jours ; '' = pas de retour).
function scDocRetour(id, valeur) {
  return _scDocAction(`/api/seance/document/${id}/retour`, { method: 'PUT',
    body: JSON.stringify({ retour: valeur ? 'rapporter' : '', delai_jours: parseInt(valeur || '0', 10) }) });
}

function scSupprimerDocument(id) {
  if (!confirm('Supprimer ce document ?')) return;
  return _scDocAction(`/api/seance/document/${id}`, { method: 'DELETE' });
}
