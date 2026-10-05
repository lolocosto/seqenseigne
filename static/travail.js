// ============================================================================
// static/travail.js — v0.47.0 (v0.47.1 : synthèse pour le cahier de textes Pronote)
// Suivi › Travail : même séance que le Début de séance et l'Observation
// (état SC de static/seance.js, en-tête commun).
//   - Donner du travail (fin de séance) : à faire / à rendre, échéance
//     (prochaine séance, 3 jours, 1 semaine, ou une séance choisie) ; les
//     absents le reçoivent par le rattrapage du Début de séance et leur
//     échéance part de cette remise ;
//   - À vérifier : « à faire » dont l'échéance est cette séance → cocher les
//     non faits (+ « à rattraper » : revient pour lui à la séance suivante) ;
//   - À ramasser : « à rendre » et documents « à rapporter » encore ouverts →
//     coche « rendu » ; « Clore » pour fermer la fenêtre ;
//   - En retard : récapitulatif de la classe.
// Backend : /api/travail (services/travail.py).
// ============================================================================

const TW = { donnees: null, occupe: false };
const _TW_TYPE = { faire: 'à faire', rendre: 'à rendre', rapporter: 'à rapporter' };

function _twE(s) { return escapeHtml(String(s == null ? '' : s)); }
function _twSeance() {
  const s = SC.donnees.seance;
  return { annee: _scAnnee(), classe_id: _scClasse(), date: s.date, creneau: s.creneau };
}
function _twNom(eid) {
  const e = (SC.donnees.eleves || []).find(x => x.id === eid);
  return e ? e.etiquette : eid;
}
function _twEch(e) { return e ? `${_scDateFr(e[0])} ${e[1]}` : '—'; }

async function twInit() {
  if (typeof SC === 'undefined') return;
  if (!SC.donnees) { await scInit(); return; }    // scCharger appelle twCharger
  await twCharger();
}

async function twCharger() {
  const z = document.getElementById('tw-corps');
  if (!z || !SC.donnees) return;
  const q = _twSeance();
  try {
    TW.donnees = await _scApi(`/api/travail?annee=${encodeURIComponent(q.annee)}`
      + `&classe_id=${encodeURIComponent(q.classe_id)}&date=${q.date}&creneau=${encodeURIComponent(q.creneau)}`);
  } catch (e) { z.innerHTML = `<p class="sc-vide">${_twE(e.message)}</p>`; return; }
  twRendre();
  if (TS.ouvert) await _tsCharger();     // v0.47.1 — synthèse ouverte : suivre la séance
}

