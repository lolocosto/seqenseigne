/**
 * static/atelier_editeur.js — v0.15
 *
 * Classe parente des ateliers qui éditent du contenu persistant : item
 * actif, état `modifie`/`enregistré`, garde-sortie, validation d'état
 * (en_cours ↔ valide), onglets Édition/Rendu PDF, et **rendu PDF**
 * (compilation, cache, sauvegarde silencieuse, race condition).
 *
 * v0.14.4 — Toute la machinerie de rendu PDF a été remontée depuis
 * AtelierAtomique (classe intermédiaire supprimée), puisqu'elle est
 * désormais commune aux 5 ateliers (Exercice, Notion, Méthode, Fiche,
 * Carte) après les unifications v0.14.1 → v0.14.3.
 *
 * Parent : Atelier (static/atelier.js)
 * Enfants : AtelierExercice, AtelierNotion, AtelierMethode,
 *           AtelierFiche, AtelierCarte (atomes : formulaire d'1 instance)
 *           AtelierAssemblage (parent des ateliers de composition,
 *                              cf. static/atelier_assemblage.js — v0.15)
 *
 * Tout ce qui est commun entre l'édition d'un atome (exercice, notion,
 * méthode, fiche, carte) et l'édition d'un assemblage (évaluation,
 * livret, progression) vit ici.
 */

class AtelierEditeur extends Atelier {
  /**
   * @param {Object} config — config Atelier + champs suivants :
   * @param {string} config.endpointBase       — URL REST sans id, ex '/api/cartes'
   * @param {string} config.labelExistant      — toolbar quand item ouvert
   * @param {string} config.labelNouveau       — toolbar pour un nouvel item
   * @param {string} config.confirmSuppression — message du confirm() avant DELETE
   * @param {string} config.messageEnregistre  — toast après save
   * @param {string} config.messageSupprime    — toast après delete
   * @param {string} [config.typeApi]          — pour rendreAtomeTab (typage côté API)
   * @param {string} [config.typeBadge]        — pour atelAtomeRafraichirBadge
   */
  constructor(config) {
    super(config);

    // ── État d'édition ────────────────────────────────────────────────────
    this.itemActif = null;      // objet courant ouvert dans l'éditeur
    this.tabCourant = 'edition'; // 'edition' | 'rendu'

    // ── Détection « modifié » par snapshot (v0.13.7.0d) ───────────────────
    //
    // Architecture unifiée pour les 5 ateliers atomiques. Le système est
    // entièrement piloté par la classe parente :
    //
    //   1. À chaque `remplirFormulaire(item)`, on capture une signature
    //      JSON du formulaire via `collecterFormulaire()`. C'est l'état
    //      « propre » (= ce qu'on a écrit dans le DOM, normalisé par le
    //      passage dans collecterFormulaire).
    //
    //   2. Un listener délégué installé sur #atl-<prefixe>-form écoute
    //      tous les events `input` et `change` qui bullent depuis les
    //      champs. À chaque event, on recalcule la signature et on la
    //      compare au snapshot.
    //
    //   3. `this.modifie` est un getter/setter :
    //      - get : signature actuelle ≠ snapshot
    //      - set false : prend un nouveau snapshot (= "tout est OK")
    //      - set true : invalide le snapshot ("le formulaire est modifié,
    //        forcer la modale au prochain check")
    //
    //   4. La restauration ("Ne pas sauvegarder") se fait en restaurant
    //      l'item depuis `itemActif` ou un snapshot dédié.
    //
    // Conséquence : les sous-classes n'ont RIEN à faire — pas d'oninput
    // dans le HTML, pas d'appel à formChange() ou marquerModifie(). Tant
    // qu'elles implémentent correctement collecterFormulaire() et
    // remplirFormulaire(), le système marche.
    this._snapshotForm = null;          // JSON.stringify(collecterFormulaire())
                                        // au dernier état « propre »
    this._snapshotInvalide = false;     // si vrai, modifie retourne toujours true
                                        // (utilisé par le setter modifie = true)
    this._listenerInstalle = false;     // idempotence de l'install du listener
    // Cache de la dernière valeur calculée de this.modifie. Sert
    // uniquement à éviter d'appeler majToolbar() en boucle quand l'état
    // ne change pas (sinon chaque keystroke ferait clignoter le badge).
    this._modifieCache = false;

    // ── Sidebar / sélection ───────────────────────────────────────────────
    this.liste = [];             // dernière liste chargée

    // ── Multi-sélection (v0.13.6.8) ───────────────────────────────────────
    // selectionMulti : Set<string> d'IDs sélectionnés en multi-sélection.
    // Vide quand on est en mode édition simple (item actif unique).
    // ancreSelectionId : dernier ID cliqué sans modificateur — sert d'ancre
    //   pour les sélections de plage avec Maj+clic.
    this.selectionMulti = new Set();
    this.ancreSelectionId = null;

    // Alias rétrocompat avec l'ancienne API non utilisée.
    this.selection = this.selectionMulti;

    // ── Rendu PDF (v0.14.4 — descendu depuis AtelierAtomique) ─────────────
    //
    // Avant v0.14.4, une classe intermédiaire AtelierAtomique entre
    // AtelierEditeur et les 5 classes feuilles (Exercice, Notion, Méthode,
    // Fiche, Carte) portait toute la machinerie de rendu PDF. Comme cette
    // machinerie est désormais identique pour les 5 ateliers (cf. workstream
    // d'unification v0.14.1 → v0.14.3), on la fait remonter dans la parente
    // commune. AtelierAtomique est supprimée — les 5 ateliers héritent
    // maintenant directement d'AtelierEditeur.

    // Lignes fautives mémorisées pour highlight dans le .tex brut.
    this.lignesFautives = [];

    // v0.13.7.6.1.1.2 — Compteur de génération pour la race condition entre
    // verifierCacheEtAfficher et compilerRendu. Chaque exécution capture sa
    // génération locale et abandonne après un await si la génération a
    // changé (= un appel plus récent est en cours).
    this._genRendu = 0;

    // v0.14.3 — Endpoint dédié pour le rendu PDF (info / rendu-pdf /
    // rendu-tex / rendu-log). Distinct de `endpointBase` qui sert au CRUD
    // des items (GET liste, POST création, PUT update, DELETE). Par défaut,
    // on retombe sur endpointBase (pour compatibilité descendante avec
    // d'éventuelles sous-classes futures qui n'auraient pas de besoin
    // particulier sur ce point).
    if (!this.config.endpointRenduPdf) {
      this.config.endpointRenduPdf = this.config.endpointBase;
    }
  }

  // ── État d'édition ──────────────────────────────────────────────────────

  /**
   * Getter/setter sur `this.modifie`. Lecture : retourne true si la
   * signature courante du formulaire diffère du snapshot. Écriture :
   *
   *  - `this.modifie = false` : prend un nouveau snapshot (= tout est OK,
   *    le formulaire est l'image de l'état persistant).
   *  - `this.modifie = true`  : invalide le snapshot (sera always-true
   *    jusqu'à ce qu'on prenne un nouveau snapshot via = false).
   *
   * Cette API permet de garder la sémantique historique des assignations
   * directes (`this.modifie = false` après save, etc.) tout en s'appuyant
   * sur la comparaison structurelle.
   */
  get modifie() {
    if (this._snapshotInvalide) return true;
    if (this._snapshotForm === null) return false;
    // collecterFormulaire peut ne pas exister sur les classes intermédiaires
    if (typeof this.collecterFormulaire !== 'function') return false;
    try {
      const signature = JSON.stringify(this.collecterFormulaire());
      return signature !== this._snapshotForm;
    } catch (e) {
      // En cas d'erreur (DOM pas prêt, etc.), assume "non modifié".
      return false;
    }
  }

  set modifie(val) {
    if (val) {
      // Marque le formulaire comme « modifié de force ».
      this._snapshotInvalide = true;
    } else {
      // Prend un nouveau snapshot = état propre.
      this._snapshotInvalide = false;
      if (typeof this.collecterFormulaire === 'function') {
        try {
          this._snapshotForm = JSON.stringify(this.collecterFormulaire());
        } catch (e) {
          this._snapshotForm = null;
        }
      } else {
        this._snapshotForm = null;
      }
    }
    this._modifieCache = this.modifie;
    this.majToolbar();
  }

  /**
   * Installe le listener délégué qui écoute les events 'input' et 'change'
   * sur tous les champs du formulaire (#atl-<prefixe>-form). Le listener
   * recalcule `this.modifie` à chaque event et déclenche majToolbar()
   * seulement si l'état change (anti-flicker).
   *
   * Idempotent : un seul listener est installé pour l'instance, même si
   * la méthode est appelée plusieurs fois.
   */
  _installerListenerForm() {
    if (this._listenerInstalle) return;
    const form = document.getElementById(this.prefixe + '-form');
    if (!form) {
      // Form pas encore dans le DOM. Réessaye au prochain remplirFormulaire.
      return;
    }
    const handler = () => {
      const courantModifie = this.modifie;
      if (courantModifie !== this._modifieCache) {
        this._modifieCache = courantModifie;
        this.majToolbar();
      }
    };
    form.addEventListener('input', handler);
    form.addEventListener('change', handler);
    this._listenerInstalle = true;
  }

  /**
   * Restaure le formulaire à l'état persistant (= depuis this.itemActif).
   * Utilisé par "Ne pas sauvegarder" pour annuler visuellement les
   * modifs en cours.
   *
   * Appelle remplirFormulaire(itemActif) puis prend un nouveau snapshot.
   * Si itemActif est null (cas d'un nouvel item jamais sauvegardé),
   * appelle afficherVide().
   */
  _restaurerForm() {
    if (this.itemActif) {
      if (typeof this.remplirFormulaire === 'function') {
        this.remplirFormulaire(this.itemActif);
      }
      this.modifie = false; // reprise du snapshot, badge éteint
    } else {
      // Aucun item actif (cas extrême) : repli à l'état vide.
      this.afficherVide();
      this._snapshotForm = null;
      this._snapshotInvalide = false;
      this._modifieCache = false;
      this.majToolbar();
    }
  }

  /**
   * Marque le formulaire comme modifié. Active le bouton « Enregistrer »
   * et le badge "modifié" dans la toolbar.
   *
   * v0.13.7.0d — Cette méthode n'est en théorie plus utile (la détection
   * est automatique via le listener délégué + comparaison de snapshot).
   * Conservée pour compat : les sous-classes peuvent encore l'appeler
   * sans nuire.
   */
  marquerModifie() {
    this.modifie = true;
  }

  /**
   * Réinitialise l'état à "enregistré" (après une sauvegarde réussie ou
   * un chargement frais).
   *
   * v0.13.7.0d — Idem ci-dessus : remplacée en pratique par
   * `this.modifie = false` qui prend automatiquement un nouveau snapshot.
   */
  marquerEnregistre() {
    this.modifie = false;
  }

  // ── Sidebar ──────────────────────────────────────────────────────────────

