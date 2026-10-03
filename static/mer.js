// ============================================================================
// static/mer.js — v0.24.1
// Sous-onglet « Mises en route » (Suivi annuel). Utilise les sélecteurs
// GLOBAUX du Suivi : année (ANNEE_ACTIVE), établissement (SUIVI_ETAB_ACTIF) et
// classe (classe-sel). Deux zones : config MER par classe + planning des
// automatismes (PDF A3 affiché en ligne).
// ============================================================================

let MER_CLASSES = [];

function _merAnnee() {
  return (typeof ANNEE_ACTIVE !== 'undefined' && ANNEE_ACTIVE)
    || (typeof anneeScolaireCourante === 'function' ? anneeScolaireCourante() : '');
}
function _merEtab() {
  return (typeof SUIVI_ETAB_ACTIF !== 'undefined' && SUIVI_ETAB_ACTIF) || '';
}
function _merClasseSel() {
  const el = document.getElementById('classe-sel');
  return el ? el.value : '';
}

async function merInit() {
  await merChargerClasses();
}

async function merChargerClasses() {
  const annee = _merAnnee();
  const etabId = _merEtab();
  try {
    const r = await api('/api/classes?annee=' + encodeURIComponent(annee));
    const classes = (r && (r.classes || r)) || [];
    MER_CLASSES = classes.filter(c =>
      !etabId || c.etablissement === etabId || c.etablissement_id === etabId);
  } catch (e) { MER_CLASSES = []; }
  merRenderClasses();
  merAfficherPlanning();
  merChargerAffectation();
}

// ── Affectation des séances MER sur l'EdT de la classe sélectionnée ──────────

let MER_AFF_GRILLE = [];
let MER_AFF_EDT = [];
let MER_AFF = {};
const MER_AFF_JOURS = ['lun', 'mar', 'mer', 'jeu', 'ven'];
const MER_AFF_JOUR_LBL = { lun: 'Lundi', mar: 'Mardi', mer: 'Mercredi', jeu: 'Jeudi', ven: 'Vendredi' };

function _merAffTypes(mode) {
  if (mode === 'progression') return ['progression', 'aucun'];
  if (mode === 'panache') return ['automatisme', 'progression', 'aucun'];
  return ['automatisme', 'aucun'];
}
const MER_AFF_LBL = { automatisme: 'Auto', progression: 'Prog', aucun: '—' };
const MER_AFF_COUL = { automatisme: '#cfe3ff', progression: '#d8f0d8', aucun: '#eee' };

async function merChargerAffectation() {
  const card = document.getElementById('mer-affect-card');
  const cid = _merClasseSel();
  const c = MER_CLASSES.find(x => x.id === cid);
  if (!card) return;
  if (!cid || !c || !c.mer_active) { card.style.display = 'none'; return; }
  card.style.display = '';
  const annee = _merAnnee();
  const etabId = _merEtab();
  try {
    const [rg, re, ra] = await Promise.all([
      api('/api/etablissements/' + etabId + '/grille-horaire'),
      api('/api/edt?annee=' + encodeURIComponent(annee)),

    ]);
    MER_AFF_GRILLE = (rg && rg.creneaux) || [];
    MER_AFF_EDT = ((re && re.creneaux) || []).filter(x =>
      x.classe_id === cid && x.groupe === 'classe_entiere' && x.usage === 'cours');
    MER_AFF = (ra && ra.affectations) || {};
  } catch (e) { MER_AFF_GRILLE = []; MER_AFF_EDT = []; MER_AFF = {}; }
  const info = document.getElementById('mer-affect-info');
  if (info) info.textContent = c.nom + ' · mode ' + (c.mer_mode || 'automatismes');
  // v0.43.2 — Début effectif des mises en route.
  try {
    const cfg = await api('/api/classes/' + cid + '/affectation-config?annee=' + encodeURIComponent(annee));
    const inp = document.getElementById('mer-date-debut');
    if (inp) inp.value = (cfg && cfg.date_debut) || '';
  } catch (e) {}
  merRenderAffectation(c.mer_mode || 'automatismes');
}

function _merAffType(edtId, mode) {
  if (MER_AFF[edtId]) return MER_AFF[edtId];
  return mode === 'panache' ? 'aucun'
    : (mode === 'progression' ? 'progression' : 'automatisme');
}

