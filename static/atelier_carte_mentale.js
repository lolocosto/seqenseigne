/**
 * static/atelier_carte_mentale.js — v0.56.2
 *
 * Atelier « Carte mentale » (portée Séquence) : une carte mentale par partie de
 * séquence, pour les deux modèles de référentiel (Fiches de résumé par objectif et
 * Notions et méthodes).
 *
 * v0.56.1 — HARMONISATION (demande de Laurent du 13 novembre 2026) : l'atelier est
 * refait sur les briques des autres ateliers. Il étend AtelierEditeur, comme
 * AtelierFiche et AtelierCarte, et en hérite tout le comportement : liste à gauche
 * (filtre d'état), ouverture, création (« + Créer »), enregistrement (PATCH),
 * suppression, Valider / Repasser en cours, badge « modifié », garde de sortie
 * (modale 3 boutons), verrou lecture seule d'une carte validée, onglets Édition /
 * Rendu PDF, compilation avec cache, viewer pdf.js, erreurs LaTeX cliquables,
 * .tex brut, « LaTeX généré » (Ctrl+L). La v0.55 avait son propre mécanisme
 * (fetch maison, pas d'onglets ni de garde) : supprimé.
 *
 * Spécificités (seules surcharges) :
 *   - un élément par PARTIE de la séquence, carte présente ou absente ;
 *     identifiant = numéro de la partie ; une partie sans carte s'ouvre sur le
 *     modèle proposé par le serveur ;
 *   - l'URL dépend de la séquence filtrée (endpointBase calculé, URL de
 *     SeqnivPur.urlCartesMentales, partagée avec l'onglet « Rendu PDF » de la
 *     séquence) ;
 *   - filtre « Sans carte » ; « + Créer » crée la carte de la partie ouverte (ou
 *     de la première partie sans carte) ;
 *   - séquence validée : tout en lecture seule (le serveur refuse par 409) ;
 *   - rendu : version à compléter / complète, la carte de la partie ou toutes
 *     celles de la séquence (même générateur que le livret et « Tout compiler »).
 *
 * v0.56.2 (demandes de Laurent du 13 novembre, 16 h 11) :
 *   - poignée de redimensionnement de la liste (atelierInstallerSplitter, comme
 *     les autres ateliers, installée par initAtelierSplitters dans app.js) ;
 *   - aucune séquence choisie (« — Toutes les séquences — ») : la liste montre
 *     les parties de toutes les séquences du niveau, groupées par séquence
 *     (préfixe N09/S03/P2), filtres d'état et « Sans carte » actifs. L'élément
 *     porte alors sa séquence dans son identifiant (« S03:2 ») ; urlItem /
 *     urlRenduItem en tirent l'URL de sa séquence (édition, rendu, « toute la
 *     séquence » = la séquence de l'entrée ouverte).
 *
 * v0.56.3 (demande de Laurent du 13 novembre, 17 h 03 : « toutes les fonctionnalités
 * communes à tous les ateliers atomiques ») — briques d'AtelierEditeur, aucune copie :
 *   - multisélection (Ctrl+clic, Maj+clic, clic droit, Échap) et actions groupées
 *     « Valider » / « Repasser en cours » (selectionMultiAppliquerEtat) : l'atelier
 *     ne fournit que l'URL du changement d'état (urlEtat = la partie) et les
 *     exclusions (raisonHorsEtat : partie sans carte, séquence validée) ; la
 *     sélection est vidée quand la liste change de niveau ou de séquence (les
 *     identifiants « 1 », « 2 »… se répètent d'une séquence à l'autre) ;
 *   - mode côte-à-côte (Préférences) : mêmes règles CSS que Notion, Méthode et
 *     Fiche, poignée édition / rendu (initAtelierSplitters) ;
 *   - lien direct (?atelier=carte_mentale&niveau&seq&atome=<partie>) et Recherche.
 *
 * Routes : /api/v2/livret-sequence/<niveau>/<séquence>/cartes-mentales
 *   GET (liste), POST (créer), /<n> GET / PATCH / DELETE,
 *   /<n>/rendu-pdf[/info] et /<n>/rendu-tex (?version=…&portee=partie|sequence) ;
 *   v0.56.2 : /api/v2/livret-sequence/<niveau>/cartes-mentales (toutes les séquences).
 */

// ── Logique pure (testée par tests_js/cartes_mentales_atelier.test.js) ─────

