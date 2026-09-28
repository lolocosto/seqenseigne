// tests_js/apercu_survol.test.js — v0.17.3
//
// Aperçu PDF au survol dans AtelierAssemblage : armement/désarmement du timer
// (1500 ms), anti-empilement via _apercuGen, modale unique, branchement
// hybride (cache_valide → affichage ; sinon → bouton Générer).

import { describe, it, expect, beforeAll, beforeEach, afterEach, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

function charger(rel) {
  const code = readFileSync(join(__dirname, '..', 'static', rel), 'utf-8');
  // eslint-disable-next-line no-new-func
  new Function(code)();
}

beforeAll(() => {
  globalThis.window.atelToast = globalThis.window.atelToast || (() => {});
  charger('atelier.js');
  charger('atelier_editeur.js');
  charger('atelier_assemblage.js');
});

function nouvelAssemblage() {
  const A = new globalThis.window.AtelierAssemblage({
    id: 'test-asm', prefixe: 'tasm', endpointBase: '/api/tests',
  });
  // Neutralise le viewer pdf.js (non pertinent ici).
  A._afficherPdfDansViewer = vi.fn();
  return A;
}

describe('AtelierAssemblage — aperçu au survol', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('délai par défaut = 1500 ms', () => {
    expect(globalThis.window.AtelierAssemblage.DELAI_APERCU_MS).toBe(1500);
  });

  it('_installerApercuSurvol est idempotent (dataset)', () => {
    const A = nouvelAssemblage();
    const c = document.createElement('div');
    A._installerApercuSurvol(c);
    A._installerApercuSurvol(c);
    expect(c.dataset.apercuInstalle).toBe('1');
  });

  it('armer puis désarmer avant 1500 ms → aucun déclenchement', () => {
    const A = nouvelAssemblage();
    const spy = vi.spyOn(A, '_declencherApercu').mockImplementation(() => {});
    const el = document.createElement('div');
    el.setAttribute('data-atome-type', 'exercice');
    el.setAttribute('data-atome-id', 'ex_1');
    A._armerApercu(el);
    vi.advanceTimersByTime(1000);
    A._desarmerApercu();
    vi.advanceTimersByTime(1000);
    expect(spy).not.toHaveBeenCalled();
  });

  it('armer et laisser filer 1500 ms → déclenche avec (type, id)', () => {
    const A = nouvelAssemblage();
    const spy = vi.spyOn(A, '_declencherApercu').mockImplementation(() => {});
    const el = document.createElement('div');
    el.setAttribute('data-atome-type', 'notion');
    el.setAttribute('data-atome-id', 'no_9');
    A._armerApercu(el);
    vi.advanceTimersByTime(1500);
    expect(spy).toHaveBeenCalledWith('notion', 'no_9', el);
  });

  it('réarmer remplace le timer précédent (un seul actif)', () => {
    const A = nouvelAssemblage();
    const spy = vi.spyOn(A, '_declencherApercu').mockImplementation(() => {});
    const el1 = document.createElement('div');
    el1.setAttribute('data-atome-type', 'exercice');
    el1.setAttribute('data-atome-id', 'ex_1');
    const el2 = document.createElement('div');
    el2.setAttribute('data-atome-type', 'fiche');
    el2.setAttribute('data-atome-id', 'fi_2');
    A._armerApercu(el1);
    vi.advanceTimersByTime(800);
    A._armerApercu(el2);     // remplace
    vi.advanceTimersByTime(1500);
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenCalledWith('fiche', 'fi_2', el2);
  });

  it('la modale unique n\'est créée qu\'une fois', () => {
    const A = nouvelAssemblage();
    A._assurerModaleApercu();
    A._assurerModaleApercu();
    expect(document.querySelectorAll('.atl-apercu-modale').length).toBe(1);
  });

  it('cache_valide=true → récupère le PDF via POST /rendu-pdf (pas GET)', async () => {
    const A = nouvelAssemblage();
    const calls = [];
    globalThis.fetch = vi.fn().mockImplementation((url, opts) => {
      calls.push({ url, method: opts && opts.method });
      if (url.endsWith('/rendu-pdf/info')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ cache_valide: true }) });
      }
      // /rendu-pdf : renvoie un blob
      return Promise.resolve({ ok: true, blob: () => Promise.resolve(new Blob(['%PDF'])) });
    });
    // URL.createObjectURL n'existe pas en jsdom : on le stubbe.
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:fake');
    await A._declencherApercu('exercice', 'ex_1', document.createElement('div'));
    // laisser la micro-tâche d'affichage se résoudre
    await Promise.resolve(); await Promise.resolve();
    const appelPdf = calls.find(c => c.url.endsWith('/rendu-pdf'));
    expect(appelPdf).toBeTruthy();
    expect(appelPdf.method).toBe('POST');  // PAS GET (sinon 405)
    expect(A._afficherPdfDansViewer).toHaveBeenCalled();
  });

  it('cache_valide=false → affiche le bouton « Générer l\'aperçu »', async () => {
    const A = nouvelAssemblage();
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true, json: () => Promise.resolve({ cache_valide: false }),
    });
    await A._declencherApercu('exercice', 'ex_1', document.createElement('div'));
    const corps = A._apercuModale.querySelector('.atl-apercu-corps');
    const btn = corps.querySelector('button.btn-prim');
    expect(btn).toBeTruthy();
    expect(btn.textContent).toContain('Générer');
  });

  it('réponse obsolète (gen périmé) est ignorée', async () => {
    const A = nouvelAssemblage();
    // fetch lent : on incrémente _apercuGen entre-temps.
    globalThis.fetch = vi.fn().mockImplementation(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({ cache_valide: true }) }));
    const p = A._declencherApercu('exercice', 'ex_1', document.createElement('div'));
    A._apercuGen += 5;  // simule un nouveau survol entre-temps
    await p;
    // _afficherApercuPdf ne doit pas avoir tenté d'afficher (gen périmé).
    expect(A._afficherPdfDansViewer).not.toHaveBeenCalled();
  });

  it('fermer la modale invalide les réponses en vol', () => {
    const A = nouvelAssemblage();
    A._assurerModaleApercu();
    const genAvant = A._apercuGen || 0;
    A._ouvrirModaleApercu();
    A._fermerModaleApercu();
    expect(A._apercuModale.style.display).toBe('none');
    expect(A._apercuGen).toBeGreaterThan(genAvant);
  });
});
