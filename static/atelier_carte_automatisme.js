/**
 * static/atelier_carte_automatisme.js — v0.13.6.6
 *
 * Atelier d'édition des cartes d'automatisme (portée séquence).
 *
 * v0.13.6.6 — REFONTE OO : étend AtelierEditeur (qui étend
 * AtelierEditeur qui étend Atelier). Les méthodes communes (chargerListe,
 * ouvrirItem, sauvegarder, basculerValidation, basculerOnglet, compilerRendu,
 * etc.) sont héritées de la chaîne ; seules les spécificités de la carte
 * sont définies ici.
 *
 * Spécificités carte :
 *   - chargerListe() : 3 fetch parallèles (cartes + notions + méthodes
 *     de la séquence, pour les sélecteurs de lien).
 *   - rendreItem() : badge 'P' si paramétrée, ID format N11/S01/CA03,
 *     titre avec icône du type pédagogique, tag 'n NN' ou 'm MM' selon
 *     l'atome lié.
 *   - collecterFormulaire() / remplirFormulaire() : champs niveau,
 *     sequence, num, nom, type_pedago, type_tech, recto, verso,
 *     variables, lien_type, lien_id.
 *   - Cadre variables affiché uniquement si type_tech='parametree'.
 *   - Sélecteur de lien (notion ou méthode) avec liste depuis caches
 *     this.notions / this.methodes.
 *
 * Compat HTML : les onclick existants dans index.html appellent
 * window.atelCarte* (ex: atelCarteOuvrir, atelCarteCharger). En
 * v0.13.6.6, ces noms sont remplacés par ATELIER_CARTE.method() — voir
 * la mise à jour de templates/index.html.
 */

class AtelierCarte extends AtelierEditeur {

  // v0.13.6.6.1 — Champs statiques déclarés APRÈS la classe (assignations
  // post-déclaration) pour rester compatible ES2015. La syntaxe
  // `static FOO = {...}` à l'intérieur d'une classe est ES2022 et n'est
  // supportée que dans les navigateurs récents (Safari 14.1+, Firefox 75+,
  // Chrome 72+) — on évite la dépendance.

  constructor() {
    super({
      id:                 'carte',
      prefixe:            'atl-carte',
      titreToolbar:       "Atelier Carte d'automatisme",
      endpointBase:       '/api/cartes',
      // v0.14.4 — Rendu PDF via l'API unifiée /api/atomes/<type>/, comme
      // les 4 autres ateliers depuis v0.14.3. La carte rejoint donc le
      // schéma générique. Les anciens alias /api/cartes/<id>/rendu-pdf,
      // /info, /rendu-tex côté backend sont supprimés dans cette même
      // livraison v0.14.4 — ce client n'en a plus besoin.
      endpointRenduPdf:   '/api/atomes/carte',
      // v0.17.1 — Clé de libellé pour la modale LaTeX commune (voirLatex
      // unifié hérité d'AtelierEditeur récupère le .tex serveur et l'affiche).
      typeLatex:          'carte_automatisme',
      // v0.13.7.0e — Plus besoin de declarer methodeUpdate: la méthode
      // par défaut côté frontend est désormais PATCH pour tous les
      // ateliers (cohérent avec la sémantique des routes serveur).
      labelExistant:      'Modifier la carte',
      labelNouveau:       'Nouvelle carte',
      confirmSuppression: 'Supprimer cette carte ?',
      messageEnregistre:  'Carte enregistrée.',
      messageSupprime:    'Carte supprimée.',
      typeApi:            'carte',
      typeBadge:          'carte',
    });

    // v0.13.6.13 — Suppression des caches this.notions / this.methodes :
    // l'atelier carte n'a plus besoin de ces listes (plus de sélecteur
    // lien). La liaison carte → objectif(s) se gère depuis l'atelier
    // d'assemblage de séquence.

    // Filtre d'état d'édition (sidebar) : '' (tous) | 'en_cours' | 'valide'.
    this.filtreEtat = '';
  }

