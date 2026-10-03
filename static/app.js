/* seqenseigne — app.js multi-classes */

let SEQ=[], CLASSES=[], eleves=[], suivi={}, niveaux={}, expanded={};
let SEQ_SOURCE=null, SEQ_REFERENTIEL=null;  // v0.6.1 : origine des séquences affichées
let currentCid=null, currentSeq=null, currentView='classe', selectedCidDetail=null;
// v0.34.0 — Option 1 : suivi PAR PARTIE de séquence. `currentPartie` = numéro de
// partie sélectionné (1, 2, 3…). La partie d'un objectif se déduit de son code :
// 01–09 → partie 1, 11–19 → partie 2, 21–29 → partie 3 (num = int(code[0])+1).
let currentPartie=1;
function _partieDObjectif(code){ const n=parseInt(String(code)[0],10); return isNaN(n)?1:n+1; }
function _partiesDeSequence(seq){
  if(!seq||!seq.objectifs) return [1];
  const set=new Set(seq.objectifs.map(o=>_partieDObjectif(o.code)));
  return Array.from(set).sort((a,b)=>a-b);
}
function _objectifsDeLaPartie(seq,partie){
  if(!seq||!seq.objectifs) return [];
  return seq.objectifs.filter(o=>_partieDObjectif(o.code)===partie);
}
let ANNEE_ACTIVE = '';   // année scolaire filtrée ('' = toutes)
let ANNEES = [];          // liste des années disponibles
let ANNEE_COURANTE = '';  // v0.27.4 — année scolaire courante fournie par le serveur

// v0.27.3 — La logique de décalage a été rapatriée CÔTÉ SERVEUR
// (services/decalage_progression.py + route /api/classes/<id>/progression-realisee).
// Le client ne calcule plus les décalages ; il affiche les créneaux déjà
// décalés reçus du serveur. L'ancienne fonction appliquerDecalagesJS est
// supprimée pour ne pas laisser de logique métier dupliquée en JS.

// v0.27.0.3 — Affiche un PDF DANS l'appli via le viewer pdf.js embarqué (et non
// par l'affichage natif du navigateur, qui l'enverrait au lecteur système).
// Fetch le PDF en blob, puis charge le viewer avec une URL blob locale.
// `iframe` : l'élément iframe cible ; `url` : l'URL de l'endpoint PDF.
async function afficherPdfDansAppli(iframe, url) {
  if (!iframe) return;
  const VIEWER = '/static/vendor/pdfjs/web/viewer.html';
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const blob = await r.blob();
    if (iframe._seqBlobUrl) { try { URL.revokeObjectURL(iframe._seqBlobUrl); } catch (_) {} }
    const blobUrl = URL.createObjectURL(blob);
    iframe._seqBlobUrl = blobUrl;
    iframe.src = VIEWER + '?file=' + encodeURIComponent(blobUrl);
  } catch (e) {
    // Repli : affichage natif (au pire, comportement d'avant).
    iframe.src = url;
  }
}
window.afficherPdfDansAppli = afficherPdfDansAppli;

// v0.27.4 — L'année scolaire courante est une RÈGLE MÉTIER calculée par le
// serveur (services/annees_scolaires). Le client ne la calcule plus : il lit la
// valeur fournie (ANNEE_COURANTE, chargée à l'init depuis /api/annees-scolaires).
// Cette fonction est conservée comme accesseur pour les appelants existants.
function anneeScolaireCourante() {
  return ANNEE_COURANTE || '';
}

// ════════════════════════════════════════════════════════════════
// RÉFÉRENTIEL NIVEAUX — chargé depuis /api/referentiel/niveaux
// ════════════════════════════════════════════════════════════════
let NIV_REF = null;   // { "1": {libelle, libelle_court, points, couleur}, ... }

async function chargerNiveauxRef() {
  try {
    const lst = await fetch('/api/referentiel/niveaux').then(r=>r.json());
    NIV_REF = {};
    for (const n of lst) NIV_REF[n.code] = n;
  } catch(e) {
    // Fallback statique si l'API n'est pas encore disponible
    NIV_REF = {
      "0":  {libelle:"Aucune donnée", libelle_court:"-",    points:null, couleur:"neutre"},
      "1":  {libelle:"Insuffisant",  libelle_court:"I",    points:4,  couleur:"rouge"},
      "2":  {libelle:"À consolider", libelle_court:"F",    points:10, couleur:"jaune"},
      "3":  {libelle:"Satisfaisant", libelle_court:"A",    points:16, couleur:"vert"},
      "4":  {libelle:"Très bien",    libelle_court:"E",    points:20, couleur:"vert_fonce"},
      "A":  {libelle:"Absent",       libelle_court:"Abs",  points:null, couleur:"bleu"},
      "D":  {libelle:"Dispensé",     libelle_court:"Disp", points:null, couleur:"bleu"},
      "NE": {libelle:"Non évalué",   libelle_court:"NE",   points:null, couleur:"blanc"},
    };
  }
}

function nivPoints(code) {
  return NIV_REF?.[code]?.points ?? null;
}
function nivLibelleCourt(code) {
  return NIV_REF?.[code]?.libelle_court ?? code;
}
function codesAvecNote() {
  if (!NIV_REF) return ["1","2","3","4"];
  return Object.keys(NIV_REF).filter(c => NIV_REF[c].points !== null);
}
function codesSansNote() {
  if (!NIV_REF) return ["A","D","NE"];
  return Object.keys(NIV_REF).filter(c => NIV_REF[c].points === null);
}
// Tous les codes valides pour le sélecteur de niveau
function tousLesCodes() {
  return NIV_REF ? Object.keys(NIV_REF) : ["1","2","3","4","A","D","NE"];
}

async function api(path, opts={}) {
  const r = await fetch(path, {headers:{'Content-Type':'application/json'}, ...opts});
  return r.json();
}

async function init() {
  await chargerNiveauxRef();
  await chargerAnnees();
  await loadClasses();
  buildClasseSel();
  renderClassesList();
  const saved = localStorage.getItem('currentCid');
  if (saved && CLASSES.find(c=>c.id===saved)) await selectClasse(saved);

  // v0.19.1.2 — L'onglet « Suivi de classe » est actif par défaut au
  // chargement : monter sa navigation à 2 barres et rendre les sélecteurs.
  // (selectClasse a pu déjà appeler sousOnglet('suivi') ; suiviInit est
  // idempotent et restaure la portée/atelier mémorisés.)
  if (typeof suiviInit === 'function') suiviInit();

  // v0.30.0 — L'onglet « Tableau de bord » est désormais l'écran d'accueil
  // (actif par défaut). On charge ses tuiles au démarrage.
  if (typeof tdbInit === 'function') tdbInit();

  // v0.13.5.1.2 — Traitement d'un deeplink éventuel (ex. atelier
  // Référentiel qui ouvre un exo précis dans l'atelier Exercice).
  // Format de l'URL : ?atelier=exercice&niveau=N11&seq=S07&atome=ex_abc
  // L'atelier cible doit être l'un de : exercice, notion, methode, fiche.
  // Pour les ateliers de portée Séquence, niveau et seq sont obligatoires.
  // On nettoie l'URL (history.replaceState) une fois le contexte posé,
  // pour qu'un rechargement (F5) ne replonge pas l'utilisateur dedans.
  _appliquerDeeplink();
}

// v0.30.1 — Action « ouvrir l'atelier de conception au niveau <niveau> ».
// Utilisée par la tuile « Atomes à finaliser » du tableau de bord : cliquer un
// niveau amène directement dans l'atelier, portée Niveau, sur ce niveau.
// (Pas de filtre « en cours » ici — option (a) validée.)
function ouvrirAtelierNiveau(niveau) {
  if (!niveau) return;
  try {
    localStorage.setItem('atl-portee-active', 'niveau');
    localStorage.setItem('atl-portee-sel-niveau',
      JSON.stringify({ niveau: niveau }));
  } catch (e) { /* localStorage indisponible — best-effort */ }
  if (typeof ATL_SELECTIONS !== 'undefined' && ATL_SELECTIONS.niveau) {
    ATL_SELECTIONS.niveau.niveau = niveau;
  }
  const btnAteliers = document.querySelector('[data-tab="ateliers"]');
  if (btnAteliers) btnAteliers.click();
}
window.ouvrirAtelierNiveau = ouvrirAtelierNiveau;

// v0.30.3 — Action fine de la tuile « Atomes à finaliser » : ouvrir l'atelier
// d'un TYPE d'atome, au niveau voulu, en mode « toutes les séquences », avec le
// filtre « en cours » pré-activé. Ex. « 279 exercices » de 3ème → atelier
// exercices, toutes séquences de 3ème, filtre en cours.
function ouvrirAtelierAtomesEnCours(niveau, typeAtome) {
  if (!niveau || !typeAtome) return;
  // type d'atome (tuile) -> nom d'atelier (portée séquence)
  const ATELIER_PAR_TYPE = {
    exercice: 'exercice', notion: 'notion', methode: 'methode',
    carte: 'carte_automatisme', fiche: 'fiche',
  };
  const atelier = ATELIER_PAR_TYPE[typeAtome];
  if (!atelier) return;
  // 1. Portée Séquence, niveau voulu, séquence vide = toutes les séquences.
  //    Mise à jour d'ATL_SELECTIONS EN MÉMOIRE (figé au chargement sinon).
  try {
    localStorage.setItem('atl-portee-active', 'sequence');
    localStorage.setItem('atl-portee-sel-sequence',
      JSON.stringify({ niveau: niveau, sequence: '' }));
  } catch (e) { /* best-effort */ }
  if (typeof ATL_SELECTIONS !== 'undefined' && ATL_SELECTIONS.sequence) {
    ATL_SELECTIONS.sequence.niveau = niveau;
    ATL_SELECTIONS.sequence.sequence = '';
  }
  // 2. Basculer sur Ateliers, appliquer la portée, activer l'atelier, puis
  //    CLIQUER le bouton « En cours » de cet atelier. On clique le bouton réel
  //    (plutôt que de poser une variable) : chaque atelier a son propre
  //    mécanisme de filtre (générique pour exercice/notion/méthode/fiche,
  //    spécifique pour la carte), et le clic synchronise aussi l'état visuel.
  const btnAteliers = document.querySelector('[data-tab="ateliers"]');
  if (btnAteliers) btnAteliers.click();
  setTimeout(() => {
    if (typeof atelPorteeSwitch === 'function') {
      try { atelPorteeSwitch('sequence'); } catch (e) { /* best-effort */ }
    }
    if (typeof atelSwitch === 'function') {
      try { atelSwitch(atelier); } catch (e) { /* best-effort */ }
    }
    // Cliquer le bouton « En cours » du panneau de l'atelier actif.
    setTimeout(() => {
      const panneau = document.getElementById('atl-' + atelier);
      const btnEnCours = panneau
        && panneau.querySelector('.exo-etat[data-etat="en_cours"]');
      if (btnEnCours) btnEnCours.click();
    }, 150);
  }, 200);
}
window.ouvrirAtelierAtomesEnCours = ouvrirAtelierAtomesEnCours;

// v0.31.1 — Variante « non rattachés » : ouvre l'atelier du type, toutes
// séquences, et clique le bouton « Non rattachés » (au lieu de « En cours »).
function ouvrirAtelierAtomesNonRattaches(niveau, typeAtome) {
  if (!niveau || !typeAtome) return;
  const ATELIER_PAR_TYPE = {
    exercice: 'exercice', notion: 'notion', methode: 'methode',
    carte: 'carte_automatisme', fiche: 'fiche',
  };
  const atelier = ATELIER_PAR_TYPE[typeAtome];
  if (!atelier) return;
  try {
    localStorage.setItem('atl-portee-active', 'sequence');
    localStorage.setItem('atl-portee-sel-sequence',
      JSON.stringify({ niveau: niveau, sequence: '' }));
  } catch (e) { /* best-effort */ }
  if (typeof ATL_SELECTIONS !== 'undefined' && ATL_SELECTIONS.sequence) {
    ATL_SELECTIONS.sequence.niveau = niveau;
    ATL_SELECTIONS.sequence.sequence = '';
  }
  const btnAteliers = document.querySelector('[data-tab="ateliers"]');
  if (btnAteliers) btnAteliers.click();
  setTimeout(() => {
    if (typeof atelPorteeSwitch === 'function') {
      try { atelPorteeSwitch('sequence'); } catch (e) {}
    }
    if (typeof atelSwitch === 'function') {
      try { atelSwitch(atelier); } catch (e) {}
    }
    setTimeout(() => {
      // Désactiver un éventuel filtre non-rattaché résiduel, puis l'activer.
      window.ATL_FILTRE_RATTACHEMENT = '';
      const panneau = document.getElementById('atl-' + atelier);
      // Le bouton « Non rattachés » est celui dont l'onclick vise
      // atelAtomeFiltrerRattachement.
      const btns = panneau ? panneau.querySelectorAll('.exo-etat') : [];
      let btnNR = null;
      btns.forEach(b => {
        if ((b.getAttribute('onclick') || '').includes('Rattachement')) btnNR = b;
      });
      if (btnNR) btnNR.click();
    }, 150);
  }, 200);
}
window.ouvrirAtelierAtomesNonRattaches = ouvrirAtelierAtomesNonRattaches;

function _appliquerDeeplink() {
  const params = new URLSearchParams(window.location.search);
  // Sans paramètre ?atelier=…, il n'y a pas de deeplink à appliquer : on sort
  // silencieusement (cas normal du chargement de la page).
  const atelier = params.get('atelier');
  if (!atelier) return;

  // v0.18.2 — carte_automatisme ajouté (le chip carte de seqniv génère déjà
  // cette URL depuis v0.13.6.3 ; elle était rejetée ici, deeplink cassé).
  const types_supportes = ['exercice', 'notion', 'methode', 'fiche',
                           'carte_automatisme'];
  if (!types_supportes.includes(atelier)) {
    console.warn('[deeplink] atelier inconnu :', atelier);
    return;
  }
  const niveau = params.get('niveau') || '';
  const seq    = params.get('seq')    || '';
  const atome  = params.get('atome')  || '';
  if (!niveau || !seq) {
    console.warn('[deeplink] niveau et seq sont obligatoires');
    return;
  }

  // 1. Préposer la portée Séquence + ses sélecteurs (niveau, seq) en
  //    localStorage. ATL_SELECTIONS les relit à l'init.
  try {
    localStorage.setItem('atl-portee-active', 'sequence');
    localStorage.setItem('atl-portee-sel-sequence',
      JSON.stringify({niveau: niveau, sequence: seq}));
  } catch (e) { /* localStorage indisponible — best-effort */ }

  // 2. Basculer vers l'onglet Ateliers (déclenche initAteliers()).
  const btnAteliers = document.querySelector('[data-tab="ateliers"]');
  if (!btnAteliers) {
    console.warn('[deeplink] onglet Ateliers introuvable');
    return;
  }
  btnAteliers.click();

  // 3. Une fois la portée appliquée et l'init terminé, ouvrir l'atome via le
  //    mécanisme OO unifié (v0.18.1) : ATELIER_*.ouvrirItem, qui couvre les 5
  //    types (dont carte). On attend que la liste de l'atelier soit chargée
  //    (async) avant d'ouvrir.
  //    Mapping nom d'atelier (URL) -> objet OO.
  const OO_PAR_ATELIER = {
    'exercice':          'ATELIER_EXERCICE',
    'notion':            'ATELIER_NOTION',
    'methode':           'ATELIER_METHODE',
    'fiche':             'ATELIER_FICHE',
    'carte_automatisme': 'ATELIER_CARTE',
  };
  setTimeout(() => {
    if (typeof atelSwitch === 'function') {
      try { atelSwitch(atelier); } catch (e) {
        console.warn('[deeplink] atelSwitch a échoué :', e);
      }
    }
    if (atome) {
      const ooNom = OO_PAR_ATELIER[atelier];
      let essais = 0;
      const max = 30;  // ~4.5s à 150ms (base réelle ~1s de chargement)
      const tenter = () => {
        const atObj = window[ooNom];
        const liste = atObj && atObj.liste;
        const trouve = liste && liste.find && liste.find(x => x.id === atome);
        if (atObj && typeof atObj.ouvrirItem === 'function' && trouve) {
          try { atObj.ouvrirItem(atome); } catch (e) {
            console.warn(`[deeplink] ${ooNom}.ouvrirItem a échoué :`, e);
          }
          return;
        }
        if (++essais < max) { setTimeout(tenter, 150); return; }
        // Dernier recours : tenter l'ouverture même sans confirmation de liste.
        if (atObj && typeof atObj.ouvrirItem === 'function') {
          try { atObj.ouvrirItem(atome); } catch (e) {
            console.warn(`[deeplink] ${ooNom}.ouvrirItem (forcé) a échoué :`, e);
          }
        } else {
          console.warn(`[deeplink] objet OO ${ooNom} introuvable.`);
        }
      };
      setTimeout(tenter, 200);
    }
    // Nettoyer l'URL pour qu'un F5 ne replonge pas dans le deeplink.
    try {
      window.history.replaceState({}, '', window.location.pathname);
    } catch (e) { /* navigateur ancien — ignorer */ }
  }, 300);
}

async function chargerAnnees() {
  try {
    ANNEES = await api('/api/admin/annees');
  } catch(e) {
    ANNEES = [];
  }
  // v0.27.4 — L'année scolaire COURANTE est calculée par le serveur
  // (règle métier). Le client ne la recalcule plus : il la lit ici.
  try {
    const r = await api('/api/annees-scolaires');
    if (r && r.annee_courante) ANNEE_COURANTE = r.annee_courante;
  } catch (e) { /* fallback géré par anneeScolaireCourante() */ }
  const sel = document.getElementById('annee-sel');
  if (!sel) return;
  // Plus récente en premier (l'API retourne déjà desc)
  sel.innerHTML = '<option value="">— Toutes les années —</option>'
    + ANNEES.map(a => `<option value="${a}">${a}</option>`).join('');
  // Restaurer la sélection
  const saved = localStorage.getItem('anneeActive');
  if (saved && ANNEES.includes(saved)) {
    ANNEE_ACTIVE = saved;
    sel.value = saved;
  } else if (ANNEES.length) {
    // Sélectionner la plus récente par défaut
    ANNEE_ACTIVE = ANNEES[0];
    sel.value = ANNEES[0];
    localStorage.setItem('anneeActive', ANNEES[0]);
  }
}

async function onAnneeChange() {
  const sel = document.getElementById('annee-sel');
  ANNEE_ACTIVE = sel.value;
  localStorage.setItem('anneeActive', ANNEE_ACTIVE);
  // Réinitialiser la classe sélectionnée
  currentCid = null;
  showNoClasse();
  await loadClasses();
  buildClasseSel();
  renderClassesList();
}

document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    // v0.10.6 — Garde de sortie : on ne sort de l'atelier vers
    // une autre destination (Suivi, Admin, Préférences, Aide…) qu'après
    // avoir confirmé le sort des modifs en cours.
    const _continuer = () => {
      document.querySelectorAll('.tab').forEach(b=>{
        b.classList.remove('active');
        if (b.getAttribute('role') === 'tab') b.setAttribute('aria-selected','false');
      });
      document.querySelectorAll('.tab-content').forEach(c=>c.style.display='none');
      btn.classList.add('active');
      if (btn.getAttribute('role') === 'tab') btn.setAttribute('aria-selected','true');
      // v0.33.0 — « Planification » et « Suivi » partagent le conteneur
      // tab-classe ; chacun force sa portée (planification vs suivi/gestion).
      // v0.42.0 — « Paramétrage » partage aussi tab-classe (portée gestion).
      const tabCible = (btn.dataset.tab === 'planification' || btn.dataset.tab === 'parametrage')
        ? 'classe' : btn.dataset.tab;
      const elCible = document.getElementById('tab-' + tabCible);
      if (elCible) elCible.style.display = '';
      if (btn.dataset.tab==='livrets') return; // onglet supprimé
      if (btn.dataset.tab==='accueil' && typeof tdbInit === 'function') tdbInit();
      if (btn.dataset.tab==='ateliers') initAteliers();
      if (btn.dataset.tab==='mer' && typeof merInit === 'function') merInit();
      if (btn.dataset.tab==='admin')    adminSousOnglet('importref');
      // v0.42.0 — Onglet « Système » : barre Administration / Préférences.
      if (btn.dataset.tab==='systeme' && typeof systemeSwitch === 'function') {
        systemeSwitch(_systemeSousOnglet());
      }
      // v0.42.0 — Onglet « Paramétrage » : portée gestion du module suivi.
      if (btn.dataset.tab==='parametrage') {
        if (typeof suiviInit === 'function') suiviInit();
        if (typeof suiviPorteeSwitch === 'function') suiviPorteeSwitch('gestion');
      }
      // v0.33.0 — Onglet « Planification » : monter la nav du suivi puis forcer
      // la portée planification.
      if (btn.dataset.tab==='planification') {
        if (typeof suiviInit === 'function') suiviInit();
        if (typeof suiviPorteeSwitch === 'function') suiviPorteeSwitch('planification');
      }
      // v0.19.1.2 — À l'entrée de l'onglet « Suivi de classe », (re)monter la
      // navigation à 2 barres (portée + atelier mémorisés) et rendre les
      // sélecteurs contextuels.
      if (btn.dataset.tab==='classe' && typeof suiviInit === 'function') {
        suiviInit();
        // v0.42.0 — L'onglet « Suivi » ne montre plus que la portée suivi
        // (la gestion est passée dans « Paramétrage »).
        if (SUIVI_PORTEE_ACTIVE !== 'suivi'
            && typeof suiviPorteeSwitch === 'function') {
          suiviPorteeSwitch('suivi');
        }
      }
      // v0.9 — Recharger les chemins de configuration à chaque entrée dans
      // l'onglet Préférences (au cas où ils auraient été modifiés ailleurs,
      // par exemple par édition directe du configuration.json).
      // (v0.42.0 — Préférences : voir systemeSwitch / _prefInitialiser.)
      // Réinitialiser les sous-onglets de l'onglet classe au sous-onglet "suivi"
      // pour éviter que le panneau paramétrage reste visible au retour

    };
    if (typeof atelGardeAvantTransition === 'function') {
      atelGardeAvantTransition(_continuer);
    } else {
      _continuer();
    }
  });
});

// ═══════════════════════════════════════════════════════════════════════════
//  v0.19.1.2 — Navigation « Suivi de classe » à 2 barres (portées)
//  Calquée sur la zone Référentiel (ATL_PORTEES / atelPorteeSwitch). Module
//  dédié `suivi*` (décision A-i : pas de mutualisation avec atel*, zones DOM
//  et sélecteurs distincts).
//
//  Portées et sous-ateliers :
//    annuel  → progression · suivi   (sélecteurs : Année/Étab/Niveau [+ Réf.])
//    gestion → classe · etab         (pas de sélecteurs contextuels)
//
//  Chaque sous-atelier est rattaché à un panneau existant (stab-*) pour ne
//  pas casser la logique métier déjà câblée :
//    progression → #stab-progression           (atelier OO)
//    suivi       → #stab-suivi                  (suivi des séquences)
//    classe/etab → #stab-parametrage + gestionSousOnglet('classes'/'etabs')
// ═══════════════════════════════════════════════════════════════════════════

const SUIVI_PORTEES = {
  // v0.33.0 — Réorganisation : la planification (prévu) passe dans l'onglet
  // principal « Planification » ; le suivi (réalisé/observé) et la gestion
  // restent dans « Suivi ».
  planification: {
    label: 'Planification',
    ateliers: ['edt', 'planif', 'indispo', 'mer', 'progmer', 'progression', 'plans'],
  },
  // v0.42.0 — Onglet « Suivi » : Début de séance, Observation, Compétences
  // (ex-« Suivi de classe »).
  suivi: {
    label: 'Suivi',
    ateliers: ['debut', 'observation', 'suivi'],
  },
  // v0.42.0 — Onglet principal « Paramétrage » (ex-portée Gestion du Suivi).
  gestion: {
    label: 'Paramétrage',
    ateliers: ['classe', 'etab', 'observables'],
  },
};

// v0.42.0 — Onglet principal correspondant à chaque portée (data-tab).
const SUIVI_PORTEE_ONGLET = { planification: 'planification', suivi: 'classe', gestion: 'parametrage' };

// atelier → panneau stab-* + éventuel sous-onglet de gestion.
const SUIVI_ATELIER_PANNEAU = {
  edt:         { panneau: 'edt',         selecteurs: ['etablissement'] },
  planif:      { panneau: 'planif',      selecteurs: ['etablissement'] },
  indispo:     { panneau: 'indispo',     selecteurs: ['etablissement'] },
  mer:         { panneau: 'mer',         selecteurs: ['etablissement', 'classe'] },
  progmer:     { panneau: 'progmer',     selecteurs: ['etablissement', 'niveau', 'classe'] },
  progression: { panneau: 'progression', selecteurs: ['etablissement', 'niveau', 'referentiel'] },
  plans:       { panneau: 'plans',       selecteurs: ['etablissement'] },   // v0.39.0
  suivi:       { panneau: 'suivi',       selecteurs: ['annee', 'etablissement', 'niveau', 'classe'] },
  // v0.42.1 — Tous les sous-onglets du Suivi : Année, Établissement, Niveau,
  // Classe (la classe choisie est partagée entre eux).
  debut:       { panneau: 'debut',       selecteurs: ['annee', 'etablissement', 'niveau', 'classe'] },
  observation: { panneau: 'observation', selecteurs: ['annee', 'etablissement', 'niveau', 'classe'] },
  // v0.42.1 — Observables : définis par niveau (indépendants de l'établissement).
  observables: { panneau: 'observables', selecteurs: ['niveau'] },
  classe:      { panneau: 'parametrage', gestion: 'classes', selecteurs: ['annee', 'etablissement', 'niveau'] },
  etab:        { panneau: 'parametrage', gestion: 'etabs', selecteurs: ['annee', 'etablissement'] },
};

let SUIVI_PORTEE_ACTIVE = (function () {
  const s = localStorage.getItem('suivi-portee-active');
  return (s && SUIVI_PORTEES[s]) ? s : 'planification';
})();

function _suiviAtelierDefaut(portee) {
  return SUIVI_PORTEES[portee].ateliers[0];
}

let SUIVI_ATELIER_ACTIF = (function () {
  const s = localStorage.getItem('suivi-atelier-actif');
  // Valider que l'atelier mémorisé appartient à la portée mémorisée.
  if (s && SUIVI_PORTEES[SUIVI_PORTEE_ACTIVE].ateliers.includes(s)) return s;
  // v0.19.1.2 / décision C : défaut = Suivi de classe.
  return _suiviAtelierDefaut(SUIVI_PORTEE_ACTIVE);
})();

function suiviPorteeSwitch(portee, depuisInit = false) {
  if (!SUIVI_PORTEES[portee]) return;
  const _continuer = () => {
    SUIVI_PORTEE_ACTIVE = portee;
    localStorage.setItem('suivi-portee-active', portee);

    // Boutons de portée (barre 1) — seules suivi/gestion ont un bouton.
    Object.keys(SUIVI_PORTEES).forEach(p => {
      const b = document.getElementById('suivi-btn-portee-' + p);
      if (b) b.classList.toggle('active', p === portee);
    });
    // v0.42.0 — Chaque portée a son onglet principal : la rangée de portées
    // est toujours masquée, et l'onglet principal actif suit la portée (une
    // bascule par code — sousOnglet, gestionAllerEtablissements… — met donc
    // aussi le bon onglet en surbrillance).
    const row = document.getElementById('suivi-portee-row');
    if (row) row.style.display = 'none';
    const ongletCible = SUIVI_PORTEE_ONGLET[portee];
    document.querySelectorAll('.tab[data-tab]').forEach(t => {
      if (!['planification', 'classe', 'parametrage'].includes(t.dataset.tab)) return;
      const actif = t.dataset.tab === ongletCible;
      const tabClasse = document.getElementById('tab-classe');
      if (tabClasse && tabClasse.style.display === 'none') return;
      t.classList.toggle('active', actif);
      if (t.getAttribute('role') === 'tab') t.setAttribute('aria-selected', actif ? 'true' : 'false');
    });

    // Boutons d'atelier (barre 2) : n'afficher que ceux de la portée.
    Object.keys(SUIVI_PORTEES).forEach(p => {
      document.querySelectorAll('.suivi-grp-' + p).forEach(b => {
        b.style.display = (p === portee) ? '' : 'none';
      });
    });

    // Choisir l'atelier actif de la portée : conserver si déjà dedans,
    // sinon le premier de la portée.
    let atelier = SUIVI_ATELIER_ACTIF;
    if (!SUIVI_PORTEES[portee].ateliers.includes(atelier)) {
      atelier = _suiviAtelierDefaut(portee);
    }
    suiviSwitch(atelier);
  };
  if (!depuisInit && typeof atelGardeAvantTransition === 'function') {
    atelGardeAvantTransition(_continuer);
  } else {
    _continuer();
  }
}

function suiviSwitch(atelier) {
  const def = SUIVI_ATELIER_PANNEAU[atelier];
  if (!def) return;
  const _continuer = () => {
    SUIVI_ATELIER_ACTIF = atelier;
    localStorage.setItem('suivi-atelier-actif', atelier);

    // Bouton actif (barre 2)
    Object.keys(SUIVI_ATELIER_PANNEAU).forEach(a => {
      const b = document.getElementById('suivi-btn-' + a);
      if (b) b.classList.toggle('active', a === atelier);
    });

    // Afficher le panneau stab-* correspondant
    ['edt', 'planif', 'indispo', 'mer', 'progmer', 'progression', 'plans', 'suivi',
     'debut', 'observation', 'observables', 'parametrage'].forEach(s => {
      const el = document.getElementById('stab-' + s);
      if (el) el.style.display = (s === def.panneau) ? '' : 'none';
    });

    // Sélecteurs contextuels de la barre 1
    suiviRenderSelecteurs();

    // Initialisations spécifiques au panneau
    if (def.panneau === 'parametrage') {
      renderClassesList();
      chargerEtablissementsEtBandeau();
      if (def.gestion && typeof gestionSousOnglet === 'function') {
        gestionSousOnglet(def.gestion);
      }
    }
    if (atelier === 'edt' && typeof edtInit === 'function') {
      edtInit().then(() => _suiviAppliquerGlobaux('edt'));
    }
    if (atelier === 'indispo' && typeof indispoInit === 'function') {
      indispoInit().then(() => _suiviAppliquerGlobaux('indispo'));
    }
    if (atelier === 'planif' && typeof planifInit === 'function') {
      planifInit();
    }
    if (atelier === 'progression' && typeof window.progInit === 'function') {
      window.progInit().then(() => _suiviAppliquerGlobaux('progression'));
    }
    if (atelier === 'mer' && typeof merInit === 'function') {
      merInit();
    }
    if (atelier === 'progmer' && typeof progMerInit === 'function') {
      progMerInit();
    }
    if (atelier === 'plans' && typeof pcInit === 'function') {   // v0.39.0
      pcInit();
    }
    if (atelier === 'debut' && typeof scInit === 'function') {   // v0.43.0
      scInit();
    }
    if (atelier === 'observables' && typeof obsInit === 'function') {   // v0.45.0
      obsInit();
    }
  };
  if (typeof atelGardeAvantTransition === 'function') {
    atelGardeAvantTransition(_continuer);
  } else {
    _continuer();
  }
}

// Déplace les <select> mémorisés (pools cachés) vers la barre 1 selon
// l'atelier actif, et y conserve leurs IDs/handlers. Décision B :
//   progression → Année · Étab · Niveau · Référentiel  (pool #prog-selecteurs-pool)
//   suivi       → Année · Classe                        (pool #suivi-selecteurs-pool)
//   classe/etab → aucun sélecteur
// ─────────────────────────────────────────────────────────────────────────
// v0.21.3 — Sélecteurs du Suivi annuel, calqués sur la Conception de
// référentiel (déclaratif). Chaque onglet déclare sa liste `selecteurs`
// (cf. SUIVI_ATELIER_PANNEAU). suiviRenderSelecteurs déplace les <label>
// correspondants (data-suivi-sel="<type>") du pool vers la barre 1, puis les
// remet. Les <select> gardent leurs IDs/handlers métier (déplacement, pas
// recréation). L'Année est un sélecteur GLOBAL, géré à part.
// Mémorisation par onglet (établissement) en localStorage, comme le
// référentiel mémorise ses sélections par portée.
// ─────────────────────────────────────────────────────────────────────────

// Établissement mémorisé (partagé EdT / Indispo / Progression).
let SUIVI_ETAB_ACTIF = (function () {
  try { return localStorage.getItem('suivi-etab-actif') || ''; }
  catch (e) { return ''; }
})();
let _SUIVI_ETABS_CACHE = null;

function suiviRenderSelecteurs() {
  const zone = document.getElementById('suivi-portee-selecteurs');
  const pool = document.getElementById('suivi-selecteurs-pool');
  if (!zone || !pool) return;

  // 1) Remettre dans le pool tout label actuellement dans la zone.
  Array.from(zone.querySelectorAll('[data-suivi-sel]')).forEach(el => pool.appendChild(el));
  zone.innerHTML = '';

  // 2) Déplacer, dans l'ordre déclaré, les labels de l'onglet actif.
  const def = SUIVI_ATELIER_PANNEAU[SUIVI_ATELIER_ACTIF] || {};
  const types = def.selecteurs || [];
  types.forEach(type => {
    const label = pool.querySelector('[data-suivi-sel="' + type + '"]');
    if (label) zone.appendChild(label);
  });

  // 3) Année globale : visible en portée Suivi annuel, masquée en Gestion.
  const anneeWrap = document.getElementById('suivi-annee-globale-wrap');
  if (anneeWrap) {
    anneeWrap.style.display = (SUIVI_PORTEE_ACTIVE === 'planification') ? '' : 'none';
  }

  // 4) Peupler les sélecteurs globaux affichés.
  suiviRemplirAnneeGlobale();
  if (types.indexOf('etablissement') >= 0) suiviRemplirEtabGlobal();
}

// Peuple le sélecteur d'année globale à partir de ANNEES.
function suiviRemplirAnneeGlobale() {
  const sel = document.getElementById('suivi-annee-globale');
  if (!sel) return;
  const annees = (typeof ANNEES !== 'undefined' && ANNEES.length)
    ? ANNEES : (ANNEE_ACTIVE ? [ANNEE_ACTIVE] : []);
  const cour = ANNEE_ACTIVE || (annees[0] || '');
  sel.innerHTML = annees.map(a =>
    `<option value="${a}"${a === cour ? ' selected' : ''}>${a}</option>`).join('');
  if (cour) sel.value = cour;
}

// Peuple le sélecteur d'établissement global (mémorisé).
async function suiviRemplirEtabGlobal() {
  const sel = document.getElementById('suivi-etab-global');
  if (!sel) return;
  if (!_SUIVI_ETABS_CACHE) {
    try {
      const r = await api('/api/etablissements');
      _SUIVI_ETABS_CACHE = (r && (r.etablissements || r)) || [];
    } catch (e) { _SUIVI_ETABS_CACHE = []; }
  }
  if (!SUIVI_ETAB_ACTIF && _SUIVI_ETABS_CACHE.length) {
    SUIVI_ETAB_ACTIF = _SUIVI_ETABS_CACHE[0].id;
  }
  sel.innerHTML = _SUIVI_ETABS_CACHE.map(e =>
    `<option value="${e.id}"${e.id === SUIVI_ETAB_ACTIF ? ' selected' : ''}>${escapeHtml(e.nom)}</option>`).join('');
  if (SUIVI_ETAB_ACTIF) sel.value = SUIVI_ETAB_ACTIF;
}

// Changement de l'année globale → ANNEE_ACTIVE + propagation + rechargement.
async function suiviAnneeGlobaleChange() {
  const sel = document.getElementById('suivi-annee-globale');
  if (!sel) return;
  ANNEE_ACTIVE = sel.value;
  try { localStorage.setItem('anneeActive', ANNEE_ACTIVE); } catch (e) {}
  const ai = document.getElementById('annee-sel'); if (ai) ai.value = ANNEE_ACTIVE;
  const ap = document.getElementById('prog-sel-annee'); if (ap) ap.value = ANNEE_ACTIVE;
  await suiviRechargerAtelierActif();
}

