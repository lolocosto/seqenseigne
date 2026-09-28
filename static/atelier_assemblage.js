/**
 * static/atelier_assemblage.js — v0.15
 *
 * Classe parente des ateliers de TYPE Assemblage.
 *
 * Pour mémoire (cf. cadrage v0.15) : la dimension « type d'atelier »
 * (Atomique / Assemblage) décrit la structure technique. Elle est
 * INDÉPENDANTE de la dimension « portée » (Séquence / Niveau / Cycle).
 * Un atelier d'assemblage peut être de portée Niveau (Évaluation,
 * Progression…) ou Séquence (Livret).
 *
 * Hiérarchie :
 *
 *   Atelier  (static/atelier.js)
 *   └── AtelierEditeur  (static/atelier_editeur.js)
 *       ├── AtelierExercice                  (atome, formulaire)
 *       ├── AtelierNotion                    (atome, formulaire)
 *       ├── AtelierMethode                   (atome, formulaire)
 *       ├── AtelierFiche                     (atome, formulaire)
 *       ├── AtelierCarte                     (atome, formulaire)
 *       └── AtelierAssemblage  ← CETTE CLASSE
 *           ├── AtelierEvaluation            (v0.15, portée Niveau)
 *           ├── AtelierLivret                (v0.15.1, portée Séquence)
 *           └── AtelierProgression           (v0.17+, portée Niveau)
 *
 * Ce que cette classe ajoute par rapport à AtelierEditeur :
 *
 *   1. La distinction « pluriel / singulier » (config.estPluriel).
 *      Un atelier d'assemblage *pluriel* a plusieurs items par scope
 *      (Évaluation : plusieurs évaluations par niveau, Progression :
 *      plusieurs progressions par niveau). Sidebar avec liste.
 *
 *      Un atelier d'assemblage *singulier* a un seul item par scope
 *      (Livret : une séquence-dans-niveau à la fois). Pas de sidebar.
 *
 *   2. La distinction « persistance immédiate vs explicite »
 *      (config.persistanceImmediate). Le Livret persiste chaque op
 *      atomiquement (drag-drop = PATCH immédiat), donc pas de notion
 *      de « modifié » globale. L'Évaluation a un bouton Enregistrer
 *      qui sauve le titre/mode/barème en une fois, donc concept de
 *      modifié actif.
 *
 *   3. Méthodes-hooks pour l'ajout/retrait/déplacement d'éléments
 *      composants (exos, objectifs, parties…) — `ajouterElement`,
 *      `retirerElement`, `deplacerElement`. Implémentations vides
 *      par défaut, à surcharger par les sous-classes.
 *
 *   4. Hook abstrait `rendreContenuPrincipal(item)` : à implémenter
 *      par chaque sous-classe pour rendre le panneau central.
 *
 * La machinerie de compilation PDF d'AtelierEditeur (verifierCacheEtAfficher,
 * compilerRendu, etc.) reste utilisable telle quelle PAR LES SOUS-CLASSES
 * dont le HTML suit la convention d'IDs `{prefixe}-pdf-iframe`,
 * `{prefixe}-rendu-erreur`, etc. Pour les sous-classes dont le HTML
 * suit une convention différente (cas de l'Évaluation actuelle), elles
 * peuvent redéfinir compilerRendu et compagnie en local.
 */

class AtelierAssemblage extends AtelierEditeur {
  /**
   * @param {Object} config — config héritée d'AtelierEditeur + :
   * @param {boolean} [config.estPluriel=true]
   *        true  : plusieurs items par scope (sidebar avec liste).
   *                Cas : Évaluation, Progression.
   *        false : un seul item par scope (filtres déterminent l'item).
   *                Cas : Livret.
   * @param {boolean} [config.persistanceImmediate=false]
   *        true  : chaque op (ajout/retrait/PATCH champ) persiste
   *                immédiatement. Pas de bouton « Enregistrer ».
   *                Le getter `this.modifie` retourne toujours false.
   *                Cas : Livret.
   *        false : bouton Enregistrer explicite. Le snapshot de
   *                AtelierEditeur fonctionne normalement.
   *                Cas : Évaluation.
   * @param {string[]} [config.modesFiltreEtat=['', 'en_cours', 'valide']]
   *        Modes de filtre par état d'édition affichés dans la sidebar
   *        (si pluriel). Liste par défaut, redéfinissable.
   */
  constructor(config) {
    // Valeurs par défaut spécifiques à AtelierAssemblage
    config = config || {};
    if (config.estPluriel === undefined) config.estPluriel = true;
    if (config.persistanceImmediate === undefined) {
      config.persistanceImmediate = false;
    }
    if (config.modesFiltreEtat === undefined) {
      config.modesFiltreEtat = ['', 'en_cours', 'valide'];
    }
    super(config);

    // Convenance : remonter les flags au niveau de l'instance
    this.estPluriel = !!config.estPluriel;
    this.persistanceImmediate = !!config.persistanceImmediate;
  }

