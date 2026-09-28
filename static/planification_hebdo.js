// ============================================================================
// static/planification_hebdo.js — v0.32.0
// Vue « Planification hebdo » (Suivi annuel) : une semaine calendaire, toutes
// classes, façon EdT. Survol = aperçu ; clic = détail (séquence, MER).
// ============================================================================

let PLANIF_LUNDI = null;      // lundi ISO de la semaine affichée
let PLANIF_DATA = null;

const PLANIF_JOURS = ['lun', 'mar', 'mer', 'jeu', 'ven'];
const PLANIF_JOUR_LBL = { lun: 'Lundi', mar: 'Mardi', mer: 'Mercredi', jeu: 'Jeudi', ven: 'Vendredi' };
const PLANIF_MER_LBL = { principale: 'Cours', mer_auto: 'MER auto', mer_prog: 'MER prog' };

function _planifAnnee() {
  return (typeof ANNEE_ACTIVE !== 'undefined' && ANNEE_ACTIVE)
    || (typeof anneeScolaireCourante === 'function' ? anneeScolaireCourante() : '');
}
function _planifEtab() {
  return (typeof SUIVI_ETAB_ACTIF !== 'undefined' && SUIVI_ETAB_ACTIF) || '';
}
function _planifDateFr(iso) {
  const m = String(iso || '').match(/^\d{4}-(\d{2})-(\d{2})/);
  return m ? `${m[2]}/${m[1]}` : iso;
}

async function planifInit() {
  PLANIF_LUNDI = null;  // semaine courante
  await planifCharger();
}

// v0.32.1 — Ajoute `nbJours` à une date ISO (aaaa-mm-jj) sans effet de fuseau
// horaire (calcul en UTC : Date locale + toISOString décalait d'un jour).
function _planifAjouterJours(iso, nbJours) {
  const [a, m, j] = iso.split('-').map(Number);
  const d = new Date(Date.UTC(a, m - 1, j));
  d.setUTCDate(d.getUTCDate() + nbJours);
  return d.toISOString().slice(0, 10);
}

// delta : -1 semaine, +1 semaine, 0 = revenir à la semaine courante.
async function planifSemaine(delta) {
  if (delta === 0) {
    PLANIF_LUNDI = null;
  } else {
    const base = PLANIF_LUNDI || (PLANIF_DATA && PLANIF_DATA.lundi);
    if (base) PLANIF_LUNDI = _planifAjouterJours(base, 7 * delta);
  }
  await planifCharger();
}

async function planifCharger() {
  const zone = document.getElementById('planif-grille');
  if (!zone) return;
  const params = new URLSearchParams({ annee: _planifAnnee() });
  if (PLANIF_LUNDI) params.set('lundi', PLANIF_LUNDI);
  if (_planifEtab()) params.set('etablissement_id', _planifEtab());
  try {
    PLANIF_DATA = await api('/api/planification-hebdo?' + params.toString());
    PLANIF_LUNDI = PLANIF_DATA.lundi;
  } catch (e) {
    zone.innerHTML = '<p style="font-size:13px;color:#c33">Erreur de chargement.</p>';
    return;
  }
  planifRendreGrille();
}

