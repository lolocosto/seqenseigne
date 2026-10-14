// ============================================================================
// static/bascule.js — v0.51.12
// Système › Administration › « Bascule » (profil complet) : sépare la base
// partagée (data\) en deux bases, data_atelier\ (conception) et data_classe\
// (planification et suivi). Aperçu d'abord (rien n'est écrit), puis bascule
// sur confirmation. data\ n'est jamais modifié.
// Routes : GET /api/bascule/apercu, POST /api/bascule {confirmer: true}.
// ============================================================================

const BSC_DEVENIR = {
  publie: 'publié vers la classe (paquet)',
  garde: 'gardé côté classe, sans documents',
  atelier: 'atelier seulement',
};

const BSC_ETATS = { en_cours: 'en cours', verrouille: 'verrouillé', utilise: 'utilisé',
  valide: 'validé', annule: 'annulé', archive: 'archivé' };

function _bscE(s) { return escapeHtml(String(s == null ? '' : s)); }

function _bscOctets(n) {
  n = Number(n || 0);
  if (n >= 1048576) return (n / 1048576).toFixed(1).replace('.', ',') + ' Mo';
  if (n >= 1024) return Math.round(n / 1024) + ' ko';
  return n + ' o';
}

function _bscTables(titre, t) {
  const noms = Object.keys(t || {});
  if (!noms.length) return '';
  const total = noms.reduce((s, k) => s + t[k], 0);
  return `<details class="bsc-tables"><summary>${titre} — ${noms.length} table(s), `
    + `${total} ligne(s)</summary><div class="bsc-liste">`
    + noms.map(k => `<span>${_bscE(k)} <b>${t[k]}</b></span>`).join('')
    + '</div></details>';
}

async function bscInit() {
  const z = document.getElementById('bsc-apercu');
  const b = document.getElementById('bsc-executer');
  if (!z) return;
  z.innerHTML = '<span style="color:var(--text-muted)">Analyse de la base…</span>';
  if (b) b.disabled = true;
  let a;
  try {
    const r = await fetch('/api/bascule/apercu');
    a = await r.json();
    if (!r.ok) throw new Error(a.error || 'Aperçu impossible');
  } catch (e) {
    z.innerHTML = `<span style="color:var(--danger)">${_bscE(e.message)}</span>`;
    return;
  }
  const refs = (a.referentiels || []).map(r => `<tr>
      <td>${_bscE(r.nom)}</td><td>${_bscE(BSC_ETATS[r.etat] || r.etat)}</td>
      <td>${r.utilise ? 'oui' : '—'}</td>
      <td class="bsc-${r.devenir}">${_bscE(BSC_DEVENIR[r.devenir] || r.devenir)}</td></tr>`).join('');
  const t = a.tables || {};
  z.innerHTML = `
    ${(a.refus || []).map(m => `<div class="bsc-refus">${_bscE(m)}</div>`).join('')}
    <div class="bsc-cibles">
      <div><b>Atelier</b> → ${_bscE((a.cibles.atelier || {}).dossier)}</div>
      <div><b>Classe</b> → ${_bscE((a.cibles.classe || {}).dossier)}</div>
      <div style="color:var(--text-secondary)">Base actuelle : ${_bscOctets((a.tailles || {}).base)}
        ; fichiers copiés côté atelier : ${_bscOctets((a.tailles || {}).atelier)}</div>
    </div>
    <table class="bsc-refs"><thead><tr><th>Référentiel</th><th>État</th><th>Utilisé</th>
      <th>Après la bascule</th></tr></thead><tbody>${refs
        || '<tr><td colspan="4" style="color:var(--text-muted)">Aucun référentiel.</td></tr>'}</tbody></table>
    ${_bscTables('Appli de classe seulement', t.classe)}
    ${_bscTables('Atelier seulement', t.atelier)}
    ${_bscTables('Des deux côtés', t.deux)}
    ${(t.inconnues || []).length ? `<div class="bsc-avert">Tables non réparties (gardées des
      deux côtés) : ${_bscE(t.inconnues.join(', '))}</div>` : ''}
    ${(a.avertissements || []).map(m => `<div class="bsc-avert">${_bscE(m)}</div>`).join('')}`;
  if (b) b.disabled = !a.possible;
}

async function bscExecuter() {
  const st = document.getElementById('bsc-status');
  const b = document.getElementById('bsc-executer');
  if (!window.confirm('Créer data_atelier\\ et data_classe\\ à partir de la base actuelle ?\n'
      + 'data\\ reste intact (il sert de sauvegarde).')) return;
  if (b) b.disabled = true;
  if (st) st.innerHTML = 'Bascule en cours…';
  try {
    const rep = await fetch('/api/bascule', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirmer: true }) });
    const r = await rep.json();
    if (!rep.ok) throw new Error(r.error || 'Bascule impossible');
    const p = r.paquet;
    document.getElementById('bsc-apercu').innerHTML = `
      <div class="bsc-ok"><b>Bascule faite.</b></div>
      <ul class="bsc-rapport">
        <li>${p ? `Paquet n° ${p.numero} (${_bscE(p.nom)}) : ${p.referentiels.length}
          référentiel(s) importé(s) par l'appli de classe.` : 'Aucun référentiel à publier.'}</li>
        <li>Retour d'usage ${_bscE(r.usage.nom)} importé par l'atelier
          (${r.usage.referentiels.filter(x => x.utilise).length} référentiel(s) utilisé(s)).</li>
        <li>Atelier : ${r.atelier.tables_retirees.length} table(s) de l'appli de classe retirée(s) ;
          classe : ${r.classe.tables_retirees.length} table(s) de conception retirée(s).</li>
        ${Object.entries(r.renommes || {}).map(([a, b2]) =>
          `<li>Ancien dossier ${_bscE(a)} renommé ${_bscE(b2)}.</li>`).join('')}
      </ul>
      <p>Arrêtez cette fenêtre, puis lancez <code>lancer.bat atelier</code> et
        <code>lancer.bat classe</code> : chaque appli ouvre désormais son dossier.
        Le rapport est enregistré dans <code>BASCULE.json</code> de chaque dossier.</p>`;
    if (st) st.innerHTML = '';
  } catch (e) {
    if (st) st.innerHTML = `<span style="color:var(--danger)">${_bscE(e.message)}</span>`;
    if (b) b.disabled = false;
  }
}
