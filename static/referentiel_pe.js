// ============================================================================
// static/referentiel_pe.js — v0.48.2
// Référentiels PRINCIPAUX externes (Conception de référentiel › Référentiels
// externes › Principaux) : même structure qu'un référentiel interne figé.
// Séquences → parties (nb de séances) → objectifs (nb de séances, critères
// F/A/E) ; fichiers (tous formats) par séquence ou par partie. Une séquence
// commencée (créneau démarré dans une progression) n'accepte plus que la
// correction des libellés et l'ajout de fichiers.
// Backend : /api/referentiels-principaux-externes.
// ============================================================================

const RPE = { liste: [], ouverts: new Set() };
const _RPE_API = '/api/referentiels-principaux-externes';

function _rpeE(s) { return escapeHtml(String(s == null ? '' : s)); }
function _rpeNiveau() { return (typeof _rxtNiveau === 'function') ? _rxtNiveau() : 'N09'; }
function _rpeAnnee() { return (typeof _rxtAnnee === 'function') ? _rxtAnnee() : ''; }
function _rpeStatus(msg, err) {
  const s = document.getElementById('rpe-status');
  if (!s) return;
  s.style.color = err ? '#c33' : '#4a7';
  s.textContent = msg || '';
  if (msg && !err) setTimeout(() => { if (s.textContent === msg) s.textContent = ''; }, 2500);
}

async function _rpeApi(url, opts) {
  const r = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...(opts || {}) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || ('Erreur ' + r.status));
  return d;
}

async function rpeInit() { await rpeCharger(); }

async function rpeCharger() {
  try {
    const l = (await _rpeApi(`${_RPE_API}?niveau=${encodeURIComponent(_rpeNiveau())}`)).referentiels;
    RPE.liste = [];
    for (const r of l) RPE.liste.push(await _rpeApi(`${_RPE_API}/${r.id}`));
  } catch (e) { RPE.liste = []; _rpeStatus(e.message, true); }
  rpeRendre();
}

async function _rpeAction(url, opts, msg) {
  try { await _rpeApi(url, opts); if (msg) _rpeStatus(msg); }
  catch (e) { _rpeStatus(e.message, true); }
  await rpeCharger();
}

function rpeCreer() {
  const d = document.getElementById('rpe-desc');
  return _rpeAction(_RPE_API, { method: 'POST', body: JSON.stringify({
    niveau: _rpeNiveau(), annee: _rpeAnnee(), description: d ? d.value : '' }) }, 'Référentiel créé.')
    .then(() => { if (d) d.value = ''; });
}

function rpeRendre() {
  const z = document.getElementById('rpe-liste');
  if (!z) return;
  if (!RPE.liste.length) {
    z.innerHTML = '<p class="rpe-vide">Aucun référentiel principal externe pour ce niveau.</p>';
    return;
  }
  z.innerHTML = RPE.liste.map(_rpeRef).join('');
}

function _rpeRef(r) {
  const ouvert = RPE.ouverts.has(r.id);
  const etat = r.utilise ? '<span class="rpe-badge rpe-utilise">utilisé</span>'
    : '<span class="rpe-badge">en construction</span>';
  return `<div class="card rpe-ref">
    <div class="rpe-ref-tete">
      <button class="btn-lien" onclick="rpeBasculer('${r.id}')">${ouvert ? '▾' : '▸'}</button>
      <strong>${_rpeE(r.nom)}</strong> ${etat}
      <input class="rpe-desc-ref" value="${_rpeE(r.description)}" placeholder="description"
        onchange="rpeModifierDesc('${r.id}', this.value)">
      <span class="rpe-espace"></span>
      ${r.utilise ? '' : `<button class="btn-sm rpe-danger" onclick="rpeSupprimer('${r.id}')">Supprimer</button>`}
    </div>
    ${ouvert ? `<div class="rpe-corps">
      ${(r.sequences || []).map(s => _rpeSeq(r, s)).join('') || '<p class="rpe-vide">Aucune séquence.</p>'}
      <div class="rpe-ajout"><input id="rpe-seq-${r.id}" placeholder="Nom de la nouvelle séquence"
        onkeydown="if(event.key==='Enter') rpeAjouterSeq('${r.id}')">
        <button class="btn-sm" onclick="rpeAjouterSeq('${r.id}')">+ séquence</button></div>
    </div>` : ''}
  </div>`;
}