function planifRendreGrille() {
  const zone = document.getElementById('planif-grille');
  const lbl = document.getElementById('planif-semaine-lbl');
  if (!zone || !PLANIF_DATA) return;
  if (lbl) lbl.textContent = `Semaine du ${_planifDateFr(PLANIF_DATA.lundi)} au ${_planifDateFr(PLANIF_DATA.vendredi)}`;

  // v0.32.3 — Borner la navigation à l'année scolaire (1er sept → 31 juillet).
  // Désactive « précédente » si la semaine précédente sort avant le début,
  // « suivante » si la semaine suivante sort après la fin.
  _planifMajBornes();

  // Index des cases par (jour, créneau).
  const parCase = {};
  (PLANIF_DATA.cases || []).forEach(c => {
    const k = c.jour + '_' + c.creneau;
    (parCase[k] = parCase[k] || []).push(c);
  });
  const creneaux = PLANIF_DATA.creneaux || [];

  // v0.32.3 — Info vacances/férié par jour (pour griser les colonnes).
  const infoParJour = {};
  (PLANIF_DATA.jours_info || []).forEach(ji => { infoParJour[ji.jour] = ji; });

  const entete = '<th style="width:56px"></th>' + PLANIF_JOURS.map((j, i) => {
    const ji = infoParJour[j] || {};
    const vac = ji.vacances ? `<br><span style="font-size:9px;color:#c0392b;font-weight:normal">${escapeHtml(ji.vacances)}</span>` : '';
    const ferie = (!ji.vacances && ji.ferie) ? `<br><span style="font-size:9px;color:#c60;font-weight:normal">${escapeHtml(ji.ferie)}</span>` : '';
    const bg = ji.vacances ? '#fdecea' : (ji.ferie ? '#fff6e5' : '#f5f5f5');
    return `<th style="padding:4px;font-size:12px;background:${bg};border:1px solid var(--border)">
      ${PLANIF_JOUR_LBL[j]}<br><span style="font-weight:normal;color:#999">${_planifDateFr(PLANIF_DATA.jours[i])}</span>${vac}${ferie}</th>`;
  }).join('');

  const lignes = creneaux.map(cr => {
    const label = `<th style="padding:2px 6px;font-size:11px;text-align:right;background:#f5f5f5;border:1px solid var(--border)">${escapeHtml(cr)}</th>`;
    const cells = PLANIF_JOURS.map(j => {
      const ji = infoParJour[j] || {};
      // Jour en vacances : colonne grisée, pas de séances affichées.
      if (ji.vacances) {
        return `<td style="border:1px solid var(--border);height:52px;background:#fdecea"></td>`;
      }
      const fondFerie = ji.ferie ? 'background:#fff6e5;' : '';
      const cases = parCase[j + '_' + cr] || [];
      if (!cases.length) {
        return `<td style="border:1px solid var(--border);height:52px;${fondFerie || 'background:#fafafa'}"></td>`;
      }
      const pastilles = cases.map(c => {
        const coul = (typeof _edtCouleur === 'function') ? _edtCouleur(c.classe_id) : '#dbeafe';
        const barre = c.indispo ? 'text-decoration:line-through;opacity:.6' : '';
        const merTag = c.type_mer !== 'principale'
          ? `<span style="font-size:9px;color:#555"> ${PLANIF_MER_LBL[c.type_mer] || ''}</span>` : '';
        // Survol enrichi : classe + type MER (+ indispo).
        const apercu = `${c.classe} — ${PLANIF_MER_LBL[c.type_mer] || 'Cours'}`
          + (c.indispo ? ' — indisponible' : '');
        return `<div onclick="planifOuvrirDetail('${c.classe_id}','${c.date}','${escapeHtml(c.creneau)}','${escapeHtml(c.classe)}')"
          title="${escapeHtml(apercu)}"
          style="cursor:pointer;background:${coul};border-radius:3px;padding:1px 5px;margin:1px 0;font-size:11px;${barre}">
          ${escapeHtml(c.classe)}${merTag}${c.indispo ? ' ⛔' : ''}</div>`;
      }).join('');
      return `<td style="border:1px solid var(--border);height:52px;padding:2px;vertical-align:top;${fondFerie}">${pastilles}</td>`;
    }).join('');
    return `<tr>${label}${cells}</tr>`;
  }).join('');

  zone.innerHTML = `<table style="border-collapse:collapse;width:100%;min-width:640px;table-layout:fixed">
    <thead><tr>${entete}</tr></thead><tbody>${lignes}</tbody></table>`;
}

