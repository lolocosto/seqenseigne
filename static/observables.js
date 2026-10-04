// ============================================================================
// static/observables.js — v0.45.0
// Paramétrage › Observables : comportements à valoriser / sanctionner, par
// niveau (sélecteur Niveau de la barre), communs ou individuels, période
// facultative, exceptions par élève (masquer / attribuer) avec période et
// commentaire, copie depuis un autre niveau, aperçu de la liste d'un élève.
// Backend : /api/observables (services/observables.py).
// ============================================================================

const OBS = { niveau: '', liste: [], eleves: [], avecExc: [], sel: null, excs: [] };
const _OBS_SECTIONS = { valoriser: 'Valoriser', sanctionner: 'Sanctionner' };
const _OBS_NIVEAUX = { N09: '6e', N10: '5e', N11: '4e', N12: '3e' };

function _obsE(s) { return escapeHtml(String(s == null ? '' : s)); }
function _obsDate(iso) { if (!iso) return ''; const [a, m, j] = iso.split('-'); return `${j}/${m}/${a}`; }
function _obsNiveau() { const s = document.getElementById('prog-sel-niveau'); return s ? s.value : ''; }
function _obsAnnee() { return (typeof ANNEE_ACTIVE !== 'undefined' && ANNEE_ACTIVE) || ''; }
function _obsToast(m, err) { if (typeof showToast === 'function') showToast(m, !!err); else if (err) alert(m); }

async function _obsApi(url, opts) {
  const r = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...(opts || {}) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || ('Erreur ' + r.status));
  return d;
}

async function obsInit() {
  if (OBS.niveau !== _obsNiveau()) OBS.sel = null;
  OBS.niveau = _obsNiveau();
  await obsCharger();
}

async function obsCharger() {
  try {
    const r = await _obsApi(`/api/observables?niveau=${encodeURIComponent(OBS.niveau)}`
      + `&annee=${encodeURIComponent(_obsAnnee())}`);
    OBS.liste = r.observables; OBS.eleves = r.eleves; OBS.avecExc = r.eleves_avec_exceptions;
  } catch (e) { _obsToast(e.message, true); return; }
  if (OBS.sel && !OBS.liste.some(o => o.id === OBS.sel)) OBS.sel = null;
  if (OBS.sel) {
    try { OBS.excs = (await _obsApi(`/api/observables/${OBS.sel}/exceptions`)).exceptions; }
    catch (e) { OBS.excs = []; }
  }
  _obsRendre();
}

function _obsRendre() {
  const nv = document.getElementById('obs-niveau');
  if (nv) nv.textContent = '— ' + (_OBS_NIVEAUX[OBS.niveau] || OBS.niveau);
  const cp = document.getElementById('obs-copier');
  if (cp) {
    const autres = Object.keys(_OBS_NIVEAUX).filter(n => n !== OBS.niveau);
    cp.innerHTML = `<label>Copier depuis <select id="obs-copier-src">${autres.map(n =>
      `<option value="${n}">${_OBS_NIVEAUX[n]}</option>`).join('')}</select></label>
      <button class="btn-sm" onclick="obsCopier()">Copier</button>`;
  }
  ['valoriser', 'sanctionner'].forEach(sec => {
    const col = document.getElementById('obs-col-' + sec);
    if (!col) return;
    const actifs = OBS.liste.filter(o => o.section === sec && o.actif);
    const inactifs = OBS.liste.filter(o => o.section === sec && !o.actif);
    const ligne = o => {
      const tags = [];
      if (o.portee === 'individuel') tags.push('<span class="obs-tag obs-tag-ind">individuel</span>');
      if (o.du || o.au) tags.push(`<span class="obs-tag">${o.du ? 'du ' + _obsDate(o.du) + ' ' : ''}${o.au ? "jusqu'au " + _obsDate(o.au) : ''}</span>`);
      if (o.nb_exceptions) tags.push(`<span class="obs-tag">${o.portee === 'commun' ? 'masqué pour' : 'attribué à'} ${o.nb_exceptions} élève${o.nb_exceptions > 1 ? 's' : ''}</span>`);
      return `<li class="obs-item${OBS.sel === o.id ? ' obs-sel' : ''}" onclick="obsChoisir('${o.id}')">
        <span class="obs-lib">${_obsE(o.libelle)}</span>${tags.join('')}</li>`;
    };
    col.innerHTML = `
      <div class="obs-col-titre obs-col-${sec}">${_OBS_SECTIONS[sec]}</div>
      ${actifs.length ? `<ul class="obs-liste">${actifs.map(ligne).join('')}</ul>`
                      : '<p class="obs-vide">Aucun observable.</p>'}
      <div class="obs-ajout">
        <input id="obs-new-${sec}" placeholder="Nouvel observable"
               onkeydown="if(event.key==='Enter') obsAjouter('${sec}')">
        <button class="btn-sm" onclick="obsAjouter('${sec}')">Ajouter</button>
      </div>
      ${inactifs.length ? `<details class="obs-desactives"><summary>Désactivés (${inactifs.length})</summary>
        <ul class="obs-liste">${inactifs.map(ligne).join('')}</ul></details>` : ''}`;
  });
  _obsRendreDetail();
  _obsRendreApercu();
  obsActivitesCharger();     // v0.47.1
}