const CarteMentalePur = {
  nbBranches(latex) {
    return ((latex || '').match(/\\seqCMBranche(?![A-Za-z])/g) || []).length;
  },

  /** v0.56.2 — Identifiant d'un élément en mode « toutes les séquences ». */
  idToutes(sequence, numero) {
    return `${sequence}:${numero}`;
  },

  /** v0.56.2 — {sequence, numero} d'un identifiant (« S03:2 » ou « 2 »). */
  decouperId(id) {
    const m = /^([^:]+):(\d+)$/.exec(String(id == null ? '' : id));
    return m ? { sequence: m[1], numero: m[2] } : { sequence: '', numero: String(id) };
  },

  /** Élément de liste (contrat d'AtelierEditeur) depuis une partie de l'API.
   *  v0.56.2 — `sequence` donnée (mode « toutes les séquences ») : l'élément
   *  porte sa séquence et son droit de modification, et son identifiant
   *  contient la séquence (unique sur tout le niveau). */
  element(p, sequence, modifiable) {
    const c = p.carte || null;
    const el = {
      id: sequence ? CarteMentalePur.idToutes(sequence, p.numero) : String(p.numero),
      numero: p.numero,
      libelle: p.libelle || '',
      presente: !!c,
      titre: c ? (c.titre || '') : '',
      etat_code: c ? (c.etat_code || 'en_cours') : 'en_cours',
      branches: c ? CarteMentalePur.nbBranches(c.latex) : 0,
    };
    if (sequence) {
      el.sequence = sequence;
      el.modifiable = modifiable !== false;
    }
    return el;
  },

  /** v0.56.2 — Liste à plat de la réponse « toutes les séquences » du niveau. */
  elementsNiveau(data) {
    return ((data && data.sequences) || []).flatMap(s =>
      (s.parties || []).map(p => CarteMentalePur.element(p, s.sequence, s.modifiable)));
  },

  /** v0.56.2 — Partie visée par « + Créer » : la partie ouverte si elle n'a pas
   *  de carte, sinon la première partie sans carte (de la séquence de la partie
   *  ouverte, s'il y en a une) ; null si aucune. Retour : l'élément de liste. */
  cibleCreation(liste, actif) {
    if (actif && !actif.presente) return actif;
    const seq = actif ? (actif.sequence || '') : '';
    return (liste || []).find(el => !el.presente && (!seq || (el.sequence || '') === seq)) || null;
  },

  /** Filtre d'état de la liste : '' | 'en_cours' | 'valide' | 'absente'. */
  garder(el, filtre) {
    if (!filtre) return true;
    if (filtre === 'absente') return !el.presente;
    return el.presente && el.etat_code === filtre;
  },

  /** Paramètres du rendu (version, portée). */
  parametres(version, portee) {
    const p = new URLSearchParams();
    p.set('version', version === 'corrigee' ? 'corrigee' : 'eleve');
    p.set('portee', portee === 'sequence' ? 'sequence' : 'partie');
    return '?' + p.toString();
  },

  /** v0.56.3 — Raison d'exclure un élément d'un changement d'état (unitaire ou
   *  groupé), null s'il peut changer : partie sans carte (rien à valider),
   *  séquence validée (lecture seule ; le serveur refuse aussi, 409).
   *  `modifiableSeq` : droit de la séquence filtrée (mode séquence). */
  raisonHorsEtat(el, modifiableSeq) {
    if (!el) return 'introuvable';
    if (!el.presente) return 'sans carte';
    const modifiable = (typeof el.modifiable === 'boolean') ? el.modifiable : modifiableSeq !== false;
    if (!modifiable) return 'séquence validée';
    return null;
  },

  /** Partie à créer : celle qui est ouverte si elle n'a pas de carte, sinon la
   *  première partie sans carte ; null si toutes ont leur carte. */
  partieACreer(liste, actif) {
    if (actif && !actif.presente) return actif.numero;
    const libre = (liste || []).find(el => !el.presente);
    return libre ? libre.numero : null;
  },
};


