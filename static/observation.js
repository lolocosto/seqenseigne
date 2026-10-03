// ============================================================================
// static/observation.js — v0.46.0
// Suivi › Observation : même séance que le Début de séance (état SC de
// static/seance.js, en-tête commun). Plan de classe de la semaine (sinon
// liste alphabétique) ; un clic sur un élève présent ouvre à côté la liste de
// SES observables (liste effective, exceptions comprises) ; un clic sur un
// libellé enregistre une occurrence horodatée ; compteurs + / − sur le plan ;
// « Annuler la dernière » et suppression d'une occurrence. Absents non
// sélectionnables.
// Backend : /api/observation (services/observation.py).
// ============================================================================

const OV = { donnees: null, eleve: null, liste: null, occupe: false };

function _ovE(s) { return escapeHtml(String(s == null ? '' : s)); }
function _ovSeance() {
  const s = SC.donnees.seance;
  return { annee: _scAnnee(), classe_id: _scClasse(), date: s.date, creneau: s.creneau };
}
function _ovToast(m) { if (typeof showToast === 'function') showToast(m, true); else alert(m); }

async function ovInit() {
  if (typeof SC === 'undefined') return;
  if (!SC.donnees) { await scInit(); return; }   // scCharger appelle ovCharger
  await ovCharger();
}

async function ovCharger() {
  const z = document.getElementById('ov-corps');
  if (!z || !SC.donnees) return;
  const q = _ovSeance();
  try {
    OV.donnees = await _scApi(`/api/observation?classe_id=${encodeURIComponent(q.classe_id)}`
      + `&date=${q.date}&creneau=${encodeURIComponent(q.creneau)}`);
  } catch (e) { z.innerHTML = `<p class="sc-vide">${_ovE(e.message)}</p>`; return; }
  if (OV.eleve && (!SC.donnees.eleves.some(e => e.id === OV.eleve) || SC.donnees.absents.includes(OV.eleve))) {
    OV.eleve = null;
  }
  await _ovChargerListe();
  ovRendre();
}

async function _ovChargerListe() {
  OV.liste = null;
  if (!OV.eleve) return;
  const q = _ovSeance();
  try {
    OV.liste = await _scApi(`/api/observation/liste?classe_id=${encodeURIComponent(q.classe_id)}`
      + `&eleve_id=${OV.eleve}&date=${q.date}`);
  } catch (e) { OV.liste = { valoriser: [], sanctionner: [] }; }
}

function ovRendre() {
  const z = document.getElementById('ov-corps');
  if (!z || !SC.donnees || !OV.donnees) return;
  z.innerHTML = `
    <div class="ov-corps">
      <div class="ov-plan" id="ov-plan"></div>
      <aside class="ov-cote" id="ov-cote"></aside>
    </div>`;
  _ovRendrePlan();
  _ovRendreCote();
}

function _ovCompteur(eid) {
  const c = (OV.donnees.compteurs || {})[eid];
  return c || { valoriser: 0, sanctionner: 0 };
}

function _ovRendrePlan() {
  const d = SC.donnees, zone = document.getElementById('ov-plan');
  const abs = new Set(d.absents);
  if (!d.plan) {
    zone.innerHTML = `<div class="sc-liste-titre">Classe (ordre alphabétique) — cliquer un élève</div>
      <div class="sc-liste sc-liste-large">${d.eleves.map(e => {
        const c = _ovCompteur(e.id);
        const badges = (c.valoriser ? ` <span class="ov-plus">+${c.valoriser}</span>` : '')
          + (c.sanctionner ? ` <span class="ov-moins">−${c.sanctionner}</span>` : '');
        return abs.has(e.id)
          ? `<span class="sc-eleve sc-absent ov-inactif" title="Absent">${_ovE(e.etiquette)}</span>`
          : `<button class="sc-eleve${OV.eleve === e.id ? ' ov-sel' : ''}" onclick="ovChoisirEleve('${e.id}')">${_ovE(e.etiquette)}${badges}</button>`;
      }).join('')}</div>`;
    return;
  }
  const S = window.SallesPur, p = d.plan;
  const noms = {}; d.eleves.forEach(e => { noms[e.id] = e; });
  const parNum = {}; p.placements.forEach(x => { parNum[x.numero] = x; });
  const c = S.cadre(p.places, 40);
  const largTab = Math.min(300, c.w * 0.5), xTab = c.x + (c.w - largTab) / 2;
  const coupe = t => (t.length > 10 ? t.slice(0, 8) + '…' : t);
  let compteurs = '';
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
    const [l1, l2] = i > 0 ? [lib.slice(0, i), lib.slice(i + 1)] : [lib, ''];
    const absent = abs.has(e.id);
    const cpt = _ovCompteur(e.id);
    // Compteurs dans le coin bas de la place, dessinés après toutes les places.
    if (!absent && (cpt.valoriser || cpt.sanctionner)) {
      const [dx, dy] = S.tournerVecteur(0, S.H / 2 - 5, pl.angle || 0);
      const txt = (cpt.valoriser ? `<tspan class="ov-plus">+${cpt.valoriser}</tspan>` : '')
        + (cpt.valoriser && cpt.sanctionner ? ' ' : '')
        + (cpt.sanctionner ? `<tspan class="ov-moins">−${cpt.sanctionner}</tspan>` : '');
      compteurs += `<text class="ov-cpt" x="${pl.x + dx}" y="${pl.y + dy}">${txt}</text>`;
    }
    const cls = absent ? 'sc-place ov-absent' : `sc-place sc-occupee${OV.eleve === e.id ? ' ov-sel' : ''}`;
    const clic = absent ? '' : ` onclick="ovChoisirEleve('${e.id}')"`;
    return `<g class="${cls}"${clic}><title>${_ovE(e.prenom)} ${_ovE(e.nom)}${absent ? ' (absent)' : ''}</title>${rect}
      <text x="${pl.x}" y="${pl.y - 10}">${_ovE(coupe(l1))}</text>
      <text x="${pl.x}" y="${pl.y + 2}">${_ovE(coupe(l2))}</text></g>`;
  }).join('');
  const places_ids = new Set(p.placements.map(x => x.eleve_id));
  const non = d.eleves.filter(e => !places_ids.has(e.id));
  zone.innerHTML = `<div class="sc-liste-titre">Plan de classe — salle ${_ovE(p.salle.nom)} — cliquer un élève</div>
    <svg id="ov-svg" viewBox="${c.x} ${c.y - 30} ${c.w} ${c.h + 30}" preserveAspectRatio="xMidYMin meet">
      <g class="sal-tableau"><rect x="${xTab}" y="${c.y - 24}" width="${largTab}" height="8" rx="2"></rect>
      <text x="${xTab + largTab / 2}" y="${c.y - 4}">Tableau</text></g>${places}
      <g class="ov-cpts">${compteurs}</g></svg>
    ${non.length ? `<div class="sc-liste-titre">Non placés</div><div class="sc-liste">${non.map(e =>
      abs.has(e.id) ? `<span class="sc-eleve sc-absent ov-inactif">${_ovE(e.etiquette)}</span>`
        : `<button class="sc-eleve${OV.eleve === e.id ? ' ov-sel' : ''}" onclick="ovChoisirEleve('${e.id}')">${_ovE(e.etiquette)}</button>`).join('')}</div>` : ''}`;
}