// Changement de l'établissement global → mémorisation + propagation + recharge.
async function suiviEtabGlobalChange() {
  const sel = document.getElementById('suivi-etab-global');
  if (!sel) return;
  SUIVI_ETAB_ACTIF = sel.value;
  try { localStorage.setItem('suivi-etab-actif', SUIVI_ETAB_ACTIF); } catch (e) {}
  await suiviRechargerAtelierActif();
}

// Après l'init d'un atelier (qui a pu peupler ses sélecteurs internes), forcer
// la valeur des globaux (année + établissement) et recharger si nécessaire.
async function _suiviAppliquerGlobaux(atelier) {
  // Amorcer l'établissement mémorisé depuis le sélecteur interne au 1er passage.
  if (!SUIVI_ETAB_ACTIF) {
    const srcId = atelier === 'edt' ? 'edt-etab'
      : (atelier === 'indispo' ? 'indispo-etab'
      : (atelier === 'progression' ? 'prog-sel-etab' : null));
    const src = srcId ? document.getElementById(srcId) : null;
    if (src && src.value) SUIVI_ETAB_ACTIF = src.value;
  }
  // Amorcer l'année globale si pas encore définie, depuis l'atelier.
  if (!ANNEE_ACTIVE && atelier === 'progression') {
    const pa = document.getElementById('prog-sel-annee');
    if (pa && pa.value) ANNEE_ACTIVE = pa.value;
  }
  await suiviRemplirEtabGlobal();
  suiviRemplirAnneeGlobale();
  const annee = ANNEE_ACTIVE, etab = SUIVI_ETAB_ACTIF || '';
  let recharge = false;
  if (atelier === 'edt') {
    const ea = document.getElementById('edt-annee');
    const ee = document.getElementById('edt-etab');
    if (ea && annee && ea.value !== annee) { ea.value = annee; recharge = true; }
    if (ee && etab && ee.value !== etab) { ee.value = etab; recharge = true; }
    if (recharge && typeof edtCharger === 'function') await edtCharger();
  } else if (atelier === 'indispo') {
    const ia = document.getElementById('indispo-annee');
    const ie = document.getElementById('indispo-etab');
    if (ia && annee && ia.value !== annee) { ia.value = annee; recharge = true; }
    if (ie && etab && ie.value !== etab) { ie.value = etab; recharge = true; }
    if (recharge && typeof indispoCharger === 'function') await indispoCharger();
  } else if (atelier === 'progression') {
    // progInit a peuplé prog-sel-annee/etab avec ses défauts (année courante).
    // On force l'année + l'établissement globaux, puis on re-déclenche le
    // chargement de la progression correspondante.
    const pa = document.getElementById('prog-sel-annee');
    const pe = document.getElementById('prog-sel-etab');
    if (pa && annee && pa.value !== annee) { pa.value = annee; recharge = true; }
    if (pe && etab && pe.value !== etab) { pe.value = etab; recharge = true; }
    if (recharge && window.ATELIER_PROGRESSION
        && typeof window.ATELIER_PROGRESSION.onSelecteurChange === 'function') {
      await window.ATELIER_PROGRESSION.onSelecteurChange();
    }
  }
}

// Recharge l'atelier actif en propageant les globaux vers ses sélecteurs
// internes et en appelant sa fonction de (re)chargement.
async function suiviRechargerAtelierActif() {
  const a = SUIVI_ATELIER_ACTIF;
  const annee = ANNEE_ACTIVE, etab = SUIVI_ETAB_ACTIF || '';
  if (a === 'edt') {
    const ea = document.getElementById('edt-annee'); if (ea) ea.value = annee;
    const ee = document.getElementById('edt-etab');  if (ee) ee.value = etab;
    if (typeof edtCharger === 'function') await edtCharger();
  } else if (a === 'indispo') {
    const ia = document.getElementById('indispo-annee'); if (ia) ia.value = annee;
    const ie = document.getElementById('indispo-etab');  if (ie) ie.value = etab;
    if (typeof indispoCharger === 'function') await indispoCharger();
  } else if (a === 'progression') {
    const pa = document.getElementById('prog-sel-annee'); if (pa) pa.value = annee;
    const pe = document.getElementById('prog-sel-etab');  if (pe) pe.value = etab;
    if (window.ATELIER_PROGRESSION
        && typeof window.ATELIER_PROGRESSION.onSelecteurChange === 'function') {
      await window.ATELIER_PROGRESSION.onSelecteurChange();
    }
  } else if (a === 'suivi' || a === 'debut' || a === 'observation') {
    // v0.42.1 — Même liste de classes pour les trois sous-onglets du Suivi.
    if (typeof onAnneeChange === 'function') await onAnneeChange();
    if (a === 'debut' && typeof scInit === 'function') await scInit();   // v0.43.0
  } else if (a === 'plans') {          // v0.39.0
    if (typeof pcInit === 'function') await pcInit();
  }
}

// ── v0.42.0 — Onglet « Système » : Administration / Préférences ────────────
function _systemeSousOnglet() {
  let s = null;
  try { s = localStorage.getItem('systeme-sous-onglet'); } catch (e) {}
  return (s === 'preferences') ? 'preferences' : 'admin';
}

function _prefInitialiser() {
  // v0.9 — Recharger les chemins de configuration à chaque entrée dans les
  // Préférences (ils peuvent avoir été modifiés ailleurs).
  if (typeof prefCheminsCharger === 'function') prefCheminsCharger();
  // v0.9.3 — Hauteur des textareas LaTeX
  if (typeof prefChargerHauteurLatex === 'function') prefChargerHauteurLatex();
  // v0.10.1 — Critères pré-remplis de l'objectif Connaître
  if (typeof prefChargerCriteresConnaitre === 'function') prefChargerCriteresConnaitre();
  // v0.18.4 — Paramètres de compilation + état replié/déplié des sections.
  if (typeof prefChargerParamsCompilation === 'function') prefChargerParamsCompilation();
  if (typeof prefCatInitEtats === 'function') prefCatInitEtats();
}

function systemeSwitch(sous) {
  if (sous !== 'admin' && sous !== 'preferences') sous = 'admin';
  try { localStorage.setItem('systeme-sous-onglet', sous); } catch (e) {}
  const sys = document.getElementById('tab-systeme');
  if (sys) sys.style.display = '';
  const admin = document.getElementById('tab-admin');
  const pref = document.getElementById('tab-preferences');
  if (admin) admin.style.display = (sous === 'admin') ? '' : 'none';
  if (pref) pref.style.display = (sous === 'preferences') ? '' : 'none';
  ['admin', 'preferences'].forEach(x => {
    const b = document.getElementById('systeme-btn-' + x);
    if (b) b.classList.toggle('active', x === sous);
  });
  if (sous === 'admin' && typeof adminSousOnglet === 'function') adminSousOnglet('importref');
  if (sous === 'preferences') _prefInitialiser();
}

// Point d'entrée à l'ouverture de l'onglet « Suivi de classe ».
function suiviInit() {
  suiviPorteeSwitch(SUIVI_PORTEE_ACTIVE, /*depuisInit=*/true);
}

// v0.19.1.2 — Shim de compatibilité : l'ancien sousOnglet(nom) est encore
// appelé ailleurs (selectClasse → 'suivi', gestionAllerEtablissements, etc.).
// On le mappe sur la nouvelle navigation.
function sousOnglet(nom) {
  const MAP = {
    progression: { portee: 'planification', atelier: 'progression' },
    suivi:       { portee: 'suivi', atelier: 'suivi' },
    parametrage: { portee: 'gestion', atelier: 'classe' },
  };
  const cible = MAP[nom] || MAP['suivi'];
  if (SUIVI_PORTEE_ACTIVE !== cible.portee) {
    SUIVI_ATELIER_ACTIF = cible.atelier;  // pour que suiviPorteeSwitch le retienne
    suiviPorteeSwitch(cible.portee, /*depuisInit=*/true);
  } else {
    suiviSwitch(cible.atelier);
  }
}

async function loadClasses() {
  const url = ANNEE_ACTIVE ? `/api/classes?annee=${encodeURIComponent(ANNEE_ACTIVE)}` : '/api/classes';
  const d = await api(url);
  CLASSES = d.classes || [];
}

async function loadSuiviNiveaux() {
  if (!currentCid) return;
  // v0.6.1 : les séquences du suivi viennent du référentiel rattaché à la
  // progression de la classe (pas du YAML courant). La route retourne
  // { source, referentiel_id, sequences } ; on extrait sequences.
  const [suiviData, nivData, seqData] = await Promise.all([
    api('/api/suivi?classe='+currentCid),
    api('/api/niveaux?classe='+currentCid),
    api('/api/classes/'+currentCid+'/sequences'),
  ]);
  suivi   = suiviData;
  niveaux = nivData;
  SEQ     = seqData.sequences || [];
  // Optionnel : exposer la source et l'id pour debug / futur affichage UI
  SEQ_SOURCE      = seqData.source;
  SEQ_REFERENTIEL = seqData.referentiel_id;
}

function buildClasseSel() {
  const sel = document.getElementById('classe-sel');
  if (!sel) return;
  // v0.34.0 (étape A) — Filtrer la liste des classes du Suivi selon les
  // sélecteurs Établissement / Niveau / Année du bandeau (partagés avec la
  // Planification). Lève l'ambiguïté des classes homonymes (ex. plusieurs 4E4
  // d'années différentes).
  const etabSel   = document.getElementById('prog-sel-etab');
  const nivSel    = document.getElementById('prog-sel-niveau');
  const anneeGlob = (typeof ANNEE_ACTIVE !== 'undefined' && ANNEE_ACTIVE) || '';
  const fEtab = etabSel ? etabSel.value : '';
  const fNiv  = nivSel ? nivSel.value : '';
  let liste = CLASSES.slice();
  if (fEtab) liste = liste.filter(c => (c.etablissement_id||'') === fEtab
                                     || (c.etablissement||'') === fEtab);
  if (fNiv)  liste = liste.filter(c => (c.niveau||'') === fNiv);
  if (anneeGlob) liste = liste.filter(c => (c.annee||'') === anneeGlob);

  // Afficher l'année si plusieurs années coexistent (désambiguïsation).
  const annees = new Set(liste.map(c=>c.annee).filter(Boolean));
  const etabs  = new Set(liste.map(c=>c.etablissement).filter(Boolean));
  sel.innerHTML = '<option value="">— Choisir une classe —</option>'
    + liste.map(c=>{
        let label = c.nom;
        const suff = [];
        if (etabs.size > 1 && c.etablissement) suff.push(c.etablissement);
        if (annees.size > 1 && c.annee) suff.push(c.annee);
        if (suff.length) label += ' (' + suff.join(' · ') + ')';
        return `<option value="${c.id}">${label}</option>`;
      }).join('');
  if (currentCid && liste.find(c=>c.id===currentCid)) sel.value = currentCid;
}

// v0.34.0 (étape A) — Rebâtir la liste des classes quand un filtre change.
function suiviClasseFiltresChange() {
  buildClasseSel();
}
window.suiviClasseFiltresChange = suiviClasseFiltresChange;

// v0.27.0 — Le sélecteur de niveau sert à plusieurs onglets. On route selon
// l'atelier actif : Progression de MER recharge sa progression ; sinon on
// délègue à l'atelier Progression principale (comportement d'origine).
// v0.34.0 (étape A) — Aiguille le changement d'établissement selon l'atelier
// actif : en Suivi de classe, refiltrer la liste des classes ; sinon, laisser
// l'atelier Progression gérer.
function onEtabChangeGlobal() {
  // v0.45.0 — Début de séance et Observation ont les mêmes sélecteurs que
  // Compétences (v0.42.1) : même refiltrage des classes.
  if (typeof SUIVI_ATELIER_ACTIF !== 'undefined'
      && ['suivi', 'debut', 'observation'].includes(SUIVI_ATELIER_ACTIF)) {
    if (typeof suiviClasseFiltresChange === 'function') suiviClasseFiltresChange();
    return;
  }
  // v0.35.0 (B1) — En Gestion (classe/etab), refiltrer la liste des classes.
  if (typeof SUIVI_ATELIER_ACTIF !== 'undefined'
      && (SUIVI_ATELIER_ACTIF === 'classe' || SUIVI_ATELIER_ACTIF === 'etab')) {
    if (typeof renderClassesList === 'function') renderClassesList();
    return;
  }
  if (window.ATELIER_PROGRESSION
      && typeof window.ATELIER_PROGRESSION.onSelecteurChange === 'function') {
    window.ATELIER_PROGRESSION.onSelecteurChange();
  }
}
window.onEtabChangeGlobal = onEtabChangeGlobal;

function onNiveauChangeGlobal() {
  // v0.34.0 (étape A) — En Suivi de classe, changer le niveau refiltre la liste
  // des classes.
  // v0.45.0 — Début de séance et Observation ont les mêmes sélecteurs que
  // Compétences (v0.42.1) : même refiltrage des classes.
  if (typeof SUIVI_ATELIER_ACTIF !== 'undefined'
      && ['suivi', 'debut', 'observation'].includes(SUIVI_ATELIER_ACTIF)) {
    if (typeof suiviClasseFiltresChange === 'function') suiviClasseFiltresChange();
    return;
  }
  // v0.45.0 — Observables : définis par niveau.
  if (typeof SUIVI_ATELIER_ACTIF !== 'undefined' && SUIVI_ATELIER_ACTIF === 'observables') {
    if (typeof obsInit === 'function') obsInit();
    return;
  }
  // v0.35.0 (B1) — En Gestion, changer le niveau refiltre la liste des classes.
  if (typeof SUIVI_ATELIER_ACTIF !== 'undefined'
      && (SUIVI_ATELIER_ACTIF === 'classe' || SUIVI_ATELIER_ACTIF === 'etab')) {
    if (typeof renderClassesList === 'function') renderClassesList();
    return;
  }
  if (typeof SUIVI_ATELIER_ACTIF !== 'undefined' && SUIVI_ATELIER_ACTIF === 'progmer'
      && typeof progMerCharger === 'function') {
    progMerCharger();
    return;
  }
  if (window.ATELIER_PROGRESSION
      && typeof window.ATELIER_PROGRESSION.onNiveauChange === 'function') {
    window.ATELIER_PROGRESSION.onNiveauChange();
  }
}

async function onClasseChange() {
  const cid = document.getElementById('classe-sel').value;
  // v0.43.0 — Début de séance : séances du jour de la classe choisie.
  if (typeof SUIVI_ATELIER_ACTIF !== 'undefined' && SUIVI_ATELIER_ACTIF === 'debut'
      && typeof scClasseChangee === 'function') {
    currentCid = cid || null;
    scClasseChangee();
    return;
  }
  // v0.24.1 — Si l'onglet Mises en route est actif, rafraîchir son planning.
  if (typeof SUIVI_ATELIER_ACTIF !== 'undefined' && SUIVI_ATELIER_ACTIF === 'mer'
      && typeof merAfficherPlanning === 'function') {
    merAfficherPlanning();
    if (typeof merChargerAffectation === 'function') merChargerAffectation();
    return;
  }
  // v0.27.0 — Onglet Progression de MER : le planning dépend de la classe.
  if (typeof SUIVI_ATELIER_ACTIF !== 'undefined' && SUIVI_ATELIER_ACTIF === 'progmer'
      && typeof progMerAfficherPlanning === 'function') {
    progMerAfficherPlanning();
    return;
  }
  if (!cid) { currentCid=null; showNoClasse(); return; }
  await selectClasse(cid);
}

async function selectClasse(cid) {
  // Assurer qu'on est sur l'onglet Suivi de classe, sous-onglet Suivi
  const tabClasse = document.getElementById('tab-classe');
  if (tabClasse && tabClasse.style.display === 'none') {
    document.querySelectorAll('.tab').forEach(b=>b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c=>c.style.display='none');
    document.querySelector('[data-tab="classe"]').classList.add('active');
    tabClasse.style.display='';
    sousOnglet('suivi');
  }
  currentCid = cid;
  localStorage.setItem('currentCid', cid);
  document.getElementById('classe-sel').value = cid;
  // Recharger les classes depuis le serveur pour avoir les élèves à jour
  await loadClasses();
  buildClasseSel();
  document.getElementById('classe-sel').value = cid;
  eleves = CLASSES.find(c=>c.id===cid)?.eleves || [];
  await loadSuiviNiveaux();
  // v0.34.0 — Déterminer séquence ET partie courantes AVANT de bâtir le
  // sélecteur (qui liste les parties).
  const savedSeq = localStorage.getItem('currentSeq_'+cid);
  if (savedSeq && SEQ.find(s=>s.code===savedSeq)) {
    currentSeq = savedSeq;
  } else if (SEQ.length) {
    currentSeq = SEQ[0].code;
  }
  const partiesDispo = _partiesDeSequence(getSeq(currentSeq));
  const savedPartie = parseInt(localStorage.getItem('currentPartie_'+cid) || '', 10);
  currentPartie = partiesDispo.includes(savedPartie) ? savedPartie : partiesDispo[0];
  buildSeqSel();
  showSuiviContent();
  buildElvSel();
  render();
}

function showNoClasse() {
  document.getElementById('no-classe').style.display='';
  document.getElementById('suivi-content').style.display='none';
}
function showSuiviContent() {
  document.getElementById('no-classe').style.display='none';
  document.getElementById('suivi-content').style.display='';
}

function buildSeqSel() {
  const sel = document.getElementById('seq-sel');
  // v0.34.0 — Une entrée par PARTIE de séquence (S03 · P1, S03 · P2…).
  // valeur = "<seqCode>|<partie>".
  const opts = [];
  SEQ.forEach(s => {
    const parties = _partiesDeSequence(s);
    parties.forEach(p => {
      const lib = parties.length > 1
        ? `${s.code} · P${p} — ${s.nom}`
        : `${s.code} — ${s.nom}`;
      opts.push(`<option value="${s.code}|${p}">${lib}</option>`);
    });
  });
  sel.innerHTML = opts.join('');
  sel.value = currentSeq + '|' + currentPartie;
}

function onSeqChange() {
  const v = document.getElementById('seq-sel').value;
  const [seqCode, partie] = v.split('|');
  currentSeq = seqCode;
  currentPartie = parseInt(partie || '1', 10);
  localStorage.setItem('currentSeq_'+currentCid, currentSeq);
  localStorage.setItem('currentPartie_'+currentCid, String(currentPartie));
  render();
}

function buildElvSel() {
  const sel = document.getElementById('elv-sel');
  sel.innerHTML = eleves.map(e=>`<option value="${e.id}">${e.nom} ${e.prenom}</option>`).join('');
  sel.onchange = () => renderEleveView();
}

function setView(v) {
  currentView = v;
  document.getElementById('view-classe').style.display = v==='classe'?'':'none';
  document.getElementById('view-eleve').style.display  = v==='eleve'?'':'none';
  document.getElementById('btn-vc').classList.toggle('active', v==='classe');
  document.getElementById('btn-ve').classList.toggle('active', v==='eleve');
  if (v==='eleve') renderEleveView();
}

function render() {
  if (currentView==='classe') renderClasseView();
  else renderEleveView();
}

function getSeq(code)         { return SEQ.find(s=>s.code===code); }
function getExos(seq,eid,s)   { return suivi[seq]?.[eid]?.[s]||[]; }
function getNiv(seq,eid,obj)  { return niveaux[seq]?.[eid]?.[obj]||'0'; }
function noteFromNiv(n) {
  const pts = nivPoints(n);
  return pts !== null ? pts : 0;  // A/D/NE ne comptent pas
}
function calcNote(seqCode,eid,partie) {
  const seq=getSeq(seqCode); if(!seq) return '—';
  // v0.34.0 — Si `partie` est fourni (vue classe par créneau), ne noter que les
  // objectifs de cette partie ; sinon toute la séquence (vue élève).
  const objs = (partie != null)
    ? _objectifsDeLaPartie(seq, partie)
    : seq.objectifs;
  const pts = objs
    .map(o => nivPoints(getNiv(seqCode,eid,o.code)))
    .filter(p => p !== null);
  if (!pts.length) return '—';
  return (pts.reduce((a,b)=>a+b,0)/pts.length).toFixed(1);
}
function badge(n) {
  const cl = 'b-' + n;
  const lb = nivLibelleCourt(n) || n;
  return `<span class="badge ${cl}">${lb}</span>`;
}

function renderClasseView() {
  const seq=getSeq(currentSeq);
  if (!seq||!eleves.length) {
    document.getElementById('main-tbl').innerHTML='<tr><td style="padding:20px;color:#999;text-align:center">Aucun élève — ajoutez des élèves dans l\'onglet Classes</td></tr>';
    document.getElementById('summary').innerHTML=''; return;
  }
  const objs=_objectifsDeLaPartie(seq,currentPartie);
  // v0.36.0 — Saisie simplifiée : une seule colonne « niveau » par objectif
  // (sélecteur direct). Plus de cases à cocher exercices/cours ni de dépliage :
  // l'enseignant juge lui-même le niveau de maîtrise atteint.
  let head='<thead><tr><th class="th-eleve">Élève</th>';
  objs.forEach(obj=>{
    head+=`<th class="th-obj" title="${obj.nom}"><div class="th-obj-lbl">obj.${obj.code}</div></th>`;
  });
  head+='<th class="th-note">Note<br>/20</th></tr></thead>';
  let body='<tbody>';
  eleves.forEach(e=>{
    // v0.36.1 — Prénom en entier (les élèves sont mieux identifiés par le prénom).
    body+=`<tr><td class="td-eleve">${e.prenom} ${e.nom}</td>`;
    objs.forEach(obj=>{
      const niv=getNiv(currentSeq,e.id,obj.code);
      // v0.36.2 — Fond de cellule indexé par CODE de niveau (niv-1…niv-4, niv-A…),
      // stylé par la palette unique §20 de app.css (teintes Pronote éclaircies).
      // Ne plus dériver la classe de NIV_REF.couleur : c'est ce qui avait produit
      // un fond bleu pour « Très bien » en v0.36.1.
      body+=`<td class="td-niv niv-${niv||'0'}"><select onchange="setNivManuel('${e.id}','${obj.code}',this.value)">${tousLesCodes().map(v=>`<option value="${v}" ${niv===v?'selected':''}>${nivLibelleCourt(v)}</option>`).join('')}</select></td>`;
    });
    body+=`<td class="td-note">${calcNote(currentSeq,e.id,currentPartie)}</td></tr>`;
  });
  body+='</tbody>';
  document.getElementById('main-tbl').innerHTML=head+body;
  renderSummary();
}

function renderSummary() {
  const seq=getSeq(currentSeq); if(!seq)return;
  // v0.36.1 — Compter sur les objectifs de la PARTIE affichée (cohérent avec le
  // tableau), pas sur toute la séquence.
  const objs=_objectifsDeLaPartie(seq,currentPartie);
  const cnt={};
  tousLesCodes().forEach(c=>cnt[c]=0);
  eleves.forEach(e=>objs.forEach(o=>{const c=getNiv(currentSeq,e.id,o.code);cnt[c]=(cnt[c]||0)+1;}));
  const notes=eleves.map(e=>parseFloat(calcNote(currentSeq,e.id,currentPartie))).filter(v=>!isNaN(v));
  const avg=notes.length?(notes.reduce((a,b)=>a+b,0)/notes.length).toFixed(1):'—';
  const badges=codesAvecNote().concat(codesSansNote())
    .filter(c=>cnt[c]>0)
    .map(c=>`${badge(c)} <strong>${cnt[c]}</strong>`)
    .join(' ');
  document.getElementById('summary').innerHTML=`<span>${eleves.length} élèves · moy. <strong>${avg}/20</strong> ·</span> ${badges}`;
}

function renderEleveView() {
  const eid=document.getElementById('elv-sel')?.value; if(!eid)return;
  document.getElementById('elv-detail').innerHTML=SEQ.map(s=>`<div class="seq-card-e"><h3>${s.code} — ${s.nom}<span style="margin-left:auto;font-weight:400;font-size:12px;color:#666">note : <strong>${calcNote(s.code,eid)}/20</strong></span></h3>${s.objectifs.map(obj=>{const niv=getNiv(s.code,eid,obj.code);const opts=tousLesCodes().map(v=>`<option value="${v}" ${niv===v?'selected':''}>${nivLibelleCourt(v)}</option>`).join('');return `<div class="obj-row-e"><span class="obj-nom-e" title="${obj.nom}">obj.${obj.code} ${obj.nom}</span><select style="border:1px solid #d0cfc8;border-radius:4px;background:#fff;font-size:11px;padding:2px 4px" onchange="setNivManuelSeq('${s.code}','${eid}','${obj.code}',this.value)">${opts}</select></div>`;}).join('')}</div>`).join('');
}

async function _postExo(seqCode,eid,serie,num,on) {
  suivi[seqCode]=suivi[seqCode]||{};suivi[seqCode][eid]=suivi[seqCode][eid]||{F:[],A:[],E:[],cours:[]};
  const arr=suivi[seqCode][eid][serie]||[];
  if(on&&!arr.includes(num))arr.push(num);
  if(!on){const i=arr.indexOf(num);if(i!==-1)arr.splice(i,1);}
  suivi[seqCode][eid][serie]=arr;
  await api('/api/suivi/exo',{method:'POST',body:JSON.stringify({classe:currentCid,seq:seqCode,eleve_id:eid,serie,num,checked:on})});
}
async function toggleExo(eid,serie,num,el){const on=!el.classList.contains(serie+'-on');el.classList.toggle(serie+'-on',on);el.textContent=String(num);await _postExo(currentSeq,eid,serie,num,on);renderSummary();}
async function toggleCours(eid,step,el){const on=!el.classList.contains('cours-on');el.classList.toggle('cours-on',on);el.textContent=on?'✓':'';await _postExo(currentSeq,eid,'cours',step,on);}
async function toggleExoElv(seqCode,eid,serie,num,el){const on=!el.classList.contains(serie+'-on');el.classList.toggle(serie+'-on',on);el.textContent=String(num);await _postExo(seqCode,eid,serie,num,on);if(seqCode===currentSeq)renderSummary();}
async function toggleCoursElv(seqCode,eid,step,el){const on=!el.classList.contains('cours-on');el.classList.toggle('cours-on',on);el.textContent=on?'✓':['','fond.','avancé','explor.'][step];await _postExo(seqCode,eid,'cours',step,on);}

async function _postNiv(seqCode,eid,objCode,val){niveaux[seqCode]=niveaux[seqCode]||{};niveaux[seqCode][eid]=niveaux[seqCode][eid]||{};niveaux[seqCode][eid][objCode]=val;await api('/api/niveaux/set',{method:'POST',body:JSON.stringify({classe:currentCid,seq:seqCode,eleve_id:eid,obj_code:objCode,niveau:val})});}
async function setNivManuel(eid,objCode,val){await _postNiv(currentSeq,eid,objCode,val);renderClasseView();}
async function setNivManuelSeq(seqCode,eid,objCode,val){await _postNiv(seqCode,eid,objCode,val);}

function askCalc(){document.getElementById('confirm-strip').classList.add('show');}
function cancelCalc(){document.getElementById('confirm-strip').classList.remove('show');}
async function doCalc(){
  cancelCalc();
  const niveau=CLASSES.find(c=>c.id===currentCid)?.niveau||'N10';
  const res=await api('/api/niveaux/calculer',{method:'POST',body:JSON.stringify({classe:currentCid,seq:currentSeq,niveau_code:niveau})});
  if(res.niveaux)niveaux[currentSeq]=res.niveaux;
  renderClasseView();
}

function toggleObj(objCode){expanded[currentSeq+'_'+objCode]=!expanded[currentSeq+'_'+objCode];renderClasseView();}
function toggleAll(on){getSeq(currentSeq)?.objectifs.forEach(o=>{expanded[currentSeq+'_'+o.code]=on;});renderClasseView();}

// ═══ ONGLET CLASSES ══════════════════════════════════════════

// Cache global pour la vue "Gestion des classes" (toutes années confondues).
// Distinct de CLASSES (qui est filtré par année active pour le Suivi).
let CLASSES_TOUTES = null;

// v0.28.4 — Peuple les options des filtres établissement/année à partir des
// classes chargées (le niveau est fixe). Conserve la sélection courante.
function _majOptionsFiltresClasses(classes) {
  // v0.35.0 (B1) — Les filtres établissement/année ont migré vers le bandeau
  // partagé (pool), peuplé par les mécanismes communs. Plus rien à faire ici.
  return;
}

// v0.35.0 (B1) — Les filtres viennent maintenant du bandeau partagé (pool) :
// #prog-sel-etab (id établissement), #prog-sel-niveau, et l'année globale
// (ANNEE_ACTIVE). Plus de filtres en dur dans la Gestion.
function _filtrerClasses(classes) {
  const fe = (document.getElementById('prog-sel-etab') || {}).value || '';
  const fn = (document.getElementById('prog-sel-niveau') || {}).value || '';
  const fa = (typeof ANNEE_ACTIVE !== 'undefined' && ANNEE_ACTIVE) || '';
  return (classes || []).filter(c =>
    (!fe || (c.etablissement_id || '') === fe || (c.etablissement || '') === fe)
    && (!fa || c.annee === fa)
    && (!fn || c.niveau === fn));
}

function _renderClassesListFrom(classes) {
  const div = document.getElementById('classes-list');
  if (!div) return;
  _majOptionsFiltresClasses(classes);
  const filtrees = _filtrerClasses(classes);
  if (!filtrees || !filtrees.length) {
    const aucunTotal = !classes || !classes.length;
    div.innerHTML = '<p style="color:#999;font-size:12px;padding:8px 0">'
      + (aucunTotal ? 'Aucune classe. Créez-en une.'
                    : 'Aucune classe ne correspond aux filtres.') + '</p>';
    return;
  }
  // Tri : année la plus récente en tête, puis par nom
  const tri = [...filtrees].sort((a, b) => {
    const ya = (a.annee || '').localeCompare(b.annee || '');
    return ya !== 0 ? -ya : (a.nom || '').localeCompare(b.nom || '');
  });
  div.innerHTML = tri.map(c => {
    const nbEl = (c.eleves || []).length;
    const metaStr = `${nbEl} élève${nbEl > 1 ? 's' : ''}`
      + (c.etablissement ? ` · ${c.etablissement}` : '')
      + (c.annee ? ` · ${c.annee}` : '');
    return `<div class="classe-card ${selectedCidDetail === c.id ? 'active' : ''}" onclick="showDetailClasse('${c.id}')"><span class="classe-badge">${c.niveau || 'N?'}</span><div class="classe-info"><div class="classe-nom">${c.nom}</div><div class="classe-meta">${metaStr}</div></div></div>`;
  }).join('');
}

function renderClassesList() {
  // 1) Rendu immédiat avec le cache ou, faute de mieux, avec CLASSES (filtré).
  //    Comme ça la zone n'est jamais vide le temps qu'une requête revienne.
  _renderClassesListFrom(CLASSES_TOUTES || CLASSES);

  // 2) Rafraîchissement async avec la liste complète (toutes années).
  //    Ne dépend pas du filtre d'année du Suivi.
  (async () => {
    try {
      const d = await api('/api/classes');
      CLASSES_TOUTES = d.classes || [];
      _renderClassesListFrom(CLASSES_TOUTES);
    } catch (e) {
      // En cas d'échec, on garde ce qui est déjà affiché (CLASSES filtré)
      console.warn('renderClassesList: /api/classes a échoué', e);
    }
  })();
}

function showDetailClasse(cid) {
  selectedCidDetail = cid;
  const c = (CLASSES_TOUTES || []).find(x => x.id === cid)
         || CLASSES.find(x => x.id === cid);
  if (!c) return;
  document.getElementById('classe-detail').style.display = '';
  document.getElementById('detail-titre').textContent = c.nom
    + (c.annee ? ` (${c.annee})` : '');
  document.getElementById('inp-csv').dataset.cid = cid;
  // v0.28.3 — Les cadres « Rythme A/B » et « Mises en route » ont été retirés
  // du détail de classe : le rythme est déduit de l'EdT, et la configuration
  // MER se fait dans l'onglet « Mises en route » (Suivi annuel). Les champs en
  // base (seances_A/B, mer_active, mer_mode) sont conservés et pilotés ailleurs.
  renderElevesListFor(c);
  renderClassesList();
}

// v0.28.3 — Fonctions retirées avec les cadres « Rythme A/B » et « Mises en
// route » du détail de classe (_majBlocMer, sauverMerClasse,
// ouvrirPlanningAutomatismes, sauverRythmeClasse). Le rythme se déduit de
// l'EdT ; la config MER est dans l'onglet « Mises en route ».

function renderElevesListFor(c) {
  const elvs = c.eleves || [];
  document.getElementById('nb-eleves').textContent = `${elvs.length} élève${elvs.length > 1 ? 's' : ''}`;
  document.getElementById('btn-vider').style.display = elvs.length ? '' : 'none';
  document.getElementById('eleves-list').innerHTML = elvs.length
    ? elvs.map((e, i) => `<div class="eleve-item"><span class="eleve-num">${i + 1}</span><span class="nom">${e.nom} ${e.prenom}</span><select class="eleve-sexe" aria-label="Sexe de ${e.prenom}" onchange="definirSexeEleve('${c.id}','${e.id}', this.value)">${['', 'M', 'F'].map(v => `<option value="${v}"${(e.sexe || '') === v ? ' selected' : ''}>${v || '—'}</option>`).join('')}</select><button class="btn-danger" style="padding:2px 7px;font-size:11px" onclick="deleteEleve('${c.id}','${e.id}','${e.nom} ${e.prenom}')">✕</button></div>`).join('')
    : '<p style="color:#999;font-size:12px">Aucun élève.</p>';
}

// v0.40.0 — Sexe d'un élève (pour l'aléatoire mixte des plans de classe).
async function definirSexeEleve(cid, eid, sexe) {
  try {
    const r = await fetch('/api/eleves/' + eid + '/sexe', { method: 'PUT',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sexe }) });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || 'Erreur');
    [CLASSES_TOUTES || [], CLASSES].forEach(liste => {
      const c = liste.find(x => x.id === cid);
      const e = c && (c.eleves || []).find(x => x.id === eid);
      if (e) e.sexe = d.sexe;
    });
  } catch (err) { alert(err.message); }
}

function renderElevesList(cid) {
  cid = cid || selectedCidDetail;
  const c = (CLASSES_TOUTES || []).find(x => x.id === cid)
         || CLASSES.find(x => x.id === cid);
  if (!c) return;
  renderElevesListFor(c);
}

function showCreateClasse(){
  document.getElementById('form-create').style.display='';
  crEtabRemplir();   // v0.41.2
  document.getElementById('cr-nom').focus();
}

// ── v0.41.2 — Établissement de la nouvelle classe : sélecteur + création ────
let _ACADEMIES = null;

async function _academies() {
  if (!_ACADEMIES) {
    try { _ACADEMIES = (await api('/api/academies')).academies || []; }
    catch (e) { _ACADEMIES = []; }
  }
  return _ACADEMIES;
}

function _optionsAcademies(liste, choisie) {
  return '<option value="">— choisir —</option>' + liste.map(a =>
    `<option value="${escapeHtml(a)}"${a === choisie ? ' selected' : ''}>${escapeHtml(a)}</option>`).join('');
}

async function crEtabRemplir(choisi) {
  const sel = document.getElementById('cr-etab');
  if (!sel) return;
  let etabs = [];
  try { etabs = (await api('/api/etablissements')).etablissements || []; } catch (e) {}
  etabs.sort((a, b) => (a.nom || '').localeCompare(b.nom || ''));
  const defaut = choisi
    || (typeof SUIVI_ETAB_ACTIF !== 'undefined' && SUIVI_ETAB_ACTIF)
    || (etabs[0] && etabs[0].id) || '';
  sel.innerHTML = etabs.length
    ? etabs.map(e => `<option value="${e.id}"${e.id === defaut ? ' selected' : ''}>${escapeHtml(e.nom)}</option>`).join('')
    : '<option value="">Aucun établissement : ajoutez-en un</option>';
}

