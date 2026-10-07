// ============================================================================
// static/progression_doc.js — v0.32.6
// Association de documents à distribuer à un créneau de la progression
// principale (via l'atelier progression). MER : câblage similaire à venir.
// ============================================================================

let PROG_DOCS_DISPO = { sequence: [], suivante: [], annuels: [] };

function _progDocsCtx() {
  // Contexte depuis l'atelier progression principale.
  const A = window.ATELIER_PROGRESSION;
  if (!A || !A.data || !A.creneauSel) return null;
  const creneaux = A.data.creneaux || [];
  const idx = creneaux.findIndex(x => x.id === A.creneauSel);
  if (idx < 0) return null;
  const cr = creneaux[idx];
  // v0.32.11 — « Séquence suivante » = séquence du créneau DATÉ immédiatement
  // après celui-ci (ordre CALENDAIRE, par date_debut ; pas l'ordre de stockage,
  // pas Sn+1). Ex. si S03 (07/09) est suivi de S11 (21/09), on propose S11.
  let seqSuivante = '';
  const datés = creneaux
    .filter(x => x.date_debut)
    .slice()
    .sort((a, b) => (a.date_debut < b.date_debut ? -1
                     : a.date_debut > b.date_debut ? 1 : 0));
  const posCal = datés.findIndex(x => x.id === cr.id);
  if (posCal >= 0) {
    for (let i = posCal + 1; i < datés.length; i++) {
      const s = datés[i].sequence || '';
      if (s && s !== (cr.sequence || '')) { seqSuivante = s; break; }
    }
  }
  return {
    prog_kind: 'principale',
    prog_ref: A.data.id,
    niveau: A.data.niveau,
    annee: (typeof ANNEE_ACTIVE !== 'undefined' && ANNEE_ACTIVE) || '',
    creneau_ref: cr.id,
    sequence: cr.sequence || '',
    sequence_suivante: seqSuivante,
  };
}

// Appelé par l'atelier à la sélection d'un créneau.
async function progDocsCharger() {
  const ctx = _progDocsCtx();
  const bloc = document.getElementById('prog-docs-saisie');
  if (!bloc) return;
  if (!ctx || !ctx.sequence) { bloc.style.display = 'none'; return; }
  bloc.style.display = '';
  await progDocsRemplirSelect();
  await progDocsRenderListe();
}

async function progDocsRemplirSelect() {
  const ctx = _progDocsCtx();
  const sel = document.getElementById('prog-docs-select');
  if (!ctx || !sel) return;
  const suivante = document.getElementById('prog-docs-suivante');
  // « Séquence suivante » = séquence du créneau suivant (fournie par le contexte).
  const seqSuiv = (suivante && suivante.checked) ? (ctx.sequence_suivante || '') : '';
  const params = new URLSearchParams({
    niveau: ctx.niveau, annee: ctx.annee, sequence: ctx.sequence });
  if (seqSuiv) params.set('suivante', seqSuiv);
  try {
    PROG_DOCS_DISPO = await api('/api/progression-doc/disponibles?' + params.toString());
  } catch (e) { PROG_DOCS_DISPO = { sequence: [], suivante: [], annuels: [] }; }

  const opt = (d, prefixe) =>
    `<option value="${escapeHtml(d.source)}|${escapeHtml(d.doc_ref)}"
       data-libelle="${escapeHtml(d.libelle)}">${prefixe}${escapeHtml(d.libelle)}</option>`;
  let html = '<option value="">— choisir un document —</option>';
  if (PROG_DOCS_DISPO.sequence.length) {
    html += '<optgroup label="Cette séquence">'
      + PROG_DOCS_DISPO.sequence.map(d => opt(d, '')).join('') + '</optgroup>';
  }
  if ((PROG_DOCS_DISPO.suivante || []).length) {
    html += '<optgroup label="Séquence suivante">'
      + PROG_DOCS_DISPO.suivante.map(d => opt(d, '→ ')).join('') + '</optgroup>';
  }
  if (PROG_DOCS_DISPO.annuels.length) {
    html += '<optgroup label="Documents annuels">'
      + PROG_DOCS_DISPO.annuels.map(d => opt(d, '')).join('') + '</optgroup>';
  }
  sel.innerHTML = html;
}

