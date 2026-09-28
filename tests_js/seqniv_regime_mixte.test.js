// tests_js/seqniv_regime_mixte.test.js — v0.16.9
//
// Tests du régime mixte + état validable côté seqniv (AtelierSeqnivAssemblage) :
//   - collecterFormulaire() lit les champs de l'objectif ouvert depuis le form ;
//   - _garderAvantStructure() bloque si modifie ;
//   - _etatSequence() / majToolbar() pilotent l'UI selon l'état.
//
// On charge la chaîne d'héritage dans jsdom (comme atelier_seqniv_assemblage.test.js)
// et on simule le DOM minimal (#liv-atl-form + champs data-champ).

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

let A;

beforeAll(() => {
  globalThis.window.atelToast = globalThis.window.atelToast || (() => {});
  charger('atelier.js');
  charger('atelier_editeur.js');
  charger('atelier_assemblage.js');
  charger('seqniv_pur.js');
  charger('atelier_seqniv_assemblage.js');
  A = globalThis.window.ATELIER_SEQNIV;
});

function poserForm({nom = '', f = '', a = '', e = '', seances = '', finCycle = null} = {}) {
  // Construit #liv-atl-form avec les champs data-champ attendus par
  // collecterFormulaire. finCycle=null → pas de case (objectif Cours).
  const fc = finCycle === null ? '' :
    `<input type="checkbox" data-champ="fin_cycle" ${finCycle ? 'checked' : ''}>`;
  document.body.innerHTML = `
    <form id="liv-atl-form">
      <input type="text" data-champ="nom" value="${nom}">
      <textarea data-champ="critere_F">${f}</textarea>
      <textarea data-champ="critere_A">${a}</textarea>
      <textarea data-champ="critere_E">${e}</textarea>
      <input type="number" data-champ="nb_seances" value="${seances}">
      ${fc}
    </form>`;
}

describe('collecterFormulaire (objectif ouvert)', () => {
  beforeEach(() => { A.objOuvert = null; document.body.innerHTML = ''; A.modifie = false; });

  it('renvoie null sans objectif ouvert', () => {
    A.objOuvert = null;
    expect(A.collecterFormulaire()).toBeNull();
  });

  it('renvoie null si objectif ouvert mais form absent', () => {
    A.objOuvert = 'o1';
    document.body.innerHTML = '';
    expect(A.collecterFormulaire()).toBeNull();
  });

  it('lit les champs du form pour l\'objectif ouvert (exo, avec fin-cycle)', () => {
    A.objOuvert = 'o1';
    poserForm({nom: 'Calculer', f: 'cF', a: 'cA', e: 'cE', seances: '2', finCycle: false});
    const c = A.collecterFormulaire();
    expect(c.obj_id).toBe('o1');
    expect(c.nom).toBe('Calculer');
    expect(c.critere_F).toBe('cF');
    expect(c.critere_E).toBe('cE');
    expect(c.nb_seances).toBe('2');
    expect(c.fin_cycle).toBe('N');  // case présente, non cochée
  });

  it('fin_cycle=null quand la case est absente (objectif Cours)', () => {
    A.objOuvert = 'oc';
    poserForm({nom: 'Cours', f: 'x', a: 'y', e: 'z', finCycle: null});
    const c = A.collecterFormulaire();
    expect(c.fin_cycle).toBeNull();
  });

  it('fin_cycle=O quand la case est cochée', () => {
    A.objOuvert = 'o2';
    poserForm({nom: 'X', finCycle: true});
    expect(A.collecterFormulaire().fin_cycle).toBe('O');
  });
});

describe('modifie (snapshot) en régime mixte', () => {
  beforeEach(() => { A.objOuvert = null; document.body.innerHTML = ''; A.modifie = false; });

  it('false juste après snapshot, true après modification d\'un champ', () => {
    A.objOuvert = 'o1';
    poserForm({nom: 'Initial', f: 'F', a: 'A', e: 'E'});
    A.modifie = false;            // prend le snapshot de l'état courant
    expect(A.modifie).toBe(false);
    // L'utilisateur tape : on change la valeur du champ nom.
    document.querySelector('[data-champ="nom"]').value = 'Modifié';
    expect(A.modifie).toBe(true);
  });
});