async function crEtabNouveauOuvrir() {
  document.getElementById('cr-etab-nouveau').style.display = '';
  document.getElementById('cr-etab-err').textContent = '';
  document.getElementById('cr-etab-acad').innerHTML = _optionsAcademies(await _academies(), '');
  document.getElementById('cr-etab-nom').focus();
}

function crEtabNouveauFermer() {
  document.getElementById('cr-etab-nouveau').style.display = 'none';
}

async function crEtabNouveauCreer() {
  const err = document.getElementById('cr-etab-err');
  const nom = document.getElementById('cr-etab-nom').value.trim();
  const academie = document.getElementById('cr-etab-acad').value;
  if (!nom || !academie) { err.textContent = 'Le nom et l\'académie sont obligatoires.'; return; }
  try {
    const r = await fetch('/api/etablissements', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nom, academie,
        ville: document.getElementById('cr-etab-ville').value.trim() }) });
    const d = await r.json();
    if (!r.ok) { err.textContent = d.error || 'Erreur'; return; }
    crEtabNouveauFermer();
    ['cr-etab-nom', 'cr-etab-ville'].forEach(id => { document.getElementById(id).value = ''; });
    await crEtabRemplir(d.id);
    if (typeof chargerEtablissementsEtBandeau === 'function') chargerEtablissementsEtBandeau();
  } catch (e) { err.textContent = e.message; }
}
function hideCreateClasse(){document.getElementById('form-create').style.display='none';}

async function confirmCreateClasse() {
  const nom=document.getElementById('cr-nom').value.trim();
  if(!nom)return;
  if(!document.getElementById('cr-etab').value){alert('Choisissez ou ajoutez un établissement.');return;}
  try {
    const c=await api('/api/classes',{method:'POST',body:JSON.stringify({
      nom,
      niveau:document.getElementById('cr-niveau').value,
      annee:document.getElementById('cr-annee').value.trim(),
      etablissement_id:document.getElementById('cr-etab').value
    })});
    if(c.error){alert('Erreur : '+c.error);return;}
    CLASSES.push(c);
    hideCreateClasse();
    document.getElementById('cr-nom').value='';
    document.getElementById('cr-annee').value='';
    await chargerAnnees();
    renderClassesList();buildClasseSel();showDetailClasse(c.id);
  } catch(e) {
    alert('Erreur : '+e.message);
  }
}

async function deleteClasse() {
  const c=CLASSES.find(x=>x.id===selectedCidDetail); if(!c)return;
  if(!confirm(`Supprimer la classe « ${c.nom} » et toutes ses données ?`))return;
  await api('/api/classes/'+selectedCidDetail,{method:'DELETE'});
  CLASSES=CLASSES.filter(x=>x.id!==selectedCidDetail);
  if(currentCid===selectedCidDetail){currentCid=null;showNoClasse();}
  selectedCidDetail=null;
  document.getElementById('classe-detail').style.display='none';
  renderClassesList();buildClasseSel();
}

async function importCSV() {
  const inp=document.getElementById('inp-csv');
  const cid=inp.dataset.cid||selectedCidDetail;
  if(!inp.files[0]||!cid)return;
  const status=document.getElementById('import-status');
  status.textContent='Import en cours…';status.style.color='#666';
  const fd=new FormData(); fd.append('file',inp.files[0]);
  const r=await fetch('/api/classes/'+cid+'/eleves/import',{method:'POST',body:fd});
  const res=await r.json();
  if(res.error){status.textContent='Erreur : '+res.error;status.style.color='#dc2626';return;}
  const c=CLASSES.find(x=>x.id===cid);
  if(c)c.eleves=res.eleves;
  if(currentCid===cid){eleves=res.eleves;buildElvSel();render();}
  status.textContent=`${res.ajouts} ajouté${res.ajouts>1?'s':''}, ${res.ignores} ignoré${res.ignores>1?'s':''}`+(res.sexes_mis_a_jour?`, sexe renseigné pour ${res.sexes_mis_a_jour}`:'');
  status.style.color='#2d6a0a';
  inp.value='';
  renderElevesList(cid);renderClassesList();buildClasseSel();
}

async function addEleve() {
  const cid=selectedCidDetail; if(!cid)return;
  const nom=document.getElementById('inp-nom').value.trim();
  const prenom=document.getElementById('inp-prenom').value.trim();
  if(!nom||!prenom)return;
  const e=await api('/api/classes/'+cid+'/eleves',{method:'POST',body:JSON.stringify({nom,prenom})});
  const c=CLASSES.find(x=>x.id===cid);
  if(c){c.eleves.push(e);c.eleves.sort((a,b)=>a.nom.localeCompare(b.nom));}
  if(currentCid===cid){eleves=c.eleves;buildElvSel();render();}
  document.getElementById('inp-nom').value='';document.getElementById('inp-prenom').value='';
  renderElevesList(cid);renderClassesList();
}

async function deleteEleve(cid,eid,nom) {
  if(!confirm('Supprimer '+nom+' ?'))return;
  await api('/api/classes/'+cid+'/eleves/'+eid,{method:'DELETE'});
  const c=CLASSES.find(x=>x.id===cid);
  if(c)c.eleves=c.eleves.filter(e=>e.id!==eid);
  if(currentCid===cid){eleves=c.eleves;buildElvSel();render();}
  renderElevesList(cid);renderClassesList();
}

async function viderClasse() {
  const c=CLASSES.find(x=>x.id===selectedCidDetail);
  if(!c||!confirm('Supprimer tous les élèves de '+c.nom+' ?'))return;
  for(const e of [...(c.eleves||[])])await api('/api/classes/'+selectedCidDetail+'/eleves/'+e.id,{method:'DELETE'});
  c.eleves=[];
  if(currentCid===selectedCidDetail){eleves=[];buildElvSel();render();}
  renderElevesList(selectedCidDetail);renderClassesList();
}

document.getElementById('btn-export').onclick=async()=>{
  const url=currentCid?'/api/export?classe='+currentCid:'/api/export';
  const data=await api(url);
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
  a.download='suivi_'+(currentCid?CLASSES.find(c=>c.id===currentCid)?.nom||currentCid:'toutes')+'_'+new Date().toISOString().slice(0,10)+'.json';
  a.click();
};

document.getElementById('inp-import').onchange=async ev=>{
  const data=JSON.parse(await ev.target.files[0].text());
  await api('/api/import',{method:'POST',body:JSON.stringify(data)});
  await loadClasses();buildClasseSel();renderClassesList();
  if(currentCid)await selectClasse(currentCid);
  ev.target.value='';
};

init();


// ════════════════════════════════════════════════════════════════
// v0.6.4 — Préférences UX : mode split (édition + rendu côte-à-côte)
// ════════════════════════════════════════════════════════════════
//
// Persistance via localStorage sous la clé 'seqenseigne_pref_split'.
// Une classe `atelier-mode-split` est ajoutée à <body> quand le toggle
// est actif ; le CSS s'occupe du reste (cf. app.css).
//
// Restauration : on lit la pref dès le chargement et on applique le
// toggle (synchronisé avec la checkbox de l'onglet Préférences si elle
// est déjà dans le DOM, ce qui est le cas car index.html la définit
// statiquement).

const PREF_SPLIT_KEY = 'seqenseigne_pref_split';

function prefSplitEstActif() {
  return localStorage.getItem(PREF_SPLIT_KEY) === '1';
}

function prefSplitAppliquer(actif) {
  document.body.classList.toggle('atelier-mode-split', actif);
  // Si un atome est chargé dans un atelier, on déclenche le rendu PDF pour
  // qu'il s'affiche immédiatement dans le panneau de droite.
  //
  // v0.14.3 — Mécanisme unifié : ATELIER_<TYPE>.basculerOnglet('rendu') passe
  // par verifierCacheEtAfficher (auto-cache, auto-compile si la pref est active).
  // v0.17.0 — La détection ne s'appuie plus sur un btn-latex visible (ce bouton
  // a quitté la toolbar du haut pour la zone de rendu). On teste directement
  // l'`itemActif` de chaque instance (un seul atelier a un item à la fois).
  if (actif) {
    const instances = [
      'ATELIER_EXERCICE', 'ATELIER_NOTION', 'ATELIER_METHODE',
      'ATELIER_FICHE', 'ATELIER_CARTE',
    ];
    for (const nom of instances) {
      const atelier = window[nom];
      if (atelier && atelier.itemActif
          && typeof atelier.basculerOnglet === 'function') {
        atelier.basculerOnglet('rendu');
      }
    }
  }
}

function prefSplitToggle() {
  const cb = document.getElementById('pref-mode-split');
  const actif = !!(cb && cb.checked);
  localStorage.setItem(PREF_SPLIT_KEY, actif ? '1' : '0');
  prefSplitAppliquer(actif);
}

// Restaurer la préférence au chargement initial.
(function _initPrefSplit() {
  const actif = prefSplitEstActif();
  const cb = document.getElementById('pref-mode-split');
  if (cb) cb.checked = actif;
  prefSplitAppliquer(actif);
})();


// ════════════════════════════════════════════════════════════════════════
// v0.14.3 — Préférence : auto-compile à l'ouverture du Rendu PDF
// ════════════════════════════════════════════════════════════════════════
//
// Quand cochée (défaut), basculer sur l'onglet « Rendu PDF » d'un atome
// déclenche automatiquement sa compilation si le PDF en cache n'est pas
// à jour (route GET /rendu-pdf/info renvoie cache_valide=false). Évite
// le clic manuel sur « Compiler le rendu » à chaque édition.
//
// Quand décochée, comportement v0.13.7.6.1.1.2 préservé : auto-cache
// uniquement (PDF affiché instantanément si le hash du .tex correspond
// au PDF en cache), sinon placeholder « Cliquez sur Compiler ».
//
// Stockage : localStorage (cohérent avec pref-mode-split — préférence
// d'UX par poste de travail, pas paramètre technique partagé).
//
// Sémantique du défaut : la clé n'existe pas → considérée comme TRUE
// (par défaut auto-compile). Pour désactiver, il faut écrire '0'
// explicitement via le toggle. Choix cohérent avec « le défaut est le
// comportement le plus pratique au quotidien ».
//
// Référence par les ateliers : AtelierAtomique.verifierCacheEtAfficher
// teste `window.prefAutoCompileEstActive()` quand cache_valide=false
// pour décider entre auto-compile ou placeholder.

const PREF_AUTO_COMPILE_KEY = 'seqenseigne_pref_auto_compile';

function prefAutoCompileEstActive() {
  // Valeur par défaut = active (clé absente → on retourne true).
  // Désactivation explicite via '0', réactivation via '1'.
  return localStorage.getItem(PREF_AUTO_COMPILE_KEY) !== '0';
}

function prefAutoCompileToggle() {
  const cb = document.getElementById('pref-auto-compile');
  const actif = !!(cb && cb.checked);
  localStorage.setItem(PREF_AUTO_COMPILE_KEY, actif ? '1' : '0');
  // Pas d'effet immédiat : la préférence sera lue au prochain
  // basculement sur l'onglet Rendu PDF d'un atome. Si l'utilisateur
  // vient juste de cocher et a déjà l'onglet Rendu ouvert sur un
  // atome sans cache, il devra cliquer Compiler une dernière fois
  // ou rouvrir l'item. Choix conservateur : pas d'effet de bord
  // inattendu sur un état déjà affiché.
}

// Expose pour qu'AtelierAtomique puisse lire depuis le scope module.
window.prefAutoCompileEstActive = prefAutoCompileEstActive;
window.prefAutoCompileToggle    = prefAutoCompileToggle;

// Restaurer la préférence au chargement initial : la checkbox doit
// refléter l'état stocké (ou cochée par défaut si jamais touchée).
(function _initPrefAutoCompile() {
  const actif = prefAutoCompileEstActive();
  const cb = document.getElementById('pref-auto-compile');
  if (cb) cb.checked = actif;
})();


// ════════════════════════════════════════════════════════════════════════
// v0.9 — Préférences : gestion des chemins de l'environnement seqenseigne
// ════════════════════════════════════════════════════════════════════════
//
// Logique :
//   - Une racine commune (chemin_racine_seqenseigne) sert d'ancrage.
//   - 4 chemins dérivés : sources livrets, pdflatex, paquet, ref séquences.
//   - Pour chaque dérivé : checkbox d'override (cochée = saisie libre,
//     décochée = valeur calculée à partir de la racine + suffixe).
//   - Le suffixe relatif est porté par l'attribut data-suffixe sur la row
//     (single source of truth : doit correspondre à SOUS_CHEMINS_RELATIFS
//     côté Python — testé indirectement via la persistance + relecture).
//
// Une checkbox cochée + champ vide est traitée comme un override volontaire
// à chaîne vide ; côté Python, la chaîne vide retombe sur la dérivation
// (cf. test_override_vide_explicite_retombe_sur_derivation). On a donc une
// asymétrie volontaire : « décocher » dans l'UI revient bien à « pas
// d'override », même si Python serait clément avec une chaîne vide.

/**
 * Calcule une valeur dérivée naïvement (concaténation racine + suffixe).
 * Pas de validation côté UI : c'est juste pour afficher un placeholder
 * informatif. La résolution réelle est faite côté Python par Configuration.
 * On utilise '/' comme séparateur d'affichage : ça reste lisible sur
 * Windows et le backend Python normalise via Path() de toute façon.
 */
function prefDerive(racine, suffixe) {
  if (!racine) return '';
  const r = racine.replace(/[/\\]+$/, '');  // retire trailing slashes
  return r + (r.match(/[\\]/) ? '\\' : '/') + suffixe;
}

/**
 * Recalcule et affiche les 4 placeholders dérivés à partir de la racine
 * actuellement saisie. Appelé sur input de #pref-chemin-racine.
 * N'écrit rien en config ; juste rafraîchit l'affichage.
 */
function prefRecalculerDerives() {
  const racine = document.getElementById('pref-chemin-racine').value.trim();
  document.querySelectorAll('#pref-chemins-derives .pref-chemin-row').forEach(row => {
    const suffixe = row.getAttribute('data-suffixe') || '';
    const input   = row.querySelector('.pref-chemin-input');
    const cb      = row.querySelector('.pref-chemin-override');
    const derive  = prefDerive(racine, suffixe);
    if (cb && !cb.checked) {
      // Mode dérivé : on affiche la valeur calculée comme valeur du champ
      // (en lecture seule, fond grisé).
      input.value = derive;
    }
    // Le placeholder reste informatif même en mode override (pour que
    // l'utilisateur sache vers quoi il revient en décochant).
    input.placeholder = derive
      ? `(dérivé : ${derive})`
      : `(dérivé : <racine>/${suffixe})`;
  });
}

/**
 * Bascule entre mode dérivé (checkbox décochée) et mode override (cochée).
 * En mode override : champ éditable, fond normal, focus pour saisir.
 * En mode dérivé : champ verrouillé, valeur recalculée depuis la racine.
 */
function prefToggleOverride(cb) {
  const row   = cb.closest('.pref-chemin-row');
  const input = row.querySelector('.pref-chemin-input');
  if (cb.checked) {
    input.readOnly = false;
    input.style.background = 'var(--surface)';
    // Si l'input contenait un dérivé en lecture seule, on le garde comme
    // point de départ pour que l'utilisateur n'ait pas à tout retaper.
    input.focus();
  } else {
    input.readOnly = true;
    input.style.background = 'var(--surface-light)';
    // Recalcul du dérivé.
    prefRecalculerDerives();
  }
}

/**
 * Charge la configuration depuis l'API et applique aux champs.
 * Pour chaque chemin dérivé : si le backend renvoie une valeur non vide,
 * on coche l'override et on remplit ; sinon on laisse en mode dérivé.
 */
async function prefCheminsCharger() {
  let cfg;
  try {
    cfg = await api('/api/configuration');
  } catch (e) {
    document.getElementById('pref-status').innerHTML =
      `<span style="color:var(--danger)">Erreur de chargement : ${e.message || e}</span>`;
    return;
  }
  // Racine
  const inputRacine = document.getElementById('pref-chemin-racine');
  inputRacine.value = cfg.chemin_racine_seqenseigne || '';
  // Dérivés
  document.querySelectorAll('#pref-chemins-derives .pref-chemin-row').forEach(row => {
    const cle    = row.getAttribute('data-cle');
    const cb     = row.querySelector('.pref-chemin-override');
    const input  = row.querySelector('.pref-chemin-input');
    const valeur = cfg[cle] || '';
    if (valeur) {
      // Override actif
      cb.checked = true;
      input.readOnly = false;
      input.style.background = 'var(--surface)';
      input.value = valeur;
    } else {
      // Mode dérivé : la valeur affichée sera recalculée juste après
      cb.checked = false;
      input.readOnly = true;
      input.style.background = 'var(--surface-light)';
      input.value = '';
    }
  });
  // Recalcul après application des overrides (les non-overridés se remplissent)
  prefRecalculerDerives();
  document.getElementById('pref-status').textContent = '';
}

/**
 * Persiste la racine + les overrides actifs.
 * Pour les overrides inactifs (checkbox décochée) on envoie une chaîne
 * vide pour effacer un éventuel override antérieur en BDD config.
 */
async function prefEnregistrerChemins() {
  const racine = document.getElementById('pref-chemin-racine').value.trim();
  const updates = { chemin_racine_seqenseigne: racine };
  document.querySelectorAll('#pref-chemins-derives .pref-chemin-row').forEach(row => {
    const cle   = row.getAttribute('data-cle');
    const cb    = row.querySelector('.pref-chemin-override');
    const input = row.querySelector('.pref-chemin-input');
    if (cb.checked) {
      // Override actif : on persiste la valeur saisie
      updates[cle] = input.value.trim();
    } else {
      // Override inactif : on persiste '' pour que la dérivation prenne le relais
      updates[cle] = '';
    }
  });
  const status = document.getElementById('pref-status');
  const btn    = document.getElementById('pref-btn-enregistrer');
  btn.disabled = true;
  status.textContent = 'Enregistrement…';
  try {
    const r = await fetch('/api/configuration', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(updates),
    });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      throw new Error(d.error || `HTTP ${r.status}`);
    }
    status.innerHTML = '<span style="color:var(--success)">✓ Enregistré.</span>';
    // Re-render pour normaliser l'affichage (espaces trim, dérivés à jour)
    prefRecalculerDerives();
  } catch (e) {
    status.innerHTML = `<span style="color:var(--danger)">Erreur : ${e.message || e}</span>`;
  } finally {
    btn.disabled = false;
  }
}

// ════════════════════════════════════════════════════════════════════════
// v0.9.3 — Préférences : hauteur des textareas LaTeX
// ════════════════════════════════════════════════════════════════════════

/**
 * Charge la valeur courante de `atl_textarea_lignes` depuis l'API et
 * la place dans le champ de saisie. Appelée à l'entrée dans l'onglet
 * Préférences (cf. routeur de tabs).
 */
async function prefChargerHauteurLatex() {
  const inp = document.getElementById('pref-textarea-lignes');
  if (!inp) return;  // template plus ancien, on ne casse pas
  try {
    const cfg = await api('/api/configuration');
    const n = parseInt(cfg.atl_textarea_lignes, 10);
    inp.value = (Number.isFinite(n) && n >= 5) ? n : 25;
  } catch (e) {
    // En cas d'échec, on garde la valeur par défaut HTML (25)
  }
}

/**
 * Persiste la nouvelle valeur de hauteur, invalide le cache JS et
 * affiche un retour à l'utilisateur. La nouvelle hauteur ne s'applique
 * qu'à la prochaine ouverture d'un atelier — on ne refait pas le DOM
 * des ateliers déjà rendus pour rester simple.
 */
async function prefEnregistrerHauteurLatex() {
  const inp = document.getElementById('pref-textarea-lignes');
  const status = document.getElementById('pref-textarea-lignes-status');
  if (!inp || !status) return;
  let n = parseInt(inp.value, 10);
  if (!Number.isFinite(n) || n < 5) {
    n = 5;
    inp.value = '5';
  }
  status.textContent = 'Enregistrement…';
  try {
    const r = await fetch('/api/configuration', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ atl_textarea_lignes: n }),
    });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      throw new Error(d.error || `HTTP ${r.status}`);
    }
    // v0.9.3 — Invalide le cache JS pour que le prochain
    // atelAppliquerHauteurLatex re-fetch la valeur fraîche
    _ATL_TEXTAREA_LIGNES = null;
    status.innerHTML = '<span style="color:var(--success)">✓ Enregistré (s\'applique à la prochaine ouverture d\'atelier).</span>';
  } catch (e) {
    status.innerHTML = `<span style="color:var(--danger)">Erreur : ${e.message || e}</span>`;
  }
}


/**
 * v0.18.4 — Paramètres de compilation (déplacés du Rendu par lot vers
 * Préférences > Outils > Rendu par lot). Lecture/écriture via
 * /api/configuration (clés timeout_compilation_court_s, _long_s,
 * compilation_batch_max_erreurs_consecutives, tikz_libraries, tblr_libraries).
 * Les inputs pref-rdl-* restent dans le DOM en permanence (onglet masqué),
 * donc _compilLireParams() peut les lire au lancement d'un batch.
 */
async function prefChargerParamsCompilation() {
  const ids = {
    'pref-rdl-timeout-court': 'timeout_compilation_court_s',
    'pref-rdl-timeout-long':  'timeout_compilation_long_s',
    'pref-rdl-max-erreurs':   'compilation_batch_max_erreurs_consecutives',
    'pref-rdl-tikz-libs':     'tikz_libraries',
    'pref-rdl-tblr-libs':     'tblr_libraries',
  };
  // Si aucun input présent (template partiel), ne rien faire.
  if (!document.getElementById('pref-rdl-timeout-court')) return;
  try {
    const cfg = await api('/api/configuration');
    for (const [domId, cle] of Object.entries(ids)) {
      const el = document.getElementById(domId);
      if (el && cfg[cle] !== undefined && cfg[cle] !== null) {
        el.value = cfg[cle];
      }
    }
  } catch (e) {
    // Échec : on garde les valeurs par défaut HTML.
  }
}

async function prefEnregistrerParamsCompilation() {
  const status = document.getElementById('pref-rdl-status');
  const num = (id, min, parDefaut) => {
    const el = document.getElementById(id);
    let n = parseInt(el ? el.value : parDefaut, 10);
    if (!Number.isFinite(n) || n < min) { n = parDefaut; if (el) el.value = String(parDefaut); }
    return n;
  };
  const str = (id, parDefaut) => {
    const el = document.getElementById(id);
    return el ? el.value : parDefaut;
  };
  const payload = {
    timeout_compilation_court_s: num('pref-rdl-timeout-court', 1, 30),
    timeout_compilation_long_s:  num('pref-rdl-timeout-long', 1, 300),
    compilation_batch_max_erreurs_consecutives: num('pref-rdl-max-erreurs', 1, 5),
    tikz_libraries: str('pref-rdl-tikz-libs',
                        'babel,shapes.geometric,arrows.meta,positioning,calc'),
    tblr_libraries: str('pref-rdl-tblr-libs', 'booktabs,varwidth'),
  };
  if (status) status.textContent = 'Enregistrement…';
  try {
    const r = await fetch('/api/configuration', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      throw new Error(d.error || `HTTP ${r.status}`);
    }
    if (status) status.innerHTML = '<span style="color:var(--success)">✓ Enregistré.</span>';
  } catch (e) {
    if (status) status.innerHTML = `<span style="color:var(--danger)">Erreur : ${e.message || e}</span>`;
  }
}


/**
 * v0.10.1 — Pré-remplit les champs Préférences > Atelier d'assemblage
 * avec les valeurs courantes en BDD (ou les défauts).
 */
async function prefChargerCriteresConnaitre() {
  const elNom = document.getElementById('pref-asm-nom');
  if (!elNom) return; // template plus ancien
  try {
    const cfg = await api('/api/configuration');
    const v = (cfg && cfg.atelier_assemblage_criteres_connaitre) || {};
    if (v.nom)       elNom.value = v.nom;
    const elF = document.getElementById('pref-asm-critF');
    const elA = document.getElementById('pref-asm-critA');
    const elE = document.getElementById('pref-asm-critE');
    if (elF && v.critere_F) elF.value = v.critere_F;
    if (elA && v.critere_A) elA.value = v.critere_A;
    if (elE && v.critere_E) elE.value = v.critere_E;
  } catch (e) {
    // valeurs HTML par défaut conservées
  }
}

/**
 * v0.10.1 — Persiste les critères pré-remplis de l'objectif Connaître.
 * Le nouvel atelier d'assemblage les utilise au moment du clic sur
 * « + Activer Connaître ». Les objectifs déjà créés ne sont pas affectés.
 */
async function prefEnregistrerCriteresConnaitre() {
  const status = document.getElementById('pref-asm-status');
  const elNom = document.getElementById('pref-asm-nom');
  const elF = document.getElementById('pref-asm-critF');
  const elA = document.getElementById('pref-asm-critA');
  const elE = document.getElementById('pref-asm-critE');
  if (!elNom || !elF || !elA || !elE || !status) return;
  status.textContent = 'Enregistrement…';
  try {
    const r = await fetch('/api/configuration', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        atelier_assemblage_criteres_connaitre: {
          nom:       elNom.value || 'Connaître les notions et les méthodes',
          critere_F: elF.value || '',
          critere_A: elA.value || '',
          critere_E: elE.value || '',
        },
      }),
    });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      throw new Error(d.error || `HTTP ${r.status}`);
    }
    status.innerHTML = '<span style="color:var(--success)">✓ Enregistré.</span>';
    setTimeout(() => { if (status.textContent.includes('✓')) status.textContent = ''; }, 3000);
  } catch (e) {
    status.innerHTML = `<span style="color:var(--danger)">Erreur : ${e.message || e}</span>`;
  }
}


/**
 * Pré-remplit les champs « chemin » des sous-onglets Admin depuis les
 * Préférences. Appelé à chaque entrée dans un sous-onglet concerné.
 *
 * Comportement :
 *   - Si le champ est vide, on le pré-remplit avec la valeur résolue.
 *   - Si l'utilisateur a déjà saisi quelque chose, on ne touche pas
 *     (override de session).
 *   - On ne persiste rien en config : les saisies Admin restent locales
 *     à la session, pour ne pas polluer les Préférences avec un chemin
 *     ponctuel.
 *
 * On utilise /api/configuration/chemins-resolus qui applique la règle
 * de dérivation côté backend (single source of truth pour la résolution).
 */
async function adminPreremplirChemins(sousOnglet) {
  let resolus;
  try {
    resolus = await api('/api/configuration/chemins-resolus');
  } catch (e) {
    return;  // silencieux : l'utilisateur peut toujours saisir manuellement
  }
  // Map : sous-onglet → [(idChamp, valeurResolue), ...]
  const cibles = {
    importref:    [['admin-chemin',              resolus.chemin_reference_sequences]],
    importpaquet: [['admin-importpaquet-chemin', resolus.chemin_paquet]],
    images:       [['admin-images-chemin',       resolus.chemin_reference_sequences]],
  };
  const liste = cibles[sousOnglet] || [];
  for (const [id, valeur] of liste) {
    const input = document.getElementById(id);
    if (input && !input.value && valeur) {
      input.value = valeur;
    }
  }
}


// ════════════════════════════════════════════════════════════════
// v0.6.4 — Raccourci Ctrl+L : ouvrir le LaTeX généré de l'atelier actif.
// v0.17.0 — Le bouton « LaTeX généré » a quitté la toolbar du haut pour la
// mini-toolbar de la zone de rendu (générée dynamiquement). On ne détecte donc
// plus l'atelier via un bouton visible : on cible directement l'INSTANCE de
// l'atelier dont le panneau est visible, et on appelle sa méthode voirLatex()
// si un item est chargé. Robuste quelle que soit la position du bouton.

document.addEventListener('keydown', (ev) => {
  if (!(ev.ctrlKey || ev.metaKey) || ev.key.toLowerCase() !== 'l') return;
  // Ne pas voler le Ctrl+L si on est dans un champ de saisie.
  const cible = ev.target;
  if (cible && /^(INPUT|TEXTAREA|SELECT)$/.test(cible.tagName)) return;

  // Panneau → instance globale (ateliers disposant d'un rendu LaTeX).
  const PANEL_VERS_INSTANCE = {
    'exercice':          'ATELIER_EXERCICE',
    'notion':            'ATELIER_NOTION',
    'methode':           'ATELIER_METHODE',
    'fiche':             'ATELIER_FICHE',
    'carte_automatisme': 'ATELIER_CARTE',
    'evaluation':        'ATELIER_EVALUATION',
  };
  const panel = (typeof atelTrouverPanelVisible === 'function')
    ? atelTrouverPanelVisible() : null;
  if (!panel) return;
  const nomInstance = PANEL_VERS_INSTANCE[panel];
  if (!nomInstance) return;
  const inst = window[nomInstance];
  // voirLatex() est un no-op si aucun item n'est chargé (garde interne).
  if (inst && typeof inst.voirLatex === 'function' && inst.itemActif) {
    ev.preventDefault();
    inst.voirLatex();
  }
});


// ════════════════════════════════════════════════════════════════
// ONGLET LIVRETS — gestion des versions
// ════════════════════════════════════════════════════════════════

let livSeqList = [];   // séquences du niveau courant
let livVersions = {};  // versions chargées { tag, date, label, objectifs, connaissances }

async function initLivrets() {
  await onLivNiveauChange();
}

async function onLivNiveauChange() {
  const niveau = document.getElementById('liv-niveau').value;
  const seqs = await api('/api/sequences?niveau=' + niveau);
  livSeqList = seqs;
  const sel = document.getElementById('liv-seq');
  sel.innerHTML = seqs.map(s => `<option value="${s.code}">${s.code} — ${s.nom}</option>`).join('');
  await onLivSeqChange();
}

async function onLivSeqChange() {
  const niveau = document.getElementById('liv-niveau').value;
  const seq    = document.getElementById('liv-seq').value;
  const seq_obj = livSeqList.find(s => s.code === seq);
  document.getElementById('liv-titre').textContent =
    seq ? `${seq} — ${seq_obj?.nom || ''}` : 'Versions disponibles';

  // Tag par défaut = date du jour
  const today = new Date().toISOString().slice(0,10);
  document.getElementById('liv-tag').value = today;

  await chargerVersions(niveau, seq);
}

async function chargerVersions(niveau, seq) {
  livVersions = await api(`/api/versions?niveau=${niveau}&seq=${seq}`);
  renderVersionsList(niveau, seq);
  renderAffectationClasses(niveau, seq);
}

function renderVersionsList(niveau, seq) {
  const div = document.getElementById('liv-versions-list');
  if (!livVersions.length) {
    div.innerHTML = '<div class="card" style="color:#999;font-size:12px">Aucune version déclarée pour cette séquence.</div>';
    return;
  }
  div.innerHTML = livVersions.slice().reverse().map(v => {
    const nbObj  = v.objectifs?.length || 0;
    const nbExos = v.objectifs?.reduce((acc, o) =>
      acc + (o.exercices?.fondamentaux?.length||0)
          + (o.exercices?.autonomes?.length||0)
          + (o.exercices?.enrichissement?.length||0), 0) || 0;
    const date = v.date ? new Date(v.date).toLocaleDateString('fr-FR') : '';
    const objList = (v.objectifs||[])
      .filter(o => o.exercices?.fondamentaux?.length || o.exercices?.autonomes?.length || o.exercices?.enrichissement?.length)
      .map(o => `<div style="font-size:11px;color:#555;padding:2px 0">
        <span style="font-weight:500">obj.${o.code}</span>
        <span style="color:#5a8a1a;margin-left:6px">F: ${(o.exercices.fondamentaux||[]).join(',')||'—'}</span>
        <span style="color:#1d5fa8;margin-left:4px">A: ${(o.exercices.autonomes||[]).join(',')||'—'}</span>
        <span style="color:#5b4ab3;margin-left:4px">E: ${(o.exercices.enrichissement||[]).join(',')||'—'}</span>
      </div>`).join('');

    return `<div class="card" style="margin-bottom:8px">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
        <span style="font-weight:600;font-size:14px">${v.tag}</span>
        <span style="font-size:12px;color:#666">${v.label !== v.tag ? v.label : ''}</span>
        <span style="margin-left:auto;font-size:11px;color:#aaa">${date} · ${nbObj} obj · ${nbExos} exos</span>
        <button class="btn-danger" style="padding:2px 8px;font-size:11px"
          onclick="supprimerVersion('${niveau}','${seq}','${v.tag}')">Supprimer</button>
      </div>
      <div style="border-top:0.5px solid #e8e8e4;padding-top:6px">${objList||'<span style="font-size:11px;color:#aaa">Pas d\'exercices renseignés</span>'}</div>
    </div>`;
  }).join('');
}

function renderAffectationClasses(niveau, seq) {
  const card = document.getElementById('liv-affectation-card');
  const div  = document.getElementById('liv-affectation-list');
  const classesNiveau = CLASSES.filter(c => c.niveau === niveau);
  if (!classesNiveau.length || !livVersions.length) {
    card.style.display = 'none'; return;
  }
  card.style.display = '';
  const key = `${niveau}_${seq}`;
  div.innerHTML = classesNiveau.map(c => {
    const actif    = c.versions_actives?.[key] || null;
    const verrouille = (c.sequences_verouillees||[]).includes(key);
    const opts = ['<option value="">— Aucune version —</option>']
      .concat(livVersions.map(v =>
        `<option value="${v.tag}" ${actif===v.tag?'selected':''}>${v.tag} — ${v.label}</option>`
      )).join('');
    const cadenas = verrouille
      ? '<span title="Verrouillée (résultats saisis)" style="color:#dc2626;font-size:14px;margin-left:6px">🔒</span>'
      : '';
    return `<div class="eleve-item">
      <span class="nom">${c.nom}${cadenas}</span>
      <select style="font-size:12px;border:1px solid #d0cfc8;border-radius:5px;padding:3px 6px;background:#fff"
        ${verrouille ? 'disabled title="Verrouillée"' : ''}
        onchange="setVersionClasse('${c.id}','${niveau}','${seq}',this.value)">
        ${opts}
      </select>
    </div>`;
  }).join('');
}

async function creerVersion() {
  const niveau = document.getElementById('liv-niveau').value;
  const seq    = document.getElementById('liv-seq').value;
  const tag    = document.getElementById('liv-tag').value.trim();
  const label  = document.getElementById('liv-label').value.trim();
  const status = document.getElementById('liv-create-status');

  if (!tag) { status.textContent = 'Le tag est requis.'; status.style.color='#dc2626'; return; }

  status.textContent = 'Création…'; status.style.color = '#666';
  const res = await api('/api/versions/creer', { method:'POST',
    body: JSON.stringify({ niveau, seq, tag, label }) });

  if (res.error) {
    status.textContent = 'Erreur : ' + res.error; status.style.color = '#dc2626'; return;
  }
  status.textContent = `Version "${tag}" créée.`; status.style.color = '#2d6a0a';
  document.getElementById('liv-label').value = '';
  await chargerVersions(niveau, seq);
}

async function supprimerVersion(niveau, seq, tag) {
  if (!confirm(`Supprimer la version "${tag}" ?`)) return;
  const res = await api('/api/versions/supprimer', { method:'POST',
    body: JSON.stringify({ niveau, seq, tag }) });
  if (res.error) { alert('Erreur : ' + res.error); return; }
  await chargerVersions(niveau, seq);
}

async function setVersionClasse(cid, niveau, seq, tag) {
  const res = await api(`/api/classes/${cid}/version`, { method:'POST',
    body: JSON.stringify({ niveau, seq, tag: tag || null }) });
  if (res.error) { alert(res.error); return; }
  // Mettre à jour le cache local
  const c = CLASSES.find(x => x.id === cid);
  if (c) {
    c.versions_actives = c.versions_actives || {};
    c.versions_actives[`${niveau}_${seq}`] = tag || null;
  }
  renderAffectationClasses(niveau, seq);
}

// (initLivrets déclenché via le gestionnaire central)


// ════════════════════════════════════════════════════════════════
// ONGLET COMPOSER — conception de livrets
// ════════════════════════════════════════════════════════════════

let cmpData = null;       // composition courante chargée depuis l'API
let cmpBiblio = null;     // bibliothèque d'exercices disponibles
let cmpModifie = false;   // y a-t-il des modifications non sauvegardées ?