function _rpeFichiers(r, seqCode, partie, fichiers) {
  return `<div class="rpe-fichiers">
    ${fichiers.map(f => `<span class="rpe-fichier">
      <a href="${_RPE_API}/fichiers/${f.id}" target="_blank" rel="noopener"
         title="${f.affichable ? 'Afficher' : 'Télécharger'}">${f.affichable ? '📄' : '⬇'} ${_rpeE(f.nom_fichier)}</a>
      <button class="btn-lien rpe-x" onclick="rpeSupprimerFichier('${f.id}')" title="Supprimer">✕</button></span>`).join('')}
    <label class="rpe-import">+ fichier(s)<input type="file" multiple style="display:none"
      onchange="rpeImporter('${r.id}', '${seqCode}', ${partie}, this)"></label>
  </div>`;
}

function _rpeSeq(r, s) {
  const verrou = s.commencee;
  const ctl = (html) => verrou ? '' : html;
  return `<div class="rpe-seq${verrou ? ' rpe-commencee' : ''}">
    <div class="rpe-seq-tete">
      <span class="rpe-code">${_rpeE(s.code)}</span>
      <input class="rpe-nom" value="${_rpeE(s.nom)}" onchange="rpeModifierSeq('${r.id}', '${s.code}', this.value)">
      ${verrou ? '<span class="rpe-badge rpe-verrou" title="Un créneau de progression a démarré">commencée</span>' : ''}
      ${ctl(`<button class="btn-sm" onclick="rpeDeplacerSeq('${r.id}', '${s.code}', -1)">↑</button>
        <button class="btn-sm" onclick="rpeDeplacerSeq('${r.id}', '${s.code}', 1)">↓</button>
        <button class="btn-lien rpe-x" onclick="rpeSupprimerSeq('${r.id}', '${s.code}')">supprimer</button>`)}
    </div>
    <div class="rpe-sous">Fichiers de la séquence : ${_rpeFichiers(r, s.code, 0, s.fichiers || [])}</div>
    ${(s.parties || []).map(p => `
      <div class="rpe-partie">
        <div class="rpe-partie-tete">Partie ${p.numero} —
          <input type="number" min="0" step="0.5" value="${p.nb_seances_R_AE}" class="rpe-nb" ${verrou ? 'disabled' : ''}
            onchange="rpeModifierPartie('${r.id}', '${s.code}', ${p.numero}, this.value)"> séance(s)
          ${ctl(`<button class="btn-sm" onclick="rpeDeplacerPartie('${r.id}', '${s.code}', ${p.numero}, -1)">↑</button>
            <button class="btn-sm" onclick="rpeDeplacerPartie('${r.id}', '${s.code}', ${p.numero}, 1)">↓</button>
            <button class="btn-lien rpe-x" onclick="rpeSupprimerPartie('${r.id}', '${s.code}', ${p.numero})">supprimer</button>`)}
        </div>
        <table class="rpe-obj"><tbody>${(p.objectifs || []).map(o => `<tr>
          <td class="rpe-code">${_rpeE(o.code)}</td>
          <td><input class="rpe-obj-nom" value="${_rpeE(o.nom)}" onchange="rpeModifierObj('${r.id}', '${s.code}', '${o.code}', {nom: this.value})"></td>
          <td><input type="number" min="0" step="0.5" value="${o.nb_seances}" class="rpe-nb" ${verrou ? 'disabled' : ''}
            title="nombre de séances" onchange="rpeModifierObj('${r.id}', '${s.code}', '${o.code}', {nb_seances: this.value})"></td>
          ${['f', 'a', 'e'].map(k => `<td><input class="rpe-crit" value="${_rpeE(o['critere_' + k])}" placeholder="critère ${k.toUpperCase()}"
            onchange="rpeModifierObj('${r.id}', '${s.code}', '${o.code}', {critere_${k}: this.value})"></td>`).join('')}
          <td>${ctl(`<button class="btn-sm" onclick="rpeDeplacerObj('${r.id}', '${s.code}', '${o.code}', -1)">↑</button>
            <button class="btn-sm" onclick="rpeDeplacerObj('${r.id}', '${s.code}', '${o.code}', 1)">↓</button>
            <button class="btn-lien rpe-x" onclick="rpeSupprimerObj('${r.id}', '${s.code}', '${o.code}')">✕</button>`)}</td>
        </tr>`).join('')}</tbody></table>
        ${ctl(`<div class="rpe-ajout"><input id="rpe-obj-${r.id}-${s.code}-${p.numero}" placeholder="Nouvel objectif">
          <button class="btn-sm" onclick="rpeAjouterObj('${r.id}', '${s.code}', ${p.numero})">+ objectif</button></div>`)}
        <div class="rpe-sous">Fichiers de la partie : ${_rpeFichiers(r, s.code, p.numero, p.fichiers || [])}</div>
      </div>`).join('')}
    ${ctl(`<div class="rpe-ajout"><input type="number" min="0" step="0.5" id="rpe-part-${r.id}-${s.code}" class="rpe-nb" value="4">
      séance(s) <button class="btn-sm" onclick="rpeAjouterPartie('${r.id}', '${s.code}')">+ partie</button></div>`)}
  </div>`;
}