function twRendre() {
  const z = document.getElementById('tw-corps');
  const d = TW.donnees;
  if (!z || !d) return;
  const suiv = SC.donnees.seance_suivante;
  z.innerHTML = `
    <div class="tw-grille">
      <section class="tw-bloc tw-pronote">
        <div class="sc-bloc-titre">Cahier de textes</div>
        <button class="btn-sm btn-prim" onclick="twSyntheseOuvrir()">Synthèse Pronote</button>
        <span class="sc-aide">contenu de la séance et travail à faire, à copier dans Pronote</span>
        <div id="tw-synthese"></div>
      </section>
      <section class="tw-bloc">
        <div class="sc-bloc-titre">Donner du travail</div>
        <div class="tw-form">
          <input id="tw-lib" placeholder="Ex. : exercices 12 et 13 p. 40">
          <select id="tw-type"><option value="faire">à faire (vérifié en classe)</option>
            <option value="rendre">à rendre (ramassé)</option></select>
          <select id="tw-delai-type" onchange="twDelaiType()">
            <option value="prochaine">à la prochaine séance${suiv ? ` (${_scDateFr(suiv.date)})` : ''}</option>
            <option value="jours">dans … jour(s)</option>
            <option value="semaines">dans … semaine(s)</option>
          </select>
          <span id="tw-delai-nb" class="tw-delai-nb" style="display:none">
            <input id="tw-delai-n" type="number" min="1" max="60" step="1" value="1">
            <span id="tw-delai-unite">jour(s)</span>
          </span>
          <button class="btn-sm btn-prim" onclick="twDonner()">Donner</button>
        </div>
        <p class="sc-aide">Les élèves absents le recevront avec les documents à rattraper du Début de
          séance ; leur échéance partira de ce jour-là.</p>
        ${d.donnes_ici.length ? `<ul class="tw-liste">${d.donnes_ici.map(t => `
          <li><span class="tw-tag tw-tag-${t.retour}">${_TW_TYPE[t.retour]}</span> ${_twE(t.libelle)}
            <span class="sc-aide">pour le ${_twEch(t.echeance_classe)}</span>
            ${t.origine === 'travail' ? `<button class="btn-lien sc-doc-suppr" onclick="twSupprimer('${t.id}')">supprimer</button>`
              : '<span class="tw-tag">prévu dans la progression</span>'}</li>`).join('')}</ul>` : ''}
      </section>

      <section class="tw-bloc">
        <div class="sc-bloc-titre">À vérifier (travail à faire pour aujourd'hui)</div>
        ${d.a_verifier.length ? d.a_verifier.map(t => `
          <div class="tw-item">
            <div class="tw-item-titre">${_twE(t.libelle)} <span class="sc-aide">donné le ${_scDateFr(t.donne_date)}</span></div>
            <p class="sc-aide">Cocher les élèves qui ne l'ont pas fait.</p>
            <ul class="tw-eleves">${t.eleves.map(e => `
              <li><label><input type="checkbox" ${e.non_fait ? 'checked' : ''}
                  onchange="twNonFait('${t.id}', '${e.eleve_id}', this.checked, false)"> ${_twE(_twNom(e.eleve_id))}</label>
                ${e.rattrapage ? '<span class="tw-tag">rattrapage</span>' : ''}
                ${e.non_fait ? `<label class="tw-ratt"><input type="checkbox" ${e.a_rattraper ? 'checked' : ''}
                  onchange="twNonFait('${t.id}', '${e.eleve_id}', true, this.checked)"> à rattraper</label>` : ''}</li>`).join('')}
            </ul>
          </div>`).join('') : '<p class="sc-aide">Rien à vérifier à cette séance.</p>'}
      </section>

      <section class="tw-bloc">
        <div class="sc-bloc-titre">À ramasser (à rendre, à rapporter)</div>
        ${d.a_ramasser.length ? d.a_ramasser.map(t => {
          const reste = t.eleves.filter(e => !e.rendu).length;
          return `
          <div class="tw-item">
            <div class="tw-item-titre"><span class="tw-tag tw-tag-${t.retour}">${_TW_TYPE[t.retour]}</span>
              ${_twE(t.libelle)} <span class="sc-aide">donné le ${_scDateFr(t.donne_date)} — ${reste} en attente</span>
              <button class="btn-sm tw-clore" onclick="twClore('${t.id}')" title="Ne plus attendre de retour">Clore</button></div>
            <ul class="tw-eleves">${t.eleves.map(e => `
              <li class="${e.en_retard && !e.rendu ? 'tw-retard' : ''}"><label><input type="checkbox" ${e.rendu ? 'checked' : ''}
                  onchange="twRendu('${t.id}', '${e.eleve_id}', this.checked)"> ${_twE(_twNom(e.eleve_id))}</label>
                <span class="sc-aide">échéance ${_twEch(e.echeance)}</span>
                ${e.en_retard && !e.rendu ? '<span class="tw-tag tw-tag-retard">en retard</span>' : ''}</li>`).join('')}
            </ul>
          </div>`;
        }).join('') : '<p class="sc-aide">Rien à ramasser.</p>'}
      </section>

      <section class="tw-bloc">
        <div class="sc-bloc-titre">En retard (classe)</div>
        ${d.en_retard.length ? `<ul class="tw-retards">${d.en_retard.map(r => `
          <li><strong>${_twE(_twNom(r.eleve_id))}</strong> :
            ${r.elements.map(x => `${_twE(x.libelle)} <span class="sc-aide">(${_TW_TYPE[x.retour]}, échéance ${_twEch(x.echeance)})</span>`).join(' ; ')}</li>`).join('')}</ul>`
          : '<p class="sc-aide">Personne n\'est en retard.</p>'}
      </section>
    </div>`;
}

