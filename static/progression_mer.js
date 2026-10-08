// ============================================================================
// static/progression_mer.js — v0.27.0
// Onglet « Progression de MER » (Suivi annuel), par NIVEAU. Présentation façon
// progression principale : parties du référentiel à gauche, progression
// composée + planning à droite. Sélecteurs globaux : établissement, niveau,
// classe (aucune = planning théorique ; une classe = planning avec ses indispos).
// ============================================================================

let PROGMER = null;        // progression MER du niveau courant
let PROGMER_REFS = [];     // référentiels MER externes validés du niveau
let PROGMER_DISPO = [];    // parties disponibles du référentiel choisi

function _progmerAnnee() {
  return (typeof ANNEE_ACTIVE !== 'undefined' && ANNEE_ACTIVE)
    || (typeof anneeScolaireCourante === 'function' ? anneeScolaireCourante() : '');
}
function _progmerNiveau() {
  const el = document.getElementById('prog-sel-niveau');
  return el ? el.value : '';
}
function _progmerClasse() {
  const el = document.getElementById('classe-sel');
  return el ? el.value : '';
}

async function progMerInit() {
  await progMerCharger();
}

async function progMerCharger() {
  const niveau = _progmerNiveau();
  const annee = _progmerAnnee();
  const lbl = document.getElementById('progmer-niveau-lbl');
  if (lbl) lbl.textContent = niveau ? '(' + niveau + ' · ' + annee + ')' : '';
  if (!niveau) { PROGMER = null; PROGMER_REFS = []; PROGMER_DISPO = []; }
  else {
    try {
      PROGMER = await api('/api/progression-mer?niveau='
        + encodeURIComponent(niveau) + '&annee=' + encodeURIComponent(annee));
    } catch (e) { PROGMER = null; }
    try {
      const r = await api('/api/referentiels-externes?niveau='
        + encodeURIComponent(niveau) + '&type=mer');
      PROGMER_REFS = ((r && r.referentiels) || []).filter(x => x.etat === 'valide')
        .map(x => ({ ...x, source: 'externe' }));
    } catch (e) { PROGMER_REFS = []; }
    // v0.49.0 — Référentiels de MER de la structure figée (utilisables dès
    // leur création, même incomplets).
    try {
      const r2 = await api('/api/referentiels-principaux-externes?niveau='
        + encodeURIComponent(niveau) + '&type=mer');
      PROGMER_REFS = PROGMER_REFS.concat(((r2 && r2.referentiels) || [])
        .map(x => ({ ...x, source: 'fige' })));
    } catch (e) {}
    await progMerChargerDispo();
  }
  progMerRenderRef();
  progMerRenderDispo();
  progMerRenderComposee();
  progMerAfficherPlanning();
}

function progMerRenderRef() {
  const sel = document.getElementById('progmer-ref');
  if (!sel) return;
  const cour = PROGMER && PROGMER.ref_mer_id;
  sel.innerHTML = '<option value="">— Choisir un référentiel de MER —</option>'
    + PROGMER_REFS.map(r => `<option value="${r.id}"${r.id === cour ? ' selected' : ''}>`
      + `${escapeHtml(r.nom || '(sans nom)')}${r.source === 'externe' ? ' (ancien modèle)' : ''}</option>`).join('');
  if (cour) sel.value = cour;
}

async function progMerDefinirRef() {
  const sel = document.getElementById('progmer-ref');
  const refId = sel ? sel.value : '';
  if (!refId) return;
  try {
    PROGMER = await api('/api/progression-mer/referentiel?annee='
      + encodeURIComponent(_progmerAnnee()),
      { method: 'POST', body: JSON.stringify({ niveau: _progmerNiveau(),
        ref_mer_id: refId,
        ref_mer_source: ((PROGMER_REFS.find(r => r.id === refId) || {}).source) || 'externe' }) });
    await progMerChargerDispo();
    progMerRenderDispo();
    progMerRenderComposee();
    progMerAfficherPlanning();
  } catch (e) {}
}

async function progMerChargerDispo() {
  PROGMER_DISPO = [];
  if (!PROGMER || !PROGMER.id || !PROGMER.ref_mer_id) return;
  try {
    const r = await api('/api/progression-mer/' + PROGMER.id + '/parties-disponibles');
    PROGMER_DISPO = (r && r.parties) || [];
  } catch (e) {}
}

function progMerRenderDispo() {
  const zone = document.getElementById('progmer-dispo');
  if (!zone) return;
  if (!PROGMER || !PROGMER.ref_mer_id) {
    zone.innerHTML = '<span style="color:#999">Choisissez un référentiel.</span>';
    return;
  }
  const poses = new Set((PROGMER.parties || []).map(p => p.partie_id));
  const dispo = PROGMER_DISPO.filter(p => !poses.has(p.id));
  zone.innerHTML = dispo.length ? dispo.map(p => `
    <div style="padding:3px 0;border-bottom:1px solid var(--border)">
      <button class="btn-sm" style="font-size:12px;width:100%;text-align:left"
        onclick="progMerPoser('${p.id}')">
        + ${escapeHtml(p.sequence_code || '')} ${escapeHtml(p.libelle || '')}
        <span style="color:#888">(${p.nb_seances})</span></button>
    </div>`).join('')
    : '<span style="color:#999">Toutes les parties sont posées.</span>';
}

