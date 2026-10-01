// ============================================================================
// static/plans_classe.js — v0.39.0 (v0.39.1 : cadenas)
// Plans de classe hebdomadaires (Planification › Plans de classe).
// Backend : /api/plans-classe (GET/PUT/DELETE), /api/plans-classe/salles,
//           /api/plans-classe/aleatoire (POST), /api/plans-classe/pdf.
// Géométrie des places : window.SallesPur (static/salles_pur.js).
//
// Interaction (validée) :
//   - clic sur un élève (liste ou plan) puis clic sur une place : placement ;
//     place occupée → les deux élèves échangent ; glisser-déposer aussi ;
//   - renvoyer un élève dans la liste le retire du plan ;
//   - un élève placé est « libre » par défaut ; cadenas → « imposé » ;
//   - semaine reconduite : les libres sont à confirmer (grisés) ; un clic sur
//     l'élève le confirme, « Tout confirmer » confirme toute la classe ;
//   - chaque action est enregistrée aussitôt (la première crée le plan de la
//     semaine) ; semaines passées en lecture seule.
// ============================================================================

const PC = {
  classes: [], classeId: '', lundi: null, salles: [], salleId: '',
  plan: null, sel: null,          // sel : eleve_id sélectionné
  drag: null, occupe: false,
};

function _pcE(s) { return escapeHtml(String(s == null ? '' : s)); }

function _pcDateFr(iso) {
  if (!iso) return '';
  const [a, m, j] = iso.split('-');
  return `${j}/${m}/${a}`;
}

function _pcAjouterJours(iso, n) {
  const d = new Date(iso + 'T12:00:00');
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

async function _pcApi(url, opts) {
  const r = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...(opts || {}) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || ('Erreur ' + r.status));
  return d;
}

function _pcToast(msg, erreur) {
  if (typeof showToast === 'function') showToast(msg, !!erreur);
  else if (erreur) alert(msg);
}

// ── Chargement ──────────────────────────────────────────────────────────────

async function pcInit() {
  const annee = (typeof ANNEE_ACTIVE !== 'undefined' && ANNEE_ACTIVE)
    || (typeof anneeScolaireCourante === 'function' ? anneeScolaireCourante() : '');
  const etab = (typeof SUIVI_ETAB_ACTIF !== 'undefined' && SUIVI_ETAB_ACTIF) || '';
  try {
    const r = await _pcApi('/api/classes?annee=' + encodeURIComponent(annee));
    const toutes = (r && (r.classes || r)) || [];
    PC.classes = toutes.filter(c => !etab || c.etablissement_id === etab || c.etablissement === etab)
      .sort((a, b) => a.nom.localeCompare(b.nom));
  } catch (e) { PC.classes = []; }
  const sel = document.getElementById('pc-classe');
  if (!sel) return;
  if (!PC.classes.some(c => c.id === PC.classeId)) {
    let mem = '';
    try { mem = localStorage.getItem('pc-classe') || ''; } catch (e) {}
    PC.classeId = PC.classes.some(c => c.id === mem) ? mem : (PC.classes[0] ? PC.classes[0].id : '');
  }
  sel.innerHTML = PC.classes.length
    ? PC.classes.map(c => `<option value="${c.id}"${c.id === PC.classeId ? ' selected' : ''}>${_pcE(c.nom)}</option>`).join('')
    : '<option value="">Aucune classe</option>';
  await pcChargerSalles();
}

async function pcChoisirClasse() {
  PC.classeId = document.getElementById('pc-classe').value;
  try { localStorage.setItem('pc-classe', PC.classeId); } catch (e) {}
  PC.sel = null;
  await pcChargerSalles();
}

async function pcSemaine(delta) {
  PC.lundi = delta === 0 ? null : _pcAjouterJours(PC.lundi, 7 * delta);
  PC.sel = null;
  await pcChargerSalles();
}

async function pcChargerSalles() {
  const plan = document.getElementById('pc-plan');
  if (!PC.classeId) {
    PC.plan = null;
    if (plan) plan.innerHTML = '<p class="pc-vide">Aucune classe pour cet établissement et cette année.</p>';
    _pcRendreEntete(); _pcRendreCote(); _pcRendreOutils();
    return;
  }
  const q = 'classe_id=' + encodeURIComponent(PC.classeId) + (PC.lundi ? '&lundi=' + PC.lundi : '');
  try {
    const r = await _pcApi('/api/plans-classe/salles?' + q);
    PC.lundi = r.lundi; PC.semaineCourante = r.semaine_courante;
    PC.salles = r.salles || [];
  } catch (e) { PC.salles = []; _pcToast(e.message, true); }
  if (!PC.salles.some(s => s.id === PC.salleId)) PC.salleId = PC.salles[0] ? PC.salles[0].id : '';
  await pcChargerPlan();
}

