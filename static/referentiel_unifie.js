// ============================================================================
// static/referentiel_unifie.js — v0.49.2 (v0.51.1 : format d'échange)
// Conception › Niveau › « Référentiel » : UN SEUL onglet pour tous les
// référentiels du niveau de la portée — internes et externes, principaux et
// MER (v0.51.11 : ancien modèle de MER retiré).
//   - liste à gauche : filtres Année, Type, Source ; pour chaque filtre sans
//     valeur choisie, groupage dans cet ordre (année, puis type, puis source) ;
//   - création : source (interne / externe), type (principal / MER),
//     description ; nom calculé ;
//   - détail à droite : interne → détail historique (static/
//     atelier_referentiel.js) ; externe → éditeur commun (static/
//     referentiel_pe.js).
//   - v0.51.6 : structure de départ d'un référentiel externe (programme du
//     cycle, référentiels existants du même type) avec aperçu dépliable.
// ============================================================================

const REFU = { f: { annee: '', type: '', source: '' }, sel: null, actif: false,
  modeles: [], apercu: null };

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
  return items;
}

async function refuInit() {
  REFU.actif = true;
  // Données : internes (déjà chargés par atelRefInit), externes (structure
  // figée).
  if (typeof rpeCharger === 'function') await rpeCharger();
  await refuChargerModeles();
  refuRendre();
}

// ── v0.51.6 — Structures modèles ────────────────────────────────────────────

async function refuChargerModeles() {
  const sel = document.getElementById('refu-c-modele');
  if (!sel) return;
  const source = (document.getElementById('refu-c-source') || {}).value;
  const type = (document.getElementById('atl-ref-type') || {}).value || 'principal';
  const niveau = (typeof ATL_FILTRE_NIVEAU !== 'undefined' && ATL_FILTRE_NIVEAU) || '';
  sel.style.display = source === 'externe' ? '' : 'none';
  REFU.modeles = [];
  if (source === 'externe' && niveau) {
    try {
      REFU.modeles = (await _rpeApi(`${_RPE_API}/modeles?niveau=${encodeURIComponent(niveau)}`
        + `&type=${encodeURIComponent(type)}`)).modeles || [];
    } catch (e) { REFU.modeles = []; }
  }
  sel.innerHTML = '<option value="">Structure vide</option>' + REFU.modeles.map(m =>
    `<option value="${_refuE(m.cle)}">${_refuE(m.nom)}${m.description ? ' — ' + _refuE(m.description) : ''}</option>`).join('');
  if (REFU.apercu) { REFU.apercu = null; _refuRendreDetailExterne(); }
}

function refuApercuModele(cle) {
  REFU.apercu = cle || null;
  _refuRendreDetailExterne();
}

function _refuArbre(m) {
  const themes = m.themes || [];
  const seqs = m.sequences || [];
  const n = (x) => String(+x || 0).replace('.', ',');
  const seq = (s) => {
    const parties = s.parties || [];
    const duree = parties.reduce((a, p) => a + (p.objectifs || []).reduce((b, o) => b + (+o.nb_seances || 0), 0), 0);
    return `<details class="refu-arbre-seq"><summary>${_refuE(s.nom)}
        <span class="rx-petit">${parties.length} partie(s) · ${n(duree)} séance(s)</span></summary>
      ${parties.map((p, i) => `<div class="refu-arbre-partie">P${i + 1}${p.libelle ? ' · ' + _refuE(p.libelle) : ''}
          <span class="rx-petit">${n((p.objectifs || []).reduce((b, o) => b + (+o.nb_seances || 0), 0))} séance(s)</span>
        <ul>${(p.objectifs || []).map(o => `<li><span class="rpe-badge">${o.type === 'connaissance' ? 'connaissance' : 'capacité'}</span>
          ${_refuE(o.nom)} <span class="rx-petit">${n(o.nb_seances)} séance(s)</span></li>`).join('')}</ul></div>`).join('')}
    </details>`;
  };
  const groupes = themes.map(t => ({ t, ss: seqs.filter(s => s.theme === t.code) }));
  const sans = seqs.filter(s => !themes.some(t => t.code === s.theme));
  if (sans.length) groupes.push({ t: null, ss: sans });
  return groupes.map(({ t, ss }) => `<details class="refu-arbre-theme" open
      ${t && typeof _rpeCouleur === 'function' ? `style="--theme:${_rpeCouleur(t.couleur)}"` : ''}>
    <summary>${t ? `Thème ${_refuE(t.code)} — ${_refuE(t.nom)}` : 'Sans thème'}
      <span class="rx-petit">${ss.length} séquence(s)</span></summary>
    ${ss.map(seq).join('') || '<div class="rpe-vide">Aucune séquence.</div>'}</details>`).join('');
}

function _refuRendreApercu(ext) {
  const m = REFU.modeles.find(x => x.cle === REFU.apercu);
  if (!m) { REFU.apercu = null; return false; }
  ext.style.display = '';
  ext.innerHTML = `<div class="card refu-apercu">
    <div class="rpe-ref-tete"><strong>Aperçu : ${_refuE(m.nom)}</strong>
      <span class="rx-petit">${_refuE(m.resume)}</span></div>
    <div class="rxa-aide">Créer recopie cette structure (thèmes, séquences, parties, objectifs avec
      critères et séances) dans un nouveau référentiel externe en conception, sans les documents ;
      vous pourrez ensuite tout modifier. Choisissez « Structure vide » pour partir de rien.</div>
    ${_refuArbre(m.modele)}
    <div class="rx-ajout"><button class="btn-prim" onclick="refuCreer()">+ Créer à partir de ce modèle</button></div>
  </div>`;
  const empty = document.getElementById('atl-ref-empty');
  if (empty) empty.style.display = 'none';
  return true;
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
  REFU.apercu = null;                                          // v0.51.6
  const mod = document.getElementById('refu-c-modele');
  if (mod) mod.value = '';
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
      + (b.publication_figee ? ' — publication figée' : '')
      // v0.51.2 — documents compilés sans PDF (non publiés), écarts de durée.
      + ((b.documents_sans_pdf || []).length
        ? `<br>${b.documents_sans_pdf.length} document(s) compilé(s) sans PDF, non publié(s)`
          + ` (${b.documents_sans_pdf.slice(0, 3).map(_refuE).join(', ')}`
          + `${b.documents_sans_pdf.length > 3 ? '…' : ''})` : '')
      + ((b.parties_ecart || []).length
        ? `<br><span class="refu-pub-ko">${b.parties_ecart.length} partie(s) dont la durée`
          + ` saisie diffère de la somme des objectifs</span> (la durée publiée est la somme) :`
          + ` ${b.parties_ecart.slice(0, 4).map(_refuE).join(' ; ')}`
          + `${b.parties_ecart.length > 4 ? '…' : ''}` : '');
  } catch (e) {
    res.textContent = e.message;
  }
}
window.refuVerifierPublication = refuVerifierPublication;
window.refuChargerModeles = refuChargerModeles;
window.refuApercuModele = refuApercuModele;

function _refuRendreDetailExterne() {
  const ext = document.getElementById('refu-ext');
  if (!ext) return;
  if (REFU.apercu && _refuRendreApercu(ext)) return;          // v0.51.6
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
      const modele = (document.getElementById('refu-c-modele') || {}).value || '';
      const r = await _rpeApi(_RPE_API, { method: 'POST', body: JSON.stringify({
        niveau, annee: _rpeAnnee(), description: desc.value, type_ref: type, modele }) });
      await rpeCharger();
      await refuChargerModeles();
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
