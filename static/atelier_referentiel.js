/* static/atelier_referentiel.js — v0.13.5.1
 *
 * Atelier Référentiel (portée Niveau).
 * Permet de créer, supprimer et figer des référentiels millésimés, et
 * d'afficher en arbre l'état d'avancement des atomes du niveau pour les
 * référentiels en phase coquille (en_cours / valide).
 *
 * Cycle de vie (cf. doc/scoping_v0_13_5_referentiels.md) :
 *   en_cours → valide → fige → verrouille
 *                       │
 *                       └─ annule (concurrents écartés au figeage)
 *
 * Périmètre v0.13.5.1 :
 *   - Création de coquille (POST /api/referentiels/coquille).
 *   - Suppression d'une coquille en_cours (DELETE /api/referentiels/<id>).
 *   - Figer minimal (POST /api/referentiels/<id>/figer) : transition d'état
 *     uniquement, pas de compilation PDF (→ v0.13.5.3).
 *   - Affichage de l'arbre du niveau (GET /api/referentiels/<id>/arbre).
 *   - Affichage en lecture seule pour fige/verrouille/annule.
 */

// ── État local ───────────────────────────────────────────────────────────────

// Liste des référentiels du niveau courant.
let ATL_REF_LISTE = [];
// Référentiel sélectionné dans la sidebar (ou null).
let ATL_REF_SELECTION = null;
// Cache de l'arbre du niveau pour le ref sélectionné (peut être absent
// pour fige/verrouille/annule, qui n'ont pas vocation à afficher l'arbre
// des tables actives).
let ATL_REF_ARBRE = null;
// v0.13.6.4 — Liste des documents publiables du référentiel sélectionné,
// cache de la dernière réponse de GET /api/referentiels/<id>/documents.
let ATL_REF_DOCUMENTS = [];
// v0.13.6.4 — Onglet actif dans la zone détail : 'dashboard' ou 'documents'.
// Toujours remis à 'dashboard' lors d'un changement de sélection.
let ATL_REF_ONGLET_ACTIF = 'dashboard';


// ── Init ─────────────────────────────────────────────────────────────────────

async function atelRefInit() {
  // Appelé par atelInvoquerInit() au switch sur l'onglet Référentiel.
  // Lit le filtre niveau actif et charge la liste.
  ATL_REF_SELECTION = null;
  ATL_REF_ARBRE = null;
  await atelRefRechargerListe();
  atelRefRendreSidebar();
  atelRefRendreDetail();
}

// Hook de changement de filtre de portée niveau : si l'atelier est visible,
// on recharge la liste. Branche dans atelAppliquerSelectionsPortee()
// (cf. app.js) qui appelle l'init de l'atelier visible.
window.atelRefInit = atelRefInit;


// ── Chargement des données ───────────────────────────────────────────────────

async function atelRefRechargerListe() {
  const niveau = (typeof ATL_FILTRE_NIVEAU !== 'undefined')
                   ? ATL_FILTRE_NIVEAU : '';
  if (!niveau) {
    ATL_REF_LISTE = [];
    return;
  }
  try {
    const data = await api(`/api/referentiels?niveau=${encodeURIComponent(niveau)}`);
    ATL_REF_LISTE = data.referentiels || [];
  } catch (e) {
    console.error('Échec chargement référentiels :', e);
    ATL_REF_LISTE = [];
  }
}

async function atelRefChargerArbre(refId) {
  try {
    const data = await api(`/api/referentiels/${encodeURIComponent(refId)}/arbre`);
    ATL_REF_ARBRE = data.arbre;
    return data;
  } catch (e) {
    console.error('Échec chargement arbre :', e);
    ATL_REF_ARBRE = null;
    return null;
  }
}


// ── Rendu — Sidebar ──────────────────────────────────────────────────────────

function atelRefRendreSidebar() {
  const cont = document.getElementById('atl-ref-liste');
  if (!cont) return;
  const niveau = (typeof ATL_FILTRE_NIVEAU !== 'undefined')
                   ? ATL_FILTRE_NIVEAU : '';
  if (!niveau) {
    cont.innerHTML = `
      <div style="padding:14px;font-size:12px;color:var(--text-muted)">
        Sélectionnez un niveau pour voir ses référentiels.
      </div>`;
    const btn = document.getElementById('atl-ref-btn-creer');
    if (btn) btn.disabled = true;
    return;
  }
  const btn = document.getElementById('atl-ref-btn-creer');
  if (btn) btn.disabled = false;

  if (ATL_REF_LISTE.length === 0) {
    cont.innerHTML = `
      <div style="padding:14px;font-size:12px;color:var(--text-muted)">
        Aucun référentiel pour ce niveau. Cliquez sur <strong>+ Créer</strong>.
      </div>`;
    return;
  }

  cont.innerHTML = ATL_REF_LISTE.map(r => atelRefItemHtml(r)).join('');
}

function atelRefItemHtml(r) {
  const isActive = ATL_REF_SELECTION && ATL_REF_SELECTION.id === r.id;
  const cls = isActive ? 'asm-item asm-item--clickable active'
                       : 'asm-item asm-item--clickable';
  const pastille = atelRefPastilleHtml(r.etat);
  const desc = (r.description || '').trim();
  // v0.13.5.1.1 — Sidebar épurée : pastille de couleur (pas de badge
  // texte), date_fin retirée (peu utile en sidebar — visible dans le
  // détail). On garde la date_debut quand elle existe (repère temporel
  // utile pour distinguer plusieurs référentiels d'une même année).
  const dateDebut = r.date_debut
    ? `<div class="atl-item-fc" style="font-size:11px;color:var(--text-muted)">depuis ${r.date_debut}</div>`
    : '';
  return `
    <div class="${cls}" onclick="atelRefSelectionner('${r.id}')">
      <div class="atl-item-id" style="display:flex;align-items:center;gap:6px">
        ${pastille}<span>${r.id}</span>
      </div>
      ${desc ? `<div class="atl-item-titre">${atelRefEscape(desc)}</div>` : ''}
      ${dateDebut}
    </div>`;
}

// v0.15.3 — Pastille colorée représentant l'état (sans texte).
// Convention :
//   en_cours   → gris    « en cours »
//   valide     → vert    « validé »
//   verrouille → bleu    « verrouillé »
//   utilise    → violet  « utilisé »  (associé à ≥ 1 progression)
//   annule     → transparent (cercle vide, hidden by default)
// Le tooltip natif (title) garde l'info textuelle pour les cas
// où la couleur ne suffit pas (daltonisme, écran B&W, …).
function atelRefPastilleHtml(etat) {
  const styles = {
    'en_cours':   'background:#bdbdbd',
    'valide':     'background:#43a047',
    'verrouille': 'background:#0d47a1',
    'utilise':    'background:#6a1b9a',
    'annule':     'background:transparent;border:1px dashed #999',
  };
  const libelles = {
    'en_cours':   'en cours',
    'valide':     'validé',
    'verrouille': 'verrouillé',
    'utilise':    'utilisé',
    'annule':     'annulé',
  };
  const style = styles[etat] || 'background:#eee';
  const libelle = libelles[etat] || etat;
  return `<span class="atl-ref-pastille" title="${libelle}"
                 style="display:inline-block;width:12px;height:12px;
                        border-radius:50%;flex-shrink:0;${style}"></span>`;
}


// ── v0.15.2.8 — Diagnostic d'éligibilité à la validation ───────────────────

// Met à jour l'encart `atl-ref-diag-validation` en interrogeant l'API.
// Affiche soit « Référentiel éligible : prêt à figer », soit la liste des
// raisons de non-éligibilité. Caché pour les états terminaux (fige/annule).
async function atelRefMajDiagValidation(refId, etat) {
  const cont    = document.getElementById('atl-ref-diag-validation');
  const libelle = document.getElementById('atl-ref-diag-validation-libelle');
  const raisons = document.getElementById('atl-ref-diag-validation-raisons');
  if (!cont || !libelle || !raisons) return;

  // États terminaux : on cache.
  if (etat !== 'en_cours' && etat !== 'valide') {
    cont.style.display = 'none';
    return;
  }

  try {
    const rep = await fetch(`/api/referentiels/${encodeURIComponent(refId)}`
                            + '/eligibilite_validation');
    if (!rep.ok) {
      cont.style.display = 'none';
      return;
    }
    const diag = await rep.json();
    if (diag.eligible) {
      cont.style.cssText =
        'display:block;margin-top:12px;padding:10px 12px;border-radius:4px;'
        + 'font-size:13px;background:#e8f5e9;color:#2e7d32;'
        + 'border:1px solid #c8e6c9';
      libelle.innerHTML =
        '<strong>Référentiel éligible.</strong> '
        + 'Tous les atomes, évaluations et documents sont validés.';
      raisons.innerHTML = '';
    } else {
      cont.style.cssText =
        'display:block;margin-top:12px;padding:10px 12px;border-radius:4px;'
        + 'font-size:13px;background:#fff3e0;color:#e65100;'
        + 'border:1px solid #ffcc80';
      libelle.innerHTML =
        '<strong>Référentiel non éligible.</strong> '
        + 'Reste à valider :';
      raisons.innerHTML =
        (diag.raisons || []).map(r =>
          `<li>${atelRefEscape(r)}</li>`).join('');
    }
  } catch (e) {
    console.error('[atelRefMajDiagValidation]', e);
    cont.style.display = 'none';
  }
}

// Bouton « Revérifier l'éligibilité » : force le recalcul lazy côté
// serveur (transition d'état appliquée si applicable) puis recharge la
// liste pour refléter le nouvel état.
async function atelRefRevalider() {
  if (!ATL_REF_SELECTION) return;
  const refId = ATL_REF_SELECTION.id;
  try {
    const rep = await fetch(
      `/api/referentiels/${encodeURIComponent(refId)}/revalider`,
      { method: 'POST' }
    );
    if (!rep.ok) {
      alert("Erreur lors du recalcul (HTTP " + rep.status + ").");
      return;
    }
    const data = await rep.json();
    // Recharger la liste pour refléter le nouvel état (et la sélection
    // courante si elle a basculé).
    await atelRefRechargerListe();
    atelRefRendreSidebar();
    // Maintenir la sélection courante si l'item existe toujours.
    const refsApres = (ATL_REF_LISTE || []).find(r => r.id === refId);
    if (refsApres) ATL_REF_SELECTION = refsApres;
    atelRefRendreDetail();
  } catch (e) {
    console.error('[atelRefRevalider]', e);
    alert("Erreur réseau lors du recalcul : " + (e.message || e));
  }
}


