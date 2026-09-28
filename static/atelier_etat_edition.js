/* static/atelier_etat_edition.js — v0.10.4 (corrigé v0.10.4.1)
 *
 * Gestion de l'état d'édition des atomes (notion, méthode, exercice)
 * dans les ateliers correspondants.
 *
 * Fonctions exposées globalement (window.*) :
 *   atelAtomeRafraichirBadge(type, atomeActif)
 *                                    — bouton "Valider/Repasser en cours"
 *                                      L'appelant fournit l'atome actif car
 *                                      `let ATL_EXERCICE_ACTIF` n'est PAS exposé
 *                                      sur window (let top-level ≠ var).
 *   atelAtomeBasculerValidation(type, atomeActif, listeAtomes)
 *                                    — bascule l'état (avec confirm())
 *   atelAtomeFiltrerEtat(type, btn, etat)
 *                                    — filtre dans la liste latérale
 *
 * Variables d'état :
 *   ATL_FILTRE_ETAT.<type>           — '' (tous), 'en_cours', 'valide'
 */

// État global du filtre par atelier
window.ATL_FILTRE_ETAT = {
  notion:       '',
  methode:      '',
  exercice:     '',
  // v0.11.1 — Atelier Fiche de résumé. Le code-type côté DOM/UI est
  // `fiche_resume` (cohérent avec entite_type côté table atome_sections
  // et avec le type accepté par routes/etats_edition.py via
  // services/etats_edition.py::TABLES_PAR_TYPE).
  fiche_resume: '',
};

// Mapping type → préfixe DOM des éléments toolbar
const _ATL_ETAT_PREFIXES = {
  notion:       'atl-notion',
  methode:      'atl-methode',
  exercice:     'atl-exercice',
  // v0.11.1 — préfixe DOM de la toolbar fiche.
  fiche_resume: 'atl-fiche',
};

// Mapping type → fonction de rendu de la liste latérale
// (résolue à l'usage via window pour éviter les ordres de chargement).
const _ATL_ETAT_RENDU_LISTE = {
  notion:       'atelRenderNotionListe',
  methode:      'atelRenderMethodeListe',
  exercice:     'atelRenderListe',
  // v0.11.1 — la liste fiche est rendue par atelFicheRenderListe
  // (cf. static/atelier_fiche.js).
  fiche_resume: 'atelFicheRenderListe',
};

// Libellé court d'un état pour le badge
function _atelAtomeLibelleEtat(code) {
  if (code === 'valide') return 'Validé';
  if (code === 'en_cours') return 'En cours';
  return code || 'En cours';
}

// Met à jour le badge et le bouton Valider de l'atelier <type>.
//
// `atomeActif` : objet de l'atome ouvert dans le formulaire, ou null.
// L'appelant DOIT le fournir car les variables `let ATL_*_ACTIF` au
// top-level d'app.js ne sont pas exposées sur window (différence
// `let` vs `var`).
window.atelAtomeRafraichirBadge = function (type, atomeActif) {
  const prefixe = _ATL_ETAT_PREFIXES[type];
  if (!prefixe) {
    console.warn('[etat_edition] Type inconnu :', type);
    return;
  }
  const badge = document.getElementById(`${prefixe}-etat-badge`);
  const bouton = document.getElementById(`${prefixe}-btn-valider`);
  if (!badge || !bouton) {
    console.warn('[etat_edition] Élément DOM introuvable pour', type,
                 '— badge:', !!badge, 'bouton:', !!bouton);
    return;
  }

  // Pas d'atome actif (ou nouveau pas encore enregistré) → cacher
  if (!atomeActif || !atomeActif.id) {
    badge.style.display = 'none';
    bouton.style.display = 'none';
    return;
  }
  const etat = atomeActif.etat_code || 'en_cours';
  badge.textContent = _atelAtomeLibelleEtat(etat);
  badge.className = `atome-etat-badge atome-etat--${etat}`;
  // v0.10.4.2 — Forcer display via setProperty pour contourner toute
  // règle CSS hostile éventuelle (au cas où un display:none aurait été
  // écrit en !important dans une règle utilisateur).
  badge.style.setProperty('display', 'inline-block', 'important');
  if (etat === 'valide') {
    bouton.textContent = 'Repasser en cours';
    bouton.title = 'Marquer cet atome comme "en cours" d\'édition';
  } else {
    bouton.textContent = 'Valider';
    bouton.title = 'Valider cet atome pour autoriser la génération définitive';
  }
  bouton.style.setProperty('display', 'inline-block', 'important');
};

