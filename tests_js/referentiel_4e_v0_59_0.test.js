// tests_js/referentiel_4e_v0_59_0.test.js — v0.59.0
//
// Création d'un référentiel interne de 4e au modèle « Fiches » (décision D4) :
//   - l'année se choisit (en cours ou suivante) : en novembre 2026, « 4e —
//     2027-2028 — Principal » se crée sans attendre août 2027 ;
//   - l'option « cartes d'automatisme » n'est proposée qu'au modèle Fiches,
//     pour un principal interne (au modèle « Notions et méthodes », les cartes
//     comptent déjà) ; l'aperçu « Avant de créer » annonce les cartes
//     rattachées qui compteront dans la validation ;
//   - année et option partent au serveur avec la création.

import { describe, it, expect, beforeAll } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const CODE = readFileSync(join(__dirname, '..', 'static', 'referentiel_unifie.js'), 'utf-8');
const HTML = readFileSync(join(__dirname, '..', 'templates', 'index.html'), 'utf-8');

function extraire(debut, fin) {
  return CODE.slice(CODE.indexOf(debut), CODE.indexOf(fin));
}

const APERCU = {
  niveau: 'N11', type_ref: 'principal', libelle_type: 'Référentiel principal',
  gabarit: 'sixieme', libelle_modele: 'Fiches de résumé par objectif',
  nb_sequences: 1, nb_parties: 1, nb_objectifs: 2, nb_objectifs_cours: 1, nb_seances: 0,
  nb_sequences_validees: 0, atomes_non_valides: 10, atomes_total: 10,
  nb_evaluations: 0, evaluations_non_valides: 0, sequences: [], documents: [],
};

describe('année du référentiel interne', () => {
  let annees;
  beforeAll(() => {
    annees = new Function(extraire('function refuAnneesProposees', 'function refuRemplirAnnees')
      + '; return refuAnneesProposees;')();
  });

  it('propose l\'année en cours puis la suivante (bascule en août)', () => {
    expect(annees(new Date(2026, 10, 16))).toEqual(['2026-2027', '2027-2028']);
    expect(annees(new Date(2027, 1, 15))).toEqual(['2026-2027', '2027-2028']);
    expect(annees(new Date(2027, 7, 1))).toEqual(['2027-2028', '2028-2029']);
  });

  it('la liste existe dans le formulaire et l\'année part avec la création', () => {
    expect(HTML).toMatch(/<select id="refu-c-annee"/);
    expect(CODE).toMatch(/\{ annee, cartes_automatisme: cartes \}\)\) \}\);/);
  });
});

describe('option « cartes d\'automatisme »', () => {
  let proposable;
  beforeAll(() => {
    proposable = new Function(extraire('function refuOptionCartesProposable',
      'function refuMajChoixModele') + '; return refuOptionCartesProposable;')();
  });

  it('seulement au modèle Fiches, pour un principal interne', () => {
    expect(proposable('interne', 'principal', 'sixieme')).toBe(true);
    expect(proposable('interne', 'principal', 'cycle4')).toBe(false);
    expect(proposable('interne', 'mer', 'sixieme')).toBe(false);
    expect(proposable('externe', 'principal', 'sixieme')).toBe(false);
  });

  it('la case est dans le formulaire, cachée par défaut', () => {
    expect(HTML).toMatch(/<label id="refu-c-cartes-bloc"[^>]*style="display:none"/);
    expect(HTML).toMatch(/<input type="checkbox" id="refu-c-cartes"/);
  });
});

describe('aperçu « Avant de créer »', () => {
  let apercu;
  beforeAll(() => {
    apercu = new Function('_refuE', extraire('function refuApercuCreationHtml',
      'async function refuApercuCreation(') + '; return refuApercuCreationHtml;')(
      x => String(x == null ? '' : x));
  });

  it('annonce l\'année choisie et les cartes rattachées comptées dans la validation', () => {
    const h = apercu({ ...APERCU, annee: '2027-2028', cartes_automatisme: true, nb_cartes: 2,
                       cartes_non_valides: 2 });
    expect(h).toMatch(/<strong>Année :<\/strong> 2027-2028/);
    expect(h).toMatch(/Cartes d'automatisme :<\/strong> 2 rattachée\(s\) aux\s+objectifs, dont 2 non validée\(s\)/);
  });

  it('sans option ni année, rien de plus qu\'avant', () => {
    const h = apercu(APERCU);
    expect(h).not.toMatch(/Cartes d'automatisme/);
    expect(h).not.toMatch(/Année :/);
  });
});
