// tests_js/showtoast.test.js — v0.16.8
//
// Régression : Atelier.toast() délègue à window.showToast(message, estErreur),
// qui n'était DÉFINIE NULLE PART → les toasts d'erreur des ateliers OO étaient
// invisibles (cf. échec de validation pédagogique HTTP 400 silencieux sur les
// cartes N10/S03/CA01-CA04). v0.16.8 ajoute window.showToast (adaptateur vers
// le toast existant atelToast).
//
// Ce test vérifie le câblage : Atelier.toast() (base) → window.showToast →
// window.atelToast, avec la bonne traduction du niveau 'erreur' → estErreur.

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
  charger('atelier_commun.js'); // définit window.showToast
  charger('atelier.js');        // définit window.Atelier (avec toast())
});

describe('window.showToast (correctif v0.16.8)', () => {
  beforeEach(() => {
    delete globalThis.window.atelToast;
  });

  it('est bien définie après chargement de atelier_commun.js', () => {
    expect(typeof globalThis.window.showToast).toBe('function');
  });

  it('délègue à atelToast en traduisant estErreur=true', () => {
    const spy = vi.fn();
    globalThis.window.atelToast = spy;
    globalThis.window.showToast('Échec', true);
    expect(spy).toHaveBeenCalledWith('Échec', true);
  });

  it('délègue à atelToast avec estErreur=false par défaut', () => {
    const spy = vi.fn();
    globalThis.window.atelToast = spy;
    globalThis.window.showToast('Validé');
    expect(spy).toHaveBeenCalledWith('Validé', false);
  });

  it("ne jette pas si atelToast est absent (fallback console)", () => {
    // atelToast supprimé en beforeEach : l'appel doit être silencieux, pas crasher.
    expect(() => globalThis.window.showToast('msg', true)).not.toThrow();
  });
});

describe('Atelier.toast() → showToast → atelToast (chaîne complète)', () => {
  it("un toast d'erreur d'un atelier remonte jusqu'à atelToast(msg, true)", () => {
    const spy = vi.fn();
    globalThis.window.atelToast = spy;
    // Instance minimale d'Atelier (config.id + prefixe requis).
    const a = new globalThis.window.Atelier({ id: 'test', prefixe: 'tst' });
    a.toast('La carte ne peut pas être validée en l\'état. — La carte n\'est liée à aucun objectif.', 'erreur');
    expect(spy).toHaveBeenCalledOnce();
    const [msg, estErreur] = spy.mock.calls[0];
    expect(estErreur).toBe(true);
    expect(msg).toContain("n'est liée à aucun objectif");
  });

  it("un toast info remonte avec estErreur=false", () => {
    const spy = vi.fn();
    globalThis.window.atelToast = spy;
    const a = new globalThis.window.Atelier({ id: 'test', prefixe: 'tst' });
    a.toast('Atome validé.');
    expect(spy).toHaveBeenCalledWith('Atome validé.', false);
  });
});
