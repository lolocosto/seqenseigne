// tests_js/series_fiches_mention.test.js — v0.56.0
//
// Décisions de Laurent (13 novembre) pour le modèle « Fiches » :
//   - séries F, A, E affichées « Entraînement (EN) », « Approfondissement (AP) »,
//     « Expertise (EX) » et codes EN06 / AP05 / EX02 dans l'interface ; les codes
//     internes (F06…) restent ceux de la base et de l'API, et le modèle « Notions et
//     méthodes » (cycle 4) ne change pas ;
//   - champ « Mention » (O obligatoire / F facultatif) dans l'atelier Exercice,
//     lu et rempli par le formulaire (sinon un enregistrement l'effacerait).

import { describe, it, expect, beforeAll } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC = readFileSync(join(__dirname, '..', 'static', 'atelier_exercice.js'), 'utf-8');
const GAB = readFileSync(join(__dirname, '..', 'static', 'gabarits_atelier.js'), 'utf-8');
const HTML = readFileSync(join(__dirname, '..', 'templates', 'index.html'), 'utf-8');

function extraire(nom) {
  const re = new RegExp(`AtelierExercice\\.${nom} = function[\\s\\S]*?\\n\\};`);
  const m = SRC.match(re);
  if (!m) throw new Error(`${nom} introuvable`);
  return m[0].replace(`AtelierExercice.${nom} =`, 'return');
}

describe('codes et noms de série affichés (atelier Exercice)', () => {
  let AE;
  beforeAll(() => {
    const debut = SRC.indexOf('AtelierExercice.SERIES_FICHES = {');
    const fin = SRC.indexOf('};', debut) + 2;
    AE = {
      modeleFiches: n => n === 'N09',
      SERIE_BUCKETS: { F: { label: 'Fondamentaux' }, A: { label: 'Avancés' },
                       E: { label: 'Exploration' }, AE: { label: 'Approche (AE)' } },
    };
    new Function('AtelierExercice', SRC.slice(debut, fin))(AE);
    for (const n of ['prefixeAffiche', 'codeAffiche', 'libelleBucket']) {
      AE[n] = new Function('AtelierExercice', extraire(n) + '\n')(AE);
    }
  });

  it('modèle Fiches : EN / AP / EX, codes EN06…, sections renommées', () => {
    expect(AE.codeAffiche('F06', 'N09')).toBe('EN06');
    expect(AE.codeAffiche('A05', 'N09')).toBe('AP05');
    expect(AE.codeAffiche('E02', 'N09')).toBe('EX02');
    expect(AE.prefixeAffiche('A', 'N09')).toBe('AP');
    expect(AE.libelleBucket('F', 'N09')).toBe('Entraînement (EN)');
    expect(AE.libelleBucket('E', 'N09')).toBe('Expertise (EX)');
  });

  it('autres séries et cycle 4 inchangés', () => {
    for (const c of ['AE01', 'EV03', 'TP01', 'AC02', 'AT01', 'MR04']) {
      expect(AE.codeAffiche(c, 'N09')).toBe(c);
    }
    expect(AE.codeAffiche('F06', 'N11')).toBe('F06');
    expect(AE.prefixeAffiche('A', 'N11')).toBe('A');
    expect(AE.libelleBucket('F', 'N11')).toBe('Fondamentaux');
    expect(AE.libelleBucket('AE', 'N09')).toBe('Approche (AE)');
  });

  it('module commun gabarits_atelier.js : même table', () => {
    const ctx = new Function('window', GAB.replace(/if \(typeof window[\s\S]*$/, '')
      + '; ATL_GABARITS.niveaux = {N09: "sixieme", N11: "cycle4"};'
      + ' return { atlCodeExercice, atlPrefixeSerie, atlLibelleSerie };')({});
    expect(ctx.atlCodeExercice('F12', 'N09')).toBe('EN12');
    expect(ctx.atlCodeExercice('F12', 'N11')).toBe('F12');
    expect(ctx.atlPrefixeSerie('E', 'N09')).toBe('EX');
    expect(ctx.atlLibelleSerie('A', 'N09', 'Avancé')).toBe('Approfondissement');
    expect(ctx.atlLibelleSerie('A', 'N11', 'Avancé')).toBe('Avancé');
  });

  it('le badge et l\'identifiant de la liste passent par le code affiché', () => {
    expect(SRC).toMatch(/AtelierExercice\.codeAffiche\(ex\.code \|\| '', niveauListe\)/);
    expect(SRC).toMatch(/AtelierExercice\.prefixeAffiche\(badgeCode, niveauListe\)/);
  });
});

describe('champ « Mention » (O / F)', () => {
  it('présent dans le formulaire, O par défaut', () => {
    expect(HTML).toMatch(/<select id="atl-exercice-mention"[^>]*>\s*<option value="O">O — obligatoire<\/option>\s*<option value="F">F — facultatif<\/option>/);
  });

  it('collecté et rempli (absent ou inconnu → O)', () => {
    expect(SRC).toMatch(/mention:\s+AtelierExercice\.lireMention\(this\.\$\('mention'\)\)/);
    expect(SRC).toMatch(/mentionEl\.value = ex\.mention === 'F' \? 'F' : 'O'/);
    const lire = new Function('AtelierExercice', extraire('lireMention') + '\n')({});
    expect(lire({ value: 'F' })).toBe('F');
    expect(lire({ value: 'O' })).toBe('O');
    expect(lire({ value: 'x' })).toBe('O');
    expect(lire(null)).toBe('O');
  });

  it('visible au modèle Fiches pour les séries F, A, E seulement', () => {
    const vis = new Function('AtelierExercice', extraire('mentionVisible') + '\n')(
      { modeleFiches: n => n === 'N09' });
    for (const s of ['fondamental', 'avancé', 'exploration']) expect(vis('N09', s)).toBe(true);
    for (const s of ['approche', 'évaluation', 'mise en route']) expect(vis('N09', s)).toBe(false);
    expect(vis('N11', 'fondamental')).toBe(false);
  });
});