// ── Initialisation ────────────────────────────────────────────
async function initComposer() {
  await onCmpNiveauChange();
}

async function onCmpNiveauChange() {
  const niveau = document.getElementById('cmp-niveau').value;
  const seqs = await api('/api/sequences?niveau=' + niveau);
  const sel = document.getElementById('cmp-seq');
  sel.innerHTML = seqs.map(s =>
    `<option value="${s.code}">${s.code} — ${s.nom}</option>`
  ).join('');
  await onCmpSeqChange();
}

async function onCmpSeqChange() {
  const niveau = document.getElementById('cmp-niveau').value;
  const seq    = document.getElementById('cmp-seq').value;
  if (!seq) return;
  document.getElementById('cmp-status').textContent = 'Chargement…';
  document.getElementById('cmp-tex-card').style.display = 'none';

  [cmpData, cmpBiblio] = await Promise.all([
    api(`/api/composition/${niveau}/${seq}`),
    api(`/api/bibliotheque/${niveau}/${seq}`),
  ]);
  cmpModifie = false;
  document.getElementById('cmp-status').textContent = '';
  renderComposer();
}

// ── Rendu principal ───────────────────────────────────────────
function renderComposer() {
  if (!cmpData) return;
  renderCmpObjectifs();
  renderCmpRevisions();
  renderCmpApercu();
}

function renderCmpObjectifs() {
  const div = document.getElementById('cmp-objectifs');
  // Dédupliquer les objectifs (éviter les obj01 en double)
  const seen = new Set();
  const objs = cmpData.objectifs.filter(o => {
    if (seen.has(o.code)) return false;
    seen.add(o.code); return true;
  });

  div.innerHTML = objs.map(obj => {
    if (obj.is01) return renderCmpObj01(obj);
    return renderCmpObjN(obj);
  }).join('');
}

function renderCmpObj01(obj) {
  return `<div class="card" style="margin-bottom:8px;border-left:3px solid var(--serie-cours)">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
      <span style="font-size:11px;font-weight:600;color:var(--serie-cours)">obj.${obj.code}</span>
      <span style="font-size:13px;font-weight:500;flex:1">${obj.nom}</span>
      ${obj.fin_cycle ? '<span style="font-size:10px;background:#fef3c7;color:#7c4a0b;padding:1px 6px;border-radius:10px">fin de cycle</span>' : ''}
    </div>
    <div style="font-size:11px;color:var(--text-secondary)">
      Cours, notions et méthodes — évalué via les fiches de résumé et l'oral.
    </div>
    ${obj.maitrise ? `
    <div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap">
      ${['TB','S','F'].map(niv => `<div style="flex:1;min-width:140px;background:var(--niv-${niv}-bg);color:var(--niv-${niv}-text);font-size:10px;padding:4px 7px;border-radius:var(--radius-sm)"><strong>${niv}</strong> ${obj.maitrise[niv]||''}</div>`).join('')}
    </div>` : ''}
  </div>`;
}

function renderCmpObjN(obj) {
  const ex = obj.exercices;
  const makeSerie = (serie, nums, couleur, libelle) => {
    const cases = nums.map(n => {
      const actif = (ex[serie]||[]).includes(n);
      const cls = actif ? `${serie}-on` : '';
      return `<div class="cb ${cls}" title="${serie}${String(n).padStart(2,'0')}"
        onclick="cmpToggleExo('${obj.code}','${serie}',${n},this)">${n}</div>`;
    }).join('');
    const total = (ex[serie]||[]).length;
    return `<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
      <span style="font-size:10px;font-weight:600;color:${couleur};width:14px">${serie}</span>
      <div style="display:flex;gap:2px;flex-wrap:wrap;flex:1">${cases||'<span style="font-size:10px;color:var(--text-muted)">—</span>'}</div>
      <span style="font-size:10px;color:var(--text-muted)">${total}</span>
    </div>`;
  };

  const allF = cmpBiblio?.F?.map(e=>e.num) || [];
  const allA = cmpBiblio?.A?.map(e=>e.num) || [];
  const allE = cmpBiblio?.E?.map(e=>e.num) || [];

  return `<div class="card" style="margin-bottom:8px">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
      <span style="font-size:11px;font-weight:600;color:var(--primary)">obj.${obj.code}</span>
      <span style="font-size:13px;font-weight:500;flex:1">${obj.nom}</span>
      ${obj.fin_cycle ? '<span style="font-size:10px;background:#fef3c7;color:#7c4a0b;padding:1px 6px;border-radius:10px">fin de cycle</span>' : ''}
    </div>
    ${obj.maitrise ? `
    <div style="display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap">
      ${['TB','S','F'].map(niv => `<div style="flex:1;min-width:120px;background:var(--niv-${niv}-bg);color:var(--niv-${niv}-text);font-size:10px;padding:3px 6px;border-radius:var(--radius-sm)"><strong>${niv}</strong> ${obj.maitrise[niv]||''}</div>`).join('')}
    </div>` : ''}
    <div style="border-top:1px solid var(--border-light);padding-top:8px">
      <div style="font-size:11px;color:var(--text-secondary);margin-bottom:6px">
        Exercices disponibles — cliquer pour inclure/exclure du livret :
      </div>
      ${makeSerie('fondamentaux', allF, 'var(--serie-F)', 'Fondamental')}
      ${makeSerie('autonomes',    allA, 'var(--serie-A)', 'Avancé')}
      ${makeSerie('enrichissement', allE, 'var(--serie-E)', 'Exploration')}
    </div>
  </div>`;
}

function cmpToggleExo(objCode, serie, num, el) {
  const obj = cmpData.objectifs.find(o => o.code === objCode);
  if (!obj) return;
  const arr = obj.exercices[serie] || [];
  const i = arr.indexOf(num);
  if (i === -1) arr.push(num);
  else arr.splice(i, 1);
  arr.sort((a,b)=>a-b);
  obj.exercices[serie] = arr;
  const actif = arr.includes(num);
  el.classList.toggle(`${serie}-on`, actif);
  cmpModifie = true;
  renderCmpApercu();
  document.getElementById('cmp-status').textContent = '● Modifications non sauvegardées';
  document.getElementById('cmp-status').style.color = 'var(--warning-text)';
}

function renderCmpRevisions() {
  const div = document.getElementById('cmp-revisions');
  const revDispos = cmpBiblio?.revisions || [];
  const revActives = cmpData?.prerequis?.exercices_revision || [];

  if (!revDispos.length) {
    div.innerHTML = '<p style="font-size:11px;color:var(--text-muted)">Aucun exercice de révision disponible.</p>';
    return;
  }

  const cases = revDispos.map(e => {
    const actif = revActives.includes(e.num);
    return `<div class="cb ${actif ? 'A-on' : ''}" title="${e.fichier}"
      onclick="cmpToggleRev(${e.num},this)">${e.num}</div>`;
  }).join('');

  div.innerHTML = `<div class="exo-row" style="flex-wrap:wrap">${cases}</div>
    <p style="font-size:10px;color:var(--text-muted);margin-top:6px">
      Exercices avancés N-1 · ${revActives.length} sélectionné${revActives.length>1?'s':''}
    </p>`;
}

function cmpToggleRev(num, el) {
  if (!cmpData.prerequis) cmpData.prerequis = { type:'annee_precedente', exercices_revision:[] };
  const arr = cmpData.prerequis.exercices_revision;
  const i = arr.indexOf(num);
  if (i === -1) arr.push(num); else arr.splice(i,1);
  arr.sort((a,b)=>a-b);
  el.classList.toggle('A-on', arr.includes(num));
  cmpModifie = true;
  renderCmpApercu();
  document.getElementById('cmp-status').textContent = '● Modifications non sauvegardées';
  document.getElementById('cmp-status').style.color = 'var(--warning-text)';
}

function renderCmpApercu() {
  const div = document.getElementById('cmp-apercu');
  if (!cmpData) return;

  const rev = cmpData.prerequis?.exercices_revision || [];
  const seen = new Set();
  const exF = [], exA = [], exE = [];
  for (const obj of cmpData.objectifs) {
    if (obj.is01 || seen.has(obj.code)) continue;
    seen.add(obj.code);
    exF.push(...(obj.exercices.fondamentaux||[]));
    exA.push(...(obj.exercices.autonomes||[]));
    exE.push(...(obj.exercices.enrichissement||[]));
  }
  const uF = [...new Set(exF)].sort((a,b)=>a-b);
  const uA = [...new Set(exA)].sort((a,b)=>a-b);
  const uE = [...new Set(exE)].sort((a,b)=>a-b);

  const ligne = (label, nums, couleur) => nums.length
    ? `<div style="display:flex;gap:6px;margin-bottom:3px;align-items:baseline">
        <span style="font-size:10px;font-weight:600;color:${couleur};width:60px">${label}</span>
        <span style="font-size:11px">${nums.join(', ')}</span>
       </div>` : '';

  div.innerHTML = `
    <div style="margin-bottom:8px">
      <div style="font-size:11px;font-weight:500;margin-bottom:4px;color:var(--text-secondary)">Révisions</div>
      ${rev.length ? `<div style="font-size:11px">${rev.join(', ')}</div>` : '<div style="font-size:11px;color:var(--text-muted)">—</div>'}
    </div>
    <div>
      <div style="font-size:11px;font-weight:500;margin-bottom:4px;color:var(--text-secondary)">Exercices</div>
      ${ligne('Fond.', uF, 'var(--serie-F)')}
      ${ligne('Avancé', uA, 'var(--serie-A)')}
      ${ligne('Explor.', uE, 'var(--serie-E)')}
      ${!uF.length && !uA.length && !uE.length ? '<div style="font-size:11px;color:var(--text-muted)">Aucun exercice sélectionné</div>' : ''}
    </div>
    <div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--border-light);font-size:11px;color:var(--text-secondary)">
      Total : ${rev.length} rév. · ${uF.length} F · ${uA.length} A · ${uE.length} E
      = ${rev.length+uF.length+uA.length+uE.length} exercices
    </div>`;
}

// ── Sauvegarde ────────────────────────────────────────────────
async function cmpSauvegarder() {
  const niveau = document.getElementById('cmp-niveau').value;
  const seq    = document.getElementById('cmp-seq').value;
  const status = document.getElementById('cmp-status');

  // Dédupliquer avant envoi
  const seen = new Set();
  const objetifsPayload = cmpData.objectifs
    .filter(o => { if(seen.has(o.code)) return false; seen.add(o.code); return true; })
    .map(o => ({ code: o.code, exercices: o.exercices, notions: o.notions || [] }));

  status.textContent = 'Enregistrement…'; status.style.color = 'var(--text-secondary)';
  const res = await api(`/api/composition/${niveau}/${seq}`, {
    method: 'PUT',
    body: JSON.stringify({ objectifs: objetifsPayload, prerequis: cmpData.prerequis })
  });

  if (res.error) {
    status.textContent = 'Erreur : ' + res.error; status.style.color = 'var(--danger)';
  } else {
    cmpModifie = false;
    status.textContent = '✓ Enregistré'; status.style.color = 'var(--success)';
    setTimeout(() => { status.textContent = ''; }, 3000);
  }
}

// ── Génération .tex ───────────────────────────────────────────
async function cmpGenererTex() {
  const niveau = document.getElementById('cmp-niveau').value;
  const seq    = document.getElementById('cmp-seq').value;
  const status = document.getElementById('cmp-status');

  if (cmpModifie) {
    await cmpSauvegarder();
  }

  status.textContent = 'Génération…'; status.style.color = 'var(--text-secondary)';
  const res = await api(`/api/composition/${niveau}/${seq}/generer`, {
    method: 'POST',
    body: JSON.stringify({})
  });

  if (res.error) {
    status.textContent = 'Erreur : ' + res.error; status.style.color = 'var(--danger)';
    return;
  }

  document.getElementById('cmp-tex-output').value = res.tex;
  document.getElementById('cmp-tex-card').style.display = '';
  status.textContent = '✓ Généré'; status.style.color = 'var(--success)';
  setTimeout(() => { status.textContent = ''; }, 3000);
}

async function cmpEcrireFichier() {
  const niveau = document.getElementById('cmp-niveau').value;
  const seq    = document.getElementById('cmp-seq').value;
  const chemin = document.getElementById('cmp-chemin').value.trim();
  if (!chemin) { alert('Indiquez le chemin vers le dossier sequences.'); return; }

  const res = await api(`/api/composition/${niveau}/${seq}/generer`, {
    method: 'POST',
    body: JSON.stringify({ chemin_sequences: chemin })
  });

  if (res.error) { alert('Erreur : ' + res.error); return; }
  alert(res.fichier ? `Fichier écrit : ${res.fichier}` : 'Fichier écrit.');
}

function cmpCopierTex() {
  const ta = document.getElementById('cmp-tex-output');
  ta.select();
  document.execCommand('copy');
  const btn = ta.nextElementSibling;
}

// (initComposer déclenché via le gestionnaire central)

// ── Ateliers ──────────────────────────────────────────────────────────────────

let ATL_EXO = [];          // liste des exercices chargés
let ATL_EXERCICE_ACTIF = null;  // exercice en cours d'édition
// v0.14.6.b.1 — ATL_OBJ_CAT supprimé : peuplait l'ancien sélecteur
// #atl-exercice-obj-sel (DOM retiré v0.10) via /api/objectifs (route
// supprimée). L'atelier utilise désormais /api/objectifs-v2/.
// v0.10.7 — ATL_EXERCICE_OBJS retiré (zone "Objectifs associés" supprimée).
let ATL_SERIE = 'fondamental';       // série sélectionnée
let ATL_FILT = '';         // filtre série actif
// Filtres niveau/séquence communs aux 3 ateliers
let ATL_FILTRE_NIVEAU = '';
let ATL_FILTRE_SEQ    = '';

// v0.9.3 — Cache de la valeur `atl_textarea_lignes` lue dans la
// configuration. La 1re demande déclenche un fetch async ; toutes les
// suivantes retournent la valeur en cache. Si la config change pendant
// la session, l'utilisateur doit recharger la page (ou nous pourrions
// refetch sur invalidation, mais pas nécessaire pour l'instant).
let _ATL_TEXTAREA_LIGNES = null;

async function _atelLireHauteurLatex() {
  if (_ATL_TEXTAREA_LIGNES !== null) return _ATL_TEXTAREA_LIGNES;
  try {
    const cfg = await api('/api/configuration');
    const n = parseInt(cfg.atl_textarea_lignes, 10);
    _ATL_TEXTAREA_LIGNES = (Number.isFinite(n) && n >= 5) ? n : 25;
  } catch (e) {
    _ATL_TEXTAREA_LIGNES = 25;  // fallback silencieux
  }
  return _ATL_TEXTAREA_LIGNES;
}

/**
 * v0.9.3 — Applique la hauteur fixe à tous les `.latex-textarea` du
 * formulaire d'atelier passé en paramètre (id du conteneur).
 *
 * Idempotent : appelé à chaque entrée dans un atelier ; si la config
 * a changé, la nouvelle hauteur est appliquée. La fonction est sûre
 * même si atelier_commun.js n'est pas encore chargé.
 */
async function atelAppliquerHauteurLatex(idForm) {
  const lignes = await _atelLireHauteurLatex();
  if (typeof atelierFixerHauteurLatexTous === 'function') {
    const racine = document.getElementById(idForm);
    if (racine) atelierFixerHauteurLatexTous(racine, lignes);
  }
}

function initAteliers() {
  // v0.13.6.17 — Initialise ATL_PANEL_ACTIF au panneau visible par
  // défaut (exercice). Le HTML pose `active` sur atl-btn-exercice et
  // les autres atl-* sont cachés via CSS/JS. Sans cette init, le hook
  // atelier_filtres_hook.js ne sait pas quel atelier recharger au
  // premier changement de filtre (avant qu'on clique sur un onglet).
  if (typeof window.ATL_PANEL_ACTIF === 'undefined') {
    window.ATL_PANEL_ACTIF = 'exercice';
  }
  atelInitFiltres();
  // v0.14.6.b.1 — atelChargerObjectifs() retiré (fonction supprimée).
  atelChargerExercices();
  atelChargerNotions();
  atelChargerMethodes();
}

// v0.6.4 — Splitters cliquer-tirer
//
// Pour chaque atelier (exo, notion, méthode), on installe :
//   1. Un splitter aside↔main, toujours actif (même hors mode split).
//      Permet de redimensionner la liste à gauche.
//   2. Un splitter form↔rendu, dans le grid mode-split. Visible et
//      actionnable uniquement quand le mode split est activé (le CSS
//      cache la poignée hors mode split).
// Pour seqniv (Séquence niveau), on installe juste le splitter aside↔content.
//
// Cette fonction est idempotente (les helpers atelierInstallerSplitter /
// atelierInstallerSplitterGrid posent un marqueur dataset).
function initAtelierSplitters() {
  if (typeof atelierInstallerSplitter !== 'function') return;

  // Helpers de récupération sûre — return null si l'atelier n'est pas
  // encore dans le DOM (par exemple si un onglet n'a pas été visité).
  const $ = (sel) => document.querySelector(sel);

  // ── 4 ateliers : aside ↔ main ──
  // v0.11.4 — Ajout de l'atelier Fiche (oublié initialement). Pour
  // l'atelier Séquence, on installe aussi un splitter aside↔main mais
  // PAS de splitter form↔rendu (cf. plus bas) car cet atelier n'a pas
  // de mode côte-à-côte (un livret entier ne s'inspecte pas en colonne).
  const triplets = [
    {
      shell:  '#atl-exercice .atl-shell',
      aside:  '#atl-exercice .atl-sidebar',
      main:   '#atl-exercice .atl-main',
      keyAside: 'split:atl-exercice:aside',
      keySplit: 'split:atl-exercice:formrendu',
    },
    {
      shell:  '#atl-notion .atl-shell',
      aside:  '#atl-notion .atl-sidebar',
      main:   '#atl-notion .atl-main',
      keyAside: 'split:atl-notion:aside',
      keySplit: 'split:atl-notion:formrendu',
    },
    {
      shell:  '#atl-methode .atl-shell',
      aside:  '#atl-methode .atl-sidebar',
      main:   '#atl-methode .atl-main',
      keyAside: 'split:atl-methode:aside',
      keySplit: 'split:atl-methode:formrendu',
    },
    {
      shell:  '#atl-fiche .atl-shell',
      aside:  '#atl-fiche .atl-sidebar',
      main:   '#atl-fiche .atl-main',
      keyAside: 'split:atl-fiche:aside',
      keySplit: 'split:atl-fiche:formrendu',
    },
    // v0.13.6.2 — Splitter pour l'atelier Carte d'automatisme.
    // Structure HTML identique aux autres ateliers d'atomes
    // (.atl-shell > .atl-sidebar + .atl-main). Le splitter aside↔main
    // permet de redimensionner la sidebar (liste des cartes) vs la zone
    // principale (formulaire d'édition / iframe rendu PDF). On installe
    // AUSSI le splitter form↔rendu via initAtelierSplitterGrid pour
    // permettre l'affichage côte-à-côte édition/PDF.
    {
      shell:  '#atl-carte_automatisme .atl-shell',
      aside:  '#atl-carte_automatisme .atl-sidebar',
      main:   '#atl-carte_automatisme .atl-main',
      keyAside: 'split:atl-carte:aside',
      keySplit: 'split:atl-carte:formrendu',
    },
  ];
  for (const t of triplets) {
    const aside = $(t.aside);
    const main  = $(t.main);
    if (aside && main) {
      atelierInstallerSplitter({
        gauche: aside, droite: main,
        cleStockage: t.keyAside,
        largeurMinGauche: 200,
        largeurMinDroite: 300,
      });
      if (typeof atelierInstallerSplitterGrid === 'function') {
        atelierInstallerSplitterGrid({
          conteneur:   main,
          cleStockage: t.keySplit,
          ratioMinPct: 25,
          ratioMaxPct: 75,
        });
      }
    }
  }

  // ── seqniv (Séquence niveau) : aside ↔ content ──
  // L'écran de l'atelier Séquence est dans #atl-livret (ID historique
  // ; le panneau a gardé son nom "livret" même si l'atelier s'est
  // diversifié). Sa structure est .atl-shell > .atl-sidebar + .atl-main
  // (mêmes classes que les ateliers d'atomes).
  // v0.11.5 — Correction de l'ID : le code historique ciblait
  // #atl-seqniv qui n'a jamais existé dans le template, donc le splitter
  // n'a en fait jamais été installé pour cet atelier.
  const seqniv = $('#atl-livret .atl-shell');
  if (seqniv) {
    const sa = $('#atl-livret .atl-sidebar');
    const sm = $('#atl-livret .atl-main');
    if (sa && sm) {
      atelierInstallerSplitter({
        gauche: sa, droite: sm,
        cleStockage: 'split:atl-livret:aside',
        largeurMinGauche: 200,
        largeurMinDroite: 300,
      });
    }
  }

  // ── v0.13.5.1 — atl-referentiel : aside ↔ content ──
  // Atelier Référentiel (portée niveau). Même structure
  // .atl-shell > .atl-sidebar + .atl-main que les ateliers d'atomes.
  // ── v0.19.1.1 — Splitters manquants : harmonisation de tous les
  //    ateliers à structure .atl-shell > .atl-sidebar + .atl-main.
  //    Avant cette livraison, Progression (nouveau), Thème, Découpage en
  //    séquences et Évaluation n'avaient pas de poignée de redimensionnement
  //    de la barre latérale. On les ajoute pour uniformiser l'ergonomie.
  const shellsSimples = [
    { shell: '#stab-progression .atl-shell', cle: 'split:prog:aside' },
    { shell: '#atl-theme .atl-shell',        cle: 'split:atl-theme:aside' },
    { shell: '#atl-seqcycle .atl-shell',     cle: 'split:atl-seqcycle:aside' },
    { shell: '#atl-evaluation .atl-shell',   cle: 'split:atl-evaluation:aside' },
  ];
  for (const s of shellsSimples) {
    const shell = $(s.shell);
    if (!shell) continue;
    const aside = shell.querySelector('.atl-sidebar');
    const main  = shell.querySelector('.atl-main');
    if (aside && main) {
      atelierInstallerSplitter({
        gauche: aside, droite: main,
        cleStockage: s.cle,
        largeurMinGauche: 200,
        largeurMinDroite: 300,
      });
    }
  }
}

// Appel après init() — les ateliers sont déjà dans le DOM (pas de fetch).
// Délai 0ms pour laisser le navigateur faire le 1er layout.
setTimeout(initAtelierSplitters, 0);

// ── v0.10 : Portées d'ateliers ───────────────────────────────────────────
//
// Les ateliers sont organisés en 4 portées :
//   - sequence : Notion, Méthode, Exercice, Séquence, Fiche de résumé
//                → sélecteurs : niveau + séquence
//   - niveau   : Récap cours, Récap exos, Plans de travail
//                → sélecteur : niveau
//   - cycle    : Thème, Découpage en séquences
//                → sélecteur : cycle
//   - generaux : Rendu par lot
//                → aucun sélecteur de portée
//
// Les sélecteurs sont mémorisés par portée en localStorage. Ils pilotent
// les variables globales ATL_FILTRE_NIVEAU / ATL_FILTRE_SEQ (portées
// sequence et niveau) et la sélection ATL_SELECTIONS.cycle.cycle (portée
// cycle), lues directement par les ateliers via leur fonction d'init —
// invoquée par atelInvoquerInit() à chaque changement de filtre.

const ATL_PORTEES = {
  sequence: {
    label: 'Séquence',
    ateliers: ['exercice', 'notion', 'methode', 'fiche', 'carte_automatisme', 'livret'],
    selecteurs: ['niveau', 'sequence'],
  },
  niveau: {
    label: 'Niveau',
    // v0.15.1 — recapcours/recapexos/plantravail supprimés
    // (remplacés par Référentiel > Documents à publier)
    ateliers: ['evaluation', 'referentiel', 'referentiel_externe'],
    selecteurs: ['niveau'],
  },
  cycle: {
    label: 'Cycle',
    ateliers: ['theme', 'seqcycle'],
    selecteurs: ['cycle'],
  },
  generaux: {
    label: 'Outils généraux',
    ateliers: ['rdl', 'recherche'],
    selecteurs: [],
  },
};

// Toutes les valeurs d'ateliers gérées par atelSwitch (à plat).
const ATL_TOUS_ATELIERS = Object.values(ATL_PORTEES)
  .flatMap(p => p.ateliers);

// Niveaux disponibles pour le sélecteur (pas d'option "Tous" en v0.10).
const ATL_NIVEAUX_OPTIONS = [
  { code: 'N09', label: '6ème (N09)' },
  { code: 'N10', label: '5ème (N10)' },
  { code: 'N11', label: '4ème (N11)' },
  { code: 'N12', label: '3ème (N12)' },
];

// Séquences S01..S14 (fallback statique pour le cycle 4 — utilisé tant
// que la liste dynamique n'est pas chargée depuis l'API).
// v0.10.4.1 — Devenu un fallback : la vraie source est /api/cycles/<code>/sequences,
// chargée via atelChargerSequencesPourNiveau().
const ATL_SEQUENCES_OPTIONS =
  Array.from({length: 14}, (_, i) => `S${String(i + 1).padStart(2, '0')}`);

// v0.10.4.1 — Mapping niveau → cycle, et cache des séquences par cycle.
// Le mapping doit rester cohérent avec celui d'atelier_seqniv_assemblage.js.
function atelCyclePourNiveau(niveau) {
  if (!niveau) return 'C04';
  // N07/N08/N09 → C03 (cycle 3)
  // N10/N11/N12 → C04 (cycle 4)
  // Tout le reste → fallback C04 (à étendre quand lycée arrivera)
  if (niveau >= 'N07' && niveau <= 'N09') return 'C03';
  return 'C04';
}

// Cache des codes séquence par code cycle. Évite de re-fetcher à chaque
// changement de niveau dans le sélecteur.
const _ATL_SEQS_PAR_CYCLE_CACHE = {};

async function atelChargerSequencesPourCycle(cycle) {
  if (_ATL_SEQS_PAR_CYCLE_CACHE[cycle]) {
    return _ATL_SEQS_PAR_CYCLE_CACHE[cycle];
  }
  try {
    const r = await fetch(`/api/cycles/${encodeURIComponent(cycle)}/sequences`);
    if (!r.ok) {
      // Cycle non importé en BDD → fallback statique
      _ATL_SEQS_PAR_CYCLE_CACHE[cycle] = ATL_SEQUENCES_OPTIONS;
      return ATL_SEQUENCES_OPTIONS;
    }
    const data = await r.json();
    const seqs = (data && data.sequences) || [];
    if (seqs.length === 0) {
      _ATL_SEQS_PAR_CYCLE_CACHE[cycle] = ATL_SEQUENCES_OPTIONS;
      return ATL_SEQUENCES_OPTIONS;
    }
    // Trier par numéro et extraire les codes
    seqs.sort((a, b) => (a.numero || 0) - (b.numero || 0));
    const codes = seqs.map(s => s.code);
    _ATL_SEQS_PAR_CYCLE_CACHE[cycle] = codes;
    return codes;
  } catch (e) {
    _ATL_SEQS_PAR_CYCLE_CACHE[cycle] = ATL_SEQUENCES_OPTIONS;
    return ATL_SEQUENCES_OPTIONS;
  }
}

// Cycles : pour l'instant un seul (C04). Chargé dynamiquement depuis l'API
// au premier rendu pour rester future-proof.
let ATL_CYCLES_OPTIONS = null; // null = pas encore chargé

// Portée active. Reprise depuis localStorage à l'ouverture.
let ATL_PORTEE_ACTIVE = (function() {
  const sauv = localStorage.getItem('atl-portee-active');
  return (sauv && ATL_PORTEES[sauv]) ? sauv : 'sequence';
})();

// Sélections mémorisées par portée. Lazy-loaded depuis localStorage,
// avec fallback sur des valeurs par défaut.
function atelChargerSelections(portee) {
  const cle = `atl-portee-sel-${portee}`;
  try {
    const raw = localStorage.getItem(cle);
    if (raw) return JSON.parse(raw);
  } catch (e) { /* ignore parse error */ }
  // Valeurs par défaut
  if (portee === 'sequence') return { niveau: 'N10', sequence: 'S01' };
  if (portee === 'niveau')   return { niveau: 'N10' };
  if (portee === 'cycle')    return { cycle: 'C04' };
  return {};
}

function atelSauverSelections(portee, sel) {
  try {
    localStorage.setItem(`atl-portee-sel-${portee}`, JSON.stringify(sel));
  } catch (e) { /* quota dépassé : on ignore */ }
}

const ATL_SELECTIONS = {
  sequence: atelChargerSelections('sequence'),
  niveau:   atelChargerSelections('niveau'),
  cycle:    atelChargerSelections('cycle'),
  generaux: {},
};

// ── Initialisation ─────────────────────────────────────────────────────────

async function atelInitFiltres() {
  // Charger la liste des cycles depuis l'API (asynchrone, mais on continue
  // sans attendre — le rendu courant utilisera C04 par défaut, le rendu
  // suivant aura la liste complète).
  if (ATL_CYCLES_OPTIONS === null) {
    ATL_CYCLES_OPTIONS = []; // marque comme "en cours" pour éviter double appel
    try {
      const r = await window.api('/api/cycles');
      ATL_CYCLES_OPTIONS = (r.cycles || []).map(c => ({
        code: c.code, label: `${c.code} — ${c.nom}`,
      }));
    } catch (e) {
      ATL_CYCLES_OPTIONS = [{ code: 'C04', label: 'C04 — Cycle 4' }];
    }
    // Re-rendre les sélecteurs si on est en portée Cycle
    if (ATL_PORTEE_ACTIVE === 'cycle') atelRenderSelecteursPortee();
  }

  // Activer la portée mémorisée et appliquer ses sélections aux variables
  // globales et à l'UI.
  atelPorteeSwitch(ATL_PORTEE_ACTIVE, /*depuisInit=*/true);
}

// ── Bascule de portée ──────────────────────────────────────────────────────

function atelPorteeSwitch(portee, depuisInit = false) {
  // v0.10.6 — Garde de sortie : passer par la garde sauf appel
  // d'initialisation (où on ne veut pas spammer la modale au démarrage
  // alors qu'aucun atelier n'a de snapshot).
  if (depuisInit) return _atelPorteeSwitchReel(portee, depuisInit);
  if (typeof atelGardeAvantTransition === 'function') {
    return atelGardeAvantTransition(() => _atelPorteeSwitchReel(portee, depuisInit));
  }
  return _atelPorteeSwitchReel(portee, depuisInit);
}

function _atelPorteeSwitchReel(portee, depuisInit = false) {
  if (!ATL_PORTEES[portee]) return;
  ATL_PORTEE_ACTIVE = portee;
  localStorage.setItem('atl-portee-active', portee);

  // Mise à jour des boutons de portée
  Object.keys(ATL_PORTEES).forEach(p => {
    const btn = document.getElementById('atl-btn-portee-' + p);
    if (btn) btn.classList.toggle('active', p === portee);
  });

  // Affichage des boutons d'atelier de la portée (et masquage des autres)
  Object.keys(ATL_PORTEES).forEach(p => {
    document.querySelectorAll('.atl-grp-' + p).forEach(b => {
      b.style.display = p === portee ? '' : 'none';
    });
  });

  // Rendu des sélecteurs contextuels
  atelRenderSelecteursPortee();

  // Application des sélections mémorisées aux variables globales
  atelAppliquerSelectionsPortee();

  // Activation du premier atelier de la portée (ou du dernier ouvert,
  // mais pour l'instant le premier suffit). On passe par
  // _atelSwitchReel pour court-circuiter la garde déjà passée.
  const ateliers = ATL_PORTEES[portee].ateliers;
  if (ateliers.length > 0) _atelSwitchReel(ateliers[0]);
}

// ── Rendu des sélecteurs contextuels ──────────────────────────────────────

function atelRenderSelecteursPortee() {
  const zone = document.getElementById('atl-portee-selecteurs');
  if (!zone) return;
  const portee = ATL_PORTEE_ACTIVE;
  const selecteurs = ATL_PORTEES[portee].selecteurs;
  const sel = ATL_SELECTIONS[portee];

  zone.innerHTML = '';
  // v0.10.4.1 — Pour la portée séquence, on a deux sélecteurs (niveau, séquence)
  // dont les options du second dépendent du premier. On stocke la référence
  // au <select> séquence pour pouvoir le rafraîchir quand le niveau change.
  let selectSequenceRef = null;

  selecteurs.forEach(type => {
    const wrap = document.createElement('label');
    wrap.style.cssText =
      'display:flex;align-items:center;gap:6px;font-size:12px;' +
      'color:var(--text-muted)';

    let label = '', options = [];
    if (type === 'niveau') {
      label = 'Niveau';
      options = ATL_NIVEAUX_OPTIONS;
    } else if (type === 'sequence') {
      label = 'Séquence';
      // v0.10.4.1 — Liste construite dynamiquement selon le cycle du
      // niveau courant. On démarre avec un fallback statique pour avoir
      // un rendu immédiat, puis on rafraîchit en arrière-plan.
      options = ATL_SEQUENCES_OPTIONS.map(s => ({ code: s, label: s }));
    } else if (type === 'cycle') {
      label = 'Cycle';
      options = (ATL_CYCLES_OPTIONS && ATL_CYCLES_OPTIONS.length > 0)
        ? ATL_CYCLES_OPTIONS
        : [{ code: 'C04', label: 'C04 — Cycle 4' }];
    }

    const select = document.createElement('select');
    select.style.cssText = 'font-size:12px;padding:3px 6px';
    select.innerHTML = options.map(o =>
      `<option value="${o.code}">${o.label}</option>`
    ).join('');
    select.value = sel[type] || options[0].code;
    select.addEventListener('change', () => {
      // v0.10.6 — Garde de sortie : passer par la garde, et si
      // annulation, restaurer la valeur précédente du sélecteur.
      const valeurPrecedente = ATL_SELECTIONS[portee][type];
      const _continuer = () => {
        ATL_SELECTIONS[portee][type] = select.value;
        atelSauverSelections(portee, ATL_SELECTIONS[portee]);
        // v0.10.4.1 — Si on change le niveau dans la portée séquence, il
        // faut aussi rafraîchir le sélecteur de séquence (peut-être que
        // la séquence courante n'existe pas dans le nouveau cycle).
        if (type === 'niveau' && portee === 'sequence' && selectSequenceRef) {
          atelRafraichirSelectSequence(selectSequenceRef, select.value, portee);
        } else {
          atelAppliquerSelectionsPortee();
        }
      };
      if (typeof atelGardeAvantTransition === 'function') {
        // Capter la valeur cible AVANT de wrapper (l'utilisateur a déjà
        // cliqué) et restaurer si annulation.
        const valeurCible = select.value;
        select.value = valeurPrecedente;  // pré-restaure immédiatement
        atelGardeAvantTransition(() => {
          select.value = valeurCible;     // re-pose la cible si confirmé
          _continuer();
        });
      } else {
        _continuer();
      }
    });

    if (type === 'sequence') selectSequenceRef = select;

    wrap.appendChild(document.createTextNode(label + ' '));
    wrap.appendChild(select);
    zone.appendChild(wrap);
  });

  // v0.10.4.1 — Pour la portée séquence, charger les vraies séquences
  // du cycle correspondant au niveau courant et les injecter en
  // remplacement du fallback statique.
  if (portee === 'sequence' && selectSequenceRef) {
    const niveauCourant = sel.niveau;
    atelRafraichirSelectSequence(selectSequenceRef, niveauCourant, portee);
  }
}

// Rafraîchit le <select> séquence avec les codes du cycle correspondant
// au niveau donné. Préserve la valeur courante si elle existe dans la
// nouvelle liste, sinon prend la première.
async function atelRafraichirSelectSequence(selectEl, niveau, portee) {
  const cycle = atelCyclePourNiveau(niveau);
  const codes = await atelChargerSequencesPourCycle(cycle);
  const valeurCourante = ATL_SELECTIONS[portee].sequence;
  // v0.30.2 — Option « toutes les séquences » (valeur vide) : liste tous les
  // atomes du niveau, groupés par séquence (consultation/finition).
  selectEl.innerHTML = '<option value="">— Toutes les séquences —</option>'
    + codes.map(c => `<option value="${c}">${c}</option>`).join('');
  if (valeurCourante === '' || codes.includes(valeurCourante)) {
    selectEl.value = valeurCourante || '';
  } else {
    selectEl.value = codes[0] || 'S01';
    ATL_SELECTIONS[portee].sequence = selectEl.value;
    atelSauverSelections(portee, ATL_SELECTIONS[portee]);
  }
  atelAppliquerSelectionsPortee();
}

