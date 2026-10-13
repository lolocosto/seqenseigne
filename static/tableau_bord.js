// ============================================================================
// static/tableau_bord.js — v0.30.0
// Écran d'accueil : tuiles synthétiques (séances de la semaine, atomes à
// finaliser). Le contenu vient du serveur ; le client ne fait qu'afficher.
// ============================================================================

const TDB_TYPE_LBL = {
  principale: 'Cours', mer_auto: 'MER auto', mer_prog: 'MER prog',
};
const TDB_TYPE_COUL = {
  principale: '#e3eefb', mer_auto: '#cfe3ff', mer_prog: '#d8f0d8',
};
const TDB_JOUR_LBL = { lun: 'Lundi', mar: 'Mardi', mer: 'Mercredi', jeu: 'Jeudi', ven: 'Vendredi' };
const TDB_ATOME_LBL = { notion: 'notions', methode: 'méthodes', exercice: 'exercices', carte: 'cartes', fiche: 'fiches' };

async function tdbInit() {
  // v0.51.0 — Une tuile par côté : séances (classe), atomes (atelier).
  const permet = (c) => (typeof profilPermet === 'function' ? profilPermet(c) : true);
  if (permet('classe')) {
    tdbChargerSeances();
    tdbChargerUsage();          // v0.51.8
  }
  if (permet('atelier')) {
    tdbChargerAtomes();
    tdbChargerNonRattaches();
    tdbChargerPublication();
  }
}

function _tdbAnnee() {
  return (typeof ANNEE_ACTIVE !== 'undefined' && ANNEE_ACTIVE)
    || (typeof anneeScolaireCourante === 'function' ? anneeScolaireCourante() : '');
}

function _tdbDateFr(iso) {
  const m = String(iso || '').match(/^\d{4}-(\d{2})-(\d{2})/);
  return m ? `${m[2]}/${m[1]}` : iso;
}

async function tdbChargerSeances() {
  const zone = document.getElementById('tdb-seances');
  const dates = document.getElementById('tdb-semaine-dates');
  if (!zone) return;
  let d;
  try {
    d = await api('/api/tableau-bord/seances-semaine?annee=' + encodeURIComponent(_tdbAnnee()));
  } catch (e) { zone.innerHTML = '<p style="font-size:12px;color:#c33">Erreur de chargement.</p>'; return; }
  if (dates) dates.textContent = `(${_tdbDateFr(d.lundi)} – ${_tdbDateFr(d.vendredi)})`;
  const jours = (d.jours || []).filter(j => j.seances.length);
  if (!jours.length) {
    zone.innerHTML = '<p style="font-size:13px;color:#999">Aucune séance cette semaine.</p>';
    return;
  }
  zone.innerHTML = jours.map(j => `
    <div style="margin-bottom:8px">
      <div style="font-size:12px;font-weight:600;color:#555">${TDB_JOUR_LBL[j.jour] || j.jour}
        <span style="font-weight:normal;color:#999">${_tdbDateFr(j.date)}</span></div>
      <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:2px">
        ${j.seances.map(s => `
          <span style="font-size:11px;background:${TDB_TYPE_COUL[s.type] || '#eee'};
            border-radius:3px;padding:1px 6px" title="${TDB_TYPE_LBL[s.type] || ''}">
            ${escapeHtml(s.creneau)} ${escapeHtml(s.classe)}</span>`).join('')}
      </div>
    </div>`).join('');
}

