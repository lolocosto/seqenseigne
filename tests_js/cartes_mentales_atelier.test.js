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

  it('Rendu PDF : bloc de compilation pour toute séquence principale (tous modèles), pas pour une mise en route', () => {
    ongletPour('S01', 'sixieme');
    expect(document.getElementById('livret-seq-cm').style.display).toBe('flex');
    ongletPour('S01', 'cycle4');
    expect(document.getElementById('livret-seq-cm').style.display).toBe('flex');
    ongletPour('M02', 'sixieme');
    expect(document.getElementById('livret-seq-cm').style.display).toBe('none');
  });

  it("Rendu PDF : plus d'éditeur, un lien vers l'atelier Carte mentale", async () => {
    ongletPour('S01', 'sixieme');
    expect(document.getElementById('livret-seq-cm-editeur')).toBe(null);
    expect(document.getElementById('livret-seq-cm-latex')).toBe(null);
    let ouvert = null;
    globalThis.window.atelSwitch = p => { ouvert = p; };
    A.cmOuvrirAtelier();
    expect(ouvert).toBe('carte_mentale');
    await A.cmCharger();
    expect(document.getElementById('livret-seq-cm-etat').textContent).toBe('1 carte(s) sur 2 partie(s)');
  });
});

describe("v0.55.0 — atelier « Carte mentale » (portée Séquence)", () => {
  let C, P, appels;
  const HTML = `<div id="atl-cm-liste"></div><div id="atl-cm-titre-partie"></div>
    <input id="atl-cm-titre"><select id="atl-cm-etat-code"><option value="en_cours">e</option><option value="valide">v</option></select>
    <textarea id="atl-cm-latex"></textarea><button id="atl-cm-btn-enregistrer"></button>
    <button id="atl-cm-btn-voir"></button><button id="atl-cm-btn-supprimer"></button><span id="atl-cm-message"></span>
    <select id="atl-cm-version"><option value="eleve">e</option><option value="corrigee">c</option></select>
    <select id="atl-cm-portee"><option value="partie">p</option><option value="sequence">s</option></select>
    <span id="atl-cm-rendu-etat"></span><iframe id="atl-cm-pdf"></iframe>`;
  beforeAll(() => {
    charger('atelier_carte_mentale.js');
    C = globalThis.window.ATELIER_CARTE_MENTALE;
    P = globalThis.window.CarteMentalePur;
  });
  beforeEach(() => {
    appels = [];
    document.body.innerHTML = HTML;
    globalThis.window.ATL_FILTRE_NIVEAU = 'N11';
    globalThis.window.ATL_FILTRE_SEQ = 'S04';
    globalThis.URL.createObjectURL = () => 'blob:x';
    globalThis.fetch = async (url, init) => {
      appels.push({ url, method: (init && init.method) || 'GET', body: init && init.body });
      if (/cartes-mentales$/.test(url)) {
        return new Response(JSON.stringify({ modifiable: true, parties: [
          { numero: 1, libelle: '', carte: { titre: 'Calcul littéral', etat_code: 'valide',
            latex: '\\begin{seqCarteMentaleSix}{T}\\seqCMBranche{a}{b}\\seqCMBranche{c}{d}\\end{seqCarteMentaleSix}' } },
          { numero: 2, libelle: '', carte: null }] }), { status: 200 });
      }
      if (/rendu-pdf/.test(url)) return new Response(new Blob(['%PDF']), { status: 200 });
      return new Response(JSON.stringify({ etat: 'créée', avertissements: [] }), { status: 200 });
    };
  });

  it('logique pure : branches, URL de liste, de partie et du PDF', () => {
    expect(P.nbBranches('\\seqCMBranche{a}{b}\\seqCMBranche{c}{d}\\seqCMBranches')).toBe(2);
    expect(P.urlListe('N11', 'S04', 2)).toBe('/api/v2/livret-sequence/N11/S04/cartes-mentales/2');
    expect(P.urlPdf('N11', 'S04', 'corrigee', 1))
      .toBe('/api/v2/livret-sequence/N11/S04/rendu-pdf?document=cartes_mentales&version=corrigee&partie=1');
    expect(P.urlPdf('N11', 'S04', 'eleve', '')).toBe('/api/v2/livret-sequence/N11/S04/rendu-pdf?document=cartes_mentales&version=eleve');
  });

  it("liste les parties d'une séquence (tout modèle) avec l'état et le nombre de branches", async () => {
    await C.chargerListe();
    const txt = document.getElementById('atl-cm-liste').textContent;
    expect(txt).toMatch(/Partie 1/); expect(txt).toMatch(/validée · 2 branche\(s\)/);
    expect(txt).toMatch(/Partie 2/); expect(txt).toMatch(/sans carte/);
    expect(document.getElementById('atl-cm-titre').value).toBe('Calcul littéral');
    C.choisir(2);
    expect(document.getElementById('atl-cm-latex').value).toMatch(/seqCarteMentaleSix/);   // modèle proposé
    expect(document.getElementById('atl-cm-btn-supprimer').disabled).toBe(true);
  });

  it('Enregistrer et voir : PUT sur la partie choisie puis PDF de cette partie', async () => {
    await C.chargerListe();
    C.choisir(2);
    document.getElementById('atl-cm-titre').value = 'Nouvelle';
    document.getElementById('atl-cm-version').value = 'corrigee';
    await C.enregistrer(true);
    const put = appels.find(a => a.method === 'PUT');
    expect(put.url).toBe('/api/v2/livret-sequence/N11/S04/cartes-mentales/2');
    expect(JSON.parse(put.body).titre).toBe('Nouvelle');
    expect(appels.at(-1).url).toMatch(/rendu-pdf\?document=cartes_mentales&version=corrigee&partie=2$/);
  });

  it('Compiler toutes les cartes de la séquence : sans partie', async () => {
    await C.chargerListe();
    document.getElementById('atl-cm-portee').value = 'sequence';
    await C.compiler();
    expect(appels.at(-1).url).toBe('/api/v2/livret-sequence/N11/S04/rendu-pdf?document=cartes_mentales&version=eleve');
  });

  it("l'atelier est déclaré dans la portée Séquence, avec son init et son rechargement sur filtre", () => {
    const app = lire('static/app.js');
    expect(app).toMatch(/'carte_automatisme', 'carte_mentale',/);
    expect(app).toMatch(/carte_mentale:\s+'atelCarteMentaleInit'/);
    expect(lire('static/atelier_filtres_hook.js')).toMatch(/'carte_mentale':\s+'ATELIER_CARTE_MENTALE'/);
    const html = lire('templates/index.html');
    expect(html).toMatch(/id="atl-btn-carte_mentale"/);
    expect(html).toMatch(/id="atl-carte_mentale"/);
    expect(html).toMatch(/atelier_carte_mentale\.js/);
  });
});