async function _twAction(url, opts) {
  if (TW.occupe) return;
  TW.occupe = true;
  try { await _scApi(url, opts); }
  catch (e) { if (typeof showToast === 'function') showToast(e.message, true); else alert(e.message); }
  TW.occupe = false;
  await twCharger();
  if (TS.ouvert) await _tsCharger();
}

function twDonner() {
  const lib = document.getElementById('tw-lib').value.trim();
  if (!lib) { document.getElementById('tw-lib').focus(); return; }
  return _twAction('/api/travail', { method: 'POST', body: JSON.stringify({
    ..._twSeance(), libelle: lib, retour: document.getElementById('tw-type').value,
    delai_jours: _twDelaiJours() }) });
}

// v0.47.2 — Délai : « à la prochaine séance », « dans x jours », « dans x
// semaines » (= la prochaine séance au moins x jours / x semaines après).
function twDelaiType() {
  const t = document.getElementById('tw-delai-type').value;
  document.getElementById('tw-delai-nb').style.display = t === 'prochaine' ? 'none' : '';
  document.getElementById('tw-delai-unite').textContent = t === 'semaines' ? 'semaine(s)' : 'jour(s)';
}

function _twDelaiJours() {
  const t = document.getElementById('tw-delai-type').value;
  const n = Math.max(1, parseInt(document.getElementById('tw-delai-n').value || '1', 10) || 1);
  return t === 'prochaine' ? 1 : (t === 'semaines' ? 7 * n : n);
}

function twSupprimer(id) {
  if (!confirm('Supprimer ce travail ?')) return;
  return _twAction(`/api/travail/${id}`, { method: 'DELETE' });
}

function twNonFait(id, eleveId, nonFait, aRattraper) {
  return _twAction(`/api/travail/${id}/non-fait`, { method: 'PUT', body: JSON.stringify({
    ..._twSeance(), eleve_id: eleveId, non_fait: nonFait, a_rattraper: aRattraper }) });
}

function twRendu(id, eleveId, rendu) {
  return _twAction(`/api/travail/${id}/rendu`, { method: 'PUT', body: JSON.stringify({
    ..._twSeance(), eleve_id: eleveId, rendu }) });
}

function twClore(id) {
  if (!confirm('Clore ? Les élèves qui ne l\'ont pas rendu ne seront plus attendus ni en retard.')) return;
  return _twAction(`/api/travail/${id}/clos`, { method: 'PUT', body: JSON.stringify({ clos: true }) });
}


// ── v0.47.1 — Synthèse Pronote ──────────────────────────────────────────────

const TS = { ouvert: false, d: null };

async function twSyntheseOuvrir() {
  TS.ouvert = !TS.ouvert;
  if (!TS.ouvert) { document.getElementById('tw-synthese').innerHTML = ''; return; }
  await _tsCharger();
}

async function _tsCharger(choix) {
  const q = _twSeance();
  try {
    TS.d = choix
      ? await _scApi('/api/seance/synthese', { method: 'PUT', body: JSON.stringify({ ...q, choix }) })
      : await _scApi(`/api/seance/synthese?annee=${encodeURIComponent(q.annee)}&classe_id=${encodeURIComponent(q.classe_id)}`
          + `&date=${q.date}&creneau=${encodeURIComponent(q.creneau)}`);
  } catch (e) {
    document.getElementById('tw-synthese').innerHTML = `<p class="sc-vide">${_twE(e.message)}</p>`;
    return;
  }
  _tsRendre();
}

function _tsCases(liste, choisis, cle) {
  return liste.map(x => `<label class="ts-case"><input type="checkbox" ${choisis.includes(x.id) ? 'checked' : ''}
    onchange="tsBasculer('${cle}', '${x.id}', this.checked)"> ${_twE(x.titre)}</label>`).join('');
}