  // ── Modifié : neutralisation en mode persistance immédiate ────────────────

  /**
   * En mode `persistanceImmediate = true`, chaque op est persistée
   * atomiquement (drag-drop = PATCH immédiat) donc le concept de
   * « modifié non sauvegardé » n'a pas de sens : on retourne toujours
   * false. Sinon, on hérite du comportement snapshot d'AtelierEditeur.
   */
  get modifie() {
    if (this.persistanceImmediate) return false;
    return super.modifie;
  }

  set modifie(val) {
    if (this.persistanceImmediate) {
      // No-op : la valeur reste à false implicitement, on met juste
      // la toolbar à jour (au cas où le caller compte dessus).
      this.majToolbar();
      return;
    }
    super.modifie = val;
  }

  // ── Hooks d'ajout / retrait / déplacement d'éléments composants ──────────

  /**
   * Hook pour ajouter un élément composant à l'item actif (un exo à
   * une évaluation, un objectif à une partie, une méthode à un livret…).
   *
   * Implémentation par défaut : no-op + warning console. À surcharger
   * par les sous-classes qui en ont besoin. Garde la signature ouverte
   * pour la flexibilité (type d'élément + payload arbitraire).
   *
   * @param {string} type    — type d'élément ajouté ('exo', 'objectif', …)
   * @param {Object} payload — données spécifiques au type
   * @returns {Promise<boolean>} true si l'ajout a réussi
   */
  async ajouterElement(type, payload) {
    console.warn(
      `[${this.id}] ajouterElement(${type}) non implémenté.`,
      payload,
    );
    return false;
  }

  /**
   * Hook symétrique d'ajouterElement : retire un élément composant.
   *
   * @param {string} type — type d'élément retiré
   * @param {string} id   — identifiant de l'élément à retirer
   * @returns {Promise<boolean>} true si le retrait a réussi
   */
  async retirerElement(type, id) {
    console.warn(`[${this.id}] retirerElement(${type}, ${id}) non implémenté.`);
    return false;
  }

  /**
   * Hook pour déplacer un élément composant (réordonnancement par
   * flèches haut/bas, alternative au drag-and-drop). Implémentation
   * par défaut : no-op.
   *
   * @param {string} type  — type d'élément déplacé
   * @param {string} id    — identifiant de l'élément à déplacer
   * @param {number} delta — +1 (descendre) ou -1 (monter)
   * @returns {Promise<boolean>} true si le déplacement a réussi
   */
  async deplacerElement(type, id, delta) {
    console.warn(
      `[${this.id}] deplacerElement(${type}, ${id}, ${delta}) non implémenté.`,
    );
    return false;
  }

  // ── Rendu du contenu principal (hook abstrait) ───────────────────────────

  /**
   * Hook abstrait : rend le panneau central de l'atelier (formulaires +
   * listes + sélecteurs d'ajout, etc.). À implémenter obligatoirement
   * par chaque sous-classe.
   *
   * Implémentation par défaut : warning console. Pas de throw pour
   * permettre d'instancier AtelierAssemblage telle quelle dans un test
   * unitaire (squelette).
   *
   * @param {Object} item — l'item actif (ou null si état vide)
   */
  rendreContenuPrincipal(item) {
    console.warn(
      `[${this.id}] rendreContenuPrincipal non implémenté.`,
      item,
    );
  }