function merRenderAffectation(mode) {
  const zone = document.getElementById('mer-affect-grille');
  if (!zone) return;
  if (!MER_AFF_GRILLE.length) {
    zone.innerHTML = '<p style="font-size:13px;color:#999">Aucun créneau dans la grille horaire.</p>';
    return;
  }
  // Index par (jour, code) → {AB, A, B} (cases de la classe pour ce créneau).
  const parCase = {};
  MER_AFF_EDT.forEach(x => {
    const k = x.jour + '_' + x.creneau_code;
    (parCase[k] = parCase[k] || {})[x.semaine || 'AB'] = x;
  });

  // Bouton d'affectation d'une case (pleine ou demi), largeur w, marqueur A/B.
  const boutonCase = (edtCase, w, demi) => {
    const typ = _merAffType(edtCase.id, mode);
    const sep = demi === 'A' ? 'border-right:1px dashed #bbb;' : '';
    const marq = demi ? `<span style="position:absolute;top:1px;left:2px;font-size:8px;color:#666;font-weight:bold">${demi}</span>` : '';
    return `<button style="width:${w};height:100%;border:0;${sep}cursor:pointer;
      font-size:11px;position:relative;background:${MER_AFF_COUL[typ]}"
      onclick="merCyclerAffectation('${edtCase.id}','${mode}')"
      aria-label="Type de MER, semaine ${demi || 'AB'}">${marq}${MER_AFF_LBL[typ]}</button>`;
  };

  const entete = '<th style="width:64px"></th>' + MER_AFF_JOURS.map(j =>
    `<th style="padding:4px;font-size:12px;background:#f5f5f5;border:1px solid var(--border)">${MER_AFF_JOUR_LBL[j]}</th>`).join('');
  const lignes = MER_AFF_GRILLE.map(cr => {
    const label = `<th style="padding:2px 6px;font-size:11px;text-align:right;background:#f5f5f5;border:1px solid var(--border);white-space:nowrap">${escapeHtml(cr.code)}</th>`;
    const cells = MER_AFF_JOURS.map(j => {
      const cases = parCase[j + '_' + cr.code];
      if (!cases) {
        return `<td style="border:1px solid var(--border);height:40px;background:#fafafa"></td>`;
      }
      let inner;
      if (cases.AB) {
        inner = boutonCase(cases.AB, '100%', '');
      } else if (cases.A || cases.B) {
        // Demi-largeur : A à gauche, B à droite (comme l'EdT enseignant).
        const gauche = cases.A ? boutonCase(cases.A, '50%', 'A')
          : `<span style="width:50%;display:inline-block;border-right:1px dashed #bbb"></span>`;
        const droite = cases.B ? boutonCase(cases.B, '50%', 'B')
          : `<span style="width:50%;display:inline-block"></span>`;
        inner = `<div style="display:flex;width:100%;height:100%">${gauche}${droite}</div>`;
      } else {
        inner = '';
      }
      return `<td style="border:1px solid var(--border);height:40px;padding:0">${inner}</td>`;
    }).join('');
    return `<tr>${label}${cells}</tr>`;
  }).join('');

  const types = _merAffTypes(mode);
  const legende = types.map(t =>
    `<span style="display:inline-flex;align-items:center;gap:4px;font-size:11px;margin-right:10px">
      <span style="width:14px;height:14px;background:${MER_AFF_COUL[t]};border:1px solid #ccc;border-radius:2px"></span>
      ${MER_AFF_LBL[t]}${t === 'aucun' ? ' (aucune MER)' : ''}</span>`).join('');
  zone.innerHTML = `<div style="margin-bottom:6px">${legende}</div>`
    + `<table style="border-collapse:collapse;width:100%;table-layout:fixed">`
    + `<thead><tr>${entete}</tr></thead><tbody>${lignes}</tbody></table>`;
}

async function merCyclerAffectation(edtId, mode) {
  const types = _merAffTypes(mode);
  const cour = _merAffType(edtId, mode);
  const suivant = types[(types.indexOf(cour) + 1) % types.length];
  const defaut = mode === 'panache' ? 'aucun'
    : (mode === 'progression' ? 'progression' : 'automatisme');
  if (suivant === defaut) delete MER_AFF[edtId];
  else MER_AFF[edtId] = suivant;
  merRenderAffectation(mode);
  try {
    await fetch('/api/classes/' + _merClasseSel() + '/affectations', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ annee: _merAnnee(),
        items: [{ edt_creneau_id: edtId, affectation: suivant }] }),
    });
  } catch (e) {}
  merAfficherPlanning();
}

