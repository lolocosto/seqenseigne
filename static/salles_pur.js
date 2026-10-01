// ============================================================================
// static/salles_pur.js — v0.37.0
// Logique PURE de l'éditeur de plan de salle (aucun accès DOM ni réseau),
// exposée sur window.SallesPur et testée par tests_js/salles_pur.test.js.
//
// Conventions (identiques à services/salles.py) :
//   - unité : cm ; repère écran, x vers la droite, y vers le BAS
//     (tableau en haut) ;
//   - une place = un emplacement d'une personne, rectangle L×H = 60×40 cm,
//     de centre (x, y), tourné de `angle` degrés (sens horaire, SVG rotate) ;
//     l'angle est celui du grand côté, normalisé dans [0, 360) ;
//   - `ilot` : identifiant de regroupement ('' = place isolée) ;
//   - `numero` : attribué par le serveur (null pour une place nouvelle).
// ============================================================================
(function () {
  const L = 60, H = 40;
  const PAS_ANGLE = 5;
  const SEUIL_AIMANT = 8;     // cm

  const rad = a => a * Math.PI / 180;
  const norm360 = a => {
    const r = ((a % 360) + 360) % 360;
    return Math.round(r * 10) / 10 % 360;
  };
  const arrondi = v => Math.round(v * 10) / 10;

  // Rotation d'un vecteur (sens horaire à l'écran, repère y vers le bas).
  function tournerVecteur(vx, vy, angle) {
    const c = Math.cos(rad(angle)), s = Math.sin(rad(angle));
    return [vx * c - vy * s, vx * s + vy * c];
  }

  // Les quatre coins d'une place, dans l'ordre (repère écran).
  function coins(p) {
    return [[-L / 2, -H / 2], [L / 2, -H / 2], [L / 2, H / 2], [-L / 2, H / 2]]
      .map(([u, v]) => {
        const [dx, dy] = tournerVecteur(u, v, p.angle || 0);
        return [p.x + dx, p.y + dy];
      });
  }

  function centre(places) {
    if (!places.length) return [0, 0];
    const sx = places.reduce((s, p) => s + p.x, 0);
    const sy = places.reduce((s, p) => s + p.y, 0);
    return [sx / places.length, sy / places.length];
  }

  // Boîte englobante (coins compris) : {xmin, ymin, xmax, ymax}.
  function boite(places) {
    if (!places.length) return { xmin: 0, ymin: 0, xmax: 0, ymax: 0 };
    const pts = places.flatMap(coins);
    return {
      xmin: Math.min(...pts.map(p => p[0])), ymin: Math.min(...pts.map(p => p[1])),
      xmax: Math.max(...pts.map(p => p[0])), ymax: Math.max(...pts.map(p => p[1])),
    };
  }

  // Sélection d'un clic : l'îlot entier, sauf demande explicite (Alt).
  function selectionDuClic(places, index, seule) {
    const p = places[index];
    if (!p) return [];
    if (seule || !p.ilot) return [index];
    return places.map((q, i) => (q.ilot === p.ilot ? i : -1)).filter(i => i >= 0);
  }

  // Pivote les places d'indices `idx` de `delta` degrés autour de leur centre
  // commun. Renvoie un NOUVEAU tableau (pas de mutation).
  function tourner(places, idx, delta) {
    const sel = idx.map(i => places[i]);
    const [cx, cy] = centre(sel);
    return places.map((p, i) => {
      if (!idx.includes(i)) return p;
      const [dx, dy] = tournerVecteur(p.x - cx, p.y - cy, delta);
      return { ...p, x: arrondi(cx + dx), y: arrondi(cy + dy),
               angle: norm360((p.angle || 0) + delta) };
    });
  }

  function deplacer(places, idx, dx, dy) {
    return places.map((p, i) => (idx.includes(i)
      ? { ...p, x: arrondi(p.x + dx), y: arrondi(p.y + dy) } : p));
  }

  // Écart angulaire modulo 90° (0 si parallèles ou perpendiculaires).
  function ecartQuartDeTour(a, b) {
    const d = ((a - b) % 90 + 90) % 90;
    return Math.min(d, 90 - d);
  }

  // Candidats d'aimantation de la place m contre la place fixe q, exprimés
  // dans le repère de q (u le long du grand côté de q, v le long du petit).
  function _candidats(m, q) {
    const parallele = Math.round(((m.angle - q.angle) % 180 + 180) % 180 / 90) % 2 === 0;
    const eu = parallele ? L : H;     // étendue de m selon u
    const ev = parallele ? H : L;     // étendue de m selon v
    const [ru, rv] = tournerVecteur(m.x - q.x, m.y - q.y, -q.angle);
    const alignU = [-L / 2 + eu / 2, 0, L / 2 - eu / 2];
    const alignV = [-H / 2 + ev / 2, 0, H / 2 - ev / 2];
    const proche = (val, opts) => {
      let best = val, d = SEUIL_AIMANT;
      for (const o of opts) if (Math.abs(o - val) < d) { d = Math.abs(o - val); best = o; }
      return best;
    };
    const c = [];
    for (const su of [-1, 1]) c.push([su * (L / 2 + eu / 2), proche(rv, alignV)]);
    for (const sv of [-1, 1]) c.push([proche(ru, alignU), sv * (H / 2 + ev / 2)]);
    return c.map(([cu, cv]) => ({ du: cu - ru, dv: cv - rv }));
  }

  // Aimantation bord à bord du groupe `idx` contre les autres places : renvoie
  // la translation [dx, dy] à appliquer (ou [0, 0] si rien à moins du seuil).
  // Seules les places parallèles ou perpendiculaires (à 1° près) s'aimantent.
  function aimanter(places, idx, seuil = SEUIL_AIMANT) {
    let best = null;
    places.forEach((q, j) => {
      if (idx.includes(j)) return;
      for (const i of idx) {
        const m = places[i];
        if (ecartQuartDeTour(m.angle || 0, q.angle || 0) > 1) continue;
        // Ne s'aimante qu'aux voisines proches (évite les calculs inutiles).
        if (Math.hypot(m.x - q.x, m.y - q.y) > L + L) continue;
        for (const { du, dv } of _candidats(m, q)) {
          const d = Math.hypot(du, dv);
          if (d <= seuil && (!best || d < best.d)) {
            const [dx, dy] = tournerVecteur(du, dv, q.angle || 0);
            best = { d, dx, dy };
          }
        }
      }
    });
    return best ? [arrondi(best.dx), arrondi(best.dy)] : [0, 0];
  }

  // Nouvel identifiant d'îlot, absent du plan.
  function nouvelIlot(places) {
    const pris = new Set(places.map(p => p.ilot));
    let k = 1;
    while (pris.has('i' + k)) k++;
    return 'i' + k;
  }

  // Regroupe les places sélectionnées (et leurs îlots entiers) en un îlot.
  function grouper(places, idx) {
    if (idx.length < 2) return places;
    const ilots = new Set(idx.map(i => places[i].ilot).filter(Boolean));
    const id = nouvelIlot(places);
    return places.map((p, i) => (idx.includes(i) || (p.ilot && ilots.has(p.ilot))
      ? { ...p, ilot: id } : p));
  }

  function degrouper(places, idx) {
    return places.map((p, i) => (idx.includes(i) ? { ...p, ilot: '' } : p));
  }

  // Modèles d'ajout : places nouvelles (numero null) autour de (x, y).
  function modele(type, x, y, places) {
    const ilot = type === 'place' ? '' : nouvelIlot(places);
    const p = (dx, dy, angle = 0) =>
      ({ numero: null, x: arrondi(x + dx), y: arrondi(y + dy), angle, ilot });
    if (type === 'ilot2') return [p(-L / 2, 0), p(L / 2, 0)];
    if (type === 'ilot4') return [p(-L / 2, -H / 2), p(L / 2, -H / 2),
                                  p(-L / 2, H / 2), p(L / 2, H / 2)];
    return [p(0, 0)];
  }

  // Emplacement libre pour un ajout : sous le plan existant, à gauche.
  function pointAjout(places) {
    if (!places.length) return [200, 120];
    const b = boite(places);
    return [arrondi(b.xmin + L), arrondi(b.ymax + H + 30)];
  }

  // Charge utile envoyée au serveur.
  function serialiser(places) {
    return places.map(p => ({ numero: p.numero == null ? null : p.numero,
      x: arrondi(p.x), y: arrondi(p.y), angle: norm360(p.angle || 0),
      ilot: p.ilot || '' }));
  }

  // Cadre d'affichage : boîte du plan + marge, avec un minimum (salle vide).
  function cadre(places, marge = 60) {
    const b = places.length ? boite(places)
      : { xmin: 0, ymin: 0, xmax: 500, ymax: 400 };
    const xmin = Math.min(0, b.xmin - marge), ymin = Math.min(0, b.ymin - marge);
    const xmax = Math.max(500, b.xmax + marge), ymax = Math.max(400, b.ymax + marge);
    return { x: xmin, y: ymin, w: xmax - xmin, h: ymax - ymin };
  }

  const api = { L, H, PAS_ANGLE, SEUIL_AIMANT, norm360, tournerVecteur, coins,
    centre, boite, selectionDuClic, tourner, deplacer, aimanter, grouper,
    degrouper, nouvelIlot, modele, pointAjout, serialiser, cadre,
    ecartQuartDeTour };
  if (typeof window !== 'undefined') window.SallesPur = api;
  else if (typeof globalThis !== 'undefined') globalThis.SallesPur = api;
})();
