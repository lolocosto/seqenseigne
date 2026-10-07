// ============================================================================
// static/referentiel_externe.js — v0.25.0
// Atelier « Référentiel externe » (Conception de référentiel › Niveau).
// Gère les référentiels externes du niveau courant : création, séquences,
// parties (nb de séances), documents (import/suppression), validation.
// ============================================================================

let RXT_LISTE = [];

function _rxtNiveau() {
  try {
    if (typeof ATL_SELECTIONS !== 'undefined' && ATL_SELECTIONS.niveau)
      return ATL_SELECTIONS.niveau.niveau || 'N09';
  } catch (e) {}
  return 'N09';
}
function _rxtAnnee() {
  return (typeof ANNEE_ACTIVE !== 'undefined' && ANNEE_ACTIVE)
    || (typeof anneeScolaireCourante === 'function' ? anneeScolaireCourante() : '');
}
function _rxtStatus(msg, err) {
  const s = document.getElementById('rxt-status');
  if (!s) return;
  s.style.color = err ? '#c33' : '#4a7';
  s.textContent = msg || '';
  if (msg && !err) setTimeout(() => { if (s.textContent === msg) s.textContent = ''; }, 2500);
}

async function rxtInit() {
  if (typeof rpeInit === 'function') rpeInit();     // v0.48.2 — principaux externes
  await rxtCharger();
}

async function rxtCharger() {
  const niveau = _rxtNiveau();
  try {
    const r = await api('/api/referentiels-externes?niveau='
      + encodeURIComponent(niveau) + '&type=mer');
    RXT_LISTE = (r && r.referentiels) || [];
  } catch (e) { RXT_LISTE = []; }
  // Charger le détail complet de chacun (séquences/parties/docs).
  for (const ref of RXT_LISTE) {
    try {
      const full = await api('/api/referentiels-externes/' + ref.id);
      ref.sequences = full.sequences || [];
      ref.docs_annuels = full.docs_annuels || [];
    } catch (e) { ref.sequences = []; ref.docs_annuels = []; }
  }
  rxtRender();
}

async function rxtCreer() {
  const nom = (document.getElementById('rxt-nouveau-nom').value || '').trim();
  try {
    await api('/api/referentiels-externes', {
      method: 'POST',
      body: JSON.stringify({ niveau: _rxtNiveau(), annee: _rxtAnnee(),
                             type: 'mer', nom }),
    });
    document.getElementById('rxt-nouveau-nom').value = '';
    _rxtStatus('Référentiel créé.');
    await rxtCharger();
  } catch (e) { _rxtStatus('Erreur : ' + (e.message || e), true); }
}

function rxtRender() {
  // v0.48.4 — Liste à gauche / détail à droite (static/referentiel_pe.js).
  if (typeof rxaRendre === 'function') { rxaRendre(); return; }
  const zone = document.getElementById('rxt-liste');
  if (!zone) return;
  if (!RXT_LISTE.length) {
    zone.innerHTML = '<p style="font-size:13px;color:#999">Aucun référentiel '
      + 'externe pour ce niveau. Créez-en un ci-dessus.</p>';
    return;
  }
  zone.innerHTML = RXT_LISTE.map(rxtRenderRef).join('');
}

function rxtRenderRef(ref) {
  const valide = ref.etat === 'valide';
  const badge = valide
    ? '<span style="font-size:11px;background:#d8f0d8;color:#276749;padding:1px 7px;border-radius:10px">validé</span>'
    : '<span style="font-size:11px;background:#fff2c2;color:#976100;padding:1px 7px;border-radius:10px">en cours</span>';
  const seqs = (ref.sequences || []).map(s => rxtRenderSeq(ref, s)).join('');
  return `<div class="card" style="margin-bottom:14px">
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px">
      <strong style="font-size:15px">${escapeHtml(ref.nom || '(sans nom)')}</strong>
      ${badge}
      <span style="font-size:12px;color:#888">${escapeHtml(ref.niveau)} · ${escapeHtml(ref.annee || '')}</span>
      <span style="margin-left:auto;display:flex;gap:6px">
        <button class="btn-sm" onclick="rxtChangerEtat('${ref.id}','${valide ? 'en_cours' : 'valide'}')"
          style="font-size:12px">${valide ? 'Repasser en cours' : 'Valider'}</button>
        <button class="btn-sm" style="font-size:12px;color:var(--danger)"
          onclick="rxtSupprimer('${ref.id}')" aria-label="Supprimer le référentiel">Supprimer</button>
      </span>
    </div>
    <div style="margin-left:6px">${seqs || '<p style="font-size:12px;color:#999">Aucune séquence.</p>'}</div>
    <div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap;align-items:center">
      <input id="rxt-seq-code-${ref.id}" placeholder="code (ex MER1)" style="font-size:12px;width:110px">
      <input id="rxt-seq-nom-${ref.id}" placeholder="nom de la séquence" style="font-size:12px;width:220px">
      <button class="btn-sm" onclick="rxtAjouterSeq('${ref.id}')" style="font-size:12px">+ séquence</button>
    </div>
    <div style="margin-top:10px;padding-top:8px;border-top:1px dashed var(--border)">
      <div style="font-size:12px;font-weight:600;margin-bottom:4px">Documents annuels</div>
      <div style="font-size:11px;color:#888;margin-bottom:6px">
        Documents rattachés au référentiel (récapitulatifs annuels), pas à une séquence.
      </div>
      <div>${rxtRenderDocsAnnuels(ref)}</div>
    </div>
  </div>`;
}

