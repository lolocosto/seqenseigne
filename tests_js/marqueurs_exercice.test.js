// tests_js/marqueurs_exercice.test.js — v0.52.7
//
// Marqueurs « ordinateur » et « calculatrice » de l'atelier d'exercices :
//   - indicateur discret de la liste, seulement pour un exercice marqué
//     (clé `marqueurs` du contrat de liste, décision M3) ;
//   - les deux listes de l'en-tête sont lues et remplies par le formulaire
//     (sinon un enregistrement les effacerait).

import { describe, it, expect, beforeAll } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC = readFileSync(join(__dirname, '..', 'static', 'atelier_exercice.js'), 'utf-8');

function extraire(nom) {
  const re = new RegExp(`AtelierExercice\\.${nom} = function[\\s\\S]*?\\n\\};`);
  const m = SRC.match(re);
  if (!m) throw new Error(`${nom} introuvable`);
  return m[0].replace(`AtelierExercice.${nom} =`, 'return');
}

describe('indicateur des marqueurs dans la liste', () => {
  let indicateur;
  beforeAll(() => {
    const AtelierExercice = {
      ORDINATEUR: { scratch: 'Scratch', geogebra: 'GeoGebra', tableur: 'Tableur', autre: 'Autre' },
      CALCULATRICE: { autorisee: 'calculatrice autorisée', interdite: 'calculatrice interdite' },
    };
    indicateur = new Function('AtelierExercice', extraire('indicateurMarqueurs') + '\n')(
      AtelierExercice);
  });
  it('rien pour un exercice non marqué (pas de clé, ou valeurs vides)', () => {
    expect(indicateur(undefined)).toBeNull();
    expect(indicateur({ ordinateur: '', calculatrice: '' })).toBeNull();
  });
  it('outil et calculatrice, détail en infobulle', () => {
    const i = indicateur({ ordinateur: 'scratch', calculatrice: 'interdite' });
    expect(i.texte).toBe('⌨ Scratch · calc. interdite');
    expect(i.titre).toBe('Ordinateur : Scratch ; Calculatrice interdite');
    expect(indicateur({ ordinateur: '', calculatrice: 'autorisee' }).texte).toBe('calc. autorisée');
  });
});

describe('formulaire', () => {
  it('collecte et remplit les deux listes', () => {
    expect(SRC).toMatch(/ordinateur:\s+\(this\.\$\('ordinateur'\)\s+\|\| \{\}\)\.value/);
    expect(SRC).toMatch(/calculatrice: \(this\.\$\('calculatrice'\) \|\| \{\}\)\.value/);
    expect(SRC).toMatch(/ordiEl\.value = AtelierExercice\.ORDINATEUR\[ex\.ordinateur\]/);
    expect(SRC).toMatch(/calcEl\.value = AtelierExercice\.CALCULATRICE\[ex\.calculatrice\]/);
  });
});
