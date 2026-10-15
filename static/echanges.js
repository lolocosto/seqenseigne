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
       depuis le ${_echE(_echDate(c.lie_le))}`
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
    ${d.base_partagee ? `<div class="ech-ligne ech-alerte">⚠ Atelier et appli en ligne partagent la même
      base : les référentiels y sont déjà, aucun échange n'est nécessaire. Pour séparer les deux
      applis : Système › Administration › Bascule (profil complet).</div>` : ''}
    <div class="ech-ligne">Cette instance : <b>${_echE(d.instance.nom)}</b>
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

window.echRendre = echRendre;

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
    <div class="ech-ligne rx-petit">Réglages : Système › Préférences › Échanges.</div>
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
  // v0.51.13 — Écran Échanges : détail, identité et imports suivent.
  if (appliquer && (r.traites || []).length && zoneId === 'ech-depot') echangesInit();
}

// ── v0.51.10 — Système › Préférences › Échanges ─────────────────────────────
// Nom de cette instance, correspondant (délier), boîte aux lettres.
async function prefEchangesCharger() {
  const z = document.getElementById('pref-echanges');
  if (!z) return;
  let e, d;
  try { [e, d] = await Promise.all([api('/api/echanges/etat'), api('/api/depot/etat')]); }
  catch (err) { z.innerHTML = '<p style="font-size:12px;color:#c33">Erreur de chargement.</p>'; return; }
  const r = d.reglages || {};
  const lib = { atelier: 'Appli locale (atelier)', classe: 'Appli en ligne (classe)' };
  const corr = Object.entries(e.correspondants || {}).filter(([, c]) => c).map(([role, c]) => `
      <div class="ech-ligne">${lib[role]} liée : <b>${_echE(c.nom || c.id)}</b>
        <span class="ech-id">${_echE(String(c.id).slice(5, 13))}</span> depuis le ${_echE(_echDate(c.lie_le))}
        <button class="btn-sm" type="button" title="Oublier ce correspondant (instance recréée, autre machine…)"
          onclick="prefEchangesDelier('${role}')">Délier</button></div>`).join('')
    || '<div class="ech-ligne rx-petit">Aucune appli liée (le lien se fait au premier échange reçu).</div>';
  z.innerHTML = `
    <p style="font-size:13px;color:var(--text-secondary);margin-bottom:10px">
      L'appli locale (atelier) et l'appli en ligne (classe) s'échangent des envois numérotés
      (paquets de publication, retours d'usage) par une boîte aux lettres : chaque appli relève
      son dossier d'entrée au démarrage puis périodiquement.</p>
    <div class="depot-reglages">
      <label>Nom de cette instance <input id="pref-ech-nom" value="${_echE(e.instance.nom)}">
        <span class="ech-id" title="${_echE(e.instance.id)}">${_echE(String(e.instance.id).slice(5, 13))}</span></label>
      ${corr}
      <label>Dossier d'entrée (relevé) <input id="pref-ech-entrants" value="${_echE(r.entrants)}"
        placeholder="défaut : ${_echE(r.entrants_effectif)}"></label>
      <label>Dossier de sortie (copie de chaque envoi, facultatif) <input id="pref-ech-sortants"
        value="${_echE(r.sortants)}" placeholder="aucun — par ex. le dossier d'entrée de l'autre appli"></label>
      <label>Traitement des envois relevés <select id="pref-ech-mode">
        <option value="confirmation"${r.mode !== 'automatique' ? ' selected' : ''}>confirmation (bouton « Traiter »)</option>
        <option value="automatique"${r.mode === 'automatique' ? ' selected' : ''}>automatique</option></select></label>
      <label>Relève toutes les <input id="pref-ech-periode" type="number" min="1" max="1440"
        value="${r.periode_min}" style="width:70px"> minutes</label>
      <button class="btn-prim" type="button" onclick="prefEchangesEnregistrer()">Enregistrer</button>
      <span id="pref-ech-status" style="font-size:12px" role="status" aria-live="polite"></span>
    </div>
    <div id="pref-ech-api" class="depot-reglages" style="margin-top:14px"></div>`;
  // v0.51.16 — Échange automatique par l'API.
  const voit = (c) => (typeof profilPermet === 'function' ? profilPermet(c) : true);
  if (voit('classe') && !voit('atelier')) prefApiJetonRendre();
  else if (voit('atelier') && !voit('classe')) prefApiClientRendre();
}

// ── v0.51.16 — Échange par l'API ────────────────────────────────────────────

function _echJour(iso) {
  const m = String(iso || '').match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : (iso || '');
}

// Alerte commune (tuiles, écran Échanges) : injoignable, jeton qui expire.
function echApiAlertes(e) {
  if (!e || !e.configuree) return '';
  const out = [];
  if (e.injoignable) {
    out.push(`<div class="ech-alerte-api">⚠ Appli de classe actuellement injoignable
      (depuis le ${_echE(_echDate(e.erreur_depuis))}) : ${_echE(e.derniere_erreur)}
      Les envois attendent la prochaine synchronisation.</div>`);
  }
  if (e.expire) {
    out.push(`<div class="ech-alerte-api">⚠ Jeton d'accès expiré le ${_echE(_echJour(e.expire_le))} :
      générez-en un nouveau dans l'appli de classe (Préférences › Échanges).</div>`);
  } else if (e.expire_bientot) {
    out.push(`<div class="ech-alerte-api">⚠ Le jeton d'accès expire le ${_echE(_echJour(e.expire_le))}
      (dans ${e.jours_restants} jour${e.jours_restants > 1 ? 's' : ''}).</div>`);
  }
  return out.join('');
}

