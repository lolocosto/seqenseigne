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

function charger() {
  window.escapeHtml = (s) => String(s).replace(/[&<>"']/g, c => `&#${c.charCodeAt(0)};`);
  window.ANNEE_ACTIVE = '2026-2027';
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
        { date: '2026-10-14', creneau: 'M2', classe_id: 'a', classe: '4EME3', type_mer: 'principale' },
        { date: '2026-10-14', creneau: 'M4', classe_id: 'b', classe: '6EME2', type_mer: 'mer_auto', indispo: true },
        { date: '2026-10-15', creneau: 'M1', classe_id: 'a', classe: '4EME3', type_mer: 'principale' },
      ],
    });
    const lignes = [...document.querySelectorAll('.tdb-jour-ligne')].map(l => l.querySelector('.tdb-jour-cr').textContent);
    expect(lignes).toEqual(['M2', 'M3', 'M4']);
    const seances = [...document.querySelectorAll('.tdb-jour-seance')].map(b => b.textContent.replace(/\s+/g, ' ').trim());
    expect(seances).toEqual(['4EME3', '6EME2 MER auto ⛔']);
    expect(document.getElementById('tdb-jour-lbl').textContent).toMatch(/^Mercredi 14\/10/);
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
