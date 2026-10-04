// ============================================================================
// static/travail.js — v0.47.0
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
}

function twRendre() {
  const z = document.getElementById('tw-corps');
  const d = TW.donnees;
  if (!z || !d) return;
  const suiv = SC.donnees.seance_suivante;
  z.innerHTML = `
    <div class="tw-grille">
      <section class="tw-bloc">
        <div class="sc-bloc-titre">Donner du travail</div>
        <div class="tw-form">
          <input id="tw-lib" placeholder="Ex. : exercices 12 et 13 p. 40">
          <select id="tw-type"><option value="faire">à faire (vérifié en classe)</option>
            <option value="rendre">à rendre (ramassé)</option></select>
          <select id="tw-delai">
            <option value="1">pour la prochaine séance${suiv ? ` (${_scDateFr(suiv.date)})` : ''}</option>
            <option value="3">dans au moins 3 jours</option>
            <option value="7">dans au moins 1 semaine</option>
          </select>
          <button class="btn-sm btn-prim" onclick="twDonner()">Donner</button>
        </div>
        <p class="sc-aide">Les élèves absents le recevront avec les documents à rattraper du Début de
          séance ; leur échéance partira de ce jour-là.</p>
        ${d.donnes_ici.length ? `<ul class="tw-liste">${d.donnes_ici.map(t => `
          <li><span class="tw-tag tw-tag-${t.retour}">${_TW_TYPE[t.retour]}</span> ${_twE(t.libelle)}
            <span class="sc-aide">pour le ${_twEch(t.echeance_classe)}</span>
            <button class="btn-lien sc-doc-suppr" onclick="twSupprimer('${t.id}')">supprimer</button></li>`).join('')}</ul>` : ''}
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
}

function twDonner() {
  const lib = document.getElementById('tw-lib').value.trim();
  if (!lib) { document.getElementById('tw-lib').focus(); return; }
  return _twAction('/api/travail', { method: 'POST', body: JSON.stringify({
    ..._twSeance(), libelle: lib, retour: document.getElementById('tw-type').value,
    delai_jours: parseInt(document.getElementById('tw-delai').value, 10) }) });
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