// Atelier : adresse de l'appli de classe et jeton.
async function prefApiClientRendre() {
  const z = document.getElementById('pref-ech-api');
  if (!z) return;
  let e;
  try { e = await api('/api/api-client/etat'); } catch (err) { return; }
  z.innerHTML = `
    <div class="ech-titre">Échange automatique avec l'appli de classe (API)</div>
    <p class="rx-petit" style="margin:0 0 6px">L'atelier dépose ses paquets dans l'appli de classe
      et y relève les retours d'usage, au démarrage puis à chaque relève (et dès qu'un paquet est
      créé). Sans adresse, seule la boîte aux lettres par dossiers sert.</p>
    <label>Adresse de l'appli de classe <input id="pref-api-url" value="${_echE(e.url)}"
      placeholder="http://localhost:5001 — en ligne : https://…"></label>
    <label>Jeton d'accès <input id="pref-api-jeton" type="password" autocomplete="off"
      placeholder="${e.jeton_enregistre ? 'jeton enregistré — coller un nouveau jeton pour le remplacer'
        : 'à générer dans l\'appli de classe (Préférences › Échanges)'}"></label>
    <div class="ech-ligne">
      <button class="btn-prim" type="button" onclick="prefApiClientEnregistrer()">Enregistrer</button>
      <button class="btn-sm" type="button" onclick="prefApiClientTester()">Tester la connexion</button>
      <span id="pref-api-status" style="font-size:12px" role="status" aria-live="polite"></span></div>
    <div class="ech-ligne rx-petit">${e.derniere_reussite
      ? `Dernier contact : ${_echE(_echDate(e.derniere_reussite))}${e.nom ? ' avec « ' + _echE(e.nom) + ' »' : ''}` : 'Aucun contact pour l\'instant.'}
      ${e.expire_le ? ` — jeton valable jusqu'au ${_echE(_echJour(e.expire_le))}` : ''}</div>
    ${echApiAlertes(e)}`;
}

async function prefApiClientEnregistrer() {
  const st = document.getElementById('pref-api-status');
  const url = document.getElementById('pref-api-url').value;
  const jeton = document.getElementById('pref-api-jeton').value;
  const r = await fetch('/api/api-client/destination', { method: 'PUT',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url, jeton }) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) { if (st) st.innerHTML = `<span style="color:#c33">✗ ${_echE(d.error || 'Erreur')}</span>`; return; }
  await prefApiClientRendre();
  if (d.configuree) await prefApiClientTester();
}

async function prefApiClientTester() {
  const st = () => document.getElementById('pref-api-status');
  if (st()) st().textContent = 'Test…';
  const t = await fetch('/api/api-client/tester', { method: 'POST' }).then(x => x.json()).catch(() => ({}));
  await prefApiClientRendre();
  if (st()) st().innerHTML = t.ok ? `✓ ${_echE(t.message)}` : `<span style="color:#c33">✗ ${_echE(t.message || 'Erreur')}</span>`;
}

// Classe : jeton d'accès de l'atelier.
async function prefApiJetonRendre(nouveau) {
  const z = document.getElementById('pref-ech-api');
  if (!z) return;
  let e;
  try { e = await api('/api/jeton'); } catch (err) { return; }
  const etat = !e.expire_le ? 'Aucun jeton : l\'atelier ne peut pas se connecter par l\'API.'
    : (e.expire ? `Jeton expiré le ${_echE(_echJour(e.expire_le))}.`
      : `Jeton actif jusqu'au ${_echE(_echJour(e.expire_le))}`
        + (e.dernier_usage ? ` — dernier contact de l'atelier : ${_echE(_echDate(e.dernier_usage))}` : ' — pas encore utilisé') + '.');
  z.innerHTML = `
    <div class="ech-titre">Accès de l'atelier (API)</div>
    <p class="rx-petit" style="margin:0 0 6px">L'atelier se connecte à cette appli avec un jeton
      pour y déposer ses paquets et relever les retours d'usage (aucune donnée d'élève). Le jeton
      n'est montré qu'une fois ; en générer un nouveau révoque l'actuel.</p>
    <div class="ech-ligne">${etat}</div>
    ${e.expire_bientot ? `<div class="ech-alerte-api">⚠ Le jeton expire dans ${e.jours_restants} jour(s).</div>` : ''}
    ${nouveau ? `<div class="ech-jeton">
      <div><b>Nouveau jeton</b> — copiez-le maintenant dans l'atelier (Préférences › Échanges) :
        il ne sera plus affiché.</div>
      <div class="ech-ligne"><input id="pref-api-jeton-nouveau" readonly value="${_echE(nouveau)}"
        style="flex:1;font-family:monospace" onclick="this.select()">
        <button class="btn-sm" type="button" onclick="prefApiJetonCopier()">Copier</button></div></div>` : ''}
    <label>Expire le <input id="pref-api-expire" type="date"
      value="${_echE(e.expiration_defaut)}"></label>
    <div class="ech-ligne">
      <button class="btn-prim" type="button" onclick="prefApiJetonGenerer(${e.actif ? 'true' : 'false'})">Générer un nouveau jeton</button>
      ${e.actif ? '<button class="btn-sm" type="button" onclick="prefApiJetonRevoquer()">Révoquer</button>' : ''}
      <span id="pref-api-status" style="font-size:12px" role="status" aria-live="polite"></span></div>`;
}