  // ── v0.17.5 — Préservation du scroll lors des re-renders ──────────────────
  //
  // Une opération de STRUCTURE (ajout/retrait/réordonnancement) provoque un
  // re-render complet du panneau central (innerHTML réécrit) qui réinitialise
  // le scrollTop à 0 — l'utilisateur « remonte tout en haut » à chaque action.
  // Ces deux helpers capturent puis restaurent la position de défilement du
  // conteneur principal autour d'un re-render. À utiliser pour les opérations
  // de structure ; PAS au changement d'item (où repartir en haut est voulu).
  //
  // _container() est fourni par la sous-classe (élément scrollable du panneau).

  _capturerScroll() {
    const c = this._container();
    this._scrollMemo = c ? c.scrollTop : 0;
  }

  _restaurerScroll() {
    const c = this._container();
    if (c && typeof this._scrollMemo === 'number') {
      // Le navigateur clampe automatiquement si le contenu a raccourci.
      c.scrollTop = this._scrollMemo;
    }
  }

  /**
   * v0.17.6 — Fait défiler le conteneur principal pour amener l'élément
   * `[data-obj-id="<objId>"]` près du haut de la zone visible (sans déplacer
   * la page entière, contrairement à scrollIntoView natif sur certains
   * layouts). Utilisé à l'ouverture/fermeture d'un objectif pour que celui-ci
   * reste sous les yeux au lieu de renvoyer l'utilisateur tout en haut.
   * No-op silencieux si le conteneur ou l'élément est absent.
   *
   * @param {string} objId  identifiant de l'objectif à révéler
   * @param {number} [marge=12] marge en px au-dessus de l'élément
   */
  _scrollVersObjectif(objId, marge = 12) {
    const c = this._container();
    if (!c || !objId) return;
    const el = c.querySelector(`[data-obj-id="${(window.CSS && CSS.escape)
      ? CSS.escape(objId) : objId}"]`);
    if (!el) return;
    // Position de l'élément relative à la zone visible du conteneur, robuste
    // quel que soit l'offsetParent (getBoundingClientRect + scrollTop courant).
    const delta = el.getBoundingClientRect().top - c.getBoundingClientRect().top;
    c.scrollTop = Math.max(0, c.scrollTop + delta - marge);
  }

  // ══════════════════════════════════════════════════════════════════════════
  // v0.17.3 — Aperçu PDF au survol d'un atome (stratégie hybride)
  // ══════════════════════════════════════════════════════════════════════════
  //
  // Au survol prolongé (DELAI_APERCU_MS) d'un élément portant
  // data-atome-type + data-atome-id, on affiche le rendu PDF de l'atome dans
  // une modale flottante unique (créée une fois dans le DOM) :
  //   - GET /api/atomes/<type>/<id>/rendu-pdf/info → si cache_valide,
  //     affichage immédiat dans le viewer pdf.js (méthode héritée
  //     _afficherPdfDansViewer) ;
  //   - sinon, modale avec « Aperçu non généré » + bouton « Générer l'aperçu »
  //     (POST .../rendu-pdf puis affichage).
  //
  // Anti-empilement : un seul timer actif (this._apercuTimer) et un compteur de
  // génération (this._apercuGen) qui invalide toute réponse obsolète (souris
  // déjà repartie). Listener DÉLÉGUÉ sur le conteneur (robuste au re-render).
  //
  // Activation : appeler this._installerApercuSurvol(conteneur) après le rendu
  // (idempotent). Les sous-classes instrumentent leurs éléments d'atome avec
  // data-atome-type + data-atome-id.

  _installerApercuSurvol(conteneur) {
    if (!conteneur || conteneur.dataset.apercuInstalle === '1') return;
    conteneur.dataset.apercuInstalle = '1';

    conteneur.addEventListener('mouseover', (ev) => {
      const el = ev.target.closest('[data-atome-type][data-atome-id]');
      if (!el) return;
      // Si on est déjà sur le même atome, ne pas réarmer.
      if (this._apercuElCourant === el) return;
      this._apercuElCourant = el;
      this._armerApercu(el);
    });

    conteneur.addEventListener('mouseout', (ev) => {
      const el = ev.target.closest('[data-atome-type][data-atome-id]');
      if (!el) return;
      // Quitter vers un élément hors de l'atome courant → désarmer.
      const versAtome = ev.relatedTarget
        && ev.relatedTarget.closest
        && ev.relatedTarget.closest('[data-atome-type][data-atome-id]');
      if (versAtome === el) return;  // déplacement interne à l'atome
      if (this._apercuElCourant === el) {
        this._apercuElCourant = null;
        this._desarmerApercu();
      }
    });
  }

