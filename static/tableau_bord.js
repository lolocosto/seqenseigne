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
  // v0.51.0 — Une tuile par côté. v0.51.13 : journée, classes, établissements
  // (classe) ; publication et retour d'usage résumés (détail : Système ›
  // Administration › Échanges).
  const permet = (c) => (typeof profilPermet === 'function' ? profilPermet(c) : true);
  if (permet('classe')) {
    if (typeof tdbChargerJournee === 'function') tdbChargerJournee();
    if (typeof tdbChargerClasses === 'function') tdbChargerClasses();
    if (typeof tdbChargerEtabs === 'function') tdbChargerEtabs();
    tdbResumeUsage();
  }
  if (permet('atelier')) {
    tdbResumePublication();
    tdbChargerAtomes();
    tdbChargerNonRattaches();
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

// v0.51.13 — Détail de la publication : Système › Administration › Échanges.
async function tdbChargerPublication() {
  const zone = document.getElementById('ech-publication');
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
      return `<span class="tdb-pub-badge sync-${s.etat}" title="${escapeHtml(titre)}">${escapeHtml(s.libelle)}</span>`
        // v0.51.13 — Modifié depuis la dernière publication : à republier.
        + (r.modifie_depuis && s.etat !== 'modifie' ? '<span class="tdb-pub-badge modif">modifié depuis</span>' : '');
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
    + (journal ? `<details class="tdb-pub-journal"><summary>Dernières publications</summary><ul>${journal}</ul></details>` : '');
}

function tdbPubCocher(id, oui) {
  if (oui) TDB_PUB.sel.add(id); else TDB_PUB.sel.delete(id);
}

function tdbPubCocherModifies() {
  TDB_PUB.liste.filter(r => r.valide && (!r.derniere_publication || r.modifie_depuis))
    .forEach(r => TDB_PUB.sel.add(r.id));
  tdbChargerPublication();
}

async function tdbPubCreer(idsImposes) {
  const res = document.getElementById(idsImposes ? 'tdb-pubr-res' : 'tdb-pub-res');
  const ids = idsImposes || [...TDB_PUB.sel];
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
    let resume = {}, envoi = {};
    try { resume = JSON.parse(r.headers.get('X-Paquet-Resume') || '{}'); } catch (e) {}
    try { envoi = JSON.parse(r.headers.get('X-Paquet-Envoi') || '{}'); } catch (e) {}
    const blob = await r.blob();
    // v0.51.16 — Livré par l'API : pas de téléchargement ; sinon le fichier
    // (boîte aux lettres par dossiers, import à la main).
    if (!envoi.livre) {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = resume.nom || 'paquet.zip';
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    }
    TDB_PUB.sel.clear();
    await tdbChargerPublication();
    await tdbResumePublication();
    if (typeof echRendre === 'function' && document.getElementById('ech-instance')) echRendre('ech-instance', 'atelier');
    const res2 = document.getElementById(idsImposes ? 'tdb-pubr-res' : 'tdb-pub-res');
    if (res2) res2.innerHTML = `<span class="tdb-pub-ok">✓ ${escapeHtml(resume.nom || 'Paquet créé')}</span>`
      + (envoi.livre ? ' envoyé à l\'appli de classe' : (envoi.configuree
        ? ` <span class="tdb-pub-ko">non envoyé (${escapeHtml(envoi.erreur || 'appli injoignable')}) : il partira à la prochaine synchronisation</span>` : ''))
      + ' — '
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

// Classe : contenu du prochain retour, création (téléchargement), échanges.
// v0.51.13 — Détail du retour d'usage : Système › Administration › Échanges.
async function tdbChargerUsage() {
  const zone = document.getElementById('ech-usage');
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
    <div class="tdb-pub-actions">${refs.length
      ? `<button class="btn-prim" type="button" onclick="tdbUsageCreer()">Créer le retour d'usage (n° ${d.echange.numero})</button>`
      : '<span style="font-size:12px;color:#888">Rien à signaler tant qu\'aucun référentiel n\'a été importé.</span>'}</div>
    <div id="tdb-usage-res" class="tdb-pub-res" role="status" aria-live="polite"></div>`;
}

async function tdbUsageCreer(depuisTuile) {
  const res = document.getElementById(depuisTuile ? 'tdb-usager-res' : 'tdb-usage-res');
  try {
    const r = await fetch('/api/retour-usage/creer', { method: 'POST' });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || 'Erreur');
    const resume = JSON.parse(r.headers.get('X-Usage-Resume') || '{}');
    const viaApi = r.headers.get('X-Usage-Api') === '1';      // v0.51.16
    const blob = await r.blob();
    if (!viaApi) {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = resume.nom || 'usage.json';
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    }
    await tdbChargerUsage();
    await tdbResumeUsage();
    if (typeof echRendre === 'function' && document.getElementById('ech-instance')) echRendre('ech-instance', 'classe');
    const res2 = document.getElementById(depuisTuile ? 'tdb-usager-res' : 'tdb-usage-res');
    if (res2) res2.textContent = `✓ ${resume.nom} créé (${resume.nb_referentiels} référentiel(s)) : `
      + (viaApi ? 'l\'atelier le relèvera à sa prochaine synchronisation.'
        : 'il part par la boîte aux lettres vers l\'appli locale.');
  } catch (e) {
    if (res) res.innerHTML = `<span class="tdb-pub-ko">✗ ${escapeHtml(e.message)}</span>`;
  }
}

window.tdbChargerUsage = tdbChargerUsage;
window.tdbUsageCreer = tdbUsageCreer;

// ── v0.51.13 — Résumés des tuiles Publication et Retour d'usage ─────────────

function tdbOuvrirEchanges() {
  try { localStorage.setItem('systeme-sous-onglet', 'admin'); } catch (e) {}
  const btn = document.querySelector('[data-tab="systeme"]');
  if (btn) btn.click();
  setTimeout(() => { if (typeof adminSousOnglet === 'function') adminSousOnglet('echanges'); }, 0);
}

// Ligne « boîte aux lettres » d'une tuile : envois en attente, Relever/Traiter.
function _tdbBoite(dep, zoneRes) {
  const att = (dep && dep.en_attente) || [];
  const prets = att.filter(x => ['attendu', 'sans_numero', 'meme_base'].includes(x.statut)).length;
  return `<div class="tdb-ligne">📥 Boîte aux lettres : ${att.length
      ? `<b>${att.length}</b> envoi(s) déposé(s)${prets ? `, ${prets} prêt(s)` : ''}` : 'rien en attente'}
    <button class="btn-sm" type="button" onclick="tdbBoite(false, '${zoneRes}')">Relever</button>
    ${prets ? `<button class="btn-prim" type="button" onclick="tdbBoite(true, '${zoneRes}')">Traiter (${prets})</button>` : ''}</div>`;
}

async function tdbBoite(appliquer, zoneRes) {
  const res = document.getElementById(zoneRes);
  if (res) res.textContent = appliquer ? 'Traitement…' : 'Relève…';
  let r = {};
  try {
    r = await fetch('/api/depot/relever', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ appliquer }) }).then(x => x.json());
  } catch (e) { if (res) res.textContent = e.message; return; }
  if (document.getElementById('tdb-publication')) await tdbResumePublication();
  if (document.getElementById('tdb-usage')) await tdbResumeUsage();
  const res2 = document.getElementById(zoneRes);
  if (res2) res2.textContent = appliquer
    ? `${(r.traites || []).length} traité(s), ${(r.refuses || []).length} refusé(s), ${(r.en_attente || []).length} restant(s).`
    : 'Boîte relevée.';
}

// v0.51.16 — Échange par l'API : atelier (dernier contact, alertes)…
function _tdbApiLigne(e) {
  if (!e || !e.configuree) return '';
  return `<div class="tdb-ligne">🔁 Appli de classe (API) : ${e.derniere_reussite
      ? 'dernier contact le ' + escapeHtml(_tdbDateHeure(e.derniere_reussite)) : 'pas encore de contact'}</div>`
    + (typeof echApiAlertes === 'function' ? echApiAlertes(e) : '');
}
// … et classe (jeton de l'atelier).
function _tdbJetonLigne(j) {
  if (!j || !j.expire_le) return '';
  if (j.expire) return `<div class="ech-alerte-api">⚠ Jeton de l'atelier expiré : générez-en un nouveau (Préférences › Échanges).</div>`;
  return `<div class="tdb-ligne">🔁 Atelier (API) : ${j.dernier_usage
      ? 'dernier contact le ' + escapeHtml(_tdbDateHeure(j.dernier_usage)) : 'pas encore de contact'}</div>`
    + (j.expire_bientot ? `<div class="ech-alerte-api">⚠ Le jeton de l'atelier expire dans ${j.jours_restants} jour(s).</div>` : '');
}

async function _tdbJson(url) {
  try { return await api(url); } catch (e) { return null; }
}

async function tdbResumePublication() {
  const zone = document.getElementById('tdb-publication');
  if (!zone) return;
  zone.innerHTML = '<p class="tdb-vide">Calcul des empreintes…</p>';
  const [d, dep, apiE] = await Promise.all([_tdbJson('/api/publication/publiables'),
    _tdbJson('/api/depot/etat'), _tdbJson('/api/api-client/etat')]);
  if (!d) { zone.innerHTML = '<p class="tdb-erreur">Erreur de chargement.</p>'; return; }
  const refs = d.referentiels || [];
  const aPublier = refs.filter(r => r.valide && (!r.derniere_publication || r.modifie_depuis));
  const etat = r => (r.synchro || {}).etat || '';
  const aJour = refs.filter(r => etat(r) === 'synchronise').length;
  const attente = refs.filter(r => etat(r) === 'en_attente' && !r.modifie_depuis).length;
  const verifier = refs.filter(r => !r.valide || ['en_retard', 'desynchronise'].includes(etat(r))).length;
  const der = (d.journal || [])[0];
  // Seuls les comptes non nuls s'affichent (« à jour » toujours).
  const chiffre = (n, lib, cls, toujours) => (n || toujours)
    ? `<span class="tdb-chiffre ${n ? cls : ''}"><b>${n}</b> ${lib}</span>` : '';
  zone.innerHTML = refs.length ? `
    <div class="tdb-chiffres">${chiffre(aJour, 'à jour', 'ok', true)}${chiffre(aPublier.length, 'à publier', 'att')}
      ${chiffre(attente, 'en attente de retour', 'neutre')}${chiffre(verifier, 'à vérifier', 'ko')}</div>
    <div class="tdb-ligne">Dernier paquet : ${der ? `n° ${der.numero || '—'} le ${escapeHtml(_tdbDateHeure(der.cree_le))}`
      : 'aucun'}</div>
    ${_tdbApiLigne(apiE)}
    ${_tdbBoite(dep, 'tdb-pubr-res')}
    <div class="tdb-actions">${aPublier.length
      ? `<button class="btn-prim" type="button" onclick='tdbPubCreer(${JSON.stringify(aPublier.map(r => r.id))})'>Publier les ${aPublier.length} à publier</button>` : ''}
      <a href="#" onclick="tdbOuvrirEchanges();return false">Détails →</a></div>
    <div id="tdb-pubr-res" class="tdb-pub-res" role="status" aria-live="polite"></div>`
    : `<p class="tdb-vide">Aucun référentiel publiable (internes verrouillés, externes).</p>
       <div class="tdb-actions"><a href="#" onclick="tdbOuvrirEchanges();return false">Détails →</a></div>`;
}

async function tdbResumeUsage() {
  const zone = document.getElementById('tdb-usage');
  if (!zone) return;
  const [d, e, dep, jet] = await Promise.all([_tdbJson('/api/retour-usage/apercu'),
    _tdbJson('/api/echanges/etat'), _tdbJson('/api/depot/etat'), _tdbJson('/api/jeton')]);
  if (!d || !e) { zone.innerHTML = '<p class="tdb-erreur">Erreur de chargement.</p>'; return; }
  const refs = d.referentiels || [];
  const recu = ((e.recus || {}).paquet || [])[0];
  const envoye = ((e.envois || {}).usage || [])[0];
  zone.innerHTML = `
    <div class="tdb-chiffres"><span class="tdb-chiffre"><b>${refs.length}</b> référentiel(s) importé(s)</span>
      <span class="tdb-chiffre"><b>${refs.filter(r => r.utilise).length}</b> utilisé(s)</span></div>
    <div class="tdb-ligne">Dernier paquet reçu : ${recu
      ? `${recu.numero ? 'n° ' + recu.numero : 'sans numéro'} le ${escapeHtml(_tdbDateHeure(recu.recu_le))}` : 'aucun'}</div>
    <div class="tdb-ligne">Dernier retour envoyé : ${envoye
      ? `n° ${envoye.numero} le ${escapeHtml(_tdbDateHeure(envoye.cree_le))} — ${envoye.acquitte_le ? 'acquitté' : 'pas encore acquitté'}`
      : 'aucun'}</div>
    ${_tdbJetonLigne(jet)}
    ${_tdbBoite(dep, 'tdb-usager-res')}
    <div class="tdb-actions">${refs.length
      ? `<button class="btn-prim" type="button" onclick="tdbUsageCreer(true)">Créer le retour d'usage n° ${d.echange.numero}</button>` : ''}
      <a href="#" onclick="tdbOuvrirEchanges();return false">Détails →</a></div>
    <div id="tdb-usager-res" class="tdb-pub-res" role="status" aria-live="polite"></div>`;
}

window.tdbOuvrirEchanges = tdbOuvrirEchanges;
window.tdbBoite = tdbBoite;
window.tdbResumePublication = tdbResumePublication;
window.tdbResumeUsage = tdbResumeUsage;