// ── Rendu — Zone détail ──────────────────────────────────────────────────────

function atelRefRendreDetail() {
  const empty = document.getElementById('atl-ref-empty');
  const detail = document.getElementById('atl-ref-detail');
  if (!ATL_REF_SELECTION) {
    if (empty)  empty.style.display = '';
    if (detail) detail.style.display = 'none';
    return;
  }
  if (empty)  empty.style.display = 'none';
  if (detail) detail.style.display = '';

  const r = ATL_REF_SELECTION;

  // Titre + pastille d'état (cohérence avec la sidebar) + libellé texte.
  // Le span#atl-ref-detail-badge sert de conteneur pour pastille + libellé.
  const titre = document.getElementById('atl-ref-detail-titre');
  if (titre) titre.textContent = r.id;
  const badge = document.getElementById('atl-ref-detail-badge');
  if (badge) {
    badge.style.cssText =
      'margin-left:8px;display:inline-flex;align-items:center;gap:5px;'
      + 'font-size:12px;font-weight:normal;color:var(--text-muted)';
    // v0.15.3 — affiche le libellé humain (« validé », « verrouillé »,
    // …) plutôt que le code BDD brut.
    const libelles = {
      'en_cours':   'en cours',
      'valide':     'validé',
      'verrouille': 'verrouillé',
      'utilise':    'utilisé',
      'annule':     'annulé',
    };
    const lib = libelles[r.etat] || r.etat;
    badge.innerHTML = atelRefPastilleHtml(r.etat) + atelRefEscape(lib);
  }

  // Méta
  const meta = document.getElementById('atl-ref-detail-meta');
  if (meta) {
    const parts = [`Niveau : <strong>${r.niveau}</strong>`,
                   `Version : <strong>${r.version}</strong>`];
    if (r.date_debut) parts.push(`Début : ${r.date_debut}`);
    if (r.date_fin)   parts.push(`Fin : ${r.date_fin}`);
    meta.innerHTML = parts.join(' &middot; ');
  }

  // Description
  const desc = document.getElementById('atl-ref-detail-desc');
  if (desc) desc.textContent = r.description || '';

  // Boutons d'action selon l'état (v0.15.3)
  const btnSupprimer    = document.getElementById('atl-ref-btn-supprimer');
  const btnVerrouiller  = document.getElementById('atl-ref-btn-verrouiller');
  const btnDeverrouiller= document.getElementById('atl-ref-btn-deverrouiller');
  const btnRevalider    = document.getElementById('atl-ref-btn-revalider');
  if (btnSupprimer)
    btnSupprimer.style.display = (r.etat === 'en_cours') ? '' : 'none';
  if (btnVerrouiller)
    btnVerrouiller.style.display = (r.etat === 'valide') ? '' : 'none';
  // v0.15.3 — Déverrouillage : disponible uniquement pour `verrouille`.
  // Pas pour `utilise` (référentiel attaché à une progression), ni
  // pour les autres états.
  if (btnDeverrouiller)
    btnDeverrouiller.style.display = (r.etat === 'verrouille') ? '' : 'none';
  // « Revérifier » dispo pour en_cours (aide à passer à valide) et
  // valide (forcer un recalcul après un changement).
  if (btnRevalider) {
    btnRevalider.style.display =
      (r.etat === 'en_cours' || r.etat === 'valide') ? '' : 'none';
  }

  // v0.15.2.8 — Diagnostic d'éligibilité (lazy load via API)
  atelRefMajDiagValidation(r.id, r.etat);

  // v0.15.3 — Bloc « Données verrouillées » (JSON + PDFs) pour les
  // référentiels `verrouille` ou `utilise`. Caché autrement.
  atelRefMajDonneesVerrouillees(r.id, r.etat);

  // Arbre : affiché pour en_cours et valide. Pour fige/verrouille/annule,
  // on affiche un message lecture seule (l'arbre des tables actives n'a
  // pas grand sens pour un référentiel figé — sa version figée du contenu
  // arrivera en v0.13.5.3 avec les PDF stockés).
  const arbreCont = document.getElementById('atl-ref-arbre');
  if (!arbreCont) return;

  if (r.etat === 'en_cours' || r.etat === 'valide') {
    atelRefRendreArbre();
  } else {
    arbreCont.innerHTML = `
      <div class="atl-cadre" style="padding:24px;text-align:center;color:var(--text-muted)">
        <p style="margin:0;font-size:13px">
          Ce référentiel est <strong>${r.etat}</strong>.
        </p>
        <p style="margin-top:8px;font-size:12px">
          L'accès au contenu figé (PDF, listes d'exercices)
          sera ajouté en v0.13.5.3.
        </p>
      </div>`;
    const stats = document.getElementById('atl-ref-stats-resume');
    if (stats) stats.textContent = '';
  }

  // v0.13.6.4 — Toujours revenir à l'onglet Tableau de bord à chaque
  // changement de sélection (état non persistant entre référentiels).
  // Les documents sont chargés à la demande à l'ouverture de l'onglet.
  atelRefChangerOnglet('dashboard');
}

async function atelRefRendreArbre() {
  const cont = document.getElementById('atl-ref-arbre');
  if (!cont) return;
  cont.innerHTML = `
    <div class="atl-cadre" style="padding:24px;text-align:center;color:var(--text-muted)">
      Chargement de l'arbre du niveau…
    </div>`;

  const data = await atelRefChargerArbre(ATL_REF_SELECTION.id);
  if (!data || !ATL_REF_ARBRE) {
    cont.innerHTML = `
      <div class="atl-cadre" style="padding:24px;text-align:center;color:#8b1a1a">
        Échec du chargement de l'arbre.
      </div>`;
    return;
  }

  const a = ATL_REF_ARBRE;
  const stats = document.getElementById('atl-ref-stats-resume');
  if (stats) {
    const t = a.stats.total, v = a.stats.valides, e = a.stats.en_cours;
    const pct = t > 0 ? Math.round(100 * v / t) : 0;
    stats.innerHTML = `<strong>${v}</strong> validés / <strong>${t}</strong> atomes (${pct}%)`;
  }

  // v0.13.6.3 — Rendu de l'arbre : 2 cadres top-level
  //   1) Évaluations (rattachées au niveau, pas à une séquence)
  //   2) Séquences (rendu historique)
  const htmlEvals = atelRefEvaluationsCadreHtml(a.evaluations || []);
  const htmlSeqs = (a.sequences || []).map(s => atelRefSequenceHtml(s)).join('');
  const cadreSeqs = htmlSeqs ? `
    <div class="atl-cadre" style="margin-bottom:10px">
      <div class="atl-cadre-titre">Séquences</div>
      <div style="padding:8px">
        ${htmlSeqs}
      </div>
    </div>` : `
    <div class="atl-cadre" style="padding:24px;text-align:center;color:var(--text-muted)">
      Aucune séquence rattachée à ce niveau.
    </div>`;
  cont.innerHTML = htmlEvals + cadreSeqs;
}

function atelRefSequenceHtml(s) {
  const couleurStyle = s.theme_couleur
    ? `border-left:4px solid var(--theme-${s.theme_couleur}, #888)`
    : '';
  const partiesHtml = s.parties.map(p => atelRefPartieHtml(p)).join('');
  const seqId = `atl-ref-seq-${s.code}`;
  return `
    <div class="atl-cadre" style="margin-bottom:10px;${couleurStyle}">
      <div class="atl-cadre-titre" style="cursor:pointer"
           onclick="atelRefBasculerSection('${seqId}')">
        <span style="font-size:11px;color:var(--text-muted);font-weight:normal">
          S${String(s.numero).padStart(2,'0')}
        </span>
        ${atelRefEscape(s.nom)}
      </div>
      <div id="${seqId}" class="atl-ref-seq-body">
        ${partiesHtml || `<div style="padding:8px;font-size:12px;color:var(--text-muted)">Aucune partie.</div>`}
      </div>
    </div>`;
}

// ── v0.13.5.1.2 — Rendu de partie : Révisions + Activité toujours présentes
//
// Spec :
//   "Révisions : "  toujours affiché. Items au format "<niveau>/<seq>/<serie><num>"
//   "Activité : "   toujours affiché. Items au format "EA01", "EA02"…
//
// Si aucun item dans une catégorie, on affiche le libellé seul, suivi
// d'un placeholder discret "(aucun)".
function atelRefPartieHtml(p) {
  const objs = p.objectifs.map(o => atelRefObjectifHtml(o)).join('');
  const seances = p.nb_seances_R_AE
    ? ` <span style="font-size:11px;color:var(--text-muted)">(${p.nb_seances_R_AE} séances R+AE)</span>`
    : '';

  // v0.13.6.3 — Cartes d'automatisme (intercalées AVANT le bloc R/EA,
  // comme demandé : "avant les révisions/approches"). Toujours
  // affichées, avec placeholder "(aucune)" si rien.
  const cartes = p.atomes_cartes || [];
  const cartesHtml = `
    <div style="padding:6px 8px;background:var(--surface);
                border-bottom:1px solid var(--border);
                display:flex;flex-direction:column;gap:4px;font-size:11px">
      ${atelRefLigneCartesHtml(cartes)}
    </div>`;

  const rae = p.atomes_rae || [];
  const r_items  = rae.filter(a => a.sous_type === 'R');
  const ea_items = rae.filter(a => a.sous_type === 'EA');

  const raeHtml = `
    <div style="padding:6px 8px;background:var(--surface);
                border-bottom:1px solid var(--border);
                display:flex;flex-direction:column;gap:4px;font-size:11px">
      ${atelRefLigneRaeHtml('Révisions', r_items)}
      ${atelRefLigneRaeHtml('Activité',  ea_items)}
    </div>`;

  return `
    <div class="atl-cadre atl-cadre--compact" style="margin:8px 6px">
      <div class="atl-cadre-titre" style="font-size:13px">
        Partie ${p.numero}${seances}
      </div>
      ${cartesHtml}
      ${raeHtml}
      <div>
        ${objs || `<div style="padding:6px;font-size:12px;color:var(--text-muted)">Aucun objectif.</div>`}
      </div>
    </div>`;
}