// ── Application des sélections aux variables globales et invocation init ──
//
// Cette fonction synchronise l'état UI avec les sélections mémorisées :
//   - Portée sequence : pose ATL_FILTRE_NIVEAU et ATL_FILTRE_SEQ, puis
//     re-rendu des listes (exercice/notion/methode) via atelRenderTous().
//     L'atelier visible (s'il n'est pas l'un des trois ci-dessus) reçoit
//     un appel à son init via atelInvoquerInit() pour se rafraîchir.
//   - Portée niveau : pose ATL_FILTRE_NIVEAU et invoque l'init de
//     l'atelier visible.
//   - Portée cycle : invoque l'init de l'atelier visible, qui ira lire
//     le cycle dans ATL_SELECTIONS.cycle.cycle.

function atelAppliquerSelectionsPortee() {
  const portee = ATL_PORTEE_ACTIVE;
  const sel = ATL_SELECTIONS[portee];

  if (portee === 'sequence') {
    ATL_FILTRE_NIVEAU = sel.niveau || '';
    ATL_FILTRE_SEQ    = sel.sequence || '';
    atelExposerFiltres();
    if (typeof atelRenderTous === 'function') atelRenderTous();
    // Les listes exercice/notion/methode sont rafraîchies par
    // atelRenderTous(). Les autres ateliers de la portée (livret) ont
    // leur propre init — on la déclenche si l'atelier est visible.
    const visible = atelTrouverPanelVisible();
    if (visible && !['exercice', 'notion', 'methode'].includes(visible)) {
      atelInvoquerInit(visible);
    }
  } else if (portee === 'niveau') {
    ATL_FILTRE_NIVEAU = sel.niveau || '';
    ATL_FILTRE_SEQ    = '';
    atelExposerFiltres();
    // v0.15.1 — Rafraîchir l'atelier visible (evaluation ou referentiel,
    // les seuls qui restent en portée Niveau depuis le retrait de Récap
    // cours / Récap exos / Plans de travail).
    const visible = atelTrouverPanelVisible();
    if (visible) atelInvoquerInit(visible);
  } else if (portee === 'cycle') {
    // Refonte v0.10 : les ateliers theme et seqcycle lisent désormais le
    // cycle directement depuis ATL_SELECTIONS.cycle.cycle. On invoque
    // simplement leur init si elle est visible — comme pour les autres
    // portées.
    atelExposerFiltres();
    const visible = atelTrouverPanelVisible();
    if (visible) atelInvoquerInit(visible);
  }
}

// Refonte v0.10 — Expose les globales de filtre sur `window` pour que les
// autres fichiers JS (chargés en IIFE) puissent y accéder. Sans ça, les
// variables déclarées avec `let` ou `const` au top-level d'un script
// classique ne sont PAS exposées sur l'objet global, contrairement aux
// `var`. Cette subtilité concerne aujourd'hui `atelier_seqniv_assemblage.js`
// qui lit ATL_FILTRE_NIVEAU/SEQ depuis sa propre IIFE.
function atelExposerFiltres() {
  window.ATL_FILTRE_NIVEAU = ATL_FILTRE_NIVEAU;
  window.ATL_FILTRE_SEQ    = ATL_FILTRE_SEQ;
  window.ATL_SELECTIONS    = ATL_SELECTIONS;
}

function atelFiltrerAtomes(liste) {
  if (ATL_FILTRE_NIVEAU) liste = liste.filter(a => a.niveau === ATL_FILTRE_NIVEAU);
  if (ATL_FILTRE_SEQ)    liste = liste.filter(a => a.sequence === ATL_FILTRE_SEQ);
  return liste;
}

// ── v0.13.4 — Helpers partagés sidebars ateliers d'atomes ─────────────────
//
// Refonte des sidebars Notion / Méthode / Fiche / Exercice sur le modèle
// visuel de l'atelier d'assemblage (.asm-item / .asm-cat). Centralise la
// génération d'un item et la persistance localStorage des sections
// repliables. Les 4 ateliers passent par ces helpers ; à terme (v0.14+)
// pourront être déplacés dans atelier_atome_generique.js si besoin.

// Échappement HTML minimal pour le contenu textuel inséré dans les items.
function _atelEsc(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// Échappement pour les attributs de tag (notamment onclick avec ID).
function _atelEscAttr(s) { return _atelEsc(s); }

// Génère le HTML d'un item de sidebar au format .asm-item--clickable.
// Paramètres :
//   - actif       : bool, ajoute la classe `active`
//   - onclick     : string JS exécuté au clic (ex. "atelExerciceCharger('id')")
//   - badge       : HTML optionnel d'un badge à gauche (.asm-item-badge--X)
//   - id          : string identifiant compact (ex. "N11/S04/F01")
//   - titre       : string OU { html, derive: bool } (italique si derive)
//   - placedTags  : tableau de strings affichées à droite (avant la
//                   pastille), grisées. Reprend le mécanisme du modèle
//                   d'assemblage : pour les ateliers d'atomes, contient
//                   les codes des objectifs liés (ex. ["02"], ["N10·S04·02"]).
//   - etatCode    : "valide" | "en_cours" — détermine la pastille ronde
//   - titleAttr   : tooltip natif sur l'élément (titre complet par défaut)
function atelAsmItemHtml(parts) {
  const cls = 'asm-item asm-item--clickable' + (parts.actif ? ' active' : '');
  const onclick = parts.onclick || '';
  const badge = parts.badge || '';
  const id = parts.id ? `<span class="atl-item-id">${_atelEsc(parts.id)}</span>` : '';

  let libHtml;
  let titleAttr = parts.titleAttr || '';
  if (parts.titre && typeof parts.titre === 'object') {
    const cls2 = 'asm-item-lib' + (parts.titre.derive ? ' atl-item-titre--derive' : '');
    libHtml = `<span class="${cls2}">${parts.titre.html || ''}</span>`;
    if (!titleAttr && parts.titre.html) titleAttr = parts.titre.html.replace(/<[^>]+>/g, '');
  } else {
    const t = parts.titre || '';
    libHtml = `<span class="asm-item-lib">${_atelEsc(t)}</span>`;
    if (!titleAttr) titleAttr = t;
  }

  // Tags d'objectifs liés à droite, repris du mécanisme placedTags du
  // modèle d'assemblage. Joint par espaces — utile quand un atome est
  // lié à plusieurs objectifs (ex. notion partagée).
  const tags = parts.placedTags || [];
  const tagsHtml = tags.length === 0 ? '' :
    `<span class="asm-item-placed-tag">${tags.map(_atelEsc).join(' ')}</span>`;

  // Pastille ronde d'état d'édition. Toujours présente (vert/gris) pour
  // distinguer visuellement les 2 états — différent du badge "Validé"
  // textuel d'avant-v0.13.4 qui n'apparaissait que pour les validés.
  const etat = parts.etatCode === 'valide' ? 'valide' : 'en_cours';
  const tipEtat = etat === 'valide' ? 'Validé' : 'En cours';
  const pastille =
    `<span class="asm-item-etat-badge atome-etat--${etat}" title="${tipEtat}"></span>`;

  const titleHtml = titleAttr ? ` title="${_atelEscAttr(titleAttr)}"` : '';
  return `<div class="${cls}" onclick="${onclick}"${titleHtml}>`
       + badge + id + libHtml + tagsHtml + pastille
       + `</div>`;
}

// Persistance localStorage de l'état (ouvert/fermé) des sections
// repliables. Clé : `seqenseigne.atl.<type>.cat.<serie>.collapsed` = "1"|"0".
function _atelCatStorageKey(type, serie) {
  return `seqenseigne.atl.${type}.cat.${serie}.collapsed`;
}

function atelCatEstReplie(type, serie, parDefaut) {
  try {
    const v = localStorage.getItem(_atelCatStorageKey(type, serie));
    if (v === '1') return true;
    if (v === '0') return false;
  } catch (e) { /* localStorage indisponible : on retombe sur défaut */ }
  return !!parDefaut;
}

function atelCatBasculer(type, serie, headerEl) {
  const cat = headerEl.parentElement;
  cat.classList.toggle('collapsed');
  const replie = cat.classList.contains('collapsed');
  try {
    localStorage.setItem(_atelCatStorageKey(type, serie), replie ? '1' : '0');
  } catch (e) { /* silencieux */ }
}

// Construit le HTML d'une section repliable .asm-cat. opts.collapsed
// applique la classe `collapsed` initiale (lue par l'appelant depuis
// localStorage). type = "exercice" pour la persistance.
function atelAsmCatHtml(type, serie, label, count, bodyHtml, opts = {}) {
  const closed = opts.collapsed ? ' collapsed' : '';
  const onclick = `atelCatBasculer('${type}','${serie}',this)`;
  return `<div class="asm-cat${closed}" data-serie="${_atelEscAttr(serie)}">`
       + `<div class="asm-cat-head" onclick="${onclick}">`
       + `<span>${_atelEsc(label)}</span>`
       + `<span class="asm-cat-count">${count}</span>`
       + `</div>`
       + `<div class="asm-cat-body">${bodyHtml}</div>`
       + `</div>`;
}

// v0.18.4 — Sections repliables de l'onglet Préférences.
// Le HTML déclare les sections .pref-cat statiquement (avec un data-pref-cat
// = identifiant stable). Ici on gère seulement l'état replié : persistance
// localStorage `seqenseigne.pref.cat.<id>.collapsed` = "1"|"0", et application
// de l'état au chargement de l'onglet. Tout est replié par défaut (D3).
function _prefCatStorageKey(id) {
  return `seqenseigne.pref.cat.${id}.collapsed`;
}

function prefCatEstReplie(id, parDefaut) {
  try {
    const v = localStorage.getItem(_prefCatStorageKey(id));
    if (v === '1') return true;
    if (v === '0') return false;
  } catch (e) { /* localStorage indisponible : on retombe sur le défaut */ }
  return parDefaut === undefined ? true : !!parDefaut;  // défaut : replié
}

function prefCatBasculer(headerEl) {
  const cat = headerEl.parentElement;
  if (!cat) return;
  cat.classList.toggle('collapsed');
  const id = cat.getAttribute('data-pref-cat') || '';
  const replie = cat.classList.contains('collapsed');
  try {
    localStorage.setItem(_prefCatStorageKey(id), replie ? '1' : '0');
  } catch (e) { /* silencieux */ }
}

// Applique l'état replié/déplié mémorisé à toutes les sections .pref-cat.
// Appelée à l'ouverture de l'onglet Préférences. Défaut : tout replié.
function prefCatInitEtats() {
  document.querySelectorAll('.pref-cat[data-pref-cat]').forEach(cat => {
    const id = cat.getAttribute('data-pref-cat');
    if (prefCatEstReplie(id, true)) {
      cat.classList.add('collapsed');
    } else {
      cat.classList.remove('collapsed');
    }
  });
}


// la logique de l'ancien atelObjLiesBadgesHtml :
//   - Si l'obj est dans la séq courante : juste le code (ex. "02")
//   - Sinon : format complet "N10·S04·02"
//   - Tronque à 3 entrées + suffixe "+N" si dépassement
function atelObjLiesEnTags(obj_lies, _nivAtome, _seqAtome) {
  const liens = obj_lies || [];
  if (liens.length === 0) return [];
  const nivCourant = window.ATL_FILTRE_NIVEAU || '';
  const seqCourante = window.ATL_FILTRE_SEQ || '';
  const tags = liens.slice(0, 3).map(l => {
    const parts = l.split('·');
    const niv = parts[0], seq = parts[1], code = parts[2] || '';
    const local = (niv === nivCourant && seq === seqCourante);
    return local ? code : l;
  });
  const reste = liens.length - 3;
  if (reste > 0) tags.push(`+${reste}`);
  return tags;
}

function atelRenderTous() {
  if (typeof atelRenderListe        === 'function') atelRenderListe();
  if (typeof atelRenderNotionListe  === 'function') atelRenderNotionListe();
  if (typeof atelRenderMethodeListe === 'function') atelRenderMethodeListe();
}

// ── Table d'initialisation par atelier ─────────────────────────────────────
//
// Mapping panel → nom de la fonction d'init globale.
// Permet d'avoir un seul point d'invocation, utilisé à la fois par
// atelSwitch (à l'ouverture d'un atelier) et par
// atelAppliquerSelectionsPortee (sur changement de filtre de portée),
// pour que l'atelier visible se rafraîchisse automatiquement.
//
// Les ateliers exercice/notion/methode passent par atelRenderTous() côté
// portée séquence — pas de fonction d'init dédiée.
//
// Toutes les fonctions d'init listées ici doivent lire ATL_FILTRE_NIVEAU
// et ATL_FILTRE_SEQ (portées sequence/niveau) ou ATL_SELECTIONS.cycle.cycle
// (portée cycle), au lieu de maintenir leur propre état de filtre. C'est
// la convention « moule commun » introduite en v0.10 lors de la refonte
// du livret.
const ATL_INITS = {
  livret:            'initLivret',
  theme:             'atelThemeInit',
  seqcycle:          'atelSeqCycleInit',
  rdl:               'compilBatchInit',
  recherche:         'rechercheInit',       // v0.18.1
  // v0.15.1 — recapcours/recapexos/plantravail supprimés
  // (remplacés par Référentiel > Documents à publier)
  evaluation:        'atelEvalInit',        // v0.13.5.2.4
  referentiel:       'atelRefInit',         // v0.13.5.1
  referentiel_externe: 'rxtInit',           // v0.25.0
  fiche:             'atelFicheInit',  // v0.10.5
  carte_automatisme: 'atelCarteCharger',    // v0.13.6.1
  // v0.13.6.17 — notion/methode/exercice ont besoin de se recharger à
  // la bascule pour refléter le filtre niveau/sequence courant (depuis
  // que le hook atelier_filtres_hook ne recharge plus tous les ateliers
  // OO à chaque changement de filtre, mais seulement l'actif).
  // Avant : la liste pouvait être obsolète si l'utilisateur changeait
  // de séquence sur exercice puis basculait sur notion.
  notion:            'atelChargerNotions',
  methode:           'atelChargerMethodes',
  exercice:          'atelChargerExercices',
};

// Invoque l'init d'un atelier si elle est définie. No-op silencieux sinon
// (placeholders, ateliers sans init, fonction non encore déclarée…).
function atelInvoquerInit(panel) {
  const nom = ATL_INITS[panel];
  if (!nom) return;
  const fn = window[nom];
  if (typeof fn === 'function') fn();
}

// Renvoie le panel actuellement visible (display !== 'none'), ou null.
// Utilisé pour cibler l'atelier à rafraîchir lors d'un changement de
// filtre de portée — on ne touche pas aux autres pour ne pas écraser
// leur état (ex. PDF généré, formulaire en cours de saisie).
function atelTrouverPanelVisible() {
  for (const p of ATL_TOUS_ATELIERS) {
    const elPanel = document.getElementById('atl-' + p);
    if (elPanel && elPanel.style.display !== 'none') return p;
  }
  return null;
}

// ── Bascule d'atelier (à l'intérieur d'une portée) ────────────────────────

function atelSwitch(panel) {
  // v0.10.6 — Garde de sortie : si un atelier atomique a des modifs
  // non sauvées, demander à l'utilisateur avant de basculer.
  // Le test panneau-courant != panneau-cible évite de spammer la
  // modale quand l'appel arrive sans changement réel (ex. clic sur
  // l'onglet déjà actif).
  if (typeof atelGardeAvantTransition === 'function') {
    return atelGardeAvantTransition(() => _atelSwitchReel(panel));
  }
  return _atelSwitchReel(panel);
}

function _atelSwitchReel(panel) {
  // v0.10 : si l'atelier demandé n'appartient pas à la portée active,
  // basculer vers sa portée (cas d'ouverture directe d'un atome via lien).
  let porteeCible = null;
  for (const [p, def] of Object.entries(ATL_PORTEES)) {
    if (def.ateliers.includes(panel)) { porteeCible = p; break; }
  }
  if (porteeCible && porteeCible !== ATL_PORTEE_ACTIVE) {
    // atelPorteeSwitch va appeler atelSwitch sur le 1er atelier de la
    // portée — pas ce qu'on veut. On change l'état sans rappeler atelSwitch.
    ATL_PORTEE_ACTIVE = porteeCible;
    localStorage.setItem('atl-portee-active', porteeCible);
    Object.keys(ATL_PORTEES).forEach(p => {
      const btn = document.getElementById('atl-btn-portee-' + p);
      if (btn) btn.classList.toggle('active', p === porteeCible);
      document.querySelectorAll('.atl-grp-' + p).forEach(b => {
        b.style.display = p === porteeCible ? '' : 'none';
      });
    });
    atelRenderSelecteursPortee();
    atelAppliquerSelectionsPortee();
  }

  // Bascule l'affichage et l'état actif des panneaux et boutons.
  ATL_TOUS_ATELIERS.forEach(p => {
    const elPanel = document.getElementById('atl-' + p);
    const elBtn   = document.getElementById('atl-btn-' + p);
    if (elPanel) elPanel.style.display = (p === panel) ? '' : 'none';
    if (elBtn)   elBtn.classList.toggle('active', p === panel);
  });

  // v0.13.6.17 — Expose le panneau actif pour les hooks externes
  // (notamment atelier_filtres_hook.js qui ne rechargera plus tous les
  // ateliers OO à chaque changement de filtre, seulement celui-ci).
  window.ATL_PANEL_ACTIF = panel;

  // Initialisations spécifiques à certains ateliers
  // (table ATL_INITS ; les ateliers sans entrée sont silencieusement
  // ignorés).
  atelInvoquerInit(panel);
}

// ── Objectifs (fonction retirée v0.14.6.b.1) ─────────────────────────────────
// atelChargerObjectifs() peuplait l'ancien sélecteur DOM
// `#atl-exercice-obj-sel` (supprimé de l'atelier exercice à v0.10) via
// l'endpoint legacy `/api/objectifs` (retiré côté backend). Le sélecteur
// d'objectif actuel passe par `/api/objectifs-v2/...` côté
// atelier_seqniv_assemblage.js, indépendamment de cette fonction.


function atelRenderListe() {
  let liste = atelFiltrerAtomes(ATL_EXO);
  // v0.13.4 — Plus de filtre série en barre (remplacé par sections
  // repliables F/A/E/EA/Autres). ATL_FILT subsiste comme code mort,
  // à nettoyer en v0.14 avec le reste de la dette.
  // v0.10.4 — Filtre par état d'édition
  if (typeof window.atelAtomeFiltreEtat_OK === 'function') {
    liste = liste.filter(e => window.atelAtomeFiltreEtat_OK('exercice', e));
  }
  const container = document.getElementById('atl-exercice-list');
  if (!liste.length) {
    container.innerHTML = '<div style="padding:14px;font-size:12px;color:var(--text-muted);text-align:center">Aucun exercice</div>';
    return;
  }

  // ── v0.13.4 — Bucketing par série en sections repliables ────────────────
  // Ordre fixe : F → A → E → EA → Autres. La section "Autres" capte tout
  // ce qui ne tombe pas dans les 4 séries standard (sécurité face aux
  // données legacy ou aux bugs de migration).
  const buckets = { F: [], A: [], E: [], EA: [], Autres: [] };
  const labels  = {
    F: 'Fondamentaux', A: 'Avancés', E: 'Exploration',
    EA: 'Approche (EA)', Autres: 'Autres',
  };
  // Mapping nom-long de série → code court. ex.serie est en nom long
  // ("fondamental", "avancé", "exploration", "approche").
  const serieEnCode = {
    'fondamental': 'F', 'avancé': 'A', 'exploration': 'E', 'approche': 'EA',
  };

  for (const ex of liste) {
    const code = ex.serie_code || serieEnCode[ex.serie] || '';
    const bucket = buckets[code] ? code : 'Autres';
    buckets[bucket].push(ex);
  }

  // Helper interne : rendu d'un item d'exo dans un bucket donné.
  const _renduExo = (ex, badgeCode) => {
    const actif = ATL_EXERCICE_ACTIF && ATL_EXERCICE_ACTIF.id === ex.id;
    // Identifiant compact N11/S04/F01 (niveau/séquence/série+num).
    const idExo = [
      ex.niveau || '',
      ex.sequence || '',
      (ex.serie_code || '') + (ex.num != null ? String(ex.num).padStart(2,'0') : ''),
    ].filter(Boolean).join('/');
    const titre = ex.titre ? ex.titre : { html: '(sans titre)', derive: true };
    // Badge série coloré, format identique au modèle d'assemblage.
    const badgeCls = badgeCode === 'Autres' ? 'M' : badgeCode;
    const badge = `<span class="asm-item-badge asm-item-badge--${_atelEscAttr(badgeCls)}">`
                + `${_atelEsc(badgeCode === 'Autres' ? '?' : badgeCode)}</span>`;
    const placedTags = atelObjLiesEnTags(ex.obj_lies, ex.niveau, ex.sequence);
    const etatCode = ex.etat_code || 'en_cours';
    return atelAsmItemHtml({
      actif, onclick: `atelExerciceCharger('${_atelEscAttr(ex.id)}')`,
      badge, id: idExo, titre, placedTags, etatCode,
    });
  };

  // Construction des sections (uniquement celles non vides, sauf
  // ordre fixe pour les 4 standards, "Autres" affichée seulement si
  // contient au moins 1 exo).
  const ordre = ['F', 'A', 'E', 'EA', 'Autres'];
  const sections = [];
  for (const code of ordre) {
    const exos = buckets[code];
    if (code === 'Autres' && exos.length === 0) continue;
    const items = exos.length > 0
      ? exos.map(ex => _renduExo(ex, code)).join('')
      : '<div style="padding:6px 4px;font-size:11px;color:var(--text-muted)">— aucun —</div>';
    // Par défaut, sections F/A ouvertes (les plus utilisées), E/EA/Autres
    // fermées. localStorage prime sur ce défaut s'il existe.
    const defautReplie = (code === 'E' || code === 'EA' || code === 'Autres');
    const collapsed = atelCatEstReplie('exercice', code, defautReplie);
    sections.push(atelAsmCatHtml('exercice', code, labels[code],
                                 exos.length, items, { collapsed }));
  }
  container.innerHTML = sections.join('');
}

// v0.10.7 — Helper de rendu des badges "objectifs liés" pour la
// sidebar des ateliers Exercice / Notion / Méthode. Affiche jusqu'à 3
// chips sur une 2e ligne en dessous du titre, plus un suffixe `+N` si
// la liste dépasse 3.
//
// (Note v0.12.2 : Fiche n'utilise PAS ce helper. La cardinalité fiche↔
// objectif est 1-1 et le code de l'objectif lié est affiché à droite
// du titre via .atl-item-obj-code, pas en chip de 2e ligne.)
//
// Format des chips :
//   - Si l'obj est dans la séquence courante (niveau/sequence du
//     filtre actif) : juste le code (ex. "02"), chip neutre.
//   - Sinon : format complet "N10·S04·02", chip plus pâle (cas exo
//     en révision dans une autre séquence/niveau).
//
// `nivAtome` / `seqAtome` (paramètres optionnels) permettent de
// préfixer en mode compact pour les notions/méthodes (qui sont
// scope-restreintes — donc tous leurs liens sont dans leur séquence
// d'origine).
function atelObjLiesBadgesHtml(obj_lies, nivAtome, seqAtome) {
  const liens = obj_lies || [];
  if (liens.length === 0) return '';
  const nivCourant = window.ATL_FILTRE_NIVEAU || '';
  const seqCourante = window.ATL_FILTRE_SEQ || '';
  const chips = liens.slice(0, 3).map(l => {
    // l = "N10·S04·02"
    const parts = l.split('·');
    const niv = parts[0], seq = parts[1], code = parts[2] || '';
    const local = (niv === nivCourant && seq === seqCourante);
    const cls = 'atl-item-objchip' + (local ? '' : ' atl-item-objchip--ext');
    const txt = local ? code : l;
    return `<span class="${cls}" title="lié à l'objectif ${l}">${txt}</span>`;
  });
  const reste = liens.length - 3;
  if (reste > 0) chips.push(`<span class="atl-item-objchip-more">+${reste}</span>`);
  return `<div class="atl-item-objs">${chips.join('')}</div>`;
}

function atelExerciceFiltrer(btn, filt) {
  document.querySelectorAll('.exo-filt').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  ATL_FILT = filt;
  atelRenderListe();
}

// ── Atelier Exercice : logique portée par la classe AtelierExercice ───────────
// v0.18.0.3 — Tout le code procédural historique de l'atelier Exercice a été
// retiré d'app.js. La logique (création, chargement, sauvegarde, suppression,
// remplissage du formulaire, séries, remédiation, toggles, onglets, rendu
// LaTeX, validation) vit désormais dans la classe AtelierExercice
// (static/atelier_exercice.js), qui expose des ponts de rétrocompat
// window.atelExercice* / window.atelChargerExercices délégant à
// ATELIER_EXERCICE.* — c'est ce que le HTML et les tables de dispatch appellent.
// Seules subsistent ici les fonctions encore propres à app.js :
// atelExerciceFiltrer (ci-dessus) et les helpers partagés atelFiltrerAtomes /
// atelObjLiesEnTags / atelObjLiesBadgesHtml.

// ── Toast ─────────────────────────────────────────────────────────────────────
function atelToast(msg, err=false) {
  let t = document.getElementById('atl-toast');
  if (!t) {
    t = document.createElement('div');
    t.id = 'atl-toast';
    t.style.cssText = 'position:fixed;bottom:24px;right:24px;padding:9px 16px;border-radius:6px;font-size:13px;font-weight:500;color:#fff;opacity:0;transition:opacity .2s;z-index:999;pointer-events:none';
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.style.background = err ? '#991b1b' : '#1d5fa8';
  t.style.opacity = '1';
  setTimeout(()=>{ t.style.opacity='0'; }, 2500);
}


// ── Atelier Notion + Atelier Méthode (v0.13.7.0c) ────────────────────────────
//
// Tout le code des ateliers Notion et Méthode a été retiré ici. La logique
// vit désormais entièrement dans :
//   - static/atelier.js (Atelier — base)
//   - static/atelier_editeur.js (AtelierEditeur — gestion modif/enregistré)
//   - static/atelier_atomique.js (AtelierAtomique — atomes avec rendu PDF)
//   - static/atelier_notion.js (AtelierNotion — singleton ATELIER_NOTION)
//   - static/atelier_methode.js (AtelierMethode — singleton ATELIER_METHODE)
//
// Cas-coin de compat : les variables globales ATL_NOTIONS, ATL_NOTION_ACTIF,
// ATL_METHODES, ATL_METHODE_ACTIF sont maintenues par les setters miroirs
// dans atelier_notion.js et atelier_methode.js (rendu_atome.js et
// atelier_etat_edition.js les lisent encore).

// ── Atelier Séquence (niveau) ─────────────────────────────────────────────────
// Nettoyage post-R4e4b : toute la machinerie Legacy (panneau #liv-atl-content,
// LIV_DATA / LIV_NOTIONS_ORDRE / LIV_METHODES_ORDRE, édition des notions et
// méthodes dans la vue Legacy, bouton « Enregistrer dans le YAML », bouton
// « Générer le .tex ») a été supprimée.
//
// Refonte v0.10 : suppression des sélecteurs niveau/séquence internes
// (#liv-atl-niveau, #liv-atl-seq) et des variables LIV_NIVEAU / LIV_SEQ.
// L'atelier s'aligne désormais sur le moule commun : il lit
// ATL_FILTRE_NIVEAU / ATL_FILTRE_SEQ et `initLivret()` est appelée par
// atelInvoquerInit() à chaque changement de portée séquence.
//
// Refonte v0.12.3.1 : suppression du toggle Assemblage / Édition avancée et
// du fichier ateliers_seqniv_v2_edit.js (l'éditeur formulaire historique).
// Toutes les fonctions essentielles (déplacement d'objectifs, fin-de-cycle)
// ont été portées dans l'atelier d'assemblage en v0.12.3.0. La toolbar
// affiche désormais un titre statique « Atelier Séquence (niveau) » au lieu
// du rappel `${niveau} ${séquence}` (l'info est déjà dans les filtres de
// portée — éviter la redondance).

async function initLivret() {
  // Titre statique : la portée niveau/séquence est déjà rappelée par les
  // filtres globaux, inutile de la dupliquer ici.
  const titre = document.getElementById('liv-atl-toolbar-title');
  if (titre) titre.textContent = 'Atelier Séquence (niveau)';

  // Si pas de séquence sélectionnée, vider les conteneurs internes.
  // v0.12.1.1 — Important : on vide UNIQUEMENT les sous-conteneurs
  // (#asm-tab-edition pour le panneau d'édition de l'assemblage), PAS le
  // wrapper #liv-atl-content-assemblage. Ce wrapper contient la structure
  // statique des onglets `#asm-tabs` (boutons Édition / Rendu PDF) et les
  // deux panneaux `#asm-tab-edition` / `#asm-tab-rendu` qui sont posés
  // dans le HTML et exploités par atelier_seqniv_assemblage.js. Un
  // `innerHTML = ''` sur le wrapper détruit irrémédiablement cette
  // structure ; les rafraîchissements ultérieurs ne trouveraient plus
  // leurs cibles.
  if (!ATL_FILTRE_NIVEAU || !ATL_FILTRE_SEQ) {
    const cEd = document.getElementById('asm-tab-edition');
    if (cEd) cEd.innerHTML = '';
    const sb = document.getElementById('liv-atl-sidebar-body');
    if (sb) sb.innerHTML = '';
    const cRd = document.getElementById('asm-tab-rendu');
    if (cRd) {
      cRd.innerHTML = '';
      cRd.dataset.initialise = '';  // Forcer la régénération paresseuse
    }
    return;
  }
  // Sécurité : s'assurer que les filtres sont visibles depuis les IIFE
  // (les `let` au top-level d'un script ne sont pas auto-exposés sur
  // `window`, contrairement aux `var`).
  if (typeof atelExposerFiltres === 'function') atelExposerFiltres();
  // Rafraîchir l'atelier d'assemblage (seul mode désormais).
  if (typeof window.seqnivAssemblageRafraichir === 'function') {
    window.seqnivAssemblageRafraichir();
  }
}


// ── Administration — Import .tex ──────────────────────────────────────────────

let ADMIN_DATA   = null;
let ADMIN_ATOMES = [];
let ADMIN_FILTRE = 'tous';

function adminSousOnglet(nom) {
  // Convention de nommage : admin-<sousSection>[-<élément>][-<modifier>].
  // Les sous-onglets Admin sont identifiés par leur panneau `admin-<nom>`
  // et leur bouton d'onglet `admin-<nom>-btn`.
  // v0.9 — 'compilation' a été déplacé vers Ateliers > Rendu par lot.
  // v0.10.5.2 — ajout de 'importfiches'.
  ['importref', 'importpaquet', 'images', 'importfiches', 'bdd',
   'importsuivi'].forEach(s => {
    const el = document.getElementById('admin-' + s);
    if (el) el.style.display = s === nom ? '' : 'none';
    const btn = document.getElementById('admin-' + s + '-btn');
    if (btn) btn.classList.toggle('active', s === nom);
  });
  if (nom === 'bdd') adminBddStatut();
  // v0.9 — pré-remplissage des chemins Admin depuis Préférences
  if (nom === 'importref'    && typeof adminPreremplirChemins === 'function') adminPreremplirChemins('importref');
  if (nom === 'importpaquet' && typeof adminPreremplirChemins === 'function') adminPreremplirChemins('importpaquet');
  if (nom === 'images'       && typeof adminPreremplirChemins === 'function') adminPreremplirChemins('images');
  // v0.10.5.2 — initialisation du nouveau sous-onglet
  if (nom === 'importfiches' && typeof adminImportFichesInit === 'function') adminImportFichesInit();
}

// v0.6.4 — Import de la mise en forme LaTeX (paquet seqenseigne en BDD)
async function adminPaquetImport() {
  const chemin = document.getElementById('admin-importpaquet-chemin').value.trim();
  if (!chemin) { alert('Indiquer le chemin du dossier paquet.'); return; }
  const btn    = document.getElementById('admin-paquet-btn-import');
  const status = document.getElementById('admin-paquet-status');
  const log    = document.getElementById('admin-paquet-log');
  btn.disabled = true;
  status.textContent = 'Import en cours…';
  log.style.display = 'none';
  try {
    const r = await fetch('/api/admin/paquet/import', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({chemin}),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
    status.innerHTML = `<span style="color:var(--success)">✓ Import réussi.</span> ${d.macros||0} macros, ${d.environnements||0} environnements, ${d.requirepackage||0} RequirePackage chargés.`;
    if (d.log) {
      log.textContent = d.log;
      log.style.display = '';
    }
  } catch (e) {
    status.innerHTML = `<span style="color:var(--danger)">Erreur : ${_escHtml(e.message)}</span>`;
  } finally {
    btn.disabled = false;
  }
}

// v0.7 — Migration des images vers data/images/
//
// 2 boutons : « Aperçu » lance un dry-run (sans toucher au disque), et
// déverrouille « Exécuter » qui lance la vraie migration. Les compteurs et
// le log sont rafraîchis après chaque appel.
async function adminImagesPreview() {
  return _adminImagesAppel(true);
}

async function adminImagesApply() {
  // Confirmation explicite : la migration ré-écrit les .tex sources.
  if (!confirm(
    "La migration va copier les images dans data/images/, convertir " +
    "les .jpg en .png, et MODIFIER les .tex sources de la référence " +
    "pour mettre à jour leurs \\includegraphics. Continuer ?"
  )) return;
  return _adminImagesAppel(false);
}

async function _adminImagesAppel(dryRun) {
  const chemin = document.getElementById('admin-images-chemin').value.trim();
  if (!chemin) { alert('Indiquer le chemin de l\'arborescence de référence.'); return; }

  const btnP   = document.getElementById('admin-images-btn-preview');
  const btnA   = document.getElementById('admin-images-btn-apply');
  const status = document.getElementById('admin-images-status');
  const log    = document.getElementById('admin-images-log');
  const compt  = document.getElementById('admin-images-compteurs');
  const blocC  = document.getElementById('admin-images-conflits-bloc');
  const listC  = document.getElementById('admin-images-conflits-list');

  btnP.disabled = true;
  btnA.disabled = true;
  status.textContent = dryRun ? 'Aperçu en cours…' : 'Migration en cours…';
  log.style.display = 'none';

  try {
    const url = dryRun ? '/api/admin/images/preview' : '/api/admin/images/apply';
    const r = await fetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({chemin_reference: chemin}),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);

    // Rendu des compteurs (4 colonnes).
    compt.style.display = 'grid';
    compt.innerHTML = `
      <div class="card" style="padding:8px"><div style="color:var(--text-secondary)">Copiées</div><div style="font-size:18px;font-weight:600">${d.images_copiees}</div></div>
      <div class="card" style="padding:8px"><div style="color:var(--text-secondary)">Converties (jpg→png)</div><div style="font-size:18px;font-weight:600">${d.images_converties}</div></div>
      <div class="card" style="padding:8px"><div style="color:var(--text-secondary)">Sautées (idempotence)</div><div style="font-size:18px;font-weight:600">${d.images_skip}</div></div>
      <div class="card" style="padding:8px"><div style="color:var(--text-secondary)">Conflits</div><div style="font-size:18px;font-weight:600;color:${d.conflits>0?'var(--warning,#b58900)':'inherit'}">${d.conflits}</div></div>
      <div class="card" style="padding:8px"><div style="color:var(--text-secondary)">.tex modifiés</div><div style="font-size:18px;font-weight:600">${d.tex_modifies}</div></div>
      <div class="card" style="padding:8px"><div style="color:var(--text-secondary)">\\includegraphics réécrits</div><div style="font-size:18px;font-weight:600">${d.reecritures}</div></div>
      <div class="card" style="padding:8px"><div style="color:var(--text-secondary)">Introuvables</div><div style="font-size:18px;font-weight:600;color:${d.introuvables>0?'var(--danger)':'inherit'}">${d.introuvables}</div></div>
      <div class="card" style="padding:8px"><div style="color:var(--text-secondary)">Orphelines</div><div style="font-size:18px;font-weight:600;color:${d.orphelines>0?'var(--text-secondary)':'inherit'}">${d.orphelines}</div></div>
    `;

    // Conflits : extraction des lignes "Liste des conflits à arbitrer" du log.
    if (d.conflits > 0 && d.log) {
      const lignes = d.log.split('\n');
      const debut = lignes.findIndex(l => l.startsWith('Liste des conflits'));
      if (debut >= 0) {
        const conflits = [];
        for (let i = debut + 1; i < lignes.length; i++) {
          if (lignes[i].startsWith('  - ')) {
            conflits.push(lignes[i].slice(4));
          } else if (lignes[i].trim() === '' || lignes[i].startsWith('---')) {
            break;
          }
        }
        listC.innerHTML = conflits.map(c => `<div>• ${_escHtml(c)}</div>`).join('');
        blocC.style.display = '';
      }
    } else {
      blocC.style.display = 'none';
    }

    // Log complet.
    if (d.log) {
      log.textContent = d.log;
      log.style.display = '';
    }

    // Statut de fin.
    const verbe = dryRun ? 'Aperçu' : 'Migration';
    if (d.introuvables > 0 || d.conflits > 0) {
      status.innerHTML = `<span style="color:var(--warning,#b58900)">${verbe} terminé(e) avec avertissements (voir détail).</span>`;
    } else {
      status.innerHTML = `<span style="color:var(--success)">✓ ${verbe} terminé(e).</span>`;
    }

    // Après un aperçu réussi, on déverrouille le bouton d'exécution.
    if (dryRun) {
      btnA.disabled = false;
    }
  } catch (e) {
    status.innerHTML = `<span style="color:var(--danger)">Erreur : ${_escHtml(e.message)}</span>`;
  } finally {
    btnP.disabled = false;
    // btnA reste disabled tant qu'un aperçu n'a pas réussi.
  }
}

async function adminScanner() {
  const chemin    = document.getElementById('admin-chemin').value.trim();
  const niveauSel = document.getElementById('admin-niveau').value;
  if (!chemin) { alert('Indiquer le chemin du dossier séquences.'); return; }

  const btn    = document.getElementById('admin-btn-scan');
  const status = document.getElementById('admin-scan-status');
  btn.disabled = true;
  status.textContent = 'Scan en cours…';
  document.getElementById('admin-resume').style.display = 'none';

  const niveaux = niveauSel === 'tous' ? ['N10','N11','N12'] : [niveauSel];

  try {
    // Aperçu (compteurs rapides)
    const aperçus = await Promise.all(niveaux.map(niv =>
      api(`/api/scanner/apercu?chemin=${encodeURIComponent(chemin)}&niveau=${niv}`)
    ));

    ADMIN_DATA = { niveaux: {}, erreurs: [] };
    for (let i = 0; i < niveaux.length; i++) {
      ADMIN_DATA.niveaux[niveaux[i]] = aperçus[i];
      ADMIN_DATA.erreurs.push(...(aperçus[i].erreurs || []));
    }

    // Détail avec statuts nouveau/existant
    const details = await Promise.all(niveaux.map(niv =>
      api(`/api/scanner/detail?chemin=${encodeURIComponent(chemin)}&niveau=${niv}`)
    ));

    ADMIN_ATOMES = [];
    for (let i = 0; i < niveaux.length; i++) {
      const d   = details[i];
      const niv = niveaux[i];
      for (const n of (d.notions   || [])) ADMIN_ATOMES.push({...n, _type:'notion',   _niveau:niv});
      for (const m of (d.methodes  || [])) ADMIN_ATOMES.push({...m, _type:'methode',  _niveau:niv});
      for (const e of (d.exercices || [])) ADMIN_ATOMES.push({...e, _type:'exercice', _niveau:niv});
      for (const l of (d.livrets   || [])) ADMIN_ATOMES.push({...l, _type:'livret',   _niveau:niv});
      ADMIN_DATA.erreurs.push(...(d.erreurs || []));
    }

    adminAfficherResume();
    status.textContent = '';
  } catch(e) {
    status.textContent = 'Erreur : ' + e.message;
  }
  btn.disabled = false;
}

function adminAfficherResume() {
  document.getElementById('admin-resume').style.display = '';

  // Compteurs par type
  const types  = ['notion','methode','exercice','livret'];
  const labels = {notion:'Notions', methode:'Méthodes', exercice:'Exercices', livret:'Livrets'};
  document.getElementById('admin-compteurs').innerHTML = types.map(t => {
    const tous = ADMIN_ATOMES.filter(a => a._type === t);
    const nv   = tous.filter(a => a._statut === 'nouveau').length;
    const ex   = tous.filter(a => a._statut === 'existant').length;
    return `<div style="background:var(--surface);border:1px solid var(--border);
        border-radius:var(--radius);padding:12px 14px">
      <div style="font-size:11px;font-weight:500;color:var(--text-secondary);
          text-transform:uppercase;letter-spacing:.04em;margin-bottom:6px">${labels[t]}</div>
      <div style="font-size:22px;font-weight:500">${tous.length}</div>
      <div style="font-size:11px;margin-top:4px">
        <span style="color:#0f6e56">${nv} nouveaux</span>
        · <span style="color:#854f0b">${ex} existants</span>
      </div>
    </div>`;
  }).join('');

  // Erreurs
  const errs = ADMIN_DATA.erreurs || [];
  const errBloc = document.getElementById('admin-erreurs-bloc');
  if (errs.length) {
    errBloc.style.display = '';
    document.getElementById('admin-erreurs-list').innerHTML =
      errs.map(e => `<div>• ${e}</div>`).join('');
  } else {
    errBloc.style.display = 'none';
  }

  adminRenderAtomes();

  const nbNouveaux = ADMIN_ATOMES.filter(a => a._statut === 'nouveau').length;
  const btnImport  = document.getElementById('admin-btn-import');
  btnImport.textContent = `Importer ${nbNouveaux} nouveaux atomes`;
  btnImport.disabled    = nbNouveaux === 0;
}

function adminFiltrer(btn, filtre) {
  document.querySelectorAll('#admin-filtres .exo-filt').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  ADMIN_FILTRE = filtre;
  adminRenderAtomes();
}

function adminRenderAtomes() {
  let liste = ADMIN_ATOMES;
  if (['notion','methode','exercice','livret'].includes(ADMIN_FILTRE)) {
    liste = liste.filter(a => a._type === ADMIN_FILTRE);
  } else if (ADMIN_FILTRE === 'nouveau') {
    liste = liste.filter(a => a._statut === 'nouveau');
  } else if (ADMIN_FILTRE === 'existant') {
    liste = liste.filter(a => a._statut === 'existant');
  }

  const typeLabel = {notion:'Notion', methode:'Méthode', exercice:'Exercice', livret:'Livret'};
  const c = document.getElementById('admin-atomes-list');

  if (!liste.length) {
    c.innerHTML = '<div style="padding:14px;font-size:12px;color:var(--text-muted);text-align:center">Aucun élément</div>';
    return;
  }

  c.innerHTML = liste.map(a => {
    const statut = a._statut === 'nouveau'
      ? '<span class="badge-import nouveau">Nouveau</span>'
      : '<span class="badge-import existant">Déjà en base</span>';
    const titre = a.titre || a.nom || a.fichier || '(sans titre)';
    const info  = a._type === 'exercice'
      ? `${a._niveau} ${a.sequence} — ${a.serie} n°${a.num}`
      : `${a._niveau} ${a.sequence || ''}`;
    return `<div class="admin-atom-row">
      ${statut}
      <span class="admin-atom-type">${typeLabel[a._type]}</span>
      <span class="admin-atom-fichier">${a.fichier || ''}</span>
      <span class="admin-atom-titre" title="${titre}">${titre}</span>
      <span style="font-size:11px;color:var(--text-muted);flex-shrink:0">${info}</span>
    </div>`;
  }).join('');
}

async function adminImporter() {
  const chemin    = document.getElementById('admin-chemin').value.trim();
  const niveauSel = document.getElementById('admin-niveau').value;
  const niveaux   = niveauSel === 'tous' ? ['N10','N11','N12'] : [niveauSel];
  const nbNv      = ADMIN_ATOMES.filter(a => a._statut === 'nouveau').length;

  if (!confirm(`Importer ${nbNv} nouveaux atomes dans la base de données ?`)) return;

  const btn    = document.getElementById('admin-btn-import');
  const status = document.getElementById('admin-import-status');
  btn.disabled = true;
  status.textContent = 'Import en cours…';

  try {
    // ⚠ Scans séquentiels (pas Promise.all) : chaque appel manipule
    // `exercices`, `objectifs`, `objectif_exos`… en écriture. Des scans
    // concurrents entraînaient des IntegrityError FK — voir l'incident
    // du 23 avril 2026 avec les 3 scans lancés en parallèle.
    const resultats = [];
    for (const niv of niveaux) {
      const r = await api('/api/scanner/lancer', {
        method: 'POST',
        body: JSON.stringify({ chemin_sequences: chemin, niveau: niv })
      });
      resultats.push(r);
    }

    let total = 0;
    const incidents = [];
    for (let i = 0; i < resultats.length; i++) {
      const r = resultats[i];
      total += (r.notions?.nouvelles  || 0) + (r.methodes?.nouvelles  || 0)
             + (r.exercices?.nouvelles || 0) + (r.livrets?.nouvelles  || 0);
      // Point 5 : collecter les incidents de macros non résolues
      for (const inc of (r.incidents_macros || [])) {
        incidents.push({ ...inc, niveau: niveaux[i] });
      }
    }
    status.textContent = `✓ ${total} atomes importés.`
      + (incidents.length ? ` · ${incidents.length} libellé(s) à saisir manuellement` : '');
    _afficherRapportIncidents(incidents);
    await adminScanner(); // Relancer pour mettre à jour les statuts
  } catch(e) {
    status.textContent = 'Erreur : ' + e.message;
    btn.disabled = false;
  }
}

// ── Rapport des macros non résolues (point 5) ────────────────────────────────
//
// Affiche sous la zone d'import une carte listant les libellés qu'il va
// falloir saisir manuellement (ou corriger à la source). Groupe par fichier
// pour faciliter la recherche. Si la liste est vide, la carte est masquée.

function _afficherRapportIncidents(incidents) {
  let card = document.getElementById('admin-importref-incidents');
  if (!card) {
    // Insertion dans le DOM après la zone #admin-resume
    const resume = document.getElementById('admin-resume');
    if (!resume || !resume.parentNode) return;
    card = document.createElement('div');
    card.id = 'admin-importref-incidents';
    card.className = 'card';
    card.style.cssText = 'margin-top:14px;border-color:#fbbf24';
    resume.parentNode.insertBefore(card, resume.nextSibling);
  }
  if (!incidents.length) {
    card.style.display = 'none';
    card.innerHTML = '';
    return;
  }
  // Groupement par fichier
  const parFichier = {};
  for (const inc of incidents) {
    (parFichier[inc.fichier] ||= []).push(inc);
  }
  const noms = Object.keys(parFichier).sort();
  const lignes = noms.map(nom => {
    const lst = parFichier[nom].map(inc => `
      <li style="padding:2px 0">
        <code style="font-size:11px">${_escHtml(inc.macro)}</code>
        <span style="color:var(--text-muted)"> dans <em>${_escHtml(inc.champ)}</em>
          — ${_escHtml(inc.raison)}</span>
      </li>`).join('');
    return `<div style="margin-bottom:10px">
      <div style="font-size:12px;font-weight:500;font-family:monospace">${_escHtml(nom)}</div>
      <ul style="margin:4px 0 0 16px;padding:0;list-style:disc;font-size:12px">${lst}</ul>
    </div>`;
  }).join('');

  card.style.display = '';
  card.innerHTML = `
    <div style="font-size:13px;font-weight:500;margin-bottom:8px;color:#b45309">
      ⚠ ${incidents.length} libellé(s) à saisir manuellement
    </div>
    <p style="font-size:12px;color:var(--text-secondary);margin-bottom:10px">
      Ces macros LaTeX nommantes n'ont pas pu être résolues au moment de l'import.
      Les champs correspondants contiennent désormais <code>[à saisir]</code>
      (ouvrir l'atome dans son atelier pour y mettre le bon libellé).
    </p>
    ${lignes}
  `;
}

function _escHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}


// ── Administration — Base de données ─────────────────────────────────────────

let ADMIN_RESET_CIBLE = null;

async function adminBddStatut() {
  // Nettoyage post-R4e4b : le champ "yaml" a disparu du /api/admin/statut.
  // Les YAML ne sont plus qu'un cache dérivé de la BDD, leur état n'a plus
  // de valeur informative dans l'écran Admin.
  const btn = document.getElementById('admin-bdd-btn-statut');
  const zone = document.getElementById('admin-bdd-statut');
  if (btn) btn.disabled = true;
  zone.innerHTML = '<span style="color:var(--text-muted)">Chargement…</span>';
  try {
    const r = await fetch('/api/admin/statut');
    const d = await r.json();

    const ref = d.reference || {};
    const c04  = d.c04 || {};
    const suivi = d.suivi || {};
    const referentiels = d.referentiels || [];

    // Grille référentiel des atomes (notions / méthodes / exercices / livrets)
    const refItems = [
      { label: 'Notions',   val: ref.notions   ?? '—' },
      { label: 'Méthodes',  val: ref.methodes  ?? '—' },
      { label: 'Exercices', val: ref.exercices ?? '—' },
      { label: 'Livrets',   val: ref.livrets   ?? '—' },
    ];
    const refGrid = `
      <div style="font-size:12px;font-weight:500;color:var(--text-secondary);margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em">Référence</div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:14px">
        ${refItems.map(it => `
          <div style="background:var(--surface-light);border-radius:var(--radius-sm);padding:10px 12px;text-align:center">
            <div style="font-size:22px;font-weight:700;color:var(--primary)">${it.val}</div>
            <div style="font-size:11px;color:var(--text-secondary);margin-top:2px">${it.label}</div>
          </div>`).join('')}
      </div>`;

    // v0.6.4 — Grille « Mise en forme » : stats du paquet seqenseigne
    // importé en BDD (macros, environnements, RequirePackage, fichiers .sty).
    // Le détail par type de macro est affiché dans une zone dépliable
    // (<details>). Si la catégorie est vide ou si l'API ne renvoie pas le
    // champ paquet, on cache la zone (cas BDD vierge avant import).
    const paquet = d.paquet || {};
    let paquetGrid = '';
    if (paquet && Object.keys(paquet).length) {
      const items = [
        { label: 'Macros',         val: paquet.macros         ?? 0 },
        { label: 'Environnements', val: paquet.environnements ?? 0 },
        { label: 'RequirePackage', val: paquet.requirepackage ?? 0 },
        { label: 'Fichiers .sty',  val: paquet.fichiers_sty   ?? 0 },
      ];
      const detail = paquet.detail || null;
      const detailHtml = detail
        ? `<details style="margin-top:8px;padding:8px 12px;background:var(--surface-light);border-radius:var(--radius-sm);font-size:12px">
             <summary style="cursor:pointer;color:var(--text-secondary)">Détail par catégorie</summary>
             <div style="margin-top:8px;display:grid;grid-template-columns:1fr 1fr;gap:4px 16px">
               ${Object.entries(detail).map(([k, v]) =>
                 `<div style="display:flex;justify-content:space-between"><span style="color:var(--text-secondary)">${_escHtml(k)}</span><span style="font-weight:500">${v}</span></div>`
               ).join('')}
             </div>
           </details>`
        : '';
      paquetGrid = `
        <div style="font-size:12px;font-weight:500;color:var(--text-secondary);margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em">Mise en forme</div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:6px">
          ${items.map(it => `
            <div style="background:var(--surface-light);border-radius:var(--radius-sm);padding:10px 12px;text-align:center">
              <div style="font-size:22px;font-weight:700;color:var(--primary)">${it.val}</div>
              <div style="font-size:11px;color:var(--text-secondary);margin-top:2px">${it.label}</div>
            </div>`).join('')}
        </div>
        ${detailHtml}
        <div style="height:14px"></div>`;
    }

    // Grille suivi (classes / élèves / progressions / créneaux / niveaux saisis / exos cochés)
    const suiviItems = [
      { label: 'Classes',        val: suivi.classes          ?? 0 },
      { label: 'Élèves',         val: suivi.eleves           ?? 0 },
      { label: 'Progressions',   val: suivi.progressions     ?? 0 },
      { label: 'Créneaux',       val: suivi.creneaux         ?? 0 },
      { label: 'Niveaux saisis', val: suivi.niveaux_saisis   ?? 0 },
      { label: 'Exos cochés',    val: suivi.exercices_coches ?? 0 },
    ];
    const suiviGrid = `
      <div style="font-size:12px;font-weight:500;color:var(--text-secondary);margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em">Suivi</div>
      <div style="display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-bottom:14px">
        ${suiviItems.map(it => `
          <div style="background:var(--surface-light);border-radius:var(--radius-sm);padding:10px 12px;text-align:center">
            <div style="font-size:20px;font-weight:700;color:var(--primary)">${it.val}</div>
            <div style="font-size:11px;color:var(--text-secondary);margin-top:2px">${it.label}</div>
          </div>`).join('')}
      </div>`;

    // Tableau des référentiels versionnés
    let referentielsBloc = '';
    if (referentiels.length) {
      const rows = referentiels.map(r => {
        const lock = r.verrouille
          ? '<span title="Verrouillé" style="color:var(--warning)">🔒</span>'
          : '<span title="Modifiable" style="color:var(--text-muted)">—</span>';
        return `<tr>
          <td style="padding:4px 10px;font-size:12px;font-family:monospace">${r.id}</td>
          <td style="padding:4px 10px;font-size:12px">${r.niveau}</td>
          <td style="padding:4px 10px;font-size:12px;color:var(--text-secondary)">${r.version}</td>
          <td style="padding:4px 10px;text-align:center">${lock}</td>
        </tr>`;
      }).join('');
      referentielsBloc = `
        <div style="margin-bottom:14px">
          <div style="font-size:12px;font-weight:500;color:var(--text-secondary);margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em">Référentiels versionnés (${referentiels.length})</div>
          <table style="width:100%;border-collapse:collapse">
            <thead><tr style="border-bottom:1px solid var(--border)">
              <th style="padding:4px 10px;font-size:10px;font-weight:600;color:var(--text-muted);text-align:left">ID</th>
              <th style="padding:4px 10px;font-size:10px;font-weight:600;color:var(--text-muted);text-align:left">Niveau</th>
              <th style="padding:4px 10px;font-size:10px;font-weight:600;color:var(--text-muted);text-align:left">Version</th>
              <th style="padding:4px 10px;font-size:10px;font-weight:600;color:var(--text-muted);text-align:center">État</th>
            </tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>`;
    }

    const c04Info = `
      <div style="font-size:11px;color:var(--text-secondary)">
        Référentiel C04 : <strong>${c04.sequences ?? 0}</strong> séquences,
        <strong>${c04.themes ?? 0}</strong> thèmes.
        ${c04.sequences === 0
          ? '<span style="color:var(--danger)"> ⚠ C04_sequences.csv introuvable dans data/</span>'
          : ''}
      </div>`;

    zone.innerHTML = refGrid + paquetGrid + suiviGrid + referentielsBloc + c04Info;
  } catch(e) {
    zone.innerHTML = `<span style="color:var(--danger)">Erreur : ${e.message}</span>`;
  } finally {
    if (btn) btn.disabled = false;
  }
}


// v0.10.3 — Auto-import des cycles : diagnostic + relance manuelle.
async function adminCyclesAutoImportStatus() {
  const zone = document.getElementById('admin-cycles-autoimport-resultat');
  if (!zone) return;
  zone.textContent = 'Chargement…';
  try {
    const r = await fetch('/api/admin/cycles/auto-import-status');
    if (!r.ok) {
      zone.innerHTML = `<span style="color:var(--danger)">Erreur HTTP ${r.status}</span>`;
      return;
    }
    const d = await r.json();
    let html = '<strong>État par cycle :</strong>\n';
    for (const c of d.cycles || []) {
      const csvT = c.csv_themes_present ? '✓' : '✗';
      const csvS = c.csv_sequences_present ? '✓' : '✗';
      const bdd  = c.en_bdd ? '✓ en BDD' : '✗ absent de BDD';
      html += `  ${c.code}  CSV thèmes ${csvT}  CSV séquences ${csvS}  ${bdd}\n`;
    }
    if (d.log_excerpt) {
      html += `\n<strong>Log (${d.log_path}) — dernières lignes :</strong>\n${d.log_excerpt}`;
    } else {
      html += `\n<em>Aucun log d'auto-import (le démarrage n'a peut-être pas encore tourné).</em>`;
    }
    zone.innerHTML = html;
  } catch (e) {
    zone.innerHTML = `<span style="color:var(--danger)">Erreur : ${e.message}</span>`;
  }
}

async function adminCyclesAutoImportRelancer() {
  const zone = document.getElementById('admin-cycles-autoimport-resultat');
  if (!zone) return;
  zone.textContent = 'Relance en cours…';
  try {
    const r = await fetch('/api/admin/cycles/auto-import-relancer', {method: 'POST'});
    if (!r.ok) {
      zone.innerHTML = `<span style="color:var(--danger)">Erreur HTTP ${r.status}</span>`;
      return;
    }
    const d = await r.json();
    let html = '<strong>Résultat de la relance :</strong>\n';
    for (const [code, rep] of Object.entries(d.rapport || {})) {
      if (rep.importe) {
        const t = (rep.rapport && rep.rapport.themes && rep.rapport.themes.crees) || 0;
        const s = (rep.rapport && rep.rapport.sequences && rep.rapport.sequences.crees) || 0;
        html += `  ✓ ${code} importé : ${t} thème(s), ${s} séquence(s)\n`;
      } else {
        html += `  · ${code} : ${rep.raison || 'inconnu'}\n`;
      }
    }
    zone.innerHTML = html;
  } catch (e) {
    zone.innerHTML = `<span style="color:var(--danger)">Erreur : ${e.message}</span>`;
  }
}


async function adminExportSqlite() {
  try {
    const r = await fetch('/api/admin/export-sqlite');
    if (!r.ok) { alert('Export impossible'); return; }
    const blob = await r.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'seqenseigne_' + new Date().toISOString().slice(0,10) + '.db';
    a.click();
  } catch(e) { alert('Erreur : ' + e.message); }
}

async function adminImportSqlite() {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.db';
  input.onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (!confirm(`Remplacer toute la base par "${file.name}" ? Cette action est irréversible.`)) return;
    const fd = new FormData();
    fd.append('file', file);
    const r = await fetch('/api/admin/import-sqlite', { method: 'POST', body: fd });
    const d = await r.json();
    if (d.ok) { alert('Base importée avec succès. Rechargement...'); location.reload(); }
    else alert('Erreur : ' + (d.error || 'inconnue'));
  };
  input.click();
}