  // v0.13.6.16 — Plus de surcharge chargerListe : avec le contrat à 6 clés
  // côté backend (v0.13.6.15), /api/cartes retourne désormais une liste
  // directe (au lieu de l'enveloppe {cartes: [...]}). Le chargerListe
  // parent (AtelierEditeur.chargerListe) sait gérer ce format directement,
  // y compris les filtres niveau/sequence. Surcharger ici n'apporte plus
  // rien et avait introduit un bug (lecture cartesData.cartes → undefined
  // → liste vide).

  // ── Surcharge filtrerListe : super + filtre d'état local ────────────────
  //
  // v0.13.6.7.2 — Appelle super.filtrerListe pour bénéficier des filtres
  // niveau/séquence et état d'édition de la classe parente, puis applique
  // en plus le filtre d'état local propre à la carte (boutons « Tous /
  // En cours / Validé » de la sidebar). Sans super, le filtre niveau/séquence
  // ajouté en v0.13.6.7.1 dans AtelierEditeur serait court-circuité (pas
  // un bug visible aujourd'hui car /api/cartes filtre déjà serveur, mais
  // fragile pour le futur).

  filtrerListe(liste) {
    liste = super.filtrerListe(liste);
    // Filtre d'état local (sidebar, boutons « Tous / En cours / Validé »)
    if (this.filtreEtat) {
      liste = liste.filter(c => c.etat_code === this.filtreEtat);
    }
    return liste;
  }

  // ── Handler du filtre d'état (boutons de la sidebar) ────────────────────

  filtrerEtat(btn, etat) {
    const btns = btn.parentElement.querySelectorAll('.exo-etat');
    btns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    this.filtreEtat = etat;
    this.rendreSidebar();
  }

  // ── Surcharge _htmlListeVide ────────────────────────────────────────────

  _htmlListeVide() {
    return '<div class="atl-list-vide" style="padding:14px 10px;' +
           'color:var(--text-muted);font-size:12px;text-align:center">' +
           (this.liste.length === 0
             ? 'Aucune carte. Cliquez "+ Créer".'
             : 'Aucune carte avec ce filtre.') +
           '</div>';
  }

  // ── Surcharge rendreItem : carte (titre + tag lien) ─────────────────────

  rendreItem(c) {
    const actif = this.itemActif && this.itemActif.id === c.id;
    // v0.13.6.16 — Aligné sur le contrat à 6 clés. Avant : `c.niveau`,
    // `c.sequence`, `c.num` lus pour construire `CA01` localement, plus
    // `c.type_pedago` pour l'icône et `c.type_tech` pour le badge `P`
    // (carte paramétrée). Maintenant : `c.code` arrive préfixé du
    // backend, niveau/sequence viennent des filtres globaux. L'icône
    // type_pedago et le badge P sont retirés de la sidebar (décision
    // v0.13.6.15) — ces infos restent visibles dans le formulaire
    // d'édition.
    const idLib = [
      window.ATL_FILTRE_NIVEAU || '',
      window.ATL_FILTRE_SEQ || '',
      c.code || '',
    ].filter(Boolean).join('/');
    const titre = c.titre
      ? c.titre
      : { html: '(sans titre)', derive: true };

    // Tags `obj XX` depuis le format unifié `liens`.
    const placedTags = window.atelLiensEnTags
      ? window.atelLiensEnTags(c.liens || [])
      : [];

    const etatCode = c.etat_code || 'en_cours';

    return Atelier.rendreItemHtml({
      actif,
      selected: this.estSelectionne(c.id),
      dataId: c.id,
      onclick: `ATELIER_CARTE.gererClicItem(event, '${Atelier.escAttr(c.id)}')`,
      oncontextmenu: `ATELIER_CARTE.gererClicDroitItem(event, '${Atelier.escAttr(c.id)}')`,
      id: idLib,
      titre,
      placedTags,
      etatCode,
    });
  }