describe('_garderAvantStructure', () => {
  beforeEach(() => { A.objOuvert = null; document.body.innerHTML = ''; A.modifie = false; });

  it('autorise (true) si rien de modifié', () => {
    A.objOuvert = null;
    A.modifie = false;  // snapshot propre (collecterFormulaire→null)
    expect(A._garderAvantStructure()).toBe(true);
  });

  it('bloque (false) + toast si modifié', () => {
    A.objOuvert = 'o1';
    poserForm({nom: 'Initial'});
    A.modifie = false;
    document.querySelector('[data-champ="nom"]').value = 'Changé';
    expect(A.modifie).toBe(true);
    const spy = vi.spyOn(A, 'toast').mockImplementation(() => {});
    expect(A._garderAvantStructure()).toBe(false);
    expect(spy).toHaveBeenCalled();
    spy.mockRestore();
  });
});

describe('_etatSequence + majToolbar', () => {
  beforeEach(() => { document.body.innerHTML = ''; A.objOuvert = null; A.modifie = false; });

  it('_etatSequence lit data.sequence_par_niveau.etat_code', () => {
    A.data = {sequence_par_niveau: {id: 's', etat_code: 'valide'}};
    expect(A._etatSequence()).toBe('valide');
    A.data = {sequence_par_niveau: {id: 's'}};
    expect(A._etatSequence()).toBe('en_cours');
  });

  it('majToolbar masque le bouton save si aucun objectif ouvert', () => {
    document.body.innerHTML = '<button id="liv-atl-btn-save"></button>';
    A.data = {sequence_par_niveau: {id: 's', etat_code: 'en_cours'}};
    A.objOuvert = null;
    A.majToolbar();
    expect(document.getElementById('liv-atl-btn-save').style.display).toBe('none');
  });

  it('majToolbar : bouton save visible mais désactivé si objectif ouvert non modifié', () => {
    document.body.innerHTML = `
      <button id="liv-atl-btn-save"></button>
      <form id="liv-atl-form"><input data-champ="nom" value="x"></form>`;
    A.data = {sequence_par_niveau: {id: 's', etat_code: 'en_cours'}};
    A.objOuvert = 'o1';
    A.modifie = false;  // snapshot propre
    A.majToolbar();
    const btn = document.getElementById('liv-atl-btn-save');
    expect(btn.style.display).toBe('inline-block');
    expect(btn.disabled).toBe(true);
  });

  it('majToolbar masque le bouton save si séquence validée (verrou)', () => {
    document.body.innerHTML = `
      <button id="liv-atl-btn-save"></button>
      <form id="liv-atl-form"><input data-champ="nom" value="x"></form>`;
    A.data = {sequence_par_niveau: {id: 's', etat_code: 'valide'}};
    A.objOuvert = 'o1';
    A.modifie = false;
    A.majToolbar();
    expect(document.getElementById('liv-atl-btn-save').style.display).toBe('none');
  });

  it('majToolbar : badges + bouton valider alignés sur les atomes', () => {
    document.body.innerHTML = `
      <span id="liv-atl-badge-modifie" style="display:none"></span>
      <span id="liv-atl-etat-badge" style="display:none"></span>
      <button id="liv-atl-btn-valider" style="display:none"></button>`;
    A.data = {sequence_par_niveau: {id: 's', etat_code: 'valide'}};
    A.objOuvert = null;
    A.majToolbar();
    const badgeEtat = document.getElementById('liv-atl-etat-badge');
    const btnValider = document.getElementById('liv-atl-btn-valider');
    expect(badgeEtat.style.display).toBe('inline-block');
    expect(badgeEtat.textContent).toBe('Validé');
    expect(badgeEtat.className).toContain('atome-etat-badge');
    expect(btnValider.textContent).toBe('Repasser en cours');
  });
});