async function adminBddReset(cible) {
  const messages = {
    reference: 'Vider les données de référence (notions, méthodes, exercices, livrets) ?',
    paquet:    'Vider les paquets, macros et environnements importés depuis les fichiers .sty ?',
    suivi:     'Vider les données de suivi (classes, élèves, suivi, niveaux, versions) ?',
    tout:      'Tout réinitialiser — données de référence ET de suivi ?',
  };
  if (!window.confirm(messages[cible] || 'Confirmer la réinitialisation ?')) return;

  const status = document.getElementById('admin-reset-status');
  if (status) status.innerHTML = '<span style="color:var(--text-muted)">Réinitialisation…</span>';

  try {
    const r = await fetch(`/api/admin/reset/${cible}`, { method: 'POST' });
    const d = await r.json();
    if (d.ok) {
      const nb = (d.vides || []).length;
      if (status) status.innerHTML = `<span style="color:#166534">✓ ${nb} fichier(s) réinitialisé(s).</span>`;
      // Recharger les classes locales si on a vidé le suivi
      if (cible === 'suivi' || cible === 'tout') {
        await loadClasses();
        buildClasseSel();
        renderClassesList();
        currentCid = null;
        showNoClasse();
      }
      adminBddStatut();
    } else {
      if (status) status.innerHTML = `<span style="color:var(--danger)">Erreur serveur.</span>`;
    }
  } catch(e) {
    if (status) status.innerHTML = `<span style="color:var(--danger)">Erreur : ${e.message}</span>`;
  }
}

// Conservées pour compatibilité HTML (boutons dans la carte de confirmation)
function adminBddResetAnnuler() {
  document.getElementById('admin-reset-confirm').style.display = 'none';
}
async function adminBddResetConfirmer() {
  // Plus utilisé — la confirmation passe par window.confirm()
}



// ════════════════════════════════════════════════════════════════
// ADMINISTRATION — IMPORT HISTORIQUE
// ════════════════════════════════════════════════════════════════



async function adminImporterSequencesDB() {
  const niveau = document.getElementById('admin-importsuivi-sdb-niveau').value;
  const chemin = document.getElementById('admin-importsuivi-sdb-chemin').value.trim();
  const etab   = document.getElementById('admin-importsuivi-sdb-etablissement').value.trim();
  const annee  = document.getElementById('admin-importsuivi-sdb-annee').value.trim();
  const status = document.getElementById('admin-importsuivi-sdb-status');

  if (!chemin || !annee) {
    status.textContent = 'Chemin et année requis.';
    status.style.color = 'var(--danger)'; return;
  }

  status.textContent = 'Import en cours…'; status.style.color = 'var(--text-secondary)';
  try {
    const res = await api(`/api/progression/${niveau}/importer-sequencesdb`, {
      method: 'POST',
      body: JSON.stringify({ chemin, annee, etablissement: etab })
    });
    if (res.error) {
      status.textContent = 'Erreur : ' + res.error;
      status.style.color = 'var(--danger)'; return;
    }
    status.textContent = `✓ ${res.creneaux} créneaux importés`;
    status.style.color = 'var(--success)';
    if (res.erreurs?.length) status.textContent += ` (${res.erreurs.length} avert.)`;
  } catch(e) {
    status.textContent = 'Erreur : ' + e.message;
    status.style.color = 'var(--danger)';
  }
}

async function adminImporterHistorique() {
  const chemin_classe      = document.getElementById('admin-importsuivi-hist-chemin-classe').value.trim();
  const chemin_sequencesdb = document.getElementById('admin-importsuivi-hist-chemin-sdb').value.trim();
  const niveau             = document.getElementById('admin-importsuivi-hist-niveau').value;
  const annee              = document.getElementById('admin-importsuivi-hist-annee').value.trim();
  const nom_classe         = document.getElementById('admin-importsuivi-hist-nom-classe').value.trim();
  const etablissement      = document.getElementById('admin-importsuivi-hist-etablissement').value.trim();
  const status             = document.getElementById('admin-importsuivi-hist-status');
  const resultat           = document.getElementById('admin-importsuivi-hist-resultat');

  if (!chemin_classe || !chemin_sequencesdb || !annee || !nom_classe) {
    status.textContent = 'Remplir tous les champs obligatoires.';
    status.style.color = 'var(--danger)';
    return;
  }

  const btn = document.getElementById('admin-importsuivi-hist-btn-lancer');
  btn.disabled = true;
  status.textContent = 'Import en cours…';
  status.style.color = 'var(--text-secondary)';
  resultat.style.display = 'none';

  try {
    const res = await api('/api/import/historique', {
      method: 'POST',
      body: JSON.stringify({
        chemin_classe, chemin_sequencesdb,
        niveau, annee, nom_classe, etablissement
      })
    });

    if (res.error) {
      status.textContent = 'Erreur : ' + res.error;
      status.style.color = 'var(--danger)';
      document.getElementById('admin-importsuivi-hist-resultat-contenu').innerHTML =
        `<pre style="font-size:11px;color:var(--danger);white-space:pre-wrap">${res.detail || ''}</pre>`;
      resultat.style.display = '';
      return;
    }

    status.textContent = '✓ Import terminé';
    status.style.color = 'var(--success)';

    const avertissements = (res.erreurs || []).length
      ? `<div style="margin-top:8px;padding:8px;background:var(--warning-bg);border-radius:var(--radius-sm);font-size:11px;color:var(--warning-text)">
          <strong>${res.erreurs.length} avertissement(s) :</strong><br>
          ${res.erreurs.map(e=>`• ${e}`).join('<br>')}
        </div>` : '';

    document.getElementById('admin-importsuivi-hist-resultat-contenu').innerHTML = `
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:10px">
        <div style="text-align:center;padding:10px;background:var(--surface-light);border-radius:var(--radius-sm)">
          <div style="font-size:22px;font-weight:700;color:var(--primary)">${res.eleves}</div>
          <div style="font-size:11px;color:var(--text-secondary)">Élèves</div>
        </div>
        <div style="text-align:center;padding:10px;background:var(--surface-light);border-radius:var(--radius-sm)">
          <div style="font-size:22px;font-weight:700;color:var(--primary)">${res.creneaux}</div>
          <div style="font-size:11px;color:var(--text-secondary)">Créneaux</div>
        </div>
        <div style="text-align:center;padding:10px;background:var(--surface-light);border-radius:var(--radius-sm)">
          <div style="font-size:22px;font-weight:700;color:var(--success)">✓</div>
          <div style="font-size:11px;color:var(--text-secondary)">Importé</div>
        </div>
      </div>
      <div style="font-size:12px">
        <strong>Classe créée :</strong> ${nom_classe} (id: ${res.classe_id})<br>
        <strong>Progression :</strong> ${res.progression_id}<br>
        <strong>Suivi :</strong> données historiques liées à la progression
      </div>
      ${avertissements}`;

    resultat.style.display = '';

    // Recharger les classes
    await loadClasses();
    buildClasseSel();
    renderClassesList();

  } catch(e) {
    status.textContent = 'Erreur : ' + e.message;
    status.style.color = 'var(--danger)';
  } finally {
    btn.disabled = false;
  }
}


// ═══════════════════════════════════════════════════════════════════════════
//  Gestion des établissements (v0.6.3b)
// ═══════════════════════════════════════════════════════════════════════════

let ETABS_ALL = [];   // cache de la liste complète des établissements

function gestionSousOnglet(nom) {
  // Bascule entre les 2 panneaux "Classes" et "Établissements"
  ['classes','etabs'].forEach(n => {
    const p = document.getElementById('gest-'+n);
    const b = document.getElementById('gest-btn-'+n);
    if (p) p.style.display = (n===nom) ? '' : 'none';
    if (b) b.classList.toggle('active', n===nom);
  });
  if (nom === 'etabs') renderEtablissements();
}

function gestionAllerEtablissements() {
  // Depuis le bandeau d'invitation. v0.19.1.2 — passer par la navigation
  // pour activer le bon bouton de la barre 2 (Gestion > Établissement).
  if (typeof suiviSwitch === 'function'
      && SUIVI_PORTEE_ACTIVE === 'gestion') {
    suiviSwitch('etab');
  } else if (typeof sousOnglet === 'function') {
    sousOnglet('parametrage');
    suiviSwitch('etab');
  } else {
    gestionSousOnglet('etabs');
  }
}

async function chargerEtablissementsEtBandeau() {
  try {
    const r = await api('/api/etablissements');
    ETABS_ALL = r.etablissements || [];
  } catch (e) {
    console.warn('chargerEtablissements:', e);
    ETABS_ALL = [];
  }
  // Bandeau : n'afficher que si établissement utilisé + académie vide
  const a_completer = ETABS_ALL.filter(e => !e.academie);
  const bandeau = document.getElementById('etab-bandeau');
  const txt     = document.getElementById('etab-bandeau-txt');
  if (!bandeau || !txt) return;
  if (a_completer.length === 0) {
    bandeau.style.display = 'none';
  } else {
    bandeau.style.display = '';
    const n = a_completer.length;
    txt.textContent = n === 1
      ? `1 établissement n'a pas d'académie renseignée. Sans académie, les vacances scolaires ne peuvent pas s'afficher dans la progression.`
      : `${n} établissements n'ont pas d'académie renseignée. Sans académie, les vacances scolaires ne peuvent pas s'afficher dans la progression.`;
  }
}

function renderEtablissements() {
  const root = document.getElementById('etabs-list');
  if (!root) return;
  if (ETABS_ALL.length === 0) {
    root.innerHTML = '<p style="font-size:13px;color:#999">Aucun établissement pour l\'instant.</p>';
    return;
  }
  root.innerHTML = ETABS_ALL.map(e => etabCard(e)).join('');
}

function etabCard(e) {
  let etatBadge;
  if (e.etat === 'valide') {
    etatBadge = '<span style="background:#e6f4ea;color:#137333;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:500">✓ Validé</span>';
  } else if (e.academie) {
    etatBadge = '<span style="background:#e8f0fe;color:#1967d2;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:500">Académie saisie</span>';
  } else {
    etatBadge = '<span style="background:#fef7e0;color:#b06000;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:500">À compléter</span>';
  }
  const acad = e.academie || '<em style="color:#c33">académie manquante</em>';
  const ville = e.ville || '—';
  const uai = e.uai ? `<code style="font-size:11px">${escapeHtml(e.uai)}</code>` : '—';
  return `
    <div class="card" style="margin-bottom:8px">
      <div style="display:flex;align-items:start;justify-content:space-between;gap:12px;flex-wrap:wrap">
        <div style="flex:1;min-width:250px">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
            <strong style="font-size:14px">${escapeHtml(e.nom)}</strong>
            ${etatBadge}
          </div>
          <div style="display:grid;grid-template-columns:max-content 1fr;gap:4px 12px;font-size:12px">
            <span style="color:#666">Académie</span>
            <span>${acad}</span>
            <span style="color:#666">Ville</span>
            <span>${escapeHtml(ville)}</span>
            <span style="color:#666">UAI</span>
            <span>${uai}</span>
          </div>
        </div>
        <div style="display:flex;flex-direction:column;gap:6px;min-width:160px">
          ${e.etat !== 'valide'
            ? `<button class="btn-prim" style="font-size:12px" onclick="etabValiderShowPopup('${e.id}')">Valider avec UAI</button>`
            : ''}
          <button class="btn-sm" style="font-size:12px" onclick="etabEditerShow('${e.id}')">Modifier</button>
          <button class="btn-sm" style="font-size:12px" onclick="grilleHoraireToggle('${e.id}')">Grille horaire</button>
          <button class="btn-sm" style="font-size:12px" onclick="sallesToggle('${e.id}')">Salles</button>
          ${ETABS_ALL.length > 1
            ? `<button class="btn-sm" style="font-size:12px" onclick="etabFusionnerShow('${e.id}')">Fusionner avec…</button>`
            : ''}
        </div>
      </div>
      <div id="etab-form-${e.id}" style="display:none;margin-top:10px;padding-top:10px;border-top:1px solid var(--border)"></div>
      <div id="etab-salles-${e.id}" class="sal-zone" style="display:none"></div>
    </div>
  `;
}

// ────────────────────────────────────────────────────────────────────────────
// v0.20.0 — Grille horaire par établissement
// Créneaux M1..M4 / S1..S4 (code, libellé, horaires, demi-journée). Éditable.
// Backend : /api/etablissements/<id>/grille-horaire (GET/POST),
//           /api/grille-horaire/<creneau_id> (PUT/DELETE).
// ────────────────────────────────────────────────────────────────────────────
const _GRILLE_OUVERTE = {};  // etabId -> bool

async function grilleHoraireToggle(etabId) {
  const zone = document.getElementById('etab-form-' + etabId);
  if (!zone) return;
  if (_GRILLE_OUVERTE[etabId] && zone.style.display !== 'none') {
    zone.style.display = 'none';
    _GRILLE_OUVERTE[etabId] = false;
    return;
  }
  _GRILLE_OUVERTE[etabId] = true;
  zone.style.display = '';
  zone.innerHTML = '<p style="font-size:12px;color:#999">Chargement…</p>';
  await grilleHoraireCharger(etabId);
}