  // ── Formulaire : lecture du DOM ─────────────────────────────────────────

  collecterFormulaire() {
    // v0.13.6.13 — Plus de lien_type/lien_id collectés : la liaison
    // carte → objectif(s) se gère uniquement depuis l'atelier
    // d'assemblage de séquence. Le bloc « Objectifs liés » de l'atelier
    // carte est en lecture seule.
    //
    // v0.13.7.0e.1 — Plus de niveau/sequence collectés en modification :
    // ces champs sont du contexte de création (fournis par
    // _payloadCreation pour le POST), pas des propriétés éditables. Les
    // garder dans le body du PATCH déclenchait ChampInvalide côté
    // serveur (modifier_carte n'accepte pas ces champs). La carte n'a
    // pas d'UI pour les changer, donc aucune perte de fonctionnalité.
    return {
      // v0.13.6.14 — num n'est plus modifiable par l'utilisateur, donc
      // pas envoyé dans le PATCH ; il reste celui de la BdD.
      // v0.13.6.15 — La colonne BdD `nom` a été renommée en `titre`,
      // l'API accepte désormais `titre`. Plus de mapping clé HTML/clé API.
      titre:       this.$('titre').value,
      type_pedago: this.$('type_pedago').value,
      type_tech:   this.$('type_tech').value,
      recto:       this.$('recto').value,
      verso:       this.$('verso').value,
      variables:   this.$('variables').value,
    };
  }

  // ── Formulaire : écriture dans le DOM ───────────────────────────────────

  remplirFormulaire(c) {
    // v0.13.6.14.1 — La ligne « Numéro » a été retirée du formulaire :
    // redondante avec l'identifiant de la sidebar (CA01, CA02…). Plus
    // rien à peupler ici pour le numéro.
    // v0.13.6.15 — La colonne BdD `nom` a été renommée en `titre`. L'API
    // métier expose désormais `titre`, plus de mapping côté JS.
    this.$('titre').value       = c.titre       || '';
    this.$('type_pedago').value = c.type_pedago || 'definition';
    this.$('type_tech').value   = c.type_tech   || 'fixe';
    this.$('recto').value       = c.recto       || '';
    this.$('verso').value       = c.verso       || '';
    this.$('variables').value   = c.variables   || '';
    this._afficherCadreVariables();
    // v0.13.6.14 — Bouton « ⤵ reprendre titre objectif » injecté ici,
    // visible si la carte a exactement 1 lien obj avec un nom non vide
    // (mécanisme du chantier B, hérité d'AtelierEditeur).
    this._injecterBoutonReprendreTitre('atl-carte-titre');
  }

  /**
   * Affichage du cadre variables selon le type technique.
   * Pure : ne modifie pas l'état modifie.
   */
  _afficherCadreVariables() {
    const tech = this.$('type_tech').value;
    const cadre = this.$('cadre-variables');
    if (cadre) {
      cadre.style.display = (tech === 'parametree') ? 'block' : 'none';
    }
  }

  /** Handler explicite (change sur le select type_tech). */
  changerTypeTech() {
    this._afficherCadreVariables();
    this.marquerModifie();
  }

  /** Handler explicite : tout changement de formulaire marque dirty. */
  formChange() {
    if (!this.itemActif) return;
    this.marquerModifie();
  }

  // ── Payload de création (pattern POST-direct unifié, v0.13.6.16) ────────
  //
  // Avant v0.13.6.16 : surcharge complète de `nouvelItem` (POST direct,
  // puis ouvrirItem). Le pattern est maintenant standardisé dans la
  // classe parente AtelierEditeur, on ne fournit plus que les valeurs
  // par défaut spécifiques à la carte.