// v0.13.6.3 — Ligne "Cartes d'automatisme : <chip> <chip> …"
// Même pattern visuel que atelRefLigneRaeHtml. La chip réutilise
// atelRefAtomeChipHtml (état coloré + deeplink).
function atelRefLigneCartesHtml(cartes) {
  const cont = cartes.length === 0
    ? `<span style="color:var(--text-muted);font-style:italic">(aucune)</span>`
    : cartes.map(c => atelRefAtomeChipHtml(c)).join(' ');
  return `
    <div style="display:flex;flex-wrap:wrap;align-items:baseline;gap:6px">
      <span style="font-weight:600;color:var(--text-muted);min-width:130px">
        Cartes d'automatisme :
      </span>
      <span style="display:flex;flex-wrap:wrap;gap:4px;align-items:center">
        ${cont}
      </span>
    </div>`;
}

function atelRefLigneRaeHtml(libelle, items) {
  // libelle = 'Révisions' ou 'Activité'
  const cont = items.length === 0
    ? `<span style="color:var(--text-muted);font-style:italic">(aucun)</span>`
    : items.map(a => atelRefAtomeChipHtml(a)).join(' ');
  return `
    <div style="display:flex;flex-wrap:wrap;align-items:baseline;gap:6px">
      <span style="font-weight:600;color:var(--text-muted);min-width:64px">
        ${libelle} :
      </span>
      <span style="display:flex;flex-wrap:wrap;gap:4px;align-items:center">
        ${cont}
      </span>
    </div>`;
}

// ── v0.13.5.1.2 — Rendu d'un objectif : 5 lignes possibles
//
//   Ligne 1 : Méthode + Fiche de révision (ou "(manquante)" si absents)
//   Lignes 2+ : Notion : <titre>     (flex-wrap si déborde)
//   Ligne F : Série F : <numéros>
//   Ligne A : Série A : <numéros>
//   Ligne E : Série E : <numéros>
//
// v0.13.5.1.4 — Cas particulier des objectifs "Cours" (codes 01, 11, 21
// selon la convention métier) : ils n'ont structurellement pas de
// méthode, fiche ni exos. On affiche uniquement leur titre, sans aucune
// ligne supplémentaire.
function atelRefObjectifHtml(o) {
  const fc = o.fin_cycle ? ' <span style="font-size:10px;color:#0d47a1">[fin cycle]</span>' : '';

  // Cas Cours : titre seul
  if (o.est_cours) {
    return `
      <div style="padding:6px 8px;border-top:1px solid var(--border)">
        <div style="font-size:13px">
          <strong>${o.code}</strong> ${atelRefEscape(o.nom)}${fc}
        </div>
      </div>`;
  }

  // Ligne 1 : Méthode + Fiche
  const lien_methode = o.methode
    ? atelRefAtomeLibHtml(o.methode, 'Méthode')
    : `<span style="color:#c0392b;opacity:.7;font-size:11px">Méthode (manquante)</span>`;
  const lien_fiche = o.fiche
    ? atelRefAtomeLibHtml(o.fiche, 'Fiche de résumé')
    : `<span style="color:#c0392b;opacity:.7;font-size:11px">Fiche de résumé (manquante)</span>`;
  const ligne1 = `
    <div style="display:flex;flex-wrap:wrap;gap:18px;align-items:baseline;
                font-size:11px;margin-top:4px">
      ${lien_methode}
      ${lien_fiche}
    </div>`;

  // Lignes notions : "Notion : <titre>" en flex-wrap
  const lignes_notions = (o.notions || []).length === 0 ? '' : `
    <div style="display:flex;flex-wrap:wrap;gap:14px;align-items:baseline;
                font-size:11px;margin-top:3px">
      ${(o.notions || []).map(n => atelRefAtomeNotionHtml(n)).join('')}
    </div>`;

  // Lignes F / A / E
  const ligne_F = atelRefLigneSerieHtml('F', o.exos_F || []);
  const ligne_A = atelRefLigneSerieHtml('A', o.exos_A || []);
  const ligne_E = atelRefLigneSerieHtml('E', o.exos_E || []);

  return `
    <div style="padding:6px 8px;border-top:1px solid var(--border)">
      <div style="font-size:13px">
        <strong>${o.code}</strong> ${atelRefEscape(o.nom)}${fc}
      </div>
      ${ligne1}
      ${lignes_notions}
      ${ligne_F}
      ${ligne_A}
      ${ligne_E}
    </div>`;
}

function atelRefLigneSerieHtml(serie, exos) {
  // Ligne fixe par série, même vide. Les chips restent compacts (juste
  // le code, ex. F01, F02), tooltip = titre de l'exo.
  const cont = exos.length === 0
    ? `<span style="color:var(--text-muted);font-style:italic">(aucun)</span>`
    : exos.map(e => atelRefAtomeChipHtml(e)).join(' ');
  return `
    <div style="display:flex;flex-wrap:wrap;align-items:baseline;gap:6px;
                font-size:11px;margin-top:3px">
      <span style="font-weight:600;color:var(--text-muted);min-width:54px">
        Série ${serie} :
      </span>
      <span style="display:flex;flex-wrap:wrap;gap:4px;align-items:center">
        ${cont}
      </span>
    </div>`;
}

// ── v0.13.5.1.2 — Helpers de rendu d'un atome
//
// Trois variantes selon le contexte :
//   - chip   : juste le code (F01, R01 = N09/S01/A01, EA01) — séries F/A/E + R/EA
//   - lib    : libellé fixe (Méthode / Fiche de résumé), titre en tooltip
//   - notion : "Notion : <titre>" en clair
//
// Toutes les variantes :
//   - cliquables si l'atome a un id (ouverture nouvel onglet via deeplink)
//   - couleur du texte selon état (vert si valide, gris foncé si en_cours)

function atelRefAtomeUrl(a) {
  // a.type ∈ {methode, notion, exo, fiche, carte}, mais l'atelier cible côté
  // app.js peut différer : exo → exercice. On fait le mapping ici.
  // v0.13.6.3 — ajout du type 'carte' → atelier 'cartes_automatisme'
  const map = {
    'methode': 'methode',
    'notion':  'notion',
    'exo':     'exercice',
    'fiche':   'fiche',
    'carte':   'carte_automatisme',
  };
  const atelier = map[a.type];
  if (!atelier || !a.id || !a.nav_niveau || !a.nav_seq) return null;
  const qs = new URLSearchParams({
    atelier: atelier,
    niveau:  a.nav_niveau,
    seq:     a.nav_seq,
    atome:   a.id,
  });
  return '/?' + qs.toString();
}

// v0.13.5.1.3 — Badges colorés uniformes
//
// Tous les atomes (méthode, fiche, notion, exo F/A/E, exo R/EA) sont
// rendus avec un badge cliquable. Fond vert pâle si l'atome est
// `valide`, fond gris si `en_cours`. Le contraste fond/texte rend
// l'état immédiatement lisible, sans pastille séparée.
function atelRefStyleBadge(a) {
  if (a.etat_code === 'valide') {
    return 'background:#c8e6c9;color:#1b5e20;border-color:#a5d6a7';
  }
  return 'background:#eeeeee;color:#444;border-color:#cfcfcf';
}

// Style de base commun à tous les badges. Le pointer cursor est posé
// par <a>, on l'ajoute aussi sur les <span> non-cliquables pour la
// cohérence visuelle (mais pas le hover effect).
const _ATL_REF_BADGE_BASE =
  'display:inline-flex;align-items:center;padding:2px 7px;'
  + 'border:1px solid;border-radius:3px;font-size:11px;'
  + 'text-decoration:none;line-height:1.4;white-space:nowrap';

