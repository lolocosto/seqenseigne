// tests_js/toolbar_rendu_factorisee.test.js — v0.17.0
//
// Factorisation : la mini-toolbar de la zone de rendu (bouton « Compiler le
// rendu », bouton « LaTeX généré », span statut) est générée par la méthode
// commune AtelierEditeur._assurerToolbarRendu(), au lieu d'être dupliquée en
// HTML statique dans les 6 ateliers. Le bouton « LaTeX généré », auparavant
// dans la toolbar du haut, est désormais à côté de « Compiler le rendu ».

import { describe, it, expect, beforeAll, beforeEach, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

function charger(rel) {
  const code = readFileSync(join(__dirname, '..', 'static', rel), 'utf-8');
  // eslint-disable-next-line no-new-func
  new Function(code)();
}

beforeAll(() => {
  globalThis.window.atelToast = globalThis.window.atelToast || (() => {});
  charger('atelier.js');
  charger('atelier_editeur.js');
});

function nouvelAtelier(prefixe = 'atl-test') {
  // Instance minimale d'AtelierEditeur (config réduite).
  const A = new globalThis.window.AtelierEditeur({
    id: 'test', prefixe, endpointBase: '/api/tests',
  });
  // majToolbar peut être appelée par _assurerToolbarRendu ; on la neutralise
  // pour isoler le test de génération (sauf test dédié).
  return A;
}

describe('_assurerToolbarRendu (factorisation v0.17.0)', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  it('génère Compiler + LaTeX généré + statut dans le conteneur', () => {
    document.body.innerHTML = '<div id="atl-test-rendu-toolbar"></div>';
    const A = nouvelAtelier();
    A._assurerToolbarRendu();
    const c = document.getElementById('atl-test-rendu-toolbar');
    const btnCompiler = document.getElementById('atl-test-btn-compiler');
    const btnLatex = document.getElementById('atl-test-btn-latex');
    const status = document.getElementById('atl-test-rendu-status');
    expect(btnCompiler).toBeTruthy();
    expect(btnCompiler.textContent).toContain('Compiler le rendu');
    expect(btnLatex).toBeTruthy();
    expect(btnLatex.textContent).toContain('LaTeX généré');
    expect(status).toBeTruthy();
    // Tous dans le conteneur.
    expect(c.contains(btnCompiler)).toBe(true);
    expect(c.contains(btnLatex)).toBe(true);
  });

  it('le bouton LaTeX est masqué par défaut (piloté ensuite par majToolbar)', () => {
    document.body.innerHTML = '<div id="atl-test-rendu-toolbar"></div>';
    const A = nouvelAtelier();
    A._assurerToolbarRendu();
    expect(document.getElementById('atl-test-btn-latex').style.display).toBe('none');
  });

  it('est idempotent : deux appels ne dupliquent pas les boutons', () => {
    document.body.innerHTML = '<div id="atl-test-rendu-toolbar"></div>';
    const A = nouvelAtelier();
    A._assurerToolbarRendu();
    A._assurerToolbarRendu();
    const compilers = document.querySelectorAll('#atl-test-rendu-toolbar [id$="-btn-compiler"]');
    expect(compilers.length).toBe(1);
  });

  it('no-op si le conteneur est absent (rétrocompatibilité)', () => {
    document.body.innerHTML = '';  // pas de conteneur
    const A = nouvelAtelier();
    expect(() => A._assurerToolbarRendu()).not.toThrow();
    expect(document.getElementById('atl-test-btn-compiler')).toBeNull();
  });

  it('le bouton Compiler câble compilerRendu (addEventListener, pas onclick)', () => {
    document.body.innerHTML = '<div id="atl-test-rendu-toolbar"></div>';
    const A = nouvelAtelier();
    const spy = vi.spyOn(A, 'compilerRendu').mockImplementation(() => {});
    A._assurerToolbarRendu();
    document.getElementById('atl-test-btn-compiler').click();
    expect(spy).toHaveBeenCalled();
    spy.mockRestore();
  });

  it('le bouton LaTeX câble voirLatex', () => {
    document.body.innerHTML = '<div id="atl-test-rendu-toolbar"></div>';
    const A = nouvelAtelier();
    const spy = vi.spyOn(A, 'voirLatex').mockImplementation(() => {});
    A._assurerToolbarRendu();
    document.getElementById('atl-test-btn-latex').click();
    expect(spy).toHaveBeenCalled();
    spy.mockRestore();
  });
});
