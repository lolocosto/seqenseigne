// tests_js/atelier_seqniv_assemblage.test.js — v0.16.7
//
// Tests de la classe AtelierSeqnivAssemblage (migration OO du seqniv).
// Groupes B/C du cadrage : registre du drag-and-drop (transitions de l'état
// this._drag) et aiguillage des 3 modes de sidebar.
//
// Les classes du projet sont des scripts classiques qui s'exposent sur
// window.* ; on charge toute la chaîne d'héritage dans le contexte jsdom
// (atelier.js → atelier_editeur.js → atelier_assemblage.js → seqniv_pur.js →
// atelier_seqniv_assemblage.js), puis on instancie. L'instanciation est
// DOM-free (les constructeurs ne touchent pas au DOM), donc sûre ici.
//
// On ne teste PAS les méthodes réseau (fetch) : seulement la logique
// synchrone d'état et d'aiguillage, qui est le risque réel de la migration
// structurelle (cf. cadrage §6 : « le registre DnD et les transitions de
// sidebar sont les zones à filet »).

import { describe, it, expect, beforeAll, beforeEach, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

function charger(rel) {
  const code = readFileSync(join(__dirname, '..', 'static', rel), 'utf-8');
  // eslint-disable-next-line no-new-func
  new Function(code)();
}

let A; // instance window.ATELIER_SEQNIV

beforeAll(() => {
  // Stubs de globals référencés par les wrappers / hooks au chargement.
  // (atelGardeEnregistrer n'est PAS appelé par le seqniv — pas besoin de stub,
  // mais on le pose au cas où une dépendance future l'exigerait.)
  globalThis.window.atelGardeEnregistrer = globalThis.window.atelGardeEnregistrer || (() => {});

  // Chaîne d'héritage, dans l'ordre du index.html.
  charger('atelier.js');
  charger('atelier_editeur.js');
  charger('atelier_assemblage.js');
  charger('seqniv_pur.js');
  charger('atelier_seqniv_assemblage.js');

  A = globalThis.window.ATELIER_SEQNIV;
});

describe('AtelierSeqnivAssemblage — instanciation & contrat OO', () => {
  it('expose une instance globale window.ATELIER_SEQNIV', () => {
    expect(A).toBeTruthy();
    expect(A.constructor.name).toBe('AtelierSeqnivAssemblage');
  });

  it("hérite d'AtelierAssemblage (donc d'AtelierEditeur, Atelier)", () => {
    expect(A instanceof globalThis.window.AtelierAssemblage).toBe(true);
    expect(A instanceof globalThis.window.Atelier).toBe(true);
  });

  it('est configuré en régime mixte (non immédiat), non pluriel', () => {
    expect(A.id).toBe('seqniv');
    expect(A.prefixe).toBe('liv-atl');
    // v0.16.9 — régime MIXTE : les champs de saisie de l'objectif ouvert
    // sont bufferisés (persistanceImmediate=false), la structure reste
    // immédiate.
    expect(A.persistanceImmediate).toBe(false);
    expect(A.estPluriel).toBe(false);
  });

  it('modifie est false quand aucun objectif n\'est ouvert', () => {
    // collecterFormulaire() renvoie null sans objectif ouvert (pas de form),
    // donc le snapshot ne marque rien comme modifié.
    A.objOuvert = null;
    expect(A.modifie).toBe(false);
  });

  it('collecterFormulaire renvoie null sans objectif ouvert', () => {
    A.objOuvert = null;
    expect(A.collecterFormulaire()).toBeNull();
  });

  it('conserve le hook public window.seqnivAssemblageRafraichir', () => {
    expect(typeof globalThis.window.seqnivAssemblageRafraichir).toBe('function');
  });

  it('expose les wrappers atelSeqniv* (style atelEval*)', () => {
    expect(typeof globalThis.window.atelSeqnivBasculerOnglet).toBe('function');
    expect(typeof globalThis.window.atelSeqnivDropMethode).toBe('function');
    expect(typeof globalThis.window.atelSeqnivLivretGenererPdf).toBe('function');
  });
});

describe('AtelierSeqnivAssemblage — registre DnD (this._drag)', () => {
  beforeEach(() => {
    A._drag = null;
  });

  function evtFactice() {
    // Event minimal : dataTransfer + target avec classList.
    return {
      dataTransfer: { effectAllowed: '', setData() {}, dropEffect: '' },
      target: { classList: { add() {}, remove() {} } },
      currentTarget: null,
      stopPropagation() {},
      preventDefault() {},
    };
  }

  it('dragStartMethode arme un payload {kind:"methode"}', () => {
    A.dragStartMethode(evtFactice(), 'M1', 'Libellé M');
    expect(A._drag).toEqual({kind: 'methode', methode_id: 'M1', libelle: 'Libellé M'});
  });

  it('dragStartObj arme {kind:"obj"}', () => {
    A.dragStartObj(evtFactice(), 'O42');
    expect(A._drag).toEqual({kind: 'obj', obj_id: 'O42'});
  });

  it('dragStartPartie arme {kind:"partie"}', () => {
    A.dragStartPartie(evtFactice(), 'P7');
    expect(A._drag).toEqual({kind: 'partie', partie_id: 'P7'});
  });

  it('dragStartExoRA arme {kind:"exo_ra_existant"} avec type', () => {
    A.dragStartExoRA(evtFactice(), 'P1', 'R', 'E9');
    expect(A._drag).toEqual({kind: 'exo_ra_existant', partie_id: 'P1', type: 'R', exo_id: 'E9'});
  });

  it('dragStartFromSidebar lit le payload JSON du dataset', () => {
    const ev = evtFactice();
    ev.currentTarget = {
      dataset: { dragPayload: JSON.stringify({kind: 'notion', notion_id: 'N3', libelle: 'Aire'}) },
      getAttribute() { return null; },
      classList: { add() {} },
    };
    A.dragStartFromSidebar(ev);
    expect(A._drag).toEqual({kind: 'notion', notion_id: 'N3', libelle: 'Aire'});
  });

  it('dragStartFromSidebar ignore un payload illisible (reste null)', () => {
    const ev = evtFactice();
    ev.currentTarget = {
      dataset: { dragPayload: '{pas du json' },
      getAttribute() { return null; },
      classList: { add() {} },
    };
    A.dragStartFromSidebar(ev);
    expect(A._drag).toBeNull();
  });

  it('dragEnd réinitialise this._drag à null', () => {
    A._drag = {kind: 'obj', obj_id: 'X'};
    A.dragEnd(evtFactice());
    expect(A._drag).toBeNull();
  });
});

describe('AtelierSeqnivAssemblage — filtre d\'autorisation dragOver', () => {
  // dragOver(ev, zone) appelle ev.preventDefault() UNIQUEMENT si le couple
  // (type de drag, type de zone) est autorisé. On observe l'appel à
  // preventDefault comme proxy de « drop autorisé ».
  function zone(attrs) {
    return { dataset: attrs, classList: { add() {}, remove() {} } };
  }
  function ev() {
    let prevented = false;
    return {
      _prevented: () => prevented,
      preventDefault() { prevented = true; },
      dataTransfer: { dropEffect: '' },
    };
  }

  it('méthode → zone methode : autorisé', () => {
    A._drag = {kind: 'methode', methode_id: 'M'};
    const e = ev();
    A.dragOver(e, zone({zone: 'methode'}));
    expect(e._prevented()).toBe(true);
  });

  it('méthode → zone R : refusé', () => {
    A._drag = {kind: 'methode', methode_id: 'M'};
    const e = ev();
    A.dragOver(e, zone({zone: 'R'}));
    expect(e._prevented()).toBe(false);
  });

  it('exo_catalogue série R → zone R : autorisé', () => {
    A._drag = {kind: 'exo_catalogue', serie: 'R', exo_id: 'E'};
    const e = ev();
    A.dragOver(e, zone({zone: 'R'}));
    expect(e._prevented()).toBe(true);
  });

  it('exo_catalogue série F → zone série F d\'un objectif : autorisé', () => {
    A._drag = {kind: 'exo_catalogue', serie: 'F', exo_id: 'E'};
    const e = ev();
    A.dragOver(e, zone({serie: 'F'}));
    expect(e._prevented()).toBe(true);
  });

  it('exo_catalogue série F → zone série A : refusé (mauvaise série)', () => {
    A._drag = {kind: 'exo_catalogue', serie: 'F', exo_id: 'E'};
    const e = ev();
    A.dragOver(e, zone({serie: 'A'}));
    expect(e._prevented()).toBe(false);
  });

  it('notion → zone notion-obj : autorisé', () => {
    A._drag = {kind: 'notion', notion_id: 'N'};
    const e = ev();
    A.dragOver(e, zone({zone: 'notion-obj'}));
    expect(e._prevented()).toBe(true);
  });

  it('fiche → zone fiche-obj : autorisé', () => {
    A._drag = {kind: 'fiche', fiche_id: 'F'};
    const e = ev();
    A.dragOver(e, zone({zone: 'fiche-obj'}));
    expect(e._prevented()).toBe(true);
  });

  it('aucun drag en cours : refusé (no-op)', () => {
    A._drag = null;
    const e = ev();
    A.dragOver(e, zone({zone: 'methode'}));
    expect(e._prevented()).toBe(false);
  });
});

describe('AtelierSeqnivAssemblage — aiguillage des 3 modes de sidebar', () => {
  // _rendreSidebar() choisit, selon this.objOuvert et le code de l'objectif,
  // l'une des 3 méthodes de rendu. On espionne ces 3 méthodes pour vérifier
  // que la bonne est appelée, sans exécuter leur logique réseau.
  beforeEach(() => {
    // Stub des éléments DOM lus par _rendreSidebar (sidebarBody) et des 3
    // méthodes de rendu.
    document.body.innerHTML = '<div id="liv-atl-sidebar-body"></div>';
  });

  function dataAvecObjConnaitre() {
    // Partie numero=1 ⇒ codeConnaitre = "01". L'objectif "01" est le Cours.
    return {
      sequence_par_niveau: {id: 'SN', niveau: 'N10', sequence_code: 'S01'},
      parties: [
        {id: 'P1', numero: 1, objectifs: [
          {id: 'OC', code: '01', nom: 'Cours'},
          {id: 'OE', code: '02', nom: 'Exo'},
        ]},
      ],
    };
  }

  it('objOuvert=null ⇒ mode 1 (objets fermés)', () => {
    A.data = dataAvecObjConnaitre();
    A.objOuvert = null;
    const m1 = vi.spyOn(A, '_rendreSidebarObjsFermes').mockImplementation(() => {});
    const m2 = vi.spyOn(A, '_rendreSidebarObjExoOuvert').mockImplementation(() => {});
    const m3 = vi.spyOn(A, '_rendreSidebarObjConnaitreOuvert').mockImplementation(() => {});
    A._rendreSidebar();
    expect(m1).toHaveBeenCalledOnce();
    expect(m2).not.toHaveBeenCalled();
    expect(m3).not.toHaveBeenCalled();
    m1.mockRestore(); m2.mockRestore(); m3.mockRestore();
  });

  it('objectif "exo" ouvert ⇒ mode 2', () => {
    A.data = dataAvecObjConnaitre();
    A.objOuvert = 'OE'; // code 02, pas le Cours
    const m1 = vi.spyOn(A, '_rendreSidebarObjsFermes').mockImplementation(() => {});
    const m2 = vi.spyOn(A, '_rendreSidebarObjExoOuvert').mockImplementation(() => {});
    const m3 = vi.spyOn(A, '_rendreSidebarObjConnaitreOuvert').mockImplementation(() => {});
    A._rendreSidebar();
    expect(m2).toHaveBeenCalledOnce();
    expect(m1).not.toHaveBeenCalled();
    expect(m3).not.toHaveBeenCalled();
    m1.mockRestore(); m2.mockRestore(); m3.mockRestore();
  });

  it('objectif "Connaître" (code 01) ouvert ⇒ mode 3', () => {
    A.data = dataAvecObjConnaitre();
    A.objOuvert = 'OC'; // code 01 = Cours/Connaître pour partie numero=1
    const m1 = vi.spyOn(A, '_rendreSidebarObjsFermes').mockImplementation(() => {});
    const m2 = vi.spyOn(A, '_rendreSidebarObjExoOuvert').mockImplementation(() => {});
    const m3 = vi.spyOn(A, '_rendreSidebarObjConnaitreOuvert').mockImplementation(() => {});
    A._rendreSidebar();
    expect(m3).toHaveBeenCalledOnce();
    expect(m1).not.toHaveBeenCalled();
    expect(m2).not.toHaveBeenCalled();
    m1.mockRestore(); m2.mockRestore(); m3.mockRestore();
  });

  it('objOuvert pointant un id inconnu ⇒ retombe en mode 1', () => {
    A.data = dataAvecObjConnaitre();
    A.objOuvert = 'INCONNU';
    const m1 = vi.spyOn(A, '_rendreSidebarObjsFermes').mockImplementation(() => {});
    A._rendreSidebar();
    expect(m1).toHaveBeenCalledOnce();
    m1.mockRestore();
  });
});

describe('AtelierSeqnivAssemblage — délégation à SeqnivPur (état d\'instance)', () => {
  it('_sn() lit this.data.sequence_par_niveau', () => {
    A.data = {sequence_par_niveau: {id: 'Z', niveau: 'N11'}};
    expect(A._sn()).toEqual({id: 'Z', niveau: 'N11'});
    A.data = null;
    expect(A._sn()).toBeNull();
  });

  it('_trouverObj délègue à SeqnivPur sur this.data', () => {
    A.data = {parties: [{id: 'P', objectifs: [{id: 'O1', code: '02'}]}]};
    const o = A._trouverObj('O1');
    expect(o).toBeTruthy();
    expect(o.code).toBe('02');
  });
});

describe('AtelierSeqnivAssemblage — editerAtome : clic simple vs Ctrl+clic (v0.18.2.1)', () => {
  beforeEach(() => {
    // Séquence courante de l'assemblage, source par défaut de niveau/seq.
    A.data = {sequence_par_niveau: {niveau: 'N10', sequence_code: 'S01'}};
    globalThis.window.compilBatchOuvrirAtelier = vi.fn();
    // deeplinkAtomeURL : reproduction fidèle du helper d'app.js (non chargé
    // ici), suffisante pour le routage.
    globalThis.window.deeplinkAtomeURL = vi.fn((type, id, niv, seq) => {
      if (!id || !niv || !seq) return null;
      const atelier = (type === 'carte') ? 'carte_automatisme' : type;
      return `/?atelier=${atelier}&niveau=${niv}&seq=${seq}&atome=${id}`;
    });
    globalThis.window.open = vi.fn();
  });

  it('clic simple : ouvre EN PLACE (compilBatchOuvrirAtelier), pas window.open', () => {
    const ev = {ctrlKey: false, metaKey: false, shiftKey: false, button: 0,
                preventDefault: vi.fn()};
    A.editerAtome('notion', 'no_1', ev);
    expect(globalThis.window.compilBatchOuvrirAtelier)
      .toHaveBeenCalledWith('notion', 'no_1', 'N10', 'S01');
    expect(globalThis.window.open).not.toHaveBeenCalled();
  });

  it('Ctrl+clic : ouvre un NOUVEL ONGLET (window.open), pas en place', () => {
    const ev = {ctrlKey: true, preventDefault: vi.fn(), button: 0};
    A.editerAtome('notion', 'no_1', ev);
    expect(globalThis.window.open).toHaveBeenCalledWith(
      '/?atelier=notion&niveau=N10&seq=S01&atome=no_1', '_blank', 'noopener');
    expect(globalThis.window.compilBatchOuvrirAtelier).not.toHaveBeenCalled();
    expect(ev.preventDefault).toHaveBeenCalled();
  });

  it('⌘+clic (metaKey) : nouvel onglet', () => {
    const ev = {metaKey: true, preventDefault: vi.fn()};
    A.editerAtome('exercice', 'ex_1', ev);
    expect(globalThis.window.open).toHaveBeenCalledWith(
      '/?atelier=exercice&niveau=N10&seq=S01&atome=ex_1', '_blank', 'noopener');
  });

  it('clic-molette (button 1) : nouvel onglet', () => {
    const ev = {button: 1, preventDefault: vi.fn()};
    A.editerAtome('methode', 'me_1', ev);
    expect(globalThis.window.open).toHaveBeenCalled();
  });

  it('niveau/sequence explicites priment sur la séquence courante (exo de Révision)', () => {
    const ev = {ctrlKey: true, preventDefault: vi.fn()};
    A.editerAtome('exercice', 'ex_R', ev, 'N09', 'S03');
    expect(globalThis.window.open).toHaveBeenCalledWith(
      '/?atelier=exercice&niveau=N09&seq=S03&atome=ex_R', '_blank', 'noopener');
  });

  it('appel programmatique (sans event) : ouverture en place', () => {
    A.editerAtome('notion', 'no_2');
    expect(globalThis.window.compilBatchOuvrirAtelier)
      .toHaveBeenCalledWith('notion', 'no_2', 'N10', 'S01');
    expect(globalThis.window.open).not.toHaveBeenCalled();
  });

  it('editerFiche route via editerAtome (type fiche)', () => {
    const ev = {ctrlKey: true, preventDefault: vi.fn()};
    A.editerFiche('fi_1', ev);
    expect(globalThis.window.open).toHaveBeenCalledWith(
      '/?atelier=fiche&niveau=N10&seq=S01&atome=fi_1', '_blank', 'noopener');
  });

  it('Ctrl+clic sans niveau/seq dérivable : retombe sur ouverture en place', () => {
    A.data = null;  // pas de séquence courante
    const ev = {ctrlKey: true, preventDefault: vi.fn()};
    A.editerAtome('notion', 'no_3', ev);  // niveau/seq vides → URL null
    expect(globalThis.window.open).not.toHaveBeenCalled();
    expect(globalThis.window.compilBatchOuvrirAtelier)
      .toHaveBeenCalledWith('notion', 'no_3', '', '');
  });
});

describe('AtelierSeqnivAssemblage — unification série approche AE (v0.18.3)', () => {
  // dragOver autorise le drop (preventDefault + classe) si la combinaison
  // zone/drag est valide. On vérifie le DÉCOUPLAGE rôle/série : la dropzone
  // de RÔLE 'EA' (approche) accepte un exo catalogue de SÉRIE 'AE'.
  function faireZone(zoneRole) {
    return { dataset: { zone: zoneRole }, classList: { add() {} } };
  }
  function faireEvent() {
    return { preventDefault: vi.fn(), dataTransfer: {} };
  }

  it('dropzone rôle EA accepte un drag de série AE (convention unifiée)', () => {
    A._drag = { kind: 'exo_catalogue', serie: 'AE' };
    const ev = faireEvent();
    A.dragOver(ev, faireZone('EA'));
    expect(ev.preventDefault).toHaveBeenCalled();  // drop autorisé
  });

  it('dropzone rôle EA REFUSE un drag de série EA (ancienne convention)', () => {
    A._drag = { kind: 'exo_catalogue', serie: 'EA' };
    const ev = faireEvent();
    A.dragOver(ev, faireZone('EA'));
    expect(ev.preventDefault).not.toHaveBeenCalled();  // drop refusé
  });

  it('dropzone rôle R accepte un drag de série R (révision inchangée)', () => {
    A._drag = { kind: 'exo_catalogue', serie: 'R' };
    const ev = faireEvent();
    A.dragOver(ev, faireZone('R'));
    expect(ev.preventDefault).toHaveBeenCalled();
  });

  // _rendreChipsRA : ouverture des exos placés en révision/approche.
  it('chip de révision (R) : ondblclick ouvre vers la séquence d’ORIGINE', () => {
    // Un exo de révision vient d'une autre séquence (origin_niveau/seq).
    const html = A._rendreChipsRA('pt_1', 'R', [{
      exercice_id: 'ex_R', ordre: 1,
      origin_niveau: 'N09', origin_seq: 'S05',
      exercice: { fichier: 'N09S05A03.tex', niveau: 'N09', sequence: 'S05',
                  etat_code: 'valide' },
    }]);
    expect(html).toContain('ondblclick=');
    expect(html).toContain("editerAtome('exercice', 'ex_R', event, 'N09', 'S05')");
  });

  it('chip d’approche (EA) : origine NULL → séquence de l’exercice lui-même', () => {
    // En base, origin_* est NULL pour l'approche ; on retombe sur ex.niveau/seq.
    const html = A._rendreChipsRA('pt_1', 'EA', [{
      exercice_id: 'ex_EA', ordre: 1,
      origin_niveau: null, origin_seq: null,
      exercice: { fichier: 'N10S04AE01.tex', niveau: 'N10', sequence: 'S04',
                  etat_code: 'en_cours' },
    }]);
    expect(html).toContain("editerAtome('exercice', 'ex_EA', event, 'N10', 'S04')");
  });

  it('chip RA affiche le badge d’origine pour la révision', () => {
    const html = A._rendreChipsRA('pt_1', 'R', [{
      exercice_id: 'ex_R', ordre: 1, origin_niveau: 'N09', origin_seq: 'S05',
      exercice: { fichier: 'x.tex', niveau: 'N09', sequence: 'S05' },
    }]);
    expect(html).toContain('N09/S05');  // tag d'origine visible
  });
});