async function tdbChargerAtomes() {
  const zone = document.getElementById('tdb-atomes');
  if (!zone) return;
  let d;
  try {
    d = await api('/api/tableau-bord/atomes-en-cours');
  } catch (e) { zone.innerHTML = '<p style="font-size:12px;color:#c33">Erreur de chargement.</p>'; return; }
  const niveaux = (d.niveaux || []).filter(n => n.total > 0);
  if (!niveaux.length) {
    zone.innerHTML = '<p style="font-size:13px;color:#4a7">Rien à finaliser : tous les atomes sont validés.</p>';
    return;
  }
  zone.innerHTML = niveaux.map(n => {
    // Chaque type est cliquable : ouvre l'atelier de ce type, toutes séquences,
    // filtre « en cours ». stopPropagation pour ne pas déclencher le clic du niveau.
    const detail = Object.entries(n.par_type).map(([t, c]) =>
      `<a href="#" onclick="event.stopPropagation();ouvrirAtelierAtomesEnCours('${escapeHtml(n.niveau)}','${escapeHtml(t)}');return false"
         style="color:#666;text-decoration:none;border-bottom:1px dotted #bbb"
         title="Ouvrir l'atelier ${TDB_ATOME_LBL[t] || t} en cours — ${escapeHtml(n.niveau_label)}"
         >${c} ${TDB_ATOME_LBL[t] || t}</a>`).join(' · ');
    return `<div style="padding:5px 4px;border-bottom:1px solid var(--border);border-radius:4px">
      <div onclick="ouvrirAtelierNiveau('${escapeHtml(n.niveau)}')"
        title="Ouvrir l'atelier de conception — ${escapeHtml(n.niveau_label)}"
        style="display:flex;justify-content:space-between;font-size:13px;cursor:pointer"
        onmouseover="this.style.opacity='0.7'" onmouseout="this.style.opacity=''">
        <strong>${escapeHtml(n.niveau_label)}</strong>
        <span style="color:#c60">${n.total} en cours ›</span>
      </div>
      <div style="font-size:11px;color:#888;margin-top:2px">${detail}</div>
    </div>`;
  }).join('');
}

// v0.30.1 — Barre d'actions : ouvre l'onglet Préférences (où vivent les
// paramètres ; la configuration de la barre pourra y être ajoutée plus tard).
function tdbOuvrirParametres() {
  // v0.42.0 — Les Préférences sont dans l'onglet « Système ».
  try { localStorage.setItem('systeme-sous-onglet', 'preferences'); } catch (e) {}
  const btn = document.querySelector('[data-tab="systeme"]');
  if (btn) btn.click();
}
window.tdbOuvrirParametres = tdbOuvrirParametres;

// v0.31.1 — Tuile « Éléments non rattachés » : par niveau, atomes non liés à un
// objectif, par type. Chaque type est cliquable → atelier, toutes séquences,
// filtre « Non rattachés » pré-activé.
async function tdbChargerNonRattaches() {
  const zone = document.getElementById('tdb-non-rattaches');
  if (!zone) return;
  let d;
  try {
    d = await api('/api/tableau-bord/atomes-non-rattaches');
  } catch (e) { zone.innerHTML = '<p style="font-size:12px;color:#c33">Erreur de chargement.</p>'; return; }
  const niveaux = (d.niveaux || []).filter(n => n.total > 0);
  if (!niveaux.length) {
    zone.innerHTML = '<p style="font-size:13px;color:#4a7">Tout est rattaché.</p>';
    return;
  }
  zone.innerHTML = niveaux.map(n => {
    const detail = Object.entries(n.par_type).map(([t, c]) =>
      `<a href="#" onclick="event.stopPropagation();ouvrirAtelierAtomesNonRattaches('${escapeHtml(n.niveau)}','${escapeHtml(t)}');return false"
         style="color:#666;text-decoration:none;border-bottom:1px dotted #bbb"
         title="Ouvrir l'atelier ${TDB_ATOME_LBL[t] || t} non rattachés — ${escapeHtml(n.niveau_label)}"
         >${c} ${TDB_ATOME_LBL[t] || t}</a>`).join(' · ');
    return `<div style="padding:5px 4px;border-bottom:1px solid var(--border);border-radius:4px">
      <div style="display:flex;justify-content:space-between;font-size:13px">
        <strong>${escapeHtml(n.niveau_label)}</strong>
        <span style="color:#a06">${n.total} à rattacher</span>
      </div>
      <div style="font-size:11px;color:#888;margin-top:2px">${detail}</div>
    </div>`;
  }).join('');
}


