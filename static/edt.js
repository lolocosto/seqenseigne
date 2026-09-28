// ============================================================================
// static/edt.js — v0.20.1
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
    const [rg, rc, re] = await Promise.all([
      api('/api/etablissements/' + etabId + '/grille-horaire'),
      api('/api/classes?annee=' + encodeURIComponent(annee)),
      api('/api/edt?annee=' + encodeURIComponent(annee)),
    ]);
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
  edtRenderGrille();
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
    // Bordure verticale entre A et B pour matérialiser "l'un après l'autre".
    const sep = (demi === 'A') ? ';border-right:1px dashed #bbb' : '';
    return `<div onclick="edtClicCase(event,'${jour}','${code}','${demi || 'AB'}')" `
      + `style="width:${w};height:100%;background:${bg};font-size:9px;line-height:1.15;`
      + `padding:2px 3px 2px 3px;overflow:hidden;box-sizing:border-box;`
      + `position:relative;display:inline-block;vertical-align:top${sep}${compte}">`
      + `${marqueur}<span style="display:block;margin-top:${demi ? '9px' : '1px'}">${txt}</span></div>`;
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
    <label style="display:block;margin-bottom:10px">Libellé (optionnel)
      <input id="edt-pop-libelle" value="${caseExistante ? escapeHtml(caseExistante.libelle || '') : ''}"
             placeholder="ex : Concertation" style="width:100%;font-size:13px">
    </label>
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
  const py = Math.min(ev.clientY, window.innerHeight - 320);
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
  const annee = _edtAnnee();
  const etabId = document.getElementById('edt-etab').value;
  const status = g('edt-pop-status');
  try {
    let r;
    if (edtId) {
      // Modification : semaine/classe/groupe/usage/libellé (jour+créneau fixes).
      r = await fetch('/api/edt/' + edtId, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ semaine, classe_id, groupe, usage, libelle }),
      });
    } else {
      r = await fetch('/api/edt', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          annee, jour, creneau_code: code, semaine, classe_id, groupe, usage,
          libelle, etablissement_id: etabId,
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
  try {
    const r = await fetch('/api/edt/' + edtId, { method: 'DELETE' });
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