  _armerApercu(el) {
    this._desarmerApercu();  // un seul timer à la fois
    const type = el.getAttribute('data-atome-type');
    const id   = el.getAttribute('data-atome-id');
    if (!type || !id) return;
    this._apercuTimer = setTimeout(() => {
      this._apercuTimer = null;
      this._declencherApercu(type, id, el);
    }, AtelierAssemblage.DELAI_APERCU_MS);
  }

  _desarmerApercu() {
    if (this._apercuTimer) {
      clearTimeout(this._apercuTimer);
      this._apercuTimer = null;
    }
  }

  async _declencherApercu(type, id, el) {
    const gen = (this._apercuGen = (this._apercuGen || 0) + 1);
    this._assurerModaleApercu();
    // Cache-check (sans compiler).
    let cacheValide = false;
    try {
      const resp = await fetch(
        `/api/atomes/${encodeURIComponent(type)}/${encodeURIComponent(id)}/rendu-pdf/info`,
        { method: 'GET' },
      );
      if (resp.ok) {
        const data = await resp.json();
        cacheValide = !!data.cache_valide;
      }
    } catch (e) { /* réseau : on bascule en mode « générer » */ }
    if (gen !== this._apercuGen) return;  // souris déjà repartie

    if (cacheValide) {
      this._afficherApercuPdf(type, id, gen);
    } else {
      this._afficherApercuNonGenere(type, id, gen);
    }
  }

  async _afficherApercuPdf(type, id, gen) {
    this._ouvrirModaleApercu();
    const zone = this._apercuModale.querySelector('.atl-apercu-corps');
    zone.innerHTML = '';
    const iframe = document.createElement('iframe');
    iframe.className = 'atl-apercu-iframe';
    iframe.style.cssText = 'width:100%;height:100%;border:none';
    zone.appendChild(iframe);
    try {
      const resp = await fetch(
        `/api/atomes/${encodeURIComponent(type)}/${encodeURIComponent(id)}/rendu-pdf`,
        { method: 'POST' },  // /rendu-pdf est POST ; sert le cache si valide (instantané)
      );
      if (gen !== this._apercuGen) return;
      if (!resp.ok) { this._afficherApercuErreur('Aperçu indisponible.'); return; }
      const blob = await resp.blob();
      if (gen !== this._apercuGen) return;
      const blobUrl = URL.createObjectURL(blob);
      this._afficherPdfDansViewer(iframe, blobUrl);  // viewer pdf.js hérité
    } catch (e) {
      if (gen === this._apercuGen) this._afficherApercuErreur('Erreur réseau.');
    }
  }

  _afficherApercuNonGenere(type, id, gen) {
    this._ouvrirModaleApercu();
    const zone = this._apercuModale.querySelector('.atl-apercu-corps');
    zone.innerHTML = '';
    const wrap = document.createElement('div');
    wrap.style.cssText =
      'display:flex;flex-direction:column;align-items:center;justify-content:center;'
      + 'height:100%;gap:14px;color:var(--text-secondary);text-align:center;padding:24px';
    const msg = document.createElement('div');
    msg.textContent = 'Aperçu non encore généré pour cet atome.';
    const btn = document.createElement('button');
    btn.className = 'btn-prim';
    btn.textContent = 'Générer l\'aperçu';
    btn.addEventListener('click', () => this._genererPuisAfficherApercu(type, id));
    wrap.appendChild(msg);
    wrap.appendChild(btn);
    zone.appendChild(wrap);
  }

