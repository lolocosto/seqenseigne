// ============================================================================
// static/referentiel_unifie.js — v0.49.2 (v0.51.1 : format d'échange)
// Conception › Niveau › « Référentiel » : UN SEUL onglet pour tous les
// référentiels du niveau de la portée — internes et externes, principaux et
// MER (ancien modèle de MER compris, tant qu'il n'est pas recréé).
//   - liste à gauche : filtres Année, Type, Source ; pour chaque filtre sans
//     valeur choisie, groupage dans cet ordre (année, puis type, puis source) ;
//   - création : source (interne / externe), type (principal / MER),
//     description ; nom calculé ;
//   - détail à droite : interne → détail historique (static/
//     atelier_referentiel.js) ; externe → éditeur commun (static/
//     referentiel_pe.js) ; ancien modèle de MER → éditeur historique
//     (static/referentiel_externe.js).
// ============================================================================

const REFU = { f: { annee: '', type: '', source: '' }, sel: null, actif: false };

function _refuE(s) { return escapeHtml(String(s == null ? '' : s)); }
function _refuAnneeInterne(version) {
  const y = parseInt(String(version || '').slice(0, 4), 10);
  return Number.isFinite(y) ? `${y}-${y + 1}` : '';
}

function _refuItems() {
  const items = [];
  (typeof ATL_REF_LISTE !== 'undefined' ? ATL_REF_LISTE : []).forEach(r => items.push({
    cle: 'I:' + r.id, id: r.id, source: 'interne', type: r.type_ref || 'principal',
    annee: _refuAnneeInterne(r.version), nom: r.nom || r.id, desc: r.description || '',
    etat: r.etat }));
  (typeof RPE !== 'undefined' ? RPE.liste : []).forEach(r => items.push({
    cle: 'E:' + r.id, id: r.id, source: 'externe', type: r.type_ref || 'principal',
    annee: r.annee || '', nom: r.nom, desc: r.description || '',
    etat: r.utilise ? 'utilise' : r.etat }));
  (typeof RXT_LISTE !== 'undefined' ? RXT_LISTE : []).forEach(r => items.push({
    cle: 'A:' + r.id, id: r.id, source: 'externe', type: 'mer', annee: r.annee || '',
    nom: (r.nom || '(sans nom)') + ' — ancien modèle', desc: r.description || '', etat: r.etat }));
  return items;
}

async function refuInit() {
  REFU.actif = true;
  // Données : internes (déjà chargés par atelRefInit), externes (structure
  // figée), ancien modèle de MER.
  if (typeof rpeCharger === 'function') await rpeCharger();
  if (typeof rxtCharger === 'function') { try { await rxtCharger(); } catch (e) {} }
  refuRendre();
}

function refuFiltre(cle, v) { REFU.f[cle] = v; refuRendre(); }

const _REFU_LIB = {
  type: { principal: 'Principal', mer: 'MER' },
  source: { interne: 'Interne', externe: 'Externe' },
};

