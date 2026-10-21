// tests_js/mises_en_route_6e.test.js — v0.53.0
//
// Mises en route de 6e (séquences Mnn) et anomalie du rendu par lot :
//   - B1 : le filtre « Séquence » du rendu par lot propose M01 à M07 ;
//   - MR2 : série MR (exercice de séance) reconnue par l'atelier d'exercices
//     (préfixe à deux lettres, bucket, série documents) ;
//   - MR1b : dans une séquence Mnn, aucun objectif n'est l'objectif « Cours »
//     (M01-01 a le code 01, qui serait le Cours de la partie 1 ailleurs) ;
//   - MR5 : l'onglet Rendu PDF d'une séquence Mnn envoie les options du
//     document de mise en route (options.mer) au lieu de celles du livret.

import { describe, it, expect, beforeAll } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const lire = rel => readFileSync(join(__dirname, '..', rel), 'utf-8');
const EXO = lire('static/atelier_exercice.js');
const APP = lire('static/app.js');

function charger(rel) {
  // eslint-disable-next-line no-new-func
  new Function(lire(join('static', rel)))();
}

describe('B1 : rendu par lot, séquences de mise en route', () => {
  it('le filtre Séquence propose M01 à M07 en plus de S01 à S14', () => {
    expect(APP).toMatch(/for \(let i = 1; i <= 7; i\+\+\) \{\s*const code = 'M' \+ String\(i\)\.padStart\(2, '0'\);/);
  });
});

describe('MR2 : série MR dans l\'atelier d\'exercices', () => {
  it('MR01 est reconnu comme série MR (pas « Autres »)', () => {
    const m = EXO.match(/AtelierExercice\.prefixeSerie = function[\s\S]*?\n\};/);
    const prefixeSerie = new Function(m[0].replace('AtelierExercice.prefixeSerie =', 'return') + '\n')();
    expect(prefixeSerie('MR01')).toBe('MR');
    expect(prefixeSerie('M01')).toBe('');
    expect(prefixeSerie('AT02')).toBe('AT');
  });
  it('MR est une série « documents » (bucket, libellé, correspondance)', () => {
    expect(EXO).toMatch(/MR: 'mise en route',\s*\/\/ v0\.53\.0/);
    expect(EXO).toMatch(/'mise en route':\s*'MR'/);
    expect(EXO).toMatch(/MR:\s*\{ label: 'Exercices de séance \(MR\)'/);
    expect(EXO).toMatch(/AT: \[\],\s*\n\s*MR: \[\], Autres: \[\]/);
  });
});

describe('MR1b et MR5 : assemblage d\'une séquence de mise en route', () => {
  let A;
  beforeAll(() => {
    globalThis.window.atelGardeEnregistrer = globalThis.window.atelGardeEnregistrer || (() => {});
    charger('atelier.js');
    charger('atelier_editeur.js');
    charger('atelier_assemblage.js');
    charger('seqniv_pur.js');
    charger('atelier_seqniv_assemblage.js');
    A = globalThis.window.ATELIER_SEQNIV;
  });
  const avecSequence = code => { A.data = { sequence_par_niveau: { niveau: 'N09', sequence_code: code } }; };

  it('S01 : le Cours de la partie n garde le code (n-1)1', () => {
    avecSequence('S01');
    expect(A._codeConnaitre(1)).toBe('01');
    expect(A._codeConnaitre(3)).toBe('21');
    expect(A._estMer()).toBe(false);
  });
  it('M01 : pas d\'objectif Cours (M01-01 est un objectif comme les autres)', () => {
    avecSequence('M01');
    expect(A._codeConnaitre(1)).toBe('');
    expect(A._estMer()).toBe(true);
  });
  it('M01 : les options envoyées sont celles du document de mise en route', () => {
    avecSequence('M01');
    const o = A._livretSeqOptions();
    expect(Object.keys(o)).toEqual(['mer']);
    expect(o.mer).toMatchObject({ document: 'planche', version: 'eleve', par_page: '4',
                                  exemplaires: '1', test: '1', sujet: 'A' });
  });
  it('S01 : options du livret inchangées (pas de clé mer)', () => {
    avecSequence('S01');
    const o = A._livretSeqOptions();
    expect(o.mer).toBeUndefined();
    expect(o.cours).toBeTruthy();
  });
});