function merRenderClasses() {
  const zone = document.getElementById('mer-classes-liste');
  if (!zone) return;
  if (!MER_CLASSES.length) {
    zone.innerHTML = '<p style="font-size:13px;color:#999">Aucune classe pour '
      + 'cet établissement / cette année.</p>';
    return;
  }
  const lignes = MER_CLASSES.map(c => {
    const active = !!c.mer_active;
    const mode = c.mer_mode || 'automatismes';
    return `<tr style="border-bottom:1px solid var(--border)">
      <td style="padding:5px 10px;font-size:13px;font-weight:500">${escapeHtml(c.nom)}</td>
      <td style="padding:5px 10px;font-size:12px;color:#888">${escapeHtml(c.niveau || '')}</td>
      <td style="padding:5px 10px">
        <label style="font-size:13px;display:flex;align-items:center;gap:6px">
          <input type="checkbox" ${active ? 'checked' : ''}
                 onchange="merToggleActive('${c.id}', this.checked)"
                 aria-label="La classe ${escapeHtml(c.nom)} fait des mises en route">
          fait des MER
        </label>
      </td>
      <td style="padding:5px 10px">
        <select ${active ? '' : 'disabled'} style="font-size:13px"
                onchange="merSetMode('${c.id}', this.value)"
                aria-label="Mode de mise en route de ${escapeHtml(c.nom)}">
          <option value="automatismes"${mode === 'automatismes' ? ' selected' : ''}>Automatismes (Leitner)</option>
          <option value="progression"${mode === 'progression' ? ' selected' : ''}>Progression</option>
          <option value="panache"${mode === 'panache' ? ' selected' : ''}>Panaché</option>
        </select>
      </td>
    </tr>`;
  }).join('');
  zone.innerHTML = `<table style="border-collapse:collapse;width:100%">
    <thead><tr style="text-align:left;color:#666;font-size:12px">
      <th style="padding:5px 10px">Classe</th><th style="padding:5px 10px">Niveau</th>
      <th style="padding:5px 10px">Mises en route</th><th style="padding:5px 10px">Mode</th>
    </tr></thead><tbody>${lignes}</tbody></table>`;
}

async function _merMaj(classeId, champs) {
  try {
    const c = await api('/api/classes/' + classeId,
      { method: 'PUT', body: JSON.stringify(champs) });
    const x = MER_CLASSES.find(y => y.id === classeId);
    if (x) { x.mer_active = c.mer_active; x.mer_mode = c.mer_mode; }
    return true;
  } catch (e) { return false; }
}

async function merToggleActive(classeId, actif) {
  await _merMaj(classeId, { mer_active: actif ? 1 : 0 });
  merRenderClasses();
  merAfficherPlanning();
}

async function merSetMode(classeId, mode) {
  await _merMaj(classeId, { mer_mode: mode });
  merRenderClasses();
  merAfficherPlanning();
}

// Affiche le(s) planning(s) de la classe selon son mode MER : automatismes →
// planning auto ; progression → planning MER ; panaché → les deux ; sinon rien.
function merAfficherPlanning() {
  const cid = _merClasseSel();
  const c = MER_CLASSES.find(x => x.id === cid);
  const cardAuto = document.getElementById('mer-auto-card');
  const cardProg = document.getElementById('mer-plan-prog-card');
  const mode = (c && c.mer_active) ? (c.mer_mode || 'automatismes') : null;
  const montreAuto = mode === 'automatismes' || mode === 'panache';
  const montreProg = mode === 'progression' || mode === 'panache';
  if (cardAuto) cardAuto.style.display = montreAuto ? '' : 'none';
  if (cardProg) cardProg.style.display = montreProg ? '' : 'none';
  if (montreAuto) _merFramePlanning(
    'mer-planning-zone', 'mer-planning-info', 'mer-planning-dl',
    '/api/classes/' + cid + '/planning-automatismes.pdf', c);
  if (montreProg) _merFramePlanning(
    'mer-plan-prog-zone', 'mer-plan-prog-info', 'mer-plan-prog-dl',
    '/api/classes/' + cid + '/planning-mer.pdf', c);
}

function _merFramePlanning(zoneId, infoId, dlId, urlBase, c) {
  const zone = document.getElementById(zoneId);
  const info = document.getElementById(infoId);
  const dl = document.getElementById(dlId);
  if (!zone) return;
  const url = urlBase + '?annee=' + encodeURIComponent(_merAnnee());
  if (info) info.textContent = c ? c.nom : '';
  const fid = zoneId + '-frame';
  zone.innerHTML = `<iframe id="${fid}" title="Planning de ${escapeHtml(c ? c.nom : '')}"
    style="width:100%;height:70vh;border:0;border-radius:6px"></iframe>`;
  afficherPdfDansAppli(document.getElementById(fid), url);
  if (dl) { dl.href = url; dl.style.display = ''; }
}


// v0.43.2 — Début effectif des mises en route (vide = dès la rentrée).
async function merDefinirDateDebut(valeur) {
  const cid = _merClasseSel();
  if (!cid) return;
  try {
    const r = await fetch('/api/classes/' + cid + '/affectation-config', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ annee: _merAnnee(), date_debut: valeur || '' }) });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || 'Erreur');
    const inp = document.getElementById('mer-date-debut');
    if (inp) inp.value = d.date_debut || '';
    if (typeof merAfficherPlanning === 'function') merAfficherPlanning();
  } catch (e) { alert(e.message); }
}
