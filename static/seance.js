// ============================================================================
// static/seance.js — v0.43.0
// Suivi › Début de séance : séance en cours (ou prochaine, ou dernière du
// jour), mise en route affichée au professeur, absents notés d'un clic sur le
// plan de classe de la semaine (sinon liste alphabétique).
// Backend : /api/seance/en-cours, /api/seance, /api/seance/absence.
// Classe : sélecteur partagé du Suivi (#classe-sel).
// ============================================================================

const SC = { date: null, creneau: null, donnees: null, occupe: false };

const _SC_JOURS = { lun: 'lundi', mar: 'mardi', mer: 'mercredi', jeu: 'jeudi', ven: 'vendredi', sam: 'samedi' };
const _SC_STATUT = { en_cours: 'en cours', a_venir: 'pas encore commencée', terminee: 'terminée' };

function _scE(s) { return escapeHtml(String(s == null ? '' : s)); }
function _scAnnee() { return (typeof ANNEE_ACTIVE !== 'undefined' && ANNEE_ACTIVE) || ''; }
function _scClasse() { const s = document.getElementById('classe-sel'); return s ? s.value : ''; }
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
  if (s) {
    const sel = document.getElementById('classe-sel');
    if (sel && [...sel.options].some(o => o.value === s.classe_id)) {
      sel.value = s.classe_id;
      if (typeof currentCid !== 'undefined') currentCid = s.classe_id;
    }
    SC.creneau = s.creneau;
    await scCharger();
  } else {
    await scClasseChangee();
  }
}

// Classe ou jour changés : séance en cours / prochaine / dernière de la classe
// ce jour-là (aujourd'hui), ou la première du jour choisi.
async function scClasseChangee() {
  SC.creneau = null;
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
  const ch = document.getElementById('sc-choix'); if (ch) ch.innerHTML = '';
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
}

function _scRendre() {
  const d = SC.donnees;
  if (!d) return;
  const s = d.seance;
  // Libellé du sélecteur sans l'établissement entre parenthèses.
  const nomClasse = ((document.getElementById('classe-sel').selectedOptions[0] || {}).text || '')
    .replace(/\s*\(.*\)\s*$/, '');
  document.getElementById('sc-titre').innerHTML = `
    <strong>${_scE(nomClasse)}</strong> — ${_SC_JOURS[s.jour] || s.jour} ${_scDateFr(s.date)},
    ${_scE(s.creneau)} (${_scE(s.heure_debut)}–${_scE(s.heure_fin)})
    <span class="sc-statut sc-statut-${s.statut}">${_SC_STATUT[s.statut] || ''}</span>`;
  const ch = document.getElementById('sc-choix');
  if (ch) {
    ch.innerHTML = d.seances_du_jour.length > 1
      ? `<label>Séance <select onchange="scChoisirSeance(this.value)">${d.seances_du_jour.map(x =>
          `<option value="${_scE(x.creneau)}"${x.creneau === s.creneau ? ' selected' : ''}>${_scE(x.creneau)} (${_scE(x.heure_debut)})</option>`).join('')}</select></label>`
      : '';
  }
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
    </div>`;
  _scRendreAbsents();
}

function _scTexteMiseEnRoute(m) {
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
}