function rxtRenderDocsAnnuels(ref) {
  const docs = (ref.docs_annuels || []).map(d => {
    const url = '/api/referentiels-externes/docs/' + d.id;
    const lien = d.affichable
      ? `<a href="#" onclick="rxtApercu('${d.id}','${escapeHtml(d.nom_fichier)}');return false">${escapeHtml(d.nom_fichier)}</a>`
      : `<a href="${url}" download>${escapeHtml(d.nom_fichier)} (télécharger)</a>`;
    return `<span style="font-size:12px;display:inline-flex;align-items:center;gap:4px;
      background:#f4f4f8;border:1px solid var(--border);border-radius:4px;padding:1px 6px;margin:2px 4px 2px 0">
      ${lien}
      ${typeof rxtTypeSelect === 'function' ? rxtTypeSelect(d) : ''}
      <button class="btn-sm" style="padding:0 3px;color:var(--danger)"
        onclick="rxtSupprimerDoc('${d.id}')" aria-label="Supprimer le document">×</button>
    </span>`;
  }).join('');
  return docs + `<label class="btn-sm" style="font-size:11px;cursor:pointer">+ document(s) annuel(s)
    <input type="file" multiple style="display:none" onchange="rxtImporterDocAnnuel('${ref.id}', this)">
  </label>`;
}

function rxtRenderSeq(ref, seq) {
  const parts = (seq.parties || []).map(p => rxtRenderPartie(ref, p)).join('');
  return `<div style="border:1px solid #d1c4e9;border-radius:6px;margin:10px 0;overflow:hidden">
    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;
                background:#ede7f6;padding:6px 10px;border-bottom:1px solid #d1c4e9">
      <span style="font-size:11px;font-weight:700;color:#5e35b1;text-transform:uppercase;letter-spacing:.5px">Séquence</span>
      <input value="${escapeHtml(seq.code || '')}" placeholder="code"
        style="font-size:14px;font-weight:700;width:90px;background:#fff"
        aria-label="Code de la séquence"
        onchange="rxtModifierSeq('${seq.id}', {code: this.value})">
      <input value="${escapeHtml(seq.nom || '')}" placeholder="nom de la séquence"
        style="font-size:14px;font-weight:600;width:300px;background:#fff" aria-label="Nom de la séquence"
        onchange="rxtModifierSeq('${seq.id}', {nom: this.value})">
      <span style="margin-left:auto;display:flex;gap:4px">
        <button class="btn-sm" style="font-size:11px" title="Monter la séquence"
          aria-label="Monter la séquence" onclick="rxtDeplacerSeq('${seq.id}','haut')">↑</button>
        <button class="btn-sm" style="font-size:11px" title="Descendre la séquence"
          aria-label="Descendre la séquence" onclick="rxtDeplacerSeq('${seq.id}','bas')">↓</button>
        <button class="btn-sm" style="font-size:11px;color:var(--danger)"
          onclick="rxtSupprimerSeq('${seq.id}')" aria-label="Supprimer la séquence">×</button>
      </span>
    </div>
    <div style="padding:6px 10px 8px 16px">
      <div>${parts || '<span style="font-size:12px;color:#999">Aucune partie.</span>'}</div>
      <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap;align-items:center">
        <input id="rxt-part-lib-${seq.id}" placeholder="libellé de la partie" style="font-size:12px;width:220px">
        <input id="rxt-part-nb-${seq.id}" type="number" min="1" value="1" style="font-size:12px;width:52px" aria-label="Nombre de séances">
        <span style="font-size:11px;color:#888">séances</span>
        <button class="btn-sm" onclick="rxtAjouterPartie('${seq.id}')" style="font-size:12px">+ partie</button>
      </div>
    </div>
  </div>`;
}

