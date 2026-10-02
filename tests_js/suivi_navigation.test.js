// tests_js/suivi_navigation.test.js — v0.19.1.2
//
// Navigation « Suivi de classe » à 2 barres (portées Suivi annuel / Gestion),
// calquée sur la zone Référentiel. On teste le module `suivi*` d'app.js de
// façon isolée : on extrait le bloc de code (de `const SUIVI_PORTEES` à la fin
// de `sousOnglet`) et on l'évalue dans un DOM jsdom minimal reproduisant les
// 2 barres + les pools de sélecteurs, avec des stubs pour les dépendances
// (gestionSousOnglet, renderClassesList, progInit, atelGardeAvantTransition).
//
// Invariants vérifiés :
//   - bascule de portée → boutons actifs + visibilité des boutons d'atelier ;
//   - défaut « Suivi de classe » dans la portée annuel (décision C) ;
//   - les sélecteurs sont déplacés depuis le bon pool selon l'atelier actif
//     (décision B : progression = 4 sélecteurs, suivi = 2) ;
//   - le shim sousOnglet() mappe les anciens noms.

import { describe, it, expect, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const APP = readFileSync(join(__dirname, '..', 'static', 'app.js'), 'utf-8');

// Extrait le bloc navigation : de la ligne `const SUIVI_PORTEES = {` jusqu'à
// la fermeture de `function sousOnglet(...)` (juste avant `async function
// loadClasses`).
function extraireBlocNavigation(src) {
  const debut = src.indexOf('const SUIVI_PORTEES');
  const ancreFin = src.indexOf('async function loadClasses');
  if (debut < 0 || ancreFin < 0) throw new Error('bornes du bloc nav introuvables');
  return src.slice(debut, ancreFin);
}

const DOM_HTML = `
  <nav>
    <button class="tab" data-tab="classe" role="tab"></button>
    <button class="tab" data-tab="planification" role="tab"></button>
    <button class="tab" data-tab="parametrage" role="tab"></button>
  </nav>
  <main id="tab-classe"></main>
  <main id="tab-systeme" style="display:none">
    <button id="systeme-btn-admin"></button><button id="systeme-btn-preferences"></button>
  </main>
  <main id="tab-admin" style="display:none"></main>
  <main id="tab-preferences" style="display:none"></main>
  <div class="toolbar">
    <div id="suivi-portee-row">
      <button class="vbtn active suivi-portee-suivi" id="suivi-btn-portee-suivi"></button>
      <button class="vbtn suivi-portee-suivi" id="suivi-btn-portee-gestion"></button>
    </div>
    <div id="suivi-portee-selecteurs"></div>
  </div>
  <div class="toolbar">
    <button class="vbtn suivi-grp-planification active" id="suivi-btn-progression"></button>
    <button class="vbtn suivi-grp-planification" id="suivi-btn-edt"></button>
    <button class="vbtn suivi-grp-suivi" id="suivi-btn-debut" style="display:none"></button>
    <button class="vbtn suivi-grp-suivi" id="suivi-btn-observation" style="display:none"></button>
    <button class="vbtn suivi-grp-suivi" id="suivi-btn-suivi" style="display:none"></button>
    <button class="vbtn suivi-grp-gestion" id="suivi-btn-classe" style="display:none"></button>
    <button class="vbtn suivi-grp-gestion" id="suivi-btn-etab" style="display:none"></button>
    <button class="vbtn suivi-grp-gestion" id="suivi-btn-observables" style="display:none"></button>
  </div>
  <label id="suivi-annee-globale-wrap" class="suivi-sel" style="display:none">
    <select id="suivi-annee-globale"></select>
  </label>
  <div id="stab-edt" style="display:none"></div>
  <div id="stab-indispo" style="display:none"></div>
  <div id="stab-progression" style="display:none"></div>
  <div id="stab-suivi" style="display:none"></div>
  <div id="stab-debut" style="display:none"></div>
  <div id="stab-observation" style="display:none"></div>
  <div id="stab-observables" style="display:none"></div>
  <!-- Pool unifié des sélecteurs contextuels (data-suivi-sel="type"). -->
  <div id="suivi-selecteurs-pool" style="display:none">
    <label class="suivi-sel" data-suivi-sel="etablissement" id="lab-etab"><select id="suivi-etab-global"></select></label>
    <label class="suivi-sel" data-suivi-sel="niveau" id="lab-niveau"><select id="prog-sel-niveau"></select></label>
    <label class="suivi-sel" data-suivi-sel="referentiel" id="lab-ref"><select id="prog-sel-ref"></select></label>
    <label class="suivi-sel" data-suivi-sel="classe" id="lab-classe"><select id="classe-sel"></select></label>
    <label class="suivi-sel" data-suivi-sel="annee" id="lab-annee"><select id="annee-sel"></select></label>
  </div>
  <div id="stab-parametrage" style="display:none">
    <div id="prog-selecteurs-pool">
      <label class="suivi-sel" data-prog-sel id="lab-p-annee"><select id="prog-sel-annee"></select></label>
      <label class="suivi-sel" data-prog-sel id="lab-p-etab"><select id="prog-sel-etab"></select></label>
    </div>
  </div>
`;

let nav;

function chargerNav() {
  // Réinitialiser le DOM et le localStorage entre chaque test.
  document.body.innerHTML = DOM_HTML;
  window.localStorage.clear();

  // Stubs des dépendances appelées par le module.
  const appels = { gestion: [], progInit: 0 };
  window.gestionSousOnglet = (n) => { appels.gestion.push(n); };
  window.renderClassesList = () => {};
  window.chargerEtablissementsEtBandeau = () => {};
  window.progInit = () => { appels.progInit++; return Promise.resolve(); };
  // Pas de garde de transition dans le test (exécution synchrone directe).
  window.atelGardeAvantTransition = undefined;

  // Évaluer le bloc dans un scope qui expose les fonctions sur un objet.
  const bloc = extraireBlocNavigation(APP);
  // Le bloc déclare des const/function au top-level ; on les capture en
  // les ré-exportant via un return. On fournit aussi les globales que le bloc
  // référence mais qui sont déclarées ailleurs dans app.js (hors du bloc) :
  // ANNEE_ACTIVE, ANNEES, api, escapeHtml.
  const prelude = `
    var ANNEE_ACTIVE = '2025-2026';
    var ANNEES = ['2025-2026', '2026-2027'];
    var api = async () => ({ etablissements: [] });
    var escapeHtml = (s) => String(s == null ? '' : s);
  `;
  const exporter = `
    ${prelude}
    ${bloc}
    return { suiviPorteeSwitch, suiviSwitch, suiviRenderSelecteurs, suiviInit,
             sousOnglet, systemeSwitch, get SUIVI_PORTEE_ACTIVE(){return SUIVI_PORTEE_ACTIVE;},
             get SUIVI_ATELIER_ACTIF(){return SUIVI_ATELIER_ACTIF;} };
  `;
  // 'window' et 'document' viennent de jsdom (globals du test).
  // eslint-disable-next-line no-new-func
  const fabrique = new Function('window', 'document', 'localStorage', exporter);
  nav = fabrique(window, document, window.localStorage);
  nav._appels = appels;
  return nav;
}

const $ = (id) => document.getElementById(id);
const selZone = () => $('suivi-portee-selecteurs');

describe('Navigation Suivi — portées', () => {
  beforeEach(() => { chargerNav(); });

  it('portée planification : masque la barre de portées', () => {
    nav.suiviInit();
    nav.suiviPorteeSwitch('planification');
    expect($('suivi-portee-row').style.display).toBe('none');
    // Un atelier de planification est visible.
    expect($('stab-progression').style.display === ''
        || $('stab-edt').style.display === '').toBe(true);
  });

  it('bascule vers Suivi puis Paramétrage (v0.42.0 : un onglet principal par portée)', () => {
    nav.suiviInit();
    nav.suiviPorteeSwitch('suivi');
    // v0.42.0 — Plus de rangée de portées : chaque portée a son onglet principal.
    expect($('suivi-portee-row').style.display).toBe('none');
    expect($('suivi-btn-suivi').style.display).toBe('');
    expect($('suivi-btn-debut').style.display).toBe('');
    expect($('suivi-btn-observation').style.display).toBe('');
    // Défaut de la portée suivi : Début de séance.
    expect(nav.SUIVI_ATELIER_ACTIF).toBe('debut');
    expect($('stab-debut').style.display).toBe('');
    nav.suiviPorteeSwitch('gestion');
    expect($('suivi-btn-portee-gestion').classList.contains('active')).toBe(true);
    expect($('suivi-btn-progression').style.display).toBe('none');
    expect($('suivi-btn-suivi').style.display).toBe('none');
    expect($('suivi-btn-classe').style.display).toBe('');
    expect($('suivi-btn-etab').style.display).toBe('');
    expect($('suivi-btn-observables').style.display).toBe('');
    expect($('suivi-btn-debut').style.display).toBe('none');
    expect($('stab-parametrage').style.display).toBe('');
    expect(nav._appels.gestion).toContain('classes');
  });

  it('Paramétrage > Observables : panneau dédié (v0.42.0)', () => {
    nav.suiviInit();
    nav.suiviPorteeSwitch('gestion');
    nav.suiviSwitch('observables');
    expect($('stab-observables').style.display).toBe('');
    expect($('stab-parametrage').style.display).toBe('none');
  });

  it('v0.42.1 — Sélecteurs : Année, Établissement, Niveau, Classe dans tout le Suivi', () => {
    nav.suiviInit();
    nav.suiviPorteeSwitch('suivi');
    for (const a of ['debut', 'observation', 'suivi']) {
      nav.suiviSwitch(a);
      const types = [...selZone().querySelectorAll('[data-suivi-sel]')].map(l => l.dataset.suiviSel);
      expect(types).toEqual(['annee', 'etablissement', 'niveau', 'classe']);
    }
  });

  it('v0.42.1 — Observables : Niveau seul', () => {
    nav.suiviInit();
    nav.suiviPorteeSwitch('gestion');
    nav.suiviSwitch('observables');
    const types = [...selZone().querySelectorAll('[data-suivi-sel]')].map(l => l.dataset.suiviSel);
    expect(types).toEqual(['niveau']);
  });

  it("l'onglet principal actif suit la portée (v0.42.0)", () => {
    nav.suiviInit();
    nav.suiviPorteeSwitch('gestion');
    expect(document.querySelector('.tab[data-tab="parametrage"]').classList.contains('active')).toBe(true);
    expect(document.querySelector('.tab[data-tab="classe"]').classList.contains('active')).toBe(false);
    nav.suiviPorteeSwitch('planification');
    expect(document.querySelector('.tab[data-tab="planification"]').classList.contains('active')).toBe(true);
    nav.suiviPorteeSwitch('suivi');
    expect(document.querySelector('.tab[data-tab="classe"]').classList.contains('active')).toBe(true);
  });

  it('Système : bascule Administration / Préférences mémorisée (v0.42.0)', () => {
    window.adminSousOnglet = () => {};
    nav.systemeSwitch('preferences');
    expect($('tab-preferences').style.display).toBe('');
    expect($('tab-admin').style.display).toBe('none');
    expect($('systeme-btn-preferences').classList.contains('active')).toBe(true);
    expect(window.localStorage.getItem('systeme-sous-onglet')).toBe('preferences');
    nav.systemeSwitch('admin');
    expect($('tab-admin').style.display).toBe('');
    expect($('tab-preferences').style.display).toBe('none');
  });

  it('Gestion > Établissement appelle gestionSousOnglet(etabs)', () => {
    nav.suiviInit();
    nav.suiviPorteeSwitch('gestion');
    nav.suiviSwitch('etab');
    expect($('suivi-btn-etab').classList.contains('active')).toBe(true);
    expect(nav._appels.gestion).toContain('etabs');
  });

  it('Progression : init de l\'atelier + panneau visible', () => {
    nav.suiviInit();
    nav.suiviSwitch('progression');
    expect($('stab-progression').style.display).toBe('');
    expect(nav._appels.progInit).toBeGreaterThanOrEqual(1);
  });
});

describe('Navigation Suivi — sélecteurs contextuels (décision B)', () => {
  beforeEach(() => { chargerNav(); });

  it('Progression : Établissement + Niveau + Référentiel contextuels', () => {
    nav.suiviInit();
    nav.suiviSwitch('progression');
    const sels = selZone().querySelectorAll('[data-suivi-sel]');
    const types = Array.from(sels).map(el => el.getAttribute('data-suivi-sel'));
    expect(types).toEqual(['etablissement', 'niveau', 'referentiel']);
  });

  it('EdT hebdo : Établissement seul', () => {
    nav.suiviInit();
    nav.suiviSwitch('edt');
    const types = Array.from(selZone().querySelectorAll('[data-suivi-sel]'))
      .map(el => el.getAttribute('data-suivi-sel'));
    expect(types).toEqual(['etablissement']);
  });

  it('Suivi de classe : Année + Établissement + Niveau + Classe (v0.34.1)', () => {
    nav.suiviInit();
    nav.suiviSwitch('suivi');
    const types = Array.from(selZone().querySelectorAll('[data-suivi-sel]'))
      .map(el => el.getAttribute('data-suivi-sel'));
    expect(types).toEqual(['annee', 'etablissement', 'niveau', 'classe']);
  });

  it('Gestion (Classe) : Année + Établissement + Niveau (v0.35 B1)', () => {
    nav.suiviInit();
    nav.suiviPorteeSwitch('gestion');
    // La portée gestion ouvre l'atelier « classe » par défaut, qui déclare
    // annee + etablissement + niveau (filtres partagés du pool).
    const types = Array.from(selZone().querySelectorAll('[data-suivi-sel]'))
      .map(el => el.getAttribute('data-suivi-sel'));
    expect(types).toEqual(['annee', 'etablissement', 'niveau']);
  });

  it('bascule Progression → Suivi → Progression : pas de fuite de sélecteurs', () => {
    nav.suiviInit();
    nav.suiviSwitch('progression');
    nav.suiviSwitch('suivi');
    nav.suiviSwitch('progression');
    const types = Array.from(selZone().querySelectorAll('[data-suivi-sel]'))
      .map(el => el.getAttribute('data-suivi-sel'));
    expect(types).toEqual(['etablissement', 'niveau', 'referentiel']);
    // Après retour sur Suivi (annee+etab+niveau+classe), le pool a récupéré ses
    // labels sans duplication. 5 labels au total (annee, etab, niveau, ref,
    // classe) ; le Suivi en utilise 4 → 1 seul reste au pool (referentiel).
    nav.suiviSwitch('suivi');
    const restants = document.getElementById('suivi-selecteurs-pool')
      .querySelectorAll('[data-suivi-sel]').length;
    expect(restants).toBe(1);
  });
});

describe('Navigation Suivi — shim sousOnglet (compat)', () => {
  beforeEach(() => { chargerNav(); });

  it("sousOnglet('progression') ouvre Progression", () => {
    nav.suiviInit();
    nav.sousOnglet('progression');
    expect($('stab-progression').style.display).toBe('');
    expect(nav.SUIVI_ATELIER_ACTIF).toBe('progression');
  });

  it("sousOnglet('parametrage') ouvre Gestion > Classe", () => {
    nav.suiviInit();
    nav.sousOnglet('parametrage');
    expect($('stab-parametrage').style.display).toBe('');
    expect(nav.SUIVI_PORTEE_ACTIVE).toBe('gestion');
  });

  it("sousOnglet('suivi') revient sur Suivi de classe", () => {
    nav.suiviInit();
    nav.sousOnglet('progression');
    nav.sousOnglet('suivi');
    expect($('stab-suivi').style.display).toBe('');
    expect(nav.SUIVI_ATELIER_ACTIF).toBe('suivi');
  });
});
