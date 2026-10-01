// ============================================================================
// static/edt.js — v0.20.1 (v0.38.0 : EdT versionné, salle, AESH)
// Écran de saisie de l'emploi du temps de l'enseignant.
// Grille jours × créneaux (façon PDF), demi-cases semaine A/B, popover d'édition.
// Backend : /api/edt (GET/POST/PUT/DELETE), grille horaire de l'établissement,
//           classes de l'année.
// ============================================================================

let EDT_ETABS = [];        // établissements
let EDT_GRILLE = [];       // créneaux de la grille horaire (établissement courant)
let EDT_CLASSES = [];      // classes de l'année/établissement
let EDT_CASES = [];        // cases d'EDT chargées
let EDT_USAGES = [];       // usages disponibles
let EDT_GROUPES = [];      // groupes disponibles
let EDT_JOURS = ['lun', 'mar', 'mer', 'jeu', 'ven'];
let EDT_META = {};         // {usages, usages_comptes, jours, semaines}
// v0.38.0 — EdT versionné.
let EDT_SEMAINE = null;    // lundi ISO de la semaine affichée (null = courante)
let EDT_ETAT = { etat: 'en_saisie', date_figeage: '' };
let EDT_CHANGEMENTS = [];  // [{lundi, debuts, fins}]
let EDT_SALLES = [];       // salles non archivées de l'établissement

const EDT_JOUR_LABEL = {
  lun: 'Lundi', mar: 'Mardi', mer: 'Mercredi', jeu: 'Jeudi', ven: 'Vendredi',
};
const EDT_GROUPE_LABEL = {
  classe_entiere: 'Classe entière',
  demi_classe_A: 'Demi-classe A',
  demi_classe_B: 'Demi-classe B',
  groupe_option: 'Groupe (option)',
  groupe_horaire_ordinaire: 'Groupe (horaire ordinaire)',
  autre: 'Autre (préciser au libellé)',
};
const EDT_USAGE_LABEL = {
  cours: 'Cours',
  vie_de_classe: 'Vie de classe',
  co_animation: 'Co-animation (autre classe)',
  autre: 'Autre (préciser au libellé)',
};

// Palette stable de couleurs par classe (assignée par ordre).
const EDT_PALETTE = ['#cfe3ff', '#ffe0cc', '#d8f0d8', '#f3d9f0', '#fff2c2',
  '#d0eef0', '#e6d8f5', '#ffd6d6', '#dce7c8', '#c8e0f5'];
let _edtCouleurClasse = {};

function _edtCouleur(classeId) {
  if (!classeId) return '#eeeeee';  // "autre" / sans classe → gris
  if (!(classeId in _edtCouleurClasse)) {
    const n = Object.keys(_edtCouleurClasse).length;
    _edtCouleurClasse[classeId] = EDT_PALETTE[n % EDT_PALETTE.length];
  }
  return _edtCouleurClasse[classeId];
}

function _edtAnnee() {
  const el = document.getElementById('edt-annee');
  return (el && el.value) || ((typeof ANNEE_ACTIVE!=="undefined" && ANNEE_ACTIVE) || (typeof anneeScolaireCourante==='function' ? anneeScolaireCourante() : ''));
}

async function edtInit() {
  // Établissements dans le sélecteur.
  const selEtab = document.getElementById('edt-etab');
  const inpAnnee = document.getElementById('edt-annee');
  if (inpAnnee && !inpAnnee.value) inpAnnee.value = (typeof ANNEE_ACTIVE!=="undefined" && ANNEE_ACTIVE) || (typeof anneeScolaireCourante === 'function' ? anneeScolaireCourante() : '');
  try {
    const r = await api('/api/etablissements');
    EDT_ETABS = (r && (r.etablissements || r)) || [];
  } catch (e) { EDT_ETABS = []; }
  if (selEtab) {
    const cour = selEtab.value;
    selEtab.innerHTML = EDT_ETABS.map(e =>
      `<option value="${e.id}">${escapeHtml(e.nom)}</option>`).join('');
    if (cour) selEtab.value = cour;
  }
  await edtCharger();
}

