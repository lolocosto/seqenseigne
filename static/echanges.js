// ============================================================================
// static/echanges.js — v0.51.7
// Protocole d'échange atelier ↔ classe (services/echanges.py) : identité de
// cette instance (nom modifiable), correspondant lié, envois numérotés
// (renvoi d'un envoi archivé), prochain numéro attendu.
//   echRendre(zoneId, type) — type : 'paquet' côté atelier (envois),
//                              'paquet' côté classe (réceptions), selon
//                              le rôle donné en 3e argument.
// Routes : /api/echanges/{etat,instance,envois/<type>/<n>,correspondants/<role>}.
// ============================================================================

function _echE(s) { return escapeHtml(String(s == null ? '' : s)); }
function _echDate(iso) {
  const m = String(iso || '').match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  return m ? `${m[3]}/${m[2]}/${m[1]} ${m[4]}h${m[5]}` : (iso || '');
}

const ECH_ZONES = {};       // zoneId → {role}

// role : 'atelier' (j'envoie des paquets) ou 'classe' (je reçois des paquets).
async function echRendre(zoneId, role) {
  ECH_ZONES[zoneId] = { role };
  const z = document.getElementById(zoneId);
  if (!z) return;
  let d;
  try { d = await api('/api/echanges/etat'); }
  catch (e) { z.innerHTML = '<p style="font-size:12px;color:#c33">Échanges : erreur de chargement.</p>'; return; }
  const autre = role === 'atelier' ? 'classe' : 'atelier';
  const lib = { atelier: 'appli locale (atelier)', classe: 'appli en ligne (classe)' };
  const c = (d.correspondants || {})[autre];
  const corr = c
    ? `liée à <b>${_echE(c.nom || c.id)}</b> <span class="ech-id">${_echE(String(c.id).slice(5, 13))}</span>
       depuis le ${_echE(_echDate(c.lie_le))}
       <button class="btn-lien" type="button" title="Oublier ce correspondant (instance recréée, autre machine…)"
         onclick="echDelier('${zoneId}', '${autre}')">délier</button>`
    : `pas encore liée à une ${lib[autre]} (lien au premier échange reçu)`;
  let suite = '';
  if (role === 'atelier') {
    const envois = (d.envois || {}).paquet || [];
    suite = `<div class="ech-ligne">Prochain paquet : n° ${d.prochain.paquet}</div>`
      + (envois.length ? `<details class="ech-envois"><summary>Paquets envoyés</summary><ul>${envois.map(e => `<li>
          n° ${e.numero} — ${_echE(_echDate(e.cree_le))} — ${_echE(e.nom_fichier)}
          ${e.acquitte_le ? `<span class="ech-ok">acquitté</span>`
            : (e.archive ? `<a href="/api/echanges/envois/paquet/${e.numero}" download>Renvoyer</a>` : '')}
        </li>`).join('')}</ul></details>` : '')
      + _echRecus(d, 'usage', `Prochain retour d'usage attendu : n° ${d.attendu.usage}`, 'Retours d\'usage reçus');
  } else {
    // v0.51.8 — Retours d'usage envoyés (renvoi tant qu'ils ne sont pas acquittés).
    const envois = (d.envois || {}).usage || [];
    suite = _echRecus(d, 'paquet', `Prochain paquet attendu : n° ${d.attendu.paquet}`, 'Paquets reçus')
      + (envois.length ? `<details class="ech-envois"><summary>Retours d'usage envoyés</summary><ul>${envois.map(e => `<li>
          n° ${e.numero} — ${_echE(_echDate(e.cree_le))} — ${_echE(e.nom_fichier)}
          ${e.acquitte_le ? `<span class="ech-ok">acquitté</span>`
            : (e.archive ? `<a href="/api/echanges/envois/usage/${e.numero}" download>Renvoyer</a>` : '')}
        </li>`).join('')}</ul></details>` : '');
  }
  z.innerHTML = `<div class="ech-bloc">
    <div class="ech-ligne">Cette instance :
      <input class="ech-nom" value="${_echE(d.instance.nom)}" aria-label="Nom de cette instance"
        onchange="echRenommer('${zoneId}', this.value)">
      <span class="ech-id" title="${_echE(d.instance.id)}">${_echE(String(d.instance.id).slice(5, 13))}</span></div>
    <div class="ech-ligne">${corr}</div>
    ${suite}
  </div>`;
}

