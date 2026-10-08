// tests_js/profils.test.js — v0.51.0
//
// Profils de lancement : profilPermet / profilAffiche (bloc extrait d'app.js).

import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const APP = readFileSync(join(__dirname, '..', 'static', 'app.js'), 'utf-8');

function charger(profil) {
  const debut = APP.indexOf('const SEQ_PROFIL_COURANT');
  const fin = APP.indexOf('window.profilAffiche = profilAffiche;');
  if (debut < 0 || fin < 0) throw new Error('bloc profil introuvable');
  window.SEQ_PROFIL = profil;
  // eslint-disable-next-line no-new-func
  return new Function(APP.slice(debut, fin)
    + 'return { profilPermet, profilAffiche };')();
}

function el(attr) {
  const d = document.createElement('div');
  if (attr !== null) d.setAttribute('data-profils', attr);
  return d;
}

describe('profils (v0.51.0)', () => {
  it('complet par défaut : tout est permis et affiché', () => {
    const f = charger(undefined);
    expect(f.profilPermet('atelier') && f.profilPermet('classe')).toBe(true);
    expect(f.profilAffiche(el('complet'))).toBe(true);
    expect(f.profilAffiche(el('atelier'))).toBe(true);
  });

  it('atelier : seulement le côté atelier', () => {
    const f = charger('atelier');
    expect(f.profilPermet('atelier')).toBe(true);
    expect(f.profilPermet('classe')).toBe(false);
    expect(f.profilAffiche(el('atelier classe'))).toBe(true);
    expect(f.profilAffiche(el('classe'))).toBe(false);
    expect(f.profilAffiche(el('complet'))).toBe(false);
    expect(f.profilAffiche(el(null))).toBe(true);
  });

  it('classe : seulement le côté classe', () => {
    const f = charger('classe');
    expect(f.profilPermet('classe')).toBe(true);
    expect(f.profilPermet('atelier')).toBe(false);
    expect(f.profilAffiche(el('atelier'))).toBe(false);
    expect(f.profilAffiche(el('atelier classe'))).toBe(true);
    expect(f.profilAffiche(null)).toBe(false);
  });
});