function refuRendre() {
  const liste = document.getElementById('atl-ref-liste');
  if (!REFU.actif || !liste) return;
  const tous = _refuItems();
  // Années connues (filtre).
  const selA = document.getElementById('refu-f-annee');
  if (selA) {
    const annees = [...new Set(tous.map(i => i.annee).filter(Boolean))].sort().reverse();
    selA.innerHTML = '<option value="">Toutes</option>' + annees.map(a =>
      `<option value="${a}"${a === REFU.f.annee ? ' selected' : ''}>${a}</option>`).join('');
  }
  const items = tous.filter(i => (!REFU.f.annee || i.annee === REFU.f.annee)
    && (!REFU.f.type || i.type === REFU.f.type) && (!REFU.f.source || i.source === REFU.f.source));
  if (REFU.sel && !tous.some(i => i.cle === REFU.sel)) REFU.sel = null;
  if (!REFU.sel) refuRendrePublication();          // v0.51.1
  const groupes = ['annee', 'type', 'source'].filter(k => !REFU.f[k]);
  const lib = (k, v) => k === 'annee' ? (v || 'Sans année') : ((_REFU_LIB[k] || {})[v] || v);
  const pastille = e => {
    const c = { utilise: '#276749', valide: '#276749', verrouille: '#3730a3' }[e] || '#976100';
    return `<span class="rxa-pastille" style="background:${c}"></span>`;
  };
  const ligne = i => `<div class="asm-item asm-item--clickable${i.cle === REFU.sel ? ' active' : ''}"
      onclick="refuChoisir('${i.cle}')">
      <div class="atl-item-id" style="display:flex;align-items:center;gap:6px">${pastille(i.etat)}<span>${_refuE(i.nom)}</span></div>
      ${i.desc ? `<div class="rxa-item-desc">${_refuE(i.desc)}</div>` : ''}</div>`;
  // Groupage récursif dans l'ordre année → type → source.
  const rendre = (lst, niv) => {
    if (niv >= groupes.length) return lst.map(ligne).join('');
    const k = groupes[niv];
    const vals = [...new Set(lst.map(i => i[k]))].sort((a, b) =>
      k === 'annee' ? String(b).localeCompare(String(a)) : String(a).localeCompare(String(b)));
    return vals.map(v => `<div class="refu-groupe refu-g${niv}">
        <div class="refu-groupe-titre">${_refuE(lib(k, v))}</div>
        ${rendre(lst.filter(i => i[k] === v), niv + 1)}</div>`).join('');
  };
  liste.innerHTML = items.length ? rendre(items, 0)
    : '<div style="padding:14px;font-size:12px;color:var(--text-muted)">Aucun référentiel pour ces critères.</div>';
  _refuRendreDetailExterne();
}

function refuChoisir(cle) {
  REFU.sel = cle;
  const [k, id] = [cle.slice(0, 1), cle.slice(2)];
  const ext = document.getElementById('refu-ext');
  if (k === 'I') {
    if (ext) ext.style.display = 'none';
    ATL_REF_SELECTION = (ATL_REF_LISTE || []).find(r => r.id === id) || null;
    if (typeof atelRefRendreDetail === 'function') atelRefRendreDetail();
  } else {
    ATL_REF_SELECTION = null;
    if (typeof atelRefRendreDetail === 'function') atelRefRendreDetail();
    const empty = document.getElementById('atl-ref-empty');
    if (empty) empty.style.display = 'none';
  }
  refuRendre();
  refuRendrePublication();
}

// v0.51.1 — Format d'échange : export JSON et vérification du référentiel
// choisi (structure figée seulement ; l'ancien modèle de MER n'est pas
// exportable). La vérification ne fige rien ; l'export d'un référentiel
// interne verrouillé conserve sa première publication (resservie ensuite).
function refuRendrePublication() {
  const z = document.getElementById('refu-publication');
  if (!z) return;
  if (!REFU.sel) { z.style.display = 'none'; z.innerHTML = ''; return; }
  const [k, id] = [REFU.sel.slice(0, 1), REFU.sel.slice(2)];
  z.style.display = '';
  if (k === 'A') {
    z.innerHTML = `<div class="refu-pub"><span class="refu-pub-titre">Format d'échange</span>
      <span class="refu-pub-info">Ancien modèle de MER : non exportable — à recréer dans la
      structure figée.</span></div>`;
    return;
  }
  const url = '/api/publication/referentiels/' + encodeURIComponent(id);
  z.innerHTML = `<div class="refu-pub"><span class="refu-pub-titre">Format d'échange</span>
    <a class="btn-sm" href="${url}.json" download>Exporter (JSON)</a>
    <button type="button" class="btn-sm" onclick="refuVerifierPublication()">Vérifier</button>
    <span id="refu-pub-res" class="refu-pub-info" role="status" aria-live="polite"></span></div>`;
}

