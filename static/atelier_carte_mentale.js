/**
 * static/atelier_carte_mentale.js — v0.56.1
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
 * Routes : /api/v2/livret-sequence/<niveau>/<séquence>/cartes-mentales
 *   GET (liste), POST (créer), /<n> GET / PATCH / DELETE,
 *   /<n>/rendu-pdf[/info] et /<n>/rendu-tex (?version=…&portee=partie|sequence).
 */

// ── Logique pure (testée par tests_js/cartes_mentales_atelier.test.js) ─────

const CarteMentalePur = {
  nbBranches(latex) {
    return ((latex || '').match(/\\seqCMBranche(?![A-Za-z])/g) || []).length;
  },

  /** Élément de liste (contrat d'AtelierEditeur) depuis une partie de l'API. */
  element(p) {
    const c = p.carte || null;
    return {
      id: String(p.numero),
      numero: p.numero,
      libelle: p.libelle || '',
      presente: !!c,
      titre: c ? (c.titre || '') : '',
      etat_code: c ? (c.etat_code || 'en_cours') : 'en_cours',
      branches: c ? CarteMentalePur.nbBranches(c.latex) : 0,
    };
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
    const url = () => {
      const niv = window.ATL_FILTRE_NIVEAU || '';
      const seq = window.ATL_FILTRE_SEQ || '';
      return (niv && seq && window.SeqnivPur)
        ? window.SeqnivPur.urlCartesMentales(niv, seq) : '/api/v2/livret-sequence/-/-/cartes-mentales';
    };
    Object.defineProperty(this.config, 'endpointBase', { get: url, configurable: true });
    Object.defineProperty(this.config, 'endpointRenduPdf', { get: url, configurable: true });
    this.filtreEtat = '';
    this.modifiable = true;          // faux si la séquence est validée
  }

  // ── Liste ───────────────────────────────────────────────────────────────

  async chargerListe() {
    const niv = window.ATL_FILTRE_NIVEAU || '';
    const seq = window.ATL_FILTRE_SEQ || '';
    this._messageListe = '';
    this.liste = [];
    if (!niv || !seq) {
      this._messageListe = 'Choisir une séquence précise : une carte mentale par partie de séquence.';
    } else {
      try {
        const resp = await fetch(this.config.endpointBase);
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
          this._messageListe = data.message || `Erreur chargement liste : HTTP ${resp.status}`;
        } else {
          this.liste = (data.parties || []).map(CarteMentalePur.element);
          this.modifiable = data.modifiable !== false;
        }
      } catch (e) {
        this.toast('Erreur réseau : ' + e.message, 'erreur');
      }
    }
    this._synchroniserItemActifAvecListe();
    this.rendreSidebar();
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
    const msg = this._messageListe
      || (this.liste.length === 0 ? 'Aucune partie dans cette séquence.' : 'Aucune partie avec ce filtre.');
    return '<div class="atl-list-vide" style="padding:14px 10px;color:var(--text-muted);'
         + `font-size:12px;text-align:center">${Atelier.escHtml(msg)}</div>`;
  }

  rendreItem(el) {
    const idLib = [window.ATL_FILTRE_NIVEAU || '', window.ATL_FILTRE_SEQ || '', 'P' + el.numero]
      .filter(Boolean).join('/');
    const titre = el.presente
      ? (el.titre || { html: '(sans titre)', derive: true })
      : { html: Atelier.escHtml(el.libelle || `Partie ${el.numero}`), derive: true };
    return Atelier.rendreItemHtml({
      actif: this.itemActif && this.itemActif.id === el.id,
      dataId: el.id,
      onclick: `ATELIER_CARTE_MENTALE.ouvrirItem('${Atelier.escAttr(el.id)}')`,
      id: idLib,
      titre,
      titleAttr: `Partie ${el.numero}${el.libelle ? ' — ' + el.libelle : ''}`,
      placedTags: el.presente ? [`${el.branches} br.`] : ['sans carte'],
      etatCode: el.etat_code,
    });
  }

  // ── Création : la carte de la partie ouverte (ou de la première sans carte) ─

  _payloadCreation() {
    return { numero: this._numeroACreer };
  }

  async nouvelItem() {
    if (!this.modifiable) {
      this.toast('Séquence validée : la repasser en cours pour créer une carte mentale.', 'erreur');
      return;
    }
    this._numeroACreer = CarteMentalePur.partieACreer(this.liste, this.itemActif);
    if (this._numeroACreer == null) {
      this.toast('Toutes les parties de la séquence ont déjà leur carte mentale.', 'erreur');
      return;
    }
    await super.nouvelItem();
  }

  _majBoutonCreer() {
    const b = document.getElementById('atl-cm-btn-creer');
    if (b) b.disabled = !this.modifiable;
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
      const partie = `Partie ${item.numero}` + (item.libelle ? ` — ${item.libelle}` : '');
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
      const resp = await fetch(`${this.config.endpointBase}/${encodeURIComponent(this.itemActif.id)}`, {
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
