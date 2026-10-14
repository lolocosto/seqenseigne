// ============================================================================
// static/tdb_tuiles.js — v0.51.13
// Tuiles du tableau de bord de l'appli de classe :
//   - Journée : la journée sur le modèle de Planification hebdo (créneaux,
//     séances des classes, vacances / férié), flèches pour changer de jour,
//     lien vers Planification hebdo à la semaine du jour affiché ;
//   - Classes : classes de l'année (nom → liste des élèves, lien « plan » vers
//     le plan de classe) ;
//   - Établissements : salles connues (lien « plan » vers le plan de salle).
// Routes : /api/planification-hebdo, /api/tableau-bord/{classes,etablissements}.
// ============================================================================

const TDB_JOURS = ['lun', 'mar', 'mer', 'jeu', 'ven'];
const TDB_JOUR_NOM = { lun: 'Lundi', mar: 'Mardi', mer: 'Mercredi', jeu: 'Jeudi', ven: 'Vendredi' };
const TDB_TYPE_SEANCE = { principale: 'Cours', mer_auto: 'MER auto', mer_prog: 'MER prog' };
let TDB_JOUR = null;            // date ISO affichée
const TDB_SEMAINES = {};        // lundi ISO → données de la planification hebdo

function _tdbE(s) { return escapeHtml(String(s == null ? '' : s)); }

