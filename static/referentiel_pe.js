// ============================================================================
// static/referentiel_pe.js — v0.48.2 (v0.48.3 : type ; v0.48.4 : liste/détail ;
// v0.48.5 : séance de distribution, retour, délai ; type des documents de MER)
// Référentiels PRINCIPAUX externes (Conception de référentiel › Référentiels
// externes › Principaux) : même structure qu'un référentiel interne figé.
// Séquences → parties (durée = somme des séances des objectifs) → objectifs (nb de séances, critères
// F/A/E) ; fichiers (tous formats) par séquence ou par partie. Une séquence
// commencée (créneau démarré dans une progression) n'accepte plus que la
// correction des libellés et l'ajout de fichiers.
// v0.51.4 : codes de séquence recalculés tant que le référentiel est en
// conception ; durée de partie calculée (somme des objectifs, lecture seule) ;
// déplacement d'un document vers un autre point d'attache.
// v0.51.5 : thèmes (bloc en tête, codes A, B… en conception) ; séquences
// regroupées par thème, déplacées à l'intérieur de leur thème.
// Backend : /api/referentiels-principaux-externes.
// ============================================================================

const RPE = { liste: [], ouverts: new Set(), types: [], criteres: new Set() };
const _RPE_API = '/api/referentiels-principaux-externes';

function _rpeE(s) { return escapeHtml(String(s == null ? '' : s)); }
function _rpeNiveau() {
  try {
    if (typeof ATL_SELECTIONS !== 'undefined' && ATL_SELECTIONS.niveau)
      return ATL_SELECTIONS.niveau.niveau || 'N09';
  } catch (e) {}
  return 'N09';
}
function _rpeAnnee() {
  return (typeof ANNEE_ACTIVE !== 'undefined' && ANNEE_ACTIVE)
    || (typeof anneeScolaireCourante === 'function' ? anneeScolaireCourante() : '');
}
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
  try { RPE.types = (await _rpeApi('/api/types-documents')).types || []; } catch (e) { RPE.types = []; }
  try {
    const l = (await _rpeApi(`${_RPE_API}?niveau=${encodeURIComponent(_rpeNiveau())}&type=tous`)).referentiels;
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
  // v0.48.4 — Liste à gauche / détail à droite.
  if (typeof rxaRendre === 'function') { rxaRendre(); return; }
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
      ${(r.alertes || []).length ? `<div class="rx-alertes" role="status">⚠ ${r.alertes.length} partie(s) sans objectif « capacité »
        (ce qu'on évalue à la fin) : ${r.alertes.map(a => _rpeE(a.split(' :')[0])).join(', ')}.</div>` : ''}
      <div class="rx-petit rpe-codes">${r.en_conception
        ? 'En conception : les codes de séquence suivent leur rang (recalculés au déplacement et à la suppression).'
        : 'Référentiel utilisé ou publié : les codes de séquence ne changent plus.'}</div>
      ${r.cree_depuis ? `<div class="rx-petit">Créé à partir de : ${_rpeE(r.cree_depuis)}</div>` : ''}
      ${(r.doublons || []).length ? `<div class="rx-alertes rpe-doublon" role="status">⚠ Contenu identique à
        ${r.doublons.map(d => _rpeE(d.nom)).join(', ')} (structure et documents). Un nouveau référentiel
        ne se justifie que si quelque chose change : pour reconduire, basez la progression sur le
        référentiel existant.</div>` : ''}
      ${_rpeThemes(r)}
      ${(r.alertes_themes || []).length ? `<div class="rx-alertes" role="status">⚠ ${r.alertes_themes.map(_rpeE).join(' ')}</div>` : ''}
      ${_rpeGroupes(r)}
      <div class="rx-annuels">
        <div class="rx-sous-titre">Documents annuels</div>
        <div class="rx-petit">Rattachés au référentiel (récapitulatifs annuels), pas à une séquence.</div>
        ${_rpeFichiers(r, '', 0, r.documents_annuels || [])}
      </div>
    </div>` : ''}
  </div>`;
}

