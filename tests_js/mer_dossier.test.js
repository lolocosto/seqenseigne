// tests_js/mer_dossier.test.js — v0.53.2
//
// Mises en route (décisions du 25 octobre 2026) côté interface :
//   - D-DOS : l'onglet « Rendu PDF » d'une séquence Mnn propose le dossier
//     enseignant (fusion du plan de la partie, de la fiche complète et des
//     corrigés, demandée par Laurent) en plus des documents existants ;
//   - D-AC : il propose aussi les activités complémentaires, et le contrôle
//     les affiche sans les compter (hors contrôle MR6).

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

describe('D-DOS et D-AC : onglet Rendu PDF d\'une mise en route', () => {
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

  it('le dossier enseignant s\'ajoute aux documents existants, qui restent', () => {
    const code = lire('static/atelier_seqniv_assemblage.js');
    const debut = code.indexOf('id="livret-seq-mer-document"');
    const liste = code.slice(debut, code.indexOf('</select>', debut));
    const valeurs = [...liste.matchAll(/option value="([a-z_]+)"/g)].map(m => m[1]);
    expect(valeurs).toEqual(['fiche_cours', 'planche', 'test_court', 'plan', 'dossier', 'activite']);
  });

  it('le document choisi part avec les options (dossier enseignant d\'une partie)', () => {
    A.data = { sequence_par_niveau: { niveau: 'N09', sequence_code: 'M04' } };
    document.body.innerHTML =
      '<select id="livret-seq-mer-document"><option value="dossier" selected>d</option></select>'
      + '<select id="livret-seq-mer-partie"><option value="3" selected>3</option></select>';
    const o = A._livretSeqOptions().mer;
    expect(o.document).toBe('dossier');
    expect(o.partie).toBe('3');
  });

  it('les activités complémentaires sont affichées par partie mais hors contrôle', () => {
    const h = A._htmlControleMer({
      code: 'M04', parties: [{ numero: 3, titre: 'Partie 3 --- Cercle', objectifs: ['M04-22'],
                               exercices: 5, seances: 5, tests: [{ numero: 41, titre: 'T' }],
                               fiche: 'Cercle', activites: [{ code: 'AC01', titre: 'Roue' }] }],
      validation: { valide: true, erreurs: [], avertissements: [], parties: {} } });
    expect(h).toMatch(/complète/);
    expect(h).toMatch(/1 activité\(s\) complémentaire\(s\) \(hors contrôle\)/);
  });
});
