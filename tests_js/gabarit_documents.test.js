// tests_js/gabarit_documents.test.js — v0.52.1 (v0.52.4 : modèles de référentiel)
//
// Gabarit de documents d'un référentiel (cycle4 / sixieme) côté interface :
//   - G1 : à la création, la liste est préremplie selon le niveau (6e →
//     sixieme, 5e à 3e → cycle4) et la valeur choisie est envoyée ;
//   - G2 : dans « Documents à publier », le choix n'est modifiable que tant
//     que le référentiel est « en cours » ;
//   - G5 : un type d'un autre gabarit s'affiche avec le libellé et les
//     options fournis par le serveur (interface générique).

import { describe, it, expect, beforeAll } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const src = f => readFileSync(join(__dirname, '..', 'static', f), 'utf-8');
const HTML = readFileSync(join(__dirname, '..', 'templates', 'index.html'), 'utf-8');

describe('création : gabarit prérempli selon le niveau (G1)', () => {
  let ctx;
  beforeAll(() => {
    const code = src('referentiel_unifie.js');
    const debut = code.indexOf('function refuGabaritParDefaut');
    const fin = code.indexOf('async function refuCreer');
    ctx = new Function('document', 'ATL_FILTRE_NIVEAU',
      code.slice(debut, fin) + '; return { refuGabaritParDefaut, refuPreremplirGabarit };');
  });

  it('N09 → sixieme, N10 à N12 → cycle4', () => {
    const { refuGabaritParDefaut } = ctx(null, '');
    expect(refuGabaritParDefaut('N09')).toBe('sixieme');
    for (const n of ['N10', 'N11', 'N12', '']) expect(refuGabaritParDefaut(n)).toBe('cycle4');
  });

  it('préremplit au changement de niveau, garde un choix manuel sinon', () => {
    const sel = { value: 'cycle4', dataset: {} };
    const doc = { getElementById: () => sel };
    ctx(doc, 'N09').refuPreremplirGabarit();
    expect(sel.value).toBe('sixieme');
    sel.value = 'cycle4';                       // choix manuel, même niveau
    ctx(doc, 'N09').refuPreremplirGabarit();
    expect(sel.value).toBe('cycle4');
    ctx(doc, 'N11').refuPreremplirGabarit();    // niveau changé
    expect(sel.value).toBe('cycle4');
  });

  it('la liste existe et la valeur part avec les deux créations', () => {
    expect(HTML).toMatch(/id="refu-c-gabarit"/);
    const code = src('referentiel_unifie.js');
    expect(code).toMatch(/type_ref: type, gabarit \}/);
    expect(code).toMatch(/type_ref: type, modele, gabarit \}/);
  });
});

