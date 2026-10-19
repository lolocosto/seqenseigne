// tests_js/series_documents_6e.test.js — v0.52.2
//
// Séries « documents » de la 6e dans l'atelier d'exercices (EV, TP, AC, AT) :
//   - préfixes à deux lettres reconnus avant « A » (AC01, AT01 ne sont pas
//     des exercices avancés) ;
//   - I1 : boutons proposés en 6e (N09) seulement, ou pour un atome qui porte
//     déjà une de ces séries ;
//   - série EV : le cadre « Remédiation » s'appelle « Sujet B » ; TP, AC, AT :
//     pas de remédiation ;
//   - module Évaluations : sujet et version transmis seulement en 6e.

import { describe, it, expect, beforeAll } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC = readFileSync(join(__dirname, '..', 'static', 'atelier_exercice.js'), 'utf-8');
const EVAL = readFileSync(join(__dirname, '..', 'static', 'atelier_evaluation_oo.js'), 'utf-8');
const EDIT = readFileSync(join(__dirname, '..', 'static', 'atelier_editeur.js'), 'utf-8');
const HTML = readFileSync(join(__dirname, '..', 'templates', 'index.html'), 'utf-8');

function extraire(nom) {
  const re = new RegExp(`AtelierExercice\\.${nom} = function[\\s\\S]*?\\n\\};`);
  const m = SRC.match(re);
  if (!m) throw new Error(`${nom} introuvable`);
  return m[0].replace(`AtelierExercice.${nom} =`, 'return');
}

describe('préfixes des séries documents', () => {
  let prefixeSerie;
  beforeAll(() => { prefixeSerie = new Function(extraire('prefixeSerie') + '\n')(); });
  it('AC, AT ne sont pas lus comme A ; EV, TP reconnus', () => {
    expect(prefixeSerie('AC02')).toBe('AC');
    expect(prefixeSerie('AT01')).toBe('AT');
    expect(prefixeSerie('EV12')).toBe('EV');
    expect(prefixeSerie('TP01')).toBe('TP');
    expect(prefixeSerie('A03')).toBe('A');
    expect(prefixeSerie('AE01')).toBe('AE');
    expect(prefixeSerie('E02')).toBe('E');
  });
  it('les sections documents ne s\'affichent que si elles ont des atomes', () => {
    expect(SRC).toMatch(/AtelierExercice\.SERIES_DOCUMENTS\.includes\(code\)\)\) continue/);
  });
});

describe('I1 / I2 : séries documents proposées au modèle « Fiches » du niveau (plus « N09 »)', () => {
  // v0.52.4 (I2) — le modèle vient du référentiel de l'atelier du niveau
  // (window.atlModeleFiches, static/gabarits_atelier.js), et non du code N09 :
  // un référentiel de 5e peut choisir le modèle « Fiches de résumé par
  // objectif », un référentiel de 6e le modèle « Notions et méthodes ».
  const SERIE_DOCUMENT = { EV: 'évaluation', TP: 'travail personnel',
    AC: 'activité complémentaire', AT: "séance d'atelier" };
  const avecModeles = (gabarits) => {
    const win = { atlModeleFiches: n => gabarits[n] === 'sixieme' };
    const AtelierExercice = { SERIE_DOCUMENT };
    AtelierExercice.modeleFiches = new Function('window', extraire('modeleFiches') + '\n')(win);
    return new Function('AtelierExercice', extraire('seriesDocumentsVisibles') + '\n')(
      AtelierExercice);
  };
  it('modèle Fiches → visibles ; Notions et méthodes → masquées, sauf atome déjà dans une de ces séries', () => {
    const visibles = avecModeles({ N09: 'sixieme', N11: 'cycle4' });
    expect(visibles('N09', 'fondamental')).toBe(true);
    expect(visibles('N11', 'fondamental')).toBe(false);
    expect(visibles('N11', 'travail personnel')).toBe(true);
  });
  it('le niveau ne décide plus : N10 au modèle Fiches les propose, N09 au modèle Notions non', () => {
    const visibles = avecModeles({ N09: 'cycle4', N10: 'sixieme' });
    expect(visibles('N10', 'fondamental')).toBe(true);
    expect(visibles('N09', 'fondamental')).toBe(false);
  });
  it('plus aucun test « === \'N09\' » pour décider du rendu ou des séries', () => {
    expect(SRC).not.toMatch(/niveau === 'N09'\s*\|\|/);
    expect(SRC).not.toMatch(/=== 'N09';\s*\n\s*overlay/);
    expect(SRC).toMatch(/estExercice6e\(\) \{[\s\S]*?AtelierExercice\.modeleFiches\(niveau\)/);
  });
  it('les boutons sont masqués par défaut dans le formulaire et la modale', () => {
    const boutons = HTML.match(/data-serie-document(-creation)?\s+style="display:none"/g) || [];
    expect(boutons.length).toBe(8);
  });
});

describe('cadre Remédiation : « Sujet B » pour une évaluation', () => {
  it('EV affiche le cadre, TP/AC/AT ne sont pas dans les séries autorisées', () => {
    expect(SRC).toMatch(/serieAutorise = \(this\.serieCourante === 'fondamental'\s*\|\| this\.serieCourante === 'avancé' \|\| estEval\)/);
  });
  it('libellés du cadre basculés selon la série', () => {
    const els = {};
    const doc = { getElementById: id => (els[id] = els[id] || { textContent: '', style: {} }) };
    const AtelierExercice = { LIBELLES_CADRE_REMED: {
      normal: { titre: 'Remédiation', case: 'c', enonce: 'e', corrige: 'r' },
      eval: { titre: 'Sujet B', case: 'cb', enonce: 'eb', corrige: 'rb' } } };
    const f = new Function('AtelierExercice', 'document',
      extraire('libellerCadreRemediation') + '\n')(AtelierExercice, doc);
    f(true);
    expect(els['atl-exercice-remed-titre'].textContent).toBe('Sujet B');
    expect(els['atl-exercice-remed-aide'].style.display).toBe('none');
    f(false);
    expect(els['atl-exercice-remed-titre'].textContent).toBe('Remédiation');
  });
  it('le gabarit porte les identifiants des libellés', () => {
    for (const id of ['atl-exercice-remed-titre', 'atl-exercice-remed-case-libelle',
                      'atl-exercice-remed-enonce-libelle', 'atl-exercice-remed-corrige-libelle'])
      expect(HTML).toContain(`id="${id}"`);
  });
});

describe('module Évaluations : sujet et version en 6e', () => {
  it('la base n\'ajoute aucun paramètre (autres ateliers inchangés)', () => {
    expect(EDIT).toMatch(/parametresRendu\(\) \{\s*return '';\s*\}/);
    expect(EDIT).toMatch(/\/rendu-pdf`\s*\+ this\.parametresRendu\(\)/);
  });
  it("l'évaluation ne transmet sujet/version qu'au modèle « Fiches » de son niveau (v0.52.4)", () => {
    expect(EVAL).toMatch(/_estEval6e\(\) \{[\s\S]*?window\.atlModeleFiches\(n\)/);
    expect(EVAL).toMatch(/if \(!this\._estEval6e\(\)\) return '';/);
  });
});