function progMerRenderComposee() {
  const zone = document.getElementById('progmer-composee');
  const total = document.getElementById('progmer-total');
  if (!zone) return;
  if (!PROGMER || !PROGMER.ref_mer_id) {
    zone.innerHTML = '<p style="font-size:13px;color:#999">Choisissez un '
      + 'référentiel MER validé pour composer la progression.</p>';
    if (total) total.textContent = '';
    return;
  }
  const posees = PROGMER.parties || [];
  if (total) {
    const n = posees.reduce((s, p) => s + (p.nb_seances || 0), 0);
    total.textContent = n + ' séance(s) au total';
  }
  zone.innerHTML = posees.length ? posees.map((p, i) => `
    <div style="display:flex;align-items:center;gap:8px;font-size:13px;padding:4px 0;border-bottom:1px solid var(--border)">
      <span style="color:#888;width:22px">${i + 1}.</span>
      <span style="flex:1">${escapeHtml(p.sequence_nom || p.sequence_code || '')} ·
        <strong>${escapeHtml(p.libelle || '')}</strong>
        <span style="color:#888">(${p.nb_seances} séance${p.nb_seances > 1 ? 's' : ''})</span></span>
      <button class="btn-sm" style="font-size:11px" aria-label="Monter"
        onclick="progMerDeplacer('${p.id}','haut')">↑</button>
      <button class="btn-sm" style="font-size:11px" aria-label="Descendre"
        onclick="progMerDeplacer('${p.id}','bas')">↓</button>
      ${PROGMER.ref_mer_source === 'fige' ? `<button class="btn-sm" style="font-size:11px"
        title="Documents à distribuer dans cette partie" onclick="progMerDocsBasculer('${p.partie_id}')">📄 documents</button>` : ''}
      <button class="btn-sm" style="font-size:11px;color:var(--danger)" aria-label="Retirer"
        onclick="progMerRetirer('${p.id}')">×</button>
    </div>
    ${PROGMER_DOCS_OUVERT === p.partie_id ? `<div class="pm-docs" id="pm-docs-zone"><p class="rx-petit">Chargement…</p></div>` : ''}`).join('')
    : '<p style="font-size:13px;color:#999">Aucune partie posée. Ajoutez-en '
      + 'depuis la colonne de gauche.</p>';
}

async function progMerPoser(partieId) {
  try {
    PROGMER = await api('/api/progression-mer/' + PROGMER.id + '/parties',
      { method: 'POST', body: JSON.stringify({ partie_id: partieId,
        partie_source: (PROGMER && PROGMER.ref_mer_source) || 'externe' }) });
    progMerRenderDispo(); progMerRenderComposee(); progMerAfficherPlanning();
  } catch (e) {}
}

async function progMerRetirer(poseId) {
  try {
    await fetch('/api/progression-mer/parties/' + poseId, { method: 'DELETE' });
    PROGMER = await api('/api/progression-mer?niveau='
      + encodeURIComponent(_progmerNiveau()) + '&annee=' + encodeURIComponent(_progmerAnnee()));
    progMerRenderDispo(); progMerRenderComposee(); progMerAfficherPlanning();
  } catch (e) {}
}

async function progMerDeplacer(poseId, sens) {
  try {
    PROGMER = await api('/api/progression-mer/parties/' + poseId + '/deplacer',
      { method: 'POST', body: JSON.stringify({ sens }) });
    progMerRenderComposee(); progMerAfficherPlanning();
  } catch (e) {}
}

// Planning : théorique (sans classe) ou pour la classe sélectionnée.
function progMerAfficherPlanning() {
  const zone = document.getElementById('progmer-plan-zone');
  const dl = document.getElementById('progmer-plan-dl');
  if (!zone) return;
  const posees = PROGMER && PROGMER.parties || [];
  if (!posees.length) {
    if (dl) dl.style.display = 'none';
    const pr = document.getElementById('progmer-plan-print');
    if (pr) pr.style.display = 'none';
    zone.innerHTML = '<p style="font-size:13px;color:#999;padding:16px;'
      + 'text-align:center">Posez des parties pour afficher l\'aperçu.</p>';
    return;
  }
  // Onglet « Progression de MER » = composition par NIVEAU → aperçu théorique
  // (sans dates réelles). Le planning daté d'une classe est dans « Mises en
  // route ».
  const q = '?annee=' + encodeURIComponent(_progmerAnnee());
  // v0.50.0 — Page imprimable HTML (A4) au lieu du PDF LaTeX.
  afficherImpression(zone, 'progmer-plan-frame',
    'Aperçu théorique de la progression MER',
    '/impression/progression-mer/' + PROGMER.id + '/planning-theorique' + q,
    { hauteur: '55vh', dlId: 'progmer-plan-dl', printId: 'progmer-plan-print' });
}