function _tsRendre() {
  const z = document.getElementById('tw-synthese');
  const d = TS.d;
  if (!z || !d) return;
  const bloc = (cle, titre) => {
    const faits = new Set(d.deja_faits[cle]);
    const neufs = d.candidats[cle].filter(x => !faits.has(x.id) || d.choix[cle].includes(x.id));
    const anciens = d.candidats[cle].filter(x => faits.has(x.id) && !d.choix[cle].includes(x.id));
    if (!d.candidats[cle].length) return '';
    return `<div class="ts-groupe"><div class="ts-titre">${titre}</div>${_tsCases(neufs, d.choix[cle], cle)}
      ${anciens.length ? `<details class="ts-faits"><summary>Déjà faits dans ce créneau (${anciens.length})</summary>
        ${_tsCases(anciens, d.choix[cle], cle)}</details>` : ''}</div>`;
  };
  const choisies = d.choix.activites;
  z.innerHTML = `
    <div class="ts-panneau">
      ${d.externe ? '' : `<div class="ts-cours">${bloc('notions', 'Notions')}${bloc('methodes', 'Méthodes')}</div>`}
      <div class="ts-groupe"><div class="ts-titre">Activités (dans l'ordre de la séance)</div>
        <div class="ts-choisies">${choisies.length ? choisies.map((a, i) =>
          `<span class="ts-chip">${i + 1}. ${_twE(a)} <button class="btn-lien" onclick="tsRetirerActivite(${i})">✕</button></span>`).join('')
          : '<span class="sc-aide">aucune</span>'}</div>
        <div class="ts-dispo">${d.activites.map((a, k) =>
          `<button class="btn-sm" onclick="tsAjouterActivite(${k})">+ ${_twE(a.libelle)}</button>`).join('')}</div>
      </div>
      <div class="ts-groupe"><div class="ts-titre">${d.externe ? 'Contenu (référentiel externe)' : 'Complément (facultatif)'}</div>
        <textarea id="ts-libre" rows="2" onchange="tsTexteLibre(this.value)">${_twE(d.choix.texte_libre)}</textarea></div>
      <div class="ts-sortie">
        <div><div class="ts-titre">Contenu de la séance <button class="btn-sm" onclick="tsCopier('ts-contenu')">Copier</button></div>
          <textarea id="ts-contenu" rows="7" readonly>${_twE(d.contenu)}</textarea></div>
        <div><div class="ts-titre">Travail à faire <button class="btn-sm" onclick="tsCopier('ts-travail')">Copier</button></div>
          <textarea id="ts-travail" rows="7" readonly>${_twE(d.travail)}</textarea></div>
      </div>
    </div>`;
}

function _tsChoix() { return JSON.parse(JSON.stringify(TS.d.choix)); }

function tsBasculer(cle, id, coche) {
  const c = _tsChoix();
  c[cle] = coche ? [...c[cle].filter(x => x !== id), id] : c[cle].filter(x => x !== id);
  // Garder l'ordre des candidats (ordre de la partie).
  const ordre = TS.d.candidats[cle].map(x => x.id);
  c[cle].sort((a, b) => ordre.indexOf(a) - ordre.indexOf(b));
  return _tsCharger(c);
}

function tsAjouterActivite(k) {
  const c = _tsChoix();
  c.activites.push(TS.d.activites[k].libelle);
  return _tsCharger(c);
}

function tsRetirerActivite(i) {
  const c = _tsChoix();
  c.activites.splice(i, 1);
  return _tsCharger(c);
}

function tsTexteLibre(v) {
  const c = _tsChoix();
  c.texte_libre = v;
  return _tsCharger(c);
}

async function tsCopier(id) {
  const t = document.getElementById(id);
  if (!t) return;
  try { await navigator.clipboard.writeText(t.value); }
  catch (e) { t.select(); document.execCommand('copy'); }
  if (typeof showToast === 'function') showToast('Copié : à coller dans Pronote.');
}