class AtelierCarteMentale extends AtelierEditeur {
  constructor() {
    super({
      id:                 'carte_mentale',
      prefixe:            'atl-cm',
      titreToolbar:       'Atelier Carte mentale',
      endpointBase:       '',          // calculé (séquence filtrée), voir plus bas
      typeLatex:          'carte_mentale',
      labelExistant:      'Modifier la carte mentale',
      labelNouveau:       'Nouvelle carte mentale',
      confirmSuppression: 'Supprimer la carte mentale de cette partie ?',
      messageEnregistre:  'Carte mentale enregistrée.',
      messageSupprime:    'Carte mentale supprimée.',
      typeApi:            'carte_mentale',
    });
    // L'URL dépend de la séquence filtrée : endpointBase (CRUD) et
    // endpointRenduPdf (rendu) sont calculés à chaque usage.
    // v0.56.2 — sans séquence filtrée : séquence de la partie visée ou ouverte.
    const url = () => {
      const niv = window.ATL_FILTRE_NIVEAU || '';
      const seq = this._seqContexte();
      return (niv && seq && window.SeqnivPur)
        ? window.SeqnivPur.urlCartesMentales(niv, seq) : '/api/v2/livret-sequence/-/-/cartes-mentales';
    };
    Object.defineProperty(this.config, 'endpointBase', { get: url, configurable: true });
    Object.defineProperty(this.config, 'endpointRenduPdf', { get: url, configurable: true });
    this.filtreEtat = '';
    this.modifiable = true;          // faux si la séquence est validée
    this._seqCible = '';             // v0.56.2 : séquence de la partie à créer
  }

  // ── v0.56.2 — Mode « toutes les séquences » ─────────────────────────────

  /** Aucune séquence choisie (niveau seul) : toutes les séquences du niveau. */
  _toutes() {
    return !!(window.ATL_FILTRE_NIVEAU || '') && !(window.ATL_FILTRE_SEQ || '');
  }

  /** Séquence des URL : celle du filtre, sinon celle de la partie visée ou ouverte. */
  _seqContexte() {
    return window.ATL_FILTRE_SEQ || this._seqCible
      || (this._itemActif && this._itemActif.sequence) || '';
  }

  // L'élément renvoyé par le serveur (GET, PATCH, POST) a pour identifiant le
  // numéro de la partie ; en mode « toutes les séquences », il reçoit
  // l'identifiant de la liste (« S03:2 ») pour rester reconnu par la liste
  // (élément actif, rechargement) et pour que ses URL visent sa séquence.
  get itemActif() {
    return this._itemActif || null;
  }

  set itemActif(item) {
    if (item && typeof item === 'object' && item.sequence && item.numero != null
        && this._toutes()) {
      item.id = CarteMentalePur.idToutes(item.sequence, item.numero);
    }
    this._itemActif = item || null;
  }

  urlItem(id) {
    const { sequence, numero } = CarteMentalePur.decouperId(id);
    const niv = window.ATL_FILTRE_NIVEAU || '';
    const seq = sequence || this._seqContexte();
    return window.SeqnivPur.urlCartesMentales(niv || '-', seq || '-', numero);
  }

  urlRenduItem(id) {
    return this.urlItem(id);
  }

  /** v0.56.3 — Changement d'état (unitaire et groupé) : PATCH {etat_code} sur la
   *  partie, même route que l'enregistrement. */
  urlEtat(id) {
    return this.urlItem(id);
  }

  /** v0.56.3 — Exclusions des actions groupées (voir CarteMentalePur.raisonHorsEtat). */
  raisonHorsEtat(el) {
    return CarteMentalePur.raisonHorsEtat(el, this.modifiable);
  }

  sequenceDeCreation() {
    return window.ATL_FILTRE_SEQ || this._seqCible || '';
  }

  // ── Liste ───────────────────────────────────────────────────────────────