// v0.48.3 — Un fichier par ligne, avec son type à côté.
function _rpeFichiers(r, seqCode, partie, fichiers) {
  const optionsType = (sel) => '<option value="">— type —</option>' + RPE.types.map(t =>
    `<option value="${t.id}"${t.id === sel ? ' selected' : ''}>${_rpeE(t.libelle)}</option>`).join('')
    + (sel && !RPE.types.some(t => t.id === sel) ? `<option value="${sel}" selected>(type désactivé)</option>` : '');
  return `<div class="rpe-fichiers">
    ${fichiers.map(f => `<div class="rpe-fichier-ligne">
      <a href="${_RPE_API}/fichiers/${f.id}" target="_blank" rel="noopener" class="rpe-fichier-nom"
         title="${f.affichable ? 'Afficher' : 'Télécharger'}">${f.affichable ? '📄' : '⬇'} ${_rpeE(f.nom_fichier)}</a>
      <select class="rpe-type" onchange="rpeTyperFichier('${f.id}', this.value)">${optionsType(f.type_id)}</select>
      ${partie ? _rpePlacement(f) : ''}
      ${_rpeDeplacerFichier(r, f)}
      <button class="btn-lien rpe-x" onclick="rpeSupprimerFichier('${f.id}')" title="Supprimer">✕</button></div>`).join('')}
    <div class="rx-ajout-doc"><label class="btn-sm rx-import">+ document(s)<input type="file" multiple style="display:none"
      onchange="rpeImporter('${r.id}', '${seqCode}', ${partie}, this)"></label></div>
  </div>`;
}

// v0.51.4 — Point d'attache d'un document : annuel, séquence ou partie.
function _rpeDeplacerFichier(r, f) {
  if (f.distribue) {
    return '<span class="rpe-badge" title="Marqué distribué dans le suivi de séance : ne se déplace plus">distribué</span>';
  }
  const ici = `${f.seq_code || ''}|${f.partie_numero || 0}`;
  const opt = (v, lib) => `<option value="${v}"${v === ici ? ' disabled' : ''}>${_rpeE(lib)}${v === ici ? ' (ici)' : ''}</option>`;
  const opts = [opt('|0', 'Documents annuels')];
  for (const s of (r.sequences || [])) {
    opts.push(opt(`${s.code}|0`, `${s.code} — ${s.nom}`));
    for (const p of (s.parties || [])) {
      opts.push(opt(`${s.code}|${p.numero}`, `\u00a0\u00a0\u00a0${s.code} · P${p.numero}${p.libelle ? ' ' + p.libelle : ''}`));
    }
  }
  return `<select class="rpe-deplacer" title="Déplacer le document vers un autre point d'attache"
    aria-label="Déplacer le document" onchange="rpeDeplacerFichier('${f.id}', this.value)">
    <option value="" selected>déplacer vers…</option>${opts.join('')}</select>`;
}

async function rpeDeplacerFichier(fid, v) {
  if (!v) return;
  const [seq_code, num] = v.split('|');
  try {
    const d = await _rpeApi(`${_RPE_API}/fichiers/${fid}/rattachement`,
      _rpeJ({ m: 'PUT', b: { seq_code, partie_numero: parseInt(num, 10) || 0 } }));
    _rpeStatus(d.alerte || 'Document déplacé.', !!d.alerte);
  } catch (e) { _rpeStatus(e.message, true); }
  await rpeCharger();
}

function rpeTyperFichier(fid, typeId) {
  return _rpeAction(`${_RPE_API}/fichiers/${fid}/type`, _rpeJ({ m: 'PUT', b: { type_id: typeId } }));
}

