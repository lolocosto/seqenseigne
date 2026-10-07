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
      <button class="btn-sm" style="font-size:11px;color:var(--danger)" aria-label="Retirer"
        onclick="progMerRetirer('${p.id}')">×</button>
    </div>`).join('')
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
    zone.innerHTML = '<p style="font-size:13px;color:#999;padding:16px;'
      + 'text-align:center">Posez des parties pour afficher l\'aperçu.</p>';
    return;
  }
  // Onglet « Progression de MER » = composition par NIVEAU → aperçu théorique
  // (sans dates réelles). Le planning daté d'une classe est dans « Mises en
  // route ».
  const url = '/api/progression-mer/' + PROGMER.id + '/planning-theorique.pdf?annee='
    + encodeURIComponent(_progmerAnnee());
  zone.innerHTML = `<iframe id="progmer-plan-frame" title="Aperçu théorique de la progression MER"
      style="width:100%;height:55vh;border:0;border-radius:6px"></iframe>`;
  afficherPdfDansAppli(document.getElementById('progmer-plan-frame'), url);
  if (dl) { dl.href = url; dl.style.display = ''; }
}
