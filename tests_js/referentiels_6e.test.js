// tests_js/referentiels_6e.test.js — v0.54.0
//
// Référentiels internes de 6e (principal, mises en route) côté interface :
//   - RI10 : « + Créer » montre d'abord le contenu (type, modèle, état de
//     départ, séquences, parties, objectifs, documents, préparation), puis
//     « Confirmer la création » ;
//   - RI12 : la progression de mise en route de la classe propose aussi les
//     référentiels de mises en route internes verrouillés.

import { describe, it, expect, beforeAll } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const src = f => readFileSync(join(__dirname, '..', 'static', f), 'utf-8');
const HTML = readFileSync(join(__dirname, '..', 'templates', 'index.html'), 'utf-8');

const APERCU = {
  niveau: 'N09', type_ref: 'mer', libelle_type: 'Référentiel de mises en route',
  gabarit: 'sixieme', libelle_modele: 'Fiches de résumé par objectif',
  nb_sequences: 7, nb_parties: 22, nb_objectifs: 25, nb_objectifs_cours: 0, nb_seances: 131,
  nb_sequences_validees: 2, atomes_non_valides: 253, atomes_total: 253,
  nb_evaluations: 22, evaluations_non_valides: 22,
  sequences: [{ code: 'M01', nom: 'Calcul mental', parties: 4, objectifs: 4, validee: true }],
  documents: [{ cle: 'mer_fiches_cours_6e', libelle: 'Fiches de cours' },
              { cle: 'mer_dossiers_6e', libelle: 'Dossier enseignant' }],
};

describe('RI10 : aperçu avant création', () => {
  let apercu;
  beforeAll(() => {
    const code = src('referentiel_unifie.js');
    const debut = code.indexOf('function refuApercuCreationHtml');
    const fin = code.indexOf('async function refuApercuCreation(');
    apercu = new Function('_refuE', code.slice(debut, fin) + '; return refuApercuCreationHtml;')(
      x => String(x == null ? '' : x));
  });

  it('dit le type, le modèle, l\'état de départ et le contenu avant de confirmer', () => {
    const h = apercu(APERCU);
    expect(h).toMatch(/Avant de créer : Référentiel de mises en route/);
    expect(h).toMatch(/modèle « Fiches de résumé par objectif »/);
    expect(h).toMatch(/créé à l'état <strong>en cours<\/strong>/);
    expect(h).toMatch(/<strong>7<\/strong> séquence\(s\), <strong>22<\/strong> partie\(s\)/);
    expect(h).toMatch(/<strong>25<\/strong> objectif\(s\)/);
    expect(h).toMatch(/Fiches de cours, Dossier enseignant/);
    expect(h).toMatch(/2 \/ 7 séquence\(s\) validée\(s\)/);
    expect(h).toMatch(/onclick="refuCreer\(true\)">Confirmer la création/);
  });

  it('prévient quand il n\'y a pas de séquence de mise en route ou pas de documents', () => {
    const h = apercu({ ...APERCU, nb_sequences: 0, sequences: [], gabarit: 'cycle4',
                       libelle_modele: 'Notions et méthodes' });
    expect(h).toMatch(/Aucune séquence de mise en route \(Mnn\)/);
    expect(h).toMatch(/aucun document/);
  });

  it('la liste de création nomme clairement les deux types', () => {
    expect(HTML).toMatch(/<option value="principal">Référentiel principal<\/option><option value="mer">Référentiel de mises en route<\/option>/);
    const code = src('referentiel_unifie.js');
    expect(code).toMatch(/source === 'interne' && confirme !== true/);
  });
});

describe('RI12 : progression de mise en route de la classe', () => {
  it('propose les référentiels de mises en route internes verrouillés en plus des externes', () => {
    const code = src('progression_mer.js');
    expect(code).toMatch(/\/api\/referentiels\?niveau=' \+ encodeURIComponent\(niveau\)\s*\+ '&type=mer&etats=verrouille,utilise'/);
    expect(code).toMatch(/source: 'fige', interne: true/);
  });
});
