// tests_js/v0_60_0_rituels_type_evaluation.test.js — v0.60.0
//
// Interface de la version 2 du modèle Fiches :
//   - T1/T2 : type (évaluation / test court) et durée de l'évaluation relus et
//     envoyés à l'enregistrement (sinon perdus), rappel de la durée
//     automatique ; masqués hors modèle Fiches, comme la calculatrice ;
//   - P0 : (v0.60.2) cadre « Rituels d'automatismes » retiré de l'atelier
//     Référentiel — voir v0_60_2_rituels_hors_atelier.test.js.

import { describe, it, expect, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const EVAL = readFileSync(join(__dirname, '..', 'static', 'atelier_evaluation_oo.js'), 'utf-8');
const REF = readFileSync(join(__dirname, '..', 'static', 'atelier_referentiel.js'), 'utf-8');
const HTML = readFileSync(join(__dirname, '..', 'templates', 'index.html'), 'utf-8');

function methode(nom, arg) {
  const m = EVAL.match(new RegExp(`\\n  ${nom}\\(${arg}\\) \\{[\\s\\S]*?\\n  \\}\\n`));
  if (!m) throw new Error(`${nom} introuvable`);
  const corps = m[0].trim().replace(new RegExp(`^${nom}\\(${arg}\\) \\{`), '').replace(/\}$/, '');
  return new Function(arg || '_', corps);
}

describe('type et durée de l\'évaluation (T1, T2)', () => {
  beforeEach(() => {
    const m = HTML.match(/<div id="atl-eval-type-bloc"[\s\S]*?\n {12}<\/div>/);
    document.body.innerHTML = `<div id="atl-eval-calculatrice-bloc"></div>
      <select id="atl-eval-calculatrice"><option value=""></option></select>
      <div id="atl-eval-calculatrice-avert"></div>${m[0]}
      <input id="atl-eval-titre"><select id="atl-eval-mode"><option value="note"></option></select>
      <input type="checkbox" id="atl-eval-afficher-bareme"><input id="atl-eval-langue-points">`;
  });

  it('modèle Fiches : type relu, durée automatique rappelée, valeurs renvoyées', () => {
    const remplir = methode('_remplirCalculatrice', 'ev');
    const ev = { type_evaluation: 'test_court', duree: null, duree_auto: 10 };
    remplir.call({ _estEval6e: () => true }, ev);
    expect(document.getElementById('atl-eval-type-bloc').style.display).toBe('flex');
    expect(document.getElementById('atl-eval-type').value).toBe('test_court');
    expect(document.getElementById('atl-eval-duree').placeholder).toBe('10');
    expect(document.getElementById('atl-eval-duree-indic').textContent).toContain('10 min');
    document.getElementById('atl-eval-duree').value = '25';
    const collecter = methode('collecterFormulaire', '');
    const champs = collecter.call({ itemActif: ev, _estEval6e: () => true });
    expect(champs.type_evaluation).toBe('test_court');
    expect(champs.duree).toBe('25');
  });

  it('cycle 4 (modèle Notions et méthodes) : masqué et non envoyé', () => {
    const remplir = methode('_remplirCalculatrice', 'ev');
    remplir.call({ _estEval6e: () => false }, { type_evaluation: 'evaluation' });
    expect(document.getElementById('atl-eval-type-bloc').style.display).toBe('none');
    const champs = methode('collecterFormulaire', '').call(
      { itemActif: {}, _estEval6e: () => false });
    expect('type_evaluation' in champs).toBe(false);
    expect('duree' in champs).toBe(false);
  });
});

// v0.60.2 — le cadre « Rituels d'automatismes » (P0) a quitté l'atelier
// Référentiel (il relève des progressions, côté suivi de classe) : ses tests
// d'interface sont remplacés par tests_js/v0_60_2_rituels_hors_atelier.test.js.

describe('niveau de création d\'une carte (F3, coordinateur du 18 novembre)', () => {
  const CARTE = readFileSync(join(__dirname, '..', 'static', 'atelier_carte_automatisme.js'), 'utf-8');

  it('champ exempt du verrou de lecture seule (corrigeable sur une carte validée)', () => {
    expect(HTML).toMatch(/<select id="atl-carte-niveau_creation" data-verrou-exempt/);
  });

  it('enregistré tout de suite par un PUT dédié, valeur relue', async () => {
    const m = CARTE.match(/\n  async changerNiveauCreation\(valeur\) \{[\s\S]*?\n  \}\n/);
    const corps = m[0].trim().replace(/^async changerNiveauCreation\(valeur\) \{/, '').replace(/\}$/, '');
    const AsyncFunction = Object.getPrototypeOf(async () => {}).constructor;
    const f = new AsyncFunction('valeur', 'fetch', corps);
    const appels = [];
    const fauxFetch = async (url, o) => { appels.push([url, o]);
      return { ok: true, json: async () => ({ niveau_creation: 'N10' }) }; };
    const ctx = { itemActif: { id: 'ca_1', niveau_creation: 'N11' }, toast: () => {}, $: () => null };
    await f.call(ctx, 'N10', fauxFetch);
    expect(appels[0][0]).toBe('/api/cartes/ca_1/niveau-creation');
    expect(appels[0][1].method).toBe('PUT');
    expect(JSON.parse(appels[0][1].body)).toEqual({ niveau_creation: 'N10' });
    expect(ctx.itemActif.niveau_creation).toBe('N10');
  });
});