  /**
   * Charge la liste depuis l'API et rend la sidebar.
   *
   * Pattern par défaut : GET endpointBase, filtre par niveau/séquence
   * via query string. Les sous-classes peuvent surcharger pour
   * personnaliser l'URL ou les filtres (ex: AtelierCarte qui fait
   * 3 fetch parallèles).
   *
   * v0.13.6.6.1 — Après chargement, vérifie que l'item actif est
   * toujours dans la liste rechargée (cas typique : on change le
   * filtre niveau/séquence pendant qu'on édite, l'item actif n'est
   * plus dans la nouvelle liste). Si plus là, ferme l'éditeur pour
   * éviter un état incohérent (sidebar à droite avec l'ancien item).
   */
  /**
   * Charge la liste depuis le serveur en passant les filtres en query
   * string. La liste reçue est stockée dans `this.liste`, puis la
   * sidebar est re-rendue.
   *
   * v0.13.6.10 — **Refonte du filtrage** :
   *   - Source unique de vérité : `window.ATL_FILTRE_NIVEAU` et
   *     `window.ATL_FILTRE_SEQ` (gérées par app.js).
   *   - Plus de propriétés `this.niveauFiltre`/`this.sequenceFiltre`
   *     (qui n'étaient jamais initialisées en pratique, source du bug
   *     « liste figée au premier chargement »).
   *   - Toutes les routes /api/<atome>?niveau=...&sequence=... filtrent
   *     côté serveur. Plus de filtrage niveau/seq côté JS dans
   *     filtrerListe (seul le filtrage par état d'édition reste).
   *
   * v0.13.6.6.1 — Après chargement, vérifie que l'item actif est
   * toujours dans la liste rechargée. Si non, ferme l'éditeur.
   */
  async chargerListe() {
    const niv = window.ATL_FILTRE_NIVEAU || '';
    const seq = window.ATL_FILTRE_SEQ || '';
    // v0.30.2 — niveau obligatoire ; séquence optionnelle : si vide, mode
    // « toutes les séquences » (liste tout le niveau, groupée par séquence).
    // Sans niveau (démarrage avant sélection), on court-circuite : liste vide.
    if (!niv) {
      this.liste = [];
      this._synchroniserItemActifAvecListe();
      this.rendreSidebar();
      return;
    }
    const url = new URL(this.config.endpointBase, window.location.origin);
    url.searchParams.set('niveau', niv);
    if (seq) url.searchParams.set('sequence', seq);  // absent = toutes séquences
    try {
      const resp = await fetch(url.toString());
      if (!resp.ok) {
        this.toast(`Erreur chargement liste : HTTP ${resp.status}`, 'erreur');
        this.liste = [];
      } else {
        this.liste = await resp.json();
      }
    } catch (e) {
      this.toast('Erreur réseau : ' + e.message, 'erreur');
      this.liste = [];
    }
    this._synchroniserItemActifAvecListe();
    this.rendreSidebar();
  }

  /**
   * v0.13.6.6.1 — Vérifie que l'item actif est toujours dans la liste
   * rechargée. Si l'item n'y est plus (typiquement : changement de
   * niveau/séquence), ferme l'éditeur (passage à l'état vide).
   *
   * Si l'utilisateur avait des modifications en cours, on les
   * abandonne silencieusement — c'est cohérent avec le fait que le
   * filtre a été changé volontairement par l'utilisateur, qui assume
   * la conséquence.
   *
   * v0.13.6.7.1 — Compare avec la liste **filtrée** (par niveau/séquence),
   * pas la liste brute. Sinon, pour les API non filtrantes (notion,
   * méthode, fiche, exercice), l'item actif d'un autre niveau resterait
   * dans la liste brute et l'éditeur ne se viderait pas malgré le
   * changement de filtre.
   *
   * À appeler dans toutes les sous-classes qui surchargent
   * chargerListe() (AtelierCarte fait 3 fetch parallèles et ne passe
   * pas par cette implémentation par défaut).
   */
  _synchroniserItemActifAvecListe() {
    if (!this.itemActif) return;
    const idActif = this.itemActif.id;
    const listeFiltree = this.filtrerListe(this.liste || []);
    const trouve = listeFiltree.some(it => it.id === idActif);
    if (!trouve) {
      this.itemActif = null;
      this.afficherVide();
      this.modifie = false; // snapshot pris après vidage
      this.majToolbar();
    }
  }

  /**
   * Rend la sidebar à partir de this.liste.
   *
   * Pattern par défaut : sidebar plate, message si vide.
   * Surchargé par AtelierExercice pour sections repliables par série.
   */
  rendreSidebar() {
    const list = this.$('list');
    if (!list) return;

    const items = this.filtrerListe(this.liste);
    if (items.length === 0) {
      list.innerHTML = this._htmlListeVide();
      return;
    }

    // v0.30.2 — Mode « toutes les séquences » (ATL_FILTRE_SEQ vide) : grouper
    // par séquence avec des sous-titres. Sinon, liste simple.
    const toutesSeq = !(window.ATL_FILTRE_SEQ || '');
    if (toutesSeq && items.some(it => it.sequence)) {
      const groupes = {};
      const ordre = [];
      items.forEach(it => {
        const s = it.sequence || '—';
        if (!groupes[s]) { groupes[s] = []; ordre.push(s); }
        groupes[s].push(it);
      });
      list.innerHTML = ordre.map(s =>
        `<div class="atl-list-groupe" style="font-size:11px;font-weight:700;`
        + `color:var(--text-secondary);background:#f2f2f5;padding:3px 10px;`
        + `position:sticky;top:0">${Atelier.escHtml ? Atelier.escHtml(s) : s}</div>`
        + groupes[s].map(it => this.rendreItem(it)).join('')
      ).join('');
      return;
    }

    list.innerHTML = items.map(it => this.rendreItem(it)).join('');
  }

  /**
   * Filtrage côté JS de la liste affichée.
   *
   * v0.13.6.10 — Plus de filtre niveau/séquence côté JS : le serveur
   * filtre déjà via les params de query. On garde uniquement le
   * filtrage par état d'édition (Tous / En cours / Validé) qui est
   * une UI purement côté client.
   */
  filtrerListe(liste) {
    if (typeof window.atelAtomeFiltreEtat_OK === 'function') {
      liste = liste.filter(it => window.atelAtomeFiltreEtat_OK(
        this.config.typeApi || this.id, it,
      ));
    }
    // v0.31.0 — Filtre « non rattachés » : un atome est non rattaché si sa
    // liste de liens vers des objectifs est vide. Piloté par le bouton
    // « Non rattachés » (ATL_FILTRE_RATTACHEMENT === 'non_rattache').
    if (window.ATL_FILTRE_RATTACHEMENT === 'non_rattache') {
      liste = liste.filter(it => !(it.liens && it.liens.length));
    }
    return liste;
  }

  /**
   * Construit le HTML d'un item. À surcharger par chaque sous-classe
   * pour adapter le rendu (badge série pour exercice, lien notion pour
   * carte, etc.).
   */
  rendreItem(item) {
    // Implémentation par défaut très minimale — chaque atelier surcharge.
    return Atelier.rendreItemHtml({
      actif:   this.itemActif && this.itemActif.id === item.id,
      onclick: `window.${this._varGlobale()}.ouvrirItem('${Atelier.escAttr(item.id)}')`,
      id:      item.id,
      titre:   item.nom || '(sans titre)',
      etatCode: item.etat_code || 'en_cours',
    });
  }

  /** HTML affiché quand la liste est vide. Surchargeable. */
  _htmlListeVide() {
    return '<div class="atl-list-vide" style="padding:14px 10px;' +
           'color:var(--text-muted);font-size:12px;text-align:center">' +
           'Aucun élément.</div>';
  }

  // ── Ouverture / création / fermeture d'un item ──────────────────────────

  /**
   * Ouvre un item dans l'éditeur central.
   * Demande confirmation si modifs en cours.
   *
   * v0.13.6.16 — GET unitaire systématique. Avant cette version la
   * stratégie « cache d'abord, fetch en fallback » fonctionnait parce
   * que la liste sidebar contenait l'item complet. Depuis v0.13.6.15
   * (harmonisation backend), la liste expose un contrat strict à 6 clés
   * `{id, titre, num, code, etat_code, liens}` insuffisant pour
   * remplir le formulaire d'édition — il faut systématiquement un GET
   * unitaire `GET /endpoint/<id>` qui retourne le détail complet.
   * Toutes les routes GET unitaires correspondantes ont été créées en
   * v0.13.6.15 (notions, méthodes, exercices) ou existaient déjà
   * (cartes, fiches).
   */
  async ouvrirItem(id) {
    // v0.13.7.0c — Modale 3 boutons unifiée via atelGardeAvantAction.
    // Remplace l'ancien confirm() natif binaire (qui ne proposait
    // qu'Annuler/OK, sans option Sauvegarder).
    if (typeof window.atelGardeAvantAction === 'function') {
      const ok = await window.atelGardeAvantAction(this);
      if (!ok) return;
    } else if (this.modifie) {
      // Repli historique : si atelier_garde.js n'est pas chargé.
      if (!confirm('Vous avez des modifications non sauvées. Les perdre ?')) {
        return;
      }
    }
    let item;
    try {
      const resp = await fetch(
        `${this.config.endpointBase}/${encodeURIComponent(id)}`,
      );
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      item = await resp.json();
    } catch (e) {
      this.toast(`Erreur ouverture : ${e.message}`, 'erreur');
      return;
    }
    this.itemActif = item;
    this.remplirFormulaire(item);
    // v0.13.7.0d — Prend le snapshot APRÈS avoir écrit le DOM (sinon
    // on snapshote l'ancien item). Puis installe le listener délégué.
    this.modifie = false;
    this._installerListenerForm();
    this.afficherEditeur(true);
    this.majToolbar();
    this.rendreSidebar();
  }

  /**
   * Crée un nouvel item.
   *
   * v0.13.6.16 — Pattern unifié pour TOUS les ateliers (D2) : POST
   * direct avec valeurs par défaut, puis ouverture de l'item retourné.
   *
   * Avant : chaque atelier avait son propre comportement.
   *   - Notion/méthode/exercice/fiche : formulaire vide affiché,
   *     itemActif=null, puis sauvegarder() faisait le POST. Bug
   *     associé : le form ne s'affichait jamais en mode création
   *     parce que `basculerOnglet` regardait `itemActif` (corrigé en
   *     v0.13.6.16 par le flag `_modeCreation`, mais cette correction
   *     devient inutile avec le nouveau pattern).
   *   - Carte : POST direct + ouverture (pattern qui marche).
   *
   * Maintenant tous les ateliers suivent le pattern carte. Chaque
   * sous-classe expose `_payloadCreation()` qui retourne le body
   * POST. Si pas surchargé, on tombe sur le payload par défaut
   * (niveau/sequence depuis filtres globaux uniquement).
   *
   * Bénéfice indirect : la régression « impossible de créer un atome »
   * de v0.13.6.15 disparaît structurellement.
   */
  async nouvelItem() {
    const niveau = window.ATL_FILTRE_NIVEAU || '';
    const sequence = window.ATL_FILTRE_SEQ || '';
    if (!niveau || !sequence) {
      this.toast('Choisir une séquence précise pour créer un élément '
        + '(la création est désactivée en mode « toutes les séquences »).',
        'erreur');
      return;
    }
    // v0.13.7.0c — Modale 3 boutons unifiée.
    if (typeof window.atelGardeAvantAction === 'function') {
      const ok = await window.atelGardeAvantAction(this);
      if (!ok) return;
    } else if (this.modifie) {
      if (!confirm('Vous avez des modifications non sauvées. Les perdre ?')) {
        return;
      }
    }
    const payload = this._payloadCreation();
    try {
      const resp = await fetch(this.config.endpointBase, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        const msg = data.message || data.error || `HTTP ${resp.status}`;
        this.toast(`Erreur création : ${msg}`, 'erreur');
        return;
      }
      const item = await resp.json();
      // Rafraîchir la liste depuis le backend (contrat à 6 clés) puis
      // ouvrir l'item nouvellement créé.
      await this.chargerListe();
      await this.ouvrirItem(item.id);
    } catch (e) {
      this.toast(`Erreur réseau : ${e.message}`, 'erreur');
    }
  }

