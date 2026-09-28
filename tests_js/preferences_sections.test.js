// tests_js/preferences_sections.test.js — v0.18.4
//
// Onglet Préférences réorganisé en catégories + sections repliables (pref-cat),
// et déplacement des paramètres de compilation depuis le Rendu par lot.
//
// On teste les helpers extraits de app.js (sans monter toute l'app) :
//   - prefCatEstReplie / prefCatBasculer / prefCatInitEtats : pliage + persistance
//   - _compilLireParams : lit désormais les inputs pref-rdl-* (et plus rdl-*)

import { describe, it, expect, beforeEach, beforeAll, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const APP = readFileSync(join(__dirname, '..', 'static', 'app.js'), 'utf-8');

function extraireFonction(src, nom) {
  const re = new RegExp('function\\s+' + nom + '\\s*\\(');
  const m = re.exec(src);
  if (!m) throw new Error('fonction introuvable : ' + nom);
  let prof = 0;
  for (let j = src.indexOf('{', m.index); j < src.length; j++) {
    if (src[j] === '{') prof++;
    else if (src[j] === '}' && --prof === 0) return src.slice(m.index, j + 1);
  }
  throw new Error('fin introuvable : ' + nom);
}

// ── Analyse statique : structure attendue ──────────────────────────────────

describe('app.js — réorganisation préférences (v0.18.4)', () => {
  it('expose les helpers pref-cat', () => {
    expect(APP).toMatch(/function prefCatEstReplie\(/);
    expect(APP).toMatch(/function prefCatBasculer\(/);
    expect(APP).toMatch(/function prefCatInitEtats\(/);
  });
  it('_compilLireParams lit les inputs pref-rdl-* (déplacés), plus rdl-timeout-*', () => {
    const fn = extraireFonction(APP, '_compilLireParams');
    expect(fn).toContain("pref-rdl-timeout-court");
    expect(fn).toContain("pref-rdl-tikz-libs");
    expect(fn).not.toContain("getElementById('rdl-timeout-court')");
  });
  it('expose les fonctions de params compilation', () => {
    expect(APP).toMatch(/function prefChargerParamsCompilation\(/);
    expect(APP).toMatch(/function prefEnregistrerParamsCompilation\(/);
  });
});

// ── Helpers pref-cat en exécution (jsdom + localStorage simulé) ─────────────

describe('pref-cat : pliage et persistance', () => {
  let H;

  beforeAll(() => {
    const src = [
      extraireFonction(APP, '_prefCatStorageKey'),
      extraireFonction(APP, 'prefCatEstReplie'),
      extraireFonction(APP, 'prefCatBasculer'),
      extraireFonction(APP, 'prefCatInitEtats'),
    ].join('\n');
    // eslint-disable-next-line no-new-func
    H = new Function(src +
      '\nreturn { _prefCatStorageKey, prefCatEstReplie, prefCatBasculer, prefCatInitEtats };')();
  });

  beforeEach(() => {
    // localStorage simulé.
    const store = {};
    globalThis.localStorage = {
      getItem: (k) => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v); },
      removeItem: (k) => { delete store[k]; },
    };
    document.body.innerHTML = '';
  });

  it('clé de stockage stable par identifiant', () => {
    expect(H._prefCatStorageKey('outils-rendu-par-lot'))
      .toBe('seqenseigne.pref.cat.outils-rendu-par-lot.collapsed');
  });

  it('replié par défaut quand rien en localStorage', () => {
    expect(H.prefCatEstReplie('x', true)).toBe(true);
    // défaut implicite = replié
    expect(H.prefCatEstReplie('x')).toBe(true);
  });

  it('respecte la valeur mémorisée (0 = déplié, 1 = replié)', () => {
    globalThis.localStorage.setItem('seqenseigne.pref.cat.x.collapsed', '0');
    expect(H.prefCatEstReplie('x', true)).toBe(false);
    globalThis.localStorage.setItem('seqenseigne.pref.cat.x.collapsed', '1');
    expect(H.prefCatEstReplie('x', false)).toBe(true);
  });

  it('prefCatBasculer alterne la classe collapsed et persiste', () => {
    document.body.innerHTML =
      '<div class="pref-cat" data-pref-cat="sec1">' +
      '<div class="pref-cat-head">H</div><div class="pref-cat-body">B</div></div>';
    const head = document.querySelector('.pref-cat-head');
    const cat = document.querySelector('.pref-cat');
    // 1er clic : replie (ajoute collapsed) — l'élément démarre déplié.
    H.prefCatBasculer(head);
    expect(cat.classList.contains('collapsed')).toBe(true);
    expect(globalThis.localStorage.getItem('seqenseigne.pref.cat.sec1.collapsed')).toBe('1');
    // 2e clic : déplie.
    H.prefCatBasculer(head);
    expect(cat.classList.contains('collapsed')).toBe(false);
    expect(globalThis.localStorage.getItem('seqenseigne.pref.cat.sec1.collapsed')).toBe('0');
  });

  it('prefCatInitEtats replie tout par défaut, déplie ce qui est mémorisé', () => {
    document.body.innerHTML =
      '<div class="pref-cat" data-pref-cat="a"><div class="pref-cat-head"></div></div>' +
      '<div class="pref-cat" data-pref-cat="b"><div class="pref-cat-head"></div></div>';
    // 'b' a été déplié précédemment.
    globalThis.localStorage.setItem('seqenseigne.pref.cat.b.collapsed', '0');
    H.prefCatInitEtats();
    const a = document.querySelector('[data-pref-cat="a"]');
    const b = document.querySelector('[data-pref-cat="b"]');
    expect(a.classList.contains('collapsed')).toBe(true);   // défaut replié
    expect(b.classList.contains('collapsed')).toBe(false);  // mémorisé déplié
  });
});