async function prefApiJetonGenerer(remplace) {
  if (remplace && !confirm('Générer un nouveau jeton ? L\'actuel sera révoqué : l\'atelier devra '
    + 'enregistrer le nouveau.')) return;
  const expire_le = document.getElementById('pref-api-expire').value;
  const r = await fetch('/api/jeton', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ expire_le }) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) {
    const st = document.getElementById('pref-api-status');
    if (st) st.innerHTML = `<span style="color:#c33">✗ ${_echE(d.error || 'Erreur')}</span>`;
    return;
  }
  await prefApiJetonRendre(d.jeton);
}

async function prefApiJetonCopier() {
  const inp = document.getElementById('pref-api-jeton-nouveau');
  if (!inp) return;
  inp.select();
  try { await navigator.clipboard.writeText(inp.value); } catch (e) { document.execCommand('copy'); }
  const st = document.getElementById('pref-api-status');
  if (st) st.textContent = '✓ Copié.';
}

async function prefApiJetonRevoquer() {
  if (!confirm('Révoquer le jeton ? L\'atelier ne pourra plus se connecter par l\'API.')) return;
  await fetch('/api/jeton', { method: 'DELETE' });
  await prefApiJetonRendre();
}

window.echApiAlertes = echApiAlertes;
window.prefApiClientEnregistrer = prefApiClientEnregistrer;
window.prefApiClientTester = prefApiClientTester;
window.prefApiJetonGenerer = prefApiJetonGenerer;
window.prefApiJetonCopier = prefApiJetonCopier;
window.prefApiJetonRevoquer = prefApiJetonRevoquer;