function _ovRendreCote() {
  const z = document.getElementById('ov-cote');
  const d = SC.donnees;
  if (!OV.eleve) {
    const n = Object.values(OV.donnees.compteurs || {}).reduce(
      (a, c) => [a[0] + c.valoriser, a[1] + c.sanctionner], [0, 0]);
    z.innerHTML = `<p class="sc-aide">Cliquez un élève présent pour noter une observation.</p>
      <div class="ov-total">Séance : <span class="ov-plus">+${n[0]}</span> <span class="ov-moins">−${n[1]}</span></div>`;
    return;
  }
  const e = d.eleves.find(x => x.id === OV.eleve) || {};
  const occ = (OV.donnees.occurrences || []).filter(o => o.eleve_id === OV.eleve);
  const l = OV.liste || { valoriser: [], sanctionner: [] };
  const bouton = (o, sec) => `<button class="ov-obs ov-obs-${sec}" onclick="ovNoter('${o.id}')">${_ovE(o.libelle)}</button>`;
  z.innerHTML = `
    <div class="ov-eleve-nom">${_ovE(e.prenom)} ${_ovE(e.nom)}
      <button class="btn-lien" onclick="ovChoisirEleve(null)" title="Fermer">✕</button></div>
    <div class="ov-sec-titre ov-plus">Valoriser</div>
    <div class="ov-obs-liste">${l.valoriser.length ? l.valoriser.map(o => bouton(o, 'valoriser')).join('')
      : '<span class="sc-aide">—</span>'}</div>
    <div class="ov-sec-titre ov-moins">Sanctionner</div>
    <div class="ov-obs-liste">${l.sanctionner.length ? l.sanctionner.map(o => bouton(o, 'sanctionner')).join('')
      : '<span class="sc-aide">—</span>'}</div>
    <div class="ov-sec-titre">Pendant cette séance</div>
    ${occ.length ? `<ul class="ov-occ">${occ.slice().reverse().map(o => `
      <li><span class="ov-heure">${_ovE((o.horodatage || '').slice(11, 16))}</span>
        <span class="${o.section === 'valoriser' ? 'ov-plus' : 'ov-moins'}">${o.section === 'valoriser' ? '+' : '−'}</span>
        ${_ovE(o.libelle || '?')}
        <button class="btn-lien ov-suppr" onclick="ovSupprimer('${o.id}')" title="Supprimer">✕</button></li>`).join('')}</ul>
      <button class="btn-sm" onclick="ovAnnulerDerniere()">Annuler la dernière</button>`
      : '<p class="sc-aide">Rien de noté pour cet élève.</p>'}`;
}

async function ovChoisirEleve(eid) {
  OV.eleve = eid;
  await _ovChargerListe();
  ovRendre();
}

async function _ovAction(url, opts) {
  if (OV.occupe) return;
  OV.occupe = true;
  try { OV.donnees = await _scApi(url, opts); }
  catch (e) { _ovToast(e.message); }
  OV.occupe = false;
  ovRendre();
}

function ovNoter(observableId) {
  return _ovAction('/api/observation', { method: 'POST', body: JSON.stringify({
    ..._ovSeance(), eleve_id: OV.eleve, observable_id: observableId }) });
}

function ovSupprimer(id) {
  return _ovAction(`/api/observation/${id}`, { method: 'DELETE' });
}

function ovAnnulerDerniere() {
  return _ovAction('/api/observation/annuler-derniere', { method: 'POST', body: JSON.stringify({
    ..._ovSeance(), eleve_id: OV.eleve }) });
}
