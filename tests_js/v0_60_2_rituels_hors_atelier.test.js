// tests_js/v0_60_2_rituels_hors_atelier.test.js — v0.60.2
//
// Décision du 18 novembre (22 h 39) : le cadre « Rituels d'automatismes et
// séances d'évaluation (progression) » n'a pas sa place dans l'atelier
// Référentiel. Il relève des progressions, donc du suivi de classe : le jour
// d'évaluation de chaque classe dépend de son emploi du temps. Le service et
// ses routes restent pour le futur chantier « progressions » (ROADMAP), mais
// l'onglet Documents d'un principal au modèle Fiches ne montre plus le cadre
// et n'appelle plus /api/progression-rituels.

import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REF = readFileSync(join(__dirname, '..', 'static', 'atelier_referentiel.js'), 'utf-8');

describe('rituels hors de l\'atelier Référentiel (v0.60.2)', () => {
  it('onglet Documents d\'un principal Fiches : pas de cadre ni d\'appel des rituels', () => {
    document.body.innerHTML = '<div id="atl-ref-panneau-documents"></div>';
    const appels = [];
    const fauxFetch = async (url) => { appels.push(String(url));
      return { ok: true, json: async () => ({}) }; };
    // Même cas que l'ancien cadre (v0.60.0, P0) : principal, modèle Fiches, en cours.
    new Function('fetch', REF + `
      ATL_REF_SELECTION = { id: 'R', type_ref: 'principal', gabarit_documents: 'sixieme',
                            etat: 'en_cours' };
      ATL_REF_DOCUMENTS = [];
      atelRefRendreDocuments();`)(fauxFetch);   // eslint-disable-line no-new-func
    const h = document.getElementById('atl-ref-panneau-documents').innerHTML;
    expect(h).toContain('Documents à publier');            // l'onglet est bien rendu
    expect(h).not.toMatch(/Rituels d'automatismes/);
    expect(h).not.toMatch(/atl-ref-rituels/);
    expect(appels.filter(u => u.includes('progression-rituels'))).toEqual([]);
  });

  it('plus aucune fonction d\'interface des rituels dans l\'atelier', () => {
    expect(REF).not.toMatch(/function atelRefRituels/);
    expect(REF).not.toMatch(/[`'"]\/api\/progression-rituels/);   // URL construite (le commentaire la cite)
  });
});
