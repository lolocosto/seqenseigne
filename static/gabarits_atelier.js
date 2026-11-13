// ============================================================================
// static/gabarits_atelier.js — v0.52.4, v0.56.0 (séries EN / AP / EX)
//
// Modèle de référentiel (« gabarit de documents ») mis à la disposition de
// l'interface (décision I2). Le modèle ne dépend pas du niveau : tout
// référentiel de N09 à N12 peut être
//   - « Notions et méthodes »            (valeur technique `cycle4`) ;
//   - « Fiches de résumé par objectif »  (valeur technique `sixieme`).
//
// Les ateliers (exercices, évaluations, assemblage de séquence) ne testent
// plus le niveau « N09 » : ils demandent le modèle de l'atelier du niveau,
// fourni par le serveur (GET /api/gabarits-documents, règle R1b : référentiel
// interne principal du niveau, hors « annulé », le plus récent ; sans
// référentiel, N09 → Fiches, N10 à N12 → Notions et méthodes).
// ============================================================================

const ATL_GABARITS = {
  charge: false,
  niveaux: {},     // {N09: 'sixieme', N10: 'cycle4', …}
  // Libellés de secours (avant la réponse du serveur) ; les descriptions
  // complètes viennent de services/gabarits_documents.MODELES.
  modeles: [
    { valeur: 'cycle4', libelle: 'Notions et méthodes' },
    { valeur: 'sixieme', libelle: 'Fiches de résumé par objectif' },
  ],
};

// Règle de secours, identique à gabarits_documents.gabarit_par_defaut.
function atlGabaritParDefaut(niveau) {
  return niveau === 'N09' ? 'sixieme' : 'cycle4';
}

function atlGabaritNiveau(niveau) {
  const n = niveau || '';
  return ATL_GABARITS.niveaux[n] || atlGabaritParDefaut(n);
}

// Vrai si le niveau est conçu au modèle « Fiches de résumé par objectif ».
function atlModeleFiches(niveau) {
  return atlGabaritNiveau(niveau) === 'sixieme';
}

// v0.56.0 (SERIES, Laurent, 13 novembre) — Modèle « Fiches » : les séries F, A, E
// s'appellent Entraînement, Approfondissement, Expertise et leurs codes affichés
// sont EN, AP, EX (EN06, AP05, EX02). Les codes internes (base, API, lots) restent
// F, A, E : seul l'affichage change ; les autres séries et le modèle « Notions et
// méthodes » ne changent pas. Même table que services/series_fiches.py.
const ATL_SERIES_FICHES = {
  F: { code: 'EN', libelle: 'Entraînement' },
  A: { code: 'AP', libelle: 'Approfondissement' },
  E: { code: 'EX', libelle: 'Expertise' },
};

// Préfixe affiché d'une série (« F » → « EN » au modèle Fiches).
function atlPrefixeSerie(lettre, niveau) {
  const s = ATL_SERIES_FICHES[lettre];
  return (s && atlModeleFiches(niveau)) ? s.code : (lettre || '');
}

// Code affiché d'un exercice (« F06 » → « EN06 » au modèle Fiches ; « AE01 »,
// « EV03 »… et le cycle 4 inchangés).
function atlCodeExercice(code, niveau) {
  const m = /^([FAE])(\d+)$/.exec(code || '');
  if (!m || !atlModeleFiches(niveau)) return code || '';
  return ATL_SERIES_FICHES[m[1]].code + m[2];
}

// Nom affiché d'une série au modèle Fiches (« Entraînement »), sinon `defaut`.
function atlLibelleSerie(lettre, niveau, defaut) {
  const s = ATL_SERIES_FICHES[lettre];
  return (s && atlModeleFiches(niveau)) ? s.libelle : defaut;
}

function atlModele(valeur) {
  return ATL_GABARITS.modeles.find(m => m.valeur === valeur) || null;
}

function atlLibelleModele(valeur) {
  const m = atlModele(valeur || 'cycle4');
  return m ? m.libelle : (valeur || '');
}

// Recharge les modèles et le modèle de chaque niveau (au démarrage, après la
// création d'un référentiel ou un changement de modèle).
async function atlChargerGabarits() {
  try {
    const r = await fetch('/api/gabarits-documents');
    if (!r.ok) return ATL_GABARITS;
    const d = await r.json();
    if (d && d.niveaux) ATL_GABARITS.niveaux = d.niveaux;
    if (d && Array.isArray(d.modeles) && d.modeles.length) ATL_GABARITS.modeles = d.modeles;
    ATL_GABARITS.charge = true;
  } catch (e) { /* hors ligne : règle de secours */ }
  return ATL_GABARITS;
}

if (typeof window !== 'undefined') {
  window.ATL_GABARITS = ATL_GABARITS;
  window.atlGabaritNiveau = atlGabaritNiveau;
  window.atlModeleFiches = atlModeleFiches;
  window.atlModele = atlModele;
  window.ATL_SERIES_FICHES = ATL_SERIES_FICHES;     // v0.56.0
  window.atlPrefixeSerie = atlPrefixeSerie;
  window.atlCodeExercice = atlCodeExercice;
  window.atlLibelleSerie = atlLibelleSerie;
  window.atlLibelleModele = atlLibelleModele;
  window.atlChargerGabarits = atlChargerGabarits;
  if (typeof document !== 'undefined' && document.addEventListener) {
    document.addEventListener('DOMContentLoaded', () => { atlChargerGabarits(); });
  }
}