  async _genererPuisAfficherApercu(type, id) {
    const gen = (this._apercuGen = (this._apercuGen || 0) + 1);
    const zone = this._apercuModale.querySelector('.atl-apercu-corps');
    zone.innerHTML =
      '<div style="display:flex;align-items:center;justify-content:center;'
      + 'height:100%;color:var(--text-secondary)">Génération en cours…</div>';
    try {
      const resp = await fetch(
        `/api/atomes/${encodeURIComponent(type)}/${encodeURIComponent(id)}/rendu-pdf`,
        { method: 'POST' },
      );
      if (gen !== this._apercuGen) return;
      if (!resp.ok) { this._afficherApercuErreur('Échec de la génération.'); return; }
      const blob = await resp.blob();
      if (gen !== this._apercuGen) return;
      const zone2 = this._apercuModale.querySelector('.atl-apercu-corps');
      zone2.innerHTML = '';
      const iframe = document.createElement('iframe');
      iframe.style.cssText = 'width:100%;height:100%;border:none';
      zone2.appendChild(iframe);
      this._afficherPdfDansViewer(iframe, URL.createObjectURL(blob));
    } catch (e) {
      if (gen === this._apercuGen) this._afficherApercuErreur('Erreur réseau.');
    }
  }

  _afficherApercuErreur(message) {
    if (!this._apercuModale) return;
    const zone = this._apercuModale.querySelector('.atl-apercu-corps');
    zone.innerHTML =
      `<div style="display:flex;align-items:center;justify-content:center;`
      + `height:100%;color:var(--text-secondary);padding:24px;text-align:center">`
      + `${message}</div>`;
  }

  // Modale unique, créée une seule fois dans le DOM (panneau large flottant
  // ancré à droite). Réutilisée à chaque survol.
  _assurerModaleApercu() {
    if (this._apercuModale) return;
    const m = document.createElement('div');
    m.className = 'atl-apercu-modale';
    m.style.cssText =
      'position:fixed;top:64px;right:24px;width:min(46vw,560px);height:min(80vh,760px);'
      + 'background:var(--bg-primary,#fff);border:1px solid var(--border,#e2e1da);'
      + 'border-radius:10px;box-shadow:0 12px 40px rgba(0,0,0,0.22);'
      + 'z-index:1200;display:none;flex-direction:column;overflow:hidden';
    const tete = document.createElement('div');
    tete.style.cssText =
      'display:flex;align-items:center;justify-content:space-between;'
      + 'padding:8px 12px;border-bottom:1px solid var(--border-light,#eee);'
      + 'background:var(--bg-secondary,#f7f7f4);font-size:13px;font-weight:500';
    tete.innerHTML = '<span>Aperçu PDF</span>';
    const btnClose = document.createElement('button');
    btnClose.className = 'btn-sm';
    btnClose.textContent = '✕';
    btnClose.title = 'Fermer l\'aperçu';
    btnClose.addEventListener('click', () => this._fermerModaleApercu());
    tete.appendChild(btnClose);
    const corps = document.createElement('div');
    corps.className = 'atl-apercu-corps';
    corps.style.cssText = 'flex:1;overflow:hidden;position:relative';
    m.appendChild(tete);
    m.appendChild(corps);
    document.body.appendChild(m);
    this._apercuModale = m;

    // Fermeture : Escape, ou souris qui quitte la modale (sans revenir).
    m.addEventListener('mouseleave', () => this._fermerModaleApercu());
    if (!this._apercuEscInstalle) {
      this._apercuEscInstalle = true;
      document.addEventListener('keydown', (ev) => {
        if (ev.key === 'Escape' && this._apercuModale
            && this._apercuModale.style.display !== 'none') {
          this._fermerModaleApercu();
        }
      });
    }
  }

  _ouvrirModaleApercu() {
    this._assurerModaleApercu();
    this._apercuModale.style.display = 'flex';
  }

  _fermerModaleApercu() {
    this._desarmerApercu();
    this._apercuElCourant = null;
    this._apercuGen = (this._apercuGen || 0) + 1;  // invalide les réponses en vol
    if (this._apercuModale) {
      this._apercuModale.style.display = 'none';
      const zone = this._apercuModale.querySelector('.atl-apercu-corps');
      if (zone) zone.innerHTML = '';
    }
  }
}

AtelierAssemblage.DELAI_APERCU_MS = 1500;

// Exposition globale (cohérent avec Atelier et AtelierEditeur)
window.AtelierAssemblage = AtelierAssemblage;