// ── v0.51.2 — Tuile « Publication » (profil atelier) ─────────────────────────
// Référentiels publiables (internes verrouillés/utilisés, externes non
// annulés), groupés par niveau : dernière publication, « modifié depuis »,
// format invalide. Les cases cochées forment le paquet (zip) téléchargé.
const TDB_PUB = { sel: new Set(), liste: [] };

function _tdbDateHeure(iso) {
  const m = String(iso || '').match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  return m ? `${m[3]}/${m[2]}/${m[1]} ${m[4]}h${m[5]}` : (iso || '');
}

async function tdbChargerPublication() {
  const zone = document.getElementById('tdb-publication');
  if (!zone) return;
  zone.innerHTML = '<p style="font-size:12px;color:#888">Calcul des empreintes…</p>';
  let d;
  try {
    d = await api('/api/publication/publiables');
  } catch (e) {
    zone.innerHTML = '<p style="font-size:12px;color:#c33">Erreur de chargement.</p>';
    return;
  }
  TDB_PUB.liste = d.referentiels || [];
  const ids = new Set(TDB_PUB.liste.map(r => r.id));
  TDB_PUB.sel = new Set([...TDB_PUB.sel].filter(i => ids.has(i)));
  if (!TDB_PUB.liste.length) {
    zone.innerHTML = '<p style="font-size:13px;color:#888">Aucun référentiel publiable '
      + '(internes verrouillés ou utilisés, externes).</p>';
    return;
  }
  const parNiveau = {};
  TDB_PUB.liste.forEach(r => (parNiveau[r.niveau] = parNiveau[r.niveau] || []).push(r));
  const badge = r => {
    if (!r.valide) return `<span class="tdb-pub-badge ko" title="${escapeHtml((r.erreurs || []).join(' ; '))}">format invalide</span>`;
    if (!r.derniere_publication) return '<span class="tdb-pub-badge neuf">jamais publié</span>';
    // v0.51.8 — État de synchronisation avec l'appli en ligne.
    const s = r.synchro || {};
    if (s.etat && s.etat !== 'non_publie') {
      const titre = `Publié le ${_tdbDateHeure(s.publie_le)}${s.publie_numero ? ' (paquet n° ' + s.publie_numero + ')' : ''}`
        + (s.usage_recu_le ? ` — dernier retour d'usage le ${_tdbDateHeure(s.usage_recu_le)}` : ' — aucun retour d\'usage');
      return `<span class="tdb-pub-badge sync-${s.etat}" title="${escapeHtml(titre)}">${escapeHtml(s.libelle)}</span>`;
    }
    const date = _tdbDateHeure(r.derniere_publication.cree_le);
    return r.modifie_depuis
      ? `<span class="tdb-pub-badge modif" title="Publié le ${escapeHtml(date)}">modifié depuis</span>`
      : `<span class="tdb-pub-badge ok">publié le ${escapeHtml(date)}</span>`;
  };
  const journal = (d.journal || []).map(j => `<li>${j.numero ? 'n° ' + j.numero + ' — ' : ''}${escapeHtml(_tdbDateHeure(j.cree_le))} —
      ${escapeHtml(j.nom_paquet)} : ${j.referentiels.map(r => escapeHtml(r.nom)).join(', ')}</li>`).join('');
  zone.innerHTML = Object.keys(parNiveau).sort().map(n => `
      <div class="tdb-pub-niveau">${escapeHtml(n)}</div>
      ${parNiveau[n].map(r => `<label class="tdb-pub-ligne">
        <input type="checkbox" ${r.valide ? '' : 'disabled'} ${TDB_PUB.sel.has(r.id) ? 'checked' : ''}
          onchange="tdbPubCocher('${escapeHtml(r.id)}', this.checked)">
        <span class="tdb-pub-nom">${escapeHtml(r.nom)}</span>${badge(r)}</label>`).join('')}`).join('')
    + `<div class="tdb-pub-actions">
        <button class="btn-sm" type="button" onclick="tdbPubCocherModifies()">Cocher les non publiés et modifiés</button>
        <button class="btn-prim" type="button" id="tdb-pub-creer" onclick="tdbPubCreer()">Créer le paquet</button>
      </div>
      <div id="tdb-pub-res" class="tdb-pub-res" role="status" aria-live="polite"></div>`
    + (journal ? `<details class="tdb-pub-journal"><summary>Dernières publications</summary><ul>${journal}</ul></details>` : '')
    + `<div class="tdb-usage-import">
        <label class="btn-sm">Importer un retour d'usage…<input type="file" accept=".json,application/json"
          style="display:none" onchange="tdbUsageImporter(this)"></label>
        <span id="tdb-usage-import-res" class="tdb-pub-res" role="status" aria-live="polite"></span>
      </div>`
    + '<div id="tdb-depot"></div><div id="tdb-echanges"></div>';
  // v0.51.7 — Identité, appli en ligne liée, paquets numérotés (renvoi).
  if (typeof echRendre === 'function') echRendre('tdb-echanges', 'atelier');
  // v0.51.9 — Boîte aux lettres (retours d'usage déposés).
  if (typeof depotRendre === 'function') depotRendre('tdb-depot');
}

