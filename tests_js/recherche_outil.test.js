// tests_js/recherche_outil.test.js — v0.18.1
//
// Outil Recherche (Outils généraux). Deux volets :
//
//  1. Analyse statique d'app.js : le câblage de l'atelier Recherche est en
//     place (entrée dans ATL_PORTEES.generaux, ATL_INITS, fonctions
//     rechercheInit / rechercheLancer / rechercheRendre, ouverture 5 types
//     généralisée). On NE charge PAS app.js entier (trop de dépendances
//     globales navigateur) — on lit le source, comme les autres tests app.js.
//
//  2. Exécution en jsdom de rechercheRendre + escAttrJs, extraites du source.
//     Ces deux fonctions sont autonomes (escAttrJs est pure ; rechercheRendre
//     n'a besoin que de escapeHtml et du DOM). On les isole pour vérifier le
//     rendu groupé sans monter toute l'application.

import { describe, it, expect, beforeAll } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const APP = readFileSync(join(__dirname, '..', 'static', 'app.js'), 'utf-8');

function lignesDeCode(src) {
  return src.split('\n').filter(l => !l.trimStart().startsWith('//')).join('\n');
}

// ── Volet 1 : analyse statique du câblage ───────────────────────────────────

describe('app.js — câblage de l’atelier Recherche (v0.18.1)', () => {
  const code = lignesDeCode(APP);

  it('recherche est déclaré dans la portée generaux', () => {
    // ateliers: ['rdl', 'recherche']
    expect(code).toMatch(/ateliers:\s*\[\s*'rdl'\s*,\s*'recherche'\s*\]/);
  });

  it('recherche a une init enregistrée (ATL_INITS)', () => {
    expect(code).toMatch(/recherche:\s*'rechercheInit'/);
  });

  it('les fonctions rechercheInit / Lancer / Rendre sont définies', () => {
    expect(code).toMatch(/function\s+rechercheInit\s*\(/);
    expect(code).toMatch(/function\s+rechercheLancer\s*\(/);
    expect(code).toMatch(/function\s+rechercheRendre\s*\(/);
  });

  it('rechercheLancer appelle GET /api/recherche', () => {
    expect(code).toMatch(/fetch\('\/api\/recherche\?'/);
  });

  it('l’ouverture d’atelier est généralisée aux 5 types', () => {
    // _OUVRIR_ATELIER_MAPPING doit couvrir fiche et carte en plus des 3 cours.
    expect(code).toMatch(/_OUVRIR_ATELIER_MAPPING/);
    expect(code).toMatch(/fiche:\s*\{sw:\s*'fiche'/);
    expect(code).toMatch(/carte:\s*\{sw:\s*'carte_automatisme'/);
  });

  it('compilBatchOuvrirAtelier accepte niveau et sequence (transversal)', () => {
    expect(code).toMatch(
      /function\s+compilBatchOuvrirAtelier\s*\(\s*type\s*,\s*id\s*,\s*niveau\s*,\s*sequence\s*\)/
    );
  });
});

// ── Volet 2 : exécution de rechercheRendre + escAttrJs ───────────────────────

// Extrait le corps source d'une fonction nommée `function NOM(...) { ... }`
// en équilibrant les accolades. Permet d'évaluer la fonction isolément.
function extraireFonction(src, nom) {
  const re = new RegExp('function\\s+' + nom + '\\s*\\(');
  const m = re.exec(src);
  if (!m) throw new Error('fonction introuvable : ' + nom);
  let i = src.indexOf('{', m.index);
  let prof = 0;
  for (let j = i; j < src.length; j++) {
    if (src[j] === '{') prof++;
    else if (src[j] === '}') {
      prof--;
      if (prof === 0) return src.slice(m.index, j + 1);
    }
  }
  throw new Error('accolade de fin introuvable pour : ' + nom);
}

// Extrait une déclaration `const NOM = ...;` (objet ou tableau) du source.
function extraireConst(src, nom) {
  const re = new RegExp('const\\s+' + nom + '\\s*=');
  const m = re.exec(src);
  if (!m) throw new Error('const introuvable : ' + nom);
  let i = src.indexOf('=', m.index) + 1;
  let prof = 0;
  for (let j = i; j < src.length; j++) {
    const c = src[j];
    if (c === '{' || c === '[') prof++;
    else if (c === '}' || c === ']') prof--;
    else if (c === ';' && prof === 0) return src.slice(m.index, j + 1);
  }
  throw new Error('fin de const introuvable : ' + nom);
}

describe('rechercheRendre + escAttrJs (exécution jsdom)', () => {
  let rechercheRendre, escAttrJs;

  beforeAll(() => {
    // escapeHtml minimal (équivalent à celui d'app.js) pour le contexte.
    const escapeHtmlSrc = `
      function escapeHtml(s){ if(s==null) return '';
        return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
          .replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }
    `;
    const labelsSrc = extraireConst(APP, '_RECH_LABEL_TYPE');
    const ordreSrc = extraireConst(APP, '_RECH_ORDRE_TYPES');
    const rendreSrc = extraireFonction(APP, 'rechercheRendre');
    const escSrc = extraireFonction(APP, 'escAttrJs');
    // v0.18.2 — rechercheRendre s'appuie désormais sur lienAtomeHTML
    // (+ deeplinkAtomeURL + _nomAtelierPourDeeplink). On les extrait aussi.
    const nomAtelierSrc = extraireFonction(APP, '_nomAtelierPourDeeplink');
    const deeplinkSrc = extraireFonction(APP, 'deeplinkAtomeURL');
    const lienSrc = extraireFonction(APP, 'lienAtomeHTML');

    const bundle = new Function(
      escapeHtmlSrc + '\n' + labelsSrc + '\n' + ordreSrc + '\n' +
      nomAtelierSrc + '\n' + deeplinkSrc + '\n' + lienSrc + '\n' +
      rendreSrc + '\n' + escSrc + '\n' +
      'return { rechercheRendre, escAttrJs, deeplinkAtomeURL, lienAtomeHTML };'
    );
    const exporte = bundle();
    rechercheRendre = exporte.rechercheRendre;
    escAttrJs = exporte.escAttrJs;
  });

  it('escAttrJs protège apostrophe et backslash', () => {
    expect(escAttrJs("a'b")).toBe("a\\'b");
    expect(escAttrJs('a\\b')).toBe('a\\\\b');
    expect(escAttrJs(null)).toBe('');
    expect(escAttrJs('N10')).toBe('N10');
  });

  it('rend « aucun résultat » quand total = 0', () => {
    document.body.innerHTML = '<div id="rech-resultats"></div>';
    rechercheRendre({ total: 0, notion: [], methode: [], exercice: [],
                      fiche: [], carte: [] });
    expect(document.getElementById('rech-resultats').textContent)
      .toMatch(/Aucun atome/);
  });

  it('groupe les résultats par type avec compteurs', () => {
    document.body.innerHTML = '<div id="rech-resultats"></div>';
    rechercheRendre({
      total: 3,
      notion: [
        { id: 'no_1', type: 'notion', niveau: 'N10', sequence: 'S01',
          identifiant: 'N10/S01/Notion 01', titre: 'Proportion',
          etat_code: 'valide' },
        { id: 'no_2', type: 'notion', niveau: 'N10', sequence: 'S01',
          identifiant: 'N10/S01/Notion 02', titre: 'Pourcentage',
          etat_code: 'en_cours' },
      ],
      methode: [], exercice: [],
      fiche: [
        { id: 'fi_1', type: 'fiche', niveau: 'N10', sequence: 'S01',
          identifiant: 'N10/S01/Fiche 01', titre: 'Résumé',
          etat_code: 'valide' },
      ],
      carte: [],
    });
    const html = document.getElementById('rech-resultats').innerHTML;
    // En-têtes de groupe présents avec compteur.
    expect(html).toMatch(/Notions\s*<span[^>]*>\(2\)/);
    expect(html).toMatch(/Fiches de résumé\s*<span[^>]*>\(1\)/);
    // v0.18.2 — « Ouvrir » est un lien <a> deeplink, clic intercepté par
    // ouvrirAtomeDepuisEvent (Ctrl+clic = nouvel onglet natif).
    // NB : innerHTML normalise & en &amp; dans les attributs.
    expect(html).toContain('href="/?atelier=notion&amp;niveau=N10&amp;seq=S01&amp;atome=no_1"');
    expect(html).toContain('href="/?atelier=fiche&amp;niveau=N10&amp;seq=S01&amp;atome=fi_1"');
    expect(html).toContain("ouvrirAtomeDepuisEvent(event,'notion','no_1','N10','S01')");
    expect(html).toContain("ouvrirAtomeDepuisEvent(event,'fiche','fi_1','N10','S01')");
    expect(html).toContain('target="_blank"');
    // Badge d'état.
    expect(html).toMatch(/validé/);
    expect(html).toMatch(/en cours/);
  });

  it('échappe le titre (anti-injection HTML)', () => {
    document.body.innerHTML = '<div id="rech-resultats"></div>';
    rechercheRendre({
      total: 1,
      notion: [{ id: 'x', type: 'notion', niveau: 'N10', sequence: 'S01',
                 identifiant: 'N10/S01/Notion 01',
                 titre: '<script>alert(1)</script>', etat_code: 'valide' }],
      methode: [], exercice: [], fiche: [], carte: [],
    });
    const html = document.getElementById('rech-resultats').innerHTML;
    expect(html).not.toContain('<script>alert(1)</script>');
    expect(html).toContain('&lt;script&gt;');
  });
});