async function planifOuvrirDetail(classeId, dateIso, creneau, classeNom) {
  const modale = document.getElementById('planif-modale');
  const titre = document.getElementById('planif-modale-titre');
  const corps = document.getElementById('planif-modale-corps');
  if (!modale) return;
  if (titre) titre.textContent = `${classeNom} — ${PLANIF_JOUR_LBL[_planifJourDe(dateIso)] || ''} ${_planifDateFr(dateIso)} · ${creneau}`;
  if (corps) corps.innerHTML = '<p style="color:#999">Chargement…</p>';
  modale.style.display = 'flex';
  try {
    const params = new URLSearchParams({ annee: _planifAnnee(), classe_id: classeId, date: dateIso, creneau });
    const d = await api('/api/planification-hebdo/seance?' + params.toString());
    // Bloc MER
    let merHtml = '';
    if (d.mer_type === 'mer_auto') {
      const env = (d.mer_enveloppes || []).length
        ? (d.mer_enveloppes || []).map(e => `enveloppe ${e}`).join(', ')
        : 'aucune';
      merHtml = `<div style="margin-bottom:8px"><strong>MER</strong> automatismes :
        <span style="color:#333">${escapeHtml(env)}</span></div>`;
    } else if (d.mer_type === 'mer_prog') {
      merHtml = `<div style="margin-bottom:8px"><strong>MER</strong> progression</div>`;
    }
    // Bloc principal
    let principalHtml;
    if (d.sequence_code) {
      const nom = d.sequence_nom ? ` — ${escapeHtml(d.sequence_nom)}` : '';
      const partie = d.partie ? ` · ${escapeHtml(d.partie)}` : '';
      const rang = (d.rang_dans_partie && d.nb_partie)
        ? ` · séance ${d.rang_dans_partie}/${d.nb_partie}` : '';
      principalHtml = `<div><strong>Principal</strong> :
        ${escapeHtml(d.sequence_code)}${nom}${partie}${rang}</div>`;
    } else {
      principalHtml = `<div><strong>Principal</strong> :
        <span style="color:#999">séquence non datée / aucune</span></div>`;
    }
    // Documents à distribuer (associés à ce créneau + rang de séance).
    let docsHtml = '';
    const docs = d.docs_a_distribuer || [];
    if (docs.length) {
      docsHtml = `<div style="margin-top:12px"><strong>Documents à distribuer</strong> :
        <ul style="margin:4px 0 0;padding-left:18px">`
        + docs.map(x => `<li>${escapeHtml(x.libelle)}</li>`).join('')
        + `</ul></div>`;
    } else {
      docsHtml = `<p style="font-size:12px;color:#999;margin-top:12px">
        Aucun document prévu pour cette séance.</p>`;
    }
    corps.innerHTML = merHtml + principalHtml + docsHtml;
  } catch (e) {
    corps.innerHTML = '<p style="color:#c33">Erreur de chargement.</p>';
  }
}

function planifFermerModale() {
  const modale = document.getElementById('planif-modale');
  if (modale) modale.style.display = 'none';
}

function _planifJourDe(iso) {
  const d = new Date(iso + 'T00:00:00');
  return PLANIF_JOURS[(d.getDay() + 6) % 7] || '';
}

// v0.32.3 — Bornes de l'année scolaire et désactivation des boutons.
function _planifBornesAnnee() {
  const a = _planifAnnee();               // "AAAA-AAAA"
  const d0 = parseInt((a.split('-')[0] || ''), 10);
  if (!d0) return null;
  return { debut: `${d0}-09-01`, fin: `${d0 + 1}-07-31` };
}

function _planifMajBornes() {
  const bornes = _planifBornesAnnee();
  const btnPrec = document.getElementById('planif-btn-prec');
  const btnSuiv = document.getElementById('planif-btn-suiv');
  if (!bornes || !PLANIF_DATA) return;
  // Semaine précédente / suivante (lundi).
  const lundiPrec = _planifAjouterJours(PLANIF_DATA.lundi, -7);
  const lundiSuiv = _planifAjouterJours(PLANIF_DATA.lundi, 7);
  // « précédente » désactivée si la semaine précédente se termine avant le début.
  const finPrec = _planifAjouterJours(lundiPrec, 4);
  if (btnPrec) btnPrec.disabled = finPrec < bornes.debut;
  // « suivante » désactivée si la semaine suivante commence après la fin.
  if (btnSuiv) btnSuiv.disabled = lundiSuiv > bornes.fin;
}
