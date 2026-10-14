// tests_js/tdb_tuiles.test.js — v0.51.13
//
// Tuile « Journée » du tableau de bord : jours ouvrés (le week-end est
// sauté dans les deux sens), lundi de la semaine, rendu de la journée
// (créneaux occupés, vacances, férié) depuis les données de la planification
// hebdo.

import { describe, it, expect, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC = readFileSync(join(__dirname, '..', 'static', 'tdb_tuiles.js'), 'utf-8');
const PLANIF = readFileSync(join(__dirname, '..', 'static', 'planification_hebdo.js'), 'utf-8');

function charger() {
  window.escapeHtml = (s) => String(s).replace(/[&<>"']/g, c => `&#${c.charCodeAt(0)};`);
  window.ANNEE_ACTIVE = '2026-2027';
  // eslint-disable-next-line no-new-func
  new Function(PLANIF)();          // planifResumeLignes / planifResumeHtml (window)
  // eslint-disable-next-line no-new-func
  return new Function(SRC + `
    return { _tdbOuvre, _tdbLundi, _tdbDecaler, tdbRendreJournee,
             setJour: (j) => { TDB_JOUR = j; } };`)();
}

beforeEach(() => {
  document.body.innerHTML = `<span id="tdb-jour-lbl"></span>
    <button id="tdb-jour-prec"></button><button id="tdb-jour-suiv"></button>
    <div id="tdb-journee"></div>`;
});

describe('tuile Journée (v0.51.13)', () => {
  it('saute le week-end dans les deux sens', () => {
    const f = charger();
    expect(f._tdbOuvre('2026-10-17', 1)).toBe('2026-10-19');      // samedi → lundi
    expect(f._tdbOuvre('2026-10-18', -1)).toBe('2026-10-16');     // dimanche → vendredi
    expect(f._tdbOuvre('2026-10-14', 1)).toBe('2026-10-14');
    expect(f._tdbLundi('2026-10-16')).toBe('2026-10-12');
    expect(f._tdbDecaler('2026-10-31', 1)).toBe('2026-11-01');
  });

  it('rend les créneaux du jour, de la première à la dernière séance', () => {
    const f = charger();
    f.setJour('2026-10-14');
    f.tdbRendreJournee({
      creneaux: ['M1', 'M2', 'M3', 'M4', 'S1'],
      jours_info: [{ date: '2026-10-14', vacances: null, ferie: null }],
      cases: [
        { date: '2026-10-14', creneau: 'M2', classe_id: 'a', classe: '4EME3', type_mer: 'principale',
          resume: { mer: null, principale: { code: 'S03', nom: 'Fractions', partie: '2', rang: 3, nb: 5 },
                    docs: ['Fiche 1', 'DM'] } },
        { date: '2026-10-14', creneau: 'M4', classe_id: 'b', classe: '6EME2', type_mer: 'mer_auto', indispo: true,
          resume: { mer: { type: 'auto', enveloppes: [1, 3] }, principale: null, docs: [] } },
        { date: '2026-10-15', creneau: 'M1', classe_id: 'a', classe: '4EME3', type_mer: 'principale' },
      ],
    });
    const lignes = [...document.querySelectorAll('.tdb-jour-ligne')].map(l => l.querySelector('.tdb-jour-cr').textContent);
    expect(lignes).toEqual(['M2', 'M3', 'M4']);
    const seances = [...document.querySelectorAll('.tdb-jour-ouvrir')].map(b =>
      [...b.children].map(x => x.textContent.trim()));
    expect(seances).toEqual([
      ['4EME3', 'MER : aucune', 'Principale : S03 Fractions (partie 2) (3/5)', 'Docs : Fiche 1, DM'],
      ['6EME2 ⛔', 'MER : automatismes (1, 3)', 'Principale : aucune', 'Docs : aucun']]);
    expect(document.querySelectorAll('.tdb-jour-liens a').length).toBe(6);
    expect(document.getElementById('tdb-jour-lbl').textContent).toMatch(/^Mercredi 14\/10/);
  });

  it('résumé : MER de progression, partie unique, sans partie posée', () => {
    charger();
    const l = (resume) => window.planifResumeLignes({ resume }).map(x => x.texte);
    expect(l({ mer: { type: 'prog', partie: { libelle: 'Série 1', rang: 2, nb: 3 } },
               principale: { code: 'S01', nom: 'Nombres', partie: '', rang: 1, nb: 4 }, docs: [] }))
      .toEqual(['MER : Série 1 (2/3)', 'Principale : S01 Nombres (1/4)', 'Docs : aucun']);
    expect(l({ mer: { type: 'prog', partie: null }, principale: null, docs: [] })[0])
      .toBe('MER : progression (aucune partie posée)');
    expect(l({ mer: { type: 'auto', enveloppes: [] } })[0]).toBe('MER : automatismes');
  });

  it('jour de vacances, jour sans séance', () => {
    const f = charger();
    f.setJour('2026-10-21');
    f.tdbRendreJournee({ creneaux: ['M1'], cases: [],
      jours_info: [{ date: '2026-10-21', vacances: 'Vacances de la Toussaint' }] });
    expect(document.getElementById('tdb-journee').textContent).toContain('Vacances de la Toussaint');
    f.setJour('2026-10-13');
    f.tdbRendreJournee({ creneaux: ['M1'], cases: [], jours_info: [] });
    expect(document.getElementById('tdb-journee').textContent).toContain('Aucune séance');
  });

  it('bornes de l\'année scolaire', () => {
    const f = charger();
    f.setJour('2026-09-01');
    f.tdbRendreJournee({ creneaux: [], cases: [], jours_info: [] });
    expect(document.getElementById('tdb-jour-prec').disabled).toBe(true);
    expect(document.getElementById('tdb-jour-suiv').disabled).toBe(false);
  });
});
