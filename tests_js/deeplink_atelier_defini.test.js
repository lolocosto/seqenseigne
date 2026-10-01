// v0.33.1 — Non-régression : _appliquerDeeplink ne doit pas lever
// « atelier is not defined » quand l'URL n'a pas de ?atelier=… (cas normal du
// chargement). Cette erreur interrompait init() et laissait l'onglet Suivi vide.
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
// v0.41.0 — Chemin relatif au fichier de test (le chemin absolu d'origine ne
// pouvait exister que dans l'environnement où le test avait été écrit).
const __dirname = dirname(fileURLToPath(import.meta.url));
const APP = readFileSync(join(__dirname, '..', 'static', 'app.js'), 'utf-8');

describe('deeplink — atelier défini', () => {
  it('_appliquerDeeplink sans ?atelier ne lève pas d’erreur', () => {
    // Extraire la fonction et l'exécuter avec une URL sans paramètre.
    const m = APP.match(/function _appliquerDeeplink[\s\S]*?\n\}/);
    expect(m).not.toBeNull();
    // Stubs minimaux.
    global.window = { location: { search: '' } };
    global.URLSearchParams = URLSearchParams;
    let box = {};
    eval(m[0] + '\n; box.fn = _appliquerDeeplink;');
    // Ne doit pas lever.
    expect(() => box.fn()).not.toThrow();
  });

  it('la source contient bien la lecture de atelier', () => {
    expect(APP).toMatch(/const atelier = params\.get\('atelier'\)/);
  });
});