// Bascule l'état (en_cours ↔ valide). Confirme avant validation (Q2-M).
//
// `atomeActif`  : objet de l'atome ouvert. Sera muté localement.
// `listeAtomes` : tableau cache (ATL_EXO/ATL_NOTIONS/ATL_METHODES). Le
//                 tableau est aussi muté en place pour synchroniser le
//                 cache utilisé par le rendu de la liste latérale.
window.atelAtomeBasculerValidation = async function (type, atomeActif, listeAtomes) {
  if (!atomeActif || !atomeActif.id) return;
  const etatActuel = atomeActif.etat_code || 'en_cours';
  const cible = (etatActuel === 'valide') ? 'en_cours' : 'valide';

  // v0.11.1.x — Plus de confirmation à la validation : la bascule est
  // réversible (le bouton « Repasser en cours » fait l'opération inverse
  // sans confirmation), donc le confirm intermédiaire n'apportait rien.
  // L'utilisateur peut revenir en arrière en un clic.

  try {
    const r = await fetch(
      `/api/atomes/${encodeURIComponent(type)}/${encodeURIComponent(atomeActif.id)}/etat`,
      {
        method: 'PATCH',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({etat_code: cible}),
      },
    );
    if (!r.ok) {
      const data = await r.json().catch(() => ({}));
      alert(`Erreur de changement d'état : ${data.error || r.status}`);
      return;
    }
    // Mettre à jour l'objet local
    atomeActif.etat_code = cible;
    // Mettre à jour la liste cache
    if (listeAtomes && Array.isArray(listeAtomes)) {
      const item = listeAtomes.find(x => x.id === atomeActif.id);
      if (item) item.etat_code = cible;
    }
    // Refresh UI : badge dans la toolbar
    window.atelAtomeRafraichirBadge(type, atomeActif);
    // Refresh UI : liste latérale
    const fnRender = _ATL_ETAT_RENDU_LISTE[type];
    if (fnRender && typeof window[fnRender] === 'function') {
      window[fnRender]();
    }
    // Toast de confirmation (si dispo)
    if (typeof window.atelToast === 'function') {
      window.atelToast(cible === 'valide' ? 'Atome validé.' : 'Atome repassé en cours.');
    }
  } catch (e) {
    alert(`Erreur réseau : ${e.message}`);
  }
};

// Filtre la liste latérale par état d'édition. Mémorise dans
// ATL_FILTRE_ETAT[type] et appelle le re-rendu de la BONNE liste
// (différent par atelier — fix v0.10.4.1).
window.atelAtomeFiltrerEtat = function (type, btn, etat) {
  if (!_ATL_ETAT_PREFIXES[type]) return;
  window.ATL_FILTRE_ETAT[type] = etat || '';
  // Mettre à jour la classe active sur les boutons de filtre du même groupe
  if (btn && btn.parentElement) {
    btn.parentElement.querySelectorAll('.exo-etat').forEach(b => {
      b.classList.toggle('active', b === btn);
    });
  }
  // Déclencher le rendu de la liste correspondant à l'atelier visé.
  // Bug v0.10.4 : on appelait `atelRenderListe()` qui ne rend que la liste
  // exercice, donc le filtre ne marchait que là.
  const fnRender = _ATL_ETAT_RENDU_LISTE[type];
  if (fnRender && typeof window[fnRender] === 'function') {
    window[fnRender]();
  }
};

// v0.31.0 — Filtre « non rattachés » (atomes sans lien vers un objectif).
// Toggle : un clic active, un second désactive. Piloté globalement par
// window.ATL_FILTRE_RATTACHEMENT ('non_rattache' | ''). Re-rend la bonne liste.
const _ATL_RENDU_LISTE_TOUS = {
  notion: 'atelRenderNotionListe', methode: 'atelRenderMethodeListe',
  exercice: 'atelRenderListe', fiche_resume: 'atelFicheRenderListe',
  carte: 'atelCarteRendreSidebar',
};
window.atelAtomeFiltrerRattachement = function (type, btn) {
  const actif = window.ATL_FILTRE_RATTACHEMENT === 'non_rattache';
  window.ATL_FILTRE_RATTACHEMENT = actif ? '' : 'non_rattache';
  if (btn) btn.classList.toggle('active', !actif);
  const fnRender = _ATL_RENDU_LISTE_TOUS[type];
  if (fnRender && typeof window[fnRender] === 'function') {
    window[fnRender]();
  }
};

// Helper exporté : renvoie true si l'atome doit être affiché compte tenu
// du filtre par état actuel pour le type donné.
window.atelAtomeFiltreEtat_OK = function (type, atome) {
  const filtre = (window.ATL_FILTRE_ETAT && window.ATL_FILTRE_ETAT[type]) || '';
  if (!filtre) return true;  // "Tous"
  const etat = (atome && atome.etat_code) || 'en_cours';
  return etat === filtre;
};

// Helper : badge HTML pour la liste latérale (à inclure dans le rendu
// d'un item de liste).
window.atelAtomeBadgeListeHtml = function (atome) {
  const etat = (atome && atome.etat_code) || 'en_cours';
  if (etat === 'valide') {
    return `<span class="atl-list-item-etat atome-etat--valide">Validé</span>`;
  }
  // Pas de badge si en_cours (état par défaut, on évite la pollution visuelle)
  return '';
};