function rxtRenderPartie(ref, p) {
  const docs = (p.docs || []).map(d => {
    const url = '/api/referentiels-externes/docs/' + d.id;
    // PDF → aperçu inline (dans l'appli) ; autres → téléchargement.
    const lien = d.affichable
      ? `<a href="#" onclick="rxtApercu('${d.id}','${escapeHtml(d.nom_fichier)}');return false">${escapeHtml(d.nom_fichier)}</a>`
      : `<a href="${url}" download>${escapeHtml(d.nom_fichier)} (télécharger)</a>`;
    return `<span style="font-size:12px;display:inline-flex;align-items:center;gap:4px;
      background:#f4f4f8;border:1px solid var(--border);border-radius:4px;padding:1px 6px;margin:2px 4px 2px 0">
      ${lien}
      ${typeof rxtTypeSelect === 'function' ? rxtTypeSelect(d) : ''}
      <button class="btn-sm" style="padding:0 3px;color:var(--danger)"
        onclick="rxtSupprimerDoc('${d.id}')" aria-label="Supprimer le document">×</button>
    </span>`;
  }).join('');
  return `<div style="margin:3px 0">
    <span style="font-size:12px;color:#666">P${p.numero} ·</span>
    <input value="${escapeHtml(p.libelle || '')}" placeholder="libellé de la partie"
      style="font-size:12px;width:240px" aria-label="Libellé de la partie"
      onchange="rxtModifierPartie('${p.id}', {libelle: this.value})">
    <input type="number" min="1" value="${p.nb_seances}"
      style="font-size:12px;width:52px" aria-label="Nombre de séances de la partie"
      onchange="rxtModifierPartie('${p.id}', {nb_seances: this.value})">
    <span style="font-size:11px;color:#888">séance(s)</span>
    <button class="btn-sm" style="font-size:11px" title="Monter la partie"
      aria-label="Monter la partie" onclick="rxtDeplacerPartie('${p.id}','haut')">↑</button>
    <button class="btn-sm" style="font-size:11px" title="Descendre la partie"
      aria-label="Descendre la partie" onclick="rxtDeplacerPartie('${p.id}','bas')">↓</button>
    <button class="btn-sm" style="font-size:11px;color:var(--danger)"
      onclick="rxtSupprimerPartie('${p.id}')" aria-label="Supprimer la partie">×</button>
    <div style="margin:2px 0 2px 10px">${docs}
      <label class="btn-sm" style="font-size:11px;cursor:pointer">+ document(s)
        <input type="file" multiple style="display:none" onchange="rxtImporterDoc('${p.id}', this)">
      </label>
    </div>
  </div>`;
}

// ── Actions ──────────────────────────────────────────────────────────────────

async function rxtChangerEtat(refId, etat) {
  try {
    await api('/api/referentiels-externes/' + refId + '/etat',
      { method: 'POST', body: JSON.stringify({ etat }) });
    await rxtCharger();
  } catch (e) { _rxtStatus('Erreur : ' + (e.message || e), true); }
}

async function rxtSupprimer(refId) {
  if (!confirm('Supprimer ce référentiel externe et tous ses documents ?')) return;
  try {
    await fetch('/api/referentiels-externes/' + refId, { method: 'DELETE' });
    await rxtCharger();
  } catch (e) { _rxtStatus('Erreur : ' + (e.message || e), true); }
}

async function rxtAjouterSeq(refId) {
  const code = document.getElementById('rxt-seq-code-' + refId).value;
  const nom = document.getElementById('rxt-seq-nom-' + refId).value;
  try {
    await api('/api/referentiels-externes/' + refId + '/sequences',
      { method: 'POST', body: JSON.stringify({ code, nom }) });
    await rxtCharger();
  } catch (e) { _rxtStatus('Erreur : ' + (e.message || e), true); }
}

async function rxtSupprimerSeq(seqId) {
  if (!confirm('Supprimer cette séquence et ses documents ?')) return;
  try {
    await fetch('/api/referentiels-externes/sequences/' + seqId, { method: 'DELETE' });
    await rxtCharger();
  } catch (e) { _rxtStatus('Erreur : ' + (e.message || e), true); }
}

async function rxtAjouterPartie(seqId) {
  const libelle = document.getElementById('rxt-part-lib-' + seqId).value;
  const nb = document.getElementById('rxt-part-nb-' + seqId).value;
  try {
    await api('/api/referentiels-externes/sequences/' + seqId + '/parties',
      { method: 'POST', body: JSON.stringify({ libelle, nb_seances: nb }) });
    await rxtCharger();
  } catch (e) { _rxtStatus('Erreur : ' + (e.message || e), true); }
}

