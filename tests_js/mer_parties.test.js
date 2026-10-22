// tests_js/mer_parties.test.js — v0.53.1
//
// Mises en route en parties (décisions du 22 octobre 2026) côté interface :
//   - MR5 révisé : l'onglet Rendu PDF d'une séquence Mnn envoie la partie
//     choisie (vide = toute la séquence) et propose les parties lues sur la
//     route /mer ;
//   - MR6 révisé : le contrôle de la mise en route est affiché par partie ;
//   - numérotation 201+ : l'arbre du niveau (atelier des référentiels)
//     affiche le code Mnn/Xnn au lieu de « S201 » / « S101 ».

import { describe, it, expect, beforeAll } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const lire = rel => readFileSync(join(__dirname, '..', rel), 'utf-8');

function charger(rel) {
  // eslint-disable-next-line no-new-func
  new Function(lire(join('static', rel)))();
}

describe('numérotation 201+ : code affiché des séquences de l\'arbre du niveau', () => {
  let atelRefCodeSequence;
  beforeAll(() => {
    const code = lire('static/atelier_referentiel.js');
    const debut = code.indexOf('function atelRefCodeSequence');
    const fin = code.indexOf('function atelRefSequenceHtml');
    atelRefCodeSequence = new Function(code.slice(debut, fin) + '; return atelRefCodeSequence;')();
  });
  it('M01 (numéro 201) s\'affiche M01, X03 (103) s\'affiche X03', () => {
    expect(atelRefCodeSequence({ code: 'M01', numero: 201 })).toBe('M01');
    expect(atelRefCodeSequence({ code: 'X03', numero: 103 })).toBe('X03');
  });
  it('S01 et le cycle 4 : affichage inchangé (S + numéro)', () => {
    expect(atelRefCodeSequence({ code: 'S01', numero: 1 })).toBe('S01');
    expect(atelRefCodeSequence({ numero: 7 })).toBe('S07');
  });
  it('les deux affichages de séquence utilisent le code', () => {
    const code = lire('static/atelier_referentiel.js');
    expect(code).not.toMatch(/S\$\{String\(s\.numero\)\.padStart/);
    expect(code.match(/\$\{atelRefCodeSequence\(s\)\}/g).length).toBe(2);
  });
});

describe('MR5 et MR6 révisés : onglet Rendu PDF d\'une mise en route', () => {
  let A;
  beforeAll(() => {
    globalThis.window.atelGardeEnregistrer = globalThis.window.atelGardeEnregistrer || (() => {});
    charger('atelier.js');
    charger('atelier_editeur.js');
    charger('atelier_assemblage.js');
    charger('seqniv_pur.js');
    charger('atelier_seqniv_assemblage.js');
    A = globalThis.window.ATELIER_SEQNIV;
  });
  const RESUME = {
    code: 'M01', parties: [
      { numero: 1, titre: 'Partie 1 --- Tables', objectifs: ['M01-02'], exercices: 6, seances: 6,
        tests: [{ numero: 30, titre: 'Test court --- Tables' }], fiche: 'Tables' },
      { numero: 2, titre: 'Partie 2 --- Compléments', objectifs: ['M01-12'], exercices: 5,
        seances: 6, tests: [], fiche: '' }],
    validation: { valide: false, erreurs: ['partie 2 : pas de fiche de cours'],
                  avertissements: ['partie 2 : aucun test court', 'fiche « X » attachée à aucune partie (ancienne fiche de séquence)'],
                  parties: { 1: { erreurs: [], avertissements: [] },
                             2: { erreurs: ['partie 2 : pas de fiche de cours'],
                                  avertissements: ['partie 2 : aucun test court'] } } } };

  it('la partie choisie part avec les options (vide : toute la séquence)', () => {
    A.data = { sequence_par_niveau: { niveau: 'N09', sequence_code: 'M01' } };
    document.body.innerHTML = '<select id="livret-seq-mer-partie"><option value="">toute</option></select>';
    expect(A._livretSeqOptions().mer.partie).toBe('');
    A._remplirPartiesMer(RESUME);
    const sel = document.getElementById('livret-seq-mer-partie');
    expect([...sel.options].map(o => o.textContent)).toEqual(
      ['toute la séquence', 'Partie 1 — Tables', 'Partie 2 — Compléments']);
    expect(sel.value).toBe('1');                     // plusieurs parties : la première
    sel.value = '2';
    expect(A._livretSeqOptions().mer.partie).toBe('2');
  });

  it('contrôle MR6 affiché par partie, sans répéter un message de partie', () => {
    const h = A._htmlControleMer(RESUME);
    expect(h).toMatch(/à compléter/);
    expect(h).toMatch(/Partie 2 — Compléments/);
    expect(h.match(/pas de fiche de cours/g).length).toBe(1);
    expect(h.match(/aucun test court/g).length).toBe(1);
    expect(h).toMatch(/attachée à aucune partie/);
  });

  it('le gabarit de l\'onglet a la liste des parties et la zone de contrôle', () => {
    const code = lire('static/atelier_seqniv_assemblage.js');
    expect(code).toMatch(/id="livret-seq-mer-partie"/);
    expect(code).toMatch(/id="livret-seq-mer-controle"/);
    expect(code).toMatch(/\/mer`\)/);
  });
});