function atelRefAtomeChipHtml(a) {
  // Badge avec juste le code (F01, R01 = N09/S01/A01, EA01).
  const url = atelRefAtomeUrl(a);
  const titreFull = (a.titre || '').replace(/"/g, '&quot;');
  const tooltip = titreFull
    ? `${a.sous_type ? a.sous_type + ' — ' : ''}${titreFull}`
    : (a.sous_type || a.type);
  const style = `${_ATL_REF_BADGE_BASE};${atelRefStyleBadge(a)}`;
  const code = atelRefEscape(a.code);
  if (url) {
    return `<a href="${url}" target="_blank" rel="noopener"
              title="${tooltip}" style="${style}">${code}</a>`;
  }
  return `<span title="${tooltip}" style="${style}">${code}</span>`;
}

function atelRefAtomeLibHtml(a, libelleFixe) {
  // Badge avec libellé fixe ("Méthode" / "Fiche de résumé"), titre en
  // tooltip (souvent = nom de l'objectif, donc inutile à répéter).
  const url = atelRefAtomeUrl(a);
  const titreFull = (a.titre || '').replace(/"/g, '&quot;');
  const style = `${_ATL_REF_BADGE_BASE};${atelRefStyleBadge(a)}`;
  const lib = atelRefEscape(libelleFixe);
  if (url) {
    return `<a href="${url}" target="_blank" rel="noopener"
              title="${titreFull}" style="${style}">${lib}</a>`;
  }
  return `<span title="${titreFull}" style="${style}">${lib}</span>`;
}

function atelRefAtomeNotionHtml(a) {
  // Badge "Notion : <titre>" — le badge entier est cliquable pour
  // ouvrir l'atelier Notion sur cette notion.
  const url = atelRefAtomeUrl(a);
  const titre = atelRefEscape(a.titre || '(sans titre)');
  const style = `${_ATL_REF_BADGE_BASE};${atelRefStyleBadge(a)}`;
  const titreFull = (a.titre || '').replace(/"/g, '&quot;');
  const contenu = `<strong style="font-weight:600;margin-right:4px">Notion :</strong>${titre}`;
  if (url) {
    return `<a href="${url}" target="_blank" rel="noopener"
              title="${titreFull}" style="${style}">${contenu}</a>`;
  }
  return `<span title="${titreFull}" style="${style}">${contenu}</span>`;
}


// ── v0.13.6.3 — Rendu du cadre "Évaluations" ────────────────────────────────
//
// Spec : un cadre top-level avant le cadre "Séquences", contenant un
// sous-cadre par évaluation. Chaque sous-cadre affiche le titre de
// l'éval et une rangée de chips, une par exo, colorée selon l'état de
// l'exo (vert si valide, gris si en_cours). Le clic sur un chip ouvre
// l'atelier Exercice sur l'exo source.
//
// Le titre de l'éval est cliquable et ouvre l'atelier Évaluation sur
// le niveau courant (la pré-sélection de l'éval n'est pas supportée
// par atelEvalInit aujourd'hui — à ajouter dans une session ultérieure
// si besoin).

function atelRefEvaluationsCadreHtml(evals) {
  if (!evals || evals.length === 0) {
    // Cadre tout de même affiché pour rappeler la portée et inciter à
    // créer des évaluations si nécessaire.
    return `
      <div class="atl-cadre" style="margin-bottom:10px">
        <div class="atl-cadre-titre">Évaluations</div>
        <div style="padding:12px;font-size:12px;color:var(--text-muted)">
          (aucune évaluation pour ce niveau)
        </div>
      </div>`;
  }
  const blocs = evals.map(ev => atelRefEvaluationBlocHtml(ev)).join('');
  return `
    <div class="atl-cadre" style="margin-bottom:10px">
      <div class="atl-cadre-titre">Évaluations</div>
      <div style="padding:8px;display:flex;flex-direction:column;gap:8px">
        ${blocs}
      </div>
    </div>`;
}

function atelRefEvaluationBlocHtml(ev) {
  const titre = atelRefEscape(ev.titre || `Évaluation ${ev.numero || ''}`);
  const numero = ev.numero
    ? `<span style="font-size:11px;color:var(--text-muted);font-weight:normal">
         ${atelRefEscape(`Éval ${String(ev.numero).padStart(2,'0')}`)}
       </span>`
    : '';
  // Couleur du titre selon l'état : vert si valide, gris foncé sinon,
  // pour cohérence avec les chips.
  // Note v0.13.6.3 : titre non cliquable car atelEvalInit n'expose pas
  // d'API de pré-sélection d'une éval donnée. Évolution possible en
  // ajoutant un atelEvalCharger(evalId) côté atelier_evaluation.js.
  const titreColor = ev.etat_code === 'valide' ? '#1b5e20' : '#444';
  const titreHtml = `<span style="color:${titreColor};font-weight:600">${numero} ${titre}</span>`;

  const chips = (ev.exos || []).length === 0
    ? `<span style="color:var(--text-muted);font-style:italic;font-size:11px">(aucun exercice)</span>`
    : ev.exos.map(ex => atelRefAtomeChipHtml(ex)).join(' ');

  return `
    <div class="atl-cadre atl-cadre--compact" style="margin:0">
      <div class="atl-cadre-titre" style="font-size:13px">
        ${titreHtml}
      </div>
      <div style="padding:6px 8px;display:flex;flex-wrap:wrap;gap:4px;
                  align-items:center;font-size:11px">
        ${chips}
      </div>
    </div>`;
}


// ── Actions utilisateur ──────────────────────────────────────────────────────

async function atelRefSelectionner(refId) {
  const r = ATL_REF_LISTE.find(x => x.id === refId);
  if (!r) return;
  ATL_REF_SELECTION = r;
  ATL_REF_ARBRE = null;
  atelRefRendreSidebar();
  atelRefRendreDetail();
}

async function atelRefCreerCoquille() {
  const niveau = (typeof ATL_FILTRE_NIVEAU !== 'undefined')
                   ? ATL_FILTRE_NIVEAU : '';
  if (!niveau) {
    alert('Aucun niveau sélectionné dans la barre de portée.');
    return;
  }
  const description = (prompt(
    `Créer un nouveau référentiel pour ${niveau}.\n\n` +
    `Le nom est calculé automatiquement (année scolaire + niveau + suffixe).\n\n` +
    `Description (optionnelle, pour vous repérer plus tard) :`,
    ''
  ) || '').trim();
  // L'utilisateur peut annuler le prompt (return null) — dans ce cas
  // description = '' après le `|| ''`. Pour distinguer "annulé" de
  // "vide", on pourrait tester `=== null` avant le ||, mais en pratique
  // créer une coquille avec description vide est un cas valide qui
  // matche le comportement attendu : "j'ai juste cliqué OK trop vite".
  // Si l'utilisateur veut vraiment annuler, il y a la suppression
  // immédiate juste après.

  try {
    const data = await api('/api/referentiels/coquille', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ niveau, description }),
    });
    await atelRefRechargerListe();
    // Sélectionne le nouveau référentiel
    ATL_REF_SELECTION = ATL_REF_LISTE.find(r => r.id === data.ref.id) || null;
    atelRefRendreSidebar();
    atelRefRendreDetail();
  } catch (e) {
    alert('Échec de la création : ' + (e.message || e));
  }
}

async function atelRefSupprimer() {
  if (!ATL_REF_SELECTION) return;
  const r = ATL_REF_SELECTION;
  if (r.etat !== 'en_cours') {
    alert(`Seuls les référentiels en_cours peuvent être supprimés. État actuel : ${r.etat}.`);
    return;
  }
  const ok = confirm(
    `Supprimer définitivement le référentiel "${r.id}" ?\n\n` +
    `Cette action est irréversible (mais sans impact sur le contenu actif).`
  );
  if (!ok) return;

  try {
    await fetch(`/api/referentiels/${encodeURIComponent(r.id)}`, {
      method: 'DELETE',
    }).then(rr => {
      if (!rr.ok && rr.status !== 204) throw new Error('HTTP ' + rr.status);
    });
    ATL_REF_SELECTION = null;
    await atelRefRechargerListe();
    atelRefRendreSidebar();
    atelRefRendreDetail();
  } catch (e) {
    alert('Échec de la suppression : ' + (e.message || e));
  }
}

async function atelRefVerrouiller() {
  if (!ATL_REF_SELECTION) return;
  const r = ATL_REF_SELECTION;
  if (r.etat !== 'valide') {
    alert(`Seuls les référentiels validés peuvent être verrouillés. État actuel : ${r.etat}.`);
    return;
  }

  // Premier appel : sans force_confirme → le serveur peut demander confirmation.
  let res;
  try {
    res = await api(`/api/referentiels/${encodeURIComponent(r.id)}/verrouiller`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ force_confirme: false }),
    });
  } catch (e) {
    alert('Échec du verrouillage : ' + (e.message || e));
    return;
  }

  // Cas 1 : confirmation requise — afficher la liste des concurrents et
  // redemander l'utilisateur.
  if (res.confirmation_requise) {
    const liste = res.concurrents.map(c => `  • ${c.id} (${c.etat})`).join('\n');
    const ok = confirm(
      `Verrouiller "${r.id}" va annuler les référentiels suivants en cours/validés :\n\n` +
      liste + `\n\n` +
      `Cette action est irréversible. Les annulés conservent leur trace ` +
      `mais ne pourront plus être édités ni utilisés.\n\n` +
      `Confirmer ?`
    );
    if (!ok) return;

    // 2e appel : avec force_confirme=true.
    try {
      res = await api(`/api/referentiels/${encodeURIComponent(r.id)}/verrouiller`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ force_confirme: true }),
      });
    } catch (e) {
      alert('Échec du verrouillage : ' + (e.message || e));
      return;
    }
  }

  // Cas 2 : verrouillage effectué (avec ou sans concurrents annulés).
  const annules = (res.concurrents_annules || []);
  let msg = `Référentiel "${res.ref.id}" verrouillé avec succès.`;
  if (annules.length > 0) {
    msg += `\n\n${annules.length} référentiel(s) annulé(s) :\n`
         + annules.map(c => `  • ${c.id}`).join('\n');
  }
  // v0.15.3 — rapport de verrouillage (trace + PDFs)
  if (res.verrouille) {
    const v = res.verrouille;
    msg += `\n\nTrace : ${v.trace}`;
    msg += `\nPDFs copiés : ${v.nb_pdfs_copies}`;
    if (v.echecs_copie && v.echecs_copie.length > 0) {
      msg += `\nÉchecs de copie : ${v.echecs_copie.length}`
           + v.echecs_copie.map(e =>
               `\n  • ${e.nom_fichier} — ${e.raison || ''}`).join('');
    }
  }
  alert(msg);

  // Recharger pour refléter l'état mis à jour.
  await atelRefRechargerListe();
  ATL_REF_SELECTION = ATL_REF_LISTE.find(x => x.id === r.id) || null;
  atelRefRendreSidebar();
  atelRefRendreDetail();
}


// v0.15.3 — Alias rétro-compat pour l'ancien nom de fonction. Le bouton
// HTML appelle désormais atelRefVerrouiller(), mais si du code legacy
// référence encore atelRefFiger(), ça reste fonctionnel.
const atelRefFiger = atelRefVerrouiller;


async function atelRefDeverrouiller() {
  // v0.15.3 — Transition verrouille → valide (action utilisateur).
  if (!ATL_REF_SELECTION) return;
  const r = ATL_REF_SELECTION;
  if (r.etat !== 'verrouille') {
    alert(`Seuls les référentiels verrouillés peuvent être déverrouillés. `
        + `État actuel : ${r.etat}.`);
    return;
  }
  const ok = confirm(
    `Déverrouiller "${r.id}" repassera le référentiel à l'état « validé ». ` +
    `Le dossier de verrouillage (JSON + PDFs) est conservé et sera écrasé ` +
    `au prochain verrouillage.\n\nContinuer ?`
  );
  if (!ok) return;
  try {
    await api(`/api/referentiels/${encodeURIComponent(r.id)}/deverrouiller`,
              { method: 'POST' });
  } catch (e) {
    alert('Échec du déverrouillage : ' + (e.message || e));
    return;
  }
  await atelRefRechargerListe();
  ATL_REF_SELECTION = ATL_REF_LISTE.find(x => x.id === r.id) || null;
  atelRefRendreSidebar();
  atelRefRendreDetail();
}


// ── v0.15.3 — Bloc « Données verrouillées » dans la zone détail ────────────


async function atelRefMajDonneesVerrouillees(refId, etat) {
  // Affiché uniquement pour `verrouille` et `utilise`. Caché autrement.
  const cont = document.getElementById('atl-ref-donnees-verrouillees');
  if (!cont) return;
  const visible = (etat === 'verrouille' || etat === 'utilise');
  cont.style.display = visible ? '' : 'none';
  if (!visible) return;

  // Chargement de la trace
  const zoneTrace = document.getElementById('atl-ref-donnees-trace');
  const zonePdfs  = document.getElementById('atl-ref-donnees-pdfs');
  if (zoneTrace) zoneTrace.innerHTML = '<em>Chargement de la trace…</em>';
  if (zonePdfs)  zonePdfs.innerHTML  = '';

  let trace = null;
  try {
    trace = await api(`/api/referentiels/${encodeURIComponent(refId)}/trace`);
  } catch (e) {
    if (zoneTrace) zoneTrace.innerHTML =
      `<em>Trace indisponible : ${e.message || e}</em>`;
    return;
  }

  // Rendu de la trace en arbre complètement dépliable (v0.15.4)
  if (zoneTrace) {
    zoneTrace.innerHTML = atelRefRenduTraceComplete(trace);
  }

  // Rendu des PDFs (un lien par cible)
  if (zonePdfs) {
    const docs = trace.documents || [];
    const liens = [];
    for (const d of docs) {
      for (const c of (d.cibles || [])) {
        const nom = c.nom_fichier;
        if (!nom) continue;
        const url = `/api/referentiels/${encodeURIComponent(refId)}/pdf/`
                  + encodeURIComponent(nom);
        liens.push(`<li><a href="${url}" target="_blank" `
                 + `rel="noopener">${escHtml(nom)}</a> `
                 + `<span style="color:#888">(${d.type_document})</span></li>`);
      }
    }
    zonePdfs.innerHTML = liens.length
      ? `<strong>PDFs verrouillés (${liens.length}) :</strong>`
        + `<ul>${liens.join('')}</ul>`
      : `<em>Aucun PDF verrouillé.</em>`;
  }
}