async function rxtSupprimerPartie(partieId) {
  if (!confirm('Supprimer cette partie et ses documents ?')) return;
  try {
    await fetch('/api/referentiels-externes/parties/' + partieId, { method: 'DELETE' });
    await rxtCharger();
  } catch (e) { _rxtStatus('Erreur : ' + (e.message || e), true); }
}

async function rxtImporterDocAnnuel(refId, input) {
  if (!input.files || !input.files.length) return;
  const fichiers = Array.from(input.files);
  let ok = 0, echecs = 0;
  _rxtStatus('Import de ' + fichiers.length + ' document(s) annuel(s)…');
  for (const f of fichiers) {
    const fd = new FormData();
    fd.append('fichier', f);
    try {
      const r = await fetch('/api/referentiels-externes/' + refId + '/docs-annuels',
        { method: 'POST', body: fd });
      if (!r.ok) throw new Error();
      ok++;
    } catch (e) { echecs++; }
  }
  input.value = '';
  _rxtStatus(echecs ? `${ok} ajouté(s), ${echecs} en échec.`
    : `${ok} document(s) annuel(s) ajouté(s).`, echecs > 0);
  await rxtCharger();
}

async function rxtImporterDoc(partieId, input) {
  if (!input.files || !input.files.length) return;
  const fichiers = Array.from(input.files);
  let ok = 0, echecs = 0;
  _rxtStatus('Import de ' + fichiers.length + ' document(s)…');
  // L'API prend un fichier par requête : on les envoie séquentiellement.
  for (const f of fichiers) {
    const fd = new FormData();
    fd.append('fichier', f);
    try {
      const r = await fetch('/api/referentiels-externes/parties/' + partieId + '/docs',
        { method: 'POST', body: fd });
      if (!r.ok) throw new Error();
      ok++;
    } catch (e) { echecs++; }
  }
  input.value = '';  // réinitialiser pour permettre de re-sélectionner
  _rxtStatus(echecs
    ? `${ok} document(s) ajouté(s), ${echecs} en échec.`
    : `${ok} document(s) ajouté(s).`, echecs > 0);
  await rxtCharger();
}

async function rxtDeplacerSeq(seqId, sens) {
  try {
    await api('/api/referentiels-externes/sequences/' + seqId + '/deplacer',
      { method: 'POST', body: JSON.stringify({ sens }) });
    await rxtCharger();
  } catch (e) { _rxtStatus('Erreur : ' + (e.message || e), true); }
}

async function rxtDeplacerPartie(partieId, sens) {
  try {
    await api('/api/referentiels-externes/parties/' + partieId + '/deplacer',
      { method: 'POST', body: JSON.stringify({ sens }) });
    await rxtCharger();
  } catch (e) { _rxtStatus('Erreur : ' + (e.message || e), true); }
}

async function rxtModifierSeq(seqId, champs) {
  try {
    await api('/api/referentiels-externes/sequences/' + seqId,
      { method: 'PUT', body: JSON.stringify(champs) });
    _rxtStatus('Séquence mise à jour.');
    await rxtCharger();
  } catch (e) { _rxtStatus('Erreur : ' + (e.message || e), true); }
}

async function rxtModifierPartie(partieId, champs) {
  try {
    await api('/api/referentiels-externes/parties/' + partieId,
      { method: 'PUT', body: JSON.stringify(champs) });
    _rxtStatus('Partie mise à jour.');
    await rxtCharger();
  } catch (e) { _rxtStatus('Erreur : ' + (e.message || e), true); }
}

async function rxtSupprimerDoc(docId) {
  if (!confirm('Supprimer ce document ?')) return;
  try {
    await fetch('/api/referentiels-externes/docs/' + docId, { method: 'DELETE' });
    await rxtCharger();
  } catch (e) { _rxtStatus('Erreur : ' + (e.message || e), true); }
}

// Aperçu d'un document PDF DANS l'appli (iframe), au lieu d'un onglet externe.
function rxtApercu(docId, nom) {
  const zone = document.getElementById('rxt-apercu');
  const frame = document.getElementById('rxt-apercu-frame');
  const lbl = document.getElementById('rxt-apercu-nom');
  if (!zone || !frame) return;
  frame.src = '/api/referentiels-externes/docs/' + docId;
  if (lbl) lbl.textContent = nom || 'Document';
  zone.style.display = '';
  zone.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function rxtFermerApercu() {
  const zone = document.getElementById('rxt-apercu');
  const frame = document.getElementById('rxt-apercu-frame');
  if (frame) frame.src = 'about:blank';
  if (zone) zone.style.display = 'none';
}
