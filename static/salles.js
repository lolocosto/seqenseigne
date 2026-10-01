// ============================================================================
// static/salles.js — v0.37.0
// Salles d'un établissement (liste dans la carte établissement) et éditeur
// libre de plan de salle (panneau plein écran, SVG).
// Logique géométrique pure : static/salles_pur.js (window.SallesPur).
// Backend : /api/etablissements/<id>/salles (GET/POST),
//           /api/salles/<id> (PUT/DELETE), /api/salles/<id>/versions (GET),
//           /api/salles/<id>/plan (GET/PUT), /api/salles/versions/<id> (DELETE).
// ============================================================================

const _SALLES_OUVERTES = {};   // etabId -> bool

function _salE(s) { return escapeHtml(String(s == null ? '' : s)); }

function _salToast(msg, erreur) {
  if (typeof showToast === 'function') showToast(msg, !!erreur);
  else if (erreur) alert(msg);
}

async function _salApi(path, opts = {}) {
  const r = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...opts });
  let data = {};
  try { data = await r.json(); } catch (e) { /* corps vide */ }
  if (!r.ok) throw new Error(data.error || ('Erreur ' + r.status));
  return data;
}

function _salDateFr(iso) {
  if (!iso) return '';
  const [a, m, j] = iso.split('-');
  return `${j}/${m}/${a}`;
}

// ── Liste des salles (dans la carte établissement) ──────────────────────────

async function sallesToggle(etabId) {
  const zone = document.getElementById('etab-salles-' + etabId);
  if (!zone) return;
  if (_SALLES_OUVERTES[etabId] && zone.style.display !== 'none') {
    zone.style.display = 'none';
    _SALLES_OUVERTES[etabId] = false;
    return;
  }
  _SALLES_OUVERTES[etabId] = true;
  zone.style.display = '';
  zone.innerHTML = '<p class="sal-vide">Chargement…</p>';
  await sallesCharger(etabId);
}

async function sallesCharger(etabId) {
  const zone = document.getElementById('etab-salles-' + etabId);
  if (!zone) return;
  try {
    const r = await _salApi('/api/etablissements/' + etabId + '/salles');
    sallesRender(etabId, r.salles || []);
  } catch (e) {
    zone.innerHTML = `<p class="sal-erreur">Chargement des salles impossible : ${_salE(e.message)}</p>`;
  }
}

function sallesRender(etabId, salles) {
  const zone = document.getElementById('etab-salles-' + etabId);
  if (!zone) return;
  const lignes = salles.map(s => {
    const etat = s.archivee ? '<span class="sal-etat sal-etat-archivee">Non utilisée cette année</span>'
      : (s.utilisee ? '<span class="sal-etat sal-etat-utilisee">À l\'emploi du temps</span>' : '');
    const supprimer = s.utilisee
      ? `<button class="btn-sm" disabled title="Salle présente à l'emploi du temps : archiver plutôt que supprimer">Supprimer</button>`
      : `<button class="btn-sm sal-danger" onclick="salleSupprimer('${etabId}','${s.id}')">Supprimer</button>`;
    return `
      <tr class="${s.archivee ? 'sal-ligne-archivee' : ''}">
        <td><input class="sal-nom" value="${_salE(s.nom)}" aria-label="Nom de la salle"
                   onchange="salleRenommer('${etabId}','${s.id}', this.value)"></td>
        <td class="sal-nb">${s.nb_places} place${s.nb_places > 1 ? 's' : ''}</td>
        <td>${etat}</td>
        <td class="sal-actions">
          <button class="btn-sm btn-prim" onclick="salleEditeurOuvrir('${etabId}','${s.id}')">Plan</button>
          <button class="btn-sm" onclick="salleArchiver('${etabId}','${s.id}', ${!s.archivee})">${s.archivee ? 'Réactiver' : 'Archiver'}</button>
          ${supprimer}
        </td>
      </tr>`;
  }).join('');
  zone.innerHTML = `
    <div class="sal-titre">Salles</div>
    <p class="sal-aide">Une salle à l'emploi du temps ne peut plus être supprimée ;
      son plan ne se modifie alors qu'à partir de la semaine prochaine.</p>
    ${salles.length ? `<table class="sal-table"><tbody>${lignes}</tbody></table>`
                    : '<p class="sal-vide">Aucune salle. Ajoutez celles où vous faites cours.</p>'}
    <div class="sal-ajout">
      <input id="sal-new-${etabId}" placeholder="Nom (ex : 302)" aria-label="Nom de la nouvelle salle"
             onkeydown="if(event.key==='Enter') salleAjouter('${etabId}')">
      <button class="btn-sm" onclick="salleAjouter('${etabId}')">Ajouter la salle</button>
    </div>`;
}