// ── v0.49.1 — Documents à distribuer d'une partie de MER ────────────────────
// Placement automatique : fichiers de la partie portant leur séance (réglé
// dans le référentiel). Association manuelle (ici) : remplace le placement
// automatique du même fichier, ou distribue un document sans séance prévue
// (documents de la partie, de la séquence ou annuels).
let PROGMER_DOCS_OUVERT = null;
const _PM_DELAIS_MER = [['prochaine', 'pour la prochaine séance'], ['jours', 'dans … jour(s)'],
  ['semaines', 'dans … semaine(s)'], ['fin_partie', 'pour la fin de la partie']];

async function progMerDocsBasculer(partieRef) {
  PROGMER_DOCS_OUVERT = (PROGMER_DOCS_OUVERT === partieRef) ? null : partieRef;
  progMerRenderComposee();
  if (PROGMER_DOCS_OUVERT) await progMerDocsCharger();
}

async function progMerDocsCharger() {
  const z = document.getElementById('pm-docs-zone');
  if (!z || !PROGMER) return;
  const pref = PROGMER_DOCS_OUVERT;
  const [rid, seq, num] = pref.split('|');
  let ref = null, manuels = [];
  try {
    ref = await api('/api/referentiels-principaux-externes/' + encodeURIComponent(rid));
    manuels = (await api('/api/progression-doc?prog_kind=mer&prog_ref=' + encodeURIComponent(PROGMER.id)
      + '&creneau_ref=' + encodeURIComponent(pref))).associations || [];
  } catch (e) { z.innerHTML = `<p class="rx-petit">${escapeHtml(e.message)}</p>`; return; }
  const s = (ref.sequences || []).find(x => x.code === seq) || { parties: [], fichiers: [] };
  const p = (s.parties || []).find(x => String(x.numero) === num) || { fichiers: [] };
  const remplaces = new Set(manuels.map(a => a.doc_ref));
  const auto = (p.fichiers || []).filter(f => f.seance_n > 0);
  const dispo = [...(p.fichiers || []), ...(s.fichiers || []), ...(ref.documents_annuels || [])];
  const lib = f => (f.type_libelle ? f.type_libelle + ' : ' : '') + f.nom_fichier;
  const ctl = (pfx, a, onch) => (typeof _pdRetourControles === 'function')
    ? _pdRetourControles(pfx, a, onch, _PM_DELAIS_MER) : '';
  z.innerHTML = `
    <div class="rx-sous-titre">Placés automatiquement (réglage du référentiel)</div>
    ${auto.length ? auto.map(f => `<div class="rx-doc-ligne${remplaces.has(f.id) ? ' pm-remplace' : ''}">
        <span class="rx-doc-nom">${escapeHtml(lib(f))}</span><span class="rx-petit">séance ${f.seance_n}</span>
        ${remplaces.has(f.id) ? '<span class="rx-petit">— remplacé par une association ci-dessous</span>' : ''}</div>`).join('')
      : '<div class="rx-petit">Aucun.</div>'}
    <div class="rx-sous-titre">Associés à la main</div>
    ${manuels.length ? manuels.map(a => `<div class="rx-doc-ligne">
        <span class="rx-doc-nom">${escapeHtml(a.doc_libelle || a.doc_ref)}</span>
        <span class="rx-petit">séance ${a.rang_seance}</span>
        ${ctl('pm-' + a.id, a, `progDocsModifierRetour('${a.id}', 'pm-${a.id}')`)}
        <button class="btn-sm rx-suppr" onclick="progMerDocSupprimer('${a.id}')">×</button></div>`).join('')
      : '<div class="rx-petit">Aucun.</div>'}
    <div class="rx-ajout">
      <select id="pm-doc-choix">${dispo.map(f => `<option value="${f.id}">${escapeHtml(lib(f))}</option>`).join('')
        || '<option value="">(aucun document dans le référentiel)</option>'}</select>
      séance <input type="number" id="pm-doc-rang" min="1" max="60" value="1" class="rpe-nb">
      ${ctl('pm-nouveau', null, '')}
      <button class="btn-sm" onclick="progMerDocAjouter()">+ associer</button>
    </div>`;
}

async function progMerDocAjouter() {
  const sel = document.getElementById('pm-doc-choix');
  if (!sel || !sel.value) return;
  const v = (typeof _pdRetourValeurs === 'function') ? _pdRetourValeurs('pm-nouveau') : {};
  try {
    await api('/api/progression-doc', { method: 'POST', body: JSON.stringify({
      prog_kind: 'mer', prog_ref: PROGMER.id, creneau_ref: PROGMER_DOCS_OUVERT,
      rang_seance: parseInt(document.getElementById('pm-doc-rang').value || '1', 10),
      doc_source: 'externe', doc_ref: sel.value,
      doc_libelle: sel.selectedOptions[0] ? sel.selectedOptions[0].text : '', ...v }) });
  } catch (e) {}
  await progMerDocsCharger();
}

async function progMerDocSupprimer(id) {
  try { await api('/api/progression-doc/' + id, { method: 'DELETE' }); } catch (e) {}
  await progMerDocsCharger();
}