async function pcChoisirSalle(id) {
  PC.salleId = id; PC.sel = null;
  await pcChargerPlan();
}

async function pcChargerPlan() {
  _pcRendreEntete();
  const zone = document.getElementById('pc-plan');
  if (!PC.salleId) {
    PC.plan = null;
    if (zone) zone.innerHTML = `<p class="pc-vide">Pas de cours en classe entière avec une salle cette
      semaine pour cette classe. Les salles se renseignent dans l'emploi du temps.</p>`;
    _pcRendreCote(); _pcRendreOutils(); _pcRendreMessages();
    return;
  }
  try {
    PC.plan = await _pcApi(`/api/plans-classe?classe_id=${encodeURIComponent(PC.classeId)}`
      + `&salle_id=${encodeURIComponent(PC.salleId)}&lundi=${PC.lundi}`);
  } catch (e) { PC.plan = null; _pcToast(e.message, true); }
  _pcRendreTout();
}

// ── Rendu ───────────────────────────────────────────────────────────────────

function _pcRendreTout() {
  _pcRendreEntete(); _pcRendreOutils(); _pcRendreMessages(); _pcRendrePlan(); _pcRendreCote();
}

function _pcRendreEntete() {
  const nav = document.getElementById('pc-semaine-nav');
  if (nav && PC.lundi) {
    nav.innerHTML = `
      <button class="btn-sm" onclick="pcSemaine(-1)" aria-label="Semaine précédente">‹</button>
      <strong>Semaine du ${_pcDateFr(PC.lundi)}</strong>
      <button class="btn-sm" onclick="pcSemaine(1)" aria-label="Semaine suivante">›</button>
      ${PC.lundi !== PC.semaineCourante ? '<button class="btn-sm" onclick="pcSemaine(0)">Cette semaine</button>' : ''}`;
  }
  const sz = document.getElementById('pc-salle-zone');
  if (sz) {
    sz.innerHTML = PC.salles.length > 1
      ? `<label>Salle <select onchange="pcChoisirSalle(this.value)">${PC.salles.map(s =>
          `<option value="${s.id}"${s.id === PC.salleId ? ' selected' : ''}>${_pcE(s.nom)}</option>`).join('')}</select></label>`
      : (PC.salles.length ? `<span class="pc-salle">Salle ${_pcE(PC.salles[0].nom)}</span>` : '');
  }
}

function _pcAConfirmer() {
  return PC.plan ? PC.plan.placements.filter(p => !p.confirme) : [];
}

function _pcRendreOutils() {
  const z = document.getElementById('pc-outils');
  if (!z) return;
  if (!PC.plan) { z.innerHTML = ''; return; }
  const p = PC.plan, mod = p.modifiable;
  const source = p.source === 'reconduit'
    ? `<span class="pc-source pc-source-reconduit">Reconduit du ${_pcDateFr(p.reconduit_de)}</span>`
    : (p.source === 'saisi' ? '<span class="pc-source">Plan de la semaine</span>'
                            : '<span class="pc-source">Aucun plan</span>');
  const nConf = _pcAConfirmer().length;
  const ro = mod ? '' : ' disabled';
  const q = `salle_id=${encodeURIComponent(PC.salleId)}&lundi=${PC.lundi}`;
  z.innerHTML = `
    ${source}
    ${!mod ? '<span class="pc-lecture">Semaine passée : lecture seule</span>' : ''}
    ${nConf ? `<button class="btn-sm btn-prim" onclick="pcToutConfirmer()"${ro}>Tout confirmer (${nConf})</button>` : ''}
    <button class="btn-sm" onclick="pcAleatoire()"${ro}>Placement aléatoire</button>
    ${p.source === 'saisi' ? `<button class="btn-sm" onclick="pcReinitialiser()"${ro}>Annuler le plan de la semaine</button>` : ''}
    <span class="pc-espace"></span>
    <a class="btn-sm" target="_blank" href="/api/plans-classe/pdf?classe_id=${encodeURIComponent(PC.classeId)}&${q}">Imprimer ce plan</a>
    <a class="btn-sm" target="_blank" href="/api/plans-classe/pdf?${q}">Imprimer les plans de la salle</a>`;
}