function tdbPubCocher(id, oui) {
  if (oui) TDB_PUB.sel.add(id); else TDB_PUB.sel.delete(id);
}

function tdbPubCocherModifies() {
  TDB_PUB.liste.filter(r => r.valide && (!r.derniere_publication || r.modifie_depuis))
    .forEach(r => TDB_PUB.sel.add(r.id));
  tdbChargerPublication();
}

async function tdbPubCreer() {
  const res = document.getElementById('tdb-pub-res');
  const ids = [...TDB_PUB.sel];
  if (!ids.length) { if (res) res.textContent = 'Cochez au moins un référentiel.'; return; }
  if (res) res.textContent = 'Création du paquet…';
  try {
    const r = await fetch('/api/publication/paquet', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ referentiels: ids }) });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      const err = ((d.rapport || {}).erreurs || []).slice(0, 6).map(escapeHtml).join('<br>');
      if (res) res.innerHTML = `<span class="tdb-pub-ko">✗ ${escapeHtml(d.error || 'Erreur')}</span>`
        + (err ? '<br>' + err : '');
      return;
    }
    let resume = {};
    try { resume = JSON.parse(r.headers.get('X-Paquet-Resume') || '{}'); } catch (e) {}
    const blob = await r.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = resume.nom || 'paquet.zip';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    TDB_PUB.sel.clear();
    await tdbChargerPublication();
    const res2 = document.getElementById('tdb-pub-res');
    if (res2) res2.innerHTML = `<span class="tdb-pub-ok">✓ ${escapeHtml(resume.nom || 'Paquet créé')}</span> — `
      + `${resume.nb_referentiels} référentiel(s), ${resume.nb_fichiers} fichier(s), `
      + `${(resume.taille / 1048576).toFixed(1)} Mo`
      + (resume.documents_sans_pdf ? ` — ${resume.documents_sans_pdf} document(s) sans PDF non publiés` : '')
      + (resume.parties_ecart ? ` — <span class="tdb-pub-ko">${resume.parties_ecart} partie(s) dont la durée saisie diffère des objectifs</span>` : '');
  } catch (e) {
    if (res) res.textContent = e.message;
  }
}
window.tdbPubCocher = tdbPubCocher;
window.tdbPubCocherModifies = tdbPubCocherModifies;
window.tdbPubCreer = tdbPubCreer;

// ── v0.51.8 — Retour d'usage ────────────────────────────────────────────────