// v0.48.6 — Présentation sur le modèle des MER (cadre violet par séquence),
// objectifs typés (connaissance en tête, capacités), critères F/A/E repliés.
function _rpeSeq(r, s) {
  const verrou = s.commencee;
  const ctl = (html) => verrou ? '' : html;
  return `<div class="rx-seq${verrou ? ' rx-seq-commencee' : ''}">
    <div class="rx-seq-tete">
      <span class="rx-seq-label">Séquence</span>
      <span class="rpe-code">${_rpeE(s.code)}</span>
      ${_rpeThemeSelect(r, s, verrou)}
      <input class="rx-seq-nom" value="${_rpeE(s.nom)}" aria-label="Nom de la séquence"
        onchange="rpeModifierSeq('${r.id}', '${s.code}', this.value)">
      ${verrou ? '<span class="rpe-badge rpe-verrou" title="Un créneau de progression a démarré">commencée</span>' : ''}
      <span class="rx-seq-actions">${ctl(`<button class="btn-sm" title="Monter la séquence" onclick="rpeDeplacerSeq('${r.id}', '${s.code}', -1)">↑</button>
        <button class="btn-sm" title="Descendre la séquence" onclick="rpeDeplacerSeq('${r.id}', '${s.code}', 1)">↓</button>
        <button class="btn-sm rx-suppr" title="Supprimer la séquence" onclick="rpeSupprimerSeq('${r.id}', '${s.code}')">×</button>`)}</span>
    </div>
    <div class="rx-seq-corps">
      <div class="rx-sous-titre">Documents de la séquence</div>
      ${_rpeFichiers(r, s.code, 0, s.fichiers || [])}
      ${(s.parties || []).map(p => _rpePartie(r, s, p, verrou, ctl)).join('')
        || '<div class="rpe-vide">Aucune partie.</div>'}
      ${ctl(`<div class="rx-ajout">
        <button class="btn-sm" onclick="rpeAjouterPartie('${r.id}', '${s.code}')">+ partie</button></div>`)}
    </div>
  </div>`;
}

function _rpePartie(r, s, p, verrou, ctl) {
  const objs = p.objectifs || [];
  const aConn = objs.some(o => o.type_obj === 'connaissance');
  return `<div class="rx-partie">
    <div class="rx-partie-tete">
      <span class="rx-petit">P${p.numero} ·</span>
      <input class="rx-partie-lib" value="${_rpeE(p.libelle || '')}" placeholder="libellé de la partie (facultatif)"
        aria-label="Libellé de la partie" onchange="rpeLibellerPartie('${r.id}', '${s.code}', ${p.numero}, this.value)">
      <span class="rpe-duree" title="Somme des séances des objectifs de la partie">${_rpeE(String(+p.nb_seances_R_AE || 0).replace('.', ','))}</span>
      <span class="rx-petit">séance(s)</span>
      ${ctl(`<button class="btn-sm" title="Monter la partie" onclick="rpeDeplacerPartie('${r.id}', '${s.code}', ${p.numero}, -1)">↑</button>
        <button class="btn-sm" title="Descendre la partie" onclick="rpeDeplacerPartie('${r.id}', '${s.code}', ${p.numero}, 1)">↓</button>
        <button class="btn-sm rx-suppr" title="Supprimer la partie" onclick="rpeSupprimerPartie('${r.id}', '${s.code}', ${p.numero})">×</button>`)}
    </div>
    <div class="rx-partie-corps">
      <div class="rx-sous-titre">Objectifs${p.sans_capacite ? ' <span class="rx-alerte-inline">— au moins une capacité attendue</span>' : ''}</div>
      ${objs.map(o => _rpeObjectif(r, s, o, verrou, ctl)).join('') || '<div class="rpe-vide">Aucun objectif.</div>'}
      ${ctl(`<div class="rx-ajout">
        ${aConn ? '' : `<button class="btn-sm" onclick="rpeAjouterConnaissance('${r.id}', '${s.code}', ${p.numero})"
          title="Objectif « Connaître le cours » (critères pré-remplis, toujours en tête)">+ objectif « Connaître »</button>`}
        <input id="rpe-obj-${r.id}-${s.code}-${p.numero}" placeholder="Nouvelle capacité"
          onkeydown="if(event.key==='Enter') rpeAjouterObj('${r.id}', '${s.code}', ${p.numero})">
        <button class="btn-sm" onclick="rpeAjouterObj('${r.id}', '${s.code}', ${p.numero})">+ capacité</button></div>`)}
      <div class="rx-sous-titre">Documents de la partie</div>
      ${_rpeFichiers(r, s.code, p.numero, p.fichiers || [])}
    </div>
  </div>`;
}