function _pcRendreMessages() {
  const z = document.getElementById('pc-messages');
  if (!z) return;
  const av = (PC.plan && PC.plan.avertissements) || [];
  z.innerHTML = av.length ? `<div class="pc-avert">${av.map(_pcE).join('<br>')}</div>` : '';
}

function _pcNoms() {
  const m = {};
  (PC.plan ? PC.plan.eleves : []).forEach(e => { m[e.id] = e; });
  return m;
}

function _pcRendrePlan() {
  const zone = document.getElementById('pc-plan');
  if (!zone || !PC.plan) return;
  const S = window.SallesPur, p = PC.plan;
  if (!p.places.length) {
    zone.innerHTML = '<p class="pc-vide">Le plan de cette salle n\'a pas encore de places (Gestion › Établissement › Salles).</p>';
    return;
  }
  const c = S.cadre(p.places, 40);
  const noms = _pcNoms();
  const parNum = {};
  p.placements.forEach(x => { parNum[x.numero] = x; });
  const largTab = Math.min(300, c.w * 0.5), xTab = c.x + (c.w - largTab) / 2;
  const places = p.places.map(pl => {
    const occ = parNum[pl.numero];
    const e = occ ? noms[occ.eleve_id] : null;
    const cls = ['pc-place'];
    if (occ) cls.push('pc-occupee', occ.statut === 'impose' ? 'pc-impose' : 'pc-libre');
    if (occ && !occ.confirme) cls.push('pc-a-confirmer');
    if (occ && PC.sel === occ.eleve_id) cls.push('pc-sel');
    if (!occ && PC.sel) cls.push('pc-cible');
    const lib = e ? e.etiquette : String(pl.numero);
    // Deux lignes (prénom / reste), tronquées pour tenir dans 60 cm ; le nom
    // complet reste en info-bulle et dans la fiche de l'élève.
    const coupe = t => (t.length > 10 ? t.slice(0, 8) + '…' : t);
    const [l1, l2] = lib.includes(' ') ? [lib.slice(0, lib.indexOf(' ')), lib.slice(lib.indexOf(' ') + 1)] : [lib, ''];
    const texte = e
      ? `<title>${_pcE(e.prenom)} ${_pcE(e.nom)}</title>`
        + `<text x="${pl.x}" y="${pl.y - 6}">${_pcE(coupe(l1))}</text><text x="${pl.x}" y="${pl.y + 8}">${_pcE(coupe(l2))}</text>`
      : `<text class="pc-num" x="${pl.x}" y="${pl.y}">${pl.numero}</text>`;
    return `<g class="${cls.join(' ')}" data-num="${pl.numero}"${occ ? ` data-eleve="${occ.eleve_id}"` : ''}>
      <rect x="${-S.L / 2}" y="${-S.H / 2}" width="${S.L}" height="${S.H}" rx="2"
            transform="translate(${pl.x} ${pl.y}) rotate(${pl.angle || 0})"></rect>${texte}</g>`;
  }).join('');
  // v0.39.1 — Cadenas des imposés : à l'INTÉRIEUR de la place, dans celui de
  // ses quatre coins (légèrement rentrés) qui est le plus en haut à droite à
  // l'écran quelle que soit la rotation, et dessinés APRÈS toutes les places
  // pour qu'aucune place voisine ne les masque.
  const coinsInternes = [[1, -1], [1, 1], [-1, -1], [-1, 1]]
    .map(([u, v]) => [u * (S.L / 2 - 7), v * (S.H / 2 - 7)]);
  const cadenas = p.places.filter(pl => parNum[pl.numero] && parNum[pl.numero].statut === 'impose')
    .map(pl => {
      const [dx, dy] = coinsInternes
        .map(([u, v]) => S.tournerVecteur(u, v, pl.angle || 0))
        .reduce((m, c) => (c[0] - c[1] > m[0] - m[1] ? c : m));
      return `<text class="pc-cadenas" x="${pl.x + dx}" y="${pl.y + dy}">🔒</text>`;
    }).join('');
  zone.innerHTML = `<svg id="pc-svg" viewBox="${c.x} ${c.y - 30} ${c.w} ${c.h + 30}" preserveAspectRatio="xMidYMin meet"
      role="img" aria-label="Plan de classe, tableau en haut">
      <g class="sal-tableau"><rect x="${xTab}" y="${c.y - 24}" width="${largTab}" height="8" rx="2"></rect>
      <text x="${xTab + largTab / 2}" y="${c.y - 4}">Tableau</text></g>
      ${places}<g class="pc-cadenas-calque" aria-hidden="true">${cadenas}</g></svg>`;
}

