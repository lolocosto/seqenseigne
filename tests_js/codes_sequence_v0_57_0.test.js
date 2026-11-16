// tests_js/codes_sequence_v0_57_0.test.js — v0.57.0 (L1, codes de thème A1)
//
// Interface tolérante aux codes de thème (plan de migration, livraison 1) :
//  - atelier_referentiel.js : un code A1 (numéro 11) s'affiche « A1 », jamais
//    « S11 » ; les anciens codes s'affichent comme avant ;
//  - app.js : les listes « séquence » de la compilation par lot et de la
//    recherche sont lues en base (cycles C03 et C04), plus de S01…S14 en dur ;
//    ordre inchangé sans code de thème, anciens codes avant les codes de thème.

import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const APP = readFileSync(join(__dirname, '..', 'static', 'app.js'), 'utf-8');
const REF = readFileSync(join(__dirname, '..', 'static', 'atelier_referentiel.js'), 'utf-8');

function extraireFonction(src, nom) {
  const re = new RegExp('(async\\s+)?function\\s+' + nom + '\\s*\\(');
  const m = re.exec(src);
  if (!m) throw new Error('fonction introuvable : ' + nom);
  const i = src.indexOf('{', m.index);
  let prof = 0;
  for (let j = i; j < src.length; j++) {
    if (src[j] === '{') prof++;
    else if (src[j] === '}') {
      prof--;
      if (prof === 0) return src.slice(m.index, j + 1);
    }
  }
  throw new Error('accolade de fin introuvable pour : ' + nom);
}

describe('atelRefCodeSequence — code affiché d’une séquence', () => {
  const f = new Function(extraireFonction(REF, 'atelRefCodeSequence')
                         + '\nreturn atelRefCodeSequence;')();

  it('un code de thème A1 (numéro 11) s’affiche A1, jamais S11', () => {
    expect(f({ code: 'A1', numero: 11 })).toBe('A1');
    expect(f({ sequence_code: 'E1', numero: 51 })).toBe('E1');
  });

  it('anciens codes, mises en route et archives : comme avant', () => {
    expect(f({ code: 'S03', numero: 3 })).toBe('S03');
    expect(f({ code: 'M02', numero: 202 })).toBe('M02');
    expect(f({ code: 'X10', numero: 110 })).toBe('X10');
  });
});

describe('listes de séquences lues en base (compilation par lot, recherche)', () => {
  const sansCommentaires = APP.split('\n').filter(l => !l.trimStart().startsWith('//')).join('\n');

  it('plus de boucle S01…S14 en dur dans compilBatchInit ni rechercheInit', () => {
    for (const nom of ['compilBatchInit', 'rechercheInit']) {
      const src = extraireFonction(sansCommentaires, nom);
      expect(src).not.toMatch(/'S'\s*\+/);
      expect(src).toMatch(/atelCodesSequencesPrincipales\(\)/);
    }
  });

  it('union C03 + C04 sans Mnn ni Xnn, anciens codes avant codes de thème', async () => {
    const parCycle = {
      C03: ['S01', 'S02', 'S13', 'X01', 'M01'],
      C04: ['S01', 'S14', 'B1', 'A1'],
    };
    const bundle = new Function('parCycle',
      'async function atelChargerSequencesPourCycle(c) { return parCycle[c]; }\n'
      + extraireFonction(APP, 'atelCleTriCodeSequence') + '\n'
      + extraireFonction(APP, 'atelComparerCodesSequence') + '\n'
      + extraireFonction(APP, 'atelCodesSequencesPrincipales') + '\n'
      + 'return atelCodesSequencesPrincipales;');
    const liste = await bundle(parCycle)();
    expect(liste).toEqual(['S01', 'S02', 'S13', 'S14', 'A1', 'B1']);
  });

  it('base actuelle (S01…S13 en 6e, S01…S14 au cycle 4) : même liste qu’avant', async () => {
    const s = n => Array.from({ length: n }, (_, i) => 'S' + String(i + 1).padStart(2, '0'));
    const parCycle = { C03: [...s(13), 'X01', 'M01'], C04: s(14) };
    const bundle = new Function('parCycle',
      'async function atelChargerSequencesPourCycle(c) { return parCycle[c]; }\n'
      + extraireFonction(APP, 'atelCleTriCodeSequence') + '\n'
      + extraireFonction(APP, 'atelComparerCodesSequence') + '\n'
      + extraireFonction(APP, 'atelCodesSequencesPrincipales') + '\n'
      + 'return atelCodesSequencesPrincipales;');
    expect(await bundle(parCycle)()).toEqual(s(14));
  });
});