describe('Documents à publier : gabarit et types génériques (G2, G5)', () => {
  let ctx;
  beforeAll(() => {
    const code = src('atelier_referentiel.js');
    ctx = (selection) => new Function('ATL_REF_SELECTION',
      code.slice(code.indexOf('const ATL_REF_DOC_TITRES'), code.indexOf('async function atelRefChargerEtRendreDocuments'))
      + code.slice(code.indexOf('const ATL_REF_GABARITS'), code.indexOf('async function atelRefChangerGabarit'))
      + code.slice(code.indexOf('function atelRefDocumentOptionsHtml'), code.indexOf('async function atelRefMajOptionDoc'))
      + code.slice(code.indexOf('function atelRefEscape'), code.indexOf('// Exposition globale'))
      + '; return { atelRefGabaritHtml, atelRefDocumentOptionsHtml };')(selection);
  });

  it('sélecteur actif en cours, désactivé une fois verrouillé', () => {
    expect(ctx({ id: 'R', etat: 'en_cours', gabarit_documents: 'sixieme' })
      .atelRefGabaritHtml()).not.toMatch(/disabled/);
    const fige = ctx({ id: 'R', etat: 'verrouille', gabarit_documents: 'sixieme' }).atelRefGabaritHtml();
    expect(fige).toMatch(/disabled/);
    expect(fige).toMatch(/value="sixieme" selected/);
  });

  it('options d\'un type 6e rendues depuis les champs du catalogue', () => {
    const html = ctx({ id: 'R', etat: 'en_cours' }).atelRefDocumentOptionsHtml({
      id: 'd1', type_document: 'livret_sequence_6e',
      options: { actif: true, version: 'corrigee', inclure_activites: true },
      champs: [{ cle: 'version', libelle: 'Version', type: 'choix',
                 valeurs: [['eleve', 'élève'], ['corrigee', 'corrigée']] },
               { cle: 'inclure_activites', libelle: "Activités d'introduction", type: 'bool' }],
    }, true);
    expect(html).toMatch(/value="corrigee"\s+checked/);
    expect(html).toMatch(/atelRefMajOptionDoc\('d1', 'inclure_activites'/);
  });
});

// ── v0.52.4 — Le gabarit est un MODÈLE de référentiel ─────────────────────────

describe('M1 : modèle choisi à la création, avec sa description', () => {
  let ctx;
  beforeAll(() => {
    const code = src('referentiel_unifie.js');
    const debut = code.indexOf('function refuGabaritParDefaut');
    const fin = code.indexOf('async function refuCreer');
    ctx = (doc, modeles) => new Function('document', 'ATL_FILTRE_NIVEAU', 'atlModele', '_refuE', 'atlLibelleModele',
      code.slice(debut, fin) + '; return { refuModeleProposable, refuDescriptionModele, refuMajChoixModele, _refuBadgeModele };')(
      doc, 'N10', v => (modeles || []).find(m => m.valeur === v) || null, x => String(x == null ? '' : x),
      v => v === 'sixieme' ? 'Fiches de résumé par objectif' : 'Notions et méthodes');
  });

  it('proposé pour un référentiel interne, principal ou de mises en route (v0.54.0), jamais externe', () => {
    // v0.54.0 (RI10, changement voulu) : un référentiel de mises en route
    // interne au modèle « Fiches » publie ses documents par partie.
    const { refuModeleProposable } = ctx(null);
    expect(refuModeleProposable('interne', 'principal')).toBe(true);
    expect(refuModeleProposable('interne', 'mer')).toBe(true);
    expect(refuModeleProposable('externe', 'principal')).toBe(false);
    expect(refuModeleProposable('externe', 'mer')).toBe(false);
  });

  it('la description dit documents, séries et règles de complétude du modèle choisi', () => {
    const els = { 'refu-c-gabarit': { value: 'sixieme', dataset: {} }, 'refu-c-modele-bloc': { style: {} },
                  'refu-c-modele-desc': { innerHTML: '' }, 'refu-c-source': { value: 'interne' },
                  'atl-ref-type': { value: 'principal' } };
    const doc = { getElementById: id => els[id] };
    ctx(doc, [{ valeur: 'sixieme', libelle: 'Fiches de résumé par objectif', resume: 'Une fiche par objectif.',
                documents: 'livret', series: 'TP, AC, AT, EV', completude: 'F et A, fiche' }]).refuMajChoixModele();
    expect(els['refu-c-modele-bloc'].style.display).toBe('');
    const h = els['refu-c-modele-desc'].innerHTML;
    expect(h).toMatch(/Une fiche par objectif/);
    expect(h).toMatch(/Séries :<\/strong> TP, AC, AT, EV/);
    expect(h).toMatch(/Pour valider :<\/strong> F et A, fiche/);
    els['refu-c-source'].value = 'externe';
    ctx(doc, []).refuMajChoixModele();
    expect(els['refu-c-modele-bloc'].style.display).toBe('none');
  });

  it('les libellés de la liste de création sont les noms des modèles', () => {
    expect(HTML).toMatch(/<option value="cycle4">Notions et méthodes<\/option>/);
    expect(HTML).toMatch(/<option value="sixieme">Fiches de résumé par objectif<\/option>/);
    expect(HTML).not.toMatch(/Documents : 6e/);
  });

  it('la liste des référentiels affiche le modèle des internes principaux', () => {
    const { _refuBadgeModele } = ctx(null);
    expect(_refuBadgeModele({ source: 'interne', type: 'principal', modele: 'sixieme' }))
      .toMatch(/Fiches de résumé par objectif/);
    expect(_refuBadgeModele({ source: 'externe', type: 'principal', modele: 'cycle4' })).toBe('');
  });
});

describe('G2b : modèle modifiable en cours et validé, « (figé) » au verrouillage', () => {
  let ctx;
  beforeAll(() => {
    const code = src('atelier_referentiel.js');
    ctx = (selection) => new Function('ATL_REF_SELECTION', 'atlModele',
      code.slice(code.indexOf('const ATL_REF_DOC_TITRES'), code.indexOf('async function atelRefChargerEtRendreDocuments'))
      + code.slice(code.indexOf('const ATL_REF_GABARITS'), code.indexOf('async function atelRefChangerGabarit'))
      + code.slice(code.indexOf('function atelRefEscape'), code.indexOf('// Exposition globale'))
      + '; return { atelRefGabaritHtml, atelRefMessageChangementModele };')(selection, () => null);
  });

  it('validé : modifiable, sans « (figé) » ; verrouillé, utilisé : figé', () => {
    const v = ctx({ id: 'R', etat: 'valide', gabarit_documents: 'cycle4' }).atelRefGabaritHtml();
    expect(v).not.toMatch(/disabled/);
    expect(v).not.toMatch(/\(figé\)/);
    for (const etat of ['verrouille', 'utilise'])
      expect(ctx({ id: 'R', etat, gabarit_documents: 'cycle4' }).atelRefGabaritHtml()).toMatch(/\(figé\)/);
  });

  it('avertit s\'il reste des documents actifs de l\'ancien modèle', () => {
    const { atelRefMessageChangementModele } = ctx({ id: 'R', etat: 'en_cours' });
    const docs = [{ type_document: 'livret_sequence', options: { actif: true } },
                  { type_document: 'livret_cours', options: { actif: false } }];
    const m = atelRefMessageChangementModele(docs, 'cycle4', 'sixieme');
    expect(m).toMatch(/1 document\(s\) actif\(s\) du modèle « Notions et méthodes »/);
    expect(m).toMatch(/Livret de séquence/);
    expect(atelRefMessageChangementModele([{ type_document: 'livret_cours', options: { actif: false } }],
      'cycle4', 'sixieme')).toBe('');
  });
});

describe('I2 : modèle de l\'atelier par niveau (static/gabarits_atelier.js)', () => {
  let m;
  beforeAll(() => {
    const code = src('gabarits_atelier.js');
    m = new Function(code.slice(0, code.indexOf("if (typeof window !== 'undefined')"))
      + '; return { ATL_GABARITS, atlGabaritNiveau, atlModeleFiches, atlLibelleModele };')();
  });
  it('sans réponse du serveur : N09 → Fiches, N10 à N12 → Notions et méthodes', () => {
    expect(m.atlModeleFiches('N09')).toBe(true);
    expect(m.atlModeleFiches('N10')).toBe(false);
  });
  it('le serveur décide (référentiel de l\'atelier du niveau, R1b)', () => {
    m.ATL_GABARITS.niveaux = { N09: 'cycle4', N10: 'sixieme' };
    expect(m.atlModeleFiches('N10')).toBe(true);
    expect(m.atlModeleFiches('N09')).toBe(false);
    expect(m.atlLibelleModele('sixieme')).toBe('Fiches de résumé par objectif');
  });
  it('chargé avant les ateliers', () => {
    expect(HTML.indexOf('/static/gabarits_atelier.js')).toBeGreaterThan(-1);
    expect(HTML.indexOf('/static/gabarits_atelier.js')).toBeLessThan(HTML.indexOf('/static/atelier_exercice.js'));
  });
});

describe('A5 : assemblage au modèle « Fiches de résumé par objectif »', () => {
  const ASM = src('atelier_seqniv_assemblage.js');
  it('objectif sans méthode : bouton « + Nouvel objectif », code du Cours réservé', () => {
    expect(ASM).toMatch(/nouvelObjectifSansMethode\(partieId\)/);
    expect(ASM).toMatch(/\{nom: '', reserver_cours: true\}/);
  });
  it('zone « Fiche de l\'objectif » (fiches_resume.objectif_id) ; Notions et Méthode masquées', () => {
    expect(ASM).toMatch(/Fiche de l'objectif/);
    expect(ASM).toMatch(/\/fiche`, \{fiche_id: ficheId\}/);
    expect(ASM).toMatch(/const methBloc = \(o\.methode_id && !modeleFiches\)/);
    expect(ASM).toMatch(/zonesContenu = modeleFiches\s*\? this\._rendreZoneFicheObjectif\(o\) \+ zonesExos \+ this\._rendreZonesDocuments\(o\)\s*: zoneNotions \+ zonesExos/);
  });
  it('zones des séries EV, TP, AC, AT', () => {
    expect(ASM).toMatch(/\['EV', 'TP', 'AC', 'AT'\]\.map\(s =>/);
  });
});

describe('Arbre « Référentiel » au modèle « Fiches » : pas de « Méthode (manquante) »', () => {
  const code = src('atelier_referentiel.js');
  const ctx = (selection) => new Function('ATL_REF_SELECTION',
    code.slice(code.indexOf('function atelRefModeleFiches'), code.indexOf('function atelRefLigneSerieHtml'))
    + code.slice(code.indexOf('function atelRefLigneSerieHtml'), code.indexOf('// ── v0.13.5.1.2 — Helpers de rendu d\'un atome'))
    + '; function atelRefEscape(s) { return String(s); }'
    + ' function atelRefAtomeLibHtml(a, l) { return l + " " + a.code; }'
    + ' function atelRefAtomeChipHtml(a) { return a.code; }'
    + ' function atelRefAtomeNotionHtml(n) { return "N " + n.titre; }'
    + '; return { atelRefObjectifHtml };')(selection);
  const o = { code: '02', nom: 'Obj', est_cours: false, methode: null, notions: [{ titre: 'n' }],
              fiche: null, exos_F: [], exos_A: [], exos_E: [] };
  it('modèle Fiches : la fiche (manquante) seulement, ni méthode ni notions', () => {
    const h = ctx({ gabarit_documents: 'sixieme' }).atelRefObjectifHtml(o);
    expect(h).not.toMatch(/Méthode \(manquante\)/);
    expect(h).toMatch(/Fiche de résumé \(manquante\)/);
    expect(h).not.toMatch(/N n/);
    expect(ctx({ gabarit_documents: 'sixieme' }).atelRefObjectifHtml({ ...o, fiche: { code: 'FR01' } }))
      .toMatch(/Fiche de résumé FR01/);
  });
  it('modèle Notions et méthodes : inchangé', () => {
    const h = ctx({ gabarit_documents: 'cycle4' }).atelRefObjectifHtml(o);
    expect(h).toMatch(/Méthode \(manquante\)/);
    expect(h).toMatch(/N n/);
  });
});
