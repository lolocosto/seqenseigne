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