async function progDocsRenderListe() {
  progDocsRenderRetourNouveau();      // v0.48.0
  const ctx = _progDocsCtx();
  const zone = document.getElementById('prog-docs-liste');
  if (!ctx || !zone) return;
  let assocs = [];
  try {
    const r = await api('/api/progression-doc?prog_kind=' + ctx.prog_kind
      + '&prog_ref=' + encodeURIComponent(ctx.prog_ref)
      + '&creneau_ref=' + encodeURIComponent(ctx.creneau_ref));
    assocs = r.associations || [];
  } catch (e) { assocs = []; }
  if (!assocs.length) {
    zone.innerHTML = '<p style="font-size:12px;color:#999">Aucun document associé à ce créneau.</p>';
    return;
  }
  zone.innerHTML = assocs.map(a => `
    <div style="display:flex;align-items:center;gap:8px;font-size:12px;padding:2px 0;flex-wrap:wrap">
      <span style="background:#eef;border-radius:3px;padding:1px 6px">séance ${a.rang_seance}</span>
      <span>${escapeHtml(a.doc_libelle || a.doc_ref)}</span>
      ${_pdRetourControles('pd-' + a.id, a, `progDocsModifierRetour('${a.id}', 'pd-${a.id}')`)}
      <button class="btn-sm" style="margin-left:auto;color:var(--danger);padding:0 6px"
        onclick="progDocsSupprimer('${a.id}')" aria-label="Retirer">×</button>
    </div>`).join('');
}

async function progDocsAjouter() {
  const ctx = _progDocsCtx();
  const sel = document.getElementById('prog-docs-select');
  const rang = document.getElementById('prog-docs-rang');
  if (!ctx || !sel || !sel.value) return;
  const [source, ...refParts] = sel.value.split('|');
  const doc_ref = refParts.join('|');
  const libelle = sel.options[sel.selectedIndex].getAttribute('data-libelle') || '';
  try {
    await fetch('/api/progression-doc', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prog_kind: ctx.prog_kind, prog_ref: ctx.prog_ref,
        creneau_ref: ctx.creneau_ref,
        rang_seance: parseInt(rang.value || '1', 10),
        doc_source: source, doc_ref: doc_ref, doc_libelle: libelle,
        ..._pdRetourValeurs('pd-nouveau'),
      }),
    });
  } catch (e) {}
  await progDocsRenderListe();
}

async function progDocsSupprimer(id) {
  try {
    await fetch('/api/progression-doc/' + id, { method: 'DELETE' });
  } catch (e) {}
  await progDocsRenderListe();
}

// ── v0.48.0 — Retour attendu (à faire / à rendre) et délai de réalisation ──

const _PD_DELAIS = [['prochaine', 'pour la prochaine séance'], ['jours', 'dans … jour(s)'],
  ['semaines', 'dans … semaine(s)'], ['fin_creneau', 'pour la fin du créneau']];

// Contrôles « retour + délai » ; `pfx` préfixe les id, `onchange` est appelé
// à chaque modification (vide pour le formulaire d'ajout).
function _pdRetourControles(pfx, a, onchange, delais) {
  // v0.49.1 — `delais` : liste des délais proposés (MER : « fin de la partie »).
  const liste = delais || _PD_DELAIS;
  const r = (a && a.retour) || '', t = (a && a.delai_type) || 'prochaine', n = (a && a.delai_n) || 1;
  const ch = onchange ? ` onchange="${onchange}"` : '';
  const nbVisible = r && (t === 'jours' || t === 'semaines');
  return `<span class="pd-retour-ctl">
    <select id="${pfx}-retour" title="Retour attendu"${onchange ? ` onchange="_pdMaj('${pfx}'); ${onchange}"` : ` onchange="_pdMaj('${pfx}')"`}>
      <option value=""${!r ? ' selected' : ''}>sans retour</option>
      <option value="faire"${r === 'faire' ? ' selected' : ''}>à faire</option>
      <option value="rendre"${r === 'rendre' ? ' selected' : ''}>à rendre</option>
    </select>
    <select id="${pfx}-delai" style="${r ? '' : 'display:none'}"${onchange ? ` onchange="_pdMaj('${pfx}'); ${onchange}"` : ` onchange="_pdMaj('${pfx}')"`}>
      ${liste.map(([v, l]) => `<option value="${v}"${v === t ? ' selected' : ''}>${l}</option>`).join('')}
    </select>
    <input id="${pfx}-n" type="number" min="1" max="60" value="${n}" style="width:46px;${nbVisible ? '' : 'display:none'}"${ch}>
  </span>`;
}

