// tests_js/deux_parties_evaluation.test.js — v0.52.9
//
// Sujet en deux parties, façon DNB (décisions D1 et D4) :
//   - le bloc « Sujet en deux parties » n'apparaît que si le serveur le dit
//     (D1 : un exercice EV interdit la calculatrice, un autre l'autorise) ;
//   - la durée de la partie 1 est relue, la durée calculée sert d'indication
//     (champ vide = calcul automatique) ;
//   - la durée part avec les autres champs à l'enregistrement (sinon perdue).

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
    <label id="atl-eval-calculatrice-bloc"><select id="atl-eval-calculatrice">
      <option value="">selon les exercices</option><option value="interdite">interdite</option>
    </select><span id="atl-eval-calculatrice-indic"></span></label>
    <div id="atl-eval-calculatrice-avert" style="display:none"></div>
    <div id="atl-eval-deux-parties" style="display:none">
      <span id="atl-eval-deux-parties-detail"></span>
      <input type="number" id="atl-eval-duree-partie1">
    </div>`;
}

describe('sujet en deux parties (module Évaluations)', () => {
  let remplir;
  beforeEach(() => {
    dom();
    remplir = methode('_remplirCalculatrice');
  });

  it('D1 : bloc affiché avec la durée calculée en indication, champ vide = automatique', () => {
    remplir.call({ _estEval6e: () => true },
                 { calculatrice: '', calculatrice_exercices: 'autorisee',
                   deux_parties: true, duree_partie1: null, duree_partie1_auto: 20 });
    expect(document.getElementById('atl-eval-deux-parties').style.display).toBe('');
    const d = document.getElementById('atl-eval-duree-partie1');
    expect(d.value).toBe('');
    expect(d.placeholder).toBe('20');
    expect(document.getElementById('atl-eval-deux-parties-detail').textContent)
      .toContain('durée calculée : 20 min');
  });

  it('D4 : durée réglée relue', () => {
    remplir.call({ _estEval6e: () => true },
                 { deux_parties: true, duree_partie1: 25, duree_partie1_auto: 20 });
    expect(document.getElementById('atl-eval-duree-partie1').value).toBe('25');
  });

  it('sujet d\'un seul tenant ou cycle 4 : bloc masqué', () => {
    remplir.call({ _estEval6e: () => true }, { deux_parties: false });
    expect(document.getElementById('atl-eval-deux-parties').style.display).toBe('none');
    remplir.call({ _estEval6e: () => false }, { deux_parties: true });
    expect(document.getElementById('atl-eval-deux-parties').style.display).toBe('none');
  });

  it('la durée part avec les autres champs à l\'enregistrement', () => {
    expect(SRC).toMatch(/const elD = document\.getElementById\('atl-eval-duree-partie1'\);\n\s+if \(elD\) champs\.duree_partie1 = elD\.value\.trim\(\);/);
  });
});