function rpeBasculer(id) { RPE.ouverts.has(id) ? RPE.ouverts.delete(id) : RPE.ouverts.add(id); rpeRendre(); }
const _rpeJ = (o) => ({ method: o.m || 'POST', body: JSON.stringify(o.b || {}) });

function rpeModifierDesc(id, v) { return _rpeAction(`${_RPE_API}/${id}`, _rpeJ({ m: 'PUT', b: { description: v } })); }
function rpeSupprimer(id) {
  if (!confirm('Supprimer ce référentiel et tous ses fichiers ?')) return;
  return _rpeAction(`${_RPE_API}/${id}`, { method: 'DELETE' }, 'Référentiel supprimé.');
}
function rpeAjouterSeq(id) {
  const i = document.getElementById('rpe-seq-' + id);
  if (!i || !i.value.trim()) return;
  RPE.ouverts.add(id);
  return _rpeAction(`${_RPE_API}/${id}/sequences`, _rpeJ({ b: { nom: i.value } }));
}
function rpeModifierSeq(id, c, nom) { return _rpeAction(`${_RPE_API}/${id}/sequences/${c}`, _rpeJ({ m: 'PUT', b: { nom } })); }
function rpeDeplacerSeq(id, c, sens) { return _rpeAction(`${_RPE_API}/${id}/sequences/${c}/deplacer`, _rpeJ({ b: { sens } })); }
function rpeSupprimerSeq(id, c) {
  if (!confirm(`Supprimer la séquence ${c} (parties, objectifs, fichiers) ?`)) return;
  return _rpeAction(`${_RPE_API}/${id}/sequences/${c}`, { method: 'DELETE' });
}
function rpeAjouterPartie(id, c) {
  const n = document.getElementById(`rpe-part-${id}-${c}`);
  return _rpeAction(`${_RPE_API}/${id}/sequences/${c}/parties`, _rpeJ({ b: { nb_seances: n ? n.value : 0 } }));
}
function rpeModifierPartie(id, c, num, v) { return _rpeAction(`${_RPE_API}/${id}/sequences/${c}/parties/${num}`, _rpeJ({ m: 'PUT', b: { nb_seances: v } })); }
function rpeDeplacerPartie(id, c, num, sens) { return _rpeAction(`${_RPE_API}/${id}/sequences/${c}/parties/${num}/deplacer`, _rpeJ({ b: { sens } })); }
function rpeSupprimerPartie(id, c, num) {
  if (!confirm(`Supprimer la partie ${num} (objectifs, fichiers) ?`)) return;
  return _rpeAction(`${_RPE_API}/${id}/sequences/${c}/parties/${num}`, { method: 'DELETE' });
}
function rpeAjouterObj(id, c, num) {
  const i = document.getElementById(`rpe-obj-${id}-${c}-${num}`);
  if (!i || !i.value.trim()) return;
  return _rpeAction(`${_RPE_API}/${id}/sequences/${c}/parties/${num}/objectifs`, _rpeJ({ b: { nom: i.value } }));
}
function rpeModifierObj(id, c, o, champs) { return _rpeAction(`${_RPE_API}/${id}/sequences/${c}/objectifs/${o}`, _rpeJ({ m: 'PUT', b: champs })); }
function rpeDeplacerObj(id, c, o, sens) { return _rpeAction(`${_RPE_API}/${id}/sequences/${c}/objectifs/${o}/deplacer`, _rpeJ({ b: { sens } })); }
function rpeSupprimerObj(id, c, o) { return _rpeAction(`${_RPE_API}/${id}/sequences/${c}/objectifs/${o}`, { method: 'DELETE' }); }
function rpeSupprimerFichier(fid) {
  if (!confirm('Supprimer ce fichier ?')) return;
  return _rpeAction(`${_RPE_API}/fichiers/${fid}`, { method: 'DELETE' });
}

async function rpeImporter(id, c, partie, input) {
  const fichiers = [...(input.files || [])];
  let ok = 0, ko = 0;
  for (const f of fichiers) {
    const fd = new FormData();
    fd.append('fichier', f);
    fd.append('partie', String(partie));
    try {
      const r = await fetch(`${_RPE_API}/${id}/sequences/${c}/fichiers`, { method: 'POST', body: fd });
      r.ok ? ok++ : ko++;
    } catch (e) { ko++; }
  }
  _rpeStatus(ko ? `${ok} ajouté(s), ${ko} en échec.` : `${ok} fichier(s) ajouté(s).`, !!ko);
  await rpeCharger();
}
