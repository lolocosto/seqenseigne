// tests_js/salles_pur.test.js — v0.37.0
//
// Logique pure de l'éditeur de plan de salle (static/salles_pur.js) :
// géométrie des places, sélection par îlot, rotation d'un îlot autour de son
// centre, aimantation bord à bord, regroupement, sérialisation.

import { describe, it, expect, beforeAll } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
let S;

beforeAll(() => {
  const code = readFileSync(join(__dirname, '..', 'static', 'salles_pur.js'), 'utf-8');
  new Function(code)();
  S = globalThis.window ? globalThis.window.SallesPur : globalThis.SallesPur;
});

const P = (x, y, angle = 0, ilot = '', numero = null) => ({ x, y, angle, ilot, numero });
const proche = (a, b) => expect(Math.abs(a - b)).toBeLessThan(0.11);

describe('géométrie', () => {
  it('coins d\'une place droite : 60×40 centrée', () => {
    const c = S.coins(P(100, 100));
    expect(c[0]).toEqual([70, 80]);
    expect(c[2]).toEqual([130, 120]);
  });
  it('une place tournée de 90° est haute de 60', () => {
    const b = S.boite([P(100, 100, 90)]);
    proche(b.xmax - b.xmin, 40);
    proche(b.ymax - b.ymin, 60);
  });
  it('angles normalisés dans [0, 360)', () => {
    expect(S.norm360(-5)).toBe(355);
    expect(S.norm360(360)).toBe(0);
    expect(S.norm360(725)).toBe(5);
  });
});

describe('sélection', () => {
  const plan = [P(0, 0, 0, 'i1'), P(60, 0, 0, 'i1'), P(200, 0)];
  it('un clic sélectionne l\'îlot entier', () => {
    expect(S.selectionDuClic(plan, 1, false)).toEqual([0, 1]);
  });
  it('Alt+clic sélectionne la place seule', () => {
    expect(S.selectionDuClic(plan, 1, true)).toEqual([1]);
  });
  it('place isolée', () => {
    expect(S.selectionDuClic(plan, 2, false)).toEqual([2]);
  });
});

describe('rotation d\'un îlot', () => {
  it('pivote autour du centre de l\'îlot et conserve les contacts', () => {
    const plan = [P(70, 100, 0, 'i1'), P(130, 100, 0, 'i1')];
    const r = S.tourner(plan, [0, 1], 90);
    proche(r[0].x, 100); proche(r[0].y, 70);
    proche(r[1].x, 100); proche(r[1].y, 130);
    expect(r[0].angle).toBe(90);
    expect(r).not.toBe(plan);                // pas de mutation
    expect(plan[0].x).toBe(70);
  });
  it('ne touche pas aux autres places', () => {
    const plan = [P(0, 0), P(500, 500, 30)];
    expect(S.tourner(plan, [0], 5)[1]).toBe(plan[1]);
  });
});

describe('aimantation', () => {
  it('colle une place parallèle bord à bord (petit côté)', () => {
    const plan = [P(100, 100), P(163, 103)];          // 3 cm de jeu, 3 cm de décalage
    const [dx, dy] = S.aimanter(plan, [1]);
    proche(163 + dx, 160); proche(103 + dy, 100);
  });
  it('colle par le grand côté', () => {
    const plan = [P(100, 100), P(98, 145)];
    const [dx, dy] = S.aimanter(plan, [1]);
    proche(98 + dx, 100); proche(145 + dy, 140);
  });
  it('colle une place perpendiculaire', () => {
    // Fixe horizontale, mobile verticale posée sous son bord bas, côté gauche.
    const plan = [P(100, 100), P(90, 152, 90)];
    const [dx, dy] = S.aimanter(plan, [1]);
    proche(90 + dx, 90); proche(152 + dy, 150);     // 100 + 20 + 30
  });
  it('fonctionne dans le repère d\'une place tournée', () => {
    const q = P(100, 100, 30);
    const [ux, uy] = S.tournerVecteur(62, 0, 30);   // 2 cm trop loin le long de u
    const plan = [q, P(100 + ux, 100 + uy, 30)];
    const [dx, dy] = S.aimanter(plan, [1]);
    const [ex, ey] = S.tournerVecteur(60, 0, 30);
    proche(100 + ux + dx, 100 + ex); proche(100 + uy + dy, 100 + ey);
  });
  it('rien au-delà du seuil ou entre angles quelconques', () => {
    expect(S.aimanter([P(100, 100), P(180, 100)], [1])).toEqual([0, 0]);
    expect(S.aimanter([P(100, 100), P(162, 100, 20)], [1])).toEqual([0, 0]);
  });
  it('un groupe ne s\'aimante pas à lui-même', () => {
    const plan = [P(100, 100, 0, 'i1'), P(161, 100, 0, 'i1')];
    expect(S.aimanter(plan, [0, 1])).toEqual([0, 0]);
  });
});

describe('îlots et modèles', () => {
  it('grouper fusionne les îlots touchés', () => {
    const plan = [P(0, 0, 0, 'i1'), P(60, 0, 0, 'i1'), P(200, 0), P(400, 0)];
    const g = S.grouper(plan, [1, 2]);
    expect(new Set(g.slice(0, 3).map(p => p.ilot)).size).toBe(1);
    expect(g[0].ilot).not.toBe('');
    expect(g[3].ilot).toBe('');
  });
  it('dégrouper isole les places', () => {
    const plan = [P(0, 0, 0, 'i1'), P(60, 0, 0, 'i1')];
    expect(S.degrouper(plan, [0]).map(p => p.ilot)).toEqual(['', 'i1']);
  });
  it('îlot de 4 : places jointives, nouvel identifiant', () => {
    const m = S.modele('ilot4', 200, 200, [P(0, 0, 0, 'i1')]);
    expect(m).toHaveLength(4);
    expect(new Set(m.map(p => p.ilot))).toEqual(new Set(['i2']));
    expect(m.every(p => p.numero === null)).toBe(true);
    proche(m[1].x - m[0].x, 60); proche(m[2].y - m[0].y, 40);
  });
});

describe('sérialisation', () => {
  it('arrondit et garde les numéros existants', () => {
    const s = S.serialiser([{ x: 10.04, y: 20.06, angle: -5, ilot: undefined, numero: 3 },
                            P(1, 2)]);
    expect(s[0]).toEqual({ numero: 3, x: 10, y: 20.1, angle: 355, ilot: '' });
    expect(s[1].numero).toBeNull();
  });
});