  _payloadCreation() {
    return {
      niveau:      window.ATL_FILTRE_NIVEAU || '',
      sequence:    window.ATL_FILTRE_SEQ || '',
      type_pedago: 'definition',
      type_tech:   'fixe',
      // v0.13.6.15 — `nom` renommé en `titre` côté BdD/API.
      titre:       '',
      recto:       '',
      verso:       '',
    };
  }
}

// ── Champs statiques de la classe AtelierCarte ───────────────────────────
// (v0.13.6.6.1 : sortis de la déclaration `class` pour rester compatibles
// ES2015. À l'intérieur de la classe ce serait `static FOO = {...}` qui
// est ES2022, donc plus restrictif côté support navigateur.)

AtelierCarte.TYPES_PEDAGO_ICONE = {
  definition:     '📖',
  propriete:      '📐',
  reconnaissance: '🔍',
  calcul:         '🧮',
  procedure:      '📋',
};
AtelierCarte.TYPES_PEDAGO_LIBELLE = {
  definition:     'Définition',
  propriete:      'Propriété',
  reconnaissance: 'Reconnaissance',
  calcul:         'Calcul',
  procedure:      'Procédure',
};

// ── Instance singleton et exposition globale ──────────────────────────────

const ATELIER_CARTE = new AtelierCarte();
window.ATELIER_CARTE = ATELIER_CARTE;

// v0.13.7.0c — Enregistrement dans le registre unifié pour la garde
// de sortie. atelier_garde.js gère la modale 3 boutons cohérente entre
// tous les ateliers (intra et inter).
if (typeof window.atelGardeEnregistrer === 'function') {
  window.atelGardeEnregistrer('Carte d\'automatisme', ATELIER_CARTE);
}

// ── Ponts rétrocompat ─────────────────────────────────────────────────────
//
// Certaines parties de app.js appellent encore l'ancien nom de fonction
// `atelCarteCharger` via une table de dispatch indexée par nom de panel
// (ATL_INITS dans app.js). Plutôt que toucher à app.js dans cette
// livraison (v0.13.6.6 ne migre que la carte), on conserve un alias
// global qui délègue à l'instance. À retirer en v0.14 avec le reste
// du nettoyage.
//
// L'ensemble des anciens noms est conservé temporairement pour qu'un
// code tiers (atelier d'assemblage qui pointerait vers la carte, par
// exemple) continue de fonctionner.
window.atelCarteCharger             = () => ATELIER_CARTE.chargerListe();
window.atelCarteNouvelle            = () => ATELIER_CARTE.nouvelItem();
window.atelCarteOuvrir              = (id) => ATELIER_CARTE.ouvrirItem(id);
window.atelCarteFermerEditeur       = () => ATELIER_CARTE.fermerEditeur();
window.atelCarteRendreSidebar       = () => ATELIER_CARTE.rendreSidebar();
window.atelCarteFiltrerEtat         = (btn, etat) => ATELIER_CARTE.filtrerEtat(btn, etat);
window.atelCarteFormChange          = () => ATELIER_CARTE.formChange();
window.atelCarteTypeTechChange      = () => ATELIER_CARTE.changerTypeTech();
window.atelCarteEnregistrer         = () => ATELIER_CARTE.sauvegarder();
window.atelCarteSupprimer           = () => ATELIER_CARTE.supprimer();
window.atelCarteBasculerValidation  = () => ATELIER_CARTE.basculerValidation();
window.atelCarteVoirLatex           = () => ATELIER_CARTE.voirLatex();
window.atelCarteCompiler            = () => ATELIER_CARTE.compilerRendu();
window.atelCarteToggleTexBrut       = () => ATELIER_CARTE.toggleTexBrut();
window.atelCarteScrollToLigneTex    = (ligne) => ATELIER_CARTE.scrollVersLigneTex(ligne);
window.atelCarteTab                 = (tab) => ATELIER_CARTE.basculerOnglet(tab);