  async chargerListe() {
    const niv = window.ATL_FILTRE_NIVEAU || '';
    const seq = window.ATL_FILTRE_SEQ || '';
    this._messageListe = '';
    this.liste = [];
    if (!niv) {
      this._messageListe = 'Choisir un niveau.';
    } else {
      // v0.56.2 — sans séquence : toutes les séquences du niveau (comme les
      // autres ateliers) ; le droit de modification est porté par chaque entrée.
      const url = seq ? this.config.endpointBase
        : `/api/v2/livret-sequence/${encodeURIComponent(niv)}/cartes-mentales`;
      try {
        const resp = await fetch(url);
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
          this._messageListe = data.message || `Erreur chargement liste : HTTP ${resp.status}`;
        } else if (seq) {
          this.liste = (data.parties || []).map(p => CarteMentalePur.element(p));
          this.modifiable = data.modifiable !== false;
        } else {
          this.liste = CarteMentalePur.elementsNiveau(data);
          this.modifiable = true;
        }
      } catch (e) {
        this.toast('Erreur réseau : ' + e.message, 'erreur');
      }
    }
    // v0.56.3 — nouvelle portée (niveau ou séquence) : la sélection multiple est
    // vidée, car un identifiant « 2 » désignerait la partie 2 d'une AUTRE séquence.
    const contexte = `${niv}|${seq}`;
    if (this._contexteListe !== undefined && this._contexteListe !== contexte) {
      this.selectionMulti.clear();
      this.ancreSelectionId = null;
    }
    this._contexteListe = contexte;
    this._synchroniserItemActifAvecListe();
    this.rendreSidebar();
    this._majSelectionToolbar();
    this._majBoutonCreer();
  }

  filtrerListe(liste) {
    return (liste || []).filter(el => CarteMentalePur.garder(el, this.filtreEtat));
  }

  filtrerEtat(btn, etat) {
    btn.parentElement.querySelectorAll('.exo-etat').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    this.filtreEtat = etat;
    this.rendreSidebar();
  }

  _htmlListeVide() {
    const vide = this._toutes() ? 'Aucune partie dans les séquences de ce niveau.'
                                : 'Aucune partie dans cette séquence.';
    const msg = this._messageListe
      || (this.liste.length === 0 ? vide : 'Aucune partie avec ce filtre.');
    return '<div class="atl-list-vide" style="padding:14px 10px;color:var(--text-muted);'
         + `font-size:12px;text-align:center">${Atelier.escHtml(msg)}</div>`;
  }

  rendreItem(el) {
    const idLib = [window.ATL_FILTRE_NIVEAU || '', el.sequence || window.ATL_FILTRE_SEQ || '', 'P' + el.numero]
      .filter(Boolean).join('/');
    const titre = el.presente
      ? (el.titre || { html: '(sans titre)', derive: true })
      : { html: Atelier.escHtml(el.libelle || `Partie ${el.numero}`), derive: true };
    return Atelier.rendreItemHtml({
      actif: this.itemActif && this.itemActif.id === el.id,
      // v0.56.3 — multisélection d'AtelierEditeur, comme les autres ateliers.
      selected: this.estSelectionne(el.id),
      dataId: el.id,
      onclick: `ATELIER_CARTE_MENTALE.gererClicItem(event, '${Atelier.escAttr(el.id)}')`,
      oncontextmenu: `ATELIER_CARTE_MENTALE.gererClicDroitItem(event, '${Atelier.escAttr(el.id)}')`,
      id: idLib,
      titre,
      titleAttr: `${el.sequence ? el.sequence + ' · ' : ''}Partie ${el.numero}${el.libelle ? ' — ' + el.libelle : ''}`,
      placedTags: el.presente ? [`${el.branches} br.`] : ['sans carte'],
      etatCode: el.etat_code,
    });
  }

  // ── Création : la carte de la partie ouverte (ou de la première sans carte) ─

  _payloadCreation() {
    return { numero: this._numeroACreer };
  }

  async nouvelItem() {
    const toutes = this._toutes();
    const cible = CarteMentalePur.cibleCreation(this.liste, this.itemActif);
    // v0.56.2 — toutes les séquences : le droit est celui de la séquence visée.
    const modifiable = toutes ? !(cible && cible.modifiable === false) : this.modifiable;
    if (!modifiable) {
      this.toast('Séquence validée : la repasser en cours pour créer une carte mentale.', 'erreur');
      return;
    }
    if (!cible) {
      this.toast(toutes ? 'Aucune partie sans carte mentale.'
                        : 'Toutes les parties de la séquence ont déjà leur carte mentale.', 'erreur');
      return;
    }
    this._numeroACreer = cible.numero;
    this._seqCible = toutes ? (cible.sequence || '') : '';
    try {
      await super.nouvelItem();
    } finally {
      this._seqCible = '';
    }
  }

  _majBoutonCreer() {
    const b = document.getElementById('atl-cm-btn-creer');
    if (b) b.disabled = this._toutes() ? false : !this.modifiable;
  }

  // ── Formulaire ──────────────────────────────────────────────────────────

  collecterFormulaire() {
    return { titre: this.$('titre').value, latex: this.$('latex').value };
  }

  remplirFormulaire(item) {
    this.$('titre').value = item.titre || '';
    this.$('latex').value = item.latex || '';
    if (typeof item.modifiable === 'boolean') this.modifiable = item.modifiable;
    const info = this.$('info');
    if (info) {
      const partie = (this._toutes() && item.sequence ? `${item.sequence} · ` : '')
        + `Partie ${item.numero}` + (item.libelle ? ` — ${item.libelle}` : '');
      info.textContent = item.presente
        ? `${partie} · ${CarteMentalePur.nbBranches(item.latex)} branche(s) (4 à 8 conseillées)`
        : `${partie} · pas encore de carte : modèle proposé (Enregistrer ou « Créer la carte »).`;
    }
    const creer = this.$('btn-creer-partie');
    if (creer) creer.style.display = item.presente ? 'none' : '';
  }

  // Avertissements du contrôle (hors 4 à 8 branches) après l'enregistrement.
  async sauvegarder(options = {}) {
    const ok = await super.sauvegarder(options);
    const av = (ok && this.itemActif && this.itemActif.avertissements) || [];
    if (av.length) this.toast('Attention : ' + av.join(' ; '), 'erreur');
    return ok;
  }

  // ── Validation : PATCH de l'état sur la partie (même route que l'enregistrement) ─

  async basculerValidation() {
    if (!this.itemActif || !this.itemActif.presente) return;
    const cible = this.itemActif.etat_code === 'valide' ? 'en_cours' : 'valide';
    try {
      const resp = await fetch(this.urlEtat(this.itemActif.id), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ etat_code: cible }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        this.toast(`Erreur validation : ${data.message || data.error || resp.status}`, 'erreur');
        return;
      }
      this.itemActif.etat_code = cible;
      this.majToolbar();
      await this.chargerListe();
    } catch (e) {
      this.toast(`Erreur réseau : ${e.message}`, 'erreur');
    }
  }

  // ── Barre d'outils : partie sans carte, séquence validée ─────────────────

  majToolbar() {
    super.majToolbar();
    const it = this.itemActif;
    if (!it) return;
    const masquer = (suffixe) => { const e = this.$(suffixe); if (e) e.style.display = 'none'; };
    if (!it.presente) {
      masquer('btn-valider');
      masquer('btn-suppr');
      const badge = this.$('etat-badge');
      if (badge) { badge.textContent = 'Sans carte'; badge.className = 'atome-etat-badge'; }
    }
    if (!this.modifiable) {
      this._appliquerVerrouLectureSeule(true);
      ['btn-valider', 'btn-suppr', 'btn-save'].forEach(masquer);
      const titre = this.$('toolbar-title');
      if (titre) titre.textContent = this.config.labelExistant + ' (séquence validée : lecture seule)';
    }
  }

  // ── Rendu : version et portée dans la barre du rendu ─────────────────────

  _assurerToolbarRendu() {
    super._assurerToolbarRendu();
    const conteneur = this.$('rendu-toolbar');
    if (!conteneur || document.getElementById('atl-cm-rendu-version')) return;
    const mk = (id, titre, choix) => {
      const sel = document.createElement('select');
      sel.id = id;
      sel.className = 'btn-sm';
      sel.title = titre;
      for (const [v, lib] of choix) {
        const o = document.createElement('option');
        o.value = v;
        o.textContent = lib;
        sel.appendChild(o);
      }
      sel.addEventListener('change', () => this.verifierCacheEtAfficher());
      return sel;
    };
    const version = mk('atl-cm-rendu-version', 'Version',
                       [['eleve', 'À compléter (élève)'], ['corrigee', 'Complète']]);
    const portee = mk('atl-cm-rendu-portee', 'Compiler',
                      [['partie', 'Cette carte'], ['sequence', 'Toutes les cartes de la séquence']]);
    const status = conteneur.querySelector('[id$="-rendu-status"]');
    conteneur.insertBefore(version, status);
    conteneur.insertBefore(portee, status);
  }

  parametresRendu() {
    const v = document.getElementById('atl-cm-rendu-version');
    const p = document.getElementById('atl-cm-rendu-portee');
    return CarteMentalePur.parametres(v ? v.value : 'eleve', p ? p.value : 'partie');
  }
}

// ── Instance et exposition globale ─────────────────────────────────────────

window.CarteMentalePur = CarteMentalePur;
window.AtelierCarteMentale = AtelierCarteMentale;
window.ATELIER_CARTE_MENTALE = new AtelierCarteMentale();
window.atelCarteMentaleInit = () => window.ATELIER_CARTE_MENTALE.chargerListe();
if (typeof window.atelGardeEnregistrer === 'function') {
  window.atelGardeEnregistrer('Carte mentale', window.ATELIER_CARTE_MENTALE);
}