async function salleAjouter(etabId) {
  const inp = document.getElementById('sal-new-' + etabId);
  const nom = (inp && inp.value || '').trim();
  if (!nom) { inp && inp.focus(); return; }
  try {
    await _salApi('/api/etablissements/' + etabId + '/salles',
                  { method: 'POST', body: JSON.stringify({ nom }) });
    await sallesCharger(etabId);
    _salToast(`Salle ${nom} ajoutée.`);
  } catch (e) { _salToast(e.message, true); }
}

async function salleRenommer(etabId, salleId, nom) {
  try {
    await _salApi('/api/salles/' + salleId, { method: 'PUT', body: JSON.stringify({ nom }) });
    _salToast('Salle renommée.');
  } catch (e) { _salToast(e.message, true); }
  await sallesCharger(etabId);
}

async function salleArchiver(etabId, salleId, archivee) {
  try {
    await _salApi('/api/salles/' + salleId,
                  { method: 'PUT', body: JSON.stringify({ archivee }) });
    await sallesCharger(etabId);
  } catch (e) { _salToast(e.message, true); }
}

async function salleSupprimer(etabId, salleId) {
  if (!confirm('Supprimer cette salle et son plan ?')) return;
  try {
    await _salApi('/api/salles/' + salleId, { method: 'DELETE' });
    await sallesCharger(etabId);
    _salToast('Salle supprimée.');
  } catch (e) { _salToast(e.message, true); }
}

// ── Éditeur de plan ─────────────────────────────────────────────────────────

const SAL = {
  etabId: null, salleId: null, plan: null, versions: [],
  places: [], sel: [], dirty: false,
  cible: null,          // {version_id} ou {date_effet} : où enregistrer
  modifiable: false,
  drag: null, cadreFige: null,
};

async function salleEditeurOuvrir(etabId, salleId) {
  SAL.etabId = etabId; SAL.salleId = salleId;
  let ov = document.getElementById('sal-editeur');
  if (!ov) {
    ov = document.createElement('div');
    ov.id = 'sal-editeur';
    ov.setAttribute('role', 'dialog');
    ov.setAttribute('aria-modal', 'true');
    document.body.appendChild(ov);
  }
  ov.style.display = '';
  document.addEventListener('keydown', _salClavier);
  await _salChargerPlan(null);
}

async function _salChargerPlan(versionId) {
  const q = versionId ? '?version_id=' + encodeURIComponent(versionId) : '';
  try {
    const [plan, vs] = await Promise.all([
      _salApi('/api/salles/' + SAL.salleId + '/plan' + q),
      _salApi('/api/salles/' + SAL.salleId + '/versions'),
    ]);
    SAL.plan = plan; SAL.versions = vs.versions || [];
    SAL.places = plan.places.map(p => ({ ...p }));
    SAL.sel = []; SAL.dirty = false;
    SAL.modifiable = plan.version.modifiable;
    SAL.cible = { version_id: plan.version.id };
    SAL.cadreFige = null;
    _salRendre();
  } catch (e) {
    _salToast(e.message, true);
  }
}

function salleEditeurFermer() {
  if (SAL.dirty && !confirm('Fermer sans enregistrer les modifications du plan ?')) return;
  const ov = document.getElementById('sal-editeur');
  if (ov) ov.style.display = 'none';
  document.removeEventListener('keydown', _salClavier);
  SAL.dirty = false;
  if (SAL.etabId) sallesCharger(SAL.etabId);
}

function _salLibelleVersion(v) {
  const quand = v.date_effet ? 'À partir du ' + _salDateFr(v.date_effet) : 'Plan initial';
  const st = { en_vigueur: 'en vigueur', future: 'à venir', passee: 'passée' }[v.statut] || '';
  return `${quand} (${st})`;
}