async function edtCharger() {
  const selEtab = document.getElementById('edt-etab');
  const etabId = selEtab ? selEtab.value : null;
  const annee = _edtAnnee();
  const zone = document.getElementById('edt-grille');
  if (!etabId) {
    if (zone) zone.innerHTML = '<p style="font-size:13px;color:#999">Aucun établissement.</p>';
    return;
  }
  if (zone) zone.innerHTML = '<p style="font-size:13px;color:#999">Chargement…</p>';
  // Grille horaire + classes + cases EDT en parallèle.
  try {
    const qSem = EDT_SEMAINE ? '&semaine_du=' + EDT_SEMAINE : '';
    const [rg, rc, re, rs] = await Promise.all([
      api('/api/etablissements/' + etabId + '/grille-horaire'),
      api('/api/classes?annee=' + encodeURIComponent(annee)),
      api('/api/edt?annee=' + encodeURIComponent(annee)
          + '&etablissement_id=' + encodeURIComponent(etabId) + qSem),
      api('/api/etablissements/' + etabId + '/salles'),
    ]);
    EDT_ETAT = (re && re.etat) || { etat: 'en_saisie', date_figeage: '' };
    EDT_CHANGEMENTS = (re && re.changements) || [];
    EDT_SALLES = ((rs && rs.salles) || []).filter(x => !x.archivee);
    EDT_GRILLE = (rg && rg.creneaux) || [];
    const classes = (rc && (rc.classes || rc)) || [];
    EDT_CLASSES = classes.filter(c => !c.etablissement || c.etablissement === etabId
      || c.etablissement_id === etabId);
    if (EDT_CLASSES.length === 0) EDT_CLASSES = classes;  // fallback
    EDT_CASES = (re && re.creneaux) || [];
    EDT_META = re || {};
    EDT_USAGES = (re && re.usages) || Object.keys(EDT_USAGE_LABEL);
    EDT_GROUPES = (re && re.groupes) || Object.keys(EDT_GROUPE_LABEL);
  } catch (e) {
    if (zone) zone.innerHTML = '<p style="font-size:13px;color:#c33">Erreur de chargement.</p>';
    return;
  }
  edtRenderBarre();
  edtRenderGrille();
  edtRenderChangements();
}

// ── v0.38.0 — Semaine affichée, état, changements programmés ────────────────

function _edtDateFr(iso) {
  if (!iso) return '';
  const [a, m, j] = iso.split('-');
  return `${j}/${m}/${a}`;
}

function _edtAjouterJours(iso, n) {
  const d = new Date(iso + 'T12:00:00');
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

function _edtFige() { return EDT_ETAT.etat === 'fige'; }

// Lundi d'effet proposé : la semaine affichée, au plus tôt la semaine prochaine.
function _edtDateEffetDefaut() {
  const mini = EDT_META.date_effet_min;
  const sem = EDT_META.semaine_du;
  return (sem && mini && sem > mini) ? sem : mini;
}

function edtSemaine(delta) {
  const base = EDT_META.semaine_du || EDT_META.semaine_courante;
  EDT_SEMAINE = delta === 0 ? null : _edtAjouterJours(base, 7 * delta);
  edtCharger();
}

function edtAllerA(lundi) {
  EDT_SEMAINE = lundi;
  edtCharger();
}

function edtRenderBarre() {
  const zone = document.getElementById('edt-barre');
  if (!zone) return;
  const sem = EDT_META.semaine_du;
  const courante = sem === EDT_META.semaine_courante;
  const etat = _edtFige()
    ? `<span class="edt-etat edt-etat-fige">Figé le ${_edtDateFr(EDT_ETAT.date_figeage)}</span>`
    : `<span class="edt-etat edt-etat-saisie">En saisie</span>
       <button class="btn-sm" onclick="edtFiger()">Figer l'emploi du temps</button>`;
  const salles = EDT_SALLES.length ? `
    <span class="edt-salle-partout">
      <select id="edt-salle-partout" aria-label="Salle à mettre sur toutes les cases">
        ${EDT_SALLES.map(x => `<option value="${x.id}">${escapeHtml(x.nom)}</option>`).join('')}
      </select>
      <button class="btn-sm" onclick="edtAppliquerSalle()">Mettre cette salle sur tous mes cours</button>
    </span>` : '';
  zone.innerHTML = `
    <span class="edt-nav">
      <button class="btn-sm" onclick="edtSemaine(-1)" aria-label="Semaine précédente">‹</button>
      <strong>Semaine du ${_edtDateFr(sem)}</strong>
      <button class="btn-sm" onclick="edtSemaine(1)" aria-label="Semaine suivante">›</button>
      ${courante ? '' : '<button class="btn-sm" onclick="edtSemaine(0)">Cette semaine</button>'}
    </span>
    ${etat}${salles}`;
}

function edtRenderChangements() {
  const zone = document.getElementById('edt-changements');
  if (!zone) return;
  if (!_edtFige()) {
    zone.innerHTML = `<p class="edt-aide">Tant que l'emploi du temps est en saisie,
      les modifications valent pour toute l'année. Une fois figé, il ne se
      modifie plus qu'à partir de la semaine prochaine, et les changements
      programmés apparaissent ici.</p>`;
    return;
  }
  if (!EDT_CHANGEMENTS.length) {
    zone.innerHTML = '<p class="edt-aide">Aucun changement programmé.</p>';
    return;
  }
  const lignes = EDT_CHANGEMENTS.map(c => {
    const parts = [];
    if (c.debuts) parts.push(`${c.debuts} case${c.debuts > 1 ? 's' : ''} qui commence${c.debuts > 1 ? 'nt' : ''}`);
    if (c.fins) parts.push(`${c.fins} case${c.fins > 1 ? 's' : ''} qui s'arrête${c.fins > 1 ? 'nt' : ''}`);
    return `<li>À partir du <strong>${_edtDateFr(c.lundi)}</strong> : ${parts.join(', ')}
      <button class="btn-sm" onclick="edtAllerA('${c.lundi}')">Voir</button>
      <button class="btn-sm edt-danger" onclick="edtAnnulerChangement('${c.lundi}')">Annuler</button></li>`;
  }).join('');
  zone.innerHTML = `<div class="edt-ch-titre">Changements programmés</div><ul>${lignes}</ul>`;
}

async function _edtJson(url, opts) {
  const r = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...(opts || {}) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status));
  return d;
}

