// tests_js/atelier_progression.test.js — v0.19.1.0
//
// Tests de la classe AtelierProgression (refonte du panneau Progression en
// atelier d'assemblage OO). On vérifie le CONTRAT OO (héritage, config) et la
// LOGIQUE SYNCHRONE pure qui est le vrai risque de la migration :
//   - _semainesParPartie : calcul des numéros de semaine où chaque partie est
//     posée (base des badges de la barre latérale) ;
//   - _estModifiable : verrou d'édition (en_cours + académie présente).
//
// On ne teste PAS les méthodes réseau (fetch/api) : seulement la logique
// d'état. Les helpers calendrier purs (_lundisEntre, _bornesAnneeScolaire,
// _jourSemaine) vivent dans app.js ; on les redéfinit ici en stubs minimaux
// sur window (équivalents fonctionnels) pour isoler le test de la classe.

import { describe, it, expect, beforeAll, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

function charger(rel) {
  const code = readFileSync(join(__dirname, '..', 'static', rel), 'utf-8');
  // eslint-disable-next-line no-new-func
  new Function(code)();
}

let A; // instance window.ATELIER_PROGRESSION

beforeAll(() => {
  // Globals consommés par la classe (normalement fournis par app.js).
  globalThis.window.escapeHtml = (s) => String(s == null ? '' : s);
  globalThis.window.api = async () => ({});

  // Helpers calendrier purs (réimplémentation fidèle des fonctions d'app.js
  // dont la classe dépend via window.*). On garde la même sémantique.
  globalThis.window.MOIS_FR = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin',
    'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
  globalThis.window._dateToISO = (d) => {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const j = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${j}`;
  };
  globalThis.window._lundisEntre = (deb, fin) => {
    const d = new Date(deb + 'T00:00:00');
    const jour = d.getDay();
    const decalage = jour === 0 ? -6 : (1 - jour);
    d.setDate(d.getDate() + decalage);
    const f = new Date(fin + 'T00:00:00');
    const out = [];
    while (d <= f) { out.push(globalThis.window._dateToISO(d)); d.setDate(d.getDate() + 7); }
    return out;
  };
  globalThis.window._bornesAnneeScolaire = (annee) => {
    const [d, f] = annee.split('-').map(Number);
    return { debut: `${d}-09-01`, fin: `${f}-08-31` };
  };
  globalThis.window._jourSemaine = (lundiISO, offset) => {
    const d = new Date(lundiISO + 'T00:00:00');
    d.setDate(d.getDate() + offset);
    return globalThis.window._dateToISO(d);
  };

  // Chaîne d'héritage, dans l'ordre du index.html.
  charger('atelier.js');
  charger('atelier_editeur.js');
  charger('atelier_assemblage.js');
  charger('atelier_progression.js');

  A = globalThis.window.ATELIER_PROGRESSION;
});

describe('AtelierProgression — contrat OO', () => {
  it('expose une instance globale window.ATELIER_PROGRESSION', () => {
    expect(A).toBeTruthy();
    expect(A.constructor.name).toBe('AtelierProgression');
  });

  it("hérite d'AtelierAssemblage (donc AtelierEditeur, Atelier)", () => {
    expect(A instanceof globalThis.window.AtelierAssemblage).toBe(true);
    expect(A instanceof globalThis.window.Atelier).toBe(true);
  });

  it('est configuré non pluriel, persistance immédiate', () => {
    expect(A.id).toBe('prog');
    expect(A.estPluriel).toBe(false);
    expect(A.persistanceImmediate).toBe(true);
  });

  it('expose window.progInit branché sur init()', () => {
    expect(typeof globalThis.window.progInit).toBe('function');
  });

  it('modifie reste false (persistance immédiate)', () => {
    // Le getter d'AtelierAssemblage court-circuite quand persistanceImmediate.
    expect(A.modifie).toBe(false);
  });
});

describe('AtelierProgression._semainesParPartie', () => {
  beforeEach(() => {
    A.data = null;
  });

  it('retourne {} sans progression', () => {
    A.data = null;
    expect(A._semainesParPartie()).toEqual({});
  });

  it('crée une entrée vide pour un créneau non daté (posé, à dater)', () => {
    A.data = {
      annee: '2025-2026',
      creneaux: [
        { sequence: 'S01', partie_debut: 1, date_debut: null, date_fin: null },
      ],
    };
    // La partie est « posée » (clé présente) mais sans numéro de semaine.
    const map = A._semainesParPartie();
    expect(map['S01|1']).toEqual([]);
  });

  it('calcule le numéro de semaine d\'un créneau daté', () => {
    // 2025-2026 : l'année scolaire démarre au 1er sept. 2025 (lundi 1er sept).
    // Un créneau du 1er au 5 sept. 2025 doit tomber en semaine 1.
    A.data = {
      annee: '2025-2026',
      creneaux: [
        { sequence: 'S01', partie_debut: 1,
          date_debut: '2025-09-01', date_fin: '2025-09-05' },
      ],
    };
    const map = A._semainesParPartie();
    expect(map['S01|1']).toEqual([1]);
  });

  it('regroupe plusieurs semaines pour une même partie et dédoublonne', () => {
    A.data = {
      annee: '2025-2026',
      creneaux: [
        { sequence: 'S01', partie_debut: 1,
          date_debut: '2025-09-01', date_fin: '2025-09-05' },   // sem 1
        { sequence: 'S01', partie_debut: 1,
          date_debut: '2025-09-15', date_fin: '2025-09-19' },   // sem 3
      ],
    };
    const map = A._semainesParPartie();
    expect(map['S01|1']).toEqual([1, 3]);
  });

  it('utilise partie_debut quand partie est absente', () => {
    A.data = {
      annee: '2025-2026',
      creneaux: [
        { sequence: 'S02', partie_debut: 2,
          date_debut: '2025-09-01', date_fin: '2025-09-05' },
      ],
    };
    const map = A._semainesParPartie();
    expect(map['S02|2']).toEqual([1]);
  });
});

describe('AtelierProgression._estModifiable', () => {
  it('vrai si en_cours et académie présente', () => {
    A.data = { etat: 'en_cours', etab_academie: 'Lyon' };
    expect(A._estModifiable()).toBe(true);
  });

  it('faux si validée', () => {
    A.data = { etat: 'valide', etab_academie: 'Lyon' };
    expect(A._estModifiable()).toBe(false);
  });

  it('faux si verrouillée / utilisée', () => {
    A.data = { etat: 'verrouille', etab_academie: 'Lyon' };
    expect(A._estModifiable()).toBe(false);
  });

  it('faux si académie absente même en_cours', () => {
    A.data = { etat: 'en_cours', etab_academie: '' };
    expect(A._estModifiable()).toBe(false);
  });
});

describe('app.js — exposition des helpers calendrier sur window (v0.19.1.1)', () => {
  // Régression du crash « window.MOIS_FR is undefined » : AtelierProgression
  // (fichier séparé) consomme les helpers calendrier d'app.js via window.* ;
  // or `const MOIS_FR`/`function _lundisEntre` au top-level d'app.js ne sont
  // PAS des propriétés de window. app.js doit donc les ré-exposer nommément.
  const APP = readFileSync(join(__dirname, '..', 'static', 'app.js'), 'utf-8');

  const exposes = [
    'window.MOIS_FR', 'window._lundisEntre', 'window._bornesAnneeScolaire',
    'window._jourSemaine', 'window._dateCourte',
  ];
  for (const e of exposes) {
    it(`expose ${e}`, () => {
      expect(APP).toContain(`${e} `);
    });
  }
});

describe('AtelierProgression — séances par série (v0.19.1.4)', () => {
  beforeEach(() => {
    A.data = null;
    A._modeSeances = 'par_serie';
    A._seancesParSerie = [
      {seq_code:'S12', partie_numero:1, niveau_cible:'TB', serie:'R', nb_seances:1.0},
      {seq_code:'S12', partie_numero:1, niveau_cible:'TB', serie:'F', nb_seances:1.5},
      {seq_code:'S12', partie_numero:1, niveau_cible:'TB', serie:'A', nb_seances:2.0},
      {seq_code:'S12', partie_numero:1, niveau_cible:'TB', serie:'E', nb_seances:2.5},
      {seq_code:'S12', partie_numero:1, niveau_cible:'S',  serie:'R', nb_seances:1.5},
      {seq_code:'S12', partie_numero:1, niveau_cible:'S',  serie:'F', nb_seances:2.5},
      {seq_code:'S12', partie_numero:1, niveau_cible:'S',  serie:'A', nb_seances:3.0},
      {seq_code:'S12', partie_numero:2, niveau_cible:'TB', serie:'R', nb_seances:1.0},
    ];
  });

  it('_matricesSeances assemble TB et S pour la bonne partie', () => {
    const m = A._matricesSeances('S12', 1);
    expect(m.TB).toEqual({R:1.0, F:1.5, A:2.0, E:2.5});
    expect(m.S).toEqual({R:1.5, F:2.5, A:3.0});
  });

  it('_matricesSeances isole par partie', () => {
    const m = A._matricesSeances('S12', 2);
    expect(m.TB).toEqual({R:1.0});
    expect(m.S).toEqual({});
  });

  it('_matricesSeances vide pour une séquence inconnue', () => {
    const m = A._matricesSeances('S99', 1);
    expect(m.TB).toEqual({});
    expect(m.S).toEqual({});
  });

  it('_fmtSeances : entier sans décimale, sinon virgule', () => {
    expect(A._fmtSeances(2)).toBe('2');
    expect(A._fmtSeances(1.5)).toBe('1,5');
    expect(A._fmtSeances(2.5)).toBe('2,5');
  });
});

describe('AtelierProgression — masquage créneaux en vacances (v0.19.1.6)', () => {
  beforeEach(() => {
    // Un créneau qui enjambe les vacances de la Toussaint (semaine avant +
    // semaine après). Vacances : 23/10 (sam) → reprise 02/11/2020. La semaine
    // du lundi 26/10 est ENTIÈREMENT en vacances ; celle du 02/11 reprend.
    A.data = {
      annee: '2020-2021',
      creneaux: [
        { id:'c1', sequence:'S01', date_debut:'2020-10-19', date_fin:'2020-11-06' },
      ],
    };
    // Vacances de la Toussaint : du 17/10 au 02/11 (reprise = fin exclusive).
    A._calVacances = [
      { start_date:'2020-10-17', end_date:'2020-11-02', description:'Toussaint' },
    ];
    A._calFeries = {};
  });

  it('cache le créneau sur une semaine entièrement en vacances', () => {
    // Lundi 26/10/2020 → vendredi 30/10 : tous en vacances.
    expect(A._semaineEntierementEnVacances('2020-10-26')).toBe(true);
    expect(A._creneauxDeLaSemaine('2020-10-26')).toEqual([]);
  });

  it('affiche le créneau la semaine AVANT les vacances', () => {
    // Lundi 19/10 → vendredi 23/10 : jours de classe (vacances commencent
    // le 17 mais ce sont sam/dim ; lun-ven 19-23 sont travaillés… or 17/10
    // est un samedi, donc 19-23 sont DANS les vacances ? Non : start 17/10.
    // 19-23 oct >= 17/10 → en vacances. Donc cette semaine est aussi vacances.
    // On teste plutôt la semaine du 12/10 (avant vacances).
    expect(A._semaineEntierementEnVacances('2020-10-12')).toBe(false);
    const cr = A._creneauxDeLaSemaine('2020-10-12');
    // Le créneau démarre le 19 : il ne couvre pas la semaine du 12.
    expect(cr.length).toBe(0);
  });

  it('affiche le créneau la semaine de reprise (02/11)', () => {
    // Lundi 02/11 = reprise (fin exclusive) → jours de classe.
    expect(A._semaineEntierementEnVacances('2020-11-02')).toBe(false);
    const cr = A._creneauxDeLaSemaine('2020-11-02');
    expect(cr.map(c => c.id)).toEqual(['c1']);
  });

  it('un jour férié seul ne rend pas la semaine « entièrement en vacances »', () => {
    // Semaine sans vacances mais avec un férié (11/11/2020, mercredi).
    A._calVacances = [];
    A._calFeries = { '2020-11-11': 'Armistice' };
    A.data.creneaux = [
      { id:'c2', sequence:'S02', date_debut:'2020-11-09', date_fin:'2020-11-13' },
    ];
    expect(A._semaineEntierementEnVacances('2020-11-09')).toBe(false);
    expect(A._creneauxDeLaSemaine('2020-11-09').map(c => c.id)).toEqual(['c2']);
  });

  it('_jourEnVacances respecte la fin exclusive (jour de reprise exclu)', () => {
    A._calVacances = [
      { start_date:'2020-10-17', end_date:'2020-11-02', description:'T' },
    ];
    expect(A._jourEnVacances('2020-10-17')).toBe(true);   // début inclus
    expect(A._jourEnVacances('2020-11-01')).toBe(true);   // avant reprise
    expect(A._jourEnVacances('2020-11-02')).toBe(false);  // reprise exclue
  });
});