function _salRendre() {
  const ov = document.getElementById('sal-editeur');
  if (!ov || !SAL.plan) return;
  const s = SAL.plan.salle;
  const optsV = SAL.versions.map(v =>
    `<option value="${v.id}"${SAL.cible.version_id === v.id ? ' selected' : ''}>${_salE(_salLibelleVersion(v))}</option>`).join('');
  const nouvelle = SAL.cible.date_effet
    ? `<option value="" selected>Nouvelle version au ${_salDateFr(SAL.cible.date_effet)}</option>` : '';
  const versionFuture = !SAL.cible.date_effet && SAL.plan.version.statut === 'future';
  const peutNouvelle = s.utilisee && !SAL.cible.date_effet;
  const dis = SAL.modifiable ? '' : ' disabled';
  const nSel = SAL.sel.length;

  ov.innerHTML = `
    <div class="sal-ed-entete">
      <h2>Plan de la salle ${_salE(s.nom)}</h2>
      <label class="sal-ed-version">Version
        <select onchange="_salChoisirVersion(this.value)">${nouvelle}${optsV}</select>
      </label>
      ${peutNouvelle ? `
        <span class="sal-ed-nouvelle">
          <input type="date" id="sal-date-effet" min="${SAL.plan.date_effet_min}" step="7"
                 value="${SAL.plan.date_effet_min}" aria-label="Lundi de prise d'effet">
          <button class="btn-sm" onclick="_salNouvelleVersion()">Préparer une nouvelle version</button>
        </span>` : ''}
      ${versionFuture && s.utilisee ? `<button class="btn-sm sal-danger" onclick="_salSupprimerVersion()">Supprimer cette version</button>` : ''}
      <span class="sal-ed-espace"></span>
      <button class="btn-prim" onclick="_salEnregistrer()"${dis}${SAL.dirty ? '' : ' aria-disabled="true"'}>Enregistrer le plan</button>
      <button class="btn-sm" onclick="salleEditeurFermer()">Fermer</button>
    </div>
    ${SAL.modifiable ? '' : `<p class="sal-ed-lecture">Cette version est ${SAL.plan.version.statut === 'passee' ? 'passée' : 'en vigueur'} et la salle est à l'emploi du temps : elle ne se modifie plus. Préparez une nouvelle version à partir d'un lundi à venir.</p>`}
    <div class="sal-ed-outils" role="toolbar" aria-label="Outils du plan">
      <span class="sal-ed-groupe">Ajouter
        <button class="btn-sm" onclick="_salAjouter('place')"${dis}>Une place</button>
        <button class="btn-sm" onclick="_salAjouter('ilot2')"${dis}>Îlot de 2</button>
        <button class="btn-sm" onclick="_salAjouter('ilot4')"${dis}>Îlot de 4</button>
      </span>
      <span class="sal-ed-groupe">Sélection
        <button class="btn-sm" onclick="_salTourner(-5)" title="Pivoter de 5° (Maj+R)"${nSel && SAL.modifiable ? '' : ' disabled'}>⟲ 5°</button>
        <button class="btn-sm" onclick="_salTourner(5)" title="Pivoter de 5° (R)"${nSel && SAL.modifiable ? '' : ' disabled'}>⟳ 5°</button>
        <button class="btn-sm" onclick="_salTourner(90)" title="Quart de tour"${nSel && SAL.modifiable ? '' : ' disabled'}>⟳ 90°</button>
        <button class="btn-sm" onclick="_salGrouper()"${nSel > 1 && SAL.modifiable ? '' : ' disabled'}>Grouper en îlot</button>
        <button class="btn-sm" onclick="_salDegrouper()"${nSel && SAL.modifiable ? '' : ' disabled'}>Dégrouper</button>
        <button class="btn-sm sal-danger" onclick="_salSupprimerSel()"${nSel && SAL.modifiable ? '' : ' disabled'}>Supprimer</button>
      </span>
      <span class="sal-ed-compte">${SAL.places.length} place${SAL.places.length > 1 ? 's' : ''}${nSel ? `, ${nSel} sélectionnée${nSel > 1 ? 's' : ''}` : ''}${SAL.dirty ? ', non enregistré' : ''}</span>
    </div>
    <p class="sal-ed-aide">Un clic sélectionne l'îlot entier, Alt+clic une seule place, Maj+clic ajoute à la sélection.
      Glisser pour déplacer : les places s'aimantent bord à bord. Flèches pour ajuster, R pour pivoter, Suppr pour retirer.</p>
    <div class="sal-ed-zone">${_salSvg()}</div>`;
  _salBrancherSvg();
}