async function grilleHoraireCharger(etabId) {
  const zone = document.getElementById('etab-form-' + etabId);
  if (!zone) return;
  let creneaux = [];
  try {
    const r = await api('/api/etablissements/' + etabId + '/grille-horaire');
    creneaux = (r && r.creneaux) || [];
  } catch (e) {
    zone.innerHTML = '<p style="font-size:12px;color:#c33">Erreur de chargement.</p>';
    return;
  }
  grilleHoraireRender(etabId, creneaux);
}

function grilleHoraireRender(etabId, creneaux) {
  const zone = document.getElementById('etab-form-' + etabId);
  if (!zone) return;
  const _e = s => escapeHtml(String(s == null ? '' : s));
  const lignes = creneaux.map(c => `
    <tr>
      <td style="padding:3px 6px"><input value="${_e(c.code)}" data-f="code" style="width:48px;font-size:12px" readonly title="Le code n'est pas modifiable"></td>
      <td style="padding:3px 6px"><input value="${_e(c.libelle)}" data-f="libelle" style="width:120px;font-size:12px"
             onblur="grilleHoraireMaj('${etabId}','${c.id}', this.closest('tr'))"></td>
      <td style="padding:3px 6px"><input value="${_e(c.heure_debut)}" data-f="heure_debut" placeholder="08:25" style="width:60px;font-size:12px"
             onblur="grilleHoraireMaj('${etabId}','${c.id}', this.closest('tr'))"></td>
      <td style="padding:3px 6px"><input value="${_e(c.heure_fin)}" data-f="heure_fin" placeholder="09:20" style="width:60px;font-size:12px"
             onblur="grilleHoraireMaj('${etabId}','${c.id}', this.closest('tr'))"></td>
      <td style="padding:3px 6px">
        <select data-f="demi_journee" style="font-size:12px" onchange="grilleHoraireMaj('${etabId}','${c.id}', this.closest('tr'))">
          <option value="M"${c.demi_journee === 'M' ? ' selected' : ''}>Matin</option>
          <option value="S"${c.demi_journee === 'S' ? ' selected' : ''}>Après-midi</option>
        </select>
      </td>
      <td style="padding:3px 6px"><button class="btn-sm" style="color:var(--danger)"
             onclick="grilleHoraireSupprimer('${etabId}','${c.id}','${_e(c.code)}')" title="Supprimer" aria-label="Supprimer">×</button></td>
    </tr>`).join('');
  zone.innerHTML = `
    <div style="font-size:13px;font-weight:500;margin-bottom:6px">Grille horaire</div>
    <p style="font-size:11px;color:#999;margin-bottom:8px">
      Créneaux de cours de l'établissement (M1–M4 le matin, S1–S4 l'après-midi).
      Ils servent de trame à la saisie de l'emploi du temps. Le code n'est pas
      modifiable ; pour changer un code, supprimer et recréer le créneau.
    </p>
    <table style="border-collapse:collapse;font-size:12px">
      <thead><tr style="text-align:left;color:#666">
        <th style="padding:3px 6px">Code</th><th style="padding:3px 6px">Libellé</th>
        <th style="padding:3px 6px">Début</th><th style="padding:3px 6px">Fin</th>
        <th style="padding:3px 6px">Demi-journée</th><th></th>
      </tr></thead>
      <tbody id="grille-tbody-${etabId}">${lignes}</tbody>
    </table>
    <div style="display:flex;align-items:center;gap:6px;margin-top:10px">
      <input id="grille-new-code-${etabId}" placeholder="Code (ex : S5)" style="width:90px;font-size:12px">
      <input id="grille-new-deb-${etabId}" placeholder="Début 17:05" style="width:80px;font-size:12px">
      <input id="grille-new-fin-${etabId}" placeholder="Fin 18:00" style="width:80px;font-size:12px">
      <select id="grille-new-dj-${etabId}" style="font-size:12px">
        <option value="M">Matin</option><option value="S" selected>Après-midi</option>
      </select>
      <button class="btn-sm" onclick="grilleHoraireAjouter('${etabId}')">Ajouter</button>
      <span id="grille-status-${etabId}" style="font-size:12px;color:#4a7"></span>
    </div>`;
}

function _grilleStatus(etabId, msg, err) {
  const s = document.getElementById('grille-status-' + etabId);
  if (!s) return;
  s.style.color = err ? '#c33' : '#4a7';
  s.textContent = msg;
  if (!err && msg) setTimeout(() => { if (s) s.textContent = ''; }, 2000);
}

async function grilleHoraireMaj(etabId, creneauId, rowEl) {
  const val = f => { const el = rowEl.querySelector('[data-f=' + f + ']'); return el ? el.value : ''; };
  try {
    const r = await fetch('/api/grille-horaire/' + creneauId, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        libelle: val('libelle'), heure_debut: val('heure_debut'),
        heure_fin: val('heure_fin'), demi_journee: val('demi_journee'),
      }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status));
    _grilleStatus(etabId, '✓ enregistré');
  } catch (e) {
    _grilleStatus(etabId, 'Erreur : ' + e.message, true);
  }
}

async function grilleHoraireAjouter(etabId) {
  const g = id => document.getElementById(id + '-' + etabId);
  const code = (g('grille-new-code').value || '').trim();
  if (!code) { _grilleStatus(etabId, 'Saisir un code.', true); return; }
  try {
    const r = await fetch('/api/etablissements/' + etabId + '/grille-horaire', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        code, heure_debut: g('grille-new-deb').value || '',
        heure_fin: g('grille-new-fin').value || '',
        demi_journee: g('grille-new-dj').value || 'M',
      }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status));
    await grilleHoraireCharger(etabId);
    _grilleStatus(etabId, 'Ajouté.');
  } catch (e) {
    _grilleStatus(etabId, 'Erreur : ' + e.message, true);
  }
}

async function grilleHoraireSupprimer(etabId, creneauId, code) {
  if (!confirm('Supprimer le créneau ' + code + ' ?')) return;
  try {
    const r = await fetch('/api/grille-horaire/' + creneauId, { method: 'DELETE' });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      throw new Error(d.error || ('HTTP ' + r.status));
    }
    await grilleHoraireCharger(etabId);
    _grilleStatus(etabId, 'Supprimé.');
  } catch (e) {
    _grilleStatus(etabId, 'Erreur : ' + e.message, true);
  }
}

function etabValiderShowPopup(etabId) {
  const zone = document.getElementById('etab-form-'+etabId);
  if (!zone) return;
  zone.style.display = '';
  zone.innerHTML = `
    <div style="font-size:13px;font-weight:500;margin-bottom:8px">Valider avec UAI</div>
    <p style="font-size:11px;color:#666;margin-bottom:8px">
      Le code UAI est un identifiant national (ex : <code>0351234A</code>).
      Tu peux le trouver sur <a href="https://www.education.gouv.fr/annuaire" target="_blank">education.gouv.fr/annuaire</a>.
    </p>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
      <input id="uai-inp-${etabId}" placeholder="0351234A" style="width:140px;font-family:monospace">
      <button class="btn-prim" onclick="etabValiderConfirm('${etabId}')">Valider</button>
      <button class="btn-sm" onclick="etabFormClose('${etabId}')">Annuler</button>
    </div>
    <div id="uai-err-${etabId}" style="color:#c33;font-size:12px;margin-top:6px"></div>
  `;
  setTimeout(() => document.getElementById('uai-inp-'+etabId)?.focus(), 50);
}

async function etabValiderConfirm(etabId) {
  const inp = document.getElementById('uai-inp-'+etabId);
  const err = document.getElementById('uai-err-'+etabId);
  const uai = (inp?.value || '').trim();
  err.textContent = '';
  if (!uai) {
    err.textContent = 'UAI requis.';
    return;
  }
  try {
    const resp = await fetch(`/api/etablissements/${etabId}/valider`, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({uai}),
    });
    if (resp.status === 409) {
      // Doublon détecté : proposer la fusion
      const data = await resp.json();
      if (data.code === 'doublon_detecte') {
        etabProposerFusionApresDoublon(etabId, data);
      } else {
        err.textContent = data.error || 'Conflit';
      }
      return;
    }
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({error: 'Erreur'}));
      err.textContent = data.error || `Erreur ${resp.status}`;
      return;
    }
    // Succès
    await chargerEtablissementsEtBandeau();
    renderEtablissements();
  } catch (e) {
    err.textContent = 'Erreur réseau : ' + e.message;
  }
}

function etabProposerFusionApresDoublon(sourceId, data) {
  // data contient etab_cible_id, nom_officiel
  const zone = document.getElementById('etab-form-'+sourceId);
  if (!zone) return;
  const cible = ETABS_ALL.find(e => e.id === data.etab_cible_id);
  if (!cible) {
    // fallback : message simple
    const err = document.getElementById('uai-err-'+sourceId);
    if (err) err.textContent = data.error || 'Doublon détecté.';
    return;
  }
  const source = ETABS_ALL.find(e => e.id === sourceId);
  zone.innerHTML = `
    <div style="background:#fef7e0;border:1px solid #f9d568;padding:10px;border-radius:4px;margin-bottom:10px">
      <div style="font-size:13px;font-weight:500;margin-bottom:6px">⚠️ Doublon détecté</div>
      <p style="font-size:12px;margin-bottom:6px">
        L'annuaire officiel donne le nom <strong>${escapeHtml(data.nom_officiel)}</strong>,
        qui est déjà celui d'un autre établissement en base. Il faut fusionner
        les deux avant de valider.
      </p>
      <p style="font-size:12px;margin-bottom:10px">
        La fusion va migrer toutes les classes et progressions de
        <strong>${escapeHtml(source?.nom || sourceId)}</strong> vers
        <strong>${escapeHtml(cible.nom)}</strong>, puis supprimer le premier.
        ${cible.etat === 'valide' ? 'La cible est déjà validée.' : 'La cible sera à valider par UAI ensuite.'}
      </p>
      <div style="display:flex;gap:8px">
        <button class="btn-prim" onclick="etabFusionnerConfirm('${sourceId}', '${cible.id}')">Fusionner</button>
        <button class="btn-sm" onclick="etabFormClose('${sourceId}')">Annuler</button>
      </div>
      <div id="fusion-err-${sourceId}" style="color:#c33;font-size:12px;margin-top:6px"></div>
    </div>
  `;
}

function etabFusionnerShow(sourceId) {
  const zone = document.getElementById('etab-form-'+sourceId);
  if (!zone) return;
  const source = ETABS_ALL.find(e => e.id === sourceId);
  // Cibles possibles : tous les autres établissements
  const cibles = ETABS_ALL.filter(e => e.id !== sourceId);
  if (cibles.length === 0) {
    zone.style.display = '';
    zone.innerHTML = `<p style="font-size:12px;color:#c33">Aucun autre établissement disponible pour la fusion.</p>`;
    return;
  }
  const options = cibles.map(e =>
    `<option value="${e.id}">${escapeHtml(e.nom)}${e.etat==='valide'?' (validé)':''}</option>`
  ).join('');
  zone.style.display = '';
  zone.innerHTML = `
    <div style="font-size:13px;font-weight:500;margin-bottom:8px">Fusionner ${escapeHtml(source.nom)} avec…</div>
    <p style="font-size:11px;color:#666;margin-bottom:8px">
      Toutes les classes et progressions seront migrées vers la cible, puis
      <strong>${escapeHtml(source.nom)}</strong> sera supprimé.
    </p>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:8px">
      <select id="fusion-cible-${sourceId}" style="flex:1;min-width:200px">${options}</select>
    </div>
    <div style="display:flex;gap:8px">
      <button class="btn-prim" onclick="etabFusionnerConfirmFromSelect('${sourceId}')">Fusionner</button>
      <button class="btn-sm" onclick="etabFormClose('${sourceId}')">Annuler</button>
    </div>
    <div id="fusion-err-${sourceId}" style="color:#c33;font-size:12px;margin-top:6px"></div>
  `;
}

function etabFusionnerConfirmFromSelect(sourceId) {
  const sel = document.getElementById('fusion-cible-'+sourceId);
  if (!sel) return;
  etabFusionnerConfirm(sourceId, sel.value);
}

async function etabFusionnerConfirm(sourceId, cibleId) {
  const err = document.getElementById('fusion-err-'+sourceId);
  if (err) err.textContent = '';
  try {
    const resp = await fetch(`/api/etablissements/${sourceId}/fusionner`, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({cible_id: cibleId}),
    });
    if (resp.status === 409) {
      const data = await resp.json();
      if (err) {
        err.innerHTML = `<strong>${escapeHtml(data.error)}</strong>`;
        if (data.code === 'conflit_progression' && data.details?.conflits) {
          err.innerHTML += `<br><span style="color:#666">${data.details.conflits.length} conflit(s). Supprimer la progression en double avant de réessayer.</span>`;
        }
      }
      return;
    }
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({error: `HTTP ${resp.status}`}));
      if (err) err.textContent = data.error || 'Erreur';
      return;
    }
    const result = await resp.json();
    alert(`Fusion réussie.\n${result.classes_migrees} classe(s) migrée(s), ${result.progressions_migrees} progression(s).`);
    await chargerEtablissementsEtBandeau();
    // Recharger aussi la liste des classes (leurs établissements ont changé)
    await loadClasses();
    renderEtablissements();
  } catch (e) {
    if (err) err.textContent = 'Erreur réseau : ' + e.message;
  }
}

function etabEditerShow(etabId) {
  const zone = document.getElementById('etab-form-'+etabId);
  if (!zone) return;
  const e = ETABS_ALL.find(x => x.id === etabId);
  if (!e) return;
  zone.style.display = '';
  zone.innerHTML = `
    <div style="font-size:13px;font-weight:500;margin-bottom:8px">Modifier</div>
    <div class="field-row"><label>Nom</label><input id="ed-nom-${etabId}" value="${escapeHtml(e.nom)}"></div>
    <div class="field-row"><label>Académie</label><select id="ed-acad-${etabId}"><option>${escapeHtml(e.academie || '')}</option></select></div>
    <div class="field-row"><label>Ville</label><input id="ed-ville-${etabId}" value="${escapeHtml(e.ville || '')}"></div>
    <div style="display:flex;gap:8px;margin-top:10px">
      <button class="btn-prim" onclick="etabEditerConfirm('${etabId}')">Enregistrer</button>
      <button class="btn-sm" onclick="etabFormClose('${etabId}')">Annuler</button>
    </div>
    <div id="ed-err-${etabId}" style="color:#c33;font-size:12px;margin-top:6px"></div>
  `;
  // v0.41.2 — Académie choisie dans la liste des académies connues.
  _academies().then(liste => {
    const sel = document.getElementById('ed-acad-' + etabId);
    if (sel) sel.innerHTML = _optionsAcademies(liste, e.academie || '');
  });
}

async function etabEditerConfirm(etabId) {
  const err = document.getElementById('ed-err-'+etabId);
  if (err) err.textContent = '';
  const body = {
    nom:      document.getElementById('ed-nom-'+etabId)?.value.trim(),
    academie: document.getElementById('ed-acad-'+etabId)?.value.trim(),
    ville:    document.getElementById('ed-ville-'+etabId)?.value.trim(),
  };
  try {
    const resp = await fetch(`/api/etablissements/${etabId}`, {
      method: 'PATCH',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({error: 'Erreur'}));
      if (err) err.textContent = data.error || 'Erreur';
      return;
    }
    await chargerEtablissementsEtBandeau();
    renderEtablissements();
  } catch (e) {
    if (err) err.textContent = 'Erreur réseau : ' + e.message;
  }
}

function etabFormClose(etabId) {
  const zone = document.getElementById('etab-form-'+etabId);
  if (zone) { zone.style.display = 'none'; zone.innerHTML = ''; }
}

// Helper HTML escape simple (si pas déjà défini ailleurs)
if (typeof escapeHtml === 'undefined') {
  function escapeHtml(s) {
    if (s == null) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
}


// ═══════════════════════════════════════════════════════════════════════════
//  Calendrier scolaire (v0.6.3c)
// ═══════════════════════════════════════════════════════════════════════════

let CAL_VACANCES = null;   // [{description, start_date, end_date, ...}]
let CAL_FERIES   = {};     // { 'AAAA-MM-JJ': 'Nom' }
let CAL_ANNEE    = null;   // année scolaire chargée ('2025-2026')
let CAL_ACADEMIE = null;   // académie utilisée pour le dernier chargement

const MOIS_FR = ['janv.','févr.','mars','avr.','mai','juin',
                 'juil.','août','sept.','oct.','nov.','déc.'];
const JOUR_FR = ['dim.','lun.','mar.','mer.','jeu.','ven.','sam.'];


// Formate une Date JS en 'AAAA-MM-JJ' en heure locale (sans passer par toISOString
// qui convertit en UTC et peut décaler d'un jour selon la timezone du navigateur).
function _dateToISO(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const j = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${j}`;
}

// Liste des lundis entre deux dates (inclusive), au format AAAA-MM-JJ
function _lundisEntre(iso_debut, iso_fin) {
  const d = new Date(iso_debut + 'T00:00:00');
  // Ajuster au lundi précédent ou actuel
  const jour = d.getDay();  // 0=dim, 1=lun, ..., 6=sam
  const decalage = jour === 0 ? -6 : (1 - jour);
  d.setDate(d.getDate() + decalage);

  const f = new Date(iso_fin + 'T00:00:00');
  const lundis = [];
  while (d <= f) {
    lundis.push(_dateToISO(d));
    d.setDate(d.getDate() + 7);
  }
  return lundis;
}

// Début et fin de l'année scolaire (1er sept → 31 août)
function _bornesAnneeScolaire(anneeScolaire) {
  const [d, f] = anneeScolaire.split('-').map(Number);
  return { debut: `${d}-09-01`, fin: `${f}-08-31` };
}

// Retourne la date ISO du jour ajouté à lundiISO
function _jourSemaine(lundiISO, offsetJours) {
  const d = new Date(lundiISO + 'T00:00:00');
  d.setDate(d.getDate() + offsetJours);
  return _dateToISO(d);
}

// Une semaine est-elle une semaine de vacances (pour les élèves) ?
// Règle : on teste le chevauchement avec la semaine DE CLASSE (lundi-vendredi).
// Les vacances qui ne couvrent que le samedi ou le dimanche de la semaine précédente
// ne comptent pas, puisque les élèves ne sont pas en cours ces jours-là.
function _vacancesDeLaSemaine(lundiISO) {
  if (!CAL_VACANCES) return null;
  const lundiIso    = lundiISO;                  // début semaine de classe
  const vendrediIso = _jourSemaine(lundiISO, 4); // fin semaine de classe

  for (const v of CAL_VACANCES) {
    if (!v.start_date || !v.end_date) continue;
    // v.end_date est le jour de REPRISE des cours, donc la vacance est
    // "active" pour les élèves jusqu'à (v.end_date - 1) inclus.
    const vacDebut = v.start_date;            // premier jour de vacances
    const vacFinExclusive = v.end_date;       // jour de reprise (= fin exclusive)

    // Chevauchement [vacDebut, vacFinExclusive[ avec [lundiIso, vendrediIso]
    // (inclusif sur vendrediIso)
    if (vacDebut <= vendrediIso && vacFinExclusive > lundiIso) {
      return v.description;
    }
  }
  return null;
}

// Jours fériés tombant dans la semaine (lundi à dimanche affiché)
function _feriesDeLaSemaine(lundiISO) {
  const feries = [];
  for (let i = 0; i < 7; i++) {
    const iso = _jourSemaine(lundiISO, i);
    if (CAL_FERIES[iso]) feries.push({date: iso, nom: CAL_FERIES[iso]});
  }
  return feries;
}

// Format date courte "15 sept."
function _dateCourte(iso) {
  const d = new Date(iso + 'T00:00:00');
  return `${d.getDate()} ${MOIS_FR[d.getMonth()]}`;
}

// v0.19.1.1 — Exposition explicite des helpers calendrier purs sur window.
// AtelierProgression (atelier_progression.js, chargé dans un autre script)
// les consomme via window.* ; or `const`/`function` au top-level d'app.js
// créent des liaisons globales NON accessibles comme propriétés de window.
// On les ré-expose donc nommément. CAL_VACANCES/CAL_FERIES sont réaffectés
// dynamiquement par la classe (window.CAL_* = …), ce qui est compatible.
window.MOIS_FR              = MOIS_FR;
window.JOUR_FR              = JOUR_FR;
window._dateToISO          = _dateToISO;
window._lundisEntre        = _lundisEntre;
window._bornesAnneeScolaire = _bornesAnneeScolaire;
window._jourSemaine        = _jourSemaine;
window._vacancesDeLaSemaine = _vacancesDeLaSemaine;
window._feriesDeLaSemaine  = _feriesDeLaSemaine;
window._dateCourte         = _dateCourte;

// ═════════════════════════════════════════════════════════════════════════════
// v0.8 — Compilateur batch des atomes
// ═════════════════════════════════════════════════════════════════════════════
//
// Sous-onglet Admin > Compilation. Permet de compiler en série tous les
// atomes filtrés (type, niveau, séquence). Le serveur stream les résultats
// via SSE (text/event-stream), un événement par atome compilé.
//
// État global du batch en cours (sert à l'annulation et à éviter les
// confusions entre runs successifs).
let COMPIL_EVENTSOURCE = null;  // EventSource actif, null hors run
let COMPIL_PREVIEW_OK  = false; // true après un aperçu réussi → bouton Lancer activé
let COMPIL_RUN_TOTAL   = 0;     // total à traiter (pour la barre de progression)

// Initialisation du sous-onglet : injection des séquences S01..S14, lecture
// de la config courante, reset des compteurs.
async function compilBatchInit() {
  // Injecter S01..S14 dans le select séquence (seulement à la première fois).
  const sel = document.getElementById('rdl-filtre-sequence');
  if (sel && sel.querySelectorAll('option').length <= 1) {
    const opts = [];
    for (let i = 1; i <= 14; i++) {
      const code = 'S' + String(i).padStart(2, '0');
      opts.push(`<option value="${code}">${code}</option>`);
    }
    sel.insertAdjacentHTML('beforeend', opts.join(''));
  }
  // v0.18.4 — Les paramètres de compilation vivent dans l'onglet Préférences
  // (inputs pref-rdl-*). On s'assure qu'ils sont chargés depuis la config,
  // même si l'onglet Préférences n'a pas encore été ouvert, pour que
  // _compilLireParams() lise des valeurs à jour au lancement du batch.
  if (typeof prefChargerParamsCompilation === 'function') {
    try { await prefChargerParamsCompilation(); } catch (e) { /* défauts HTML */ }
  }
}

// ════════════════════════════════════════════════════════════════════════════
// v0.18.1 — Outil Recherche (Outils généraux)
//
// Recherche transversale sur les 5 types d'atomes via GET /api/recherche.
// - rechercheInit()   : init du panneau (injection des séquences S01..S14).
// - rechercheLancer()  : lit les filtres, appelle l'API, affiche les résultats.
// - rechercheRendre()  : rendu des résultats groupés par type.
//
// Libellés lisibles par type (pluriel) pour les en-têtes de groupe.
const _RECH_LABEL_TYPE = {
  notion:   'Notions',
  methode:  'Méthodes',
  exercice: 'Exercices',
  fiche:    'Fiches de résumé',
  carte:    "Cartes d'automatisme",
};
// Ordre d'affichage des groupes (aligné sur le rendu par lot : cours → fiches
// → cartes).
const _RECH_ORDRE_TYPES = ['notion', 'methode', 'exercice', 'fiche', 'carte'];

// Init : injecte les séquences S01..S14 dans le filtre (une seule fois).
function rechercheInit() {
  const sel = document.getElementById('rech-filtre-sequence');
  if (sel && sel.querySelectorAll('option').length <= 1) {
    const opts = [];
    for (let i = 1; i <= 14; i++) {
      const code = 'S' + String(i).padStart(2, '0');
      opts.push(`<option value="${code}">${code}</option>`);
    }
    sel.insertAdjacentHTML('beforeend', opts.join(''));
  }
  // Permettre de lancer la recherche en appuyant sur Entrée dans le champ.
  const champ = document.getElementById('rech-texte');
  if (champ && !champ._rechListener) {
    champ.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') { ev.preventDefault(); rechercheLancer(); }
    });
    champ._rechListener = true;
  }
}

// Lance la recherche : lit les filtres, appelle l'API, affiche le résultat.
async function rechercheLancer() {
  const type = document.getElementById('rech-filtre-type').value;
  const niveau = document.getElementById('rech-filtre-niveau').value;
  const sequence = document.getElementById('rech-filtre-sequence').value;
  const etat = document.getElementById('rech-filtre-etat').value;
  const texte = document.getElementById('rech-texte').value;
  const regex = document.getElementById('rech-regex').checked;

  const errDiv = document.getElementById('rech-erreur');
  const zone = document.getElementById('rech-resultats');
  const btn = document.getElementById('rech-btn');
  errDiv.style.display = 'none';
  errDiv.textContent = '';

  const params = new URLSearchParams();
  if (type) params.set('type', type);
  if (niveau) params.set('niveau', niveau);
  if (sequence) params.set('sequence', sequence);
  if (etat) params.set('etat', etat);
  if (texte) params.set('texte', texte);
  if (regex) params.set('regex', '1');

  btn.disabled = true;
  const ancienLabel = btn.textContent;
  btn.textContent = 'Recherche…';
  zone.innerHTML = '<div style="color:var(--text-muted);padding:8px 0">Recherche en cours…</div>';

  try {
    const r = await fetch('/api/recherche?' + params.toString());
    const data = await r.json();
    if (!r.ok) {
      // Erreur (regex invalide, type invalide…) : message inline, pas de crash.
      errDiv.textContent = data.error || `Erreur HTTP ${r.status}`;
      errDiv.style.display = '';
      zone.innerHTML = '';
      return;
    }
    rechercheRendre(data);
  } catch (e) {
    errDiv.textContent = 'Erreur réseau : ' + e.message;
    errDiv.style.display = '';
    zone.innerHTML = '';
  } finally {
    btn.disabled = false;
    btn.textContent = ancienLabel;
  }
}

// Rend les résultats groupés par type.
function rechercheRendre(data) {
  const zone = document.getElementById('rech-resultats');
  const total = data.total || 0;

  if (total === 0) {
    zone.innerHTML = '<div style="color:var(--text-muted);padding:8px 0">Aucun atome ne correspond.</div>';
    return;
  }

  const blocs = [];
  blocs.push(
    `<div style="font-size:12px;color:var(--text-secondary);margin-bottom:10px">` +
    `${total} résultat${total > 1 ? 's' : ''}</div>`
  );

  for (const t of _RECH_ORDRE_TYPES) {
    const liste = data[t] || [];
    if (liste.length === 0) continue;

    blocs.push(
      `<div class="atl-cadre atl-cadre--compact" style="margin-bottom:12px">` +
      `<div class="atl-cadre-titre">${_RECH_LABEL_TYPE[t]} ` +
      `<span style="color:var(--text-muted);font-weight:400">(${liste.length})</span></div>`
    );

    const lignes = liste.map(a => {
      const etatBadge = a.etat_code === 'valide'
        ? `<span style="font-size:11px;color:var(--success)">validé</span>`
        : `<span style="font-size:11px;color:var(--text-muted)">en cours</span>`;
      const titre = a.titre
        ? escapeHtml(a.titre)
        : `<span style="color:var(--text-muted);font-style:italic">(sans titre)</span>`;
      // v0.18.2 — « Ouvrir » est un lien deeplink : clic simple = en place,
      // Ctrl/⌘+clic = nouvel onglet (cf. lienAtomeHTML / ouvrirAtomeDepuisEvent).
      const lienOuvrir = lienAtomeHTML(
        t, a.id, a.niveau, a.sequence,
        'Ouvrir',
        'class="vbtn" style="font-size:12px;padding:2px 10px;text-decoration:none"'
      );
      return (
        `<div style="display:flex;align-items:center;gap:10px;padding:5px 0;` +
        `border-top:1px solid var(--border)">` +
        `<code style="font-size:11px;color:var(--text-secondary);` +
        `white-space:nowrap">${escapeHtml(a.identifiant)}</code>` +
        `<span style="flex:1;min-width:0;overflow:hidden;` +
        `text-overflow:ellipsis;white-space:nowrap">${titre}</span>` +
        `${etatBadge}` +
        `${lienOuvrir}` +
        `</div>`
      );
    });

    blocs.push(lignes.join(''));
    blocs.push('</div>');
  }

  zone.innerHTML = blocs.join('');
}

// Échappement pour insertion dans un attribut onclick="...'VALEUR'...".
// Les ids et codes niveau/séquence sont simples (pas de quote attendue),
// mais on protège tout de même contre une apostrophe ou un backslash.
function escAttrJs(s) {
  return String(s == null ? '' : s)
    .replace(/\\/g, '\\\\')
    .replace(/'/g, "\\'");
}


// Récupère les filtres et paramètres saisis dans l'UI.
function _compilLireParams() {
  // v0.18.4 — Les paramètres de compilation ont migré dans l'onglet
  // Préférences (> Outils > Rendu par lot), inputs `pref-rdl-*`. Ils restent
  // dans le DOM en permanence (l'onglet est masqué via display:none, pas
  // retiré), donc lisibles ici. Le backend les persiste au lancement.
  // Fallback défensif : si un input est absent (DOM partiel), on prend une
  // valeur par défaut raisonnable plutôt que de planter.
  const val = (id, parDefaut) => {
    const el = document.getElementById(id);
    return el ? el.value : parDefaut;
  };
  return {
    type:        document.getElementById('rdl-filtre-type').value,
    niveau:      document.getElementById('rdl-filtre-niveau').value,
    sequence:    document.getElementById('rdl-filtre-sequence').value,
    timeout_court: val('pref-rdl-timeout-court', '30'),
    timeout_long:  val('pref-rdl-timeout-long', '300'),
    max_erreurs:   val('pref-rdl-max-erreurs', '5'),
    tikz_libraries: val('pref-rdl-tikz-libs',
                        'babel,shapes.geometric,arrows.meta,positioning,calc'),
    tblr_libraries: val('pref-rdl-tblr-libs', 'booktabs,varwidth'),
  };
}

// Aperçu : compte les atomes éligibles, déverrouille le bouton « Lancer ».
async function compilBatchPreview() {
  const p = _compilLireParams();
  const qs = new URLSearchParams({
    type: p.type, niveau: p.niveau, sequence: p.sequence,
  });
  const status = document.getElementById('rdl-status');
  const bloc   = document.getElementById('rdl-preview-bloc');
  const btnRun = document.getElementById('rdl-btn-run');

  status.textContent = 'Comptage…';
  bloc.style.display = 'none';

  try {
    const r = await fetch('/api/admin/compilation-atomes/preview?' + qs);
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);

    bloc.style.display = 'grid';
    bloc.innerHTML = `
      <div class="card" style="padding:8px"><div style="color:var(--text-secondary)">Total éligibles</div><div style="font-size:18px;font-weight:600">${d.total}</div></div>
      <div class="card" style="padding:8px"><div style="color:var(--text-secondary)">Notions</div><div style="font-size:18px;font-weight:600">${d.par_type.notion}</div></div>
      <div class="card" style="padding:8px"><div style="color:var(--text-secondary)">Méthodes</div><div style="font-size:18px;font-weight:600">${d.par_type.methode}</div></div>
      <div class="card" style="padding:8px"><div style="color:var(--text-secondary)">Exercices</div><div style="font-size:18px;font-weight:600">${d.par_type.exercice}</div></div>
      <div class="card" style="padding:8px"><div style="color:var(--text-secondary)">Fiches</div><div style="font-size:18px;font-weight:600">${d.par_type.fiche || 0}</div></div>
      <div class="card" style="padding:8px"><div style="color:var(--text-secondary)">Cartes</div><div style="font-size:18px;font-weight:600">${d.par_type.carte || 0}</div></div>
    `;

    if (d.total === 0) {
      status.innerHTML = `<span style="color:var(--text-secondary)">Aucun atome ne correspond au filtre.</span>`;
      btnRun.disabled = true;
      COMPIL_PREVIEW_OK = false;
    } else {
      status.innerHTML = `<span style="color:var(--success)">✓ ${d.total} atomes éligibles.</span>`;
      btnRun.disabled = false;
      COMPIL_PREVIEW_OK = true;
      COMPIL_RUN_TOTAL = d.total;
    }
  } catch (e) {
    status.innerHTML = `<span style="color:var(--danger)">Erreur : ${_escHtml(e.message)}</span>`;
    btnRun.disabled = true;
    COMPIL_PREVIEW_OK = false;
  }
}

// Lance le run : ouvre un EventSource, ajoute une ligne par atome compilé.
function compilBatchRun() {
  if (!COMPIL_PREVIEW_OK) {
    alert('Faites d\'abord un aperçu pour compter les atomes.');
    return;
  }
  if (COMPIL_EVENTSOURCE) {
    alert('Un run est déjà en cours.');
    return;
  }
  const total = COMPIL_RUN_TOTAL;
  if (!confirm(
    `${total} atomes vont être compilés. ` +
    `Comptez quelques secondes par atome non encore en cache. Continuer ?`
  )) return;

  const p = _compilLireParams();
  const qs = new URLSearchParams({
    type: p.type, niveau: p.niveau, sequence: p.sequence,
    // v0.10 — Deux timeouts. Le backend les persiste tous deux dans
    // configuration.json, sous timeout_compilation_court_s et
    // timeout_compilation_long_s.
    timeout_court: p.timeout_court,
    timeout_long:  p.timeout_long,
    max_erreurs: p.max_erreurs,
    tikz_libraries: p.tikz_libraries,
    tblr_libraries: p.tblr_libraries,
  });

  // Reset UI
  const liste     = document.getElementById('rdl-liste');
  const status    = document.getElementById('rdl-status');
  const blocProg  = document.getElementById('rdl-progress-bloc');
  const blocRapp  = document.getElementById('rdl-rapport-bloc');
  const counts    = document.getElementById('rdl-progress-counts');
  const bar       = document.getElementById('rdl-progress-bar');
  const btnPrev   = document.getElementById('rdl-btn-preview');
  const btnRun    = document.getElementById('rdl-btn-run');
  const btnCanc   = document.getElementById('rdl-btn-cancel');

  liste.innerHTML = '';
  blocProg.style.display = '';
  blocRapp.style.display = 'none';
  status.textContent = 'Compilation en cours…';
  counts.textContent = `0 / ${total}`;
  bar.style.width = '0%';
  bar.style.background = 'var(--success)';
  btnPrev.disabled = true;
  btnRun.disabled  = true;
  btnCanc.style.display = '';

  // Compteurs locaux pour ne pas avoir à parcourir le DOM.
  const compteurs = {succes:0, cache:0, echec_vide:0,
                     echec_compilation:0, echec_infra:0};

  COMPIL_EVENTSOURCE = new EventSource(
    '/api/admin/compilation-atomes/run?' + qs);

  COMPIL_EVENTSOURCE.onmessage = (msg) => {
    let ev;
    try { ev = JSON.parse(msg.data); }
    catch (e) { console.error('SSE parse error', e, msg.data); return; }

    if (ev.kind === 'atome') {
      compteurs[ev.statut] = (compteurs[ev.statut] || 0) + 1;
      _compilAjouterLigne(ev);
      const traite = ev.index;
      counts.textContent = `${traite} / ${ev.total}`;
      const pct = ev.total > 0 ? (100 * traite / ev.total) : 0;
      bar.style.width = pct.toFixed(1) + '%';
    } else if (ev.kind === 'fin' || ev.kind === 'abandon' || ev.kind === 'annule') {
      _compilFinaliser(ev, compteurs);
      // IMPORTANT : EventSource se reconnecte automatiquement quand le serveur
      // ferme le stream. On doit donc fermer explicitement ici, sinon le run
      // redémarre tout seul en boucle. (Le serveur émet encore l'événement
      // 'rapport' juste après, mais celui-ci est petit et peut très bien
      // arriver avant qu'on ferme — sinon on le récupérera au run suivant via
      // le dossier rapports/. Pour ne pas le perdre, on attend un court délai.)
      setTimeout(() => _compilNettoyerEventSource(), 500);
    } else if (ev.kind === 'rapport') {
      // Lien de téléchargement du rapport.
      const lien = document.getElementById('rdl-rapport-link');
      lien.href        = ev.url;
      lien.textContent = 'Télécharger le rapport : ' + ev.nom;
      blocRapp.style.display = '';
      // Le rapport est le dernier événement émis par le serveur. On peut
      // fermer immédiatement, sans attendre les 500ms du setTimeout ci-dessus.
      _compilNettoyerEventSource();
    } else if (ev.kind === 'erreur_serveur') {
      status.innerHTML = `<span style="color:var(--danger)">Erreur serveur : ${_escHtml(ev.message)}</span>`;
    }
  };

  COMPIL_EVENTSOURCE.onerror = () => {
    // Ce handler se déclenche pour deux raisons :
    //   1. Vraie erreur réseau (serveur tombé, connexion coupée).
    //   2. Le serveur a fermé le stream et EventSource se prépare à se
    //      reconnecter. État readyState === CONNECTING dans ce cas.
    // Dans les deux cas, si on n'a pas reçu d'événement final (fin/abandon/
    // annule/rapport) qui aurait déjà fait le ménage, on coupe ici pour
    // empêcher la reconnexion automatique (qui relancerait le run).
    if (!COMPIL_EVENTSOURCE) return;
    _compilNettoyerEventSource();
    const status = document.getElementById('rdl-status');
    if (status && !status.textContent.match(/Terminé|Annulé|Abandon/)) {
      status.innerHTML = `<span style="color:var(--danger)">Connexion interrompue.</span>`;
    }
    document.getElementById('rdl-btn-preview').disabled = false;
    document.getElementById('rdl-btn-run').disabled     = !COMPIL_PREVIEW_OK;
    document.getElementById('rdl-btn-cancel').style.display = 'none';
  };
}

