// tests_js/impression_cadre.test.js — v0.50.0
//
// Documents imprimables HTML (sans LaTeX) affichés dans un cadre de l'appli :
// on extrait d'app.js le bloc `imprimerCadre` / `afficherImpression` et on
// vérifie le câblage des contrôles (cadre, impression, onglet, ancien PDF).

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const APP = readFileSync(join(__dirname, '..', 'static', 'app.js'), 'utf-8');

function extraireBloc(src) {
  const debut = src.indexOf('function imprimerCadre(');
  const fin = src.indexOf('window.afficherImpression = afficherImpression;');
  if (debut < 0 || fin < 0) throw new Error('bloc impression introuvable');
  return src.slice(debut, fin) + 'window.afficherImpression = afficherImpression;';
}

beforeEach(() => {
  document.body.innerHTML = `
    <button id="x-print" style="display:none"></button>
    <a id="x-dl" style="display:none"></a>
    <a id="x-ancien" style="display:none"></a>
    <div id="x-zone"></div>`;
  globalThis.escapeHtml = (s) => String(s).replace(/</g, '&lt;');
  // eslint-disable-next-line no-new-func
  new Function(extraireBloc(APP))();
});

describe('afficherImpression (v0.50.0)', () => {
  it('pose un cadre sur la page HTML et branche les contrôles', () => {
    const f = window.afficherImpression(document.getElementById('x-zone'),
      'x-frame', 'Planning <4A>', '/impression/a?annee=1',
      { dlId: 'x-dl', printId: 'x-print', ancienId: 'x-ancien',
        ancienUrl: '/api/a.pdf?annee=1' });
    expect(f.id).toBe('x-frame');
    expect(f.getAttribute('src')).toBe('/impression/a?annee=1');
    expect(f.getAttribute('title')).toBe('Planning <4A>');
    expect(document.getElementById('x-dl').getAttribute('href')).toBe('/impression/a?annee=1');
    expect(document.getElementById('x-dl').style.display).toBe('');
    expect(document.getElementById('x-print').style.display).toBe('');
    expect(document.getElementById('x-ancien').getAttribute('href')).toBe('/api/a.pdf?annee=1');
  });

  it('cache le lien vers l’ancien PDF quand il n’y en a pas', () => {
    document.getElementById('x-ancien').style.display = '';
    window.afficherImpression(document.getElementById('x-zone'), 'x-frame',
      't', '/impression/b', { ancienId: 'x-ancien' });
    expect(document.getElementById('x-ancien').style.display).toBe('none');
  });

  it('le bouton imprime le seul contenu du cadre', () => {
    const f = window.afficherImpression(document.getElementById('x-zone'),
      'x-frame', 't', '/impression/c', { printId: 'x-print' });
    const print = vi.spyOn(f.contentWindow, 'print').mockImplementation(() => {});
    document.getElementById('x-print').click();
    expect(print).toHaveBeenCalledTimes(1);
    print.mockRestore();
  });

  it('repli : ouvre dans un onglet si l’impression du cadre échoue', () => {
    const f = window.afficherImpression(document.getElementById('x-zone'),
      'x-frame', 't', '/impression/d', { printId: 'x-print' });
    const print = vi.spyOn(f.contentWindow, 'print')
      .mockImplementation(() => { throw new Error('bloqué'); });
    const open = vi.spyOn(window, 'open').mockImplementation(() => null);
    document.getElementById('x-print').click();
    expect(open).toHaveBeenCalledWith(f.src, '_blank');
    open.mockRestore();
    print.mockRestore();
  });
});
