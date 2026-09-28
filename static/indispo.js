// ============================================================================
// static/indispo.js — v0.21.0
// Écran de saisie des indisponibilités (séances/journées, portée moi/classes).
// Backend : /api/indisponibilites (GET/POST/PUT/DELETE).
// ============================================================================

let INDISPO_ETABS = [];
let INDISPO_CLASSES = [];
let INDISPO_GRILLE = [];
let INDISPO_LISTE = [];
let INDISPO_EDIT_ID = null;   // null = création ; sinon id de l'indispo éditée

// Formate une date ISO (aaaa-mm-jj) en français (jj/mm/aaaa).
function _indispoDateFr(iso) {
  if (!iso) return '';
  const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : iso;
}

function _indispoAnnee() {
  const el = document.getElementById('indispo-annee');
  return (el && el.value) || ((typeof ANNEE_ACTIVE!=="undefined" && ANNEE_ACTIVE) || (typeof anneeScolaireCourante==='function' ? anneeScolaireCourante() : ''));
}

async function indispoInit() {
  const sel = document.getElementById('indispo-etab');
  const inpAnnee = document.getElementById('indispo-annee');
  if (inpAnnee && !inpAnnee.value) inpAnnee.value = (typeof ANNEE_ACTIVE!=="undefined" && ANNEE_ACTIVE) || (typeof anneeScolaireCourante === 'function' ? anneeScolaireCourante() : '');
  try {
    const r = await api('/api/etablissements');
    INDISPO_ETABS = (r && (r.etablissements || r)) || [];
  } catch (e) { INDISPO_ETABS = []; }
  if (sel) {
    const cour = sel.value;
    sel.innerHTML = INDISPO_ETABS.map(e =>
      `<option value="${e.id}">${escapeHtml(e.nom)}</option>`).join('');
    if (cour) sel.value = cour;
  }
  await indispoCharger();
}

async function indispoCharger() {
  const etabId = document.getElementById('indispo-etab').value;
  const annee = _indispoAnnee();
  if (!etabId) return;
  try {
    const [rc, rg, ri] = await Promise.all([
      api('/api/classes?annee=' + encodeURIComponent(annee)),
      api('/api/etablissements/' + etabId + '/grille-horaire'),
      api('/api/indisponibilites?annee=' + encodeURIComponent(annee)
        + '&etablissement_id=' + etabId),
    ]);
    const classes = (rc && (rc.classes || rc)) || [];
    INDISPO_CLASSES = classes.filter(c =>
      !c.etablissement || c.etablissement === etabId || c.etablissement_id === etabId);
    if (INDISPO_CLASSES.length === 0) INDISPO_CLASSES = classes;
    INDISPO_GRILLE = (rg && rg.creneaux) || [];
    INDISPO_LISTE = (ri && ri.indisponibilites) || [];
  } catch (e) {
    INDISPO_CLASSES = []; INDISPO_GRILLE = []; INDISPO_LISTE = [];
  }
  // Si l'indispo en cours d'édition n'existe plus (supprimée, ou changement
  // d'établissement/année), sortir du mode édition.
  if (INDISPO_EDIT_ID !== null
      && !INDISPO_LISTE.some(x => x.id === INDISPO_EDIT_ID)) {
    INDISPO_EDIT_ID = null;
  }
  indispoRenderForm();
  indispoRenderListe();
}