function _pdMaj(pfx) {
  const r = document.getElementById(pfx + '-retour').value;
  const t = document.getElementById(pfx + '-delai').value;
  document.getElementById(pfx + '-delai').style.display = r ? '' : 'none';
  document.getElementById(pfx + '-n').style.display = (r && (t === 'jours' || t === 'semaines')) ? '' : 'none';
}

function _pdRetourValeurs(pfx) {
  const r = document.getElementById(pfx + '-retour');
  if (!r || !r.value) return { retour: '' };
  return { retour: r.value, delai_type: document.getElementById(pfx + '-delai').value,
           delai_n: parseInt(document.getElementById(pfx + '-n').value || '1', 10) || 1 };
}

async function progDocsModifierRetour(id, pfx) {
  try {
    const r = await fetch('/api/progression-doc/' + id + '/retour', { method: 'PUT',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(_pdRetourValeurs(pfx)) });
    if (!r.ok) { const d = await r.json(); alert(d.error || 'Erreur'); }
  } catch (e) { alert(e.message); }
}

function progDocsRenderRetourNouveau() {
  const z = document.getElementById('prog-docs-retour-zone');
  if (z) z.innerHTML = _pdRetourControles('pd-nouveau', null, '');
}

window.progDocsModifierRetour = progDocsModifierRetour;
window.progDocsCharger = progDocsCharger;
window.progDocsRemplirSelect = progDocsRemplirSelect;
window.progDocsAjouter = progDocsAjouter;
window.progDocsSupprimer = progDocsSupprimer;

// ============================================================================
// v0.32.9 — Redimensionnement du panneau de détail (poignée entre calendrier
// et détail). On tire la poignée : la largeur du détail suit la souris, le
// calendrier (flex:1) prend le reste.
// ============================================================================
let _progPoigneeX0 = 0, _progPoigneeW0 = 0;

function progPoigneeStart(ev) {
  const detail = document.getElementById('prog-creneau-form');
  if (!detail) return;
  ev.preventDefault();
  _progPoigneeX0 = ev.clientX;
  _progPoigneeW0 = detail.getBoundingClientRect().width;
  document.addEventListener('mousemove', _progPoigneeMove);
  document.addEventListener('mouseup', _progPoigneeStop);
  document.body.style.userSelect = 'none';
}

function _progPoigneeMove(ev) {
  const detail = document.getElementById('prog-creneau-form');
  if (!detail) return;
  // Tirer vers la GAUCHE (clientX diminue) élargit le détail.
  const delta = _progPoigneeX0 - ev.clientX;
  let w = _progPoigneeW0 + delta;
  const maxW = window.innerWidth * 0.7;
  w = Math.max(240, Math.min(maxW, w));
  detail.style.width = w + 'px';
}

function _progPoigneeStop() {
  document.removeEventListener('mousemove', _progPoigneeMove);
  document.removeEventListener('mouseup', _progPoigneeStop);
  document.body.style.userSelect = '';
  // Mémoriser la largeur choisie (par session).
  const detail = document.getElementById('prog-creneau-form');
  if (detail) {
    try { localStorage.setItem('prog-detail-largeur', detail.style.width); }
    catch (e) {}
  }
}

// Restaurer la largeur mémorisée au chargement.
(function _progPoigneeRestore() {
  try {
    const w = localStorage.getItem('prog-detail-largeur');
    if (w) {
      const appliquer = () => {
        const d = document.getElementById('prog-creneau-form');
        if (d) d.style.width = w;
      };
      if (document.readyState !== 'loading') appliquer();
      else document.addEventListener('DOMContentLoaded', appliquer);
    }
  } catch (e) {}
})();

window.progPoigneeStart = progPoigneeStart;

// v0.32.9 — La poignée n'est visible que quand le détail du créneau l'est.
function progSyncPoignee() {
  const detail = document.getElementById('prog-creneau-form');
  const poignee = document.getElementById('prog-poignee');
  if (!poignee) return;
  const visible = detail && detail.style.display !== 'none';
  // display:'' retomberait sur la règle CSS (.prog-poignee{display:none}) →
  // il faut une valeur explicite pour rendre la poignée visible.
  poignee.style.display = visible ? 'block' : 'none';
}
window.progSyncPoignee = progSyncPoignee;
