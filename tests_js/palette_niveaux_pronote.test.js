// tests_js/palette_niveaux_pronote.test.js — v0.36.2
//
// Pourquoi : en v0.36.1, le fond des cellules du tableau de suivi était dérivé
// du champ sémantique NIV_REF.couleur (« bleu » pour Très bien) via une palette
// CSS séparée, d'où un Très bien bleu alors que tout le reste de l'appli le
// montre en vert foncé. Invariant posé : UNE SEULE palette de niveaux
// (variables --niv-<code>-* du §20 de app.css), alignée sur les teintes Pronote,
// et des cellules indexées par CODE de niveau.

import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const CSS = readFileSync(join(__dirname, '..', 'static', 'app.css'), 'utf-8');
const APP = readFileSync(join(__dirname, '..', 'static', 'app.js'), 'utf-8');

function varCss(nom) {
  const m = CSS.match(new RegExp(`${nom}:\\s*(#[0-9a-fA-F]{6})`));
  return m ? m[1].toLowerCase() : null;
}

describe('Palette des niveaux — source unique alignée sur Pronote (v0.36.2)', () => {
  it('les badges reprennent les teintes Pronote pleines (cohérence avec l\'ENT)', () => {
    expect(varCss('--niv-1-bg')).toBe('#f80a0a');
    expect(varCss('--niv-2-bg')).toBe('#ffda01');
    expect(varCss('--niv-3-bg')).toBe('#45b851');
    expect(varCss('--niv-4-bg')).toBe('#008000');
    expect(varCss('--niv-A-text')).toBe('#009ee1');
    expect(varCss('--niv-D-text')).toBe('#009ee1');
  });

  it('Très bien reste un VERT en cellule, jamais un bleu (régression v0.36.1)', () => {
    const cell = varCss('--niv-4-cell');
    expect(cell).not.toBeNull();
    const [r, g, b] = [1, 3, 5].map(i => parseInt(cell.slice(i, i + 2), 16));
    expect(g).toBeGreaterThan(r);
    expect(g).toBeGreaterThan(b);
  });

  it('les fonds de cellule passent par les variables, pas par des couleurs en dur', () => {
    for (const c of ['1', '2', '3', '4']) {
      expect(CSS).toMatch(new RegExp(`\\.td-niv\\.niv-${c}\\s*\\{[^}]*var\\(--niv-${c}-cell\\)`));
    }
  });

  it('l\'ancienne palette de cellules par nom de couleur a disparu', () => {
    expect(CSS).not.toMatch(/\.td-niv\.niv-(rouge|orange|vert|bleu|gris|neutre|blanc)\b/);
  });

  it('les anciennes variables --niv-TB/S/F/I ne sont plus ni définies ni utilisées', () => {
    expect(CSS).not.toMatch(/--niv-(TB|S|F|I)-(bg|text)/);
  });

  it('renderClasseView indexe la cellule par code de niveau, pas par NIV_REF.couleur', () => {
    expect(APP).toMatch(/class="td-niv niv-\$\{niv\|\|'0'\}"/);
    expect(APP).not.toMatch(/NIV_REF\?\.\[niv\]\?\.couleur/);
  });

  it('le select de cellule est transparent pour laisser voir le fond du niveau', () => {
    const m = CSS.match(/\.td-niv select\s*\{([^}]*)\}/g) || [];
    expect(m.length).toBeGreaterThan(0);
    for (const r of m) expect(r).not.toMatch(/background:\s*var\(--surface\)/);
  });
});
