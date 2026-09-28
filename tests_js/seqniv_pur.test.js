// tests_js/seqniv_pur.test.js — v0.16.6
//
// Tests de la logique PURE du seqniv (Groupe A du cadrage : placements,
// calculs, recherche, formatage). Le module static/seqniv_pur.js est un script
// classique qui s'expose sur window.SeqnivPur ; on le charge en évaluant son
// code dans le contexte jsdom, puis on lit window.SeqnivPur.

import { describe, it, expect, beforeAll } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

let P; // window.SeqnivPur

beforeAll(() => {
  const code = readFileSync(
    join(__dirname, '..', 'static', 'seqniv_pur.js'), 'utf-8');
  // Exécute le script dans le contexte global (jsdom fournit window).
  // eslint-disable-next-line no-new-func
  new Function(code)();
  P = globalThis.window ? globalThis.window.SeqnivPur : globalThis.SeqnivPur;
});

// Jeu de données représentatif d'une séquence avec 2 parties.
function dataFixture() {
  return {
    parties: [
      {
        id: 'p1', numero: 1, nb_seances_R_AE: 2,
        exos_revision_approche: {
          R:  [{ exercice_id: 'exR1' }],
          EA: [{ exercice_id: 'exEA1' }],
        },
        objectifs: [
          {
            id: 'o1', code: 'N11-1', nb_seances: 3, methode_id: 'm1',
            notions: [{ id: 'n1' }, { id: 'n2' }],
            exos_par_serie: {
              F: [{ exercice_id: 'exF1' }],
              A: [{ exercice_id: 'exA1' }, { exercice_id: 'exF1' }],
              E: [],
            },
          },
          {
            id: 'o2', code: 'N11-2', nb_seances: 1.5, methode_id: null,
            notions: [{ id: 'n1' }],
            exos_par_serie: { F: [], A: [], E: [{ exercice_id: 'exE2' }] },
          },
        ],
      },
      {
        id: 'p2', numero: 2, nb_seances_R_AE: 0,
        exos_revision_approche: { R: [], EA: [] },
        objectifs: [],
      },
    ],
  };
}

describe('SeqnivPur — chargement', () => {
  it('expose toutes les fonctions attendues', () => {
    for (const fn of [
      'esc', 'escAttr', 'placementsExos', 'placementsExosRA',
      'placementsNotions', 'placementsMethodes', 'calculerTotalSeancesPartie',
      'indexObjDansPartie', 'trouverObj', 'trouverPartie',
      'trouverPartiePourObj', 'trouverPartieDeObj', 'fmtSeances',
      'fmtSeancesAffichage', 'couleurTheme',
    ]) {
      expect(typeof P[fn]).toBe('function');
    }
  });
});

describe('esc / escAttr', () => {
  it('échappe les caractères HTML', () => {
    expect(P.esc('<a>&"\'')).toBe('&lt;a&gt;&amp;&quot;&#39;');
  });
  it('gère null/undefined', () => {
    expect(P.esc(null)).toBe('');
    expect(P.esc(undefined)).toBe('');
  });
});

describe('placementsExos', () => {
  it('mappe chaque exo vers les codes objectifs (toutes séries)', () => {
    const m = P.placementsExos(dataFixture());
    expect(m.get('exF1')).toEqual(['N11-1', 'N11-1']); // F et A du même obj
    expect(m.get('exA1')).toEqual(['N11-1']);
    expect(m.get('exE2')).toEqual(['N11-2']);
  });
  it('renvoie une Map vide si pas de parties', () => {
    expect(P.placementsExos({}).size).toBe(0);
    expect(P.placementsExos(null).size).toBe(0);
  });
});

describe('placementsExosRA', () => {
  it('mappe les exos R/EA au niveau partie', () => {
    const m = P.placementsExosRA(dataFixture());
    expect(m.get('exR1')).toBe('P1 R');
    expect(m.get('exEA1')).toBe('P1 EA');
  });
});

describe('placementsNotions', () => {
  it('mappe chaque notion vers ses objectifs', () => {
    const m = P.placementsNotions(dataFixture());
    expect(m.get('n1')).toEqual(['N11-1', 'N11-2']);
    expect(m.get('n2')).toEqual(['N11-1']);
  });
});

describe('placementsMethodes', () => {
  it('mappe la méthode vers P{N}/{code}, ignore methode_id null', () => {
    const m = P.placementsMethodes(dataFixture());
    expect(m.get('m1')).toBe('P1/N11-1');
    expect(m.has(null)).toBe(false);
  });
});

describe('calculerTotalSeancesPartie', () => {
  it('somme R+AE + séances des objectifs', () => {
    const d = dataFixture();
    expect(P.calculerTotalSeancesPartie(d.parties[0])).toBe(2 + 3 + 1.5);
    expect(P.calculerTotalSeancesPartie(d.parties[1])).toBe(0);
  });
});

describe('indexObjDansPartie', () => {
  it('retourne l\'index ou -1', () => {
    const d = dataFixture();
    expect(P.indexObjDansPartie(d.parties[0], 'o2')).toBe(1);
    expect(P.indexObjDansPartie(d.parties[0], 'inconnu')).toBe(-1);
  });
});

describe('recherche dans l\'arbre', () => {
  it('trouverObj', () => {
    const d = dataFixture();
    expect(P.trouverObj(d, 'o2').code).toBe('N11-2');
    expect(P.trouverObj(d, 'x')).toBeNull();
  });
  it('trouverPartie', () => {
    const d = dataFixture();
    expect(P.trouverPartie(d, 'p2').numero).toBe(2);
    expect(P.trouverPartie(d, 'x')).toBeNull();
  });
  it('trouverPartiePourObj retourne la partie', () => {
    const d = dataFixture();
    expect(P.trouverPartiePourObj(d, 'o1').id).toBe('p1');
    expect(P.trouverPartiePourObj(d, 'x')).toBeNull();
  });
  it('trouverPartieDeObj retourne l\'id de partie', () => {
    const d = dataFixture();
    expect(P.trouverPartieDeObj(d, 'o2')).toBe('p1');
    expect(P.trouverPartieDeObj(d, 'x')).toBeNull();
  });
});

describe('fmtSeances (valeur input)', () => {
  it('0/null/undefined → chaîne vide', () => {
    expect(P.fmtSeances(0)).toBe('');
    expect(P.fmtSeances(null)).toBe('');
    expect(P.fmtSeances(undefined)).toBe('');
  });
  it('entier et décimal (point)', () => {
    expect(P.fmtSeances(2)).toBe('2');
    expect(P.fmtSeances(1.5)).toBe('1.5');
  });
});

describe('fmtSeancesAffichage (texte)', () => {
  it('null → "0", décimal avec virgule', () => {
    expect(P.fmtSeancesAffichage(null)).toBe('0');
    expect(P.fmtSeancesAffichage(3)).toBe('3');
    expect(P.fmtSeancesAffichage(1.5)).toBe('1,5');
  });
});

describe('couleurTheme', () => {
  it('mappe les thèmes connus, défaut sinon', () => {
    expect(P.couleurTheme('nombres')).toBe('#1d5fa8');
    expect(P.couleurTheme('inconnu')).toBe('#475569');
  });
});
