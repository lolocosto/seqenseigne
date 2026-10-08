// ============================================================================
// static/import_publication.js — v0.51.3
// Système › Administration › « Import référentiels » (profil classe) :
// analyse puis import d'un paquet de publication produit par l'appli locale.
//   - Analyser : vérifie le paquet et montre, par référentiel, son statut
//     (nouveau, mise à jour, identique, refusé), les changements, les raisons
//     d'un refus et les associations de documents qui deviendraient orphelines ;
//   - Importer : applique les référentiels nouveaux ou mis à jour ;
//   - liste des référentiels importés et journal.
// Routes : /api/import-publication/{analyse,importer,etat}.
// ============================================================================

const IMPPUB_LIB = { nouveau: 'nouveau', mise_a_jour: 'mise à jour',
  identique: 'identique', refuse: 'refusé' };

function _impE(s) { return escapeHtml(String(s == null ? '' : s)); }

function _impDate(iso) {
  const m = String(iso || '').match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  return m ? `${m[3]}/${m[2]}/${m[1]} ${m[4]}h${m[5]}` : (iso || '');
}

async function impPubInit() {
  await impPubChargerEtat();
}

function _impFichier() {
  const inp = document.getElementById('imppub-fichier');
  return inp && inp.files && inp.files[0];
}

async function _impEnvoyer(url) {
  const f = _impFichier();
  if (!f) throw new Error('Choisissez d\'abord un paquet (.zip).');
  const fd = new FormData();
  fd.append('paquet', f);
  const r = await fetch(url, { method: 'POST', body: fd });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) {
    const e = new Error(d.error || 'Erreur');
    e.erreurs = d.erreurs || [];
    throw e;
  }
  return d;
}

function _impRendreAnalyse(a, apresImport) {
  const z = document.getElementById('imppub-analyse');
  if (!z) return;
  const p = a.paquet || {};
  const rap = p.rapport || {};
  const lignes = (a.referentiels || []).map(r => {
    const liste = (titre, xs, cls) => (xs && xs.length)
      ? `<div class="imppub-${cls}"><b>${titre}</b><ul>${xs.map(x => `<li>${_impE(x)}</li>`).join('')}</ul></div>` : '';
    const etat = apresImport
      ? (r.importe ? '<span class="imppub-badge ok">importé</span>'
        : `<span class="imppub-badge ${r.statut}">${IMPPUB_LIB[r.statut] || r.statut}</span>`)
      : `<span class="imppub-badge ${r.statut}">${IMPPUB_LIB[r.statut] || r.statut}</span>`;
    return `<div class="imppub-ref">
      <div class="imppub-ref-tete"><b>${_impE(r.nom)}</b> <code>${_impE(r.id)}</code> ${etat}</div>
      ${liste('Raisons', r.raisons, 'raisons')}
      ${liste('Changements', r.changements, 'changements')}
      ${liste('Associations de documents qui deviennent orphelines (conservées)', r.orphelins, 'orphelins')}
    </div>`;
  }).join('');
  const notes = [];
  if ((rap.documents_sans_pdf || []).length) notes.push(`${rap.documents_sans_pdf.length} document(s) sans PDF non publiés par l'atelier`);
  if ((rap.parties_ecart || []).length) notes.push(`${rap.parties_ecart.length} partie(s) dont la durée saisie diffère des objectifs (durée importée = somme)`);
  z.innerHTML = `<div class="imppub-paquet">Paquet <b>${_impE(p.nom || '')}</b>
      ${p.cree_le ? '— créé le ' + _impE(_impDate(p.cree_le)) : ''}
      ${p.nb_fichiers != null ? '— ' + p.nb_fichiers + ' fichier(s)' : ''}
      ${notes.length ? '<br><span class="imppub-note">' + notes.map(_impE).join(' ; ') + '</span>' : ''}</div>` + lignes;
  const btn = document.getElementById('imppub-importer');
  if (btn) btn.disabled = apresImport || !(a.referentiels || [])
    .some(r => r.statut === 'nouveau' || r.statut === 'mise_a_jour');
}

async function impPubAnalyser() {
  const st = document.getElementById('imppub-status');
  if (st) st.textContent = 'Vérification du paquet…';
  try {
    const a = await _impEnvoyer('/api/import-publication/analyse');
    _impRendreAnalyse(a, false);
    if (st) st.textContent = 'Analyse terminée : rien n\'est encore importé.';
  } catch (e) {
    _impErreur(e);
  }
}

async function impPubImporter() {
  const st = document.getElementById('imppub-status');
  if (st) st.textContent = 'Import…';
  try {
    const a = await _impEnvoyer('/api/import-publication/importer');
    _impRendreAnalyse(a, true);
    const n = (a.referentiels || []).filter(r => r.importe).length;
    if (st) st.textContent = `${n} référentiel(s) importé(s).`;
    await impPubChargerEtat();
  } catch (e) {
    _impErreur(e);
  }
}

function _impErreur(e) {
  const st = document.getElementById('imppub-status');
  if (st) st.innerHTML = `<span class="imppub-ko">✗ ${_impE(e.message)}</span>`;
  const z = document.getElementById('imppub-analyse');
  if (z) z.innerHTML = (e.erreurs || []).length
    ? `<ul class="imppub-raisons">${e.erreurs.slice(0, 20).map(x => `<li>${_impE(x)}</li>`).join('')}</ul>` : '';
  const btn = document.getElementById('imppub-importer');
  if (btn) btn.disabled = true;
}

async function impPubChargerEtat() {
  const zi = document.getElementById('imppub-importes');
  const zj = document.getElementById('imppub-journal');
  let d;
  try {
    d = await api('/api/import-publication/etat');
  } catch (e) {
    if (zi) zi.innerHTML = '<p style="font-size:12px;color:#c33">Erreur de chargement.</p>';
    return;
  }
  if (zi) zi.innerHTML = (d.importes || []).length
    ? `<table class="imppub-table"><thead><tr><th>Référentiel</th><th>État</th><th>Importé le</th><th>Empreinte</th></tr></thead><tbody>`
      + d.importes.map(r => `<tr><td>${_impE(r.nom)} <code>${_impE(r.id)}</code></td>
        <td>${_impE(r.etat)}</td><td>${_impE(_impDate(r.importe_le))}</td>
        <td><code>${_impE(String(r.empreinte || '').slice(7, 15))}</code></td></tr>`).join('')
      + '</tbody></table>'
    : '<p style="font-size:12px;color:#888">Aucun référentiel importé.</p>';
  if (zj) zj.innerHTML = (d.journal || []).length
    ? '<ul>' + d.journal.map(j => `<li>${_impE(_impDate(j.importe_le))} — ${_impE(j.nom_paquet)} :
        ${_impE(j.nom)} — ${IMPPUB_LIB[j.statut] || _impE(j.statut)}</li>`).join('') + '</ul>'
    : '<p style="color:#888">Aucun import.</p>';
}

window.impPubInit = impPubInit;
window.impPubAnalyser = impPubAnalyser;
window.impPubImporter = impPubImporter;