function _echRecus(d, type, attendu, titre) {
  const recus = (d.recus || {})[type] || [];
  return `<div class="ech-ligne">${_echE(attendu)}</div>`
    + (recus.length ? `<details class="ech-envois"><summary>${_echE(titre)}</summary><ul>${recus.map(r => `<li>
        ${r.numero ? 'n° ' + r.numero : 'sans numéro'} — ${_echE(_echDate(r.recu_le))} — ${_echE(r.nom_fichier)}</li>`).join('')}
      </ul></details>` : '');
}

async function echRenommer(zoneId, nom) {
  try { await api('/api/echanges/instance', { method: 'PUT', body: JSON.stringify({ nom }) }); }
  catch (e) { /* message dans la zone au rechargement */ }
  await echRendre(zoneId, (ECH_ZONES[zoneId] || {}).role);
}

async function echDelier(zoneId, role) {
  if (!confirm('Oublier ce correspondant ? Le prochain échange reçu liera la nouvelle instance.')) return;
  try { await api('/api/echanges/correspondants/' + role, { method: 'DELETE' }); } catch (e) {}
  await echRendre(zoneId, (ECH_ZONES[zoneId] || {}).role);
}

window.echRendre = echRendre;
window.echRenommer = echRenommer;
window.echDelier = echDelier;

// ── v0.51.9 — Boîte aux lettres (dossier de dépôt) ──────────────────────────
// depotRendre(zoneId) : dossier relevé, mode, envois en attente (« Traiter »
// en mode confirmation), réglages, journal. Routes : /api/depot/*.

const DEPOT_STATUT = {
  attendu: ['ok', 'prêt'], sans_numero: ['ok', 'prêt (sans numéro)'], meme_base: ['ok', 'prêt'],
  manquants: ['att', 'en attente'], deja_recu: ['neutre', 'déjà reçu'],
  autre_instance: ['ko', 'refusé'], refuse_sans_numero: ['ko', 'refusé'],
  illisible: ['ko', 'illisible'], non_attendu: ['ko', 'pas pour cette appli'],
};
const DEPOT_PRETS = ['attendu', 'sans_numero', 'meme_base'];