function _tdbIso(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
function _tdbDate(iso) {
  const [a, m, j] = iso.split('-').map(Number);
  return new Date(a, m - 1, j);
}
function _tdbDecaler(iso, n) {
  const d = _tdbDate(iso);
  d.setDate(d.getDate() + n);
  return _tdbIso(d);
}
// Jour ouvré : samedi et dimanche → lundi suivant (sens > 0) ou vendredi (sens < 0).
function _tdbOuvre(iso, sens) {
  let d = iso;
  while ([0, 6].includes(_tdbDate(d).getDay())) d = _tdbDecaler(d, sens >= 0 ? 1 : -1);
  return d;
}
function _tdbLundi(iso) {
  const j = (_tdbDate(iso).getDay() + 6) % 7;
  return _tdbDecaler(iso, -j);
}
function _tdbAnneeTuile() {
  return (typeof ANNEE_ACTIVE !== 'undefined' && ANNEE_ACTIVE)
    || (typeof anneeScolaireCourante === 'function' ? anneeScolaireCourante() : '');
}
function _tdbBornes() {
  const d0 = parseInt((_tdbAnneeTuile().split('-')[0] || ''), 10);
  return d0 ? { debut: `${d0}-09-01`, fin: `${d0 + 1}-07-31` } : null;
}

// ── Journée ─────────────────────────────────────────────────────────────────

async function tdbJour(delta) {
  if (delta === 0 || !TDB_JOUR) TDB_JOUR = _tdbOuvre(_tdbIso(new Date()), 1);
  else TDB_JOUR = _tdbOuvre(_tdbDecaler(TDB_JOUR, delta), delta);
  await tdbChargerJournee();
}

async function tdbChargerJournee() {
  const zone = document.getElementById('tdb-journee');
  if (!zone) return;
  if (!TDB_JOUR) TDB_JOUR = _tdbOuvre(_tdbIso(new Date()), 1);
  const lundi = _tdbLundi(TDB_JOUR);
  let d = TDB_SEMAINES[lundi];
  if (!d) {
    const p = new URLSearchParams({ annee: _tdbAnneeTuile(), lundi });
    const etab = (typeof SUIVI_ETAB_ACTIF !== 'undefined' && SUIVI_ETAB_ACTIF) || '';
    if (etab) p.set('etablissement_id', etab);
    try { d = await api('/api/planification-hebdo?' + p.toString()); }
    catch (e) { zone.innerHTML = '<p class="tdb-erreur">Erreur de chargement.</p>'; return; }
    TDB_SEMAINES[lundi] = d;
  }
  tdbRendreJournee(d);
}

function tdbRendreJournee(d) {
  const zone = document.getElementById('tdb-journee');
  const lbl = document.getElementById('tdb-jour-lbl');
  const iso = TDB_JOUR;
  const jour = TDB_JOURS[(_tdbDate(iso).getDay() + 6) % 7];
  const auj = _tdbIso(new Date()) === iso;
  if (lbl) lbl.textContent = `${TDB_JOUR_NOM[jour]} ${iso.slice(8, 10)}/${iso.slice(5, 7)}${auj ? ' — aujourd\'hui' : ''}`;
  const b = _tdbBornes();
  const prec = document.getElementById('tdb-jour-prec');
  const suiv = document.getElementById('tdb-jour-suiv');
  if (b && prec) prec.disabled = _tdbOuvre(_tdbDecaler(iso, -1), -1) < b.debut;
  if (b && suiv) suiv.disabled = _tdbOuvre(_tdbDecaler(iso, 1), 1) > b.fin;
  const info = (d.jours_info || []).find(j => j.date === iso) || {};
  if (info.vacances) {
    zone.innerHTML = `<p class="tdb-jour-vac">${_tdbE(info.vacances)}</p>`;
    return;
  }
  const cases = (d.cases || []).filter(c => c.date === iso);
  const ferie = info.ferie ? `<p class="tdb-jour-ferie">Férié : ${_tdbE(info.ferie)}</p>` : '';
  if (!cases.length) {
    zone.innerHTML = ferie || '<p class="tdb-vide">Aucune séance ce jour.</p>';
    return;
  }
  const parCreneau = {};
  cases.forEach(c => (parCreneau[c.creneau] = parCreneau[c.creneau] || []).push(c));
  // Créneaux de la grille, plus ceux d'un autre établissement absents de la grille.
  const creneaux = [...(d.creneaux || [])];
  Object.keys(parCreneau).forEach(c => { if (!creneaux.includes(c)) creneaux.push(c); });
  // Lignes vides avant la première et après la dernière séance : retirées.
  const occupes = creneaux.map(c => !!parCreneau[c]);
  const i0 = occupes.indexOf(true), i1 = occupes.lastIndexOf(true);
  const lignes = creneaux.slice(i0, i1 + 1).map(cr => {
    const pastilles = (parCreneau[cr] || []).map(c => {
      const coul = (typeof _edtCouleur === 'function') ? _edtCouleur(c.classe_id) : '#dbeafe';
      const type = c.type_mer !== 'principale' ? ` <span class="tdb-jour-type">${_tdbE(TDB_TYPE_SEANCE[c.type_mer] || '')}</span>` : '';
      const titre = `${c.classe} — ${TDB_TYPE_SEANCE[c.type_mer] || 'Cours'}${c.indispo ? ' — indisponible' : ''}`;
      return `<button type="button" class="tdb-jour-seance${c.indispo ? ' indispo' : ''}" style="background:${coul}"
        title="${_tdbE(titre)}" onclick="tdbOuvrirSeance('${_tdbE(c.classe_id)}','${c.date}','${_tdbE(c.creneau)}','${_tdbE(c.classe)}')">
        ${_tdbE(c.classe)}${type}${c.indispo ? ' ⛔' : ''}</button>`;
    }).join('');
    return `<div class="tdb-jour-ligne${pastilles ? '' : ' libre'}"><span class="tdb-jour-cr">${_tdbE(cr)}</span>
      <span class="tdb-jour-cases">${pastilles}</span></div>`;
  }).join('');
  zone.innerHTML = ferie + `<div class="tdb-jour">${lignes}</div>`;
}

// Détail d'une séance : celui de Planification hebdo (fenêtre ramenée au
// niveau de la page pour être visible depuis le tableau de bord).
function tdbOuvrirSeance(classeId, dateIso, creneau, classeNom) {
  const m = document.getElementById('planif-modale');
  if (m && m.parentElement !== document.body) document.body.appendChild(m);
  if (typeof planifOuvrirDetail === 'function') planifOuvrirDetail(classeId, dateIso, creneau, classeNom);
}

function tdbOuvrirPlanifHebdo() {
  const lundi = _tdbLundi(TDB_JOUR || _tdbOuvre(_tdbIso(new Date()), 1));
  const btn = document.querySelector('[data-tab="planification"]');
  if (btn) btn.click();
  if (typeof suiviSwitch === 'function') suiviSwitch('planif');
  setTimeout(() => {
    if (typeof planifCharger !== 'function') return;
    PLANIF_LUNDI = lundi;
    planifCharger();
  }, 0);
}

// ── Classes ─────────────────────────────────────────────────────────────────

async function tdbChargerClasses() {
  const zone = document.getElementById('tdb-classes');
  if (!zone) return;
  let d;
  try { d = await api('/api/tableau-bord/classes?annee=' + encodeURIComponent(_tdbAnneeTuile())); }
  catch (e) { zone.innerHTML = '<p class="tdb-erreur">Erreur de chargement.</p>'; return; }
  const an = document.getElementById('tdb-classes-annee');
  if (an) an.textContent = d.annee || '';
  const classes = d.classes || [];
  if (!classes.length) { zone.innerHTML = '<p class="tdb-vide">Aucune classe cette année.</p>'; return; }
  const parEtab = {};
  classes.forEach(c => (parEtab[c.etablissement] = parEtab[c.etablissement] || []).push(c));
  const plusieurs = Object.keys(parEtab).length > 1;
  zone.innerHTML = Object.entries(parEtab).map(([etab, cs]) => `
    ${plusieurs ? `<div class="tdb-groupe">${_tdbE(etab)}</div>` : ''}
    <ul class="tdb-liste">${cs.map(c => `<li>
      <a href="#" onclick="tdbOuvrirClasse('${_tdbE(c.id)}');return false" title="Liste des élèves">${_tdbE(c.nom)}</a>
      <span class="tdb-sous">${c.effectif} élève${c.effectif > 1 ? 's' : ''}</span>
      ${c.plan ? `<a href="#" class="tdb-plan" onclick="tdbOuvrirPlanClasse('${_tdbE(c.id)}','${_tdbE(c.etablissement_id)}');return false">plan</a>` : ''}
    </li>`).join('')}</ul>`).join('');
}

function tdbOuvrirClasse(cid) {
  const btn = document.querySelector('[data-tab="parametrage"]');
  if (btn) btn.click();
  if (typeof suiviSwitch === 'function') suiviSwitch('classe');
  setTimeout(async () => {
    if (typeof showDetailClasse !== 'function') return;
    if (!(CLASSES_TOUTES || []).some(c => c.id === cid) && !(CLASSES || []).some(c => c.id === cid)) {
      try { CLASSES_TOUTES = (await api('/api/classes')).classes || []; } catch (e) {}
    }
    showDetailClasse(cid);
  }, 0);
}

function tdbOuvrirPlanClasse(cid, etabId) {
  if (etabId) {
    SUIVI_ETAB_ACTIF = etabId;
    try { localStorage.setItem('suivi-etab-actif', etabId); } catch (e) {}
  }
  try { localStorage.setItem('pc-classe', cid); } catch (e) {}
  if (typeof PC !== 'undefined') { PC.classeId = cid; PC.lundi = null; }
  const btn = document.querySelector('[data-tab="planification"]');
  if (btn) btn.click();
  if (typeof suiviSwitch === 'function') suiviSwitch('plans');
}

// ── Établissements ──────────────────────────────────────────────────────────

async function tdbChargerEtabs() {
  const zone = document.getElementById('tdb-etabs');
  if (!zone) return;
  let d;
  try { d = await api('/api/tableau-bord/etablissements'); }
  catch (e) { zone.innerHTML = '<p class="tdb-erreur">Erreur de chargement.</p>'; return; }
  const etabs = d.etablissements || [];
  if (!etabs.length) { zone.innerHTML = '<p class="tdb-vide">Aucun établissement.</p>'; return; }
  zone.innerHTML = etabs.map(e => `
    <div class="tdb-groupe">${_tdbE(e.nom)}</div>
    ${e.salles.length ? `<ul class="tdb-liste">${e.salles.map(s => `<li>${_tdbE(s.nom)}
      ${s.plan ? `<a href="#" class="tdb-plan" onclick="tdbOuvrirPlanSalle('${_tdbE(e.id)}','${_tdbE(s.id)}');return false">plan</a>` : ''}
    </li>`).join('')}</ul>` : '<p class="tdb-vide">Aucune salle connue.</p>'}`).join('');
}

function tdbOuvrirPlanSalle(etabId, salleId) {
  if (typeof salleEditeurOuvrir === 'function') salleEditeurOuvrir(etabId, salleId);
}

window.tdbJour = tdbJour;
window.tdbChargerJournee = tdbChargerJournee;
window.tdbOuvrirSeance = tdbOuvrirSeance;
window.tdbOuvrirPlanifHebdo = tdbOuvrirPlanifHebdo;
window.tdbChargerClasses = tdbChargerClasses;
window.tdbOuvrirClasse = tdbOuvrirClasse;
window.tdbOuvrirPlanClasse = tdbOuvrirPlanClasse;
window.tdbChargerEtabs = tdbChargerEtabs;
window.tdbOuvrirPlanSalle = tdbOuvrirPlanSalle;
