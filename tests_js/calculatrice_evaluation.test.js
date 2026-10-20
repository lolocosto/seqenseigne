// tests_js/calculatrice_evaluation.test.js — v0.52.8
//
// Réglage « Calculatrice » du module Évaluations (décisions C1 et C3) :
//   - le réglage est lu et envoyé à l'enregistrement (sinon il serait perdu) ;
//   - un réglage contraire aux exercices affiche l'avertissement du serveur,
//     sans changer la valeur choisie par l'enseignant ;
//   - le réglage n'a pas de sens pour une évaluation du cycle 4 : masqué.

import { describe, it, expect, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC = readFileSync(join(__dirname, '..', 'static', 'atelier_evaluation_oo.js'), 'utf-8');

function methode(nom) {
  const m = SRC.match(new RegExp(`\\n  ${nom}\\(ev\\) \\{[\\s\\S]*?\\n  \\}\\n`));
  if (!m) throw new Error(`${nom} introuvable`);
  const corps = m[0].trim().replace(new RegExp(`^${nom}\\(ev\\) \\{`), '').replace(/\}$/, '');
  return new Function('ev', corps);
}

function dom() {
  document.body.innerHTML = `
    <label id="atl-eval-calculatrice-bloc">
      <select id="atl-eval-calculatrice">
        <option value="">selon les exercices</option>
        <option value="interdite">interdite</option>
        <option value="autorisee">autorisée</option>
        <option value="non_precisee">non précisée</option>
      </select>
      <span id="atl-eval-calculatrice-indic"></span>
    </label>
    <div id="atl-eval-calculatrice-avert" style="display:none"></div>`;
}

describe('réglage Calculatrice de l\'évaluation', () => {
  let remplir;
  beforeEach(() => {
    dom();
    remplir = methode('_remplirCalculatrice');
  });

  it('6e : valeur relue, règle des exercices rappelée, pas d\'avertissement si cohérent', () => {
    remplir.call({ _estEval6e: () => true },
                 { calculatrice: '', calculatrice_exercices: 'autorisee',
                   calculatrice_avertissement: '' });
    expect(document.getElementById('atl-eval-calculatrice').value).toBe('');
    expect(document.getElementById('atl-eval-calculatrice-indic').textContent)
      .toBe('(exercices : autorisée)');
    expect(document.getElementById('atl-eval-calculatrice-avert').style.display).toBe('none');
  });

  it('C3 : réglage contraire aux exercices signalé, sans écraser le réglage', () => {
    const msg = 'Calculatrice réglée « interdite » à la main…';
    remplir.call({ _estEval6e: () => true },
                 { calculatrice: 'interdite', calculatrice_exercices: 'autorisee',
                   calculatrice_avertissement: msg });
    expect(document.getElementById('atl-eval-calculatrice').value).toBe('interdite');
    const av = document.getElementById('atl-eval-calculatrice-avert');
    expect(av.textContent).toBe(msg);
    expect(av.style.display).toBe('');
  });

  it('cycle 4 : réglage masqué et aucun avertissement', () => {
    remplir.call({ _estEval6e: () => false },
                 { calculatrice: 'interdite', calculatrice_avertissement: 'x' });
    expect(document.getElementById('atl-eval-calculatrice-bloc').style.display).toBe('none');
    expect(document.getElementById('atl-eval-calculatrice-avert').style.display).toBe('none');
  });

  it('le réglage part avec les autres champs à l\'enregistrement', () => {
    expect(SRC).toMatch(/const elK = document\.getElementById\('atl-eval-calculatrice'\);\n\s+if \(elK\) champs\.calculatrice = elK\.value;/);
    expect(SRC).toMatch(/this\.itemActif = data\.evaluation;\n\s+\/\/ v0\.52\.8 \(C3\)[^\n]*\n\s+this\._remplirCalculatrice\(this\.itemActif\);/);
  });
});
