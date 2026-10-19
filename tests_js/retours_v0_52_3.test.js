// tests_js/retours_v0_52_3.test.js — v0.52.3
//
// Retours de Laurent sur la v0.52.2 :
//   1. activité d'approche : le bouton de série « Activité d'approche » doit
//      être sélectionné à l'ouverture (id atl-serie-approche, cherché par
//      changerSerie) ; un code 'EA' écrit avant v0.52.3 reste rangé en
//      Approche, pas en Exploration ;
//   2. module Évaluations : l'onglet « Rendu PDF » suit l'évaluation
//      sélectionnée (il gardait le dernier PDF compilé) ; l'information de
//      cache porte les mêmes paramètres (sujet, version) que la compilation.

import { describe, it, expect, beforeAll } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const lire = (...p) => readFileSync(join(__dirname, '..', ...p), 'utf-8');
const EXO = lire('static', 'atelier_exercice.js');
const EVAL = lire('static', 'atelier_evaluation_oo.js');
const EDIT = lire('static', 'atelier_editeur.js');
const APP = lire('static', 'app.js');
const HTML = lire('templates', 'index.html');

describe('1. série approche dans l\'atelier d\'exercices', () => {
  it('le bouton a l\'id que changerSerie cherche, sinon aucune série n\'est sélectionnée', () => {
    expect(HTML).toMatch(/id="atl-serie-approche"[^>]*changerSerie\('approche'\)/);
    expect(HTML).not.toMatch(/atl-serie-AP\b/);
    expect(EXO).toMatch(/\['fondamental', 'avancé', 'exploration', 'approche'\]\.forEach/);
    expect(EXO).toMatch(/getElementById\('atl-serie-' \+ k\)/);
  });

  it('changerSerie(\'approche\') sélectionne le bouton (DOM)', () => {
    document.body.innerHTML = ['fondamental', 'avancé', 'exploration', 'approche']
      .map(k => `<button id="atl-serie-${k}" class="serie-btn"></button>`).join('');
    const m = EXO.match(/ {2}changerSerie\(s, marquerDirty = true\) \{[\s\S]*?\n {2}\}/);
    const corps = m[0].replace(/^ {2}changerSerie\(s, marquerDirty = true\) \{/, '')
      .replace(/\}$/, '');
    const fn = new Function('s', 'marquerDirty', 'AtelierExercice', corps);
    const self = { majSeriesDocuments() {}, majVisibiliteRemediation() {},
                   majSelecteursRendu6e() {}, itemActif: null };
    fn.call(self, 'approche', false, { SERIE_DOCUMENT: {} });
    expect(document.getElementById('atl-serie-approche').className)
      .toBe('serie-btn active-approche');
    expect(document.getElementById('atl-serie-fondamental').className).toBe('serie-btn');
  });

  it('un code EA (écrit avant v0.52.3) est rangé en Approche, pas en Exploration', () => {
    const m = EXO.match(/AtelierExercice\.prefixeSerie = function[\s\S]*?\n\};/);
    const prefixeSerie = new Function(m[0].replace('AtelierExercice.prefixeSerie =', 'return')
      + '\n')();
    expect(prefixeSerie('EA01')).toBe('AE');
    expect(prefixeSerie('AE03')).toBe('AE');
    expect(prefixeSerie('E02')).toBe('E');
    expect(prefixeSerie('EV01')).toBe('EV');
  });

  it('le code legacy d\'app.js utilise aussi AE', () => {
    expect(APP).toMatch(/'approche': 'AE'/);
    expect(APP).not.toMatch(/'approche': 'EA'/);
  });
});

describe('2. Rendu PDF du module Évaluations', () => {
  let synchroniser;
  beforeAll(() => {
    const m = EVAL.match(/ {2}_synchroniserRendu\(\) \{[\s\S]*?\n {2}\}/);
    if (!m) throw new Error('_synchroniserRendu introuvable');
    synchroniser = new Function(m[0].replace(/^ {2}_synchroniserRendu\(\) \{/, '')
      .replace(/\}$/, ''));
  });

  function faux(tab) {
    const appels = [];
    return {
      appels, tabCourant: tab, _genRendu: 3, itemActif: { id: 'E1' },
      _remettrePlaceholderRendu() { appels.push('placeholder'); },
      _majSelecteursRendu6e() { appels.push('selecteurs'); },
      verifierCacheEtAfficher() { appels.push('verifier'); },
    };
  }

  it('changer d\'évaluation remet la zone à zéro et recharge le PDF si l\'onglet est ouvert', () => {
    const a = faux('rendu');
    synchroniser.call(a);
    expect(a.appels).toEqual(['placeholder', 'selecteurs', 'verifier']);
    expect(a._genRendu).toBe(4);                 // une compilation en vol est invalidée
    a.appels.length = 0;
    synchroniser.call(a);                        // même évaluation : rien
    expect(a.appels).toEqual([]);
    a.itemActif = { id: 'E2' };
    synchroniser.call(a);
    expect(a.appels).toEqual(['placeholder', 'selecteurs', 'verifier']);
  });

  it('onglet Édition : la zone est remise à zéro sans compiler', () => {
    const a = faux('edition');
    synchroniser.call(a);
    expect(a.appels).toEqual(['placeholder', 'selecteurs']);
  });

  it('branché sur la vue complète (sélection, création, suppression) et sur l\'onglet', () => {
    const vue = EVAL.match(/ {2}_rendreVueComplete\(\) \{[\s\S]*?\n {2}\}/)[0];
    expect((vue.match(/this\._synchroniserRendu\(\)/g) || []).length).toBe(2);
    const onglet = EVAL.match(/ {2}basculerOnglet\(nom\) \{[\s\S]*?\n {2}\}/)[0];
    expect(onglet).toMatch(/this\.verifierCacheEtAfficher\(\)/);
    expect(EVAL).toMatch(/sel\.addEventListener\('change', \(\) => this\.verifierCacheEtAfficher\(\)\)/);
  });

  it('l\'information de cache porte les paramètres du rendu (sujet, version)', () => {
    expect(EDIT).toMatch(/rendu-pdf\/info`\s*\n[^\n]*\n[^\n]*\n\s*\+ this\.parametresRendu\(\)/);
  });
});
