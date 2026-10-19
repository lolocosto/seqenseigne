// tests_js/gabarit_documents.test.js — v0.52.1
//
// Gabarit de documents d'un référentiel (cycle4 / sixieme) côté interface :
//   - G1 : à la création, la liste est préremplie selon le niveau (6e →
//     sixieme, 5e à 3e → cycle4) et la valeur choisie est envoyée ;
//   - G2 : dans « Documents à publier », le choix n'est modifiable que tant
//     que le référentiel est « en cours » ;
//   - G5 : un type d'un autre gabarit s'affiche avec le libellé et les
//     options fournis par le serveur (interface générique).

import { describe, it, expect, beforeAll } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const src = f => readFileSync(join(__dirname, '..', 'static', f), 'utf-8');
const HTML = readFileSync(join(__dirname, '..', 'templates', 'index.html'), 'utf-8');

describe('création : gabarit prérempli selon le niveau (G1)', () => {
  let ctx;
  beforeAll(() => {
    const code = src('referentiel_unifie.js');
    const debut = code.indexOf('function refuGabaritParDefaut');
    const fin = code.indexOf('async function refuCreer');
    ctx = new Function('document', 'ATL_FILTRE_NIVEAU',
      code.slice(debut, fin) + '; return { refuGabaritParDefaut, refuPreremplirGabarit };');
  });

  it('N09 → sixieme, N10 à N12 → cycle4', () => {
    const { refuGabaritParDefaut } = ctx(null, '');
    expect(refuGabaritParDefaut('N09')).toBe('sixieme');
    for (const n of ['N10', 'N11', 'N12', '']) expect(refuGabaritParDefaut(n)).toBe('cycle4');
  });

  it('préremplit au changement de niveau, garde un choix manuel sinon', () => {
    const sel = { value: 'cycle4', dataset: {} };
    const doc = { getElementById: () => sel };
    ctx(doc, 'N09').refuPreremplirGabarit();
    expect(sel.value).toBe('sixieme');
    sel.value = 'cycle4';                       // choix manuel, même niveau
    ctx(doc, 'N09').refuPreremplirGabarit();
    expect(sel.value).toBe('cycle4');
    ctx(doc, 'N11').refuPreremplirGabarit();    // niveau changé
    expect(sel.value).toBe('cycle4');
  });

  it('la liste existe et la valeur part avec les deux créations', () => {
    expect(HTML).toMatch(/id="refu-c-gabarit"/);
    const code = src('referentiel_unifie.js');
    expect(code).toMatch(/type_ref: type, gabarit \}/);
    expect(code).toMatch(/type_ref: type, modele, gabarit \}/);
  });
});

describe('Documents à publier : gabarit et types génériques (G2, G5)', () => {
  let ctx;
  beforeAll(() => {
    const code = src('atelier_referentiel.js');
    ctx = (selection) => new Function('ATL_REF_SELECTION',
      code.slice(code.indexOf('const ATL_REF_DOC_TITRES'), code.indexOf('async function atelRefChargerEtRendreDocuments'))
      + code.slice(code.indexOf('const ATL_REF_GABARITS'), code.indexOf('async function atelRefChangerGabarit'))
      + code.slice(code.indexOf('function atelRefDocumentOptionsHtml'), code.indexOf('async function atelRefMajOptionDoc'))
      + code.slice(code.indexOf('function atelRefEscape'), code.indexOf('// Exposition globale'))
      + '; return { atelRefGabaritHtml, atelRefDocumentOptionsHtml };')(selection);
  });

  it('sélecteur actif en cours, désactivé une fois verrouillé', () => {
    expect(ctx({ id: 'R', etat: 'en_cours', gabarit_documents: 'sixieme' })
      .atelRefGabaritHtml()).not.toMatch(/disabled/);
    const fige = ctx({ id: 'R', etat: 'verrouille', gabarit_documents: 'sixieme' }).atelRefGabaritHtml();
    expect(fige).toMatch(/disabled/);
    expect(fige).toMatch(/value="sixieme" selected/);
  });

  it('options d\'un type 6e rendues depuis les champs du catalogue', () => {
    const html = ctx({ id: 'R', etat: 'en_cours' }).atelRefDocumentOptionsHtml({
      id: 'd1', type_document: 'livret_sequence_6e',
      options: { actif: true, version: 'corrigee', inclure_activites: true },
      champs: [{ cle: 'version', libelle: 'Version', type: 'choix',
                 valeurs: [['eleve', 'élève'], ['corrigee', 'corrigée']] },
               { cle: 'inclure_activites', libelle: "Activités d'introduction", type: 'bool' }],
    }, true);
    expect(html).toMatch(/value="corrigee"\s+checked/);
    expect(html).toMatch(/atelRefMajOptionDoc\('d1', 'inclure_activites'/);
  });
});