function indispoRenderForm() {
  const zone = document.getElementById('indispo-form');
  if (!zone) return;
  const optCreneaux = INDISPO_GRILLE.map(c =>
    `<option value="${c.code}">${escapeHtml(c.code)} (${escapeHtml(c.heure_debut || '')})</option>`).join('');
  const optClasses = INDISPO_CLASSES.map(c =>
    `<option value="${c.id}">${escapeHtml(c.nom)}</option>`).join('');
  const enEdition = INDISPO_EDIT_ID !== null;
  const it = enEdition
    ? INDISPO_LISTE.find(x => x.id === INDISPO_EDIT_ID) : null;
  const titre = enEdition ? 'Modifier l\'indisponibilité'
                          : 'Ajouter une indisponibilité';
  const libBtn = enEdition ? 'Enregistrer les modifications' : 'Ajouter';
  const boutons = enEdition
    ? `<button class="btn-prim" onclick="indispoEnregistrer()" style="font-size:13px">${libBtn}</button>`
      + `<button class="btn-sm" onclick="indispoAnnulerEdition()" style="font-size:13px">Annuler</button>`
    : `<button class="btn-prim" onclick="indispoEnregistrer()" style="font-size:13px">${libBtn}</button>`;
  zone.innerHTML = `
    <div style="font-weight:600;margin-bottom:8px;font-size:13px">${titre}</div>
    <div style="display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end;font-size:13px">
      <label>Type
        <select id="indispo-type" onchange="indispoTypeChange()" style="display:block;font-size:13px">
          <option value="journees">Journées entières</option>
          <option value="seances">Plage de séances (une journée)</option>
        </select>
      </label>
      <label>Date${'\u00A0'}début
        <input type="date" id="indispo-date-debut" style="display:block;font-size:13px">
      </label>
      <label id="indispo-lbl-datefin">Date${'\u00A0'}fin
        <input type="date" id="indispo-date-fin" style="display:block;font-size:13px">
      </label>
      <span id="indispo-creneaux" style="display:none">
        <label>Du créneau
          <select id="indispo-cren-debut" style="display:block;font-size:13px">${optCreneaux}</select>
        </label>
        <label>au créneau
          <select id="indispo-cren-fin" style="display:block;font-size:13px">${optCreneaux}</select>
        </label>
      </span>
      <label>Portée
        <select id="indispo-portee" onchange="indispoPorteeChange()" style="display:block;font-size:13px">
          <option value="moi">Moi (toutes mes séances)</option>
          <option value="classes">Une ou plusieurs classes</option>
        </select>
      </label>
      <span id="indispo-classes-wrap" style="display:none">
        <label>Classes (Ctrl pour plusieurs)
          <select id="indispo-classes" multiple size="3" style="display:block;font-size:13px;min-width:120px">${optClasses}</select>
        </label>
      </span>
      <label style="flex:1;min-width:160px">Motif
        <input id="indispo-motif" placeholder="ex : Surveillance DNB" style="display:block;width:100%;font-size:13px">
      </label>
      ${boutons}
    </div>
    <div id="indispo-form-status" style="font-size:12px;color:#c33;margin-top:6px"></div>`;
  // Pré-remplissage en mode édition.
  if (it) {
    document.getElementById('indispo-type').value = it.type;
    document.getElementById('indispo-date-debut').value = it.date_debut || '';
    document.getElementById('indispo-date-fin').value = it.date_fin || '';
    if (it.creneau_debut) document.getElementById('indispo-cren-debut').value = it.creneau_debut;
    if (it.creneau_fin) document.getElementById('indispo-cren-fin').value = it.creneau_fin;
    document.getElementById('indispo-portee').value = it.portee;
    document.getElementById('indispo-motif').value = it.motif || '';
    if (it.portee === 'classes') {
      const sel = document.getElementById('indispo-classes');
      Array.from(sel.options).forEach(o => {
        o.selected = (it.classes_ids || []).indexOf(o.value) >= 0;
      });
    }
  }
  indispoTypeChange();
  indispoPorteeChange();
}

function indispoTypeChange() {
  const t = document.getElementById('indispo-type').value;
  const cren = document.getElementById('indispo-creneaux');
  const lblFin = document.getElementById('indispo-lbl-datefin');
  if (cren) cren.style.display = (t === 'seances') ? '' : 'none';
  // Pour une plage de séances, la date de fin = date de début (une seule journée).
  if (lblFin) lblFin.style.display = (t === 'seances') ? 'none' : '';
}

function indispoPorteeChange() {
  const p = document.getElementById('indispo-portee').value;
  const w = document.getElementById('indispo-classes-wrap');
  if (w) w.style.display = (p === 'classes') ? '' : 'none';
}

