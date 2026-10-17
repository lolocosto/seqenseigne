// tests_js/atelier_fiche_zones_exemple.test.js — v0.51.19
//
// Atelier Fiche de résumé : case « Inclure une zone d'exemple » + hauteur
// en lignes sous chaque zone de texte, et case « Ajouter une zone exemple
// jusqu'au bas de page » pour la fiche. Mêmes classes que le « Cadre de
// réponse » de l'atelier Exercice (UI cohérente).
//
// Volet 1 : helpers statiques exécutés dans jsdom (rendu, bascule, lecture).
// Volet 2 : branchement dans le formulaire (analyse statique) — la
// détection « modifié » compare collecterFormulaire à l'instantané pris
// après remplirFormulaire : les deux doivent produire la même forme
// (null quand il n'y a pas de zone).

import { describe, it, expect, beforeAll } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC = readFileSync(
  join(__dirname, '..', 'static', 'atelier_fiche.js'), 'utf-8');
const HTML = readFileSync(
  join(__dirname, '..', 'templates', 'index.html'), 'utf-8');

let AF;

beforeAll(() => {
  const m = SRC.match(
    /AtelierFiche\.EXEMPLE_LIGNES_DEFAUT[\s\S]*?\nAtelierFiche\.lireZoneExemple = function[\s\S]*?\n\};/);
  if (!m) throw new Error('helpers zone d\'exemple introuvables');
  AF = {};
  // eslint-disable-next-line no-new-func
  new Function('AtelierFiche', m[0])(AF);
});

function bloc(lignes) {
  const div = document.createElement('div');
  div.className = 'atl-fiche-section';
  div.innerHTML = AF.htmlZoneExemple(lignes);
  document.body.appendChild(div);
  return div;
}

describe('zone d\'exemple — helpers (jsdom)', () => {
  it('sans zone : case décochée, hauteur masquée, valeur par défaut 6', () => {
    const b = bloc(null);
    expect(b.querySelector('.atl-fiche-section-ex-actif').checked).toBe(false);
    expect(b.querySelector('.atl-fiche-section-ex-lignes-wrap').style.display).toBe('none');
    expect(b.querySelector('.atl-fiche-section-ex-lignes').value).toBe('6');
    expect(AF.lireZoneExemple(b)).toBeNull();
  });

  it('avec zone de 12 lignes : relue à l\'identique (aller-retour)', () => {
    const b = bloc(12);
    expect(b.querySelector('.atl-fiche-section-ex-actif').checked).toBe(true);
    expect(AF.lireZoneExemple(b)).toBe(12);
  });

  it('cocher affiche la hauteur et lit la valeur ; décocher → null', () => {
    const b = bloc(null);
    const c = b.querySelector('.atl-fiche-section-ex-actif');
    c.checked = true;
    AF.basculerZoneExemple(c);
    expect(b.querySelector('.atl-fiche-section-ex-lignes-wrap').style.display).toBe('');
    expect(AF.lireZoneExemple(b)).toBe(6);
    c.checked = false;
    AF.basculerZoneExemple(c);
    expect(b.querySelector('.atl-fiche-section-ex-lignes-wrap').style.display).toBe('none');
    expect(AF.lireZoneExemple(b)).toBeNull();
  });

  it('bornes du champ alignées sur le serveur (1 à 40)', () => {
    const champ = bloc(3).querySelector('.atl-fiche-section-ex-lignes');
    expect(champ.min).toBe('1');
    expect(champ.max).toBe('40');
  });

  it('reprend les classes du cadre de réponse (UI cohérente)', () => {
    const b = bloc(null);
    expect(b.querySelector('.atl-cadre-rep-row')).not.toBeNull();
    expect(b.querySelector('.atl-cadre-rep-toggle')).not.toBeNull();
    expect(b.querySelector('.atl-cadre-rep-lignes')).not.toBeNull();
  });
});

describe('zone d\'exemple — branchement dans le formulaire', () => {
  it('chaque zone de texte rend sa ligne « zone d\'exemple »', () => {
    expect(SRC).toMatch(/AtelierFiche\.htmlZoneExemple\(sec\.exemple_lignes\)/);
  });
  it('la capture DOM lit la zone d\'exemple de chaque bloc', () => {
    expect(SRC).toMatch(/exemple_lignes:\s*AtelierFiche\.lireZoneExemple\(bloc\)/);
  });
  it('remplirFormulaire normalise en null (même forme que la capture)', () => {
    expect(SRC).toMatch(/exemple_lignes:\s*parseInt\(s\.exemple_lignes, 10\) \|\| null/);
  });
  it('collecterFormulaire envoie la case de fin de page', () => {
    expect(SRC).toMatch(/exemple_fin_page:\s*finPage \? !!finPage\.checked : true/);
  });
  it('la case de fin de page existe, cochée par défaut', () => {
    expect(HTML).toMatch(/id="atl-fiche-exemple-fin-page" checked/);
    expect(HTML).toContain("Ajouter une zone exemple jusqu'au bas de page");
  });
});