function _rpeObjectif(r, s, o, verrou, ctl) {
  const cle = `${r.id}|${s.code}|${o.code}`;
  const ouvert = RPE.criteres.has(cle);
  const conn = o.type_obj === 'connaissance';
  return `<div class="rx-obj">
    <div class="rx-obj-ligne">
      <span class="rpe-code">${_rpeE(o.code)}</span>
      <span class="rx-obj-type rx-obj-${conn ? 'conn' : 'cap'}">${conn ? 'connaissance' : 'capacité'}</span>
      <input class="rx-obj-nom" value="${_rpeE(o.nom)}" aria-label="Nom de l'objectif"
        onchange="rpeModifierObj('${r.id}', '${s.code}', '${o.code}', {nom: this.value})">
      <input type="number" min="0" step="0.5" value="${o.nb_seances}" class="rpe-nb" ${verrou ? 'disabled' : ''}
        title="nombre de séances" onchange="rpeModifierObj('${r.id}', '${s.code}', '${o.code}', {nb_seances: this.value})">
      <span class="rx-petit">séance(s)</span>
      <button class="btn-lien rx-criteres-btn" onclick="rpeBasculerCriteres('${cle}')">${ouvert ? '▾' : '▸'} critères d'atteinte des niveaux de maîtrise</button>
      <span class="rx-seq-actions">${ctl(conn ? `<button class="btn-sm rx-suppr" title="Supprimer" onclick="rpeSupprimerObj('${r.id}', '${s.code}', '${o.code}')">×</button>`
        : `<button class="btn-sm" title="Monter" onclick="rpeDeplacerObj('${r.id}', '${s.code}', '${o.code}', -1)">↑</button>
        <button class="btn-sm" title="Descendre" onclick="rpeDeplacerObj('${r.id}', '${s.code}', '${o.code}', 1)">↓</button>
        <button class="btn-sm rx-suppr" title="Supprimer" onclick="rpeSupprimerObj('${r.id}', '${s.code}', '${o.code}')">×</button>`)}</span>
    </div>
    ${ouvert ? `<div class="rx-criteres">${['f', 'a', 'e'].map(k => `
      <label><span>Critère ${k.toUpperCase()}</span>
        <textarea rows="2" onchange="rpeModifierObj('${r.id}', '${s.code}', '${o.code}', {critere_${k}: this.value})">${_rpeE(o['critere_' + k])}</textarea></label>`).join('')}
    </div>` : ''}
  </div>`;
}

function rpeBasculerCriteres(cle) {
  RPE.criteres.has(cle) ? RPE.criteres.delete(cle) : RPE.criteres.add(cle);
  rpeRendre();
}

function rpeAjouterConnaissance(id, c, num) {
  return _rpeAction(`${_RPE_API}/${id}/sequences/${c}/parties/${num}/objectifs`,
    _rpeJ({ b: { type_obj: 'connaissance' } }));
}

function rpeBasculer(id) { RPE.ouverts.has(id) ? RPE.ouverts.delete(id) : RPE.ouverts.add(id); rpeRendre(); }
const _rpeJ = (o) => ({ method: o.m || 'POST', body: JSON.stringify(o.b || {}) });

function rpeModifierDesc(id, v) { return _rpeAction(`${_RPE_API}/${id}`, _rpeJ({ m: 'PUT', b: { description: v } })); }
function rpeSupprimer(id) {
  if (!confirm('Supprimer ce référentiel et tous ses documents ?')) return;
  return _rpeAction(`${_RPE_API}/${id}`, { method: 'DELETE' }, 'Référentiel supprimé.');
}
function rpeAjouterSeq(id, theme) {
  const i = document.getElementById(`rpe-seq-${id}-${theme || '_'}`);
  if (!i || !i.value.trim()) return;
  RPE.ouverts.add(id);
  return _rpeAction(`${_RPE_API}/${id}/sequences`, _rpeJ({ b: { nom: i.value, theme_code: theme || null } }));
}