function _edtBase() {
  return { annee: _edtAnnee(), etablissement_id: document.getElementById('edt-etab').value };
}

async function edtFiger() {
  if (!confirm("Figer l'emploi du temps ?\n\nAprès cela, il ne se modifie plus sur place "
      + "(sauf les libellés) : chaque changement prend effet un lundi, au plus tôt "
      + "la semaine prochaine. C'est définitif pour cette année.")) return;
  try {
    await _edtJson('/api/edt/figer', { method: 'POST', body: JSON.stringify(_edtBase()) });
    await edtCharger();
  } catch (e) { alert(e.message); }
}

async function edtAnnulerChangement(lundi) {
  if (!confirm(`Annuler tous les changements programmés au ${_edtDateFr(lundi)} ?`)) return;
  const b = _edtBase();
  try {
    await _edtJson(`/api/edt/changements/${lundi}?annee=${encodeURIComponent(b.annee)}`
      + `&etablissement_id=${encodeURIComponent(b.etablissement_id)}`, { method: 'DELETE' });
    await edtCharger();
  } catch (e) { alert(e.message); }
}

// Aperçu de l'effet sur les séances restantes, puis confirmation. Renvoie
// true si l'utilisateur confirme (ou si rien ne change).
async function _edtConfirmerApercu(corps) {
  let d;
  try {
    d = await _edtJson('/api/edt/apercu', { method: 'POST',
      body: JSON.stringify({ ..._edtBase(), ...corps }) });
  } catch (e) { alert(e.message); return false; }
  const diff = (d.classes || []).filter(c => c.avant !== c.apres);
  const quand = corps.a_partir_du ? `à partir du ${_edtDateFr(corps.a_partir_du)}` : '';
  if (!diff.length) {
    return confirm(`Enregistrer ce changement ${quand} ?\n\n`
      + 'Le nombre de séances restantes des classes ne change pas.');
  }
  const lignes = diff.map(c => `  ${c.nom} : ${c.avant} → ${c.apres} séances`).join('\n');
  return confirm(`Enregistrer ce changement ${quand} ?\n\nSéances restantes jusqu'à la fin `
    + `de l'année :\n${lignes}\n\nLes progressions de ces classes seront recalculées.`);
}