  /**
   * Retourne le body POST envoyé à la création (pattern v0.13.6.16).
   * Surchargeable par les sous-classes pour fournir les valeurs par
   * défaut spécifiques au type d'atome (titre vide, série, énoncé
   * vide pour l'exercice, etc.).
   *
   * Par défaut : juste niveau/sequence depuis les filtres globaux.
   * Suffit pour les atomes les plus simples ; les autres surchargent.
   */
  _payloadCreation() {
    return {
      niveau:   window.ATL_FILTRE_NIVEAU || '',
      sequence: window.ATL_FILTRE_SEQ || '',
    };
  }

  /**
   * Ferme l'éditeur (revient à l'état vide). Demande confirmation si
   * modifs en cours.
   *
   * v0.13.7.0c — Devient async pour utiliser atelGardeAvantAction.
   * Les appelants existants (handlers de bouton) ne se soucient pas du
   * retour de Promise — c'est `fire-and-forget` au niveau du DOM, ce
   * qui est compatible.
   */
  async fermerEditeur() {
    if (typeof window.atelGardeAvantAction === 'function') {
      const ok = await window.atelGardeAvantAction(this);
      if (!ok) return;
    } else if (this.modifie) {
      if (!confirm('Vous avez des modifications non sauvées. Les perdre ?')) {
        return;
      }
    }
    this.itemActif = null;
    this.afficherVide();
    this.modifie = false; // snapshot pris après vidage
    this.majToolbar();
  }

  // ── Lecture / écriture du formulaire (surcharge obligatoire) ────────────

  /**
   * À surcharger : lit les champs du DOM et retourne un objet pour POST/PUT.
   * Doit retourner null si validation échoue.
   */
  collecterFormulaire() {
    throw new Error(`${this.constructor.name}.collecterFormulaire() à implémenter`);
  }

  /**
   * À surcharger : remplit les champs du formulaire depuis un objet
   * (l'item complet retourné par le GET unitaire ou le POST de
   * création — depuis v0.13.6.16 le pattern POST-direct unifié garantit
   * qu'on ne passe jamais d'item « vide » construit côté JS).
   */
  remplirFormulaire(_item) {
    throw new Error(`${this.constructor.name}.remplirFormulaire() à implémenter`);
  }

  // ── Persistance ──────────────────────────────────────────────────────────