async function depotRendre(zoneId) {
  const z = document.getElementById(zoneId);
  if (!z) return;
  let d;
  try { d = await api('/api/depot/etat'); }
  catch (e) { z.innerHTML = '<p style="font-size:12px;color:#c33">Boîte aux lettres : erreur de chargement.</p>'; return; }
  const r = d.reglages || {};
  const att = d.en_attente || [];
  const prets = att.filter(x => DEPOT_PRETS.includes(x.statut)).length;
  const lignes = att.map(x => {
    const [cls, lib] = DEPOT_STATUT[x.statut] || ['neutre', x.statut];
    return `<li><span class="depot-badge ${cls}" title="${_echE(x.message)}">${_echE(lib)}</span>
      ${x.numero ? 'n° ' + x.numero + ' — ' : ''}${_echE(x.fichier)}
      ${x.statut === 'manquants' ? `<span class="rx-petit">(il manque le n° ${(x.manquants || []).join(', ')})</span>` : ''}</li>`;
  }).join('');
  const der = d.derniere_releve;
  const journal = (d.journal || []).map(j => `<li>${_echE(_echDate(j.le))} — ${_echE(j.fichier)} :
      ${j.issue === 'traite' ? '✓' : (j.issue === 'doublon' ? '=' : '✗')} ${_echE(j.message)}</li>`).join('');
  z.innerHTML = `<div class="ech-bloc depot-bloc">
    <div class="ech-ligne"><b>Boîte aux lettres</b> — mode <b>${r.mode === 'automatique' ? 'automatique' : 'confirmation'}</b>,
      relève toutes les ${r.periode_min} min${der ? ` (dernière : ${_echE(_echDate(der.releve_le))})` : ''}</div>
    <div class="ech-ligne rx-petit" title="Dossier relevé">📥 ${_echE(r.entrants_effectif)}</div>
    ${r.sortants ? `<div class="ech-ligne rx-petit" title="Chaque envoi y est aussi copié">📤 ${_echE(r.sortants)}</div>` : ''}
    ${att.length ? `<ul class="depot-liste">${lignes}</ul>` : '<div class="ech-ligne rx-petit">Aucun envoi dans le dossier.</div>'}
    <div class="ech-ligne">
      <button class="btn-sm" type="button" onclick="depotRelever('${zoneId}', false)">Relever le dépôt</button>
      ${prets ? `<button class="btn-prim" type="button" onclick="depotRelever('${zoneId}', true)">Traiter (${prets})</button>` : ''}
      <span id="${zoneId}-res" class="tdb-pub-res" role="status" aria-live="polite"></span>
    </div>
    <details class="ech-envois"><summary>Réglages</summary>
      <div class="depot-reglages">
        <label>Dossier d'entrée <input id="${zoneId}-entrants" value="${_echE(r.entrants)}"
          placeholder="défaut : data\\echanges\\entrants"></label>
        <label>Dossier de sortie (copie de chaque envoi) <input id="${zoneId}-sortants" value="${_echE(r.sortants)}"
          placeholder="aucun"></label>
        <label>Mode <select id="${zoneId}-mode">
          <option value="confirmation"${r.mode !== 'automatique' ? ' selected' : ''}>confirmation</option>
          <option value="automatique"${r.mode === 'automatique' ? ' selected' : ''}>automatique</option></select></label>
        <label>Relève toutes les <input id="${zoneId}-periode" type="number" min="1" max="1440"
          value="${r.periode_min}" style="width:60px"> min</label>
        <button class="btn-sm" type="button" onclick="depotEnregistrer('${zoneId}')">Enregistrer</button>
      </div></details>
    ${journal ? `<details class="ech-envois"><summary>Journal de la boîte aux lettres</summary><ul>${journal}</ul></details>` : ''}
  </div>`;
}

async function depotRelever(zoneId, appliquer) {
  const res = document.getElementById(zoneId + '-res');
  if (res) res.textContent = appliquer ? 'Traitement…' : 'Relève…';
  let r;
  try {
    r = await fetch('/api/depot/relever', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ appliquer }) }).then(x => x.json());
  } catch (e) { if (res) res.textContent = e.message; return; }
  await depotRendre(zoneId);
  const res2 = document.getElementById(zoneId + '-res');
  if (res2 && appliquer) {
    res2.textContent = `${(r.traites || []).length} traité(s), ${(r.doublons || []).length} doublon(s), `
      + `${(r.refuses || []).length} refusé(s), ${(r.en_attente || []).length} restant(s).`;
  }
  // Les tuiles voisines (publication, retour d'usage) reflètent le traitement.
  if (appliquer && (r.traites || []).length) {
    if (typeof tdbChargerPublication === 'function' && document.getElementById('tdb-publication')
        && zoneId === 'tdb-depot') tdbChargerPublication();
    if (typeof tdbChargerUsage === 'function' && zoneId === 'tdb-usage-depot') tdbChargerUsage();
  }
}

async function depotEnregistrer(zoneId) {
  const v = (s) => (document.getElementById(`${zoneId}-${s}`) || {}).value;
  const res = document.getElementById(zoneId + '-res');
  const r = await fetch('/api/depot/reglages', { method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ entrants: v('entrants'), sortants: v('sortants'), mode: v('mode'),
      periode_min: v('periode') }) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) { if (res) res.innerHTML = `<span class="tdb-pub-ko">✗ ${_echE(d.error || 'Erreur')}</span>`; return; }
  await depotRendre(zoneId);
  const res2 = document.getElementById(zoneId + '-res');
  if (res2) res2.textContent = 'Réglages enregistrés (la période s\'applique à la prochaine relève).';
}

window.depotRendre = depotRendre;
window.depotRelever = depotRelever;
window.depotEnregistrer = depotEnregistrer;
