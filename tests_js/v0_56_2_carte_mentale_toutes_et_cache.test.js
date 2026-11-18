// tests_js/v0_56_2_carte_mentale_toutes_et_cache.test.js — v0.56.2
//
// Demandes de Laurent (13 novembre 2026, 16 h 11), doc/redemarrage_v0_56_2.md :
//   1. atelier Carte mentale : poignée de redimensionnement de la liste, la même que
//      dans les autres ateliers (atelierInstallerSplitter, largeur en localStorage) ;
//   2. aucune séquence choisie : les parties de toutes les séquences du niveau ;
//   3. « Recompiler sans cache » dans l'onglet Rendu PDF de chaque atelier (brique
//      commune AtelierEditeur), option « sans cache » de l'atelier Séquence et de
//      « Tout compiler », « Vider le cache des rendus PDF » dans Administration.

import { describe, it, expect, beforeAll, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const lire = rel => readFileSync(join(__dirname, '..', rel), 'utf-8');
function charger(rel) { new Function(lire(join('static', rel)))(); }   // eslint-disable-line no-new-func
const json = (d, status = 200) => new Response(JSON.stringify(d), { status, headers: { 'Content-Type': 'application/json' } });

const HTML_CM = `<div id="atl-cm-list"></div><span id="atl-cm-toolbar-title"></span>
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

let C, P, appels;
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

function serveur(seqValidee = '') {
  globalThis.fetch = async (url, init) => {
    const method = (init && init.method) || 'GET';
    appels.push({ url, method, body: init && init.body });
    if (url === '/api/v2/livret-sequence/N09/cartes-mentales') {
      return json({ niveau: 'N09', sequences: [
        { sequence: 'S01', modifiable: seqValidee !== 'S01', parties: [
          { numero: 1, libelle: 'Nombres', carte: { titre: 'Entiers', latex: CARTE, etat_code: 'valide' } },
          { numero: 2, libelle: 'Fractions', carte: null }] },
        { sequence: 'S02', modifiable: seqValidee !== 'S02', parties: [
          { numero: 1, libelle: 'Angles', carte: null }] }] });
    }
    const m = /\/N09\/(S0\d)\/cartes-mentales(?:\/(\d+))?(.*)$/.exec(url);
    if (m && method === 'POST' && !m[2]) {
      return json({ id: '1', numero: 1, sequence: m[1], presente: true, titre: '', latex: CARTE,
                    etat_code: 'en_cours', modifiable: true }, 201);
    }
    if (m && m[2] && !m[3]) {
      const presente = m[1] === 'S01' && m[2] === '1';
      return json({ id: m[2], numero: Number(m[2]), sequence: m[1], niveau: 'N09', libelle: 'L',
                    presente, titre: presente ? 'Entiers' : '', latex: CARTE,
                    etat_code: presente ? 'valide' : 'en_cours', modifiable: seqValidee !== m[1],
                    avertissements: [] });
    }
    if (/rendu-pdf\/info/.test(url)) return json({ cache_valide: false });
    if (/rendu-pdf/.test(url)) return new Response(new Blob(['%PDF']), { status: 200, headers: { 'X-Seq-Depuis-Cache': '0' } });
    return json({});
  };
}

beforeEach(() => {
  appels = [];
  document.body.innerHTML = HTML_CM;
  C.itemActif = null; C.filtreEtat = ''; C._snapshotForm = null; C._snapshotInvalide = false;
  C._listenerInstalle = false; C._seqCible = '';
  globalThis.window.ATL_FILTRE_NIVEAU = 'N09';
  globalThis.window.ATL_FILTRE_SEQ = '';
  globalThis.window.atelGardeAvantAction = async () => true;
  globalThis.window.prefAutoCompileEstActive = () => false;
  globalThis.confirm = () => true;
  serveur();
});

describe('v0.56.2 — 1. poignée de redimensionnement de la liste', () => {
  it("installée par initAtelierSplitters avec le même mécanisme que les autres ateliers", () => {
    const app = lire('static/app.js');
    const bloc = app.slice(app.indexOf('function initAtelierSplitters'),
                           app.indexOf('setTimeout(initAtelierSplitters'));
    // Même liste que Thème, Découpage en séquences et Évaluation (atelierInstallerSplitter,
    // largeur mémorisée en localStorage sous une clé « split:<atelier>:aside »).
    expect(bloc).toMatch(/\{ shell: '#atl-carte_mentale \.atl-shell', cle: 'split:atl-cm:aside' \}/);
    expect(bloc.indexOf("split:atl-cm:aside")).toBeGreaterThan(bloc.indexOf('const shellsSimples'));
    // Le template a bien la structure attendue (.atl-shell > .atl-sidebar + .atl-main).
    const html = lire('templates/index.html');
    const panneau = html.slice(html.indexOf('<div id="atl-carte_mentale"'), html.indexOf('/atl-carte_mentale'));
    expect(panneau).toMatch(/class="atl-shell"/);
    expect(panneau).toMatch(/<aside class="atl-sidebar">/);
    expect(panneau).toMatch(/class="atl-main"/);
  });

  it('la poignée posée sur ce panneau mémorise sa largeur comme ailleurs (localStorage)', () => {
    charger('atelier_commun.js');
    document.body.innerHTML = '<div id="atl-carte_mentale"><div class="atl-shell" style="display:flex">'
      + '<aside class="atl-sidebar"></aside><div class="atl-main"></div></div></div>';
    localStorage.setItem('split:atl-cm:aside', '320');
    globalThis.window.atelierInstallerSplitter({
      gauche: document.querySelector('#atl-carte_mentale .atl-sidebar'),
      droite: document.querySelector('#atl-carte_mentale .atl-main'),
      cleStockage: 'split:atl-cm:aside', largeurMinGauche: 200, largeurMinDroite: 300,
    });
    expect(document.querySelector('#atl-carte_mentale .atelier-splitter')).not.toBe(null);
    expect(document.querySelector('#atl-carte_mentale .atl-sidebar').style.flex).toBe('0 0 320px');
  });
});

describe('v0.56.2 — 2. aucune séquence choisie : toutes les séquences du niveau', () => {
  it('logique pure : identifiant avec la séquence, liste à plat, partie visée par « + Créer »', () => {
    expect(P.idToutes('S03', 2)).toBe('S03:2');
    expect(P.decouperId('S03:2')).toEqual({ sequence: 'S03', numero: '2' });
    expect(P.decouperId('2')).toEqual({ sequence: '', numero: '2' });
    const liste = P.elementsNiveau({ sequences: [
      { sequence: 'S01', modifiable: true, parties: [{ numero: 1, carte: { titre: 'a', latex: '', etat_code: 'valide' } },
                                                     { numero: 2, carte: null }] },
      { sequence: 'S02', modifiable: false, parties: [{ numero: 1, carte: null }] }] });
    expect(liste.map(e => e.id)).toEqual(['S01:1', 'S01:2', 'S02:1']);
    expect(liste[2]).toMatchObject({ sequence: 'S02', modifiable: false, presente: false });
    // La partie ouverte a déjà sa carte : première partie sans carte DE SA séquence.
    expect(P.cibleCreation(liste, { ...liste[0] }).id).toBe('S01:2');
    expect(P.cibleCreation(liste, { id: 'S02:9', sequence: 'S02', presente: true }).id).toBe('S02:1');
    // Mode séquence (éléments sans `sequence`) : comportement v0.56.1 inchangé.
    const simple = [P.element({ numero: 1, carte: { latex: '' } }), P.element({ numero: 2, carte: null })];
    expect(simple.map(e => e.id)).toEqual(['1', '2']);
    expect(P.cibleCreation(simple, simple[0]).numero).toBe(2);
  });

  it('la liste montre les parties de toutes les séquences, groupées, préfixe séquence/partie visible', async () => {
    await C.chargerListe();
    expect(appels.map(a => a.url)).toEqual(['/api/v2/livret-sequence/N09/cartes-mentales']);
    const liste = document.getElementById('atl-cm-list');
    expect(liste.querySelectorAll('.atl-list-groupe').length).toBe(2);       // S01, S02
    const txt = liste.textContent;
    expect(txt).toMatch(/N09\/S01\/P1/); expect(txt).toMatch(/N09\/S01\/P2/); expect(txt).toMatch(/N09\/S02\/P1/);
    expect(txt).toMatch(/Entiers/);
  });

  it('filtres d\'état et « Sans carte » toujours actifs', async () => {
    await C.chargerListe();
    C.filtreEtat = 'absente'; C.rendreSidebar();
    let txt = document.getElementById('atl-cm-list').textContent;
    expect(txt).not.toMatch(/S01\/P1/); expect(txt).toMatch(/S01\/P2/); expect(txt).toMatch(/S02\/P1/);
    C.filtreEtat = 'valide'; C.rendreSidebar();
    txt = document.getElementById('atl-cm-list').textContent;
    expect(txt).toMatch(/S01\/P1/); expect(txt).not.toMatch(/S02\/P1/);
  });

  it("ouvrir une entrée : GET, enregistrement et rendu sur l'URL de SA séquence ; l'entrée reste active", async () => {
    await C.chargerListe();
    await C.ouvrirItem('S01:1');
    expect(appels.at(-1).url).toBe('/api/v2/livret-sequence/N09/S01/cartes-mentales/1');
    expect(C.itemActif.id).toBe('S01:1');                  // identifiant de la liste
    expect(document.querySelector('#atl-cm-list .active, #atl-cm-list [class*="actif"]')).not.toBe(null);
    expect(document.getElementById('atl-cm-info').textContent).toMatch(/^S01 · Partie 1/);
    document.getElementById('atl-cm-titre').value = 'Nouveau';
    await C.sauvegarder();
    const patch = appels.find(a => a.method === 'PATCH');
    expect(patch.url).toBe('/api/v2/livret-sequence/N09/S01/cartes-mentales/1');
    expect(C.itemActif.id).toBe('S01:1');                  // toujours dans la liste rechargée
    expect(document.getElementById('atl-cm-form').style.display).not.toBe('none');
    // Rendu : « toute la séquence » porte sur la séquence de l'entrée ouverte.
    C._assurerToolbarRendu();
    document.getElementById('atl-cm-rendu-portee').value = 'sequence';
    await C.compilerRendu();
    expect(appels.at(-1).url)
      .toBe('/api/v2/livret-sequence/N09/S01/cartes-mentales/1/rendu-pdf?version=eleve&portee=sequence');
  });

  it('« + Créer » sur une partie sans carte : POST dans sa séquence, puis ouverture', async () => {
    await C.chargerListe();
    await C.ouvrirItem('S02:1');
    await C.nouvelItem();
    const post = appels.find(a => a.method === 'POST');
    expect(post.url).toBe('/api/v2/livret-sequence/N09/S02/cartes-mentales');
    expect(JSON.parse(post.body)).toEqual({ numero: 1 });
    expect(appels.at(-1).url).toBe('/api/v2/livret-sequence/N09/S02/cartes-mentales/1');
    expect(C.itemActif.id).toBe('S02:1');
    expect(C._seqCible).toBe('');
  });

  it('séquence validée : lecture seule pour ses entrées seulement', async () => {
    serveur('S02');
    const toasts = []; C.toast = m => toasts.push(m);
    await C.chargerListe();
    expect(document.getElementById('atl-cm-btn-creer').disabled).toBe(false);
    await C.ouvrirItem('S02:1');
    expect(document.getElementById('atl-cm-latex').disabled).toBe(true);
    await C.nouvelItem();
    expect(appels.some(a => a.method === 'POST')).toBe(false);
    expect(toasts.join(' ')).toMatch(/Séquence validée/);
    await C.ouvrirItem('S01:2');
    expect(document.getElementById('atl-cm-latex').disabled).toBe(false);
  });

  it('route serveur déclarée (liste du niveau)', () => {
    expect(lire('routes/livret_sequence.py'))
      .toMatch(/@bp\.route\('\/api\/v2\/livret-sequence\/<niveau>\/cartes-mentales', methods=\['GET'\]\)/);
  });
});

describe('v0.56.2 — 3. « Recompiler sans cache »', () => {
  it('Atelier.urlSansCache ajoute sans_cache=1 avec ? ou &', () => {
    const A = globalThis.window.Atelier;
    expect(A.urlSansCache('/x/rendu-pdf')).toBe('/x/rendu-pdf?sans_cache=1');
    expect(A.urlSansCache('/x/rendu-pdf?version=eleve')).toBe('/x/rendu-pdf?version=eleve&sans_cache=1');
    expect(A.urlSansCache('/x', false)).toBe('/x');
  });

  it("brique commune : le bouton est créé par AtelierEditeur._assurerToolbarRendu (pas de copie par atelier)", async () => {
    globalThis.window.ATL_FILTRE_SEQ = 'S01';
    await C.chargerListe();
    await C.ouvrirItem('1');
    C._assurerToolbarRendu();
    const b = document.getElementById('atl-cm-btn-compiler-sans-cache');
    expect(b).not.toBe(null);
    expect(b.textContent).toBe('Recompiler sans cache');
    // Un seul endroit du code crée ce bouton : atelier_editeur.js.
    for (const f of ['atelier_carte_mentale.js', 'atelier_exercice.js', 'atelier_evaluation_oo.js',
                     'atelier_fiche.js', 'atelier_notion.js', 'atelier_methode.js', 'atelier_carte_automatisme.js']) {
      expect(lire(join('static', f))).not.toMatch(/Recompiler sans cache/);
    }
    expect(lire('static/atelier_editeur.js')).toMatch(/btnSansCache\.textContent = 'Recompiler sans cache'/);
  });

  it('clic : compilation POST avec ?sans_cache=1 et les paramètres du rendu ; « Compiler » sans', async () => {
    globalThis.window.ATL_FILTRE_SEQ = 'S01';
    await C.chargerListe();
    await C.ouvrirItem('1');
    C._assurerToolbarRendu();
    document.getElementById('atl-cm-btn-compiler-sans-cache').click();
    await new Promise(r => setTimeout(r, 0));
    await new Promise(r => setTimeout(r, 0));
    const post = appels.filter(a => a.method === 'POST' && /rendu-pdf/.test(a.url)).at(-1);
    expect(post.url).toBe('/api/v2/livret-sequence/N09/S01/cartes-mentales/1/rendu-pdf?version=eleve&portee=partie&sans_cache=1');
    await C.compilerRendu();
    expect(appels.at(-1).url).not.toMatch(/sans_cache/);
  });

  it('atelier Séquence : case « Sans cache » appliquée à Compiler, au plan et à « Tout compiler »', async () => {
    const A = globalThis.window.ATELIER_SEQNIV;
    A.data = { sequence_par_niveau: { niveau: 'N09', sequence_code: 'S01' }, modele: { gabarit: 'sixieme' } };
    A._chargerResumeMer = () => {}; A.cmCharger = () => {};
    document.body.innerHTML = '<div id="asm-tab-rendu"></div>';
    A._assurerOngletRendu();
    const caseSC = document.getElementById('livret-seq-sans-cache');
    expect(caseSC).not.toBe(null);
    expect(A._urlCache('/api/v2/livret-sequence/N09/S01/tout-compiler')).toBe('/api/v2/livret-sequence/N09/S01/tout-compiler');
    caseSC.checked = true;
    expect(A._urlCache('/api/v2/livret-sequence/N09/S01/tout-compiler'))
      .toBe('/api/v2/livret-sequence/N09/S01/tout-compiler?sans_cache=1');
    const src = lire('static/atelier_seqniv_assemblage.js');
    expect(src).toMatch(/this\._urlCache\(P\.urlToutCompiler\(/);
    // v0.60.1 (D19) : livret et plan (le bloc « Carte mentale » est retiré).
    expect((src.match(/this\._urlCache\(`/g) || []).length).toBe(2);
  });

  it('Administration › Base de données : « Vider le cache des rendus PDF » avec confirmation et nombre de fichiers', async () => {
    const html = lire('templates/index.html');
    const bdd = html.slice(html.indexOf('<div id="admin-bdd"'), html.indexOf('<!-- Réinitialisation -->'));
    expect(bdd).toMatch(/Vider le cache des rendus PDF/);
    expect(bdd).toMatch(/onclick="adminCacheRendusVider\(\)"/);
    const app = lire('static/app.js');
    const f = app.slice(app.indexOf('async function adminCacheRendusVider'), app.indexOf('async function adminExportSqlite'));
    expect(f).toMatch(/window\.confirm\(/);
    expect(f).toMatch(/\/api\/admin\/cache-rendus\/vider/);
    expect(f).toMatch(/nb_fichiers/);
  });
});
