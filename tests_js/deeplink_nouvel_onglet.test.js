// tests_js/deeplink_nouvel_onglet.test.js — v0.18.2
//
// Helpers d'ouverture d'un atome dans un nouvel onglet (Ctrl/⌘+clic) :
//   - deeplinkAtomeURL(type, id, niveau, sequence) -> URL ou null
//   - _nomAtelierPourDeeplink / _typeCourtAtome : normalisation carte
//   - ouvrirAtomeDepuisEvent(event, ...) : clic simple = en place,
//     Ctrl/⌘/Shift/molette = laisse le navigateur (retourne true)
//   - lienAtomeHTML(...) : balise <a> (ou <span> si niveau/seq manquants)
//
// On extrait ces fonctions du source app.js et on les évalue isolément
// (elles ne dépendent que les unes des autres + compilBatchOuvrirAtelier,
// qu'on mocke).

import { describe, it, expect, beforeAll, vi } from 'vitest';
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
  throw new Error('accolade de fin introuvable : ' + nom);
}

let H;  // helpers exportés
let compilSpy;

beforeAll(() => {
  const noms = ['_nomAtelierPourDeeplink', '_typeCourtAtome',
                'deeplinkAtomeURL', 'ouvrirAtomeDepuisEvent', 'lienAtomeHTML',
                'escAttrJs'];
  const src = noms.map(n => extraireFonction(APP, n)).join('\n');
  // compilBatchOuvrirAtelier est mocké via une globale injectée.
  const bundle = new Function('compilBatchOuvrirAtelier', src +
    '\nreturn { _nomAtelierPourDeeplink, _typeCourtAtome, deeplinkAtomeURL,' +
    ' ouvrirAtomeDepuisEvent, lienAtomeHTML, escAttrJs };');
  compilSpy = vi.fn();
  // Le code appelle `compilBatchOuvrirAtelier` (global). On le rend visible.
  globalThis.compilBatchOuvrirAtelier = compilSpy;
  H = bundle(compilSpy);
  // ouvrirAtomeDepuisEvent référence compilBatchOuvrirAtelier par nom global :
  // on s'assure qu'il pointe sur le spy.
  globalThis.compilBatchOuvrirAtelier = compilSpy;
});

describe('normalisation type/atelier', () => {
  it('carte -> carte_automatisme pour l’URL', () => {
    expect(H._nomAtelierPourDeeplink('carte')).toBe('carte_automatisme');
    expect(H._nomAtelierPourDeeplink('notion')).toBe('notion');
    expect(H._nomAtelierPourDeeplink('carte_automatisme')).toBe('carte_automatisme');
  });
  it('carte_automatisme -> carte (type court)', () => {
    expect(H._typeCourtAtome('carte_automatisme')).toBe('carte');
    expect(H._typeCourtAtome('exercice')).toBe('exercice');
  });
});

describe('deeplinkAtomeURL', () => {
  it('construit l’URL avec encodage', () => {
    expect(H.deeplinkAtomeURL('notion', 'no_1', 'N10', 'S01'))
      .toBe('/?atelier=notion&niveau=N10&seq=S01&atome=no_1');
  });
  it('mappe carte vers carte_automatisme', () => {
    expect(H.deeplinkAtomeURL('carte', 'ca_1', 'N10', 'S01'))
      .toBe('/?atelier=carte_automatisme&niveau=N10&seq=S01&atome=ca_1');
  });
  it('renvoie null si niveau ou séquence manquent', () => {
    expect(H.deeplinkAtomeURL('notion', 'no_1', '', 'S01')).toBeNull();
    expect(H.deeplinkAtomeURL('notion', 'no_1', 'N10', '')).toBeNull();
    expect(H.deeplinkAtomeURL('notion', '', 'N10', 'S01')).toBeNull();
  });
});

describe('ouvrirAtomeDepuisEvent', () => {
  it('clic simple : preventDefault + ouverture en place, retourne false', () => {
    compilSpy.mockClear();
    const ev = { ctrlKey: false, metaKey: false, shiftKey: false, button: 0,
                 preventDefault: vi.fn() };
    const r = H.ouvrirAtomeDepuisEvent(ev, 'notion', 'no_1', 'N10', 'S01');
    expect(r).toBe(false);
    expect(ev.preventDefault).toHaveBeenCalled();
    expect(compilSpy).toHaveBeenCalledWith('notion', 'no_1', 'N10', 'S01');
  });

  it('Ctrl+clic : laisse le navigateur (retourne true, pas d’ouverture en place)', () => {
    compilSpy.mockClear();
    const ev = { ctrlKey: true, metaKey: false, shiftKey: false, button: 0,
                 preventDefault: vi.fn() };
    const r = H.ouvrirAtomeDepuisEvent(ev, 'notion', 'no_1', 'N10', 'S01');
    expect(r).toBe(true);
    expect(ev.preventDefault).not.toHaveBeenCalled();
    expect(compilSpy).not.toHaveBeenCalled();
  });

  it('⌘+clic (metaKey) : nouvel onglet (true)', () => {
    const ev = { metaKey: true, preventDefault: vi.fn() };
    expect(H.ouvrirAtomeDepuisEvent(ev, 'carte', 'ca_1', 'N10', 'S01')).toBe(true);
  });

  it('clic-molette (button 1) : nouvel onglet (true)', () => {
    const ev = { button: 1, preventDefault: vi.fn() };
    expect(H.ouvrirAtomeDepuisEvent(ev, 'exercice', 'ex_1', 'N10', 'S01')).toBe(true);
  });

  it('mappe le type court pour l’ouverture en place (carte_automatisme -> carte)', () => {
    compilSpy.mockClear();
    const ev = { button: 0, preventDefault: vi.fn() };
    H.ouvrirAtomeDepuisEvent(ev, 'carte_automatisme', 'ca_1', 'N10', 'S01');
    expect(compilSpy).toHaveBeenCalledWith('carte', 'ca_1', 'N10', 'S01');
  });
});

describe('lienAtomeHTML', () => {
  it('produit un <a> deeplink avec onclick d’interception', () => {
    const h = H.lienAtomeHTML('notion', 'no_1', 'N10', 'S01', 'Ouvrir',
                              'class="vbtn"');
    expect(h).toContain('<a href="/?atelier=notion&niveau=N10&seq=S01&atome=no_1"');
    expect(h).toContain('target="_blank"');
    expect(h).toContain('rel="noopener"');
    expect(h).toContain("ouvrirAtomeDepuisEvent(event,'notion','no_1','N10','S01')");
    expect(h).toContain('class="vbtn"');
    expect(h).toContain('>Ouvrir</a>');
  });

  it('retombe sur un <span> inerte si niveau/séquence manquent', () => {
    const h = H.lienAtomeHTML('notion', 'no_1', '', '', 'Ouvrir', 'class="x"');
    expect(h).toContain('<span class="x">Ouvrir</span>');
    expect(h).not.toContain('<a ');
  });

  it('échappe l’apostrophe dans les arguments inline', () => {
    // id contenant une apostrophe (cas théorique) : escAttrJs protège.
    const h = H.lienAtomeHTML('notion', "no'1", 'N10', 'S01', 'X', '');
    expect(h).toContain("\\'");  // apostrophe échappée dans le onclick
  });
});