function _obsRendreDetail() {
  const z = document.getElementById('obs-detail');
  if (!z) return;
  const o = OBS.liste.find(x => x.id === OBS.sel);
  if (!o) { z.innerHTML = ''; return; }
  const commun = o.portee === 'commun';
  const titreEleves = commun ? 'Masqué pour' : 'Attribué à';
  const optsEleves = OBS.eleves.map(e =>
    `<option value="${e.id}">${_obsE(e.nom)} ${_obsE(e.prenom)} (${_obsE(e.classe)})</option>`).join('');
  z.innerHTML = `
    <div class="obs-detail">
      <div class="obs-detail-ligne">
        <label>Libellé <input id="obs-d-lib" value="${_obsE(o.libelle)}" onchange="obsModifier({libelle: this.value})"></label>
        <span class="obs-section-tag obs-col-${o.section}">${_OBS_SECTIONS[o.section]}</span>
        ${o.actif ? `<button class="btn-sm" onclick="obsDeplacer(-1)" title="Monter">↑</button>
          <button class="btn-sm" onclick="obsDeplacer(1)" title="Descendre">↓</button>` : ''}
        <span class="obs-espace"></span>
        <button class="btn-sm" onclick="obsModifier({actif: ${!o.actif}})">${o.actif ? 'Désactiver' : 'Réactiver'}</button>
        <button class="btn-sm" onclick="obsChoisir(null)">Fermer</button>
      </div>
      <div class="obs-detail-ligne">
        <span>Portée :</span>
        <label><input type="radio" name="obs-portee" ${commun ? 'checked' : ''} onchange="obsModifier({portee: 'commun'})"> commun (tous les élèves du niveau)</label>
        <label><input type="radio" name="obs-portee" ${!commun ? 'checked' : ''} onchange="obsModifier({portee: 'individuel'})"> individuel (élèves désignés)</label>
      </div>
      <div class="obs-detail-ligne">
        <span>Période :</span>
        <label>du <input type="date" value="${o.du}" onchange="obsModifier({du: this.value})"></label>
        <label>au <input type="date" value="${o.au}" onchange="obsModifier({au: this.value})"></label>
        <span class="obs-aide-inline">(vide = sans limite)</span>
      </div>
      <div class="obs-eleves">
        <div class="obs-col-titre">${titreEleves}</div>
        ${OBS.excs.length ? `<table class="obs-exc"><tbody>${OBS.excs.map(x => `
          <tr>
            <td>${_obsE(x.nom || '?')} ${_obsE(x.prenom || '')}</td>
            <td>du <input type="date" value="${x.du}" onchange="obsModifierExc('${x.id}', {du: this.value})"></td>
            <td>au <input type="date" value="${x.au}" onchange="obsModifierExc('${x.id}', {au: this.value})"></td>
            <td><input class="obs-comm" value="${_obsE(x.commentaire)}" placeholder="Commentaire (facultatif)"
                 onchange="obsModifierExc('${x.id}', {commentaire: this.value})"></td>
            <td><button class="btn-lien obs-suppr" onclick="obsSupprimerExc('${x.id}')">retirer</button></td>
          </tr>`).join('')}</tbody></table>`
          : `<p class="obs-vide">${commun ? 'Aucun élève : l\'observable vaut pour toute la classe.' : 'Aucun élève : cet observable ne sera proposé à personne.'}</p>`}
        <div class="obs-ajout-exc">
          <select id="obs-exc-eleve">${optsEleves || '<option value="">Aucun élève dans les classes de ce niveau</option>'}</select>
          <label>du <input type="date" id="obs-exc-du"></label>
          <label>au <input type="date" id="obs-exc-au"></label>
          <input id="obs-exc-comm" class="obs-comm" placeholder="Commentaire (facultatif)">
          <button class="btn-sm" onclick="obsAjouterExc()">+ élève</button>
        </div>
      </div>
    </div>`;
}

function _obsRendreApercu() {
  const z = document.getElementById('obs-apercu');
  if (!z) return;
  if (!OBS.avecExc.length) { z.innerHTML = ''; return; }
  z.innerHTML = `
    <div class="obs-col-titre">Aperçu de la liste d'un élève aujourd'hui</div>
    <select id="obs-apercu-eleve" onchange="obsApercu(this.value)">
      <option value="">— élève ayant des exceptions —</option>
      ${OBS.avecExc.map(e => `<option value="${e.id}">${_obsE(e.nom)} ${_obsE(e.prenom)}</option>`).join('')}
    </select>
    <div id="obs-apercu-res"></div>`;
}