function _pcRendreCote() {
  const z = document.getElementById('pc-cote');
  if (!z) return;
  if (!PC.plan) { z.innerHTML = ''; return; }
  const noms = _pcNoms(), p = PC.plan;
  const non = p.non_places.map(id => noms[id]).filter(Boolean);
  let fiche = '';
  const occ = PC.sel ? p.placements.find(x => x.eleve_id === PC.sel) : null;
  if (PC.sel && noms[PC.sel]) {
    const e = noms[PC.sel];
    fiche = `<div class="pc-fiche">
      <div class="pc-fiche-nom">${_pcE(e.prenom)} ${_pcE(e.nom)}</div>
      ${occ ? `<div>Place ${occ.numero}</div>
        <label class="pc-impose-lbl"><input type="checkbox" ${occ.statut === 'impose' ? 'checked' : ''}
          ${p.modifiable ? '' : 'disabled'} onchange="pcBasculerImpose('${e.id}', this.checked)">
          Placé par l'enseignant (imposé)</label>
        <button class="btn-sm" onclick="pcRetirer('${e.id}')"${p.modifiable ? '' : ' disabled'}>Retirer du plan</button>`
        : '<div class="pc-aide">Cliquez une place pour l\'y installer.</div>'}
      </div>`;
  }
  z.innerHTML = `${fiche}
    <div class="pc-liste-titre">Non placés (${non.length})</div>
    <div id="pc-liste" class="pc-liste" data-liste="1">
      ${non.length ? non.map(e => `<div class="pc-eleve${PC.sel === e.id ? ' pc-sel' : ''}" data-eleve="${e.id}">${_pcE(e.etiquette)}</div>`).join('')
                   : '<div class="pc-aide">Tous les élèves sont placés.</div>'}
    </div>
    <p class="pc-aide">Cliquez un élève puis une place (une place occupée : les deux élèves échangent),
      ou faites-le glisser. Déposé ici, il est retiré du plan.
      <span class="pc-legende"><b>🔒 gras</b> : imposé ; <i>grisé</i> : à confirmer.</span></p>`;
}

// ── Actions ─────────────────────────────────────────────────────────────────

async function _pcEnregistrer(placements) {
  if (!PC.plan || !PC.plan.modifiable || PC.occupe) return;
  PC.occupe = true;
  try {
    PC.plan = await _pcApi('/api/plans-classe', { method: 'PUT', body: JSON.stringify({
      classe_id: PC.classeId, salle_id: PC.salleId, lundi: PC.lundi, placements }) });
  } catch (e) { _pcToast(e.message, true); }
  PC.occupe = false;
  _pcRendreTout();
}

function _pcCopie() {
  return PC.plan.placements.map(p => ({ ...p }));
}

// Place l'élève `eid` à la place `num` (échange si occupée).
function pcPlacer(eid, num) {
  const pl = _pcCopie();
  const moi = pl.find(p => p.eleve_id === eid);
  const autre = pl.find(p => p.numero === num);
  if (autre && autre.eleve_id === eid) return;
  if (autre) {
    if (moi) autre.numero = moi.numero;
    else pl.splice(pl.indexOf(autre), 1);
  }
  if (moi) { moi.numero = num; moi.confirme = 1; }
  else pl.push({ eleve_id: eid, numero: num, statut: 'libre', confirme: 1 });
  PC.sel = null;
  _pcEnregistrer(pl);
}

function pcRetirer(eid) {
  PC.sel = null;
  _pcEnregistrer(_pcCopie().filter(p => p.eleve_id !== eid));
}

function pcBasculerImpose(eid, impose) {
  const pl = _pcCopie();
  const p = pl.find(x => x.eleve_id === eid);
  if (!p) return;
  p.statut = impose ? 'impose' : 'libre';
  p.confirme = 1;
  // Désélectionner : sinon le clic suivant sur un autre élève l'échangerait
  // avec celui-ci (règle « élève puis place occupée = échange »).
  PC.sel = null;
  _pcEnregistrer(pl);
}

function pcToutConfirmer() {
  _pcEnregistrer(_pcCopie().map(p => ({ ...p, confirme: 1 })));
}