// Atelier : import d'un retour d'usage (séquence stricte, acquittements).
async function tdbUsageImporter(input) {
  const f = input.files && input.files[0];
  const res = document.getElementById('tdb-usage-import-res');
  if (!f) return;
  const fd = new FormData();
  fd.append('fichier', f);
  if (res) res.textContent = 'Import…';
  try {
    const r = await fetch('/api/retour-usage/importer', { method: 'POST', body: fd });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || 'Erreur');
    const nouv = (d.referentiels || []).reduce((n, x) => n + (x.nouvelles_sequences || []).length
      + (x.nouvelles_parties_mer || []).length, 0);
    const parts = [`Retour ${escapeHtml(d.nom || '')} importé : ${(d.referentiels || []).length} référentiel(s)`];
    if (nouv) parts.push(`${nouv} nouvelle(s) séquence(s) ou partie(s) de MER en usage`);
    if ((d.paquets_acquittes || []).length) parts.push(`paquet(s) n° ${d.paquets_acquittes.join(', ')} acquitté(s)`);
    if ((d.inconnus || []).length) parts.push(`${d.inconnus.length} référentiel(s) inconnu(s) ici : ${d.inconnus.map(escapeHtml).join(', ')}`);
    if (res) res.innerHTML = '✓ ' + parts.join(' ; ') + '.';
    await tdbChargerPublication();
    const res2 = document.getElementById('tdb-usage-import-res');
    if (res2) res2.innerHTML = '✓ ' + parts.join(' ; ') + '.';
  } catch (e) {
    if (res) res.innerHTML = `<span class="tdb-pub-ko">✗ ${escapeHtml(e.message)}</span>`;
  }
  input.value = '';
}

// Classe : contenu du prochain retour, création (téléchargement), échanges.
async function tdbChargerUsage() {
  const zone = document.getElementById('tdb-usage');
  if (!zone) return;
  let d;
  try { d = await api('/api/retour-usage/apercu'); }
  catch (e) { zone.innerHTML = '<p style="font-size:12px;color:#c33">Erreur de chargement.</p>'; return; }
  const refs = d.referentiels || [];
  const lignes = refs.map(r => `<li><b>${escapeHtml(r.nom || r.id)}</b> —
      ${r.utilise ? `utilisé${r.utilise_depuis ? ' depuis le ' + escapeHtml(_tdbDateFr(r.utilise_depuis)) : ''}` : 'non utilisé'}
      ${r.sequences.length ? ` · ${r.sequences.length} séquence(s) planifiée(s)` : ''}
      ${r.parties_mer.length ? ` · ${r.parties_mer.length} partie(s) de MER posée(s)` : ''}</li>`).join('');
  zone.innerHTML = `<p style="font-size:12px;color:var(--text-secondary);margin:0 0 6px">
      Indique à l'appli locale quels référentiels sont utilisés et quelles séquences sont
      planifiées (date du premier créneau), pour qu'elle les verrouille. Aucune donnée d'élève,
      de classe ni d'établissement.</p>
    ${refs.length ? `<ul class="tdb-usage-liste">${lignes}</ul>` : '<p style="font-size:13px;color:#888">Aucun référentiel importé.</p>'}
    <div class="tdb-pub-actions"><button class="btn-prim" type="button" onclick="tdbUsageCreer()">Créer le retour d'usage (n° ${d.echange.numero})</button></div>
    <div id="tdb-usage-res" class="tdb-pub-res" role="status" aria-live="polite"></div>
    <div id="tdb-usage-depot"></div><div id="tdb-usage-ech"></div>`;
  if (typeof echRendre === 'function') echRendre('tdb-usage-ech', 'classe');
  if (typeof depotRendre === 'function') depotRendre('tdb-usage-depot');   // v0.51.9
}

async function tdbUsageCreer() {
  const res = document.getElementById('tdb-usage-res');
  try {
    const r = await fetch('/api/retour-usage/creer', { method: 'POST' });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || 'Erreur');
    const resume = JSON.parse(r.headers.get('X-Usage-Resume') || '{}');
    const blob = await r.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = resume.nom || 'usage.json';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    await tdbChargerUsage();
    const res2 = document.getElementById('tdb-usage-res');
    if (res2) res2.textContent = `✓ ${resume.nom} créé (${resume.nb_referentiels} référentiel(s)) : importez-le dans l'appli locale (tableau de bord › Publication).`;
  } catch (e) {
    if (res) res.innerHTML = `<span class="tdb-pub-ko">✗ ${escapeHtml(e.message)}</span>`;
  }
}

window.tdbUsageImporter = tdbUsageImporter;
window.tdbChargerUsage = tdbChargerUsage;
window.tdbUsageCreer = tdbUsageCreer;
