// tests_js/v0_56_3_carte_mentale_fonctions_communes.test.js — v0.56.3
//
// Demande de Laurent (13 novembre 2026, 17 h 03), doc/redemarrage_v0_56_3.md :
// « mettre en place la multisélection pour valider plusieurs éléments en une seule
// fois […] reprends toutes les fonctionnalités communes à tous les ateliers
// atomiques pour vérifier qu'elles sont bien présentes ».
//
// L'atelier Carte mentale reçoit ce qui lui manquait, en réutilisant les briques
// existantes (aucune réimplémentation) :
//   1. multisélection et actions groupées d'AtelierEditeur (Valider / Repasser en
//      cours), avec deux crochets seulement : urlEtat (où envoyer le PATCH) et
//      raisonHorsEtat (parties sans carte et séquences validées ignorées) ;
//   2. mode côte-à-côte (règles CSS et poignée édition / rendu des autres ateliers) ;
//   3. lien direct (?atelier=carte_mentale…), Recherche, lien depuis l'atelier Séquence.

import { describe, it, expect, beforeAll, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const lire = rel => readFileSync(join(__dirname, '..', rel), 'utf-8');
function charger(rel) { new Function(lire(join('static', rel)))(); }   // eslint-disable-line no-new-func
const json = (d, status = 200) => new Response(JSON.stringify(d), { status, headers: { 'Content-Type': 'application/json' } });
const attendre = () => new Promise(r => setTimeout(r, 0));

const HTML_CM = `<aside><div id="atl-cm-list"></div></aside><span id="atl-cm-toolbar-title"></span>
  <span id="atl-cm-badge-modifie"></span><span id="atl-cm-etat-badge"></span>
  <button id="atl-cm-btn-valider"></button><button id="atl-cm-btn-suppr"></button>
  <button id="atl-cm-btn-save"></button><button id="atl-cm-btn-creer"></button>
  <div id="atl-cm-tabs"></div><button id="atl-cm-tab-btn-edition"></button><button id="atl-cm-tab-btn-rendu"></button>
  <div id="atl-cm-empty"></div>
  <div id="atl-cm-form" style="display:none"><div id="atl-cm-info"></div><input id="atl-cm-titre">
    <textarea id="atl-cm-latex"></textarea><button id="atl-cm-btn-creer-partie"></button></div>
  <div id="atl-cm-rendu" style="display:none"><div id="atl-cm-rendu-toolbar"></div>
    <iframe id="atl-cm-pdf-iframe"></iframe><div id="atl-cm-rendu-erreur"></div>
    <div id="atl-cm-rendu-loading"></div><div id="atl-cm-rendu-placeholder"></div></div>`;

const CARTE = '\\begin{seqCarteMentaleSix}{T}\\seqCMBranche{a}{b}\\end{seqCarteMentaleSix}';
const carte = (etat) => ({ titre: 'T', latex: CARTE, etat_code: etat });

let C, P, appels, toasts;
beforeAll(() => {
  globalThis.window.atelGardeEnregistrer = globalThis.window.atelGardeEnregistrer || (() => {});
  charger('atelier.js');
  charger('atelier_editeur.js');
  charger('atelier_assemblage.js');
  charger('seqniv_pur.js');
  charger('atelier_seqniv_assemblage.js');
  charger('atelier_carte_mentale.js');
  C = globalThis.window.ATELIER_CARTE_MENTALE;
  P = globalThis.window.CarteMentalePur;
});

// S01 (en cours) : P1 et P2 avec carte en cours, P3 sans carte, P4 validée.
// S02 : P1 avec carte en cours ; `validees` liste les séquences validées.
function serveur(validees = []) {
  const parties = {
    S01: [{ numero: 1, libelle: 'a', carte: carte('en_cours') }, { numero: 2, libelle: 'b', carte: carte('en_cours') },
          { numero: 3, libelle: 'c', carte: null }, { numero: 4, libelle: 'd', carte: carte('valide') }],
    S02: [{ numero: 1, libelle: 'e', carte: carte('en_cours') }],
  };
  globalThis.fetch = async (url, init) => {
    const method = (init && init.method) || 'GET';
    appels.push({ url, method, body: init && init.body && JSON.parse(init.body) });
    if (url === '/api/v2/livret-sequence/N09/cartes-mentales') {
      return json({ niveau: 'N09', sequences: Object.entries(parties).map(([s, ps]) =>
        ({ sequence: s, modifiable: !validees.includes(s), parties: ps })) });
    }
    const m = /\/N09\/(S0\d)\/cartes-mentales(?:\/(\d+))?$/.exec(url);
    if (m && !m[2] && method === 'GET') {
      return json({ parties: parties[m[1]], modifiable: !validees.includes(m[1]) });
    }
    if (m && m[2] && method === 'PATCH') {
      if (validees.includes(m[1])) {
        return json({ error: 'sequence_validee', message: 'Séquence validée : la repasser en cours.' }, 409);
      }
      return json({ id: m[2], numero: Number(m[2]), sequence: m[1], presente: true, etat_code: 'valide' });
    }
    if (m && m[2]) {
      return json({ id: m[2], numero: Number(m[2]), sequence: m[1], presente: true, titre: 'T', latex: CARTE,
                    etat_code: 'en_cours', modifiable: !validees.includes(m[1]) });
    }
    return json({});
  };
}

beforeEach(() => {
  appels = []; toasts = [];
  document.body.innerHTML = HTML_CM;
  C.itemActif = null; C.filtreEtat = ''; C._snapshotForm = null; C._snapshotInvalide = false;
  C._listenerInstalle = false; C._seqCible = ''; C.modifiable = true;
  C.selectionMulti.clear(); C.ancreSelectionId = null; C._contexteListe = undefined;
  C.toast = (m, niveau) => toasts.push({ m, niveau: niveau || 'info' });
  globalThis.window.ATL_FILTRE_NIVEAU = 'N09';
  globalThis.window.ATL_FILTRE_SEQ = 'S01';
  globalThis.window.atelGardeAvantAction = async () => true;
  globalThis.window.prefAutoCompileEstActive = () => false;
  globalThis.confirm = () => true;
  serveur();
});

const ev = (mods = {}) => ({ preventDefault() {}, clientX: 10, clientY: 10, ...mods });
const patchs = () => appels.filter(a => a.method === 'PATCH');

describe('v0.56.3 — 1. multisélection de la liste (briques d\'AtelierEditeur)', () => {
  it('chaque entrée porte les gestionnaires communs (clic, Ctrl/Maj+clic, clic droit) et la classe de sélection', async () => {
    await C.chargerListe();
    const el = document.querySelector('#atl-cm-list .asm-item');
    expect(el.getAttribute('onclick')).toBe("ATELIER_CARTE_MENTALE.gererClicItem(event, '1')");
    expect(el.getAttribute('oncontextmenu')).toBe("ATELIER_CARTE_MENTALE.gererClicDroitItem(event, '1')");
    C.gererClicItem(ev({ ctrlKey: true }), '2');
    expect(document.querySelector('#atl-cm-list [data-item-id="2"]').classList.contains('asm-item--selected')).toBe(true);
    // Le code de sélection n'est pas recopié : l'atelier n'en définit aucune méthode.
    const src = lire('static/atelier_carte_mentale.js');
    expect(src).not.toMatch(/selectionMulti(AppliquerEtat|Toggle|Plage|OuvrirMenu)\s*\(/);
  });

  it('Ctrl+clic, Maj+clic (plage), barre d\'actions « ✓ Valider / ⟲ En cours », Échap vide la sélection', async () => {
    await C.chargerListe();
    C.gererClicItem(ev(), '1');                    // ancre (ouvre la partie 1)
    await attendre();
    C.gererClicItem(ev({ shiftKey: true }), '3');  // plage 1..3
    expect([...C.selectionMulti]).toEqual(['1', '2', '3']);
    const barre = document.getElementById('atl-cm-selection-toolbar');
    expect(barre.style.display).toBe('flex');
    expect(barre.textContent).toMatch(/3 sélectionnés/);
    expect(barre.textContent).toMatch(/✓ Valider/);
    expect(barre.textContent).toMatch(/⟲ En cours/);
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(C.selectionMulti.size).toBe(0);
    expect(lire('static/atelier_editeur.js')).toMatch(/'ATELIER_EXERCICE', 'ATELIER_CARTE_MENTALE'\]/);
  });

  it('clic droit : menu contextuel commun avec « Valider la sélection »', async () => {
    await C.chargerListe();
    C.gererClicDroitItem(ev(), '2');
    const menu = document.getElementById('__selection-menu__');
    expect(menu).not.toBe(null);
    expect(menu.textContent).toMatch(/1 item sélectionné/);
    expect(menu.textContent).toMatch(/Valider la sélection/);
    C.selectionMultiFermerMenu();
  });
});

describe('v0.56.3 — 2. validation groupée', () => {
  it('valide plusieurs cartes en une fois : un PATCH {etat_code} par partie, sur la route de la partie', async () => {
    await C.chargerListe();
    ['1', '2'].forEach(id => C.selectionMultiToggleId(id));
    await C.selectionMultiAppliquerEtat('valide');
    expect(patchs().map(a => [a.url, a.body])).toEqual([
      ['/api/v2/livret-sequence/N09/S01/cartes-mentales/1', { etat_code: 'valide' }],
      ['/api/v2/livret-sequence/N09/S01/cartes-mentales/2', { etat_code: 'valide' }],
    ]);
    expect(toasts.at(-1)).toEqual({ m: '2 validé', niveau: 'info' });
  });

  it('les parties sans carte sont ignorées (aucun appel) et comptées à part ; une carte déjà validée est « à jour »', async () => {
    await C.chargerListe();
    ['1', '3', '4'].forEach(id => C.selectionMultiToggleId(id));
    await C.selectionMultiAppliquerEtat('valide');
    expect(patchs().map(a => a.url)).toEqual(['/api/v2/livret-sequence/N09/S01/cartes-mentales/1']);
    expect(toasts.at(-1).m).toBe('1 validé, 1 déjà à jour, 1 ignoré (sans carte)');
  });

  it('repasser en cours en groupe : même mécanisme, cible « en_cours »', async () => {
    await C.chargerListe();
    ['3', '4'].forEach(id => C.selectionMultiToggleId(id));
    await C.selectionMultiAppliquerEtat('en_cours');
    expect(patchs().map(a => [a.url, a.body])).toEqual([
      ['/api/v2/livret-sequence/N09/S01/cartes-mentales/4', { etat_code: 'en_cours' }]]);
    expect(toasts.at(-1).m).toBe('1 repassé en cours, 1 ignoré (sans carte)');
  });

  it('séquence validée (mode séquence) : refus sans appel, signalé en erreur', async () => {
    serveur(['S01']);
    await C.chargerListe();
    expect(C.modifiable).toBe(false);
    ['1', '2'].forEach(id => C.selectionMultiToggleId(id));
    await C.selectionMultiAppliquerEtat('valide');
    expect(patchs()).toEqual([]);
    expect(toasts.at(-1)).toEqual({ m: '2 ignorés (séquence validée)', niveau: 'erreur' });
  });

  it('toutes les séquences : seules les entrées des séquences validées sont refusées', async () => {
    serveur(['S02']);
    globalThis.window.ATL_FILTRE_SEQ = '';
    await C.chargerListe();
    ['S01:1', 'S01:3', 'S02:1'].forEach(id => C.selectionMultiToggleId(id));
    await C.selectionMultiAppliquerEtat('valide');
    expect(patchs().map(a => a.url)).toEqual(['/api/v2/livret-sequence/N09/S01/cartes-mentales/1']);
    expect(toasts.at(-1).m).toBe('1 validé, 1 ignoré (sans carte), 1 ignoré (séquence validée)');
  });

  it('refus du serveur (séquence validée entre-temps) : compté en échec, avec son motif', async () => {
    await C.chargerListe();                 // liste chargée quand S01 était modifiable
    serveur(['S01']);                        // … puis la séquence est validée ailleurs
    C.selectionMultiToggleId('1');
    await C.selectionMultiAppliquerEtat('valide');
    expect(patchs().length).toBe(1);
    expect(toasts.at(-1)).toEqual({ m: '1 en échec : Séquence validée : la repasser en cours.', niveau: 'erreur' });
  });

  it('la carte ouverte suit la validation groupée (badge et verrou lecture seule)', async () => {
    await C.chargerListe();
    await C.ouvrirItem('1');
    ['1', '2'].forEach(id => C.selectionMultiToggleId(id));
    await C.selectionMultiAppliquerEtat('valide');
    expect(C.itemActif.etat_code).toBe('valide');
    expect(document.getElementById('atl-cm-etat-badge').textContent).toBe('Validé');
    expect(document.getElementById('atl-cm-latex').disabled).toBe(true);
  });

  it('changer de séquence vide la sélection (« 2 » désignerait la partie 2 d\'une autre séquence)', async () => {
    await C.chargerListe();
    C.selectionMultiToggleId('1');
    await C.chargerListe();                   // même séquence : sélection gardée
    expect([...C.selectionMulti]).toEqual(['1']);
    globalThis.window.ATL_FILTRE_SEQ = 'S02';
    await C.chargerListe();
    expect(C.selectionMulti.size).toBe(0);
    expect(document.getElementById('atl-cm-selection-toolbar').style.display).toBe('none');
  });

  it('logique pure des exclusions', () => {
    expect(P.raisonHorsEtat({ presente: false })).toBe('sans carte');
    expect(P.raisonHorsEtat({ presente: true }, false)).toBe('séquence validée');
    expect(P.raisonHorsEtat({ presente: true, modifiable: false }, true)).toBe('séquence validée');
    expect(P.raisonHorsEtat({ presente: true, modifiable: true }, false)).toBe(null);
    expect(P.raisonHorsEtat({ presente: true })).toBe(null);
  });

  it('les autres ateliers gardent la route unifiée des états ; aucune exclusion par défaut', () => {
    const A = new globalThis.window.AtelierEditeur({ id: 'x', prefixe: 'atl-x', typeApi: 'notion', endpointBase: '/api/notions' });
    expect(A.urlEtat('no_1')).toBe('/api/atomes/notion/no_1/etat');
    expect(A.raisonHorsEtat({ etat_code: 'en_cours' })).toBe(null);
    // Valider (unitaire) et l'action groupée passent par la même construction.
    const src = lire('static/atelier_editeur.js');
    expect((src.match(/this\.urlEtat\(/g) || []).length).toBe(2);
    expect(src).not.toMatch(/`\/api\/atomes\/\$\{encodeURIComponent\(this\.config\.typeApi\)\}` \+\s*`\/\$\{encodeURIComponent\(id\)\}\/etat`/);
  });

  it('Valider (unitaire) de l\'atelier passe aussi par urlEtat', async () => {
    await C.chargerListe();
    await C.ouvrirItem('2');
    await C.basculerValidation();
    expect(patchs().at(-1)).toEqual({ url: '/api/v2/livret-sequence/N09/S01/cartes-mentales/2', method: 'PATCH',
                                      body: { etat_code: 'valide' } });
  });
});

describe('v0.56.3 — 3. mode côte-à-côte (édition + rendu PDF)', () => {
  it('mêmes règles CSS que Notion, Méthode et Fiche (et Carte d\'automatisme, qui en manquait)', () => {
    const css = lire('static/app.css');
    const regle = (sel) => css.slice(0, css.indexOf(sel)).split('}').pop() + css.slice(css.indexOf(sel)).split('}')[0];
    expect(regle('body.atelier-mode-split #atl-cm-form')).toMatch(/grid-area: form/);
    expect(regle('body.atelier-mode-split #atl-cm-rendu')).toMatch(/grid-area: rendu/);
    expect(regle('body.atelier-mode-split #atl-carte-form')).toMatch(/grid-area: form/);
    expect(regle('body.atelier-mode-split #atl-carte-rendu')).toMatch(/grid-area: rendu/);
  });

  it("activation : la carte ouverte affiche son rendu ; poignée édition / rendu de la même brique", () => {
    const app = lire('static/app.js');
    const pref = app.slice(app.indexOf('function prefSplitAppliquer'), app.indexOf('function prefSplitToggle'));
    expect(pref).toMatch(/'ATELIER_CARTE_MENTALE'/);
    const split = app.slice(app.indexOf('function initAtelierSplitters'), app.indexOf('setTimeout(initAtelierSplitters'));
    expect(split).toMatch(/\$\('#atl-carte_mentale \.atl-main'\)/);
    expect(split).toMatch(/atelierInstallerSplitterGrid\(\{\s*conteneur:\s*cmMain,\s*cleStockage: 'split:atl-cm:formrendu'/);
  });
});

describe('v0.56.3 — 4. lien direct, Recherche, lien depuis l\'atelier Séquence', () => {
  it('lien direct ?atelier=carte_mentale (comme les 5 autres ateliers) et ouverture depuis un résultat', () => {
    const app = lire('static/app.js');
    const dl = app.slice(app.indexOf('function _appliquerDeeplink'), app.indexOf('async function chargerAnnees'));
    expect(dl).toMatch(/'carte_automatisme', 'carte_mentale'\]/);
    expect(dl).toMatch(/'carte_mentale':\s+'ATELIER_CARTE_MENTALE'/);
    expect(app).toMatch(/carte_mentale: \{sw: 'carte_mentale', oo: 'ATELIER_CARTE_MENTALE'\}/);
  });

  it('le lien direct pose la portée tout de suite (ATL_SELECTIONS), pas au chargement suivant', () => {
    // ATL_SELECTIONS est lu depuis localStorage au chargement du script : écrire
    // seulement localStorage laissait la liste sur la séquence précédente, et une
    // carte mentale (identifiant = numéro de partie) aurait été celle d'une autre séquence.
    const app = lire('static/app.js');
    const dl = app.slice(app.indexOf('function _appliquerDeeplink'), app.indexOf('async function chargerAnnees'));
    const pose = dl.indexOf('ATL_SELECTIONS.sequence = { niveau: niveau, sequence: seq }');
    expect(pose).toBeGreaterThan(0);
    expect(pose).toBeLessThan(dl.indexOf("btnAteliers.click()"));
  });

  it('Recherche : groupe « Cartes mentales » et type dans le filtre', () => {
    const app = lire('static/app.js');
    expect(app).toMatch(/const _RECH_ORDRE_TYPES = \['notion', 'methode', 'exercice', 'fiche', 'carte',\s*'carte_mentale'\]/);
    expect(app).toMatch(/carte_mentale: 'Cartes mentales'/);
    const html = lire('templates/index.html');
    const filtre = html.slice(html.indexOf('<select id="rech-filtre-type"'));
    expect(filtre.slice(0, filtre.indexOf('</select>'))).toMatch(/<option value="carte_mentale">Cartes mentales<\/option>/);
  });

  it('atelier Séquence : « Modifier dans l\'atelier » ouvre la partie choisie (même mécanisme que les autres atomes)', () => {
    const A = globalThis.window.ATELIER_SEQNIV;
    A.data = { sequence_par_niveau: { niveau: 'N09', sequence_code: 'S03' }, modele: { gabarit: 'sixieme' } };
    A._cartesMentales = { parties: [{ numero: 1 }, { numero: 2 }] };
    document.body.innerHTML = '<select id="livret-seq-cm-partie"><option value=""></option><option value="2">2</option></select>';
    document.getElementById('livret-seq-cm-partie').value = '2';
    const vus = [];
    globalThis.window.compilBatchOuvrirAtelier = (...a) => vus.push(a);
    A.cmOuvrirAtelier();
    expect(vus).toEqual([['carte_mentale', '2', 'N09', 'S03']]);
    // Aucune partie choisie : l'atelier s'ouvre simplement (comportement d'avant).
    document.getElementById('livret-seq-cm-partie').value = '';
    const sw = []; globalThis.window.atelSwitch = (x) => sw.push(x);
    A.cmOuvrirAtelier();
    expect(sw).toEqual(['carte_mentale']);
    expect(vus.length).toBe(1);
  });
});