  /**
   * Sauvegarde l'item courant. POST si nouveau, PUT si existant.
   */
  /**
   * Enregistre l'item courant (POST si nouveau, PATCH/PUT si existant).
   *
   * @param {Object} [options] — v0.14.3
   * @param {boolean} [options.silencieuse=false]
   *   Si `true`, pas de toast de succès et pas de rechargement de liste.
   *   Utilisé par les appelants qui sauvegardent en arrière-plan avant
   *   une autre opération (typiquement `compilerRendu` qui sauvegarde
   *   l'atome juste avant de générer son PDF, pour s'assurer que le
   *   PDF reflète bien les dernières saisies du formulaire).
   *   Les erreurs sont toujours signalées par un toast (la sauvegarde
   *   silencieuse ne doit pas masquer les problèmes).
   *
   * @returns {Promise<boolean>}
   *   `true` si la sauvegarde a réussi, `false` sinon (erreur de
   *   validation, échec réseau, erreur serveur). La valeur de retour
   *   permet aux appelants d'annuler les opérations en cascade qui
   *   dépendraient du succès de la save.
   *
   *   Pour la rétrocompatibilité, les appelants historiques qui ne
   *   testent pas le retour continuent de fonctionner (le résultat
   *   est ignoré).
   */
  async sauvegarder(options = {}) {
    const silencieuse = !!options.silencieuse;
    const data = this.collecterFormulaire();
    if (data === null || data === undefined) {
      // Validation échouée — le collecteur a déjà affiché le message
      return false;
    }
    const url = this.itemActif
      ? `${this.config.endpointBase}/${encodeURIComponent(this.itemActif.id)}`
      : this.config.endpointBase;
    // v0.13.7.0e — PATCH par défaut (sémantique HTTP correcte : tous les
    // services `modifier_*` côté backend font de la modification partielle
    // via whitelist + assignation). Les sous-classes peuvent surcharger
    // via config.methodeUpdate si besoin (peu probable désormais : toutes
    // les routes d'atome sont passées en PATCH strict en v0.13.7.0e).
    const methodeUpdate = this.config.methodeUpdate || 'PATCH';
    const method = this.itemActif ? methodeUpdate : 'POST';

    try {
      const resp = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        const msg = errData.message || errData.error || `HTTP ${resp.status}`;
        // Les erreurs sont signalées même en mode silencieux : si
        // la sauvegarde échoue, l'utilisateur doit le savoir.
        this.toast(`Erreur enregistrement : ${msg}`, 'erreur');
        return false;
      }
      const item = await resp.json();
      this.itemActif = item;
      this.modifie = false;
      // v0.13.6.16 — Invalidation du cache PDF/.tex selon la règle
      // générale : on n'invalide que quand la BdD a changé. Ici, on
      // vient de PUT ou POST avec succès, donc le rendu correspondant
      // est désormais obsolète. Le prochain toggleTexBrut refetchera.
      this._texChargeId = null;
      if (!silencieuse) {
        this.toast(this.config.messageEnregistre);
      }
      this.majToolbar();
      if (!silencieuse) {
        await this.chargerListe();
      }
      return true;
    } catch (e) {
      this.toast(`Erreur réseau : ${e.message}`, 'erreur');
      return false;
    }
  }

  /**
   * Supprime l'item courant après confirmation.
   */
  async supprimer() {
    if (!this.itemActif) return;
    if (!confirm(this.config.confirmSuppression)) return;
    try {
      const resp = await fetch(
        `${this.config.endpointBase}/${encodeURIComponent(this.itemActif.id)}`,
        { method: 'DELETE' },
      );
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        const msg = errData.message || errData.error || `HTTP ${resp.status}`;
        this.toast(`Erreur suppression : ${msg}`, 'erreur');
        return;
      }
      this.toast(this.config.messageSupprime);
      this.itemActif = null;
      this.modifie = false;
      // v0.13.6.16 — Item supprimé en BdD : cache PDF invalidé (cf.
      // sauvegarder).
      this._texChargeId = null;
      this.afficherVide();
      this.majToolbar();
      await this.chargerListe();
    } catch (e) {
      this.toast(`Erreur réseau : ${e.message}`, 'erreur');
    }
  }

  /**
   * v0.16.4 — Applique (ou retire) le verrou « lecture seule » sur le
   * formulaire d'édition selon que l'item est validé.
   *
   * Quand `estValide` est vrai : tous les champs de saisie (input, select,
   * textarea) et les boutons situés DANS le formulaire sont désactivés. Le
   * bouton « Repasser en cours », les onglets et « Compiler » sont HORS du
   * formulaire (barre d'outils) et restent actifs — voulu : repasser en
   * cours est la seule action d'édition, consulter le rendu reste permis.
   *
   * Les éléments portant `data-verrou-exempt` ne sont jamais désactivés.
   * Idempotent : on mémorise l'état `disabled` d'origine (data-verrou-orig)
   * pour ne pas réactiver un champ désactivé pour une autre raison.
   */
  _appliquerVerrouLectureSeule(estValide) {
    const form = this.$('form');
    if (!form) return;
    const champs = form.querySelectorAll(
      'input, select, textarea, button, [contenteditable]'
    );
    champs.forEach((el) => {
      if (el.hasAttribute('data-verrou-exempt')) return;
      if (estValide) {
        if (!el.hasAttribute('data-verrou-orig')) {
          el.setAttribute('data-verrou-orig', el.disabled ? '1' : '0');
        }
        if (el.isContentEditable) {
          el.setAttribute('contenteditable', 'false');
        } else {
          el.disabled = true;
        }
      } else if (el.hasAttribute('data-verrou-orig')) {
        const orig = el.getAttribute('data-verrou-orig') === '1';
        el.removeAttribute('data-verrou-orig');
        if (el.getAttribute('contenteditable') === 'false') {
          el.setAttribute('contenteditable', 'true');
        } else {
          el.disabled = orig;
        }
      }
    });
    form.classList.toggle('atl-verrou-lecture-seule', estValide);
  }

  // ── Validation d'état (en_cours ↔ valide) ───────────────────────────────

  /**
   * Bascule l'état d'édition entre 'en_cours' et 'valide'.
   *
   * v0.13.6.14.1 — Correction de l'endpoint. Avant : `POST endpointBase/
   * <id>/validation` (qui n'existe pas/plus côté serveur, renvoyait 404).
   * Maintenant : `PATCH /api/atomes/<typeApi>/<id>/etat` avec body
   * `{etat_code: 'valide'|'en_cours'}`, qui est le mécanisme unifié des
   * états d'édition (cf. routes/etats_edition.py).
   */
  async basculerValidation() {
    if (!this.itemActif) return;
    const cible = this.itemActif.etat_code === 'valide' ? 'en_cours' : 'valide';
    try {
      const resp = await fetch(
        `/api/atomes/${encodeURIComponent(this.config.typeApi)}` +
        `/${encodeURIComponent(this.itemActif.id)}/etat`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ etat_code: cible }),
        },
      );
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        // L'API etats_edition renvoie {raisons: [...]} en cas d'échec
        // pédagogique (code 'validation_pedagogique_echec').
        const raisons = Array.isArray(errData.raisons)
          ? ' — ' + errData.raisons.join(' ; ') : '';
        const msg = (errData.error || `HTTP ${resp.status}`) + raisons;
        this.toast(`Erreur validation : ${msg}`, 'erreur');
        return;
      }
      this.itemActif.etat_code = cible;
      this.majToolbar();
      await this.chargerListe();
    } catch (e) {
      this.toast(`Erreur réseau : ${e.message}`, 'erreur');
    }
  }

  // ── Onglets Édition / Rendu PDF ─────────────────────────────────────────

  /**
   * Bascule entre les onglets Édition et Rendu PDF. Met le bon display
   * sur les sous-zones (flex pour permettre au flex:1 enfant de prendre
   * effet).
   */
  basculerOnglet(tab) {
    if (tab !== 'edition' && tab !== 'rendu') return;
    this.tabCourant = tab;

    // Activer le bon bouton d'onglet
    const btnEdit = this.$('tab-btn-edition');
    const btnRendu = this.$('tab-btn-rendu');
    if (btnEdit) btnEdit.classList.toggle('active', tab === 'edition');
    if (btnRendu) btnRendu.classList.toggle('active', tab === 'rendu');

    // v0.13.6.16 — Le form est visible si :
    //   - on a un item actif (édition d'un existant), OU
    //   - on est en mode création (itemActif null, mais on saisit un nouvel item).
    // Avant : seul `this.itemActif` était vérifié → form caché en
    // création, régression visible sur tous les ateliers sauf carte
    // (cf. afficherEditeur).
    const editable = this.itemActif || this._modeCreation;
    this.setDisplay('form', (tab === 'edition' && editable) ? 'block' : 'none');
    this.setDisplay('rendu', (tab === 'rendu' && this.itemActif) ? 'flex' : 'none');

    // Sécurité : s'assurer que le bandeau d'onglets reste visible.
    if (editable) {
      this.setDisplay('tabs', 'flex');
    }

    // v0.14.4 — Auto-chargement du PDF si le cache est valide (et
    // auto-compile si la pref auto-compile est active). Descendu depuis
    // AtelierAtomique.basculerOnglet — voir verifierCacheEtAfficher.
    if (tab === 'rendu' && this.itemActif) {
      // Pas d'await ici : on lance en arrière-plan et on rend la main
      // au caller. La méthode gère elle-même le placeholder et la
      // race condition.
      this.verifierCacheEtAfficher();
    }
  }

  // ── Affichage / masquage de l'éditeur ───────────────────────────────────

  /**
   * Affiche l'éditeur central pour un item.
   *
   * v0.13.6.16 — Le paramètre `existant` n'est plus utilisé : avec le
   * pattern unifié de création (POST direct dans `nouvelItem`),
   * `itemActif` est toujours posé quand on arrive ici. On garde le
   * paramètre pour compatibilité des appels.
   *
   * Suffixes affichés/masqués :
   *   - empty   → none (cache l'état "rien sélectionné")
   *   - tabs    → flex (bandeau onglets visible)
   *   - et basculement vers l'onglet courant via basculerOnglet
   */
  afficherEditeur(existant) {
    this.setDisplay('empty', 'none');
    this.setDisplay('tabs', 'flex');
    this.basculerOnglet(this.tabCourant);
  }

  /**
   * Affiche l'état vide (aucun item sélectionné).
   */
  afficherVide() {
    this.setDisplay('empty', 'flex');
    this.setDisplay('tabs', 'none');
    this.setDisplay('form', 'none');
    this.setDisplay('rendu', 'none');
  }

  // ── Toolbar (boutons et badges en haut) ─────────────────────────────────

  /**
   * Met à jour les boutons et badges de la toolbar selon l'état actuel
   * (item actif, modifié, validé).
   *
   * Conventions d'IDs DOM :
   *   - {prefixe}-toolbar-title : titre
   *   - {prefixe}-badge-modifie : badge "modifié"
   *   - {prefixe}-etat-badge    : badge "validé" / "en cours"
   *   - {prefixe}-btn-valider   : bouton bascule validation
   *   - {prefixe}-btn-latex     : bouton LaTeX
   *   - {prefixe}-btn-suppr     : bouton Supprimer
   *   - {prefixe}-btn-save      : bouton Enregistrer
   */
  majToolbar() {
    const titre = this.$('toolbar-title');
    if (titre) {
      if (this.itemActif) {
        titre.textContent = this.config.labelExistant;
      } else if (this.itemActif === null && this.aFormulaireOuvert()) {
        titre.textContent = this.config.labelNouveau;
      } else {
        titre.textContent = this.config.titreToolbar || '';
      }
    }

    const badgeModifie = this.$('badge-modifie');
    if (badgeModifie) {
      badgeModifie.style.display = this.modifie ? 'inline-block' : 'none';
    }

    const badgeEtat = this.$('etat-badge');
    if (badgeEtat) {
      if (this.itemActif) {
        badgeEtat.style.display = 'inline-block';
        if (this.itemActif.etat_code === 'valide') {
          badgeEtat.textContent = 'Validé';
          badgeEtat.className = 'atome-etat-badge valide';
        } else {
          badgeEtat.textContent = 'En cours';
          badgeEtat.className = 'atome-etat-badge en_cours';
        }
      } else {
        badgeEtat.style.display = 'none';
      }
    }

    const btnValider = this.$('btn-valider');
    if (btnValider) {
      if (this.itemActif) {
        btnValider.style.display = 'inline-block';
        btnValider.textContent = (this.itemActif.etat_code === 'valide')
          ? 'Repasser en cours' : 'Valider';
      } else {
        btnValider.style.display = 'none';
      }
    }

    // v0.16.4 — Verrou « validé = lecture seule ». Quand l'item est validé,
    // on grise les champs et masque les actions de structure : la seule
    // action possible est « Repasser en cours » (bouton valider ci-dessus).
    // Garantie réelle côté backend (409) ; ici, confort visuel.
    this._appliquerVerrouLectureSeule(
      !!(this.itemActif && this.itemActif.etat_code === 'valide')
    );

    const btnLatex = this.$('btn-latex');
    if (btnLatex) {
      btnLatex.style.display = this.itemActif ? 'inline-block' : 'none';
    }

    const btnSuppr = this.$('btn-suppr');
    if (btnSuppr) {
      btnSuppr.style.display = this.itemActif ? 'inline-block' : 'none';
    }

    const btnSave = this.$('btn-save');
    if (btnSave) {
      btnSave.style.display = this.aFormulaireOuvert() ? 'inline-block' : 'none';
      btnSave.disabled = !this.modifie;
    }
  }

  /**
   * Indique si un formulaire est ouvert (item actif OU nouveau en
   * cours). Utilisé par majToolbar pour décider d'afficher les
   * boutons.
   */
  aFormulaireOuvert() {
    // Détecte la présence visible du form via le style display.
    // Plus fiable que de tenter de tracker un booléen interne car
    // les ouvertures de nouveau item peuvent passer par des codes
    // qui ne mettent pas itemActif à un objet.
    const form = this.$('form');
    return form && form.style.display !== 'none';
  }

  // ══════════════════════════════════════════════════════════════════════
  // Multi-sélection (v0.13.6.8)
  // ══════════════════════════════════════════════════════════════════════
  //
  // Modèle d'interaction :
  //   - clic simple             → ouvre l'item (comportement actuel) +
  //                                vide la sélection multi
  //   - Ctrl+clic / Cmd+clic    → toggle l'item dans la sélection
  //   - Maj+clic                → sélectionne la plage entre l'ancre et
  //                                l'item cliqué (dans l'ordre de la liste
  //                                filtrée affichée)
  //   - clic droit              → ouvre le menu contextuel ; ajoute aussi
  //                                l'item à la sélection s'il n'y est pas
  //   - Échap                   → vide la sélection
  //
  // Actions disponibles (dans le menu contextuel ou la barre d'actions) :
  //   - Valider la sélection (tous en 'valide')
  //   - Repasser en cours (tous en 'en_cours')
  //   - Annuler la sélection
  //
  // Mode tolérant aux erreurs (Q3) : on tente chaque opération, on
  // continue en cas d'échec partiel, on affiche un résumé à la fin
  // (ex: « 8 OK, 2 échecs »).

  /**
   * Handler de clic sur un item de la sidebar. Appelé par le `onclick`
   * généré dans `rendreItem`. Aiguille selon les modificateurs Ctrl/Maj.
   *
   * @param {MouseEvent} ev — événement du clic
   * @param {string} id     — ID de l'item cliqué
   */
  gererClicItem(ev, id) {
    // Ctrl/Cmd : toggle
    if (ev && (ev.ctrlKey || ev.metaKey)) {
      ev.preventDefault();
      this.selectionMultiToggleId(id);
      this.ancreSelectionId = id;
      return;
    }
    // Maj : plage entre ancre et id
    if (ev && ev.shiftKey) {
      ev.preventDefault();
      this.selectionMultiPlage(id);
      // Pas de mise à jour de l'ancre pour Maj+clic : permet d'étendre
      // une plage dans plusieurs directions sans réancrage.
      return;
    }
    // Clic simple : ouvre l'item + vide la sélection multi
    this.selectionMultiEffacer();
    this.ancreSelectionId = id;
    this.ouvrirItem(id);
  }

  /**
   * Handler de clic droit sur un item. Évite le menu contextuel natif,
   * ajoute l'item à la sélection s'il n'y est pas déjà, et ouvre le
   * menu contextuel applicatif.
   */
  gererClicDroitItem(ev, id) {
    if (!ev) return;
    ev.preventDefault();
    if (!this.selectionMulti.has(id)) {
      // Item pas encore sélectionné : on remplace la sélection par cet
      // item (comportement standard, cf. Explorer Windows).
      this.selectionMulti.clear();
      this.selectionMulti.add(id);
      this.ancreSelectionId = id;
      this.rendreSidebar();
      this._majSelectionToolbar();
    }
    this.selectionMultiOuvrirMenu(ev.clientX, ev.clientY);
  }

  /** Ajoute ou retire un id de la sélection multi. */
  selectionMultiToggleId(id) {
    if (this.selectionMulti.has(id)) {
      this.selectionMulti.delete(id);
    } else {
      this.selectionMulti.add(id);
    }
    this.rendreSidebar();
    this._majSelectionToolbar();
  }

  /**
   * Sélectionne une plage entre l'ancre (`ancreSelectionId`) et l'id
   * cible, dans l'ordre de la liste filtrée. Si pas d'ancre, sélectionne
   * juste l'item cible.
   */
  selectionMultiPlage(idCible) {
    const items = this.filtrerListe(this.liste);
    const ids = items.map(it => it.id);
    const ancre = this.ancreSelectionId;
    if (!ancre || !ids.includes(ancre)) {
      // Pas d'ancre valide → comportement Ctrl+clic
      this.selectionMulti.add(idCible);
    } else {
      const iAncre = ids.indexOf(ancre);
      const iCible = ids.indexOf(idCible);
      if (iCible < 0) return;
      const [debut, fin] = iAncre < iCible ? [iAncre, iCible] : [iCible, iAncre];
      for (let i = debut; i <= fin; i++) {
        this.selectionMulti.add(ids[i]);
      }
    }
    this.rendreSidebar();
    this._majSelectionToolbar();
  }

  /** Vide la sélection multi. */
  selectionMultiEffacer() {
    if (this.selectionMulti.size === 0) return;
    this.selectionMulti.clear();
    this.rendreSidebar();
    this._majSelectionToolbar();
    this.selectionMultiFermerMenu();
  }

  /**
   * Action de masse : passe tous les items sélectionnés à l'état cible
   * ('valide' ou 'en_cours'). Tolérant aux erreurs : itère sur tous,
   * collecte succès/échecs, affiche un résumé.
   */
  async selectionMultiAppliquerEtat(cible) {
    if (!['valide', 'en_cours'].includes(cible)) return;
    const ids = Array.from(this.selectionMulti);
    if (ids.length === 0) return;

    // Filtrer : on ne refait pas une opération sur un item qui est déjà
    // dans l'état cible (évite un POST inutile et un faux échec si l'API
    // est stricte là-dessus).
    const dejaCible = [];
    const aTraiter = [];
    for (const id of ids) {
      const it = this.liste.find(x => x.id === id);
      if (!it) continue;
      if ((it.etat_code || 'en_cours') === cible) {
        dejaCible.push(id);
      } else {
        aTraiter.push(id);
      }
    }

    const reussis = [];
    const echoues = [];
    for (const id of aTraiter) {
      try {
        // v0.13.6.14.1 — Même endpoint corrigé que basculerValidation
        // single : PATCH /api/atomes/<typeApi>/<id>/etat
        const resp = await fetch(
          `/api/atomes/${encodeURIComponent(this.config.typeApi)}` +
          `/${encodeURIComponent(id)}/etat`,
          {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ etat_code: cible }),
          },
        );
        if (resp.ok) {
          reussis.push(id);
          // Mettre à jour le cache local pour que le rendu reflète l'état
          const it = this.liste.find(x => x.id === id);
          if (it) it.etat_code = cible;
          // Si c'est l'item actif, mettre à jour aussi
          if (this.itemActif && this.itemActif.id === id) {
            this.itemActif.etat_code = cible;
          }
        } else {
          echoues.push(id);
        }
      } catch (e) {
        echoues.push(id);
      }
    }

    // Résumé toast
    const libelleAction = cible === 'valide' ? 'validé' : 'repassé en cours';
    const parts = [];
    if (reussis.length > 0) parts.push(`${reussis.length} ${libelleAction}`);
    if (dejaCible.length > 0) parts.push(`${dejaCible.length} déjà à jour`);
    if (echoues.length > 0) parts.push(`${echoues.length} en échec`);
    const msg = parts.join(', ');
    if (echoues.length > 0) {
      this.toast(msg, 'erreur');
    } else if (reussis.length > 0) {
      this.toast(msg);
    } else {
      this.toast(msg);
    }

    // Mettre à jour la toolbar de l'item actif (si concerné)
    this.majToolbar();

    // Recharger la liste pour rafraîchir l'affichage
    await this.chargerListe();
    this._majSelectionToolbar();
  }

  // ── Menu contextuel : créé à la volée, supprimé au clic ailleurs ────────

  selectionMultiOuvrirMenu(clientX, clientY) {
    this.selectionMultiFermerMenu();
    const n = this.selectionMulti.size;
    if (n === 0) return;

    const menu = document.createElement('div');
    menu.id = '__selection-menu__';
    menu.className = 'asm-selection-menu';
    menu.style.cssText = [
      'position:fixed',
      `left:${clientX}px`,
      `top:${clientY}px`,
      'background:var(--bg-card)',
      'border:1px solid var(--border)',
      'border-radius:6px',
      'box-shadow:0 4px 12px rgba(0,0,0,0.15)',
      'padding:4px 0',
      'z-index:10000',
      'min-width:220px',
      'font-size:13px',
    ].join(';');

    const varG = this._varGlobale();
    const sufN = n > 1 ? 's' : '';
    menu.innerHTML = `
      <div style="padding:6px 12px;color:var(--text-muted);font-size:11px;
                  border-bottom:1px solid var(--border)">
        ${n} item${sufN} sélectionné${sufN}
      </div>
      <div class="asm-selection-menu-item"
           onclick="${varG}.selectionMultiAppliquerEtat('valide');${varG}.selectionMultiFermerMenu()"
           style="padding:8px 12px;cursor:pointer">
        ✓ Valider la sélection
      </div>
      <div class="asm-selection-menu-item"
           onclick="${varG}.selectionMultiAppliquerEtat('en_cours');${varG}.selectionMultiFermerMenu()"
           style="padding:8px 12px;cursor:pointer">
        ⟲ Repasser en cours
      </div>
      <div style="height:1px;background:var(--border);margin:4px 0"></div>
      <div class="asm-selection-menu-item"
           onclick="${varG}.selectionMultiEffacer()"
           style="padding:8px 12px;cursor:pointer;color:var(--text-muted)">
        Annuler la sélection
      </div>`;

    document.body.appendChild(menu);

    // Ajuster la position si le menu dépasse à droite ou en bas
    const rect = menu.getBoundingClientRect();
    if (rect.right > window.innerWidth) {
      menu.style.left = (window.innerWidth - rect.width - 4) + 'px';
    }
    if (rect.bottom > window.innerHeight) {
      menu.style.top = (window.innerHeight - rect.height - 4) + 'px';
    }

    // Effet hover sur les items du menu
    menu.querySelectorAll('.asm-selection-menu-item').forEach(el => {
      el.addEventListener('mouseenter', () => {
        el.style.background = 'var(--bg-hover, rgba(0,0,0,0.05))';
      });
      el.addEventListener('mouseleave', () => {
        el.style.background = '';
      });
    });

    // Clic ailleurs ferme le menu (différé pour ne pas l'attraper soi-même)
    setTimeout(() => {
      const onDocClick = () => {
        this.selectionMultiFermerMenu();
        document.removeEventListener('click', onDocClick);
      };
      document.addEventListener('click', onDocClick);
    }, 0);
  }

  selectionMultiFermerMenu() {
    const menu = document.getElementById('__selection-menu__');
    if (menu) menu.remove();
  }

  // ── Toolbar de sélection : barre d'actions ──────────────────────────────

  /**
   * Met à jour la barre d'actions multi-sélection au-dessus de la
   * sidebar. Visible si selectionMulti.size > 0, cachée sinon.
   */
  _majSelectionToolbar() {
    let toolbar = this.$('selection-toolbar');
    if (!toolbar) {
      // Créer la toolbar à la volée, juste après le bouton « + Créer »
      // de la sidebar (cherche un parent de la liste).
      const list = this.$('list');
      if (!list || !list.parentElement) return;
      toolbar = document.createElement('div');
      toolbar.id = `${this.config.prefixe}-selection-toolbar`;
      toolbar.className = 'asm-selection-toolbar';
      toolbar.style.cssText = [
        'display:none',
        'padding:8px 10px',
        'background:var(--bg-subtle, rgba(0,120,212,0.08))',
        'border-bottom:1px solid var(--border)',
        'font-size:12px',
        'gap:6px',
        'align-items:center',
        'flex-wrap:wrap',
      ].join(';');
      list.parentElement.insertBefore(toolbar, list);
    }

    const n = this.selectionMulti.size;
    if (n === 0) {
      toolbar.style.display = 'none';
      return;
    }
    toolbar.style.display = 'flex';
    const varG = this._varGlobale();
    const sufN = n > 1 ? 's' : '';
    toolbar.innerHTML = `
      <span style="font-weight:500;flex:1">
        ${n} sélectionné${sufN}
      </span>
      <button class="btn-sm" title="Valider la sélection (tous → validé)"
              onclick="${varG}.selectionMultiAppliquerEtat('valide')">
        ✓ Valider
      </button>
      <button class="btn-sm" title="Repasser en cours (tous → en cours)"
              onclick="${varG}.selectionMultiAppliquerEtat('en_cours')">
        ⟲ En cours
      </button>
      <button class="btn-sm" title="Annuler la sélection (Échap)"
              onclick="${varG}.selectionMultiEffacer()">
        ✕
      </button>`;
  }

  // ── Helper : marqueur de sélection passé à rendreItemHtml ───────────────

  /**
   * Retourne true si l'id donné est dans la sélection multi.
   * Utilisé par les sous-classes dans leur `rendreItem` pour passer
   * `selected: this.estSelectionne(id)` à `Atelier.rendreItemHtml`.
   */
  estSelectionne(id) {
    return this.selectionMulti.has(id);
  }

  // ══════════════════════════════════════════════════════════════════════
  // Fin du bloc multi-sélection
  // ══════════════════════════════════════════════════════════════════════

  // ── Helper interne ──────────────────────────────────────────────────────

  // ──────────────────────────────────────────────────────────────────────
  // v0.13.6.11 — Chantier B : bouton « reprendre titre objectif »
  // ──────────────────────────────────────────────────────────────────────

  /**
   * Retourne le nom de l'objectif lié si l'item actif a EXACTEMENT 1
   * lien de type='obj' (cardinalité 1:1), sinon null.
   *
   * Utilisé pour :
   *   - décider si le bouton « reprendre titre objectif » est affiché
   *     (visible seulement si la fonction renvoie une chaîne non vide)
   *   - récupérer le nom à injecter lors du clic
   *
   * Si l'objectif lié existe mais a un `nom` vide, on retourne ''.
   * L'appelant choisit s'il affiche quand même le bouton (sans effet
   * utile) ou s'il le cache.
   */
  _reprendreObjectifDispo() {
    if (!this.itemActif) return null;
    const liens = this.itemActif.liens || [];
    const objs = liens.filter(l => l && l.type === 'obj');
    if (objs.length !== 1) return null;
    return objs[0].nom || '';
  }

  /**
   * Action déclenchée par le bouton « reprendre titre objectif ».
   *
   * Comportement :
   *   - Si pas de lien 1:1 obj → ne fait rien (cas où le bouton ne
   *     devrait pas être visible mais sécurité défensive)
   *   - Si l'objectif n'a pas de nom (chaîne vide) → toast d'avertissement
   *   - Si le champ titre est vide → injecte directement
   *   - Sinon → confirme avant d'écraser
   *
   * @param {string} idChampTitre - id de l'input à mettre à jour
   *                                (ex: 'atl-notion-titre', 'atl-exercice-titre')
   */
  reprendreLibelleObjectif(idChampTitre) {
    const nom = this._reprendreObjectifDispo();
    if (nom === null) {
      // Pas de lien 1:1 obj : silence (le bouton ne devrait pas être là)
      return;
    }
    if (!nom) {
      // Objectif sans nom renseigné
      this.toast('L\'objectif lié n\'a pas de libellé renseigné.', 'erreur');
      return;
    }
    const input = document.getElementById(idChampTitre);
    if (!input) {
      console.warn(`reprendreLibelleObjectif: champ #${idChampTitre} introuvable`);
      return;
    }
    const valeurActuelle = (input.value || '').trim();
    if (valeurActuelle && valeurActuelle !== nom) {
      if (!confirm(
        `Le titre actuel est :\n  « ${valeurActuelle} »\n\n` +
        `Le remplacer par le libellé de l'objectif ?\n  « ${nom} »`,
      )) return;
    }
    input.value = nom;
    // Déclencher l'événement input pour propager le dirty-flag de la
    // classe (par ex. via les listeners d'auto-detect modifications).
    input.dispatchEvent(new Event('input', { bubbles: true }));
    this.modifie = true;
    this._rafraichirToolbar?.();
  }

  /**
   * Injecte (ou rafraîchit) le bouton « reprendre titre objectif » dans
   * le slot prévu côté HTML.
   *
   * Convention HTML (v0.13.6.12) : la ligne du label « Titre » est un
   * `<div class="atl-field-titre-row" data-slot-reprendre-obj="<id-input>">`
   * contenant le `<label>`. Le bouton est inséré à droite (le flex
   * gère le `space-between`). Si le slot est absent (cas legacy), on
   * tombe en fallback sur l'insertion après l'input.
   *
   * Affichage conditionnel : visible seulement si lien 1:1 obj avec
   * un nom non vide.
   *
   * @param {string} idChampTitre - id de l'input
   */
  _injecterBoutonReprendreTitre(idChampTitre) {
    const input = document.getElementById(idChampTitre);
    if (!input) return;

    // Cible : slot data-attr en priorité, fallback après input
    const slot = document.querySelector(
      `[data-slot-reprendre-obj="${idChampTitre}"]`,
    );

    // Crée le bouton la première fois, sinon récupère l'existant
    const idBouton = idChampTitre + '-reprendre-obj';
    let bouton = document.getElementById(idBouton);
    if (!bouton) {
      bouton = document.createElement('button');
      bouton.type = 'button';
      bouton.id = idBouton;
      bouton.className = 'atl-btn-reprendre-obj';
      bouton.textContent = '⤵ reprendre titre objectif';
      bouton.title = 'Réutiliser le libellé de l\'objectif lié comme titre';
      bouton.addEventListener('click', () => {
        this.reprendreLibelleObjectif(idChampTitre);
      });
      if (slot) {
        slot.appendChild(bouton);
      } else {
        input.parentNode.insertBefore(bouton, input.nextSibling);
      }
    }

    // Affichage conditionnel : visible seulement si lien 1:1 obj avec nom
    const nom = this._reprendreObjectifDispo();
    bouton.style.display = (nom && nom.trim()) ? '' : 'none';
  }

  _varGlobale() {
    return 'ATELIER_' + this.id.toUpperCase();
  }


  // ════════════════════════════════════════════════════════════════════════
  // v0.14.4 — Rendu PDF unifié (descendu depuis AtelierAtomique)
  // ════════════════════════════════════════════════════════════════════════
  //
  // Méthodes du rendu PDF utilisées par les 5 ateliers (Exercice, Notion,
  // Méthode, Fiche, Carte) :
  //   - verifierCacheEtAfficher  : appelé depuis basculerOnglet quand on
  //                                bascule sur l'onglet Rendu PDF. Décide
  //                                entre auto-cache, auto-compile (si pref
  //                                active) ou placeholder.
  //   - _remettrePlaceholderRendu : remet la zone Rendu en état initial
  //                                (iframe masquée, placeholder visible).
  //   - compilerRendu             : compile le PDF (avec sauvegarde
  //                                silencieuse en amont si l'item est
  //                                modifié) et l'affiche dans l'iframe.
  //   - _afficherErreurCompilation: liste des erreurs LaTeX + bouton .tex.
  //   - toggleTexBrut             : ouvre/ferme la zone .tex brut.
  //   - _afficherTexBrut          : rendu numéroté + highlight des fautes.
  //   - scrollVersLigneTex        : scroll vers une ligne fautive.
  //   - voirLatex                 : ouvre /rendu-tex dans un nouvel onglet.
  //
  // Pré-v0.14.4 : ces méthodes vivaient dans une classe intermédiaire
  // AtelierAtomique (atelier_atomique.js). Comme le code est désormais
  // identique pour les 5 ateliers (cf. unification v0.14.1 → v0.14.3),
  // on remonte dans la parente commune et on supprime l'intermédiaire.

  // ── Rendu PDF (compilation unitaire) ────────────────────────────────────
  /**
   * v0.13.7.6.1 — Vérification non-bloquante du cache PDF.
   *
   * Appelle `${endpointBase}/${id}/rendu-pdf/info` (GET) :
   *  - si le serveur répond `{cache_valide: true}` → fetch du PDF
   *    (POST /rendu-pdf), qui sera servi depuis le cache (X-Seq-Depuis-Cache=1)
   *  - sinon → remet l'UI en état placeholder pour éviter d'afficher
   *    l'iframe d'un item précédent qui n'est plus pertinent
   *
   * v0.13.7.6.1.1 — Correction du bug visuel : quand on passait d'une
   * carte compilée à une carte non compilée, le PDF de la première
   * restait visible (l'iframe gardait son src). On nettoie maintenant
   * l'UI dans tous les cas où on ne va PAS afficher un PDF valide.
   *
   * v0.13.7.6.1.1.2 — Correction d'une race condition : si l'utilisateur
   * clique rapidement carte A (avec cache) puis carte B (sans cache),
   * la promesse `compilerRendu(A)` peut résoudre APRÈS le
   * `_remettrePlaceholderRendu(B)`, écrasant le placeholder de B par
   * le PDF de A. Solution : compteur de génération `_genRendu`,
   * incrémenté à chaque appel ; chaque exécution capture sa génération
   * locale et abandonne silencieusement après un await si la génération
   * a changé (= un appel plus récent est en cours).
   *
   * Tolère le 404 (endpoint pas encore en place côté serveur, ou
   * carte introuvable) en fallback : on remet aussi le placeholder
   * pour la même raison.
   */
  /**
   * v0.17.0 — Génère (une seule fois, idempotent) la mini-toolbar de la zone
   * de rendu : bouton « Compiler le rendu », bouton « LaTeX généré », et le
   * span de statut. Factorise ce qui était dupliqué en HTML statique dans les
   * 6 ateliers (5 atomes + évaluation).
   *
   * Le bouton « LaTeX généré » était auparavant dans la toolbar du HAUT de
   * chaque atelier ; il est désormais ici, à côté de « Compiler le rendu »
   * (alignement sur l'atelier Séquence, demande v0.17). La visibilité du
   * bouton LaTeX reste pilotée par majToolbar (via this.$('btn-latex')).
   *
   * Cible : le conteneur #<prefixe>-rendu-toolbar (posé en HTML, vide). Si ce
   * conteneur est absent (atelier non encore migré), on ne fait rien — la
   * toolbar statique éventuelle reste en place (rétrocompatibilité).
   *
   * Handlers câblés par addEventListener (pas d'onclick inline) : la base n'a
   * pas à connaître le nom de la variable globale de l'instance.
   */
  _assurerToolbarRendu() {
    const conteneur = this.$('rendu-toolbar');
    if (!conteneur || conteneur.dataset.genere === '1') return;

    const btnCompiler = document.createElement('button');
    btnCompiler.className = 'btn-sm btn-prim';
    btnCompiler.type = 'button';
    btnCompiler.id = this.prefixe + '-btn-compiler';
    btnCompiler.textContent = 'Compiler le rendu';
    btnCompiler.addEventListener('click', () => this.compilerRendu());

    const btnLatex = document.createElement('button');
    btnLatex.className = 'btn-sm';
    btnLatex.type = 'button';
    btnLatex.id = this.prefixe + '-btn-latex';
    btnLatex.textContent = 'LaTeX généré';
    btnLatex.title = 'Voir le LaTeX généré (Ctrl+L)';
    btnLatex.style.display = 'none';  // visibilité pilotée par majToolbar
    btnLatex.addEventListener('click', () => this.voirLatex());

    const status = document.createElement('span');
    status.id = this.prefixe + '-rendu-status';
    status.style.cssText =
      'font-size:11px;color:var(--text-muted);margin-left:auto';

    conteneur.appendChild(btnCompiler);
    conteneur.appendChild(btnLatex);
    conteneur.appendChild(status);
    conteneur.dataset.genere = '1';

    // Synchronise immédiatement la visibilité du bouton LaTeX (et des autres
    // contrôles pilotés) avec l'état courant : la toolbar vient d'apparaître,
    // un majToolbar antérieur n'avait pas pu agir dessus (bouton inexistant).
    this.majToolbar();
  }

  async verifierCacheEtAfficher() {
    if (!this.itemActif) return;
    this._assurerToolbarRendu();
    const id = this.itemActif.id;
    // v0.13.7.6.1.1.2 — Génération courante : invalide les exécutions
    // antérieures encore en vol après cet appel.
    const maGen = ++this._genRendu;
    try {
      const resp = await fetch(
        `${this.config.endpointRenduPdf}/${encodeURIComponent(id)}/rendu-pdf/info`,
        { method: 'GET' },
      );
      // Si un appel plus récent a démarré pendant le fetch, on
      // n'écrit plus rien dans l'UI : c'est l'appel récent qui
      // décide de l'état final.
      if (maGen !== this._genRendu) return;
      if (!resp.ok) {
        this._remettrePlaceholderRendu();
        return;
      }
      const data = await resp.json().catch(() => ({}));
      if (maGen !== this._genRendu) return;
      if (data.cache_valide !== true) {
        // v0.14.3 — Préférence « compiler automatiquement si pas de
        // cache valide ». Quand active (par défaut), on lance la
        // compilation à l'ouverture de l'onglet Rendu PDF au lieu
        // d'afficher juste le placeholder « Cliquez sur Compiler ».
        //
        // La pref est en localStorage (par PC, cohérent avec pref-split).
        // Lecture protégée : si la fonction n'est pas encore définie
        // (chargement initial), on retombe sur le comportement de
        // placeholder (mode opt-in implicite, sûr).
        const autoCompile =
          typeof window.prefAutoCompileEstActive === 'function'
          && window.prefAutoCompileEstActive();
        if (autoCompile) {
          // Auto-compilation : on lance compilerRendu en mode
          // _chargementAuto pour que le statut affiche
          // « Compilation en cours… » de façon cohérente avec
          // l'auto-cache. compilerRendu hérite de la génération
          // _genRendu posée par cet appel (pas de ré-incrément).
          this._chargementAuto = true;
          try {
            await this.compilerRendu();
          } finally {
            this._chargementAuto = false;
          }
          return;
        }
        // Sinon : comportement v0.13.7.6.1.1 (placeholder visible,
        // l'utilisateur doit cliquer sur Compiler).
        this._remettrePlaceholderRendu();
        return;
      }
      // Cache valide : on lance la « compilation » qui sera en réalité
      // un service-depuis-cache (X-Seq-Depuis-Cache=1) → instantané.
      // On indique le contexte via un drapeau pour que le statut soit
      // affiché « ✓ Servi depuis le cache » plutôt que «  Compilé en X ms ».
      this._chargementAuto = true;
      try {
        // compilerRendu utilise la même protection _genRendu pour ne
        // pas écrire dans l'UI si une exécution plus récente arrive.
        await this.compilerRendu();
      } finally {
        this._chargementAuto = false;
      }
    } catch (_) {
      // Si une exécution plus récente est en cours, ne touche pas l'UI.
      if (maGen !== this._genRendu) return;
      // Réseau down : on remet aussi le placeholder. L'utilisateur
      // peut toujours cliquer sur Compiler pour réessayer.
      this._remettrePlaceholderRendu();
    }
  }

  /**
   * v0.13.7.6.1.1 — Remet la zone Rendu PDF en état initial :
   *   - masque l'iframe (et libère son src pour éviter de garder en
   *     mémoire un PDF d'un autre item)
   *   - masque la zone d'erreur
   *   - vide le statut
   *   - affiche le placeholder « Cliquer pour compiler »
   *
   * Appelée quand on bascule vers l'onglet Rendu d'un item dont le
   * cache PDF n'est pas valide, pour éviter que l'iframe d'un item
   * précédent reste visible.
   */
  _remettrePlaceholderRendu() {
    const iframe = this.$('pdf-iframe');
    const erreurEl = this.$('rendu-erreur');
    const statusEl = this.$('rendu-status');
    const placeholder = this.$('rendu-placeholder');
    // v0.14.4 — Spinner ajouté en v0.14.4. À masquer aussi pour que le
    // placeholder ne soit pas superposé au spinner si _remettrePlaceholderRendu
    // est appelé pendant qu'une compilation venait juste de démarrer.
    const loadingEl = this.$('rendu-loading');
    if (iframe) {
      // Libère le blob URL précédent si présent (évite la fuite mémoire
      // et le PDF résiduel affiché).
      // v0.16 — Depuis l'affichage via le viewer pdf.js, `iframe.src`
      // pointe vers viewer.html (pas le blob). On révoque donc le blob
      // mémorisé dans le dataset. Filet : on couvre aussi l'ancien cas
      // où src serait directement un blob:.
      if (iframe._seqBlobUrl) {
        try { URL.revokeObjectURL(iframe._seqBlobUrl); } catch (_) {}
        iframe._seqBlobUrl = null;
      }
      if (iframe.src && iframe.src.startsWith('blob:')) {
        try { URL.revokeObjectURL(iframe.src); } catch (_) {}
      }
      iframe.removeAttribute('src');
      iframe.style.display = 'none';
    }
    if (erreurEl) {
      erreurEl.style.display = 'none';
      erreurEl.innerHTML = '';
    }
    if (statusEl) statusEl.textContent = '';
    if (loadingEl) loadingEl.style.display = 'none';
    if (placeholder) placeholder.style.display = '';
  }

  /**
   * Compile le PDF de l'item courant en POSTant vers
   * `${endpointBase}/${id}/rendu-pdf`. Affiche le PDF dans l'iframe
   * `#{prefixe}-pdf-iframe` ou les erreurs dans
   * `#{prefixe}-rendu-erreur`.
   *
   * v0.13.7.6.1.1.2 — Protection contre la race condition avec
   * verifierCacheEtAfficher. Si un autre appel (auto-cache ou clic
   * utilisateur) démarre pendant qu'on attend la réponse, on
   * abandonne silencieusement nos écritures UI : c'est l'appel le
   * plus récent qui décide de l'état final.
   *
   * Note : on incrémente `_genRendu` AUSSI quand on est appelé depuis
   * un clic utilisateur direct (bouton Compiler). Cela invalide une
   * éventuelle exécution `verifierCacheEtAfficher` toujours en vol.
   * Si on est appelé depuis `verifierCacheEtAfficher` lui-même, la
   * génération a déjà été incrémentée juste avant ; on respecte
   * la valeur courante (pas d'incrément redondant) en utilisant le
   * drapeau `_chargementAuto`.
   */
  async compilerRendu() {
    if (!this.itemActif) return;
    this._assurerToolbarRendu();
    const id = this.itemActif.id;

    // v0.13.7.6.1.1.2 — Si on est appelé en dehors d'un auto-chargement
    // (clic utilisateur), on incrémente la génération pour invalider
    // un éventuel verifierCacheEtAfficher en vol depuis un changement
    // d'item antérieur.
    if (!this._chargementAuto) {
      this._genRendu = (this._genRendu || 0) + 1;
    }
    const maGen = this._genRendu;

    // v0.14.3 — Sauvegarde silencieuse avant compilation.
    //
    // Pour garantir que le PDF reflète toujours l'état du formulaire
    // (et non un état périmé en BdD), on déclenche d'abord la
    // sauvegarde de l'atome courant.
    //
    // Pourquoi conditionnel sur `this.modifie` : si l'item n'a pas de
    // modifications en attente, la sauvegarde serait un round-trip
    // serveur inutile (PATCH /api/.../{id} avec les mêmes données).
    // Skipper l'appel dans ce cas réduit notablement la latence
    // perceptible du clic « Compiler » sur des items non modifiés
    // (cas le plus fréquent quand on navigue dans la liste).
    //
    // Pourquoi pas en mode auto-chargement (`_chargementAuto`) :
    // dans ce cas on lit juste un PDF déjà en cache, l'état de la
    // BdD n'a pas d'influence sur le résultat. Sauvegarder serait
    // futile et risquerait d'invalider le cache au passage
    // (sauvegarder() fait `_texChargeId = null`).
    if (!this._chargementAuto && this.modifie) {
      const okSave = await this.sauvegarder({ silencieuse: true });
      if (maGen !== this._genRendu) return;  // race : item changé
      if (!okSave) {
        // Toast d'erreur déjà émis par sauvegarder(). On n'enchaîne pas
        // la compilation pour ne pas générer un PDF qui ne refléterait
        // pas l'intention de l'utilisateur (PDF de l'état BdD ancien
        // alors qu'il vient d'éditer le formulaire).
        return;
      }
    }

    const btn = this.$('btn-compiler');
    const statusEl = this.$('rendu-status');
    const iframe = this.$('pdf-iframe');
    const erreurEl = this.$('rendu-erreur');
    const placeholder = this.$('rendu-placeholder');
    // v0.14.4 — Spinner visuel (cercle qui tourne + texte) pendant la
    // compilation. Le bloc #atl-<type>-rendu-loading est dans le HTML
    // statique de chaque atelier, masqué par défaut.
    const loadingEl = this.$('rendu-loading');

    if (btn) btn.disabled = true;
    if (statusEl) {
      statusEl.textContent = this._chargementAuto
        ? 'Chargement du PDF en cache…'
        : 'Compilation en cours…';
    }
    if (erreurEl) {
      erreurEl.style.display = 'none';
      erreurEl.innerHTML = '';
    }
    if (placeholder) placeholder.style.display = 'none';
    // v0.14.4 — On masque aussi l'iframe (au cas où un PDF précédent
    // serait encore affiché) et on montre le spinner. Cas particulier
    // de l'auto-cache : la réponse arrive en quelques ms (servie depuis
    // cache), donc le spinner ne sera visible qu'un flash imperceptible.
    // Mais pour une vraie compilation (qq centaines de ms à plusieurs s),
    // le spinner donne un feedback indispensable.
    if (iframe) iframe.style.display = 'none';
    if (loadingEl) loadingEl.style.display = 'flex';

    try {
      const resp = await fetch(
        `${this.config.endpointRenduPdf}/${encodeURIComponent(id)}/rendu-pdf`,
        { method: 'POST' },
      );
      // v0.13.7.6.1.1.2 — Si une exécution plus récente est en cours
      // (l'utilisateur a cliqué sur une autre carte pendant le fetch),
      // on n'écrit plus rien dans l'UI.
      if (maGen !== this._genRendu) {
        // On consomme la réponse pour libérer la connexion, mais sans
        // l'utiliser. Si c'est un PDF, son blob serait inutile.
        if (resp.ok) {
          try { await resp.blob(); } catch (_) {}
        }
        return;
      }

      if (resp.ok) {
        const cache = resp.headers.get('X-Seq-Depuis-Cache') === '1';
        const duree = resp.headers.get('X-Seq-Duree-Ms') || '?';
        const blob = await resp.blob();
        // Re-vérification après le second await.
        if (maGen !== this._genRendu) return;
        const url = URL.createObjectURL(blob);
        // v0.14.4 — Masquer le spinner ET afficher l'iframe en
        // une seule passe pour éviter le flash visuel (le spinner
        // disparaît au moment où le PDF est prêt).
        if (loadingEl) loadingEl.style.display = 'none';
        if (iframe) {
          // v0.16 — Affichage forcé via le viewer pdf.js embarqué
          // (static/vendor/pdfjs) plutôt que l'affichage natif du
          // navigateur. Garantit un rendu inline identique quel que
          // soit le navigateur et ses réglages PDF (symptôme « ouvre
          // dans une nouvelle fenêtre » sur poste verrouillé). Le blob
          // est same-origin avec le viewer, donc accepté en ?file=.
          this._afficherPdfDansViewer(iframe, url);
          iframe.style.display = 'block';
        }
        if (statusEl) {
          statusEl.textContent = cache
            ? '✓ PDF servi depuis le cache'
            : `✓ Compilé en ${duree} ms`;
        }
      } else {
        const data = await resp.json().catch(() => ({}));
        if (maGen !== this._genRendu) return;
        // v0.14.4 — Masquer le spinner avant d'afficher l'erreur.
        if (loadingEl) loadingEl.style.display = 'none';
        if (statusEl) statusEl.textContent = '✗ Échec';
        this._afficherErreurCompilation(resp.status, data);
      }
    } catch (e) {
      if (maGen !== this._genRendu) return;
      // v0.14.4 — Masquer le spinner avant d'afficher l'erreur réseau.
      if (loadingEl) loadingEl.style.display = 'none';
      if (statusEl) statusEl.textContent = '✗ Erreur réseau';
      if (erreurEl) {
        erreurEl.innerHTML =
          `<div class="rendu-err-title">⚠ Erreur réseau</div>` +
          `<p>${Atelier.escHtml(String(e))}</p>`;
        erreurEl.style.display = 'block';
      }
    } finally {
      // Le bouton et le bandeau d'onglets doivent rester cohérents même
      // si on a abandonné (génération obsolète) — mais on ne touche pas
      // à ces éléments parce qu'ils ne dépendent pas de la course
      // (le bouton se réactive proprement même si on n'a pas affiché
      // le PDF de l'ancien item).
      if (btn) btn.disabled = false;
      // v0.14.4 — Sécurité : si on est arrivé ici par race condition
      // (return anticipé après un await), le spinner pourrait être
      // resté affiché. Le masquer dans tous les cas. Les cas de succès
      // l'ont déjà masqué ; ici c'est filet de sécurité.
      if (loadingEl) loadingEl.style.display = 'none';
      // Sécurité : bandeau d'onglets reste visible après compilation.
      if (this.itemActif) {
        this.setDisplay('tabs', 'flex');
      }
    }
  }

  /**
   * v0.16 — Affiche un PDF (blob URL) dans l'iframe via le viewer
   * pdf.js embarqué (static/vendor/pdfjs), au lieu de l'affichage natif
   * du navigateur.
   *
   * POURQUOI : sur poste verrouillé (établissement), le navigateur peut
   * être configuré pour ouvrir les PDF dans une nouvelle fenêtre ou les
   * télécharger au lieu de les afficher inline dans une iframe. Le
   * viewer pdf.js dessine le PDF dans un <canvas> : le navigateur ne voit
   * jamais un content-type application/pdf à « gérer », donc le rendu
   * inline est garanti quel que soit le navigateur et ses réglages.
   *
   * Le PDF est passé en `?file=<blobUrl>`. Le blob étant créé par cette
   * page (même origine que le viewer servi par Flask depuis /static),
   * pdf.js l'accepte sans erreur d'origine croisée.
   *
   * Le blob URL est mémorisé sur `iframe._seqBlobUrl` pour pouvoir le
   * révoquer plus tard (cf. _remettrePlaceholderRendu), car `iframe.src`
   * pointe désormais vers viewer.html et non vers le blob.
   *
   * @param {HTMLIFrameElement} iframe
   * @param {string} blobUrl  URL blob: du PDF à afficher
   */
  _afficherPdfDansViewer(iframe, blobUrl) {
    // Révoquer un éventuel blob précédent encore mémorisé (évite la fuite
    // mémoire si on enchaîne deux compilations sans repasser par le
    // placeholder).
    if (iframe._seqBlobUrl && iframe._seqBlobUrl !== blobUrl) {
      try { URL.revokeObjectURL(iframe._seqBlobUrl); } catch (_) {}
    }
    iframe._seqBlobUrl = blobUrl;

    const base = (this.config && this.config.viewerPdfBase)
      ? this.config.viewerPdfBase
      : '/static/vendor/pdfjs/web/viewer.html';
    iframe.src = `${base}?file=${encodeURIComponent(blobUrl)}`;
  }


  /**
   * Affichage du panneau d'erreurs de compilation LaTeX. Liste
   * cliquable des erreurs, bouton "Voir le .tex brut", bouton "Voir le
   * log complet".
   *
   * Pattern hérité de l'ancien `_carteAfficherErreurCompilation` et
   * `_evalAfficherErreurCompilation`.
   */
  _afficherErreurCompilation(status, data) {
    const erreurEl = this.$('rendu-erreur');
    if (!erreurEl) return;

    if (status === 404) {
      erreurEl.innerHTML =
        `<div class="rendu-err-title">⚠ Élément introuvable</div>` +
        `<p>L'élément a-t-il été supprimé ?</p>`;
      erreurEl.style.display = 'block';
      return;
    }

    const erreurs = Array.isArray(data.erreurs) ? data.erreurs : [];
    const titre = status === 503
      ? 'Compilation impossible (infrastructure)'
      : 'La compilation a échoué';

    this.lignesFautives = erreurs
      .filter(e => e.ligne != null)
      .map(e => e.ligne);

    const lignesHtml = erreurs.map(e => {
      const ligne = e.ligne != null ? `L.${e.ligne}` : '—';
      const ctx = e.contexte
        ? `<div class="rendu-err-ctx">${Atelier.escHtml(e.contexte)}</div>`
        : '';
      const varGlob = this._varGlobale();
      const clickable = e.ligne != null
        ? `onclick="${varGlob}.scrollVersLigneTex(${e.ligne})"`
        : '';
      const cls = e.ligne != null
        ? 'rendu-err-item clickable'
        : 'rendu-err-item';
      return `
        <li class="${cls}" ${clickable}>
          <div class="rendu-err-head">
            <span class="rendu-err-ligne">${ligne}</span>
            <span class="rendu-err-msg">${Atelier.escHtml(e.message || '')}</span>
          </div>
          ${ctx}
        </li>`;
    }).join('');

    const varGlob = this._varGlobale();
    erreurEl.innerHTML = `
      <div class="rendu-erreurs">
        <div class="rendu-err-title">
          ⚠ ${Atelier.escHtml(titre)} (${erreurs.length} erreur${erreurs.length > 1 ? 's' : ''}).
        </div>
        <ul class="rendu-err-list">${lignesHtml ||
          '<li class="rendu-err-item"><em>Aucune erreur détaillée.</em></li>'}</ul>
        <div class="rendu-tex-toggle">
          <button class="btn-sm" type="button" onclick="${varGlob}.toggleTexBrut()">
            <span id="${this.prefixe}-rendu-tex-label">Voir le .tex brut</span>
          </button>
        </div>
        <div class="rendu-tex-zone" id="${this.prefixe}-rendu-tex" style="display:none">
          <div class="rendu-loading"><p>Chargement du .tex…</p></div>
        </div>
      </div>`;
    erreurEl.style.display = 'block';
  }

  /**
   * Toggle de la zone .tex brut. Au premier clic, fetch
   * `${endpointBase}/${id}/rendu-tex` et affiche le contenu avec
   * numéros de ligne et highlight des lignes fautives.
   */
  async toggleTexBrut() {
    const zone = this.$('rendu-tex');
    const label = this.$('rendu-tex-label');
    if (!zone || !label) return;

    if (zone.style.display === 'none') {
      zone.style.display = 'block';
      label.textContent = 'Masquer le .tex brut';
      // v0.13.6.16 — Cache PDF par item : on regarde si la zone DOM
      // contient déjà le .tex de l'item courant. Avant : `_texCharge`
      // (booléen global) invalidé à chaque ouverture, ce qui forçait
      // un re-fetch même quand la BdD était inchangée. Maintenant :
      // `_texChargeId` retient l'id de l'item dont le DOM contient
      // le .tex, invalidé uniquement à la sauvegarde / suppression
      // (= quand les données en BdD changent réellement).
      const dejaCharge = this.itemActif
                      && this._texChargeId === this.itemActif.id;
      if (!dejaCharge && this.itemActif) {
        try {
          const resp = await fetch(
            `${this.config.endpointRenduPdf}/${encodeURIComponent(this.itemActif.id)}/rendu-tex`,
          );
          if (resp.ok) {
            const tex = await resp.text();
            this._afficherTexBrut(tex);
            this._texChargeId = this.itemActif.id;
          } else {
            zone.innerHTML = '<p>Impossible de charger le .tex brut.</p>';
          }
        } catch (err) {
          zone.innerHTML = `<p>Erreur : ${Atelier.escHtml(String(err))}</p>`;
        }
      }
    } else {
      zone.style.display = 'none';
      label.textContent = 'Voir le .tex brut';
    }
  }

  _afficherTexBrut(tex) {
    const zone = this.$('rendu-tex');
    if (!zone) return;
    const lignesFautives = new Set(this.lignesFautives);
    const lignes = tex.split('\n').map((l, i) => {
      const numero = i + 1;
      const faute = lignesFautives.has(numero);
      const cls = 'rendu-tex-line' + (faute ? ' rendu-tex-line--faute' : '');
      return `<div class="${cls}" id="${this.prefixe}-rendu-tex-l${numero}">` +
             `<span class="rendu-tex-num">${numero}</span>` +
             `<span class="rendu-tex-code">${Atelier.escHtml(l) || '&nbsp;'}</span>` +
             `</div>`;
    }).join('');
    zone.innerHTML = `<div class="rendu-tex-code-bloc">${lignes}</div>`;
  }

  /**
   * Scroll dans la zone .tex brut vers une ligne donnée (clic sur une
   * erreur dans la liste). Ouvre la zone si pas déjà visible.
   */
  async scrollVersLigneTex(ligne) {
    const zone = this.$('rendu-tex');
    if (!zone) return;
    // v0.13.6.16 — Cache par item (cf. toggleTexBrut).
    const dejaCharge = this.itemActif
                    && this._texChargeId === this.itemActif.id;
    if (zone.style.display === 'none' || !dejaCharge) {
      await this.toggleTexBrut();
    }
    const elt = this.$(`rendu-tex-l${ligne}`);
    if (elt) {
      elt.scrollIntoView({ behavior: 'smooth', block: 'center' });
      const oldStyle = elt.style.boxShadow;
      elt.style.boxShadow = 'inset 0 0 0 2px #dc2626';
      setTimeout(() => { elt.style.boxShadow = oldStyle; }, 1500);
    }
  }

  /**
   * Voir le LaTeX généré (popup ou onglet selon la convention). Ouvre
   * une nouvelle fenêtre vers `${endpointBase}/${id}/rendu-tex`.
   */
  /**
   * v0.17.1 — Affiche le LaTeX généré dans la modale commune
   * (window.atelierAfficherLatex), à partir du .tex produit CÔTÉ SERVEUR
   * (route <endpointRenduPdf>/<id>/rendu-tex). Le LaTeX est désormais une
   * source de vérité unique côté serveur ; le client se contente de le
   * récupérer et de l'afficher (séparation des rôles).
   *
   * Si l'item a des modifications non enregistrées, on sauvegarde d'abord
   * (silencieusement) pour que le .tex reflète l'état courant — même logique
   * que compilerRendu.
   *
   * NB v0.17.1 : exercice/notion/methode/fiche conservent encore une surcharge
   * de génération CLIENT (retrait prévu en v0.17.2). Cette base sert dès
   * maintenant carte, séquence et évaluation.
   *
   * `this.config.typeLatex` (ou le préfixe) fournit la clé de libellé de la
   * modale (cf. atelierAfficherLatex).
   */
  async voirLatex() {
    if (!this.itemActif) return;
    if (this.modifie) {
      const okSave = await this.sauvegarder({ silencieuse: true });
      if (!okSave) return;  // toast d'erreur déjà émis par sauvegarder()
    }
    const id = this.itemActif.id;
    let tex;
    try {
      const resp = await fetch(
        `${this.config.endpointRenduPdf}/${encodeURIComponent(id)}/rendu-tex`,
        { method: 'GET' },
      );
      if (!resp.ok) {
        let msg = `HTTP ${resp.status}`;
        try { const j = await resp.json(); if (j.error) msg = j.error; } catch (e) {}
        this.toast(`Impossible de récupérer le LaTeX : ${msg}`, 'erreur');
        return;
      }
      tex = await resp.text();
    } catch (e) {
      this.toast('Erreur réseau lors de la récupération du LaTeX.', 'erreur');
      return;
    }
    const typeLatex = this.config.typeLatex || this.id || 'atome';
    if (typeof window.atelierAfficherLatex === 'function') {
      window.atelierAfficherLatex(typeLatex, tex);
    } else {
      this.toast('Module commun manquant : LaTeX dans la console.', 'erreur');
      console.log(tex);
    }
  }

  // ── v0.13.6.16 — Plus d'invalidation du cache .tex à ouvrirItem /
  // nouvelItem. Selon la règle générale « on n'invalide un rendu PDF
  // que si les données correspondantes en base changent », le cache
  // est désormais piloté par `_texChargeId` (id de l'item dont le DOM
  // contient le .tex). Il reste valide tant que la BdD de cet item
  // n'a pas changé (= jusqu'à sauvegarder() / supprimer()). Voir
  // toggleTexBrut et scrollVersLigneTex pour la logique de cache.
  //
  // Les méthodes ouvrirItem et nouvelItem ne sont donc plus surchargées
  // ici : le comportement parent (AtelierEditeur) suffit.
}

