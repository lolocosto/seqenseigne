// tests_js/smoke.test.js — Vérifie que l'infra Vitest fonctionne.
// (v0.16.6, étape 1 : mise en place du filet JS.)
import { describe, it, expect } from 'vitest';

describe('infra Vitest', () => {
  it('exécute un test trivial', () => {
    expect(1 + 1).toBe(2);
  });

  it('a accès au DOM (jsdom)', () => {
    const div = document.createElement('div');
    div.textContent = 'ok';
    expect(div.textContent).toBe('ok');
  });
});