async function edtAppliquerSalle() {
  const sel = document.getElementById('edt-salle-partout');
  if (!sel) return;
  const nom = sel.options[sel.selectedIndex].text;
  const corps = { operation: 'appliquer_salle', salle_id: sel.value };
  if (_edtFige()) {
    const d = prompt(`Mettre la salle ${nom} sur tous vos cours à partir du lundi (AAAA-MM-JJ) :`,
                     _edtDateEffetDefaut());
    if (!d) return;
    corps.a_partir_du = d;
  } else if (!confirm(`Mettre la salle ${nom} sur tous vos cours, pour toute l'année ?`)) {
    return;
  }
  try {
    const r = await _edtJson('/api/edt/appliquer-salle', { method: 'POST',
      body: JSON.stringify({ ..._edtBase(), ...corps }) });
    await edtCharger();
    if (typeof showToast === 'function') showToast(`Salle ${nom} : ${r.cases_modifiees} case(s) mise(s) à jour.`);
  } catch (e) { alert(e.message); }
}

function _edtCasesDe(jour, code) {
  // Cases (de cet établissement/année) pour un jour+créneau donné.
  return EDT_CASES.filter(c => c.jour === jour && c.creneau_code === code);
}

function _edtLibelleCase(c) {
  // Compose le contenu d'une case : nom de classe, puis (si pertinent) le
  // groupe, puis le libellé saisi. Chaque élément sur sa ligne.
  const lignes = [];
  const cls = EDT_CLASSES.find(x => x.id === c.classe_id);
  if (cls) lignes.push(cls.nom);
  // Groupe : affiché seulement si ce n'est pas la classe entière ni « autre »
  // (autre étant déjà précisé par le libellé).
  const grp = c.groupe || 'classe_entiere';
  if (grp !== 'classe_entiere' && grp !== 'autre') {
    lignes.push(EDT_GROUPE_LABEL[grp] || grp);
  }
  // Libellé libre s'il est saisi.
  if (c.libelle && c.libelle.trim()) lignes.push(c.libelle.trim());
  // Repli : si rien (ni classe, ni libellé), montrer l'usage lisible.
  if (lignes.length === 0) lignes.push(EDT_USAGE_LABEL[c.usage] || '');
  // v0.38.0 — Salle et AESH.
  const extra = [];
  if (c.salle_nom) extra.push(c.salle_nom);
  if (c.nb_aesh) extra.push(c.nb_aesh > 1 ? `${c.nb_aesh} AESH` : 'AESH');
  if (extra.length) lignes.push(extra.join(', '));
  return lignes;
}

function _edtCouleurCase(c) {
  // Gris dès que ce n'est pas un cours ; sinon couleur de la classe.
  if ((c.usage || 'cours') !== 'cours') return '#dddddd';
  return _edtCouleur(c.classe_id);
}

function _edtEstCompte(c) {
  const gc = EDT_META.groupes_comptes || ['classe_entiere'];
  const uc = EDT_META.usages_comptes || ['cours'];
  return gc.indexOf(c.groupe || 'classe_entiere') >= 0
      && uc.indexOf(c.usage || 'cours') >= 0;
}

function _edtCelluleHTML(jour, code) {
  const cases = _edtCasesDe(jour, code);
  const ab = cases.find(c => c.semaine === 'AB');
  const a = cases.find(c => c.semaine === 'A');
  const b = cases.find(c => c.semaine === 'B');
  const cellStyle = 'border:1px solid var(--border);height:46px;position:relative;'
    + 'cursor:pointer;vertical-align:top;padding:0';

  // Une demi-case (ou pleine) : `demi` vaut '', 'A' ou 'B'.
  function sousCase(c, demi, largeur) {
    const bg = c ? _edtCouleurCase(c) : '#fff';
    const lignes = c ? _edtLibelleCase(c) : [];
    const txt = lignes.map((l, i) =>
      `<span style="display:block${i === 0 ? ';font-weight:600' : ''}">`
      + `${escapeHtml(l)}</span>`).join('');
    const compte = c && !_edtEstCompte(c) ? ';opacity:.75' : '';
    const w = largeur || '100%';
    const marqueur = demi ? `<span style="position:absolute;top:1px;left:2px;`
      + `font-size:9px;color:#666;font-weight:bold">${demi}</span>` : '';
    // v0.38.0 — Changement programmé sur cette case (fin de période à venir,
    // ou case qui commence cette semaine-là).
    let change = '';
    if (c && c.valide_au) {
      change = `<span class="edt-marque-change" title="Change à partir du ${_edtDateFr(c.valide_au)}">⟳ ${_edtDateFr(c.valide_au).slice(0, 5)}</span>`;
    } else if (c && c.valide_du && c.valide_du === EDT_META.semaine_du) {
      change = `<span class="edt-marque-change" title="Nouveau à partir du ${_edtDateFr(c.valide_du)}">nouveau</span>`;
    }
    // Bordure verticale entre A et B pour matérialiser "l'un après l'autre".
    const sep = (demi === 'A') ? ';border-right:1px dashed #bbb' : '';
    return `<div onclick="edtClicCase(event,'${jour}','${code}','${demi || 'AB'}')" `
      + `style="width:${w};height:100%;background:${bg};font-size:9px;line-height:1.15;`
      + `padding:2px 3px 2px 3px;overflow:hidden;box-sizing:border-box;`
      + `position:relative;display:inline-block;vertical-align:top${sep}${compte}">`
      + `${marqueur}${change}<span style="display:block;margin-top:${demi ? '9px' : '1px'}">${txt}</span></div>`;
  }

  let inner;
  if (ab) {
    inner = sousCase(ab, '', '100%');
  } else if (a || b) {
    // Demi-LARGEUR : A à gauche, B à droite (l'un après l'autre dans le temps).
    inner = `<div style="display:flex;width:100%;height:100%">`
      + sousCase(a, 'A', '50%') + sousCase(b, 'B', '50%') + `</div>`;
  } else {
    inner = `<div onclick="edtClicCase(event,'${jour}','${code}','AB')" `
      + `style="height:100%"></div>`;
  }
  return `<td style="${cellStyle}">${inner}</td>`;
}

