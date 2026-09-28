// tests_js/atelier_exercice_bucket_ae.test.js — v0.18.3.1
//
// Régression : dans l'atelier exercice, les exercices d'approche
// (serie_code='AE') doivent être rangés dans le bucket d'affichage 'AE',
// PAS dans 'Autres' (symptôme : invisibles) ni dans 'A'/avancés (symptôme :
// mal classés via le fallback code.charAt(0) sur un code 'AE01').
//
// Cause historique : le bucket s'appelait 'EA' (ancienne convention) alors
// que serie_code vaut 'AE'. Corrigé en v0.18.3.1 (buckets/ordre/SERIE_BUCKETS
// /SERIE_EN_CODE → 'AE').
//
// Deux volets : analyse statique des constantes + bucketing fonctionnel.

import { describe, it, expect, beforeAll } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC = readFileSync(
  join(__dirname, '..', 'static', 'atelier_exercice.js'), 'utf-8');

// ── Volet 1 : constantes ─────────────────────────────────────────────────────

describe('atelier_exercice.js — constantes série approche = AE (v0.18.3.1)', () => {
  it('SERIE_BUCKETS a une clé AE (et plus de clé EA)', () => {
    expect(SRC).toMatch(/SERIE_BUCKETS\s*=\s*\{[\s\S]*?\bAE:\s*\{/);
    expect(SRC).not.toMatch(/SERIE_BUCKETS\s*=\s*\{[\s\S]*?\bEA:\s*\{/);
  });

  it("SERIE_EN_CODE['approche'] vaut 'AE'", () => {
    expect(SRC).toMatch(/'approche':\s*'AE'/);
    expect(SRC).not.toMatch(/'approche':\s*'EA'/);
  });

  it("l'objet buckets et l'ordre utilisent AE, pas EA", () => {
    expect(SRC).toMatch(/buckets\s*=\s*\{\s*F:\s*\[\],\s*A:\s*\[\],\s*E:\s*\[\],\s*AE:\s*\[\]/);
    expect(SRC).toMatch(/ordre\s*=\s*\['F',\s*'A',\s*'E',\s*'AE',\s*'Autres'\]/);
  });
});

// ── Volet 2 : le préfixe de série gère AE (2 lettres) avant A ───────────────
//
// Le backend renvoie un contrat à 6 clés SANS serie_code : la série est le
// PRÉFIXE de `ex.code` ('F01', 'A03', 'AE01'…). Le piège est qu'un code
// 'AE01' commence par 'A' : sans reconnaissance du préfixe à 2 lettres, il
// tomberait dans le bucket Avancés. On teste le helper prefixeSerie et le
// fait qu'il est branché dans la chaîne de résolution.

describe('atelier_exercice — préfixe de série AE (2 lettres)', () => {
  let prefixeSerie;
  beforeAll(() => {
    // Extrait la fonction du source et l'évalue isolément.
    const m = SRC.match(
      /AtelierExercice\.prefixeSerie = function[\s\S]*?\n\};/);
    if (!m) throw new Error('prefixeSerie introuvable dans le source');
    const src = m[0].replace('AtelierExercice.prefixeSerie =', 'return');
    // eslint-disable-next-line no-new-func
    prefixeSerie = new Function(src + '\n')();
  });

  it("'AE01' → 'AE' (pas 'A')", () => {
    expect(prefixeSerie('AE01')).toBe('AE');
  });
  it("'A01' → 'A', 'F03' → 'F', 'E02' → 'E', 'R05' → 'R'", () => {
    expect(prefixeSerie('A01')).toBe('A');
    expect(prefixeSerie('F03')).toBe('F');
    expect(prefixeSerie('E02')).toBe('E');
    expect(prefixeSerie('R05')).toBe('R');
  });
  it('code vide ou inconnu → \'\'', () => {
    expect(prefixeSerie('')).toBe('');
    expect(prefixeSerie('X9')).toBe('');
    expect(prefixeSerie(null)).toBe('');
  });

  it('la chaîne de résolution du bucketing utilise prefixeSerie(ex.code)', () => {
    // serie_code (absent du contrat 6 clés) puis SERIE_EN_CODE puis
    // prefixeSerie(ex.code) — plus de ex.code.charAt(0) qui cassait AE.
    expect(SRC).toMatch(
      /const code = ex\.serie_code\s*\n?\s*\|\|\s*AtelierExercice\.SERIE_EN_CODE\[ex\.serie\]\s*\n?\s*\|\|\s*AtelierExercice\.prefixeSerie\(ex\.code\)/
    );
    expect(SRC).not.toContain('ex.code.charAt(0)');
  });
});

// ── Volet 3 : bucketing FONCTIONNEL (rendreSidebar réel) ────────────────────
//
// Ce volet monte la vraie classe et appelle rendreSidebar avec des exos au
// format réel du backend (6 clés, code préfixé 'AE01'…), pour vérifier le
// rangement effectif — c'est le test qui aurait attrapé la régression v0.18.3.1
// (où 'AE01' tombait dans le bucket Avancés via charAt(0)).

describe('atelier_exercice — rendreSidebar range les AE dans le bucket AE', () => {
  let inst;
  let capturees;

  beforeAll(() => {
    globalThis.window = globalThis.window || {};
    globalThis.window.atelGardeEnregistrer = () => {};
    globalThis.window.atelCatEstReplie = () => false;
    globalThis.window.atelObjLiesEnTags = () => [];
    globalThis.window.atelObjLiesBadgesHtml = () => '';
    // Capture (code, count) de chaque section rendue.
    globalThis.window.atelAsmCatHtml = (atelier, code, label, count) => {
      capturees.push({ code, count });
      return `<section data-code="${code}">${count}</section>`;
    };

    const charger = (rel) => {
      const code = readFileSync(join(__dirname, '..', 'static', rel), 'utf-8');
      // eslint-disable-next-line no-new-func
      new Function(code)();
    };
    charger('atelier.js');
    charger('atelier_editeur.js');
    charger('atelier_exercice.js');
    inst = globalThis.window.ATELIER_EXERCICE;
  });

  function rendre(items) {
    capturees = [];
    document.body.innerHTML = '<div id="atl-exercice-list"></div>';
    inst.liste = items;
    inst.rendreSidebar();
    return Object.fromEntries(capturees.map(s => [s.code, s.count]));
  }

  it('exos au format backend (code AE01) : AE dans bucket AE, pas A', () => {
    // Reproduit N10/S14 : 3 F, 3 A, 3 E, 2 AE.
    const parCode = rendre([
      { id: 'f1', code: 'F01', titre: 'F1' },
      { id: 'a1', code: 'A01', titre: 'A1' },
      { id: 'a2', code: 'A02', titre: 'A2' },
      { id: 'ae1', code: 'AE01', titre: 'AE1' },
      { id: 'ae2', code: 'AE02', titre: 'AE2' },
      { id: 'e1', code: 'E01', titre: 'E1' },
    ]);
    expect(parCode['AE']).toBe(2);   // les 2 AE bien rangés
    expect(parCode['A']).toBe(2);    // seulement les vrais avancés
    expect(parCode['F']).toBe(1);
    expect(parCode['E']).toBe(1);
    expect(parCode['Autres'] || 0).toBe(0);  // aucune fuite
  });

  it('aucun exo AE ne fuit dans le bucket Avancés (régression v0.18.3.1)', () => {
    const parCode = rendre([
      { id: 'ae1', code: 'AE01', titre: 'AE1' },
      { id: 'ae2', code: 'AE02', titre: 'AE2' },
      { id: 'ae3', code: 'AE03', titre: 'AE3' },
    ]);
    expect(parCode['AE']).toBe(3);
    expect(parCode['A'] || 0).toBe(0);
  });
});
