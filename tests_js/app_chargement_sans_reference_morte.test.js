// tests_js/app_chargement_sans_reference_morte.test.js — v0.18.0 (correctif)
//
// Régression : un bloc top-level « ATL_ATOME_CONFIG.exercice.callbacks = {…} »
// était resté orphelin dans app.js après la suppression de
// atelier_atome_generique.js (v0.13.7.0c). ATL_ATOME_CONFIG n'existant plus,
// ce bloc levait un ReferenceError AU CHARGEMENT de app.js, interrompant
// l'évaluation du script : toutes les déclarations suivantes (dont
// `let COMPIL_PREVIEW_OK`) restaient en zone morte temporelle (TDZ), d'où
// l'erreur « can't access lexical declaration 'COMPIL_PREVIEW_OK' before
// initialization » au clic sur « Aperçu (compter) » du Rendu par lot.
//
// Ce test garde la barrière : aucune AFFECTATION/LECTURE top-level de
// ATL_ATOME_CONFIG ne doit subsister dans app.js (les mentions en commentaire
// sont tolérées). On vérifie aussi que la déclaration de COMPIL_PREVIEW_OK est
// présente (la variable doit exister pour le Rendu par lot).

import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const APP = readFileSync(join(__dirname, '..', 'static', 'app.js'), 'utf-8');

function lignesDeCode(src) {
  // Retire les lignes de commentaire ligne (// …) pour ne tester que le code.
  return src.split('\n')
    .filter(l => !l.trimStart().startsWith('//'))
    .join('\n');
}

describe('app.js — pas de référence morte au chargement (v0.18.0)', () => {
  it('aucune utilisation de code de ATL_ATOME_CONFIG (symbole supprimé)', () => {
    const code = lignesDeCode(APP);
    expect(code).not.toMatch(/ATL_ATOME_CONFIG/);
  });

  it('la variable COMPIL_PREVIEW_OK est bien déclarée', () => {
    expect(APP).toMatch(/\b(let|const|var)\s+COMPIL_PREVIEW_OK\b/);
  });
});