function edtRenderGrille() {
  const zone = document.getElementById('edt-grille');
  if (!zone) return;
  if (EDT_GRILLE.length === 0) {
    zone.innerHTML = '<p style="font-size:13px;color:#999">Aucun créneau dans la '
      + 'grille horaire de cet établissement. Définissez-la d\'abord dans '
      + 'Gestion › Établissements.</p>';
    return;
  }
  // Ordre des créneaux : par la grille (déjà triée par ordre).
  const entete = '<th style="width:70px"></th>' + EDT_JOURS.map(j =>
    `<th style="padding:4px;font-size:12px;background:#f5f5f5;border:1px solid var(--border)">`
    + `${EDT_JOUR_LABEL[j]}</th>`).join('');
  const lignes = EDT_GRILLE.map(cr => {
    const label = `<th style="padding:2px 6px;font-size:11px;text-align:right;`
      + `background:#f5f5f5;border:1px solid var(--border);white-space:nowrap">`
      + `${escapeHtml(cr.code)}<br><span style="color:#999;font-weight:normal">`
      + `${escapeHtml(cr.heure_debut || '')}</span></th>`;
    const cells = EDT_JOURS.map(j => _edtCelluleHTML(j, cr.code)).join('');
    return `<tr>${label}${cells}</tr>`;
  }).join('');
  zone.innerHTML = `<table style="border-collapse:collapse;width:100%;table-layout:fixed">`
    + `<thead><tr>${entete}</tr></thead><tbody>${lignes}</tbody></table>`;
}

// ── Popover d'édition ────────────────────────────────────────────────────────

function edtClicCase(ev, jour, code, semaine) {
  ev.stopPropagation();
  const cases = _edtCasesDe(jour, code);
  // Case existante correspondant à la semaine cliquée.
  let caseExistante = cases.find(c => c.semaine === semaine);
  // Si on clique une demi-case mais qu'il existe une AB, on édite l'AB.
  if (!caseExistante && (semaine === 'A' || semaine === 'B')) {
    caseExistante = cases.find(c => c.semaine === 'AB');
    if (caseExistante) semaine = 'AB';
  }
  edtOuvrirPopover(ev, jour, code, semaine, caseExistante, cases);
}