async function indispoEnregistrer() {
  const g = id => document.getElementById(id);
  const type = g('indispo-type').value;
  const portee = g('indispo-portee').value;
  const status = g('indispo-form-status');
  const classes_ids = portee === 'classes'
    ? Array.from(g('indispo-classes').selectedOptions).map(o => o.value) : [];
  const body = {
    annee: _indispoAnnee(),
    etablissement_id: g('indispo-etab').value,
    type,
    date_debut: g('indispo-date-debut').value,
    date_fin: type === 'journees' ? g('indispo-date-fin').value : '',
    creneau_debut: type === 'seances' ? g('indispo-cren-debut').value : '',
    creneau_fin: type === 'seances' ? g('indispo-cren-fin').value : '',
    portee, classes_ids,
    motif: g('indispo-motif').value,
  };
  const enEdition = INDISPO_EDIT_ID !== null;
  const url = enEdition ? '/api/indisponibilites/' + INDISPO_EDIT_ID
                        : '/api/indisponibilites';
  const method = enEdition ? 'PUT' : 'POST';
  try {
    const r = await fetch(url, {
      method, headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status));
    INDISPO_EDIT_ID = null;
    await indispoCharger();
  } catch (e) {
    if (status) status.textContent = 'Erreur : ' + e.message;
  }
}

function indispoEditer(iid) {
  INDISPO_EDIT_ID = iid;
  indispoRenderForm();
  // Amener le formulaire à l'écran.
  const f = document.getElementById('indispo-form');
  if (f && f.scrollIntoView) f.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function indispoAnnulerEdition() {
  INDISPO_EDIT_ID = null;
  indispoRenderForm();
}

function _indispoDescription(it) {
  const nomClasse = id => {
    const c = INDISPO_CLASSES.find(x => x.id === id);
    return c ? c.nom : id;
  };
  let quand;
  if (it.type === 'journees') {
    quand = (it.date_debut === it.date_fin || !it.date_fin)
      ? `le ${_indispoDateFr(it.date_debut)}`
      : `du ${_indispoDateFr(it.date_debut)} au ${_indispoDateFr(it.date_fin)}`;
  } else {
    quand = `le ${_indispoDateFr(it.date_debut)}, de ${it.creneau_debut} à ${it.creneau_fin}`;
  }
  const port = it.portee === 'classes'
    ? (it.classes_ids || []).map(nomClasse).join(', ')
    : 'toutes mes séances';
  return { quand, port };
}

function indispoRenderListe() {
  const zone = document.getElementById('indispo-liste');
  if (!zone) return;
  if (INDISPO_LISTE.length === 0) {
    zone.innerHTML = '<p style="font-size:13px;color:#999">Aucune indisponibilité saisie.</p>';
    return;
  }
  const lignes = INDISPO_LISTE.map(it => {
    const d = _indispoDescription(it);
    return `<tr>
      <td style="padding:4px 8px;font-size:13px">${escapeHtml(d.quand)}</td>
      <td style="padding:4px 8px;font-size:13px">${escapeHtml(d.port)}</td>
      <td style="padding:4px 8px;font-size:13px">${escapeHtml(it.motif || '')}</td>
      <td style="padding:4px 8px;white-space:nowrap">
        <button class="btn-sm" onclick="indispoEditer('${it.id}')" title="Modifier">Modifier</button>
        <button class="btn-sm" style="color:var(--danger)"
            onclick="indispoSupprimer('${it.id}')" title="Supprimer" aria-label="Supprimer">×</button>
      </td>
    </tr>`;
  }).join('');
  zone.innerHTML = `<table style="border-collapse:collapse;width:100%">
    <thead><tr style="text-align:left;color:#666;font-size:12px">
      <th style="padding:4px 8px">Quand</th><th style="padding:4px 8px">Portée</th>
      <th style="padding:4px 8px">Motif</th><th></th>
    </tr></thead><tbody>${lignes}</tbody></table>`;
}

async function indispoSupprimer(iid) {
  if (!confirm('Supprimer cette indisponibilité ?')) return;
  try {
    const r = await fetch('/api/indisponibilites/' + iid, { method: 'DELETE' });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      throw new Error(d.error || ('HTTP ' + r.status));
    }
    await indispoCharger();
  } catch (e) {
    alert('Erreur : ' + e.message);
  }
}