// Annulation : ferme le stream côté client. Le serveur écrit le rapport
// partiel sur GeneratorExit.
function compilBatchAnnuler() {
  if (!COMPIL_EVENTSOURCE) return;
  if (!confirm('Interrompre la compilation ?')) return;
  _compilNettoyerEventSource();
  const status = document.getElementById('rdl-status');
  status.innerHTML = `<span style="color:var(--text-secondary)">Annulé.</span>`;
  document.getElementById('rdl-btn-preview').disabled = false;
  document.getElementById('rdl-btn-run').disabled     = !COMPIL_PREVIEW_OK;
  document.getElementById('rdl-btn-cancel').style.display = 'none';
}

function _compilNettoyerEventSource() {
  if (COMPIL_EVENTSOURCE) {
    try { COMPIL_EVENTSOURCE.close(); } catch (e) {}
    COMPIL_EVENTSOURCE = null;
  }
}

// Couleurs et libellés des statuts (identiques à ce qu'on affiche en MD côté
// serveur, pour cohérence visuelle).
const _COMPIL_STATUTS = {
  succes:            {label: 'OK',         color: 'var(--success)',          bg: 'transparent'},
  cache:             {label: 'cache',      color: 'var(--text-secondary)',   bg: 'transparent'},
  echec_vide:        {label: 'vide',       color: '#b58900',                 bg: 'rgba(181,137,0,0.08)'},
  echec_compilation: {label: 'LaTeX',      color: 'var(--danger)',           bg: 'rgba(220,50,47,0.08)'},
  echec_infra:       {label: 'infra',      color: 'var(--danger)',           bg: 'rgba(220,50,47,0.16)'},
};

// Ajoute une ligne en HAUT de la liste (ordre antichronologique : on voit
// toujours ce qui vient d'être traité). On limite la liste à 2000 lignes
// pour éviter de saturer le DOM dans un run massif (1124 atomes total
// aujourd'hui, 2000 laisse de la marge si on scale au-dessus).
function _compilAjouterLigne(ev) {
  const liste = document.getElementById('rdl-liste');
  const stat = _COMPIL_STATUTS[ev.statut] || {label: ev.statut, color: 'inherit', bg: 'transparent'};

  // Le placeholder « Aucun atome traité » est viré au premier ajout.
  if (liste.childElementCount === 1 && liste.firstElementChild.tagName === 'DIV'
      && liste.firstElementChild.style.fontStyle === 'italic') {
    liste.innerHTML = '';
  }

  const dureeS = ev.duree_ms ? (ev.duree_ms / 1000).toFixed(1) + 's' : '';
  const message = ev.message ? ` — <span style="color:var(--text-secondary)">${_escHtml(ev.message)}</span>` : '';
  const titre   = ev.titre ? ` <span style="color:var(--text-secondary)">— ${_escHtml(ev.titre.slice(0, 80))}</span>` : '';

  // v0.18.2 — clic simple = ouvrir en place ; Ctrl/⌘+clic ou clic-molette =
  // nouvel onglet (deeplink). niveau/sequence viennent de l'event backend.
  const ligne = document.createElement('div');
  ligne.style.cssText =
    'padding:3px 6px;border-bottom:1px solid var(--border);' +
    'cursor:pointer;display:flex;align-items:center;gap:8px;' +
    'background:' + stat.bg;
  ligne.onmouseenter = () => { ligne.style.background = 'var(--surface)'; };
  ligne.onmouseleave = () => { ligne.style.background = stat.bg; };
  ligne.onclick = (event) => {
    const url = deeplinkAtomeURL(ev.type, ev.id, ev.niveau, ev.sequence);
    if (url && event && (event.ctrlKey || event.metaKey || event.shiftKey)) {
      window.open(url, '_blank', 'noopener');
      return;
    }
    compilBatchOuvrirAtelier(ev.type, ev.id, ev.niveau, ev.sequence);
  };
  // Clic-molette (bouton du milieu) : nouvel onglet aussi.
  ligne.onauxclick = (event) => {
    if (event && event.button === 1) {
      const url = deeplinkAtomeURL(ev.type, ev.id, ev.niveau, ev.sequence);
      if (url) { event.preventDefault(); window.open(url, '_blank', 'noopener'); }
    }
  };
  ligne.innerHTML =
    `<span style="color:var(--text-muted);min-width:55px">${ev.index}/${ev.total}</span>` +
    `<span style="color:${stat.color};min-width:60px;font-weight:500">${stat.label}</span>` +
    `<span style="min-width:24px;color:var(--text-muted)">${ev.type[0].toUpperCase()}</span>` +
    `<span style="min-width:140px">${_escHtml(ev.identifiant)}</span>` +
    `<span style="min-width:50px;color:var(--text-muted);text-align:right">${dureeS}</span>` +
    `<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${titre}${message}</span>`;

  liste.insertBefore(ligne, liste.firstChild);

  // Cap pour ne pas saturer le DOM.
  while (liste.childElementCount > 2000) {
    liste.removeChild(liste.lastChild);
  }
}

// Finalisation : événement {kind: fin|abandon|annule} reçu.
function _compilFinaliser(ev, compteurs) {
  const status = document.getElementById('rdl-status');
  const bar    = document.getElementById('rdl-progress-bar');
  const btnPr  = document.getElementById('rdl-btn-preview');
  const btnRn  = document.getElementById('rdl-btn-run');
  const btnCn  = document.getElementById('rdl-btn-cancel');
  const counts = document.getElementById('rdl-progress-counts');

  btnPr.disabled = false;
  btnRn.disabled = !COMPIL_PREVIEW_OK;
  btnCn.style.display = 'none';

  const c = ev.compteurs || compteurs;
  const dureeS = ((ev.duree_totale_ms || 0) / 1000).toFixed(1);
  counts.textContent = `${ev.traite || 0} / ${ev.total || 0}`;

  // Recap textuel.
  const recap =
    `Succès ${c.succes||0} · ` +
    `Cache ${c.cache||0} · ` +
    `Vides ${c.echec_vide||0} · ` +
    `LaTeX ${c.echec_compilation||0} · ` +
    `Infra ${c.echec_infra||0} · ` +
    `${dureeS}s`;

  if (ev.kind === 'fin') {
    const echecs = (c.echec_vide||0) + (c.echec_compilation||0) + (c.echec_infra||0);
    if (echecs > 0) {
      status.innerHTML = `<span style="color:#b58900">⚠ Terminé avec ${echecs} échec${echecs>1?'s':''}.</span> ${recap}`;
      bar.style.background = '#b58900';
    } else {
      status.innerHTML = `<span style="color:var(--success)">✓ Terminé.</span> ${recap}`;
    }
  } else if (ev.kind === 'abandon') {
    status.innerHTML = `<span style="color:var(--danger)">✗ Abandon : ${_escHtml(ev.message || '')}</span> ${recap}`;
    bar.style.background = 'var(--danger)';
  } else if (ev.kind === 'annule') {
    status.innerHTML = `<span style="color:var(--text-secondary)">Annulé.</span> ${recap}`;
    bar.style.background = 'var(--text-secondary)';
  }
}

// Ouvre l'atelier d'un atome : bascule sur l'onglet Ateliers, active le bon
// sous-onglet, puis charge l'atome dans le formulaire.
//
// v0.18.1 — Généralisé aux CINQ types (notion, methode, exercice, fiche,
// carte) pour servir à la fois le Rendu par lot et l'outil Recherche.
// Au lieu des anciennes globales/fonctions hétérogènes, on s'appuie sur les
// objets OO ATELIER_* (tous héritent d'AtelierEditeur : chargerListe() +
// ouvrirItem(id) + propriété `liste`). C'est uniforme et robuste : fiche et
// carte n'étaient pas chargées par initAteliers(), on déclenche donc
// explicitement leur chargerListe().
//
// On n'utilise PAS btnTab.click() : le handler attaché à .tab fait
// `sousOnglet('suivi')` quand on quitte un onglet qui n'est pas 'classe',
// ce qui réinitialise un sous-onglet sans rapport. On reproduit donc
// manuellement uniquement ce qui nous concerne : afficher le panneau
// Ateliers et appeler initAteliers() qui charge les listes cours.
//
// ════════════════════════════════════════════════════════════════════════════
// v0.18.2 — Ouverture d'un atome dans un nouvel onglet (Ctrl/⌘+clic)
//
// Mécanisme unique : un deeplink URL `/?atelier=...&niveau=...&seq=...&atome=...`
// ouvert dans un onglet (cf. _appliquerDeeplink au démarrage). Réutilisé par :
// la Recherche, le Rendu par lot, l'atelier seqniv et l'atelier évaluation.
//
// Convention d'ouverture (D2) : chaque cible ouvrable est un <a href={deeplink}>
//   - clic simple        -> intercepté (preventDefault) + ouverture EN PLACE ;
//   - Ctrl/⌘+clic, molette -> laissé au navigateur => nouvel onglet natif.
//
// Le « type » accepté est soit le type court (notion/methode/exercice/fiche/
// carte), soit directement le nom d'atelier (carte_automatisme). On normalise.

// type court -> nom d'atelier (pour l'URL ?atelier=...). Les noms d'atelier
// déjà corrects (incl. 'carte_automatisme') passent inchangés.
function _nomAtelierPourDeeplink(type) {
  if (type === 'carte') return 'carte_automatisme';
  return type;  // notion, methode, exercice, fiche, carte_automatisme
}

// type court depuis n'importe quelle forme (pour compilBatchOuvrirAtelier,
// qui attend le type COURT, donc 'carte' et non 'carte_automatisme').
function _typeCourtAtome(type) {
  if (type === 'carte_automatisme') return 'carte';
  return type;
}

// Construit l'URL deeplink, ou null si niveau/séquence manquent (l'ouverture
// directe exige le couple niveau+séquence).
function deeplinkAtomeURL(type, id, niveau, sequence) {
  if (!id || !niveau || !sequence) return null;
  const atelier = _nomAtelierPourDeeplink(type);
  return '/?atelier=' + encodeURIComponent(atelier)
       + '&niveau=' + encodeURIComponent(niveau)
       + '&seq=' + encodeURIComponent(sequence)
       + '&atome=' + encodeURIComponent(id);
}

// Handler de clic sur un <a> d'atome. Retourne true si on laisse le navigateur
// agir (nouvel onglet), false si on a ouvert en place (clic simple).
// À câbler en inline : onclick="return ouvrirAtomeDepuisEvent(event,'notion','id','N10','S01')".
function ouvrirAtomeDepuisEvent(event, type, id, niveau, sequence) {
  // Ctrl (Win/Linux), ⌘ (Mac), Shift, ou clic-molette (auxclick button 1) :
  // laisser le comportement natif du lien (nouvel onglet / fenêtre).
  if (event && (event.ctrlKey || event.metaKey || event.shiftKey || event.button === 1)) {
    return true;  // ne pas preventDefault : le navigateur ouvre l'onglet
  }
  // Clic simple : ouverture en place.
  if (event && typeof event.preventDefault === 'function') event.preventDefault();
  if (typeof compilBatchOuvrirAtelier === 'function') {
    compilBatchOuvrirAtelier(_typeCourtAtome(type), id, niveau, sequence);
  }
  return false;
}

// Construit le HTML d'un lien <a> ouvrant un atome (helper de rendu partagé).
// `contenu` est le HTML interne déjà échappé ; `attrsSup` des attributs en plus
// (style, class, title…). Si niveau/seq manquent, renvoie un <span> inerte.
function lienAtomeHTML(type, id, niveau, sequence, contenu, attrsSup) {
  const url = deeplinkAtomeURL(type, id, niveau, sequence);
  const sup = attrsSup || '';
  if (!url) {
    return `<span ${sup}>${contenu}</span>`;
  }
  // escAttrJs protège l'apostrophe dans les arguments inline.
  const onclick = `return ouvrirAtomeDepuisEvent(event,`
    + `'${escAttrJs(type)}','${escAttrJs(id)}',`
    + `'${escAttrJs(niveau)}','${escAttrJs(sequence)}')`;
  return `<a href="${url}" target="_blank" rel="noopener" `
       + `onclick="${onclick}" ${sup}>${contenu}</a>`;
}

// Mapping type -> (sous-onglet atelSwitch, objet OO ATELIER_*).
const _OUVRIR_ATELIER_MAPPING = {
  notion:   {sw: 'notion',            oo: 'ATELIER_NOTION'},
  methode:  {sw: 'methode',           oo: 'ATELIER_METHODE'},
  exercice: {sw: 'exercice',          oo: 'ATELIER_EXERCICE'},
  fiche:    {sw: 'fiche',             oo: 'ATELIER_FICHE'},
  carte:    {sw: 'carte_automatisme', oo: 'ATELIER_CARTE'},
};

function compilBatchOuvrirAtelier(type, id, niveau, sequence) {
  // 1. Bascule manuelle vers l'onglet Ateliers, sans simuler un clic.
  document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
  const btnTab = document.querySelector('.tab[data-tab="ateliers"]');
  const panneau = document.getElementById('tab-ateliers');
  if (!btnTab || !panneau) {
    alert('Onglet Ateliers introuvable.');
    return;
  }
  btnTab.classList.add('active');
  panneau.style.display = '';

  const m = _OUVRIR_ATELIER_MAPPING[type];
  if (!m) {
    console.warn(`compilBatchOuvrirAtelier : type inconnu ${type}`);
    return;
  }

  // v0.18.1 — Si on connaît le niveau/séquence de l'atome (cas de l'outil
  // Recherche, transversal), on positionne le filtre de la portée Séquence
  // AVANT de charger les listes : chargerListe() des ateliers OO ne charge
  // que le niveau/séquence courant (l'API exige le couple). Sans ça, un
  // atome trouvé hors du contexte de filtre courant resterait introuvable.
  if (niveau && sequence) {
    ATL_PORTEE_ACTIVE = 'sequence';
    localStorage.setItem('atl-portee-active', 'sequence');
    ATL_SELECTIONS.sequence = { niveau: niveau, sequence: sequence };
    atelSauverSelections('sequence', ATL_SELECTIONS.sequence);
    // Boutons de portée + visibilité des groupes d'ateliers.
    Object.keys(ATL_PORTEES).forEach(p => {
      const btn = document.getElementById('atl-btn-portee-' + p);
      if (btn) btn.classList.toggle('active', p === 'sequence');
      document.querySelectorAll('.atl-grp-' + p).forEach(b => {
        b.style.display = p === 'sequence' ? '' : 'none';
      });
    });
    atelRenderSelecteursPortee();
    atelAppliquerSelectionsPortee();  // pose ATL_FILTRE_NIVEAU/SEQ + recharge
  }

  // initAteliers() est idempotent (recharge les listes cours + filtres).
  if (typeof initAteliers === 'function') initAteliers();

  const atelier = window[m.oo];
  if (!atelier) {
    console.warn(`compilBatchOuvrirAtelier : objet ${m.oo} absent`);
    return;
  }

  // 2. S'assurer que la liste de cet atelier est chargée. initAteliers ne
  //    charge que notion/methode/exercice : pour fiche/carte on déclenche
  //    explicitement chargerListe(). Idempotent dans tous les cas.
  try {
    const p = atelier.chargerListe && atelier.chargerListe();
    void p;
  } catch (e) { /* on retombe sur la boucle d'attente */ }

  // 3. Bascule sur le sous-onglet puis attente que l'item soit présent dans
  //    atelier.liste (chargement async, ~1s sur la base réelle). On essaie
  //    pendant 5s avant d'abandonner.
  let essais = 0;
  const max = 50;  // 50 × 100ms = 5s
  const tenter = () => {
    essais++;
    if (typeof atelSwitch === 'function') atelSwitch(m.sw);
    const liste = atelier.liste;
    const trouve = liste && liste.find && liste.find(x => x.id === id);
    if (trouve) {
      atelier.ouvrirItem(id);
      return;
    }
    if (essais < max) {
      setTimeout(tenter, 100);
    } else {
      console.warn(`Atome ${type}/${id} introuvable dans ${m.oo}.liste après ${max*100}ms.`);
      try { atelier.ouvrirItem(id); } catch(e) {}
    }
  };
  setTimeout(tenter, 50);
}


// ── v0.10.4.2 — Wrappers globaux pour le bouton "Valider/Repasser en cours"
//
// Pourquoi ces wrappers ?
//   Les `let ATL_EXERCICE_ACTIF` et consorts sont déclarés en `let` au top-level
//   de ce fichier. Contrairement à `var`, `let` top-level ne crée PAS de
//   propriété sur `window`. Les attributs HTML `onclick="…"` sont évalués
//   dans le scope global (~window), donc `onclick="fn(ATL_EXERCICE_ACTIF)"`
//   provoque ReferenceError silencieux au clic.
//
//   Solution : wrapper qui lit la `let` depuis son scope lexical (ce
//   fichier) et l'expose via une fonction sur window. Pas de duplication
//   d'état, pas de migration `let` → `var` risquée.

window.atelExerciceBasculerValidationCb = function () {
  if (typeof window.atelAtomeBasculerValidation === 'function') {
    window.atelAtomeBasculerValidation('exercice', ATL_EXERCICE_ACTIF, ATL_EXO);
  }
};

window.atelNotionBasculerValidationCb = function () {
  if (typeof window.atelAtomeBasculerValidation === 'function') {
    window.atelAtomeBasculerValidation('notion', ATL_NOTION_ACTIF, ATL_NOTIONS);
  }
};

window.atelMethodeBasculerValidationCb = function () {
  if (typeof window.atelAtomeBasculerValidation === 'function') {
    window.atelAtomeBasculerValidation('methode', ATL_METHODE_ACTIF, ATL_METHODES);
  }
};


// ════════════════════════════════════════════════════════════════════════════
// v0.10.5.2 — Préférences : section « Titres de zone fiche »
// ════════════════════════════════════════════════════════════════════════════
//
// Gère la liste paramétrable des titres de zone proposés dans l'atelier
// Fiche de résumé. CRUD via /api/preferences/titre_zone_fiche.
//
// La liste est rendue dans le DOM avec, pour chaque ligne :
//   - le libellé éditable inline (input type=text)
//   - boutons monter/descendre (réordonner via PUT /ordre)
//   - bouton supprimer
//
// Au chargement de l'onglet Préférences (déclenché par le code de
// navigation existant), on appelle prefTitresZoneCharger() pour peupler
// la liste. Pas de bouton "Enregistrer" global : chaque action
// (ajout, renommage, suppression, déplacement) est persistée
// immédiatement.

let _PREF_TITRES_ZONE = [];  // cache local de la liste

async function prefTitresZoneCharger() {
  try {
    const r = await api('/api/preferences/titre_zone_fiche');
    _PREF_TITRES_ZONE = (r && r.items) || [];
  } catch (e) {
    _PREF_TITRES_ZONE = [];
  }
  prefTitresZoneRender();
  // Invalider le cache côté atelier Fiche pour qu'il rerelise les
  // titres au prochain ouvre/render.
  if (typeof window.atelFicheInvaliderCacheTitres === 'function') {
    window.atelFicheInvaliderCacheTitres();
  }
}

function prefTitresZoneRender() {
  const cont = document.getElementById('pref-titres-zone-list');
  if (!cont) return;
  if (_PREF_TITRES_ZONE.length === 0) {
    cont.innerHTML = '<div style="font-size:12px;color:var(--text-muted);' +
                     'padding:10px;text-align:center;border:1px dashed var(--border);' +
                     'border-radius:4px">Aucun titre. Ajoutez-en un ci-dessous.</div>';
    return;
  }
  cont.innerHTML = _PREF_TITRES_ZONE.map((it, i) => {
    const peutMonter = i > 0;
    const peutDescendre = i < _PREF_TITRES_ZONE.length - 1;
    const _esc = s => String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
    return `
      <div style="display:flex;align-items:center;gap:6px;padding:5px 0;
                  border-bottom:1px solid var(--border)">
        <span style="font-size:11px;color:var(--text-muted);width:20px">${i + 1}.</span>
        <input type="text" value="${_esc(it.valeur)}"
               data-id="${_esc(it.id)}"
               onblur="prefTitresZoneRenommer('${_esc(it.id)}', this)"
               onkeydown="if (event.key==='Enter') this.blur();"
               style="flex:1;font-size:13px">
        <button class="btn-sm" onclick="prefTitresZoneDeplacer('${_esc(it.id)}', -1)"
                ${peutMonter ? '' : 'disabled'} title="Monter" aria-label="Monter">↑</button>
        <button class="btn-sm" onclick="prefTitresZoneDeplacer('${_esc(it.id)}', 1)"
                ${peutDescendre ? '' : 'disabled'} title="Descendre" aria-label="Descendre">↓</button>
        <button class="btn-sm" style="color:var(--danger)"
                onclick="prefTitresZoneSupprimer('${_esc(it.id)}', '${_esc(it.valeur)}')"
                title="Supprimer" aria-label="Supprimer">×</button>
      </div>`;
  }).join('');
}

async function prefTitresZoneAjouter() {
  const input = document.getElementById('pref-titres-zone-nouveau');
  const status = document.getElementById('pref-titres-zone-status');
  const valeur = (input.value || '').trim();
  if (!valeur) {
    status.textContent = 'Saisir un titre.';
    return;
  }
  try {
    const r = await fetch('/api/preferences/titre_zone_fiche', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({valeur}),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
    input.value = '';
    status.textContent = 'Ajouté.';
    await prefTitresZoneCharger();
  } catch (e) {
    status.textContent = `Erreur : ${e.message}`;
  }
}

async function prefTitresZoneRenommer(itemId, inputEl) {
  const valeur = (inputEl.value || '').trim();
  const status = document.getElementById('pref-titres-zone-status');
  // Si la valeur n'a pas changé, on ne fait rien
  const item = _PREF_TITRES_ZONE.find(x => x.id === itemId);
  if (item && item.valeur === valeur) return;
  try {
    const r = await fetch(`/api/preferences/items/${encodeURIComponent(itemId)}`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({valeur}),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
    status.textContent = 'Modifié.';
    await prefTitresZoneCharger();
  } catch (e) {
    status.textContent = `Erreur : ${e.message}`;
    // restore old value
    if (item) inputEl.value = item.valeur;
  }
}

async function prefTitresZoneSupprimer(itemId, valeur) {
  if (!confirm(`Supprimer "${valeur}" de la liste des titres ?\n\n` +
               `Les fiches existantes utilisant ce titre conserveront leur valeur.`)) {
    return;
  }
  const status = document.getElementById('pref-titres-zone-status');
  try {
    const r = await fetch(`/api/preferences/items/${encodeURIComponent(itemId)}`, {
      method: 'DELETE',
    });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      throw new Error(d.error || `HTTP ${r.status}`);
    }
    status.textContent = 'Supprimé.';
    await prefTitresZoneCharger();
  } catch (e) {
    status.textContent = `Erreur : ${e.message}`;
  }
}

async function prefTitresZoneDeplacer(itemId, delta) {
  const status = document.getElementById('pref-titres-zone-status');
  const idx = _PREF_TITRES_ZONE.findIndex(x => x.id === itemId);
  if (idx < 0) return;
  const newIdx = idx + delta;
  if (newIdx < 0 || newIdx >= _PREF_TITRES_ZONE.length) return;
  // Permuter localement
  const ids = _PREF_TITRES_ZONE.map(x => x.id);
  [ids[idx], ids[newIdx]] = [ids[newIdx], ids[idx]];
  try {
    const r = await fetch('/api/preferences/titre_zone_fiche/ordre', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ids}),
    });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      throw new Error(d.error || `HTTP ${r.status}`);
    }
    await prefTitresZoneCharger();
  } catch (e) {
    status.textContent = `Erreur : ${e.message}`;
  }
}

// ────────────────────────────────────────────────────────────────────────────
// v0.19.1.15 — Types de mise en route (progression à la séance)
// CRUD via /api/preferences/type_mise_en_route. La `valeur` de chaque item est
// un JSON {libelle, couleur}. Liste globale (tous niveaux).
// ────────────────────────────────────────────────────────────────────────────
let _PREF_MER = [];

function _merParse(valeur) {
  // Retourne {libelle, couleur} depuis la valeur brute (JSON ou texte simple).
  try {
    const o = JSON.parse(valeur);
    if (o && typeof o === 'object') {
      return { libelle: o.libelle || '', couleur: o.couleur || '#4a90d9' };
    }
  } catch (e) { /* valeur legacy = libellé simple */ }
  return { libelle: valeur || '', couleur: '#4a90d9' };
}

async function prefMerCharger() {
  try {
    const r = await api('/api/preferences/type_mise_en_route');
    _PREF_MER = (r && r.items) || [];
  } catch (e) {
    _PREF_MER = [];
  }
  prefMerRender();
}

function prefMerRender() {
  const cont = document.getElementById('pref-mer-list');
  if (!cont) return;
  if (_PREF_MER.length === 0) {
    cont.innerHTML = '<div style="font-size:12px;color:var(--text-muted);' +
      'padding:10px;text-align:center;border:1px dashed var(--border);' +
      'border-radius:4px">Aucun type. Ajoutez-en un ci-dessous.</div>';
    return;
  }
  const _esc = s => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
  cont.innerHTML = _PREF_MER.map((it, i) => {
    const d = _merParse(it.valeur);
    const peutMonter = i > 0;
    const peutDescendre = i < _PREF_MER.length - 1;
    return `
      <div style="display:flex;align-items:center;gap:6px;padding:5px 0;
                  border-bottom:1px solid var(--border)">
        <span style="font-size:11px;color:var(--text-muted);width:20px">${i + 1}.</span>
        <input type="color" value="${_esc(d.couleur)}"
               onchange="prefMerMaj('${_esc(it.id)}', this.closest('div'))"
               data-role="couleur"
               style="width:34px;height:30px;padding:2px" title="Couleur">
        <input type="text" value="${_esc(d.libelle)}"
               data-role="libelle"
               onblur="prefMerMaj('${_esc(it.id)}', this.closest('div'))"
               onkeydown="if (event.key==='Enter') this.blur();"
               style="flex:1;font-size:13px">
        <button class="btn-sm" onclick="prefMerDeplacer('${_esc(it.id)}', -1)"
                ${peutMonter ? '' : 'disabled'} title="Monter" aria-label="Monter">↑</button>
        <button class="btn-sm" onclick="prefMerDeplacer('${_esc(it.id)}', 1)"
                ${peutDescendre ? '' : 'disabled'} title="Descendre" aria-label="Descendre">↓</button>
        <button class="btn-sm" style="color:var(--danger)"
                onclick="prefMerSupprimer('${_esc(it.id)}', '${_esc(d.libelle)}')"
                title="Supprimer" aria-label="Supprimer">×</button>
      </div>`;
  }).join('');
}

async function prefMerAjouter() {
  const input = document.getElementById('pref-mer-nouveau');
  const couleurEl = document.getElementById('pref-mer-couleur');
  const status = document.getElementById('pref-mer-status');
  const libelle = (input.value || '').trim();
  if (!libelle) { status.textContent = 'Saisir un libellé.'; return; }
  const valeur = JSON.stringify({ libelle, couleur: couleurEl.value || '#4a90d9' });
  try {
    const r = await fetch('/api/preferences/type_mise_en_route', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ valeur }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
    input.value = '';
    status.textContent = 'Ajouté.';
    await prefMerCharger();
  } catch (e) {
    status.textContent = `Erreur : ${e.message}`;
  }
}

async function prefMerMaj(itemId, rowEl) {
  const status = document.getElementById('pref-mer-status');
  const libelle = (rowEl.querySelector('[data-role=libelle]').value || '').trim();
  const couleur = rowEl.querySelector('[data-role=couleur]').value || '#4a90d9';
  if (!libelle) { status.textContent = 'Le libellé ne peut pas être vide.'; return; }
  const valeur = JSON.stringify({ libelle, couleur });
  try {
    const r = await fetch(`/api/preferences/items/${encodeURIComponent(itemId)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ valeur }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
    status.textContent = 'Modifié.';
    await prefMerCharger();
  } catch (e) {
    status.textContent = `Erreur : ${e.message}`;
  }
}

async function prefMerSupprimer(itemId, libelle) {
  if (!confirm(`Supprimer le type « ${libelle} » ?`)) return;
  const status = document.getElementById('pref-mer-status');
  try {
    const r = await fetch(`/api/preferences/items/${encodeURIComponent(itemId)}`, {
      method: 'DELETE',
    });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      throw new Error(d.error || `HTTP ${r.status}`);
    }
    status.textContent = 'Supprimé.';
    await prefMerCharger();
  } catch (e) {
    status.textContent = `Erreur : ${e.message}`;
  }
}

async function prefMerDeplacer(itemId, delta) {
  const status = document.getElementById('pref-mer-status');
  const idx = _PREF_MER.findIndex(x => x.id === itemId);
  if (idx < 0) return;
  const newIdx = idx + delta;
  if (newIdx < 0 || newIdx >= _PREF_MER.length) return;
  const ids = _PREF_MER.map(x => x.id);
  [ids[idx], ids[newIdx]] = [ids[newIdx], ids[idx]];
  try {
    const r = await fetch('/api/preferences/type_mise_en_route/ordre', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids }),
    });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      throw new Error(d.error || `HTTP ${r.status}`);
    }
    await prefMerCharger();
  } catch (e) {
    status.textContent = `Erreur : ${e.message}`;
  }
}

// Patch : à l'ouverture du panneau Préférences, charger la liste.
// On hooke prefAfficher s'il existe, sinon on hooke le bouton de
// changement d'onglet via une délégation.
(function () {
  // Méthode robuste : surveiller le changement d'affichage de
  // tab-preferences via MutationObserver. Léger, pas de réentrance.
  document.addEventListener('DOMContentLoaded', function () {
    const tab = document.getElementById('tab-preferences');
    if (!tab) return;
    let lastDisplay = tab.style.display;
    const observer = new MutationObserver(function () {
      const cur = tab.style.display;
      if (cur !== 'none' && lastDisplay === 'none') {
        prefTitresZoneCharger();
        prefMerCharger();
      }
      lastDisplay = cur;
    });
    observer.observe(tab, {attributes: true, attributeFilter: ['style']});
    // Si l'onglet est déjà visible au chargement (peu probable mais bon)
    if (tab.style.display !== 'none') {
      prefTitresZoneCharger();
      prefMerCharger();
    }
  });
})();


// ════════════════════════════════════════════════════════════════════════════
// v0.10.5.2 — Admin : Import des fiches de résumé depuis fichier .tex
// ════════════════════════════════════════════════════════════════════════════

function adminImportFichesInit() {
  // Réinitialiser l'état d'affichage à chaque ouverture du sous-onglet.
  const status = document.getElementById('admin-importfiches-status');
  const rapport = document.getElementById('admin-importfiches-rapport');
  if (status)  status.textContent = '';
  if (rapport) rapport.style.display = 'none';
}

async function adminImportFichesLancer() {
  const niveau = document.getElementById('admin-importfiches-niveau').value;
  const input  = document.getElementById('admin-importfiches-fichier');
  const status = document.getElementById('admin-importfiches-status');
  const btn    = document.getElementById('admin-importfiches-btn-go');
  const rapport = document.getElementById('admin-importfiches-rapport');
  const rapContenu = document.getElementById('admin-importfiches-rapport-contenu');

  if (!input.files || input.files.length === 0) {
    status.textContent = 'Sélectionner un fichier .tex.';
    return;
  }
  const fichier = input.files[0];

  btn.disabled = true;
  status.textContent = 'Import en cours…';
  rapport.style.display = 'none';

  try {
    const fd = new FormData();
    fd.append('fichier', fichier);
    fd.append('niveau', niveau);
    const r = await fetch('/api/admin/fiches/import', {method: 'POST', body: fd});
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);

    const rap = d.rapport || {};
    status.innerHTML = `<span style="color:var(--success)">✓ Import terminé.</span>`;
    const lignes = [];
    lignes.push(`<div><strong>Fichier :</strong> ${_esc(d.fichier || fichier.name)}</div>`);
    lignes.push(`<div><strong>Niveau :</strong> ${_esc(d.niveau || niveau)}</div>`);
    lignes.push(`<div style="margin-top:8px"><strong>Fiches créées :</strong> ${rap.fiches_creees || 0}</div>`);
    lignes.push(`<div><strong>Fiches étendues :</strong> ${rap.fiches_etendues || 0} <span style="color:var(--text-muted)">(zones ajoutées en fin sans toucher l'existant)</span></div>`);
    lignes.push(`<div><strong>Total zones ajoutées :</strong> ${rap.zones_ajoutees || 0}</div>`);
    if ((rap.objectifs_introuvables || []).length > 0) {
      lignes.push(`<div style="margin-top:10px;color:var(--warning)"><strong>Objectifs introuvables (fiches ignorées) :</strong></div>`);
      lignes.push('<ul style="margin:4px 0 0 18px;font-family:monospace;font-size:11px">' +
        (rap.objectifs_introuvables || []).map(c => `<li>${_esc(c)}</li>`).join('') +
        '</ul>');
    }
    if ((rap.erreurs || []).length > 0 && (rap.objectifs_introuvables || []).length === 0) {
      // Si on a des erreurs autres que objectifs_introuvables, on les affiche aussi
      lignes.push(`<div style="margin-top:10px;color:var(--danger)"><strong>Erreurs :</strong></div>`);
      lignes.push('<ul style="margin:4px 0 0 18px;font-size:11px">' +
        (rap.erreurs || []).map(e => `<li>${_esc(e)}</li>`).join('') +
        '</ul>');
    }
    rapContenu.innerHTML = lignes.join('');
    rapport.style.display = '';
  } catch (e) {
    status.innerHTML = `<span style="color:var(--danger)">Erreur : ${_esc(e.message)}</span>`;
  } finally {
    btn.disabled = false;
  }
}

// Petit utilitaire d'échappement local (réutilisable via un global au cas où
// une autre version n'existerait pas).
function _esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}


// ════════════════════════════════════════════════════════════════════════════
// v0.13.7.0c — La garde de sortie a été refondue dans atelier_garde.js
// (registre window.ATELIER_REGISTRE alimenté à l'instanciation des classes
// OO + modale 3 boutons unifiée). Le bloc historique d'enregistrement de
// handlers (atelGardeEnregistrerHandler + écoute DOM via _brancher) a été
// retiré ici car il branchait l'ancien pipeline snapshot qui ne fonctionnait
// plus depuis la migration OO.
// ════════════════════════════════════════════════════════════════════════════
