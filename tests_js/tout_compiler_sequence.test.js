// tests_js/tout_compiler_sequence.test.js — v0.54.2
//
// « Tout compiler » pour toute séquence (Laurent, 26 octobre 2026,
// doc/redemarrage_v0_54_2.md) :
//   - D-TOUT-SEQ : le bouton est affiché pour une Snn comme pour une Mnn ;
//   - une Mnn garde sa route et sa partie, une Snn appelle la route des
//     séquences (sans partie : la liste vient de la table du modèle, serveur) ;
//   - changer de séquence annule un « Tout compiler » en cours.

import { describe, it, expect, beforeAll, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const lire = rel => readFileSync(join(__dirname, '..', rel), 'utf-8');
function charger(rel) { new Function(lire(join('static', rel)))(); }   // eslint-disable-line no-new-func

class FauxEventSource {
  constructor(url) { this.url = url; this.ferme = false; FauxEventSource.dernier = this; }
  close() { this.ferme = true; }
}

describe('D-TOUT-SEQ — Tout compiler pour toute séquence', () => {
  let A, P;
  beforeAll(() => {
    globalThis.window.atelGardeEnregistrer = globalThis.window.atelGardeEnregistrer || (() => {});
    charger('atelier.js');
    charger('atelier_editeur.js');
    charger('atelier_assemblage.js');
    charger('seqniv_pur.js');
    charger('atelier_seqniv_assemblage.js');
    A = globalThis.window.ATELIER_SEQNIV;
    P = globalThis.window.SeqnivPur;
    globalThis.EventSource = FauxEventSource;
  });
  beforeEach(() => { A._merSource = null; FauxEventSource.dernier = null; });

  it('URL : une mise en route garde sa route et sa partie, une Snn appelle la route des séquences', () => {
    expect(P.urlToutCompiler('N09', 'M03', '1'))
      .toBe('/api/v2/livret-sequence/N09/M03/mer/tout-compiler?partie=1');
    expect(P.urlToutCompiler('N09', 'M03', '')).toBe('/api/v2/livret-sequence/N09/M03/mer/tout-compiler');
    expect(P.urlToutCompiler('N09', 'S03', '2')).toBe('/api/v2/livret-sequence/N09/S03/tout-compiler');
    expect(P.urlToutCompiler('N11', 'S04')).toBe('/api/v2/livret-sequence/N11/S04/tout-compiler');
  });

  function ongletPour(seq) {
    A.data = { sequence_par_niveau: { niveau: seq.startsWith('M') ? 'N09' : 'N11', sequence_code: seq } };
    A._chargerResumeMer = () => {};
    document.body.innerHTML = '<div id="asm-tab-rendu"></div>';
    A._assurerOngletRendu();
  }

  it('le bouton est affiché pour une séquence principale, sans le bloc des documents de mise en route', () => {
    ongletPour('S04');
    expect(document.getElementById('livret-seq-mer-tout').style.display).toBe('flex');
    expect(document.getElementById('livret-seq-mer').style.display).toBe('none');
    expect(document.getElementById('livret-seq-mer-btn-tout').title).toMatch(/modèle du référentiel/);
    expect(document.getElementById('livret-seq-btn-pdf').textContent).toMatch(/Compiler le livret/);
  });

  it('une mise en route garde son bloc, son bouton et son infobulle', () => {
    ongletPour('M03');
    expect(document.getElementById('livret-seq-mer-tout').style.display).toBe('flex');
    expect(document.getElementById('livret-seq-mer').style.display).toBe('flex');
    expect(document.getElementById('livret-seq-mer-btn-tout').title).toMatch(/dossier enseignant/);
  });

  it('Snn : la partie (sélecteur des mises en route) est ignorée', () => {
    ongletPour('S04');
    document.getElementById('livret-seq-mer-partie').innerHTML = '<option value="2" selected>2</option>';
    A.merToutCompiler();
    expect(FauxEventSource.dernier.url).toBe('/api/v2/livret-sequence/N11/S04/tout-compiler');
    A.merToutAnnuler();
  });

  it('changer de séquence annule un « Tout compiler » en cours', () => {
    ongletPour('S04');
    A.merToutCompiler();
    const src = FauxEventSource.dernier;
    A._reinitialiserOngletRendu();
    expect(src.ferme).toBe(true);
    expect(A._merSource).toBe(null);
  });
});