async function obsApercu(eid) {
  const res = document.getElementById('obs-apercu-res');
  if (!res) return;
  if (!eid) { res.innerHTML = ''; return; }
  try {
    const l = await _obsApi(`/api/observables/effectifs?niveau=${encodeURIComponent(OBS.niveau)}&eleve_id=${eid}`);
    res.innerHTML = '<div class="obs-colonnes">' + ['valoriser', 'sanctionner'].map(sec =>
      `<div class="obs-col"><div class="obs-col-titre obs-col-${sec}">${_OBS_SECTIONS[sec]}</div>
        ${l[sec].length ? `<ul class="obs-liste">${l[sec].map(o => `<li class="obs-item obs-item-ro">${_obsE(o.libelle)}${o.portee === 'individuel' ? ' <span class="obs-tag obs-tag-ind">individuel</span>' : ''}</li>`).join('')}</ul>`
                         : '<p class="obs-vide">—</p>'}</div>`).join('') + '</div>';
  } catch (e) { res.textContent = e.message; }
}

async function obsChoisir(id) {
  OBS.sel = id;
  OBS.excs = [];
  await obsCharger();
}

async function _obsAction(url, opts) {
  try { await _obsApi(url, opts); }
  catch (e) { _obsToast(e.message, true); }
  await obsCharger();
}

function obsAjouter(section) {
  const inp = document.getElementById('obs-new-' + section);
  const libelle = (inp && inp.value || '').trim();
  if (!libelle) { inp && inp.focus(); return; }
  return _obsAction('/api/observables', { method: 'POST',
    body: JSON.stringify({ niveau: OBS.niveau, section, libelle }) });
}

function obsModifier(champs) {
  return _obsAction(`/api/observables/${OBS.sel}`, { method: 'PUT', body: JSON.stringify(champs) });
}

function obsDeplacer(sens) {
  return _obsAction(`/api/observables/${OBS.sel}/deplacer`, { method: 'POST', body: JSON.stringify({ sens }) });
}

function obsAjouterExc() {
  const eleve_id = document.getElementById('obs-exc-eleve').value;
  if (!eleve_id) return;
  return _obsAction(`/api/observables/${OBS.sel}/exceptions`, { method: 'POST', body: JSON.stringify({
    eleve_id, du: document.getElementById('obs-exc-du').value,
    au: document.getElementById('obs-exc-au').value,
    commentaire: document.getElementById('obs-exc-comm').value }) });
}

function obsModifierExc(id, champs) {
  return _obsAction(`/api/observables/exceptions/${id}`, { method: 'PUT', body: JSON.stringify(champs) });
}

function obsSupprimerExc(id) {
  return _obsAction(`/api/observables/exceptions/${id}`, { method: 'DELETE' });
}

async function obsCopier() {
  const src = document.getElementById('obs-copier-src').value;
  if (!confirm(`Copier les observables communs actifs de ${_OBS_NIVEAUX[src]} vers ${_OBS_NIVEAUX[OBS.niveau] || OBS.niveau} ?\n\n`
      + 'Les exceptions ne sont pas copiées ; un libellé déjà présent n\'est pas dupliqué.')) return;
  try {
    const r = await _obsApi('/api/observables/copier', { method: 'POST',
      body: JSON.stringify({ source: src, cible: OBS.niveau }) });
    _obsToast(`${r.copies} observable(s) copié(s).`);
  } catch (e) { _obsToast(e.message, true); }
  await obsCharger();
}


// ── v0.47.1 — Activités de séance (synthèse Pronote) ────────────────────────

async function obsActivitesCharger() {
  const z = document.getElementById('obs-activites');
  if (!z) return;
  let liste = [];
  try { liste = (await _obsApi('/api/activites-seance')).activites; } catch (e) {}
  z.innerHTML = `<ul class="obs-liste">${liste.map(a => `
      <li class="obs-item obs-item-ro${a.actif ? '' : ' obs-inactif'}">
        <input class="obs-act-lib" value="${_obsE(a.libelle)}" onchange="obsActiviteModifier('${a.id}', {libelle: this.value})">
        <button class="btn-sm" onclick="obsActiviteModifier('${a.id}', {actif: ${!a.actif}})">${a.actif ? 'Désactiver' : 'Réactiver'}</button>
      </li>`).join('')}</ul>
    <div class="obs-ajout"><input id="obs-act-new" placeholder="Nouvelle activité (ex. : travail de groupe)"
      onkeydown="if(event.key==='Enter') obsActiviteAjouter()">
      <button class="btn-sm" onclick="obsActiviteAjouter()">Ajouter</button></div>`;
}

async function obsActiviteAjouter() {
  const inp = document.getElementById('obs-act-new');
  const libelle = (inp && inp.value || '').trim();
  if (!libelle) return;
  try { await _obsApi('/api/activites-seance', { method: 'POST', body: JSON.stringify({ libelle }) }); }
  catch (e) { _obsToast(e.message, true); }
  await obsActivitesCharger();
}

async function obsActiviteModifier(id, champs) {
  try { await _obsApi(`/api/activites-seance/${id}`, { method: 'PUT', body: JSON.stringify(champs) }); }
  catch (e) { _obsToast(e.message, true); }
  await obsActivitesCharger();
}
