// tests_js/v0_59_3_multiselection_sequences.test.js — v0.59.3
//
// Demande de Laurent (17 novembre 2026, 22 h), doc/redemarrage_v0_59_3.md :
// « Ajouter la possibilité de sélectionner plusieurs séquences, comme ça je les
// repasse toutes "en cours" en une seule opération. »
//
// L'atelier Séquence (niveau), sans séquence choisie (« — Toutes les séquences — »),
// liste les séquences du niveau avec la multisélection d'AtelierEditeur, sans
// copie : l'atelier ne fournit que des crochets (chargerListe, rendreItem, urlEtat,
// raisonHorsEtat, libelleItem, avertissementEtatGroupe). Chaque séquence change
// d'état par la route UNITAIRE PATCH …/<id>/etat (mêmes règles qu'une par une).
//
// Et, dans l'atelier Référentiel (Laurent, 22 h 15 et 22 h 22) : poignée de
// largeur comme les autres ateliers, explication du modèle en infobulle.

import { describe, it, expect, beforeAll, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const lire = rel => readFileSync(join(__dirname, '..', rel), 'utf-8');
function charger(rel) { new Function(lire(join('static', rel)))(); }   // eslint-disable-line no-new-func
const json = (d, status = 200) => new Response(JSON.stringify(d), { status, headers: { 'Content-Type': 'application/json' } });

const HTML = `<span id="liv-atl-sidebar-titre"></span><span id="liv-atl-sidebar-hint"></span>
  <div id="liv-atl-sidebar-body"></div>
  <span id="liv-atl-badge-modifie"></span><span id="liv-atl-etat-badge"></span>
  <button id="liv-atl-btn-valider"></button><button id="liv-atl-btn-save"></button>
  <div id="asm-tab-edition"></div><div id="asm-tab-rendu"></div>
  <button id="asm-tab-btn-edition"></button><button id="asm-tab-btn-rendu"></button>`;

// N11 comme chez Laurent : A1…E1 validées (2027_N11 validé), une archive X03,
// 2025_N11b verrouillé (instantané en codes S, ne contient pas A1…).
const REFS = [
  { id: '2025_N11b', nom: '4e — 2025-2026 — Principal b', etat: 'verrouille', type_ref: 'principal', fige: true },
  { id: '2027_N11', nom: '4e — 2027-2028 — Principal', etat: 'valide', type_ref: 'principal', fige: false },
];
const seq = (id, code, etat, per = 'principal') => ({
  id, code, nom: 'Séquence ' + code, numero: 0, etat_code: etat, perimetre: per,
  referentiels_vivants: per === 'principal' ? ['2027_N11'] : [], referentiels_figes: [] });

let S, P, appels, toasts, confirmations, etats, refuse;
beforeAll(() => {
  globalThis.window.atelGardeEnregistrer = globalThis.window.atelGardeEnregistrer || (() => {});
  charger('atelier.js');
  charger('atelier_editeur.js');
  charger('atelier_assemblage.js');
  charger('seqniv_pur.js');
  charger('atelier_seqniv_assemblage.js');
  S = globalThis.window.ATELIER_SEQNIV;
  P = globalThis.window.SeqnivPur;
});

function serveur() {
  globalThis.fetch = async (url, init) => {
    const method = (init && init.method) || 'GET';
    const body = init && init.body ? JSON.parse(init.body) : undefined;
    appels.push({ url, method, body });
    if (url === '/api/v2/sequences-par-niveau?niveau=N11') {
      return json({ niveau: 'N11', referentiels: REFS, sequences: [
        seq('sa1', 'A1', etats.sa1), seq('sa2', 'A2', etats.sa2), seq('sb1', 'B1', etats.sb1),
        seq('sx3', 'X03', etats.sx3, 'archive')] });
    }
    const m = /^\/api\/v2\/sequences-par-niveau\/(\w+)\/etat$/.exec(url);
    if (m && method === 'PATCH') {
      if (body.etat_code === 'valide' && refuse[m[1]]) {
        return json({ error: "La séquence ne peut pas être validée en l'état.",
                      code: 'validation_pedagogique_echec', raisons: refuse[m[1]] }, 400);
      }
      etats[m[1]] = body.etat_code;
      return json({ id: m[1], etat_code: body.etat_code });
    }
    return json({});
  };
}

beforeEach(() => {
  appels = []; toasts = []; confirmations = [];
  etats = { sa1: 'valide', sa2: 'valide', sb1: 'valide', sx3: 'en_cours' };
  refuse = {};
  document.body.innerHTML = HTML;
  S.selectionMulti.clear(); S.ancreSelectionId = null; S._niveauListe = undefined;
  S.toast = (m, niveau) => toasts.push({ m, niveau: niveau || 'info' });
  globalThis.window.ATL_FILTRE_NIVEAU = 'N11';
  globalThis.window.ATL_FILTRE_SEQ = '';
  globalThis.window.confirm = (m) => { confirmations.push(m); return true; };
  serveur();
});

const ev = (mods = {}) => ({ preventDefault() {}, clientX: 10, clientY: 10, ...mods });
const patchs = () => appels.filter(a => a.method === 'PATCH');

describe('v0.59.3 — 1. « Toutes les séquences » : la liste des séquences du niveau', () => {
  it("rafraichir() sans séquence liste les séquences (au lieu d'un atelier vide)", async () => {
    await S.rafraichir();
    const items = [...document.querySelectorAll('#liv-atl-list .asm-item')];
    expect(items.map(e => e.getAttribute('data-item-id'))).toEqual(['sa1', 'sa2', 'sb1', 'sx3']);
    expect(document.getElementById('liv-atl-sidebar-titre').textContent).toBe('Séquences');
    expect(items[0].getAttribute('onclick')).toBe("ATELIER_SEQNIV.gererClicItem(event, 'sa1')");
    expect(items[0].getAttribute('oncontextmenu')).toBe("ATELIER_SEQNIV.gererClicDroitItem(event, 'sa1')");
    expect(items[3].textContent).toMatch(/archive/);
    // Le panneau central rappelle les gestes et les référentiels du niveau.
    const centre = document.getElementById('asm-tab-edition').textContent;
    expect(centre).toMatch(/4 séquence\(s\), dont 3 validée\(s\)/);
    expect(centre).toMatch(/2025_N11b/);
    // initLivret ne vide plus l'atelier quand seul le niveau est choisi.
    const app = lire('static/app.js');
    const init = app.slice(app.indexOf('async function initLivret'), app.indexOf('// ── Administration — Import .tex'));
    expect(init).toMatch(/if \(!ATL_FILTRE_NIVEAU\) \{/);
  });

  it('aucune réimplémentation : les méthodes de sélection viennent d\'AtelierEditeur', () => {
    const src = lire('static/atelier_seqniv_assemblage.js');
    expect(src).not.toMatch(/selectionMulti(AppliquerEtat|Toggle|Plage|OuvrirMenu|Effacer)\s*\([^)]*\)\s*\{/);
    expect(S.selectionMultiAppliquerEtat).toBe(globalThis.window.AtelierEditeur.prototype.selectionMultiAppliquerEtat);
    expect(lire('static/atelier_editeur.js')).toMatch(/'ATELIER_SEQNIV'[,\]]/);   // Échap (v0.60.1 : + ATELIER_EVALUATION après lui)
  });

  it('mêmes gestes : Ctrl+clic, Maj+clic (plage), barre « ✓ Valider / ⟲ En cours », Échap', async () => {
    await S.rafraichir();
    S.gererClicItem(ev({ ctrlKey: true }), 'sa1');
    S.gererClicItem(ev({ shiftKey: true }), 'sb1');
    expect([...S.selectionMulti]).toEqual(['sa1', 'sa2', 'sb1']);
    expect(document.querySelector('[data-item-id="sa2"]').classList.contains('asm-item--selected')).toBe(true);
    const barre = document.getElementById('liv-atl-selection-toolbar');
    expect(barre.style.display).toBe('flex');
    expect(barre.textContent).toMatch(/3 sélectionnés/);
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(S.selectionMulti.size).toBe(0);
  });

  it('clic simple : ouvre la séquence (sélecteur de séquence de la portée)', async () => {
    await S.rafraichir();
    const sauvees = [];
    globalThis.window.ATL_SELECTIONS = { sequence: { niveau: 'N11', sequence: '' } };
    globalThis.window.atelSauverSelections = (p, sel) => sauvees.push([p, { ...sel }]);
    let rendu = 0;
    globalThis.window.atelRenderSelecteursPortee = () => { rendu += 1; };
    S.gererClicItem(ev(), 'sa2');
    expect(sauvees).toEqual([['sequence', { niveau: 'N11', sequence: 'A2' }]]);
    expect(rendu).toBe(1);
    expect(S.selectionMulti.size).toBe(0);
  });
});

describe('v0.59.3 — 2. actions groupées sur les séquences', () => {
  it('repasser en cours : avertissement d\'abord, puis un PATCH unitaire par séquence', async () => {
    await S.rafraichir();
    ['sa1', 'sa2', 'sb1'].forEach(id => S.selectionMultiToggleId(id));
    await S.selectionMultiAppliquerEtat('en_cours');
    expect(confirmations.length).toBe(1);
    const m = confirmations[0];
    expect(m).toMatch(/Repasser 3 séquences « en cours » : A1, A2, B1\./);
    expect(m).toMatch(/2027_N11 \(4e — 2027-2028 — Principal\)/);        // validé : retombera en cours
    expect(m).toMatch(/Les référentiels verrouillés ne changent pas/);
    expect(patchs().map(a => [a.url, a.body])).toEqual([
      ['/api/v2/sequences-par-niveau/sa1/etat', { etat_code: 'en_cours' }],
      ['/api/v2/sequences-par-niveau/sa2/etat', { etat_code: 'en_cours' }],
      ['/api/v2/sequences-par-niveau/sb1/etat', { etat_code: 'en_cours' }],
    ]);
    expect(toasts.at(-1)).toEqual({ m: '3 repassé en cours', niveau: 'info' });
    // La liste est rechargée : les pastilles suivent.
    expect(document.querySelector('[data-item-id="sa1"] .atome-etat--en_cours')).not.toBe(null);
  });

  it('annuler l\'avertissement : rien n\'est envoyé', async () => {
    await S.rafraichir();
    globalThis.window.confirm = () => false;
    S.selectionMultiToggleId('sa1');
    await S.selectionMultiAppliquerEtat('en_cours');
    expect(patchs()).toEqual([]);
  });

  it('revalider en groupe : pas d\'avertissement ; refus comptés avec la séquence et sa raison', async () => {
    etats = { sa1: 'en_cours', sa2: 'en_cours', sb1: 'valide', sx3: 'en_cours' };
    refuse = { sa2: ["L'objectif 03 n'a pas de fiche de résumé."] };
    await S.rafraichir();
    ['sa1', 'sa2', 'sb1', 'sx3'].forEach(id => S.selectionMultiToggleId(id));
    await S.selectionMultiAppliquerEtat('valide');
    expect(confirmations).toEqual([]);
    expect(patchs().map(a => a.url)).toEqual(['/api/v2/sequences-par-niveau/sa1/etat',
                                              '/api/v2/sequences-par-niveau/sa2/etat']);
    expect(toasts.at(-1)).toEqual({
      m: "1 validé, 1 déjà à jour, 1 ignoré (archive, hors référentiel), 1 en échec : "
        + "A2 : La séquence ne peut pas être validée en l'état. — L'objectif 03 n'a pas de fiche de résumé.",
      niveau: 'erreur' });
  });

  it('avertissement : référentiel verrouillé contenant les séquences cité (cas 2026_N09)', () => {
    const data = { referentiels: [{ id: '2026_N09', nom: '6e — 2026-2027 — Principal', etat: 'verrouille', fige: true }] };
    const m = P.avertissementRepasserSequences(
      [{ code: 'A2', referentiels_vivants: [], referentiels_figes: ['2026_N09'] }], data);
    expect(m).toMatch(/^Repasser 1 séquence « en cours » : A2\./);
    expect(m).toMatch(/Référentiel verrouillé contenant cette séquence, qui ne change pas/);
    expect(m).toMatch(/2026_N09 \(6e — 2026-2027 — Principal\)/);
    expect(m).not.toMatch(/repassera/);
    expect(P.avertissementRepasserSequences([], data)).toBe(null);
  });

  it('les ateliers d\'atomes gardent leur comportement (crochets neutres par défaut)', () => {
    const E = globalThis.window.AtelierEditeur.prototype;
    expect(E.avertissementEtatGroupe('en_cours', [{}])).toBe(null);
    expect(E.libelleItem({ code: 'A1' })).toBe('');
  });
});

describe('v0.59.3 — 3. atelier Référentiel : poignée et infobulle du modèle', () => {
  it('poignée de largeur : même mécanisme et même mémorisation que les autres ateliers', () => {
    const app = lire('static/app.js');
    const bloc = app.slice(app.indexOf('function initAtelierSplitters'), app.indexOf('setTimeout(initAtelierSplitters'));
    expect(bloc).toMatch(/\{ shell: '#atl-referentiel \.atl-shell', cle: 'split:atl-referentiel:aside' \}/);
    expect(bloc.indexOf('split:atl-referentiel:aside')).toBeGreaterThan(bloc.indexOf('const shellsSimples'));
    const html = lire('templates/index.html');
    const panneau = html.slice(html.indexOf('<div id="atl-referentiel"'), html.indexOf('id="atl-ref-main"'));
    expect(panneau).toMatch(/class="atl-shell"/);
    expect(panneau).toMatch(/<aside class="atl-sidebar" id="atl-ref-sidebar">/);
    // Installée sur ce panneau, la poignée relit la largeur mémorisée.
    charger('atelier_commun.js');
    document.body.innerHTML = '<div id="atl-referentiel"><div class="atl-shell" style="display:flex">'
      + '<aside class="atl-sidebar" id="atl-ref-sidebar"></aside><section class="atl-main"></section></div></div>';
    localStorage.setItem('split:atl-referentiel:aside', '420');
    globalThis.window.atelierInstallerSplitter({
      gauche: document.getElementById('atl-ref-sidebar'),
      droite: document.querySelector('#atl-referentiel .atl-main'),
      cleStockage: 'split:atl-referentiel:aside', largeurMinGauche: 200, largeurMinDroite: 300 });
    expect(document.querySelector('#atl-referentiel .atelier-splitter')).not.toBe(null);
    expect(document.getElementById('atl-ref-sidebar').style.flex).toBe('0 0 420px');
  });

  it('explication du modèle : infobulle sur un bouton ⓘ focusable, au survol et au focus', () => {
    const html = lire('templates/index.html');
    const bloc = html.slice(html.indexOf('id="refu-c-modele-bloc"'), html.indexOf('id="refu-c-cartes-bloc"'));
    expect(bloc).toMatch(/<button type="button" class="refu-info" id="refu-c-modele-info"/);
    expect(bloc).toMatch(/aria-describedby="refu-c-modele-desc">ⓘ<\/button>\s*<div id="refu-c-modele-desc" class="refu-modele-desc refu-infobulle" role="tooltip"><\/div>/);
    const css = lire('static/app.css');
    expect(css).toMatch(/\.refu-infobulle \{ display: none;/);
    expect(css).toMatch(/\.refu-info:hover \+ \.refu-infobulle, \.refu-info:focus \+ \.refu-infobulle/);
  });
});