function _salSvg() {
  const S = window.SallesPur;
  const c = SAL.cadreFige || S.cadre(SAL.places);
  const largTab = Math.min(300, c.w * 0.5);
  const xTab = c.x + (c.w - largTab) / 2;
  const tableau = `
    <g class="sal-tableau" aria-hidden="true">
      <rect x="${xTab}" y="${c.y + 8}" width="${largTab}" height="10" rx="2"></rect>
      <text x="${xTab + largTab / 2}" y="${c.y + 34}">Tableau</text>
    </g>`;
  const places = SAL.places.map((p, i) => {
    const sel = SAL.sel.includes(i);
    return `
      <g class="sal-place${sel ? ' sal-sel' : ''}${p.ilot ? '' : ' sal-isolee'}" data-i="${i}">
        <rect x="${-S.L / 2}" y="${-S.H / 2}" width="${S.L}" height="${S.H}" rx="2"
              transform="translate(${p.x} ${p.y}) rotate(${p.angle || 0})"></rect>
        <text x="${p.x}" y="${p.y}">${p.numero == null ? '+' : p.numero}</text>
      </g>`;
  }).join('');
  return `<svg id="sal-svg" viewBox="${c.x} ${c.y} ${c.w} ${c.h}"
               preserveAspectRatio="xMidYMin meet" role="img"
               aria-label="Plan de la salle, tableau en haut">
            <rect class="sal-fond" x="${c.x}" y="${c.y}" width="${c.w}" height="${c.h}"></rect>
            ${tableau}${places}
          </svg>`;
}

function _salPoint(svg, evt) {
  const pt = svg.createSVGPoint();
  pt.x = evt.clientX; pt.y = evt.clientY;
  const m = svg.getScreenCTM();
  return m ? pt.matrixTransform(m.inverse()) : { x: 0, y: 0 };
}

function _salBrancherSvg() {
  const svg = document.getElementById('sal-svg');
  if (!svg) return;
  svg.addEventListener('pointerdown', evt => {
    const g = evt.target.closest('.sal-place');
    if (!g) {
      if (SAL.sel.length) { SAL.sel = []; _salRendre(); }
      return;
    }
    const i = +g.dataset.i;
    const S = window.SallesPur;
    const clic = S.selectionDuClic(SAL.places, i, evt.altKey);
    if (evt.shiftKey) {
      const tous = SAL.sel.includes(i) ? SAL.sel.filter(k => !clic.includes(k))
                                       : [...new Set([...SAL.sel, ...clic])];
      SAL.sel = tous;
    } else if (!SAL.sel.includes(i)) {
      SAL.sel = clic;
    }
    if (!SAL.modifiable || !SAL.sel.length) { _salRendre(); return; }
    const p0 = _salPoint(svg, evt);
    SAL.cadreFige = S.cadre(SAL.places);
    SAL.drag = { x0: p0.x, y0: p0.y, base: SAL.places, bouge: false, id: evt.pointerId };
    _salRendre();
    const svg2 = document.getElementById('sal-svg');
    svg2.setPointerCapture && svg2.setPointerCapture(evt.pointerId);
    evt.preventDefault();
  });
}

document.addEventListener('pointermove', evt => {
  if (!SAL.drag) return;
  const svg = document.getElementById('sal-svg');
  if (!svg) return;
  const p = _salPoint(svg, evt);
  const dx = p.x - SAL.drag.x0, dy = p.y - SAL.drag.y0;
  if (!SAL.drag.bouge && Math.hypot(dx, dy) < 1) return;
  SAL.drag.bouge = true;
  SAL.places = window.SallesPur.deplacer(SAL.drag.base, SAL.sel, dx, dy);
  // Mise à jour légère : seules les positions des places sélectionnées.
  for (const i of SAL.sel) {
    const g = svg.querySelector(`.sal-place[data-i="${i}"]`);
    if (!g) continue;
    const q = SAL.places[i];
    g.querySelector('rect').setAttribute('transform', `translate(${q.x} ${q.y}) rotate(${q.angle || 0})`);
    const t = g.querySelector('text');
    t.setAttribute('x', q.x); t.setAttribute('y', q.y);
  }
});

document.addEventListener('pointerup', () => {
  if (!SAL.drag) return;
  const bouge = SAL.drag.bouge;
  SAL.drag = null;
  if (bouge) {
    const S = window.SallesPur;
    const [ax, ay] = S.aimanter(SAL.places, SAL.sel);
    SAL.places = S.deplacer(SAL.places, SAL.sel, ax, ay);
    SAL.dirty = true;
  }
  SAL.cadreFige = null;
  _salRendre();
});

