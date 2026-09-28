// tests_js/app_nettoyage_oo_exercice.test.js — v0.18.0.3
//
// Nettoyage du code procédural legacy de l'atelier Exercice dans app.js.
// La logique est portée par la classe AtelierExercice (atelier_exercice.js),
// qui expose des ponts window.atelExercice* / window.atelChargerExercices.
// Les anciennes `function atelExercice*` d'app.js étaient soit écrasées par
// ces ponts OO, soit plus appelées du tout → supprimées.
//
// Ce test garde la barrière : les fonctions mortes ne doivent plus être
// DÉFINIES dans app.js (sinon le code legacy réapparaît et diverge de l'OO),
// tandis que les fonctions encore propres à app.js doivent rester présentes.

import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const APP = readFileSync(join(__dirname, '..', 'static', 'app.js'), 'utf-8');

function estDefinie(nom) {
  // Cherche une définition `function nom(` ou `async function nom(`.
  return new RegExp(`^(?:async )?function ${nom}\\(`, 'm').test(APP);
}

describe('app.js — nettoyage OO exercice (v0.18.0.3)', () => {
  const mortes = [
    '_atelExerciceLireDom',
    'atelChargerExercices',
    'atelExerciceNouveau',
    'atelExerciceCharger',
    'atelExerciceSauvegarder',
    'atelExerciceSupprimer',
    'atelExerciceRemplir',
    'atelExerciceAfficherEditeur',
    'atelExerciceSerie',
    'atelExerciceMajVisibiliteRemediation',
    'atelExerciceToggleVariables',
    'atelExerciceToggleCadreReponsePrincipal',
    'atelExerciceToggleCadreReponseRemed',
    'atelExerciceTab',
  ];

  it('les fonctions exo legacy mortes ne sont plus définies dans app.js', () => {
    const survivantes = mortes.filter(estDefinie);
    expect(survivantes).toEqual([]);
  });

  const vivantes = [
    'atelExerciceFiltrer',
    'atelFiltrerAtomes',
    'atelObjLiesEnTags',
    'atelObjLiesBadgesHtml',
  ];

  it('les fonctions encore propres à app.js restent définies', () => {
    const manquantes = vivantes.filter((f) => !estDefinie(f));
    expect(manquantes).toEqual([]);
  });

  it('aucun appel de code aux symboles du système générique supprimé', () => {
    // On ignore les lignes de commentaire (// …) : seules les mentions de code
    // comptent. Les symboles d'ÉTAT encore vivants (atelAtomeFiltreEtat_OK,
    // atelAtomeBasculerValidation) sont volontairement exclus de cette liste.
    const codeSeul = APP.split('\n')
      .filter((l) => !l.trimStart().startsWith('//'))
      .join('\n');
    for (const sym of [
      'ATL_ATOME_CONFIG',
      'atelAtomeNouveau',
      'atelAtomeCharger',
      'atelAtomeSauvegarder',
      'atelAtomeSupprimer',
      'atelAtomeAfficherEditeur',
      'atelAtomeTabBasculer',
    ]) {
      expect(codeSeul).not.toMatch(new RegExp(`\\b${sym}\\b`));
    }
  });
});