// ── v0.51.5 — Thèmes ────────────────────────────────────────────────────────
const RPE_COULEURS = { nombres: '#c0392b', donnees: '#2980b9', grandeurs: '#d35400',
  geometrie: '#8e44ad', algorithmique: '#e91e63', proportionnalite: '#00808a',
  noir_gris: '#555555' };
function _rpeCouleur(c) { return RPE_COULEURS[c] || '#777'; }

function _rpeThemes(r) {
  const couleurs = r.couleurs_themes || [];
  const opts = (sel) => '<option value="">— couleur —</option>' + couleurs.map(c =>
    `<option value="${c.code}"${c.code === sel ? ' selected' : ''}>${_rpeE(c.libelle)}</option>`).join('');
  const lignes = (r.themes || []).map(t => `<div class="rpe-theme-ligne">
      <span class="rpe-theme-code" style="background:${_rpeCouleur(t.couleur)}">${_rpeE(t.code)}</span>
      <input class="rpe-theme-nom" value="${_rpeE(t.nom)}" aria-label="Nom du thème"
        onchange="rpeModifierTheme('${r.id}', '${t.code}', {nom: this.value})">
      <select onchange="rpeModifierTheme('${r.id}', '${t.code}', {couleur: this.value})" aria-label="Couleur du thème">${opts(t.couleur)}</select>
      <span class="rx-petit">${t.nb_sequences} séquence(s)</span>
      <button class="btn-sm" title="Monter le thème et ses séquences" onclick="rpeDeplacerTheme('${r.id}', '${t.code}', -1)">↑</button>
      <button class="btn-sm" title="Descendre le thème et ses séquences" onclick="rpeDeplacerTheme('${r.id}', '${t.code}', 1)">↓</button>
      <button class="btn-sm rx-suppr" title="Supprimer le thème" onclick="rpeSupprimerTheme('${r.id}', '${t.code}', ${t.nb_sequences})">×</button>
    </div>`).join('');
  return `<div class="rpe-themes">
    <div class="rx-sous-titre">Thèmes</div>
    ${lignes || '<div class="rpe-vide">Aucun thème.</div>'}
    <div class="rx-ajout"><input id="rpe-theme-${r.id}" placeholder="Nouveau thème"
        onkeydown="if(event.key==='Enter') rpeAjouterTheme('${r.id}')">
      <select id="rpe-theme-coul-${r.id}" aria-label="Couleur du nouveau thème">${opts('')}</select>
      <button class="btn-sm" onclick="rpeAjouterTheme('${r.id}')">+ thème</button></div>
  </div>`;
}

// Séquences regroupées par thème (ordre des thèmes), puis les séquences sans thème.
function _rpeGroupes(r) {
  const themes = r.themes || [];
  const seqs = r.sequences || [];
  const groupes = themes.map(t => ({ t, seqs: seqs.filter(s => s.theme_code === t.code) }));
  const sans = seqs.filter(s => !themes.some(t => t.code === s.theme_code));
  if (sans.length || !themes.length) groupes.push({ t: null, seqs: sans });
  return groupes.map(({ t, seqs: ss }) => {
    const cle = t ? t.code : '_';
    const arg = t ? `'${t.code}'` : 'null';
    return `<div class="rpe-groupe"${t ? ` style="--theme:${_rpeCouleur(t.couleur)}"` : ''}>
      <div class="rpe-groupe-tete">${t ? `Thème ${_rpeE(t.code)} — ${_rpeE(t.nom)}` : 'Sans thème'}</div>
      ${ss.map(s => _rpeSeq(r, s)).join('') || '<p class="rpe-vide">Aucune séquence.</p>'}
      <div class="rpe-ajout"><input id="rpe-seq-${r.id}-${cle}" placeholder="Nom de la nouvelle séquence"
        onkeydown="if(event.key==='Enter') rpeAjouterSeq('${r.id}', ${arg})">
        <button class="btn-sm" onclick="rpeAjouterSeq('${r.id}', ${arg})">+ séquence</button></div>
    </div>`;
  }).join('');
}

