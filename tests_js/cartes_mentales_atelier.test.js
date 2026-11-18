// tests_js/cartes_mentales_atelier.test.js — v0.55.0
//
// Cartes mentales de partie dans l'onglet « Rendu PDF » (Laurent, 12 novembre 2026,
// doc/redemarrage_v0_55_0.md) :
//   - le bloc n'apparaît que pour une séquence principale au modèle « Fiches » (pas pour
//     une mise en route, qui n'a pas de carte, ni au modèle « Notions et méthodes ») ;
//   - le PDF passe par la route du livret (?document=cartes_mentales), même générateur que
//     « Tout compiler » ;
//   - v0.55.0 révisée : l'éditeur est dans l'atelier « Carte mentale » (portée Séquence),
//     « Rendu PDF » garde la compilation et un lien vers l'atelier.

import { describe, it, expect, beforeAll, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const lire = rel => readFileSync(join(__dirname, '..', rel), 'utf-8');
function charger(rel) { new Function(lire(join('static', rel)))(); }   // eslint-disable-line no-new-func

describe('v0.55.0 — cartes mentales dans l\'atelier', () => {
  let A, P, appels;
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
  beforeEach(() => {
    appels = [];
    globalThis.fetch = async (url, init) => {
      appels.push({ url, method: (init && init.method) || 'GET', body: init && init.body });
      if (/cartes-mentales$/.test(url)) {
        return new Response(JSON.stringify({ modifiable: true, parties: [
          { numero: 1, carte: { titre: 'Nombres', latex: '\\begin{seqCarteMentaleSix}{N}', etat_code: 'en_cours' } },
          { numero: 2, carte: null }] }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }
      return new Response(JSON.stringify({ etat: 'mise à jour', avertissements: [] }),
                          { status: 200, headers: { 'Content-Type': 'application/json' } });
    };
  });

  it('URL de la liste, de la partie et du rendu par la route du livret', () => {
    expect(P.urlCartesMentales('N09', 'S03')).toBe('/api/v2/livret-sequence/N09/S03/cartes-mentales');
    expect(P.urlCartesMentales('N09', 'S03', 2)).toBe('/api/v2/livret-sequence/N09/S03/cartes-mentales/2');
    expect(P.requeteRenduCartes('corrigee', 2)).toBe('?document=cartes_mentales&version=corrigee&partie=2');
    expect(P.requeteRenduCartes('autre', '')).toBe('?document=cartes_mentales&version=eleve');
  });

  function ongletPour(seq, gabarit) {
    A.data = { sequence_par_niveau: { niveau: 'N09', sequence_code: seq }, modele: { gabarit } };
    A._chargerResumeMer = () => {};
    document.body.innerHTML = '<div id="asm-tab-rendu"></div>';
    A._assurerOngletRendu();
  }

  // v0.60.1 (D19, décision du 18 novembre) — le bloc « Carte mentale » de l'onglet
  // Rendu PDF est retiré : les cartes mentales se compilent dans leur atelier,
  // comme les autres atomes (ces deux tests supposaient le bloc de la v0.55.0).
  it('D19 — Rendu PDF : plus de bloc « Carte mentale », quel que soit le modèle', () => {
    for (const [seq, gab] of [['S01', 'sixieme'], ['S01', 'cycle4'], ['M02', 'sixieme']]) {
      ongletPour(seq, gab);
      expect(document.getElementById('livret-seq-cm')).toBe(null);
      expect(document.getElementById('livret-seq-cm-btn-pdf')).toBe(null);
    }
  });

  it("D19 — ni éditeur ni sélecteurs de carte mentale dans l'assemblage (l'atelier Carte mentale reste)", () => {
    ongletPour('S01', 'sixieme');
    expect(document.getElementById('livret-seq-cm-editeur')).toBe(null);
    expect(document.getElementById('livret-seq-cm-partie')).toBe(null);
    expect(A.cmCompiler).toBe(undefined);
    expect(A.cmOuvrirAtelier).toBe(undefined);
  });
});

// v0.56.1 — Atelier harmonisé (Laurent, 13 novembre 2026) : AtelierCarteMentale étend
// AtelierEditeur (mêmes briques que Fiche de résumé et Carte d'automatisme).
describe("v0.56.1 — atelier « Carte mentale » harmonisé sur AtelierEditeur", () => {
  let C, P, appels, reponses;
  const CARTE = '\\begin{seqCarteMentaleSix}{T}\\seqCMBranche{a}{b}\\seqCMBranche{c}{d}\\end{seqCarteMentaleSix}';
  const HTML = `<div id="atl-cm-list"></div><span id="atl-cm-toolbar-title"></span>
    <span id="atl-cm-badge-modifie"></span><span id="atl-cm-etat-badge"></span>
    <button id="atl-cm-btn-valider"></button><button id="atl-cm-btn-suppr"></button>
    <button id="atl-cm-btn-save"></button><button id="atl-cm-btn-creer"></button>
    <div id="atl-cm-tabs"></div><button id="atl-cm-tab-btn-edition"></button><button id="atl-cm-tab-btn-rendu"></button>
    <div id="atl-cm-empty"></div>
    <div id="atl-cm-form" style="display:none"><div id="atl-cm-info"></div><input id="atl-cm-titre">
      <textarea id="atl-cm-latex"></textarea><button id="atl-cm-btn-creer-partie"></button></div>
    <div id="atl-cm-rendu" style="display:none"><div id="atl-cm-rendu-toolbar"></div></div>`;
  const json = (d, status = 200) => new Response(JSON.stringify(d), { status, headers: { 'Content-Type': 'application/json' } });
  function element(n, carte, modifiable = true) {
    return { id: String(n), numero: n, libelle: `L${n}`, presente: !!carte, titre: carte ? carte.titre : '',
             latex: carte ? carte.latex : '\\begin{seqCarteMentaleSix}{Titre central}', etat_code: carte ? carte.etat_code : 'en_cours',
             modifiable };
  }
  beforeAll(() => {
    globalThis.window.atelGardeEnregistrer = globalThis.window.atelGardeEnregistrer || (() => {});
    charger('atelier.js');
    charger('atelier_editeur.js');
    charger('seqniv_pur.js');
    charger('atelier_carte_mentale.js');
    C = globalThis.window.ATELIER_CARTE_MENTALE;
    P = globalThis.window.CarteMentalePur;
  });
  beforeEach(() => {
    appels = [];
    document.body.innerHTML = HTML;
    C.itemActif = null; C.filtreEtat = ''; C._snapshotForm = null; C._snapshotInvalide = false;
    C._listenerInstalle = false;
    globalThis.window.ATL_FILTRE_NIVEAU = 'N11';
    globalThis.window.ATL_FILTRE_SEQ = 'S04';
    globalThis.window.atelGardeAvantAction = async () => true;
    globalThis.confirm = () => true;
    reponses = { modifiable: true, parties: [
      { numero: 1, libelle: 'L1', carte: { titre: 'Calcul littéral', etat_code: 'valide', latex: CARTE } },
      { numero: 2, libelle: 'L2', carte: null }] };
    globalThis.fetch = async (url, init) => {
      const method = (init && init.method) || 'GET';
      appels.push({ url, method, body: init && init.body });
      if (/cartes-mentales$/.test(url) && method === 'GET') return json(reponses);
      if (/cartes-mentales$/.test(url) && method === 'POST') return json(element(2, { titre: '', latex: CARTE, etat_code: 'en_cours' }), 201);
      if (/cartes-mentales\/1$/.test(url)) return json({ ...element(1, reponses.parties[0].carte, reponses.modifiable), avertissements: ['2 branches (4 à 8 conseillées)'] });
      if (/cartes-mentales\/2$/.test(url)) return json(element(2, null, reponses.modifiable));
      return json({});
    };
  });

  it("hérite d'AtelierEditeur : mêmes briques que les autres ateliers (pas de second mécanisme)", () => {
    expect(C).toBeInstanceOf(globalThis.window.AtelierEditeur);
    for (const m of ['ouvrirItem', 'sauvegarder', 'supprimer', 'basculerOnglet', 'compilerRendu',
                     'verifierCacheEtAfficher', 'voirLatex', 'toggleTexBrut']) {
      expect(typeof C[m]).toBe('function');
    }
    // Surcharges limitées aux spécificités : pas de compilation ni d'ouverture maison.
    const propres = Object.getOwnPropertyNames(globalThis.window.AtelierCarteMentale.prototype);
    for (const m of ['compilerRendu', 'ouvrirItem', 'supprimer', 'basculerOnglet', 'verifierCacheEtAfficher']) {
      expect(propres).not.toContain(m);
    }
  });

  it("URL de la séquence filtrée, partagée avec l'onglet Rendu PDF de la séquence (SeqnivPur)", () => {
    expect(C.config.endpointBase).toBe('/api/v2/livret-sequence/N11/S04/cartes-mentales');
    expect(C.config.endpointRenduPdf).toBe(C.config.endpointBase);
    globalThis.window.ATL_FILTRE_SEQ = 'S05';
    expect(C.config.endpointBase).toBe('/api/v2/livret-sequence/N11/S05/cartes-mentales');
  });

  it('logique pure : élément de liste, filtre, partie à créer, paramètres du rendu', () => {
    expect(P.nbBranches('\\seqCMBranche{a}{b}\\seqCMBranche{c}{d}\\seqCMBranches')).toBe(2);
    const a = P.element(reponses.parties[0]); const b = P.element(reponses.parties[1]);
    expect(a).toMatchObject({ id: '1', presente: true, etat_code: 'valide', branches: 2 });
    expect(b).toMatchObject({ id: '2', presente: false });
    expect(P.garder(b, 'absente')).toBe(true); expect(P.garder(a, 'absente')).toBe(false);
    expect(P.garder(b, 'en_cours')).toBe(false); expect(P.garder(a, 'valide')).toBe(true);
    expect(P.partieACreer([a, b], a)).toBe(2); expect(P.partieACreer([a], a)).toBe(null);
    expect(P.parametres('corrigee', 'sequence')).toBe('?version=corrigee&portee=sequence');
    expect(P.parametres('x', 'y')).toBe('?version=eleve&portee=partie');
  });

  it('liste : une entrée par partie (carte présente / absente), filtre « Sans carte »', async () => {
    await C.chargerListe();
    const txt = document.getElementById('atl-cm-list').textContent;
    expect(txt).toMatch(/N11\/S04\/P1/); expect(txt).toMatch(/Calcul littéral/); expect(txt).toMatch(/2 br\./);
    expect(txt).toMatch(/N11\/S04\/P2/); expect(txt).toMatch(/sans carte/);
    C.filtreEtat = 'absente'; C.rendreSidebar();
    expect(document.getElementById('atl-cm-list').textContent).not.toMatch(/P1/);
  });

  // v0.56.2 — décision renversée à la demande de Laurent (13 novembre, 16 h 11) :
  // sans séquence choisie, la liste montre toutes les séquences du niveau
  // (tests_js/v0_56_2_carte_mentale_toutes_et_cache.test.js).
  it("sans séquence précise (v0.56.2) : plus de message « Choisir une séquence précise », liste du niveau", async () => {
    globalThis.window.ATL_FILTRE_SEQ = '';
    await C.chargerListe();
    expect(appels.map(a => a.url)).toEqual(['/api/v2/livret-sequence/N11/cartes-mentales']);
    expect(document.getElementById('atl-cm-list').textContent).not.toMatch(/séquence précise/);
  });

  it('ouvrir puis enregistrer : GET unitaire puis PATCH (méthode héritée), avertissement affiché', async () => {
    const toasts = []; C.toast = (m) => toasts.push(m);
    await C.chargerListe();
    await C.ouvrirItem('1');
    expect(document.getElementById('atl-cm-titre').value).toBe('Calcul littéral');
    document.getElementById('atl-cm-titre').value = 'Nouveau';
    expect(C.modifie).toBe(true);                       // badge « modifié », garde de sortie
    await C.sauvegarder();
    const patch = appels.find(x => x.method === 'PATCH');
    expect(patch.url).toBe('/api/v2/livret-sequence/N11/S04/cartes-mentales/1');
    expect(JSON.parse(patch.body)).toEqual({ titre: 'Nouveau', latex: CARTE });
    expect(toasts.join(' ')).toMatch(/4 à 8 conseillées/);
  });

  it('« + Créer » : POST avec le numéro de la partie sans carte, puis ouverture', async () => {
    await C.chargerListe();
    await C.ouvrirItem('2');
    expect(document.getElementById('atl-cm-btn-creer-partie').style.display).toBe('');
    expect(document.getElementById('atl-cm-btn-valider').style.display).toBe('none');
    await C.nouvelItem();
    const post = appels.find(x => x.method === 'POST');
    expect(JSON.parse(post.body)).toEqual({ numero: 2 });
  });

  it('Valider : PATCH etat_code seul sur la partie', async () => {
    reponses.parties[0].carte.etat_code = 'en_cours';
    await C.chargerListe();
    await C.ouvrirItem('1');
    await C.basculerValidation();
    const patch = appels.filter(x => x.method === 'PATCH').at(-1);
    expect(JSON.parse(patch.body)).toEqual({ etat_code: 'valide' });
  });

  it('séquence validée : formulaire verrouillé, Enregistrer / Supprimer / Valider masqués', async () => {
    reponses.modifiable = false;
    await C.chargerListe();
    await C.ouvrirItem('1');
    expect(document.getElementById('atl-cm-latex').disabled).toBe(true);
    for (const id of ['atl-cm-btn-save', 'atl-cm-btn-suppr', 'atl-cm-btn-valider']) {
      expect(document.getElementById(id).style.display).toBe('none');
    }
    expect(document.getElementById('atl-cm-btn-creer').disabled).toBe(true);
    expect(document.getElementById('atl-cm-toolbar-title').textContent).toMatch(/lecture seule/);
  });

  it('rendu : sélecteurs version et portée dans la barre du rendu, transmis à la compilation', async () => {
    await C.chargerListe();
    await C.ouvrirItem('1');
    C._assurerToolbarRendu();
    document.getElementById('atl-cm-rendu-version').value = 'corrigee';
    document.getElementById('atl-cm-rendu-portee').value = 'sequence';
    expect(C.parametresRendu()).toBe('?version=corrigee&portee=sequence');
    expect(document.getElementById('atl-cm-btn-compiler')).not.toBe(null);
  });

  it("l'atelier est déclaré dans la portée Séquence, avec son init, son rechargement sur filtre et Ctrl+L", () => {
    const app = lire('static/app.js');
    expect(app).toMatch(/'carte_automatisme', 'carte_mentale',/);
    expect(app).toMatch(/carte_mentale:\s+'atelCarteMentaleInit'/);
    expect(app).toMatch(/'carte_mentale':\s+'ATELIER_CARTE_MENTALE'/);
    expect(lire('static/atelier_filtres_hook.js')).toMatch(/'carte_mentale':\s+'ATELIER_CARTE_MENTALE'/);
    const html = lire('templates/index.html');
    expect(html).toMatch(/id="atl-btn-carte_mentale"/);
    expect(html).toMatch(/id="atl-carte_mentale"/);
    expect(html).toMatch(/atelier_carte_mentale\.js/);
    // Même structure de template que les autres ateliers (toolbar, onglets, zone de rendu).
    for (const id of ['atl-cm-list', 'atl-cm-tabs', 'atl-cm-tab-btn-rendu', 'atl-cm-form', 'atl-cm-rendu-toolbar',
                      'atl-cm-pdf-iframe', 'atl-cm-rendu-erreur', 'atl-cm-btn-save', 'atl-cm-btn-valider']) {
      expect(html).toContain(`id="${id}"`);
    }
    // Plus d'ancien mécanisme (liste déroulante d'état, iframe maison).
    expect(html).not.toContain('id="atl-cm-etat-code"');
    expect(html).not.toContain('id="atl-cm-pdf"');
  });
});
