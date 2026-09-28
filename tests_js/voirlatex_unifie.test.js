// tests_js/voirlatex_unifie.test.js — v0.17.1
//
// (1) AtelierEditeur.voirLatex() unifié : récupère le .tex CÔTÉ SERVEUR
//     (fetch <endpointRenduPdf>/<id>/rendu-tex) et l'affiche dans la modale
//     commune window.atelierAfficherLatex. Plus de window.open.
// (2) L'évaluation régénère la mini-toolbar de rendu à l'ouverture de l'onglet
//     Rendu (_assurerToolbarRendu) — réparation du bouton « Compiler » disparu
//     en v0.17.0.

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

beforeAll(() => {
  globalThis.window.atelToast = globalThis.window.atelToast || (() => {});
  charger('atelier.js');
  charger('atelier_editeur.js');
});

function nouvelAtelier(prefixe = 'atl-test') {
  return new globalThis.window.AtelierEditeur({
    id: 'test', prefixe,
    endpointBase: '/api/tests',
    endpointRenduPdf: '/api/atomes/test',
    typeLatex: 'exercice',
  });
}

describe('voirLatex unifié (serveur + modale) — v0.17.1', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    globalThis.fetch = undefined;
  });

  it('no-op si aucun item actif', async () => {
    const A = nouvelAtelier();
    A.itemActif = null;
    const spy = vi.fn();
    globalThis.window.atelierAfficherLatex = spy;
    await A.voirLatex();
    expect(spy).not.toHaveBeenCalled();
  });

  it('récupère le .tex serveur et l\'affiche dans la modale commune', async () => {
    const A = nouvelAtelier();
    A.itemActif = { id: 'ex_1' };
    // modifie=false → pas de sauvegarde préalable
    A.modifie = false;
    const tex = '\\begin{seqExercice}...\\end{seqExercice}';
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve(tex),
    });
    const spyModale = vi.fn();
    globalThis.window.atelierAfficherLatex = spyModale;

    await A.voirLatex();

    // fetch appelé sur la route .tex serveur
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/atomes/test/ex_1/rendu-tex',
      expect.objectContaining({ method: 'GET' }),
    );
    // modale commune appelée avec (typeLatex, tex)
    expect(spyModale).toHaveBeenCalledWith('exercice', tex);
  });

  it('affiche un toast d\'erreur si le serveur répond non-ok', async () => {
    const A = nouvelAtelier();
    A.itemActif = { id: 'ex_1' };
    A.modifie = false;
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false, status: 404,
      json: () => Promise.resolve({ error: 'introuvable' }),
    });
    const spyModale = vi.fn();
    globalThis.window.atelierAfficherLatex = spyModale;
    const spyToast = vi.spyOn(A, 'toast').mockImplementation(() => {});

    await A.voirLatex();

    expect(spyModale).not.toHaveBeenCalled();
    expect(spyToast).toHaveBeenCalled();
    spyToast.mockRestore();
  });

  it('sauvegarde d\'abord si l\'item est modifié', async () => {
    const A = nouvelAtelier();
    A.itemActif = { id: 'ex_1' };
    // Force modifie=true via snapshot invalide
    A._snapshotInvalide = true;
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true, text: () => Promise.resolve('tex'),
    });
    globalThis.window.atelierAfficherLatex = vi.fn();
    const spySave = vi.spyOn(A, 'sauvegarder').mockResolvedValue(true);

    await A.voirLatex();

    expect(spySave).toHaveBeenCalledWith({ silencieuse: true });
    spySave.mockRestore();
  });
});
