// tests_js/mer_rendu_selecteurs.test.js — v0.53.3
//
// Onglet « Rendu PDF » d'une mise en route (Laurent, 25 octobre 2026) :
//   - D-SEL : seuls les sélecteurs qui ont un sens pour le document choisi
//     sont affichés (table SeqnivPur.SELECTEURS_DOCUMENT_MER, même table que
//     le serveur, comparée par tests/test_v0_53_3_rendu_mer.py) ;
//   - Test n° borné de 1 au nombre de tests de la partie (ou de la séquence) ;
//   - D-TOUT : bouton « Tout compiler » et liste des statuts (lien vers le log).

import { describe, it, expect, beforeAll } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const lire = rel => readFileSync(join(__dirname, '..', rel), 'utf-8');
function charger(rel) { new Function(lire(join('static', rel)))(); }   // eslint-disable-line no-new-func

const RESUME = { parties: [
  { numero: 1, tests: [{ numero: 11 }] },
  { numero: 2, tests: [{ numero: 12 }, { numero: 13 }] },
  { numero: 3, tests: [] }] };

describe('D-SEL, test n° borné, Tout compiler', () => {
  let A, P;
  beforeAll(() => {
    globalThis.window.atelGardeEnregistrer = globalThis.window.atelGardeEnregistrer || (() => {});
    charger('atelier.js');
    charger('atelier_editeur.js');
    charger('atelier_assemblage.js');
    charger('seqniv_pur.js');
    charger('atelier_seqniv_assemblage.js');
    A = globalThis.window.ATELIER_SEQNIV;
    P = globalThis.window.SeqnivPur;
  });

  it('table document → sélecteurs : test n° et sujet pour le test court seulement, Par A4 pour la planche', () => {
    expect(P.selecteursVisiblesMer('test_court'))
      .toEqual({ version: true, par_page: false, exemplaires: true, test: true, sujet: true });
    expect(P.selecteursVisiblesMer('planche'))
      .toEqual({ version: true, par_page: true, exemplaires: false, test: false, sujet: false });
    expect(P.selecteursVisiblesMer('fiche_cours'))
      .toEqual({ version: true, par_page: false, exemplaires: true, test: false, sujet: false });
    expect(P.selecteursVisiblesMer('activite').version).toBe(true);
    for (const d of ['plan', 'dossier'])                  // une seule version
      expect(Object.values(P.selecteursVisiblesMer(d)).some(Boolean)).toBe(false);
  });

  it('chaque document de la liste « Document » a sa ligne dans la table', () => {
    const code = lire('static/atelier_seqniv_assemblage.js');
    const debut = code.indexOf('id="livret-seq-mer-document"');
    const liste = code.slice(debut, code.indexOf('</select>', debut));
    const valeurs = [...liste.matchAll(/option value="([a-z_]+)"/g)].map(m => m[1]);
    expect(valeurs.sort()).toEqual(Object.keys(P.SELECTEURS_DOCUMENT_MER).sort());
  });

  it('le changement de document masque les sélecteurs inutiles', () => {
    A.data = { sequence_par_niveau: { niveau: 'N09', sequence_code: 'M01' } };
    A._resumeMer = RESUME;
    document.body.innerHTML =
      '<select id="livret-seq-mer-document"><option value="plan" selected>p</option></select>'
      + '<select id="livret-seq-mer-partie"><option value="2" selected>2</option></select>'
      + P.SELECTEURS_MER.map(k => `<label id="livret-seq-mer-lbl-${k}">${k}</label>`).join('')
      + '<input id="livret-seq-mer-test" value="5">';
    A._majSelecteursMer();
    for (const k of P.SELECTEURS_MER)
      expect(document.getElementById('livret-seq-mer-lbl-' + k).style.display).toBe('none');
    document.getElementById('livret-seq-mer-document').innerHTML = '<option value="test_court" selected>t</option>';
    A._majSelecteursMer();
    expect(document.getElementById('livret-seq-mer-lbl-test').style.display).toBe('');
    expect(document.getElementById('livret-seq-mer-lbl-par_page').style.display).toBe('none');
    const t = document.getElementById('livret-seq-mer-test');
    expect(t.value).toBe('2');                           // 5 ramené au max (2 tests en partie 2)
    expect(t.max).toBe('2');
  });

  it('test n° : min 1, max = nombre de tests de la partie ou de la séquence', () => {
    expect(P.nbTestsMer(RESUME, '1')).toBe(1);
    expect(P.nbTestsMer(RESUME, '')).toBe(3);
    expect(P.nbTestsMer(RESUME, '3')).toBe(0);
    expect(P.bornerTestMer('0', 3)).toBe(1);
    expect(P.bornerTestMer('-4', 3)).toBe(1);
    expect(P.bornerTestMer('abc', 3)).toBe(1);
    expect(P.bornerTestMer('7', 3)).toBe(3);
    expect(P.bornerTestMer('2', 3)).toBe(2);
    expect(P.bornerTestMer('2', 0)).toBe(1);             // partie sans test : 1
  });

  it('les options envoyées portent un test n° dans les bornes', () => {
    A._resumeMer = RESUME;
    document.body.innerHTML =
      '<select id="livret-seq-mer-document"><option value="test_court" selected>t</option></select>'
      + '<select id="livret-seq-mer-partie"><option value="1" selected>1</option></select>'
      + '<input id="livret-seq-mer-test" value="4">';
    expect(A._livretSeqOptions().mer.test).toBe('1');
  });

  it('Tout compiler : bouton présent, statut d\'échec avec lien vers le log', () => {
    expect(lire('static/atelier_seqniv_assemblage.js')).toMatch(/merToutCompiler\(\)[^]*Tout compiler/);
    const ok = P.htmlStatutToutCompiler({ kind: 'document', index: 1, total: 2,
                                          nom: 'M01_p1_plan.pdf', statut: 'cache' });
    expect(ok).toMatch(/succès \(cache\)/);
    const ko = P.htmlStatutToutCompiler({ kind: 'document', index: 2, total: 2,
                                          nom: 'M01_p1_dossier_enseignant.pdf', statut: 'echec',
                                          message: 'Undefined <x>', log: 'M01_p1_dossier_enseignant.log' });
    expect(ko).toMatch(/échec/);
    expect(ko).toMatch(/href="\/api\/v2\/livret-sequence\/mer\/echec\/M01_p1_dossier_enseignant\.log"/);
    expect(ko).toContain('Undefined &lt;x&gt;');
    expect(P.htmlStatutToutCompiler({ kind: 'fin' })).toBe('');
  });
});