function edtOuvrirPopover(ev, jour, code, semaine, caseExistante, casesCreneau) {
  const pop = document.getElementById('edt-popover');
  if (!pop) return;
  const existeAB = casesCreneau.some(c => c.semaine === 'AB');
  const existeAouB = casesCreneau.some(c => c.semaine === 'A' || c.semaine === 'B');

  const optClasses = ['<option value="">— aucune —</option>'].concat(
    EDT_CLASSES.map(c => `<option value="${c.id}"${caseExistante
      && caseExistante.classe_id === c.id ? ' selected' : ''}>${escapeHtml(c.nom)}</option>`)
  ).join('');
  const optGroupes = EDT_GROUPES.map(g => `<option value="${g}"${caseExistante
    && caseExistante.groupe === g ? ' selected' : (!caseExistante && g === 'classe_entiere'
    ? ' selected' : '')}>${escapeHtml(EDT_GROUPE_LABEL[g] || g)}</option>`).join('');
  const optUsages = EDT_USAGES.map(u => `<option value="${u}"${caseExistante
    && caseExistante.usage === u ? ' selected' : (!caseExistante && u === 'cours'
    ? ' selected' : '')}>${escapeHtml(EDT_USAGE_LABEL[u] || u)}</option>`).join('');

  // v0.38.0 — Salle (non archivées + celle déjà posée), AESH, date d'effet.
  const salleCour = caseExistante ? caseExistante.salle_id : null;
  const optSalles = ['<option value="">— aucune —</option>'].concat(
    EDT_SALLES.map(x => `<option value="${x.id}"${salleCour === x.id ? ' selected' : ''}>${escapeHtml(x.nom)}</option>`)
  ).concat(salleCour && !EDT_SALLES.some(x => x.id === salleCour)
    ? [`<option value="${salleCour}" selected>${escapeHtml(caseExistante.salle_nom || '?')}</option>`] : []
  ).join('');
  const caseFuture = caseExistante && caseExistante.valide_du
    && caseExistante.valide_du >= EDT_META.date_effet_min;
  let blocDate = '';
  if (_edtFige()) {
    blocDate = caseFuture
      ? `<p class="edt-pop-note">Case à venir (à partir du ${_edtDateFr(caseExistante.valide_du)}) : modifiée directement.</p>`
      : `<label style="display:block;margin-bottom:10px">À partir du lundi
           <input id="edt-pop-date" type="date" min="${EDT_META.date_effet_min}" step="7"
                  value="${_edtDateEffetDefaut()}" style="width:100%;font-size:13px">
         </label>
         <p class="edt-pop-note">Emploi du temps figé : seul le libellé se corrige sur place.</p>`;
  }

  // Choix de semaine : AB seulement si aucune A/B, A/B seulement si aucune AB.
  const semOpts = [];
  if (!existeAouB || (caseExistante && caseExistante.semaine === 'AB')) {
    semOpts.push(`<option value="AB"${semaine === 'AB' ? ' selected' : ''}>Toutes semaines (AB)</option>`);
  }
  if (!existeAB || (caseExistante && caseExistante.semaine !== 'AB')) {
    semOpts.push(`<option value="A"${semaine === 'A' ? ' selected' : ''}>Semaine A</option>`);
    semOpts.push(`<option value="B"${semaine === 'B' ? ' selected' : ''}>Semaine B</option>`);
  }

  pop.innerHTML = `
    <div style="font-weight:600;margin-bottom:8px">${EDT_JOUR_LABEL[jour]} · ${escapeHtml(code)}</div>
    <label style="display:block;margin-bottom:6px">Semaine
      <select id="edt-pop-semaine" style="width:100%;font-size:13px">${semOpts.join('')}</select>
    </label>
    <label style="display:block;margin-bottom:6px">Classe
      <select id="edt-pop-classe" style="width:100%;font-size:13px">${optClasses}</select>
    </label>
    <label style="display:block;margin-bottom:6px">Groupe
      <select id="edt-pop-groupe" style="width:100%;font-size:13px">${optGroupes}</select>
    </label>
    <label style="display:block;margin-bottom:6px">Usage
      <select id="edt-pop-usage" style="width:100%;font-size:13px">${optUsages}</select>
    </label>
    <label style="display:block;margin-bottom:6px">Libellé (optionnel)
      <input id="edt-pop-libelle" value="${caseExistante ? escapeHtml(caseExistante.libelle || '') : ''}"
             placeholder="ex : Concertation" style="width:100%;font-size:13px">
    </label>
    <div style="display:flex;gap:8px;margin-bottom:10px">
      <label style="flex:1">Salle
        <select id="edt-pop-salle" style="width:100%;font-size:13px">${optSalles}</select>
      </label>
      <label style="width:70px">AESH
        <input id="edt-pop-aesh" type="number" min="0" max="5" value="${caseExistante ? (caseExistante.nb_aesh || 0) : 0}"
               style="width:100%;font-size:13px">
      </label>
    </div>
    ${blocDate}
    <div style="display:flex;gap:6px;justify-content:space-between;align-items:center">
      <button class="btn-prim" style="font-size:12px"
        onclick="edtEnregistrerCase('${jour}','${code}','${caseExistante ? caseExistante.id : ''}')">Enregistrer</button>
      ${caseExistante ? `<button class="btn-sm" style="font-size:12px;color:var(--danger)"
        onclick="edtSupprimerCase('${caseExistante.id}')">Supprimer</button>` : ''}
      <button class="btn-sm" style="font-size:12px" onclick="edtFermerPopover()">Fermer</button>
    </div>
    <div id="edt-pop-status" style="font-size:11px;color:#c33;margin-top:6px"></div>`;

  // Positionnement près du clic.
  pop.style.display = 'block';
  const px = Math.min(ev.clientX, window.innerWidth - 300);
  const py = Math.min(ev.clientY, window.innerHeight - 440);
  pop.style.left = Math.max(8, px) + 'px';
  pop.style.top = Math.max(8, py) + 'px';
}