function _rpeThemeSelect(r, s, verrou) {
  if (!(r.themes || []).length) return '';
  const opts = '<option value="">— sans thème —</option>' + r.themes.map(t =>
    `<option value="${t.code}"${t.code === s.theme_code ? ' selected' : ''}>${_rpeE(t.code)} ${_rpeE(t.nom)}</option>`).join('');
  return `<select class="rpe-seq-theme" title="Thème de la séquence" aria-label="Thème de la séquence"
    ${verrou ? 'disabled' : ''} onchange="rpeAffecterTheme('${r.id}', '${s.code}', this.value)">${opts}</select>`;
}

function rpeAjouterTheme(id) {
  const i = document.getElementById('rpe-theme-' + id);
  const c = document.getElementById('rpe-theme-coul-' + id);
  if (!i || !i.value.trim()) return;
  return _rpeAction(`${_RPE_API}/${id}/themes`, _rpeJ({ b: { nom: i.value, couleur: c ? c.value : '' } }));
}
function rpeModifierTheme(id, code, champs) { return _rpeAction(`${_RPE_API}/${id}/themes/${code}`, _rpeJ({ m: 'PUT', b: champs })); }
function rpeDeplacerTheme(id, code, sens) { return _rpeAction(`${_RPE_API}/${id}/themes/${code}/deplacer`, _rpeJ({ b: { sens } })); }
function rpeSupprimerTheme(id, code, n) {
  if (!confirm(n ? `Supprimer le thème ${code} ? Ses ${n} séquence(s) passeront « sans thème ».` : `Supprimer le thème ${code} ?`)) return;
  return _rpeAction(`${_RPE_API}/${id}/themes/${code}`, { method: 'DELETE' });
}
function rpeAffecterTheme(id, c, theme) {
  return _rpeAction(`${_RPE_API}/${id}/sequences/${c}/theme`, _rpeJ({ m: 'PUT', b: { theme_code: theme || null } }));
}
function rpeModifierSeq(id, c, nom) { return _rpeAction(`${_RPE_API}/${id}/sequences/${c}`, _rpeJ({ m: 'PUT', b: { nom } })); }
function rpeDeplacerSeq(id, c, sens) { return _rpeAction(`${_RPE_API}/${id}/sequences/${c}/deplacer`, _rpeJ({ b: { sens } })); }
function rpeSupprimerSeq(id, c) {
  if (!confirm(`Supprimer la séquence ${c} (parties, objectifs, fichiers) ?`)) return;
  return _rpeAction(`${_RPE_API}/${id}/sequences/${c}`, { method: 'DELETE' });
}
function rpeAjouterPartie(id, c) {
  return _rpeAction(`${_RPE_API}/${id}/sequences/${c}/parties`, _rpeJ({ b: {} }));
}
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
  if (!confirm('Supprimer ce document ?')) return;
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
      const url = c ? `${_RPE_API}/${id}/sequences/${c}/fichiers` : `${_RPE_API}/${id}/documents-annuels`;
      const r = await fetch(url, { method: 'POST', body: fd });
      r.ok ? ok++ : ko++;
    } catch (e) { ko++; }
  }
  _rpeStatus(ko ? `${ok} ajouté(s), ${ko} en échec.` : `${ok} document(s) ajouté(s).`, !!ko);
  await rpeCharger();
}


// ── v0.48.3 — Types de documents (Système › Préférences) ────────────────────