async function pcAleatoire() {
  if (!PC.plan || !PC.plan.modifiable) return;
  if (!confirm('Placer au hasard tous les élèves non imposés ?\n\nLes élèves imposés gardent leur place ; '
      + 'les autres sont répartis sur les places restantes et deviennent imposés.')) return;
  try {
    PC.plan = await _pcApi('/api/plans-classe/aleatoire', { method: 'POST', body: JSON.stringify({
      classe_id: PC.classeId, salle_id: PC.salleId, lundi: PC.lundi }) });
  } catch (e) { _pcToast(e.message, true); }
  PC.sel = null;
  _pcRendreTout();
}

async function pcReinitialiser() {
  if (!confirm('Annuler le plan saisi pour cette semaine ?\n\nLa semaine reprendra le plan de la '
      + 'dernière semaine saisie (ou un plan vide).')) return;
  const q = `classe_id=${encodeURIComponent(PC.classeId)}&salle_id=${encodeURIComponent(PC.salleId)}&lundi=${PC.lundi}`;
  try { PC.plan = await _pcApi('/api/plans-classe?' + q, { method: 'DELETE' }); }
  catch (e) { _pcToast(e.message, true); }
  PC.sel = null;
  _pcRendreTout();
}

// Clic (sans glisser) sur un élève ou une place.
function _pcClic(cible) {
  if (!PC.plan) return;
  const eid = cible.dataset.eleve || null;
  const num = cible.dataset.num ? +cible.dataset.num : null;
  if (eid) {
    const occ = PC.plan.placements.find(p => p.eleve_id === eid);
    // Un élève à confirmer se confirme d'un clic (sauf si on veut l'échanger).
    if (occ && !occ.confirme && PC.plan.modifiable && !PC.sel) {
      const pl = _pcCopie();
      pl.find(p => p.eleve_id === eid).confirme = 1;
      PC.sel = eid;
      _pcEnregistrer(pl);
      return;
    }
    if (PC.sel && PC.sel !== eid && num != null && PC.plan.modifiable) {
      pcPlacer(PC.sel, num);              // échange avec l'élève cliqué
      return;
    }
    PC.sel = PC.sel === eid ? null : eid;
  } else if (num != null) {
    if (PC.sel && PC.plan.modifiable) { pcPlacer(PC.sel, num); return; }
  } else if (cible.dataset.liste && PC.sel) {
    if (PC.plan.placements.some(p => p.eleve_id === PC.sel) && PC.plan.modifiable) {
      pcRetirer(PC.sel);
      return;
    }
    PC.sel = null;
  }
  _pcRendrePlan(); _pcRendreCote();
}

// Échap : désélectionner.
document.addEventListener('keydown', evt => {
  const racine = document.getElementById('stab-plans');
  if (evt.key !== 'Escape' || !racine || racine.style.display === 'none' || !PC.sel) return;
  PC.sel = null;
  _pcRendrePlan(); _pcRendreCote();
});

// Glisser-déposer (souris, stylet, doigt) entre la liste et le plan.
document.addEventListener('pointerdown', evt => {
  const racine = document.getElementById('stab-plans');
  if (!racine || racine.style.display === 'none' || !racine.contains(evt.target)) return;
  const cible = evt.target.closest('[data-eleve], [data-num], [data-liste]');
  if (!cible) return;
  PC.drag = { cible, x: evt.clientX, y: evt.clientY, bouge: false,
              eid: cible.dataset.eleve || null, fantome: null };
});

document.addEventListener('pointermove', evt => {
  const d = PC.drag;
  if (!d || !d.eid || !PC.plan || !PC.plan.modifiable) return;
  if (!d.bouge && Math.hypot(evt.clientX - d.x, evt.clientY - d.y) < 6) return;
  if (!d.bouge) {
    d.bouge = true;
    const e = _pcNoms()[d.eid];
    d.fantome = document.createElement('div');
    d.fantome.className = 'pc-fantome';
    d.fantome.textContent = e ? e.etiquette : '';
    document.body.appendChild(d.fantome);
  }
  d.fantome.style.left = (evt.clientX + 8) + 'px';
  d.fantome.style.top = (evt.clientY + 8) + 'px';
});

document.addEventListener('pointerup', evt => {
  const d = PC.drag;
  if (!d) return;
  PC.drag = null;
  if (d.fantome) d.fantome.remove();
  if (!d.bouge) { _pcClic(d.cible); return; }
  const sous = document.elementFromPoint(evt.clientX, evt.clientY);
  const place = sous && sous.closest('[data-num]');
  const liste = sous && sous.closest('[data-liste]');
  if (place) pcPlacer(d.eid, +place.dataset.num);
  else if (liste && PC.plan.placements.some(p => p.eleve_id === d.eid)) pcRetirer(d.eid);
});