function edtFermerPopover() {
  const pop = document.getElementById('edt-popover');
  if (pop) pop.style.display = 'none';
}

async function edtEnregistrerCase(jour, code, edtId) {
  const g = id => document.getElementById(id);
  const semaine = g('edt-pop-semaine').value;
  const classe_id = g('edt-pop-classe').value || null;
  const groupe = g('edt-pop-groupe').value;
  const usage = g('edt-pop-usage').value;
  const libelle = g('edt-pop-libelle').value || '';
  const salle_id = g('edt-pop-salle').value || null;
  const nb_aesh = parseInt(g('edt-pop-aesh').value || '0', 10) || 0;
  const a_partir_du = g('edt-pop-date') ? (g('edt-pop-date').value || null) : null;
  const annee = _edtAnnee();
  const etabId = document.getElementById('edt-etab').value;
  const status = g('edt-pop-status');
  const champs = { semaine, classe_id, groupe, usage, libelle, salle_id, nb_aesh };
  try {
    // v0.38.0 — EdT figé : changement daté, avec aperçu de l'effet sur les
    // séances (sauf correction de libellé seule, faite sur place).
    if (_edtFige() && a_partir_du) {
      const avant = edtId ? EDT_CASES.find(c => c.id === edtId) : null;
      const structurel = !avant || ['semaine', 'classe_id', 'groupe', 'usage', 'salle_id', 'nb_aesh']
        .some(k => (avant[k] || null) !== (champs[k] || null) && !(k === 'nb_aesh' && (avant[k] || 0) === champs[k]));
      if (structurel) {
        const corps = edtId
          ? { operation: 'modifier', edt_id: edtId, champs, a_partir_du }
          : { operation: 'ajouter', champs: { jour, creneau_code: code, ...champs }, a_partir_du };
        if (!(await _edtConfirmerApercu(corps))) return;
      }
    }
    let r;
    if (edtId) {
      // Modification : semaine/classe/groupe/usage/salle/AESH/libellé
      // (jour+créneau fixes).
      r = await fetch('/api/edt/' + edtId, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...champs, a_partir_du }),
      });
    } else {
      r = await fetch('/api/edt', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          annee, jour, creneau_code: code, ...champs, a_partir_du,
          etablissement_id: etabId,
        }),
      });
    }
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status));
    edtFermerPopover();
    await edtCharger();
  } catch (e) {
    if (status) status.textContent = 'Erreur : ' + e.message;
  }
}

async function edtSupprimerCase(edtId) {
  const champDate = document.getElementById('edt-pop-date');
  const a_partir_du = champDate ? (champDate.value || null) : null;
  try {
    if (_edtFige() && a_partir_du) {
      if (!(await _edtConfirmerApercu({ operation: 'supprimer', edt_id: edtId, a_partir_du }))) return;
    }
    const q = a_partir_du ? '?a_partir_du=' + a_partir_du : '';
    const r = await fetch('/api/edt/' + edtId + q, { method: 'DELETE' });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      throw new Error(d.error || ('HTTP ' + r.status));
    }
    edtFermerPopover();
    await edtCharger();
  } catch (e) {
    const status = document.getElementById('edt-pop-status');
    if (status) status.textContent = 'Erreur : ' + e.message;
  }
}

// Fermer le popover si on clique en dehors.
document.addEventListener('click', function (ev) {
  const pop = document.getElementById('edt-popover');
  if (!pop || pop.style.display === 'none') return;
  if (!pop.contains(ev.target)) {
    // Ne pas fermer si le clic vient d'une case (géré par edtClicCase).
    if (ev.target.closest && ev.target.closest('#edt-grille')) return;
    edtFermerPopover();
  }
});