async function prefEchangesEnregistrer() {
  const v = (s) => (document.getElementById('pref-ech-' + s) || {}).value;
  const st = () => document.getElementById('pref-ech-status');
  const nom = (v('nom') || '').trim();
  try {
    if (nom) await fetch('/api/echanges/instance', { method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nom }) });
    const r = await fetch('/api/depot/reglages', { method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ entrants: v('entrants'), sortants: v('sortants'), mode: v('mode'),
        periode_min: v('periode') }) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || 'Erreur');
  } catch (err) {
    if (st()) st().innerHTML = `<span style="color:#c33">✗ ${_echE(err.message)}</span>`;
    return;
  }
  await prefEchangesCharger();
  if (st()) st().textContent = '✓ Enregistré (la période s\'applique à la prochaine relève).';
}

async function prefEchangesDelier(role) {
  if (!confirm('Oublier cette appli liée ? Le prochain échange reçu liera la nouvelle instance.')) return;
  try { await api('/api/echanges/correspondants/' + role, { method: 'DELETE' }); } catch (e) {}
  await prefEchangesCharger();
}

window.prefEchangesCharger = prefEchangesCharger;
window.prefEchangesEnregistrer = prefEchangesEnregistrer;
window.prefEchangesDelier = prefEchangesDelier;
window.depotRendre = depotRendre;
window.depotRelever = depotRelever;

// ── v0.51.13 — Système › Administration › Échanges ─────────────────────────
// Détail de la publication (atelier) ou du retour d'usage (classe), boîte
// aux lettres, identité et correspondant, imports à la main.
async function echangesInit() {
  const permet = (c) => (typeof profilPermet === 'function' ? profilPermet(c) : true);
  const role = permet('atelier') ? 'atelier' : 'classe';
  if (permet('atelier') && typeof tdbChargerPublication === 'function') tdbChargerPublication();
  if (permet('classe') && typeof tdbChargerUsage === 'function') tdbChargerUsage();
  depotRendre('ech-depot');
  echRendre('ech-instance', role);
  if (role === 'atelier') echApiRendre();
  if (permet('atelier') && typeof impUsageInit === 'function') impUsageInit();
  if (permet('classe') && typeof impPubInit === 'function') impPubInit();
}
window.echangesInit = echangesInit;

// v0.51.16 — Écran Échanges (atelier) : état de l'API, synchroniser.
async function echApiRendre(message) {
  const z = document.getElementById('ech-api');
  if (!z) return;
  let e;
  try { e = await api('/api/api-client/etat'); } catch (err) { z.innerHTML = ''; return; }
  z.innerHTML = e.configuree ? `<div class="ech-bloc">
      <div class="ech-ligne"><b>Appli de classe (API)</b> — ${_echE(e.url)}
        <button class="btn-sm" type="button" onclick="echApiSynchroniser()">Synchroniser maintenant</button>
        <span id="ech-api-res" class="rx-petit" role="status" aria-live="polite">${_echE(message || '')}</span></div>
      <div class="ech-ligne rx-petit">${e.derniere_reussite ? 'Dernier contact : ' + _echE(_echDate(e.derniere_reussite)) : 'Aucun contact pour l\'instant.'}
        ${e.expire_le ? ` — jeton valable jusqu'au ${_echE(_echJour(e.expire_le))}` : ''}</div>
      ${echApiAlertes(e)}</div>`
    : `<div class="ech-bloc"><div class="ech-ligne rx-petit">Échange automatique par l'API non réglé
        (Système › Préférences › Échanges) : la boîte aux lettres par dossiers et l'import à la main
        restent disponibles.</div></div>`;
}

async function echApiSynchroniser() {
  const res = document.getElementById('ech-api-res');
  if (res) res.textContent = 'Synchronisation…';
  const s = await fetch('/api/api-client/synchroniser', { method: 'POST' }).then(x => x.json()).catch(() => ({}));
  const msg = s.ok ? `✓ ${(s.livres || []).length} paquet(s) envoyé(s), ${(s.recus || []).length} retour(s) d'usage reçu(s).`
    : (s.erreur || '');
  await echangesInit();
  await echApiRendre(msg);
}
window.echApiRendre = echApiRendre;
window.echApiSynchroniser = echApiSynchroniser;
