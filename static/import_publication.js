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

// v0.51.7 — Séquence des paquets : n° attendu seulement.
const IMPPUB_ACCEPTES = ['attendu', 'sans_numero', 'meme_base'];

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
  const ec = a.echange || null;
  const ecOk = !ec || IMPPUB_ACCEPTES.includes(ec.statut);
  const ecHtml = ec ? `<div class="imppub-echange ${ecOk ? 'ok' : 'ko'}">${ecOk ? '✓' : '✗'} ${_impE(ec.message)}</div>` : '';
  z.innerHTML = ecHtml + `<div class="imppub-paquet">Paquet <b>${_impE(p.nom || '')}</b>
      ${p.cree_le ? '— créé le ' + _impE(_impDate(p.cree_le)) : ''}
      ${p.nb_fichiers != null ? '— ' + p.nb_fichiers + ' fichier(s)' : ''}
      ${notes.length ? '<br><span class="imppub-note">' + notes.map(_impE).join(' ; ') + '</span>' : ''}</div>` + lignes;
  const btn = document.getElementById('imppub-importer');
  // v0.51.7 — Un paquet attendu s'importe même sans changement (la séquence avance).
  if (btn) btn.disabled = apresImport || !ecOk || (!(a.referentiels || [])
    .some(r => r.statut === 'nouveau' || r.statut === 'mise_a_jour') && !(ec && ec.statut === 'attendu'));
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
  if (typeof echRendre === 'function') echRendre('imppub-echanges', 'classe');
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

// ============================================================================
// v0.51.11 — Atelier : Système › Administration › « Import retours d'usage »
// (pendant de l'import de référentiels). Routes : /api/retour-usage/
// {analyse,importer,etat}.
// ============================================================================

function _impUsageFichier() {
  const inp = document.getElementById('impusage-fichier');
  return inp && inp.files && inp.files[0];
}

async function _impUsageEnvoyer(url) {
  const f = _impUsageFichier();
  if (!f) throw new Error('Choisissez d\'abord un retour d\'usage (.json).');
  const fd = new FormData();
  fd.append('fichier', f);
  const r = await fetch(url, { method: 'POST', body: fd });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || 'Erreur');
  return d;
}

async function impUsageInit() {
  const z = document.getElementById('impusage-analyse');
  if (z) z.innerHTML = '';
  const btn = document.getElementById('impusage-importer');
  if (btn) btn.disabled = true;
  await impUsageChargerEtat();
}

async function impUsageAnalyser() {
  const st = document.getElementById('impusage-status');
  const z = document.getElementById('impusage-analyse');
  const btn = document.getElementById('impusage-importer');
  if (st) st.textContent = 'Vérification…';
  try {
    const a = await _impUsageEnvoyer('/api/retour-usage/analyse');
    const ok = IMPPUB_ACCEPTES.includes(a.echange.statut);
    if (z) z.innerHTML = `<div class="imppub-echange ${ok ? 'ok' : 'ko'}">${ok ? '✓' : '✗'} ${_impE(a.echange.message)}</div>
      <div class="imppub-paquet">Retour <b>${_impE(a.nom || '')}</b>${a.cree_le ? ' — créé le ' + _impE(_impDate(a.cree_le)) : ''}</div>
      <ul class="imppub-changements">${(a.referentiels || []).map(r => `<li><code>${_impE(r.id)}</code>
        ${r.connu ? '' : '<b>inconnu ici</b> — '}${r.utilise ? 'utilisé' : 'non utilisé'}
        · ${r.nb_sequences} séquence(s) planifiée(s) · ${r.nb_parties_mer} partie(s) de MER</li>`).join('')}</ul>`;
    if (btn) btn.disabled = !ok;
    if (st) st.textContent = 'Analyse terminée : rien n\'est encore importé.';
  } catch (e) {
    if (st) st.innerHTML = `<span class="imppub-ko">✗ ${_impE(e.message)}</span>`;
    if (btn) btn.disabled = true;
  }
}

async function impUsageImporter() {
  const st = document.getElementById('impusage-status');
  const z = document.getElementById('impusage-analyse');
  const btn = document.getElementById('impusage-importer');
  if (st) st.textContent = 'Import…';
  try {
    const r = await _impUsageEnvoyer('/api/retour-usage/importer');
    const parts = [`${(r.referentiels || []).length} référentiel(s) mis à jour`];
    if ((r.paquets_acquittes || []).length) parts.push(`paquet(s) n° ${r.paquets_acquittes.join(', ')} acquitté(s)`);
    if ((r.inconnus || []).length) parts.push(`${r.inconnus.length} inconnu(s) ici`);
    if (z) z.innerHTML = `<ul class="imppub-changements">${(r.referentiels || []).map(x => `<li><b>${_impE(x.nom)}</b> —
      ${_impE((x.synchro || {}).libelle || '')}${(x.nouvelles_sequences || []).length
        ? ' · nouvelles séquences en usage : ' + x.nouvelles_sequences.map(_impE).join(', ') : ''}</li>`).join('')}</ul>`;
    if (st) st.textContent = '✓ ' + parts.join(' ; ') + '.';
    if (btn) btn.disabled = true;
    await impUsageChargerEtat();
  } catch (e) {
    if (st) st.innerHTML = `<span class="imppub-ko">✗ ${_impE(e.message)}</span>`;
  }
}

async function impUsageChargerEtat() {
  const z = document.getElementById('impusage-etat');
  if (!z) return;
  let d;
  try { d = await api('/api/retour-usage/etat'); }
  catch (e) { z.innerHTML = '<p style="font-size:12px;color:#c33">Erreur de chargement.</p>'; return; }
  const u = (d.usages || []).filter(Boolean);
  z.innerHTML = u.length
    ? `<table class="imppub-table"><thead><tr><th>Référentiel</th><th>Utilisé</th><th>Séquences en usage</th><th>Reçu le</th></tr></thead><tbody>`
      + u.map(x => `<tr><td><code>${_impE(x.referentiel_id)}</code></td>
        <td>${x.utilise ? 'oui' + (x.utilise_depuis ? ' (depuis le ' + _impE(x.utilise_depuis) + ')' : '') : 'non'}</td>
        <td>${Object.entries(x.sequences || {}).map(([k, v]) => `${_impE(k)} (${_impE(v)})`).join(', ')
            || '—'}${(x.parties_mer || []).length ? ' · MER : ' + x.parties_mer.map(_impE).join(', ') : ''}</td>
        <td>${_impE(_impDate(x.recu_le))} (n° ${x.numero})</td></tr>`).join('')
      + '</tbody></table>'
    : '<p style="font-size:12px;color:#888">Aucun retour d\'usage reçu.</p>';
}

window.impUsageInit = impUsageInit;
window.impUsageAnalyser = impUsageAnalyser;
window.impUsageImporter = impUsageImporter;