// v0.15.4 — Rendu complet de la trace JSON en arbre dépliable.
// Tous les niveaux sont navigables :
//   référentiel → thèmes → séquences → parties → objectifs
//                 → méthodes / notions / exercices / fiches / cartes
// Plus les exercices R/AE de chaque partie.
function atelRefRenduTraceComplete(trace) {
  const h = [];
  h.push('<div class="atl-ref-trace-arbre">');

  // Métadonnées top-level
  h.push('<div class="atl-ref-trace-meta" style="margin-bottom:8px;color:#555">');
  h.push(`<strong>Schéma v${trace.version_schema}</strong>`);
  if (trace.date_figeage)
    h.push(` &middot; verrouillé le ${escHtml(trace.date_figeage)}`);
  h.push('</div>');

  // Référentiel — métadonnées
  h.push('<details><summary>Référentiel — métadonnées</summary>');
  const ref = trace.referentiel || {};
  h.push('<dl style="margin-left:1em">');
  for (const [k, v] of Object.entries(ref)) {
    h.push(`<dt style="font-weight:600">${escHtml(k)}</dt>`);
    h.push(`<dd style="margin-left:1em">${escHtml(v ?? '—')}</dd>`);
  }
  h.push('</dl></details>');

  // Thèmes
  const themes = trace.themes || [];
  h.push(`<details><summary>Thèmes (${themes.length})</summary>`);
  h.push('<ul style="margin-left:1em">');
  for (const t of themes) {
    h.push(`<li><strong>${escHtml(t.code)}</strong> — ${escHtml(t.nom)}`);
    if (t.couleur) h.push(` <span style="color:#888">[${escHtml(t.couleur)}]</span>`);
    h.push('</li>');
  }
  h.push('</ul></details>');

  // Séquences
  const sequences = trace.sequences || [];
  h.push(`<details open><summary>Séquences (${sequences.length})</summary>`);
  for (const s of sequences) {
    h.push(atelRefRenduSequence(s));
  }
  h.push('</details>');

  // Évaluations (s'il y en a)
  const evals = trace.evaluations || [];
  if (evals.length > 0) {
    h.push(`<details><summary>Évaluations (${evals.length})</summary>`);
    h.push('<ul style="margin-left:1em">');
    for (const ev of evals) {
      h.push(`<li>#${ev.numero ?? '?'} ordre=${ev.ordre ?? '?'} — `
           + `<strong>${escHtml(ev.titre || '(sans titre)')}</strong></li>`);
    }
    h.push('</ul></details>');
  }

  // Documents — déjà rendus à part en liens PDF, mais on dump le JSON ici
  const documents = trace.documents || [];
  if (documents.length > 0) {
    h.push(`<details><summary>Documents (${documents.length})</summary>`);
    h.push('<ul style="margin-left:1em">');
    for (const d of documents) {
      h.push(`<li><strong>${escHtml(d.type_document)}</strong>`);
      if (d.provenance)
        h.push(` <span style="color:#888">[${escHtml(d.provenance)}]</span>`);
      const cibles = d.cibles || [];
      if (cibles.length) {
        h.push('<ul>');
        for (const c of cibles) {
          h.push(`<li>${escHtml(c.libelle || c.cible_id || '?')} — `
               + `<code>${escHtml(c.nom_fichier || '')}</code></li>`);
        }
        h.push('</ul>');
      }
      h.push('</li>');
    }
    h.push('</ul></details>');
  }

  h.push('</div>');
  return h.join('');
}


function atelRefRenduSequence(s) {
  const h = [];
  const numero = String(s.numero ?? '?').padStart(2, '0');
  h.push(`<details style="margin-left:1em;margin-bottom:4px">`);
  h.push(`<summary><strong>S${numero}</strong> — ${escHtml(s.nom)} `
       + `<span style="color:#888">[thème ${escHtml(s.theme_code)}]</span>`
       + `</summary>`);

  // Précédents
  const prec = s.precedents || [];
  if (prec.length > 0) {
    h.push(`<div style="margin-left:1em;margin-top:4px;color:#555">`);
    h.push(`<strong>Prérequis :</strong> `);
    h.push(prec.map(p => `${escHtml(p.niveau)}/${escHtml(p.sequence)}`).join(', '));
    h.push(`</div>`);
  }

  // Parties
  const parties = s.parties || [];
  for (const p of parties) {
    h.push(atelRefRenduPartie(p));
  }
  h.push('</details>');
  return h.join('');
}


function atelRefRenduPartie(p) {
  const h = [];
  h.push(`<details open style="margin-left:1em;margin-top:4px">`);
  h.push(`<summary><strong>Partie ${escHtml(p.numero)}</strong> `
       + `<span style="color:#888">(R/AE : ${p.nb_seances_R_AE ?? 0} séance(s))</span>`
       + `</summary>`);

  // Cartes d'automatisme de la partie
  const cartes = p.cartes_automatisme || [];
  if (cartes.length > 0) {
    h.push(`<details style="margin-left:1em">`);
    h.push(`<summary>Cartes d'automatisme (${cartes.length})</summary>`);
    h.push('<ul style="margin-left:1em">');
    for (const c of cartes) {
      h.push(`<li>#${escHtml(c.num)} `);
      if (c.type_pedago) h.push(`<span style="color:#888">[${escHtml(c.type_pedago)}]</span> `);
      h.push(`${escHtml(c.titre || '(sans titre)')}</li>`);
    }
    h.push('</ul></details>');
  }

  // Révisions (exercices_R)
  const exosR = p.exercices_R || [];
  if (exosR.length > 0) {
    h.push(`<details style="margin-left:1em">`);
    h.push(`<summary>Révisions (${exosR.length})</summary>`);
    h.push('<ul style="margin-left:1em">');
    for (const e of exosR) {
      h.push(`<li>${escHtml(e.niveau)}/${escHtml(e.sequence)} — `
           + `exo n°${escHtml(e.num)} série ${escHtml(e.serie)}`);
      if (e.titre) h.push(` — ${escHtml(e.titre)}`);
      h.push('</li>');
    }
    h.push('</ul></details>');
  }

  // Exos d'approche (exercices_AE)
  const exosAE = p.exercices_AE || [];
  if (exosAE.length > 0) {
    h.push(`<details style="margin-left:1em">`);
    h.push(`<summary>Approche (${exosAE.length})</summary>`);
    h.push('<ul style="margin-left:1em">');
    for (const e of exosAE) {
      h.push(`<li>${escHtml(e.niveau)}/${escHtml(e.sequence)} — `
           + `exo n°${escHtml(e.num)} série ${escHtml(e.serie)}`);
      if (e.titre) h.push(` — ${escHtml(e.titre)}`);
      h.push('</li>');
    }
    h.push('</ul></details>');
  }

  // Objectifs
  const objs = p.objectifs || [];
  if (objs.length > 0) {
    h.push(`<div style="margin-left:1em;margin-top:6px">`);
    h.push(`<strong>Objectifs (${objs.length})</strong>`);
    for (const o of objs) {
      h.push(atelRefRenduObjectif(o));
    }
    h.push(`</div>`);
  }

  h.push('</details>');
  return h.join('');
}


function atelRefRenduObjectif(o) {
  const h = [];
  // Résumé compact en summary
  const infos = [];
  if (o.methodes)      infos.push(`${o.methodes.length} méth`);
  if (o.notions)       infos.push(`${o.notions.length} not`);
  if (o.exercices)     infos.push(`${o.exercices.length} exo`);
  if (o.fiches_resume) infos.push(`${o.fiches_resume.length} fiche`);
  const tag = infos.length
    ? ` <span style="color:#888">(${infos.join(', ')})</span>`
    : '';
  h.push(`<details style="margin-left:1em;margin-top:2px">`);
  h.push(`<summary><strong>${escHtml(o.code)}</strong> — `
       + `${escHtml(o.nom)}${tag}</summary>`);

  // Critères F/A/E
  if (o.critere_f || o.critere_a || o.critere_e) {
    h.push(`<div style="margin-left:1em;margin-top:4px;font-size:11px">`);
    if (o.critere_f) h.push(`<div><strong>F</strong> (à consolider) : ${escHtml(o.critere_f)}</div>`);
    if (o.critere_a) h.push(`<div><strong>A</strong> (satisfaisant) : ${escHtml(o.critere_a)}</div>`);
    if (o.critere_e) h.push(`<div><strong>E</strong> (très bon) : ${escHtml(o.critere_e)}</div>`);
    h.push(`</div>`);
  }
  if (typeof o.nb_seances !== 'undefined') {
    h.push(`<div style="margin-left:1em;color:#888;font-size:11px">`
         + `Séances : ${escHtml(o.nb_seances)}`
         + (o.fin_cycle ? ' &middot; fin de cycle' : '')
         + `</div>`);
  }

  // Méthodes
  const meths = o.methodes;
  if (meths) {
    if (meths.length > 0) {
      h.push(`<div style="margin-left:1em;margin-top:4px">`);
      h.push(`<strong>Méthodes :</strong><ul>`);
      for (const m of meths) {
        h.push(`<li>n°${escHtml(m.num_methode)} — ${escHtml(m.titre || '(sans titre)')}</li>`);
      }
      h.push(`</ul></div>`);
    }
  }

  // Notions
  const nots = o.notions;
  if (nots && nots.length > 0) {
    h.push(`<div style="margin-left:1em">`);
    h.push(`<strong>Notions :</strong><ul>`);
    for (const n of nots) {
      h.push(`<li>n°${escHtml(n.num_connaissance)} — ${escHtml(n.titre || '(sans titre)')}</li>`);
    }
    h.push(`</ul></div>`);
  }

  // Exercices
  const exos = o.exercices;
  if (exos && exos.length > 0) {
    // Regrouper par série pour lisibilité
    const par_serie = { fondamental: [], 'avancé': [], exploration: [], autre: [] };
    for (const e of exos) {
      const s = e.serie || 'autre';
      (par_serie[s] || par_serie.autre).push(e);
    }
    h.push(`<div style="margin-left:1em">`);
    h.push(`<strong>Exercices :</strong>`);
    for (const [serie, liste] of Object.entries(par_serie)) {
      if (!liste.length) continue;
      const nums = liste.map(e =>
        e.titre
          ? `${escHtml(e.num)} <span style="color:#888">(${escHtml(e.titre)})</span>`
          : escHtml(e.num)
      ).join(', ');
      h.push(`<div style="margin-left:1em"><em>${serie}</em> : ${nums}</div>`);
    }
    h.push(`</div>`);
  }

  // Fiches de résumé (seulement pour l'objectif Cours, agrégées de la partie)
  const fiches = o.fiches_resume;
  if (fiches && fiches.length > 0) {
    h.push(`<div style="margin-left:1em">`);
    h.push(`<strong>Fiches de résumé :</strong><ul>`);
    for (const f of fiches) {
      h.push(`<li>n°${escHtml(f.num_fiche)} — ${escHtml(f.titre || '(sans titre)')}</li>`);
    }
    h.push(`</ul></div>`);
  }

  h.push('</details>');
  return h.join('');
}