window.AtelierEditeur = AtelierEditeur;

// ── Listener global Échap pour annuler la sélection multi ─────────────────
//
// v0.13.6.8 — Quand l'utilisateur appuie sur Échap et qu'au moins un
// atelier a une sélection multi active, on la vide. Si plusieurs
// ateliers ont une sélection (cas peu probable mais possible), on les
// vide tous.
//
// On vérifie aussi qu'on n'est pas dans un input/textarea/select pour
// ne pas voler le Échap qui aurait une autre signification dans le
// formulaire (ex: fermer un autocomplete).

(function _installerListenerEchap() {
  if (window.__atelierEchapInstalle__) return;
  window.__atelierEchapInstalle__ = true;
  document.addEventListener('keydown', function (ev) {
    if (ev.key !== 'Escape') return;
    const tag = (ev.target && ev.target.tagName || '').toUpperCase();
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)) return;
    // Parcourir les variables ATELIER_* connues
    const noms = ['ATELIER_CARTE', 'ATELIER_NOTION', 'ATELIER_METHODE',
                  'ATELIER_FICHE', 'ATELIER_EXERCICE'];
    let aQuelqueChose = false;
    for (const n of noms) {
      const at = window[n];
      if (at && at.selectionMulti && at.selectionMulti.size > 0) {
        at.selectionMultiEffacer();
        aQuelqueChose = true;
      }
    }
    if (aQuelqueChose) {
      ev.preventDefault();
    }
  });
})();