async function refuVerifierPublication() {
  const res = document.getElementById('refu-pub-res');
  if (!REFU.sel || !res) return;
  const id = REFU.sel.slice(2);
  res.textContent = 'Vérification…';
  try {
    const r = await fetch('/api/publication/referentiels/' + encodeURIComponent(id)
      + '/verification');
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || 'Erreur');
    const b = d.bilan || {};
    if (!d.valide) {
      res.innerHTML = '<span class="refu-pub-ko">✗ Format invalide :</span> '
        + (d.erreurs || []).slice(0, 5).map(_refuE).join(' ; ');
      return;
    }
    const sans = b.documents_sans_fichier || [];
    res.innerHTML = '<span class="refu-pub-ok">✓ Format valide</span> — '
      + `${b.nb_sequences} séquence(s), ${b.nb_parties} partie(s), ${b.nb_documents} document(s)`
      + (sans.length ? ` — <span class="refu-pub-ko">${sans.length} sans fichier</span>`
        + ` (${sans.slice(0, 3).map(_refuE).join(', ')}${sans.length > 3 ? '…' : ''})` : '')
      + ` — empreinte <code>${_refuE(String(b.empreinte || '').slice(7, 15))}</code>`
      + (b.publication_figee ? ' — publication figée' : '');
  } catch (e) {
    res.textContent = e.message;
  }
}
window.refuVerifierPublication = refuVerifierPublication;

function _refuRendreDetailExterne() {
  const ext = document.getElementById('refu-ext');
  if (!ext) return;
  if (!REFU.sel || REFU.sel[0] === 'I') { ext.style.display = 'none'; return; }
  const [k, id] = [REFU.sel.slice(0, 1), REFU.sel.slice(2)];
  ext.style.display = '';
  if (k === 'E') {
    const r = RPE.liste.find(x => x.id === id);
    if (r) RPE.ouverts.add(id);
    ext.innerHTML = r ? `<div class="rxa-aide">Référentiel externe : séquences → parties → objectifs
      (connaissance, capacités ; critères F/A/E) ; documents par séquence, par partie, annuels.
      Une séquence commencée ne se modifie plus (libellés et ajout de documents seulement).</div>
      ${_rpeRef(r)}` : '';
  } else {
    const r = (RXT_LISTE || []).find(x => x.id === id);
    ext.innerHTML = (r && typeof rxtRenderRef === 'function') ? rxtRenderRef(r) : '';
  }
  const empty = document.getElementById('atl-ref-empty');
  if (empty) empty.style.display = 'none';
}

async function refuCreer() {
  const source = document.getElementById('refu-c-source').value;
  const type = document.getElementById('atl-ref-type').value;
  const desc = document.getElementById('refu-c-desc');
  const st = document.getElementById('refu-status');
  const niveau = (typeof ATL_FILTRE_NIVEAU !== 'undefined' && ATL_FILTRE_NIVEAU) || '';
  if (!niveau) { if (st) st.textContent = 'Choisissez d\'abord un niveau.'; return; }
  try {
    if (source === 'interne') {
      const r = await fetch('/api/referentiels/coquille', { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ niveau, description: desc.value, type_ref: type }) });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || 'Erreur');
      await atelRefRechargerListe();
      REFU.sel = 'I:' + ((d.ref && d.ref.id) || d.id);
    } else {
      const r = await _rpeApi(_RPE_API, { method: 'POST', body: JSON.stringify({
        niveau, annee: _rpeAnnee(), description: desc.value, type_ref: type }) });
      await rpeCharger();
      REFU.sel = 'E:' + r.id;
    }
    desc.value = '';
    if (st) st.textContent = 'Référentiel créé.';
    refuChoisir(REFU.sel);
  } catch (e) { if (st) st.textContent = e.message; }
}

// L'écran interne historique rafraîchit sa liste via atelRefRendreSidebar()
// (après création, suppression, changement d'état…) : dans l'onglet unique,
// c'est la liste commune qui est rendue.
atelRefRendreSidebar = function () { refuRendre(); };   // eslint-disable-line no-global-assign

// Ouverture de l'onglet : atelRefInit (chargement des internes) puis la vue
// unifiée.
(function () {
  const initInterne = window.atelRefInit;
  if (typeof initInterne !== 'function') return;
  window.atelRefInit = async function () {
    await initInterne();
    await refuInit();
  };
})();