function escHtml(s) {
  return String(s || '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[ch]);
}


// ── Section repliable d'une séquence ─────────────────────────────────────────

function atelRefBasculerSection(seqId) {
  const el = document.getElementById(seqId);
  if (!el) return;
  el.style.display = (el.style.display === 'none') ? '' : 'none';
}


// ── v0.13.6.4 ─ Onglet "Documents à publier" ─────────────────────────────────
//
// Le panneau liste les 9 types de documents publiables avec leurs options.
// Sauvegarde automatique à chaque onchange (PUT vers l'API).

const ATL_REF_DOC_TITRES = {
  'livret_sequence':         'Livret de séquence',
  'livret_exercices':        "Livret d'exercices",
  'livret_cours':            'Livret de cours',
  'livret_fiches':           'Livret de fiches de résumé',
  'livret_plans':            'Livret de plans de travail',
  'livret_corriges':         "Livret de corrigés d'exercices",
  'evaluation':              'Évaluations',
  'livret_cartes_recap':     "Récap des cartes d'automatisme",
  'livret_cartes_planches':  "Planches de cartes d'automatisme",
};

const ATL_REF_DOC_SOUS_TITRES = {
  'livret_sequence':        "Un livret par séquence (14 livrets). Mêmes options pour toutes les séquences.",
  'livret_exercices':       "Tous les exercices du niveau, organisés par séquence.",
  'livret_cours':           "Toutes les notions et méthodes du niveau, par séquence.",
  'livret_fiches':          "Toutes les fiches de résumé du niveau, par séquence.",
  'livret_plans':           "Plans de travail des séquences du niveau.",
  'livret_corriges':        "Tous les corrigés du niveau, organisés par séquence.",
  'evaluation':             "Une page par évaluation déclarée (options portées par chaque évaluation).",
  'livret_cartes_recap':    "Pour l'enseignant : 8 cartes par page, recto/verso à suivre.",
  'livret_cartes_planches': "Pour les élèves : 16 exemplaires par carte par feuille, recto puis verso.",
};


// Bascule entre les onglets Tableau de bord / Documents à publier.
function atelRefChangerOnglet(nom) {
  if (nom !== 'dashboard' && nom !== 'documents') return;
  ATL_REF_ONGLET_ACTIF = nom;

  document.querySelectorAll('.atl-ref-onglet').forEach(btn => {
    const actif = btn.dataset.tab === nom;
    btn.classList.toggle('is-actif', actif);
    btn.style.color = actif ? 'var(--primary)' : 'var(--text-secondary)';
    btn.style.borderBottomColor = actif ? 'var(--primary)' : 'transparent';
  });

  const panDash = document.getElementById('atl-ref-panneau-dashboard');
  const panDocs = document.getElementById('atl-ref-panneau-documents');
  if (panDash) panDash.style.display = (nom === 'dashboard') ? '' : 'none';
  if (panDocs) panDocs.style.display = (nom === 'documents') ? '' : 'none';

  if (nom === 'documents' && ATL_REF_SELECTION) {
    atelRefChargerEtRendreDocuments();
  }
}


async function atelRefChargerEtRendreDocuments() {
  const cont = document.getElementById('atl-ref-panneau-documents');
  if (!cont) return;
  cont.innerHTML = `
    <div class="atl-cadre" style="padding:24px;text-align:center;color:var(--text-muted)">
      Chargement des documents…
    </div>`;
  try {
    const rep = await fetch(
      `/api/referentiels/${encodeURIComponent(ATL_REF_SELECTION.id)}/documents`,
    );
    if (!rep.ok) {
      cont.innerHTML = `
        <div class="atl-cadre" style="padding:24px;text-align:center;color:#8b1a1a">
          Échec du chargement des documents.
        </div>`;
      return;
    }
    const data = await rep.json();
    ATL_REF_DOCUMENTS = data.documents || [];
    atelRefRendreDocuments();
  } catch (e) {
    console.error('[ref-documents] fetch error :', e);
    cont.innerHTML = `
      <div class="atl-cadre" style="padding:24px;text-align:center;color:#8b1a1a">
        Erreur réseau lors du chargement.
      </div>`;
  }
}


function atelRefRendreDocuments() {
  const cont = document.getElementById('atl-ref-panneau-documents');
  if (!cont) return;
  const editable = ATL_REF_SELECTION
                 && (ATL_REF_SELECTION.etat === 'en_cours'
                     || ATL_REF_SELECTION.etat === 'valide');
  const bandeauReadOnly = editable ? '' : `
    <div class="atl-cadre" style="margin-bottom:10px;padding:10px 14px;
         background:#fff5f0;border-left:3px solid #d97706">
      <span style="font-size:12px;color:#7c4a03">
        Ce référentiel est <strong>${atelRefEscape(ATL_REF_SELECTION ? ATL_REF_SELECTION.etat : '')}</strong>.
        Les options sont en lecture seule.
      </span>
    </div>`;

  const cadres = ATL_REF_DOCUMENTS
    .map(d => atelRefDocumentCadreHtml(d, editable))
    .join('');

  cont.innerHTML = `
    ${bandeauReadOnly}
    <div class="atl-cadre" style="margin-bottom:10px">
      <div class="atl-cadre-titre">Documents à publier</div>
      <div style="padding:8px;font-size:12px;color:var(--text-muted)">
        Coche les documents que tu veux produire avec ce référentiel et
        configure leurs options.
      </div>
    </div>
    ${cadres}`;
}


function atelRefDocumentCadreHtml(doc, editable) {
  const titre = ATL_REF_DOC_TITRES[doc.type_document] || doc.type_document;
  const soustitre = ATL_REF_DOC_SOUS_TITRES[doc.type_document] || '';
  const actif = !!doc.options.actif;

  const fond = actif ? '#f0f7f0' : 'var(--surface)';
  const bord = actif ? '#a5d6a7' : 'var(--border)';

  const optionsHtml = atelRefDocumentOptionsHtml(doc, editable);

  const disabled = editable ? '' : 'disabled';

  // v0.13.6.5.1 — Badge d'état effectif + bouton Tester + zone progression
  const etat = doc.etat_effectif || 'non_compile';
  const badge = atelRefBadgeEtat(etat);
  const boutonTester = (editable && actif)
    ? `<button class="btn-sm"
               onclick="atelRefCompilerDoc('${doc.id}')"
               ${etat === 'en_cours' ? 'disabled' : ''}
               style="font-size:11px;padding:2px 8px;margin-left:8px">
         ${etat === 'en_cours' ? 'Compilation…' : 'Tester'}
       </button>` : '';
  // Zone de progression : visible quand en cours
  const zoneProg = `
    <div id="atl-ref-doc-progress-${doc.id}" class="atl-ref-doc-progress"
         style="display:${etat === 'en_cours' ? 'block' : 'none'};
                padding:4px 12px 4px 30px;font-size:11px;
                color:var(--text-secondary)">
      <span class="atl-ref-doc-progress-etape">Initialisation…</span>
      <div style="margin-top:3px;height:4px;background:#e0e0e0;
                  border-radius:2px;overflow:hidden">
        <div class="atl-ref-doc-progress-bar"
             style="height:100%;width:0%;background:#3b82f6;
                    transition:width 0.3s ease"></div>
      </div>
    </div>`;

  // Lien vers PDF si compilé OK
  const lienPdf = (etat === 'ok' || etat === 'perime')
    ? atelRefLienPdf(doc) : '';

  // v0.13.6.5.1.1 — Bouton "Voir les erreurs" si état ko
  const boutonErreurs = (etat === 'ko')
    ? `<button class="btn-sm"
              onclick="atelRefBasculerErreurs('${doc.id}')"
              style="font-size:11px;padding:2px 8px;margin-left:4px">
         Voir les erreurs
       </button>`
    : '';

  // Zone du panneau d'erreurs (rempli à la demande)
  const zoneErreurs = `
    <div id="atl-ref-doc-erreurs-${doc.id}"
         style="display:none;padding:8px 12px 4px 30px"></div>`;

  return `
    <div class="atl-cadre atl-cadre--compact"
         style="margin-bottom:8px;background:${fond};border-color:${bord}">
      <div class="atl-cadre-titre"
           style="font-size:13px;display:flex;align-items:center;
                  flex-wrap:wrap;gap:6px">
        <label style="display:flex;align-items:center;gap:8px;
                      cursor:${editable ? 'pointer' : 'default'};flex:1">
          <input type="checkbox" ${actif ? 'checked' : ''} ${disabled}
                 onchange="atelRefMajOptionDoc('${doc.id}', 'actif', this.checked)">
          <strong>${atelRefEscape(titre)}</strong>
        </label>
        ${badge}
        ${boutonTester}
        ${boutonErreurs}
      </div>
      <div style="padding:6px 12px 4px 30px;font-size:11px;
                  color:var(--text-muted);font-style:italic">
        ${atelRefEscape(soustitre)}
        ${lienPdf}
      </div>
      ${zoneProg}
      ${zoneErreurs}
      ${optionsHtml}
    </div>`;
}


// v0.13.6.5.1 — Rendu du badge d'état effectif (5 cas).
function atelRefBadgeEtat(etat) {
  const styles = {
    'non_compile': { txt: 'Non compilé', bg: '#e0e0e0', fg: '#444' },
    'en_cours':    { txt: 'Compilation…', bg: '#bfdbfe', fg: '#1e40af' },
    'ko':          { txt: 'Erreur',     bg: '#fecaca', fg: '#7f1d1d' },
    'perime':      { txt: 'Périmé',     bg: '#fed7aa', fg: '#7c2d12' },
    'ok':          { txt: 'OK',         bg: '#bbf7d0', fg: '#14532d' },
  };
  const s = styles[etat] || styles.non_compile;
  return `<span style="display:inline-block;padding:2px 8px;border-radius:10px;
                       background:${s.bg};color:${s.fg};font-size:11px;
                       font-weight:600;white-space:nowrap">${s.txt}</span>`;
}


// v0.32.4 — Renvoie le(s) lien(s) vers le(s) PDF(s) compilé(s). La détection
// multi-cible est DYNAMIQUE (doc.cibles), pas par liste de types en dur : tout
// document ayant plusieurs cibles (livret_sequence, planches de cartes,
// évaluations…) affiche un lien par cible (avec ?cible=…), au lieu d'un lien
// direct qui échouerait (« cible requise »).
function atelRefLienPdf(doc) {
  const refId = ATL_REF_SELECTION.id;
  const docId = doc.id;
  const baseUrl = `/api/referentiels/${encodeURIComponent(refId)}`
                + `/documents/${encodeURIComponent(docId)}/pdf`;
  const cibles = doc.cibles || [];

  if (cibles.length > 1) {
    // Un lien par cible (chaque cible = une séquence en général).
    const liens = cibles.map(c => {
      const id = (typeof c === 'string') ? c : (c.cible_id || c.id || '');
      const lib = (typeof c === 'string') ? c : (c.libelle || c.cible_id || id);
      return `<a href="${baseUrl}?cible=${encodeURIComponent(id)}"
        target="_blank" rel="noopener"
        style="color:#1e40af;font-size:11px;margin:0 6px 0 0;white-space:nowrap">📄 ${escHtml(lib)}</a>`;
    }).join('');
    return `<span style="margin-left:8px;display:inline-flex;flex-wrap:wrap;gap:2px">${liens}</span>`;
  }
  // Une seule cible (ou aucune) : lien direct.
  let url = baseUrl;
  if (cibles.length === 1) {
    const c = cibles[0];
    const id = (typeof c === 'string') ? c : (c.cible_id || c.id || '');
    if (id) url = `${baseUrl}?cible=${encodeURIComponent(id)}`;
  }
  return `
    <a href="${url}" target="_blank" rel="noopener"
       style="margin-left:8px;color:#1e40af">📄 Voir le PDF</a>`;
}


// v0.13.6.5.1 — Lance la compilation et démarre le polling de progression.
async function atelRefCompilerDoc(docId) {
  if (!ATL_REF_SELECTION) return;
  const refId = ATL_REF_SELECTION.id;

  // Lancement
  try {
    const rep = await fetch(
      `/api/referentiels/${encodeURIComponent(refId)}`
      + `/documents/${encodeURIComponent(docId)}/compiler`,
      { method: 'POST' },
    );
    if (!rep.ok) {
      const err = await rep.json().catch(() => ({}));
      alert(`Échec du lancement : ${err.message || rep.status}`);
      return;
    }
  } catch (e) {
    console.error('[compiler] erreur lancement :', e);
    alert("Erreur réseau au lancement de la compilation.");
    return;
  }

  // Maj UI immédiat : badge → en_cours, zone de progression visible
  const doc = ATL_REF_DOCUMENTS.find(d => d.id === docId);
  if (doc) {
    doc.etat_effectif = 'en_cours';
    doc.compile_en_cours = true;
  }
  atelRefRendreDocuments();

  // Polling
  _atlRefDemarrerPolling(docId);
}


// État du polling actif : un setInterval id par doc en cours.
const ATL_REF_POLLING = {};


// v0.13.6.5.1.1 — Ouvre/ferme le panneau d'erreurs d'un document.
//
// Le panneau est rempli à la demande à partir des données de compile_log
// (JSON) déjà chargées dans ATL_REF_DOCUMENTS. Le module
// compilation_erreurs.js gère le rendu et les boutons "Voir .tex" /
// "Voir log".
function atelRefBasculerErreurs(docId) {
  const zone = document.getElementById(`atl-ref-doc-erreurs-${docId}`);
  if (!zone) return;
  if (zone.style.display === 'none') {
    _atlRefOuvrirErreurs(docId, zone);
  } else {
    zone.style.display = 'none';
    if (typeof compErreursFermer === 'function') {
      compErreursFermer(`atl-ref-doc-erreurs-${docId}__panel`);
    }
  }
}


async function _atlRefOuvrirErreurs(docId, zone) {
  const doc = ATL_REF_DOCUMENTS.find(d => d.id === docId);
  if (!doc) return;
  const refId = ATL_REF_SELECTION.id;

  zone.style.display = '';
  zone.innerHTML = `
    <div id="atl-ref-doc-erreurs-${docId}__panel">
      <div style="padding:10px;color:var(--text-muted);font-size:11px">
        Chargement du panneau d'erreurs…
      </div>
    </div>`;

  // Le compile_log côté serveur est un JSON v0.13.6.5.1.1 :
  // {version:'1', type_document, cibles:[{cible_id, libelle, ok, ...}, ...]}
  // On le récupère depuis l'API statut (toujours frais) ou depuis
  // compile_log de notre cache local ATL_REF_DOCUMENTS.
  let logData = null;
  try {
    // Préférer une lecture serveur fraîche
    const rep = await fetch(
      `/api/referentiels/${encodeURIComponent(refId)}`
      + `/documents/${encodeURIComponent(docId)}/compiler/statut`,
    );
    if (rep.ok) {
      const d = await rep.json();
      const logBdd = d.bdd && d.bdd.compile_log;
      if (logBdd) {
        try {
          logData = JSON.parse(logBdd);
        } catch (e) {
          // Pas un JSON (peut arriver si v0.13.6.5.1 brut avant migration)
          logData = null;
        }
      }
    }
  } catch (e) {
    console.warn('[ref-documents] erreur chargement statut :', e);
  }

  if (!logData || !Array.isArray(logData.cibles)) {
    zone.innerHTML = `
      <div id="atl-ref-doc-erreurs-${docId}__panel">
        <div style="padding:10px;color:#7c2d12;font-size:11px;
                    background:#fff5f5;border:1px solid #fecaca;border-radius:4px">
          Pas d'information détaillée d'erreur disponible.
          ${doc.compile_log ? '<br><br><pre style="white-space:pre-wrap;font-size:10px">'
            + (doc.compile_log.length > 1000 ? doc.compile_log.slice(0, 1000) + '…' : doc.compile_log)
            + '</pre>' : ''}
        </div>
      </div>`;
    return;
  }

  // Confier le rendu au module compilation_erreurs.js
  const contexte = {
    titre:     'Erreurs de compilation',
    sousTitre: ATL_REF_DOC_TITRES[doc.type_document] || doc.type_document,
    cibles:    logData.cibles,
    texUrl: (cibleId) => {
      const qs = encodeURIComponent(cibleId);
      return `/api/referentiels/${encodeURIComponent(refId)}`
           + `/documents/${encodeURIComponent(docId)}/tex?cible=${qs}`;
    },
    logUrl: (cibleId) => {
      const qs = encodeURIComponent(cibleId);
      return `/api/referentiels/${encodeURIComponent(refId)}`
           + `/documents/${encodeURIComponent(docId)}/log?cible=${qs}`;
    },
  };

  if (typeof compErreursAfficher === 'function') {
    compErreursAfficher(`atl-ref-doc-erreurs-${docId}__panel`, contexte);
  } else {
    zone.innerHTML = `
      <div style="padding:10px;color:#7c2d12">
        Module compilation_erreurs.js non chargé.
      </div>`;
  }
}


function _atlRefDemarrerPolling(docId) {
  // Arrêter un polling précédent si présent
  if (ATL_REF_POLLING[docId]) {
    clearInterval(ATL_REF_POLLING[docId]);
  }
  const refId = ATL_REF_SELECTION.id;
  ATL_REF_POLLING[docId] = setInterval(async () => {
    try {
      const rep = await fetch(
        `/api/referentiels/${encodeURIComponent(refId)}`
        + `/documents/${encodeURIComponent(docId)}/compiler/statut`,
      );
      if (!rep.ok) {
        clearInterval(ATL_REF_POLLING[docId]);
        delete ATL_REF_POLLING[docId];
        return;
      }
      const data = await rep.json();
      _atlRefMajProgress(docId, data);

      const enCoursMem = data.statut && data.statut.en_cours;
      const enCoursBdd = data.bdd && data.bdd.compile_en_cours;
      if (!enCoursMem && !enCoursBdd) {
        clearInterval(ATL_REF_POLLING[docId]);
        delete ATL_REF_POLLING[docId];
        // Recharger la liste complète des documents pour avoir les
        // colonnes compile_* à jour et l'état effectif recalculé.
        atelRefChargerEtRendreDocuments();
      }
    } catch (e) {
      console.error('[poll] erreur :', e);
    }
  }, 700);
}


function _atlRefMajProgress(docId, data) {
  const cont = document.getElementById(`atl-ref-doc-progress-${docId}`);
  if (!cont) return;
  const statut = data.statut;
  if (!statut) return;

  const total = statut.total || 1;
  const fait = statut.fait || 0;
  const pct = Math.min(100, Math.round(100 * fait / total));

  // v0.15.2.6 — Suffixe « (page N) » quand pdflatex a déjà shippé une page
  // de la cible courante. Donne un signal de vie ~à chaque seconde pendant
  // les 25-30s que dure une cible (sinon la barre ne bouge que tous les
  // 25-30s, ce qui est trop lent pour rassurer l'utilisateur).
  //
  // v0.15.2.8 — Préfixé par « passe N/M » quand pdflatex est en cours de
  // compilation. Le total M reste constant (2 actuellement, exposé par
  // statut.passes_total). Affichage final : « passe 2/2, page 47 ».
  let suffixeProgression = '';
  if (statut.passe_courante && statut.passes_total) {
    suffixeProgression = ` (passe ${statut.passe_courante}/${statut.passes_total}`;
    if (statut.page_courante && statut.page_courante > 0) {
      suffixeProgression += `, page ${statut.page_courante}`;
    }
    suffixeProgression += ')';
  } else if (statut.page_courante && statut.page_courante > 0) {
    // Fallback : page connue mais pas la passe (cas test ou compat).
    suffixeProgression = ` (page ${statut.page_courante})`;
  }

  const span = cont.querySelector('.atl-ref-doc-progress-etape');
  const bar  = cont.querySelector('.atl-ref-doc-progress-bar');
  if (span) {
    if (total > 1) {
      span.textContent = `${fait}/${total} — ${statut.etape_courante || ''}${suffixeProgression}`;
    } else {
      span.textContent = `${statut.etape_courante || 'En cours…'}${suffixeProgression}`;
    }
  }
  if (bar) bar.style.width = `${pct}%`;
}


function atelRefDocumentOptionsHtml(doc, editable) {
  const type = doc.type_document;
  const opts = doc.options || {};
  const actif = !!opts.actif;
  const disabled = (editable && actif) ? '' : 'disabled';
  const opacity = actif ? '1' : '0.5';

  // Pour livret_sequence : selon le radio "contenu", les options de
  // cours et/ou exercices doivent être masquées.
  const inclureCours = (type === 'livret_sequence')
    ? (opts.contenu !== 'exercices_seul')
    : true;
  const inclureExos  = (type === 'livret_sequence')
    ? (opts.contenu !== 'cours_seul')
    : true;

  let inner = '';
  if (type === 'livret_sequence') {
    const blocCours = inclureCours ? `
      <div style="margin-top:6px;font-size:11px;color:var(--text-muted);font-weight:600">
        Partie cours :
      </div>
      ${_atlRefRadio(doc.id, 'inclure_fiches_resume_en_fin',
                     opts.inclure_fiches_resume_en_fin,
                     'Fiches de résumé en fin de livret',
                     [['non', '(aucune)'],
                      ['completes', 'complètes'],
                      ['a_completer', 'à compléter']],
                     disabled)}
    ` : '';
    const blocExos = inclureExos ? `
      <div style="margin-top:6px;font-size:11px;color:var(--text-muted);font-weight:600">
        Partie exercices :
      </div>
      ${_atlRefCb(doc.id, 'inclure_enonces_serie_a',
                  opts.inclure_enonces_serie_a,
                  "Inclure les énoncés de la série A (entre F et E)", disabled)}
      <div style="margin-top:4px;font-size:11px;color:var(--text-muted);font-weight:600">
        Corrigés inclus :
      </div>
      ${_atlRefCb(doc.id, 'inclure_corriges_serie_r_ae',
                  opts.inclure_corriges_serie_r_ae,
                  'Série R/AE', disabled)}
      ${_atlRefCb(doc.id, 'inclure_corriges_serie_f',
                  opts.inclure_corriges_serie_f, 'Série F', disabled)}
      ${_atlRefCb(doc.id, 'inclure_corriges_serie_a',
                  opts.inclure_corriges_serie_a, 'Série A', disabled)}
      ${_atlRefCb(doc.id, 'inclure_corriges_serie_e',
                  opts.inclure_corriges_serie_e, 'Série E', disabled)}
      ${_atlRefCb(doc.id, 'inclure_corriges_remediation',
                  opts.inclure_corriges_remediation,
                  'Corrigés de remédiation', disabled)}
    ` : '';
    inner = `
      ${_atlRefRadio(doc.id, 'contenu', opts.contenu,
                     'Contenu du livret',
                     [['cours_et_exercices', 'Cours et exercices'],
                      ['cours_seul', 'Cours uniquement'],
                      ['exercices_seul', 'Exercices uniquement']],
                     disabled)}
      ${_atlRefCb(doc.id, 'inclure_plan_travail_en_tete',
                  opts.inclure_plan_travail_en_tete,
                  'Plan de travail en première page', disabled)}
      ${blocCours}
      ${blocExos}
    `;
  } else if (type === 'livret_exercices') {
    inner = `
      <div style="margin-top:6px;font-size:11px;color:var(--text-muted);font-weight:600">
        Énoncés inclus :
      </div>
      ${_atlRefCb(doc.id, 'enonces_r_ae', opts.enonces_r_ae, 'Série R/AE', disabled)}
      ${_atlRefCb(doc.id, 'enonces_f', opts.enonces_f, 'Série F', disabled)}
      ${_atlRefCb(doc.id, 'enonces_a', opts.enonces_a, 'Série A', disabled)}
      ${_atlRefCb(doc.id, 'enonces_e', opts.enonces_e, 'Série E', disabled)}
      ${_atlRefCb(doc.id, 'enonces_remediation', opts.enonces_remediation,
                  'Exercices de remédiation', disabled)}
      <div style="margin-top:6px;font-size:11px;color:var(--text-muted);font-weight:600">
        Corrigés inclus :
      </div>
      ${_atlRefCb(doc.id, 'corriges_r_ae', opts.corriges_r_ae, 'Série R/AE', disabled)}
      ${_atlRefCb(doc.id, 'corriges_f', opts.corriges_f, 'Série F', disabled)}
      ${_atlRefCb(doc.id, 'corriges_a', opts.corriges_a, 'Série A', disabled)}
      ${_atlRefCb(doc.id, 'corriges_e', opts.corriges_e, 'Série E', disabled)}
      ${_atlRefCb(doc.id, 'corriges_remediation', opts.corriges_remediation,
                  'Corrigés de remédiation', disabled)}
    `;
  } else if (type === 'livret_cours') {
    inner = `
      ${_atlRefRadio(doc.id, 'inclure_fiches_resume_en_fin',
                     opts.inclure_fiches_resume_en_fin,
                     'Fiches de résumé en fin de livret',
                     [['non', '(aucune)'],
                      ['completes', 'complètes'],
                      ['a_completer', 'à compléter']],
                     disabled)}
    `;
  } else if (type === 'livret_fiches') {
    inner = `
      ${_atlRefRadio(doc.id, 'version_fiches', opts.version_fiches,
                     'Version des fiches',
                     [['completes', 'complètes'],
                      ['a_completer', 'à compléter']],
                     disabled)}
      ${_atlRefRadio(doc.id, 'decoupage_fiches', opts.decoupage_fiches || 'annuel',
                     'Découpage',
                     [['annuel', 'un livret annuel'],
                      ['par_sequence', 'un livret par séquence'],
                      ['les_deux', 'les deux']],
                     disabled)}
    `;
  } else if (type === 'livret_corriges') {
    inner = `
      <div style="margin-top:6px;font-size:11px;color:var(--text-muted);font-weight:600">
        Séries incluses :
      </div>
      ${_atlRefCb(doc.id, 'inclure_serie_r_ae', opts.inclure_serie_r_ae,
                  'Série R/AE', disabled)}
      ${_atlRefCb(doc.id, 'inclure_serie_f', opts.inclure_serie_f,
                  'Série F', disabled)}
      ${_atlRefCb(doc.id, 'inclure_serie_a', opts.inclure_serie_a,
                  'Série A', disabled)}
      ${_atlRefCb(doc.id, 'inclure_serie_e', opts.inclure_serie_e,
                  'Série E', disabled)}
    `;
  }

  if (!inner.trim()) return '';
  return `
    <div style="padding:4px 12px 10px 30px;opacity:${opacity}">
      ${inner}
    </div>`;
}


function _atlRefCb(docId, cle, val, libelle, disabled) {
  return `
    <label style="display:flex;align-items:center;gap:6px;margin:3px 0;
                  font-size:12px;cursor:${disabled ? 'default' : 'pointer'}">
      <input type="checkbox" ${val ? 'checked' : ''} ${disabled}
             onchange="atelRefMajOptionDoc('${docId}', '${cle}', this.checked)">
      <span>${atelRefEscape(libelle)}</span>
    </label>`;
}


function _atlRefRadio(docId, cle, valActuelle, libelle, options, disabled) {
  const radios = options.map(([val, lib]) => `
    <label style="display:inline-flex;align-items:center;gap:4px;
                  margin-right:14px;font-size:12px;
                  cursor:${disabled ? 'default' : 'pointer'}">
      <input type="radio" name="${docId}_${cle}" value="${val}"
             ${valActuelle === val ? 'checked' : ''} ${disabled}
             onchange="atelRefMajOptionDoc('${docId}', '${cle}', '${val}')">
      <span>${atelRefEscape(lib)}</span>
    </label>`).join('');
  return `
    <div style="margin:6px 0;font-size:12px">
      <div style="color:var(--text-muted);margin-bottom:2px">
        ${atelRefEscape(libelle)} :
      </div>
      <div style="padding-left:4px">${radios}</div>
    </div>`;
}


async function atelRefMajOptionDoc(docId, cle, valeur) {
  if (!ATL_REF_SELECTION) return;
  const payload = { options: { [cle]: valeur } };
  try {
    const rep = await fetch(
      `/api/referentiels/${encodeURIComponent(ATL_REF_SELECTION.id)}`
      + `/documents/${encodeURIComponent(docId)}`,
      {
        method:  'PUT',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(payload),
      });
    if (!rep.ok) {
      const err = await rep.json().catch(() => ({}));
      console.error('[ref-documents] PUT échec :', err);
      alert(`Erreur lors de la mise à jour de l'option : ${err.message || rep.status}`);
      atelRefChargerEtRendreDocuments();
      return;
    }
    const data = await rep.json();
    const doc = data.document;
    const i = ATL_REF_DOCUMENTS.findIndex(d => d.id === doc.id);
    if (i >= 0) ATL_REF_DOCUMENTS[i] = doc;
    atelRefRendreDocuments();
  } catch (e) {
    console.error('[ref-documents] PUT erreur :', e);
    alert('Erreur réseau lors de la mise à jour.');
  }
}


// ── Helpers ──────────────────────────────────────────────────────────────────

function atelRefEscape(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}


// Exposition globale pour l'orchestration depuis app.js
window.atelRefInit          = atelRefInit;
window.atelRefSelectionner  = atelRefSelectionner;
window.atelRefCreerCoquille = atelRefCreerCoquille;
window.atelRefSupprimer     = atelRefSupprimer;
window.atelRefFiger         = atelRefFiger;
window.atelRefBasculerSection = atelRefBasculerSection;

// v0.13.6.4 — Onglets et documents publiables
window.atelRefChangerOnglet  = atelRefChangerOnglet;
window.atelRefMajOptionDoc   = atelRefMajOptionDoc;

// v0.13.6.5.1 — Compilation des documents publiables
window.atelRefCompilerDoc    = atelRefCompilerDoc;

// v0.13.6.5.1.1 — Panneau d'erreurs des documents publiables
window.atelRefBasculerErreurs = atelRefBasculerErreurs;