function _salModifier(nouvelles, sel) {
  if (!SAL.modifiable) return;
  SAL.places = nouvelles;
  if (sel) SAL.sel = sel;
  SAL.dirty = true;
  _salRendre();
}

function _salAjouter(type) {
  const S = window.SallesPur;
  const [x, y] = S.pointAjout(SAL.places);
  const neuves = S.modele(type, x, y, SAL.places);
  const debut = SAL.places.length;
  _salModifier([...SAL.places, ...neuves], neuves.map((_, k) => debut + k));
}

function _salTourner(delta) {
  if (!SAL.sel.length) return;
  _salModifier(window.SallesPur.tourner(SAL.places, SAL.sel, delta));
}

function _salGrouper() {
  _salModifier(window.SallesPur.grouper(SAL.places, SAL.sel));
}

function _salDegrouper() {
  _salModifier(window.SallesPur.degrouper(SAL.places, SAL.sel));
}

function _salSupprimerSel() {
  if (!SAL.sel.length) return;
  _salModifier(SAL.places.filter((_, i) => !SAL.sel.includes(i)), []);
}

function _salClavier(evt) {
  const ov = document.getElementById('sal-editeur');
  if (!ov || ov.style.display === 'none') return;
  const tag = (evt.target && evt.target.tagName) || '';
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes(tag)) return;
  if (evt.key === 'Escape') {
    if (SAL.sel.length) { SAL.sel = []; _salRendre(); } else salleEditeurFermer();
    return;
  }
  if (!SAL.modifiable || !SAL.sel.length) return;
  const pas = evt.shiftKey ? 10 : 1;
  const fleches = { ArrowLeft: [-pas, 0], ArrowRight: [pas, 0], ArrowUp: [0, -pas], ArrowDown: [0, pas] };
  if (fleches[evt.key]) {
    const [dx, dy] = fleches[evt.key];
    _salModifier(window.SallesPur.deplacer(SAL.places, SAL.sel, dx, dy));
    evt.preventDefault();
  } else if (evt.key === 'r' || evt.key === 'R') {
    _salTourner(evt.shiftKey ? -5 : 5);
    evt.preventDefault();
  } else if (evt.key === 'Delete' || evt.key === 'Backspace') {
    _salSupprimerSel();
    evt.preventDefault();
  }
}

async function _salChoisirVersion(versionId) {
  if (!versionId) return;
  if (SAL.dirty && !confirm('Abandonner les modifications non enregistrées ?')) { _salRendre(); return; }
  await _salChargerPlan(versionId);
}

function _salNouvelleVersion() {
  const inp = document.getElementById('sal-date-effet');
  const v = inp && inp.value;
  if (!v) return;
  const d = new Date(v + 'T12:00:00');
  if (d.getDay() !== 1) { _salToast('La date d\'effet doit être un lundi.', true); return; }
  if (v < SAL.plan.date_effet_min) {
    _salToast('Une nouvelle version prend effet au plus tôt le ' + _salDateFr(SAL.plan.date_effet_min) + '.', true);
    return;
  }
  // Part du plan affiché ; numéros conservés (identifiants stables des places).
  SAL.cible = { date_effet: v };
  SAL.modifiable = true;
  SAL.dirty = true;
  _salRendre();
}

async function _salSupprimerVersion() {
  if (!confirm('Supprimer cette version à venir du plan ?')) return;
  try {
    await _salApi('/api/salles/versions/' + SAL.plan.version.id, { method: 'DELETE' });
    SAL.dirty = false;
    await _salChargerPlan(null);
    _salToast('Version supprimée.');
  } catch (e) { _salToast(e.message, true); }
}

async function _salEnregistrer() {
  if (!SAL.modifiable) return;
  const corps = { places: window.SallesPur.serialiser(SAL.places), ...SAL.cible };
  try {
    const plan = await _salApi('/api/salles/' + SAL.salleId + '/plan',
                               { method: 'PUT', body: JSON.stringify(corps) });
    SAL.dirty = false;
    await _salChargerPlan(plan.version.id);
    _salToast('Plan enregistré.');
  } catch (e) { _salToast(e.message, true); }
}

// Fermeture de l'onglet avec un plan non enregistré.
window.addEventListener('beforeunload', evt => {
  if (SAL.dirty) { evt.preventDefault(); evt.returnValue = ''; }
});
