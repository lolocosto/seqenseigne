/**
 * static/seqniv_pur.js — v0.16.6
 *
 * Logique PURE de l'atelier d'assemblage séquence-niveau, extraite de
 * `atelier_seqniv_assemblage.js` pour être testable unitairement (Vitest).
 *
 * Ces fonctions sont DÉTERMINISTES : pas de DOM, pas de fetch, pas d'état
 * global mutable. Elles reçoivent les données (`data` = réponse
 * GET /api/v2/sequences-par-niveau/...) en argument explicite, au lieu de lire
 * la variable module `DATA` comme dans le fichier procédural historique.
 *
 * Chargement : script classique (comme le reste du projet, pas de bundler).
 * Exposé sur `window.SeqnivPur`. Le fichier procédural
 * `atelier_seqniv_assemblage.js` délègue à ces fonctions (comportement
 * identique). Les tests (tests_js/seqniv_pur.test.js) lisent window.SeqnivPur.
 *
 * v0.16.6 — étape « extraire + tester la logique pure » du chantier de
 * migration OO du seqniv (la classe AtelierSeqnivAssemblage viendra ensuite et
 * réutilisera ce module).
 */
(function (root) {
  'use strict';

  // ── Échappement HTML ───────────────────────────────────────────────────────

  function esc(s) {
    if (s === null || s === undefined) return '';
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function escAttr(s) { return esc(s); }

  // ── Placements (exoId/notionId/methodeId → où l'élément est placé) ──────────

  /** Map exoId → liste de codes d'objectifs où il est placé (séries F/A/E). */
  function placementsExos(data) {
    const m = new Map();
    for (const p of ((data && data.parties) || [])) {
      for (const o of (p.objectifs || [])) {
        const eps = o.exos_par_serie || {};
        for (const s of ['F', 'A', 'E']) {
          for (const e of (eps[s] || [])) {
            const arr = m.get(e.exercice_id) || [];
            arr.push(o.code);
            m.set(e.exercice_id, arr);
          }
        }
      }
    }
    return m;
  }

  /** Map exoId → "P{N} R" ou "P{N} EA" (R et EA au niveau partie). */
  function placementsExosRA(data) {
    const m = new Map();
    for (const p of ((data && data.parties) || [])) {
      const ra = p.exos_revision_approche || { R: [], EA: [] };
      for (const e of (ra.EA || [])) {
        if (!m.has(e.exercice_id)) m.set(e.exercice_id, `P${p.numero} EA`);
      }
      for (const e of (ra.R || [])) {
        if (!m.has(e.exercice_id)) m.set(e.exercice_id, `P${p.numero} R`);
      }
    }
    return m;
  }

  /** Map notionId → liste de codes d'objectifs où elle est placée. */
  function placementsNotions(data) {
    const m = new Map();
    for (const p of ((data && data.parties) || [])) {
      for (const o of (p.objectifs || [])) {
        for (const n of (o.notions || [])) {
          const arr = m.get(n.id) || [];
          arr.push(o.code);
          m.set(n.id, arr);
        }
      }
    }
    return m;
  }

  /** Map methodeId → "P{N}/{code}" (1 méthode ↔ 1 objectif max). */
  function placementsMethodes(data) {
    const m = new Map();
    for (const p of ((data && data.parties) || [])) {
      for (const o of (p.objectifs || [])) {
        if (o.methode_id) m.set(o.methode_id, `P${p.numero}/${o.code}`);
      }
    }
    return m;
  }

  // ── Calculs ─────────────────────────────────────────────────────────────────

  /** Total des séances d'une partie : R+AE de la partie + somme des objectifs. */
  function calculerTotalSeancesPartie(p) {
    let total = Number(p.nb_seances_R_AE) || 0;
    for (const o of (p.objectifs || [])) {
      total += Number(o.nb_seances) || 0;
    }
    return total;
  }

  /** Index d'un objectif dans sa partie (-1 si absent). */
  function indexObjDansPartie(partie, objId) {
    const objs = partie.objectifs || [];
    return objs.findIndex(o => o.id === objId);
  }

  // ── Recherche dans l'arbre DATA ─────────────────────────────────────────────

  function trouverObj(data, objId) {
    for (const p of ((data && data.parties) || [])) {
      for (const o of (p.objectifs || [])) {
        if (o.id === objId) return o;
      }
    }
    return null;
  }

  function trouverPartie(data, partieId) {
    for (const p of ((data && data.parties) || [])) {
      if (p.id === partieId) return p;
    }
    return null;
  }

  /** Retourne la partie contenant l'objectif (l'objet partie), ou null. */
  function trouverPartiePourObj(data, objId) {
    for (const p of ((data && data.parties) || [])) {
      const objs = p.objectifs || [];
      if (objs.some(o => o.id === objId)) return p;
    }
    return null;
  }

  /** Retourne l'ID de la partie contenant l'objectif, ou null. */
  function trouverPartieDeObj(data, objId) {
    for (const p of ((data && data.parties) || [])) {
      for (const o of (p.objectifs || [])) {
        if (o.id === objId) return p.id;
      }
    }
    return null;
  }

  // ── Formatage des séances ────────────────────────────────────────────────────

  /**
   * Formate pour l'attribut value d'un <input type=number> : 0/null → ''
   * (placeholder visible), sinon le nombre avec un point décimal.
   */
  function fmtSeances(n) {
    if (n === null || n === undefined) return '';
    const f = Number(n);
    if (!Number.isFinite(f) || f === 0) return '';
    return String(f);
  }

  /** Formate pour l'affichage (texte) : null → '0', décimal avec virgule. */
  function fmtSeancesAffichage(n) {
    if (n === null || n === undefined) return '0';
    const f = Number(n);
    if (!Number.isFinite(f)) return '0';
    if (Number.isInteger(f)) return String(f);
    return String(f).replace('.', ',');
  }

  // ── Couleur de thème ─────────────────────────────────────────────────────────

  function couleurTheme(code) {
    const map = {
      'nombres':     '#1d5fa8',
      'grandeurs':   '#5a8a1a',
      'geometrie':   '#5b4ab3',
      'donnees':     '#d97706',
      'algorithmes': '#0f766e',
    };
    return map[code] || '#475569';
  }

  // ── Exposition ───────────────────────────────────────────────────────────────

  const SeqnivPur = {
    esc, escAttr,
    placementsExos, placementsExosRA, placementsNotions, placementsMethodes,
    calculerTotalSeancesPartie, indexObjDansPartie,
    trouverObj, trouverPartie, trouverPartiePourObj, trouverPartieDeObj,
    fmtSeances, fmtSeancesAffichage, couleurTheme,
  };

  // Navigateur : window.SeqnivPur. (Pas d'export ES : le projet charge tout en
  // <script> classique. Les tests Vitest lisent window.SeqnivPur via jsdom.)
  root.SeqnivPur = SeqnivPur;

})(typeof window !== 'undefined' ? window : globalThis);