async function prefTypesDocsCharger() {
  const z = document.getElementById('pref-typesdocs-liste');
  if (!z) return;
  let types = [];
  try { types = (await _rpeApi('/api/types-documents?tout=1')).types || []; } catch (e) {}
  z.innerHTML = types.map(t => `<div class="pref-td-ligne${t.actif ? '' : ' pref-td-inactif'}">
      <input value="${_rpeE(t.libelle)}" onchange="prefTypesDocsModifier('${t.id}', {libelle: this.value})">
      <button class="btn-sm" onclick="prefTypesDocsDeplacer('${t.id}', -1)" title="Monter">↑</button>
      <button class="btn-sm" onclick="prefTypesDocsDeplacer('${t.id}', 1)" title="Descendre">↓</button>
      <button class="btn-sm" onclick="prefTypesDocsModifier('${t.id}', {actif: ${!t.actif}})">${t.actif ? 'Désactiver' : 'Réactiver'}</button>
    </div>`).join('');
}

async function _prefTd(url, opts) {
  const st = document.getElementById('pref-typesdocs-status');
  try { await _rpeApi(url, opts); if (st) st.textContent = ''; }
  catch (e) { if (st) st.textContent = e.message; }
  await prefTypesDocsCharger();
}

function prefTypesDocsAjouter() {
  const i = document.getElementById('pref-typesdocs-nouveau');
  if (!i || !i.value.trim()) return;
  return _prefTd('/api/types-documents', { method: 'POST', body: JSON.stringify({ libelle: i.value }) })
    .then(() => { i.value = ''; });
}
function prefTypesDocsModifier(id, champs) {
  return _prefTd('/api/types-documents/' + id, { method: 'PUT', body: JSON.stringify(champs) });
}
function prefTypesDocsDeplacer(id, sens) {
  return _prefTd('/api/types-documents/' + id + '/deplacer', { method: 'POST', body: JSON.stringify({ sens }) });
}


// v0.49.2 — Le rendu passe par l'onglet unique (static/referentiel_unifie.js).
// v0.51.11 — L'écran intermédiaire (liste + détail) et l'ancien modèle de MER
// sont retirés.
function rxaRendre() {
  if (typeof refuRendre === 'function') refuRendre();
}


// ── v0.48.5 — Placement par défaut d'un fichier de partie ────────────────────
// Séance de distribution dans la partie (vide = à associer à la main dans la
// progression), retour attendu et délai (contrôles partagés avec la
// progression : static/progression_doc.js).
function _rpePlacement(f) {
  const pfx = 'rpf-' + f.id;
  // v0.49.1 — Référentiel de MER : « pour la fin de la partie » au lieu de
  // « pour la fin du créneau ».
  const mer = (RPE.liste.find(r => r.id === f.referentiel_id) || {}).type_ref === 'mer';
  const delais = mer && typeof _PM_DELAIS_MER !== 'undefined' ? _PM_DELAIS_MER : undefined;
  const ctl = (typeof _pdRetourControles === 'function')
    ? _pdRetourControles(pfx, f, `rpePlacer('${f.id}')`, delais) : '';
  return `<span class="rpe-placement" title="Placement automatique dans la progression principale">
    séance <input type="number" min="0" max="60" id="${pfx}-seance" class="rpe-nb"
      value="${f.seance_n || ''}" placeholder="—" onchange="rpePlacer('${f.id}')">
    ${ctl}</span>`;
}

function rpePlacer(fid) {
  const pfx = 'rpf-' + fid;
  const v = (typeof _pdRetourValeurs === 'function') ? _pdRetourValeurs(pfx) : { retour: '' };
  const n = parseInt((document.getElementById(pfx + '-seance') || {}).value || '0', 10) || 0;
  return _rpeAction(`${_RPE_API}/fichiers/${fid}/placement`, _rpeJ({ m: 'PUT', b: { seance_n: n, ...v } }));
}

// v0.49.0 — Libellé de partie (correction toujours permise).
function rpeLibellerPartie(id, c, num, v) {
  return _rpeAction(`${_RPE_API}/${id}/sequences/${c}/parties/${num}/libelle`, _rpeJ({ m: 'PUT', b: { libelle: v } }));
}
