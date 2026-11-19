// tests_js/v0_60_1_suite_fiches.test.js — v0.60.1
//
// Interface de la suite de la version 2 du modèle Fiches (doc/redemarrage_v0_60_1.md) :
//   - TC : titre court saisi dans l'onglet Édition de l'assemblage (séquences du
//     principal ; lecture seule pour une séquence validée) et envoyé à la route ;
//   - D18b : mode de mise en route envoyé à la création (principal seulement) ;
//     onglet : lecture seule quand le référentiel est figé ;
//   - D17b, D-SE : cadre des rituels (choix des tests courts, séance d'évaluation) ;
//   - C11 : identifiant d'un exercice avec sa séquence en « toutes les séquences »,
//     règles CSS sur #atl-exercice-form, rendu par lot (cartes mentales, sans cache) ;
//   - C12b : exemples « A1 » au lieu de « S01 ».

import { describe, it, expect, beforeAll, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const lire = rel => readFileSync(join(__dirname, '..', rel), 'utf-8');
function charger(rel) { new Function(lire(join('static', rel)))(); }   // eslint-disable-line no-new-func

describe('TC — titre court dans l\'assemblage', () => {
  let A, appels;
  beforeAll(() => {
    globalThis.window.atelGardeEnregistrer = globalThis.window.atelGardeEnregistrer || (() => {});
    charger('atelier.js');
    charger('atelier_editeur.js');
    charger('atelier_assemblage.js');
    charger('seqniv_pur.js');
    charger('atelier_seqniv_assemblage.js');
    A = globalThis.window.ATELIER_SEQNIV;
  });
  beforeEach(() => {
    appels = [];
    globalThis.fetch = async (url, init) => {
      appels.push({ url, method: (init && init.method) || 'GET', body: init && init.body });
      return new Response(JSON.stringify({ id: 'sn1', titre_court: 'Nombres relatifs' }),
                          { status: 200, headers: { 'Content-Type': 'application/json' } });
    };
  });

  it('champ affiché pour une séquence du principal, envoyé à la route, absent pour Mnn/Xnn', async () => {
    const sn = { id: 'sn1', niveau: 'N11', sequence_code: 'A1', sequence_nom: 'Nombres', titre_court: '' };
    document.body.innerHTML = A._rendreTitreCourt(sn);
    const champ = document.getElementById('asm-titre-court');
    expect(champ.placeholder).toBe('Nombres');
    expect(champ.disabled).toBe(false);
    A.data = { sequence_par_niveau: sn };
    A._status = () => {};
    champ.value = '  Nombres relatifs ';
    await A.enregistrerTitreCourt();
    expect(appels[0].method).toBe('PUT');
    expect(appels[0].url).toBe('/api/v2/sequences-par-niveau/sn1/titre-court');
    expect(JSON.parse(appels[0].body)).toEqual({ titre_court: '  Nombres relatifs ' });
    expect(champ.value).toBe('Nombres relatifs');
    expect(A._rendreTitreCourt({ ...sn, sequence_code: 'M03' })).toBe('');
    expect(A._rendreTitreCourt({ ...sn, sequence_code: 'X02' })).toBe('');
  });

  it('séquence validée : champ en lecture seule, sans bouton', () => {
    document.body.innerHTML = A._rendreTitreCourt({ id: 's', sequence_code: 'B2', etat_code: 'valide' });
    expect(document.getElementById('asm-titre-court').disabled).toBe(true);
    expect(document.body.innerHTML).not.toMatch(/enregistrerTitreCourt/);
  });

  it('D19 — onglet Rendu PDF sans bloc « Carte mentale »', () => {
    A.data = { sequence_par_niveau: { niveau: 'N11', sequence_code: 'A1' }, modele: { gabarit: 'sixieme' } };
    A._chargerResumeMer = () => {};
    document.body.innerHTML = '<div id="asm-tab-rendu"></div>';
    A._assurerOngletRendu();
    expect(document.getElementById('livret-seq-cm')).toBe(null);
    expect(document.getElementById('livret-seq-btn-pdf')).not.toBe(null);
  });
});

describe('D18b — mode de mise en route', () => {
  beforeAll(() => {
    globalThis.escapeHtml = globalThis.escapeHtml || (s => String(s).replace(/&/g, '&amp;')
      .replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'));
    // Fonctions de création et de l'onglet, extraites du fichier.
    const src = lire('static/referentiel_unifie.js');
    const fonctions = ['_refuE', 'refuChoixMer', 'refuMerHtml'].map(nom => {
      const m = src.match(new RegExp(`function ${nom}\\([^)]*\\) \\{[\\s\\S]*?\\n\\}\\n`));
      if (!m) throw new Error(`${nom} introuvable`);
      return m[0];
    }).join('\n');
    new Function(`${fonctions}; Object.assign(globalThis, { _refuE, refuChoixMer, refuMerHtml });`)();   // eslint-disable-line no-new-func
  });

  it('création : envoyé pour un principal (MER désignée si progression), jamais pour une MER', () => {
    const html = lire('templates/index.html');
    const bloc = html.slice(html.indexOf('<label id="refu-c-mer-bloc"'), html.indexOf('<input id="refu-c-desc"'));
    document.body.innerHTML = bloc;
    expect(globalThis.refuChoixMer('principal')).toEqual({});
    document.getElementById('refu-c-mer-mode').value = 'progression';
    document.getElementById('refu-c-mer-ref').innerHTML = '<option value="2026_N09b">2026_N09b</option>';
    expect(globalThis.refuChoixMer('principal')).toEqual({ mise_en_route: 'progression', mer_referentiel: '2026_N09b' });
    expect(globalThis.refuChoixMer('mer')).toEqual({});
    document.getElementById('refu-c-mer-mode').value = 'cartes';
    expect(globalThis.refuChoixMer('principal')).toEqual({ mise_en_route: 'cartes' });
  });

  it('onglet : modifiable (bouton) ou lecture seule quand le référentiel est figé', () => {
    const d = { mode: 'progression', mer: 'M', mers: [{ id: 'M' }], modifiable: true };
    document.body.innerHTML = globalThis.refuMerHtml(d);
    expect(document.getElementById('refu-mer-mode').value).toBe('progression');
    expect(document.getElementById('refu-mer-ref').style.display).toBe('');
    expect(document.body.innerHTML).toMatch(/refuMerEnregistrer/);
    document.body.innerHTML = globalThis.refuMerHtml({ ...d, mode: 'cartes', modifiable: false });
    expect(document.getElementById('refu-mer-mode').disabled).toBe(true);
    expect(document.getElementById('refu-mer-ref').style.display).toBe('none');
    expect(document.body.innerHTML).toMatch(/lecture seule/);
  });
});

// v0.60.2 — cadre des rituels (D17b, D-SE) retiré de l'atelier Référentiel :
// voir v0_60_2_rituels_hors_atelier.test.js (routes et service gardés).

describe('C11, C12b — petits manques', () => {
  it('exercice en « toutes les séquences » : la séquence entre dans l\'identifiant', () => {
    globalThis.window.atelGardeEnregistrer = () => {};
    globalThis.window.atelLiensEnTags = () => [];
    charger('atelier.js');
    charger('atelier_editeur.js');
    charger('atelier_exercice.js');
    const ex = globalThis.window.ATELIER_EXERCICE;
    globalThis.window.ATL_FILTRE_NIVEAU = 'N11';
    globalThis.window.ATL_FILTRE_SEQ = '';
    expect(ex.rendreItem({ id: 'e1', code: 'F01', titre: 'T', sequence: 'A3' }, 'F')).toMatch(/N11\/A3\//);
    globalThis.window.ATL_FILTRE_SEQ = 'A3';
    expect(ex.rendreItem({ id: 'e1', code: 'F01', titre: 'T', sequence: 'B1' }, 'F')).toMatch(/N11\/A3\//);
  });

  it('règles CSS sur #atl-exercice-form (l\'identifiant #atl-exo-form n\'existe pas)', () => {
    const css = lire('static/app.css');
    expect(css).not.toMatch(/#atl-exo-form/);
    expect(css).toMatch(/body\.atelier-mode-split #atl-exercice-form,/);
    expect(css).toMatch(/#atl-exercice-form \.atl-cadre \{/);
    expect(lire('templates/index.html')).toMatch(/id="atl-exercice-form"/);
  });

  it('rendu par lot : type « Cartes mentales » et case « Sans cache » transmise', () => {
    const html = lire('templates/index.html');
    const t = html.slice(html.indexOf('<select id="rdl-filtre-type"'));
    expect(t.slice(0, t.indexOf('</select>'))).toMatch(/<option value="carte_mentale">Cartes mentales<\/option>/);
    expect(html).toMatch(/<input type="checkbox" id="rdl-sans-cache">/);
    const app = lire('static/app.js');
    expect(app).toMatch(/if \(p\.sans_cache\) qs\.set\('sans_cache', '1'\);/);
    expect(app).toMatch(/d\.par_type\.carte_mentale/);
  });

  it('exemples de codes de séquence en « A1 » (plus de « S01 » dans les placeholders)', () => {
    expect(lire('templates/index.html')).not.toMatch(/placeholder="S01"/);
    expect(lire('static/ateliers_seqniv_v2_edit.js')).not.toMatch(/placeholder="S01"/);
    expect(lire('static/app.js')).toMatch(/sequence: 'A1' \}/);
  });
});

describe('Module Évaluations — multisélection (réimport des tests courts)', () => {
  let E, appels;
  beforeAll(() => {
    globalThis.window.atelGardeEnregistrer = globalThis.window.atelGardeEnregistrer || (() => {});
    charger('atelier.js');
    charger('atelier_editeur.js');
    charger('atelier_assemblage.js');
    charger('atelier_evaluation_oo.js');
    E = globalThis.window.ATELIER_EVALUATION;
  });
  beforeEach(() => {
    appels = [];
    globalThis.fetch = async (url, init) => {
      appels.push({ url, method: (init && init.method) || 'GET', body: init && init.body });
      return new Response(JSON.stringify({ evaluations: E.liste, evaluation: {} }),
                          { status: 200, headers: { 'Content-Type': 'application/json' } });
    };
    document.body.innerHTML = '<div><div id="atl-eval-list"></div></div>';
    E.liste = [{ id: 'e1', numero: 1, titre: 'Évaluation', etat_code: 'valide' },
               { id: 'e2', numero: 2, titre: 'Test court', etat_code: 'valide' },
               { id: 'e3', numero: 3, titre: 'Autre', etat_code: 'en_cours' }];
    E.selectionMulti.clear();
    E.filtreEtat = '';
    E._niveau = () => 'N11';
  });

  it('Maj+clic sélectionne une plage, « ⟲ En cours » passe par PATCH …/etat', async () => {
    E._rendreSidebar();
    expect(document.querySelector('[data-id="e1"]').getAttribute('onclick')).toMatch(/clicListe/);
    E.clicListe({ ctrlKey: true, preventDefault() {} }, 'e1');
    E.clicListe({ shiftKey: true, preventDefault() {} }, 'e3');
    expect([...E.selectionMulti]).toEqual(['e1', 'e2', 'e3']);
    expect(document.querySelector('[data-id="e2"]').className).toMatch(/selected/);
    expect(document.getElementById('atl-eval-selection-toolbar').innerHTML).toMatch(/En cours/);
    E.toast = () => {};
    await E.selectionMultiAppliquerEtat('en_cours');
    const patchs = appels.filter(a => a.method === 'PATCH');
    expect(patchs.map(a => a.url)).toEqual(['/api/evaluations/e1/etat', '/api/evaluations/e2/etat']);
    expect(JSON.parse(patchs[0].body)).toEqual({ etat_code: 'en_cours' });
  });

  it('clic simple : ouvre l\'évaluation et vide la sélection', () => {
    let ouverte = null;
    E.selectionner = id => { ouverte = id; };
    E.selectionMulti.add('e2');
    E.clicListe({}, 'e1');
    expect(ouverte).toBe('e1');
    expect(E.selectionMulti.size).toBe(0);
  });
});
