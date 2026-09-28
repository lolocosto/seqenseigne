/**
 * static/atelier_fiche.js — v0.13.6.7.4
 *
 * Atelier d'édition des fiches de résumé (portée séquence).
 *
 * v0.13.6.7.4 — REFONTE OO : classe AtelierFiche qui étend AtelierEditeur.
 * Suit le même modèle que AtelierNotion (v0.13.6.7) et AtelierMethode
 * (v0.13.6.7.3), mais avec un nombre élevé de spécificités à préserver.
 *
 * Spécificités fiche (toutes conservées dans cette migration mécanique) :
 *
 *   1. ENDPOINT particulier : /api/fiches-resume (et non /api/fiches)
 *   2. Réponse GET liste : {fiches: [...]} (objet wrapper, pas tableau direct)
 *   3. GET unitaire existe : /api/fiches-resume/<id>
 *   4. POST création : v0.13.6.14 — objectif_id devient optionnel (chantier D).
 *      Si absent, niveau/sequence doivent être fournis. Le rattachement à
 *      un objectif se fait depuis l'atelier d'assemblage de séquence.
 *   5. SÉLECTEUR D'OBJECTIF : retiré au chantier D (v0.13.6.14).
 *   6. (Plus de cache objectifsCache : retiré au chantier D.)
 *   7. SECTIONS « ZONES DE TEXTE » : 1 textarea long par section (vs N items
 *      courts pour notion/méthode). Le modèle BDD est commun (atome_sections
 *      avec entite_type='fiche_resume') mais la UI est différente.
 *   8. CACHE TITRES DE ZONE (this.titresZoneCache) : titres paramétrables
 *      depuis /api/preferences/titre_zone_fiche. Si un titre est hors liste,
 *      il s'affiche tel quel marqué « (hors liste) ».
 *   9. BOUTON « INITIALISER DEPUIS » : permet d'aplatir le contenu d'une
 *      notion ou méthode liée au même objectif dans une zone de la fiche.
 *      Appel API : POST /api/fiches-resume/aplatir-atome. Sans objectif lié,
 *      le sélecteur reste vide (cf. _peuplerSelectInitialisationAuOuverture).
 *  10. v0.13.6.12 — Fallback titre supprimé. La migration BDD a matérialisé
 *      le libellé d'objectif dans f.titre pour les fiches existantes
 *      sans titre. À la création, le titre peut être repris du libellé
 *      via le bouton « reprendre titre objectif » (chantier B).
 *  11. IDENTIFIANT SIDEBAR : N11/S01/FR01 (basé sur num_fiche, préfixe FR).
 *  12. TYPE pour filtre d'état d'édition : 'fiche_resume' (et non 'fiche').
 *      typeApi='fiche_resume' dans la config, mais endpointBase reste l'URL.
 *  13. PLACED TAGS : format `obj 02` au lieu de `02` (legacy avant le
 *      chantier A d'homogénéisation).
 *  14. (Plus d'auto-init titre via sélecteur d'objectif : retiré au
 *      chantier D. Bouton « reprendre titre objectif » conservé.)
 *
 * Compat : les onclick HTML appellent ATELIER_FICHE.method().
 */

class AtelierFiche extends AtelierEditeur {

  constructor() {
    super({
      id:                 'fiche',
      prefixe:            'atl-fiche',
      titreToolbar:       'Atelier Fiche de résumé',
      endpointBase:       '/api/fiches-resume',
      // v0.14.3 — Rendu PDF via l'API unifiée /api/atomes/<type>/.
      // Note : le type côté API rendu reste 'fiche' (alias pédagogique
      // côté serveur), différent de typeApi='fiche_resume' utilisé
      // par les filtres d'état d'édition.
      endpointRenduPdf:   '/api/atomes/fiche',
      labelExistant:      'Modifier la fiche',
      labelNouveau:       'Nouvelle fiche',
      confirmSuppression: 'Supprimer cette fiche ?',
      messageEnregistre:  'Fiche enregistrée.',
      messageSupprime:    'Fiche supprimée.',
      // typeApi='fiche_resume' pour le filtre d'état d'édition global qui
      // est indexé par ce nom particulier (héritage v0.10.4). Différent de
      // l'id 'fiche' utilisé par tout le reste.
      typeApi:            'fiche_resume',
      typeBadge:          'fiche_resume',
    });

    // Caches spécifiques fiche. v0.13.6.14 — objectifsCache retiré
    // (chantier D, plus de sélecteur d'objectif).
    this.titresZoneCache = null;

    // Sections (zones de texte) en cours d'édition (modèle 1 textarea
    // long par section, mais structure BDD identique aux notion/méthode :
    // {titre, items: [contenu]}).
    this.sections = [];
  }

  // ── Setters miroir vers variables globales (compat ancien code) ─────────
  //
  // rendu_atome.js et atelier_etat_edition.js lisent directement les
  // variables globales ATL_FICHE_ACTIF et ATL_FICHES. v0.13.6.7.3.1 a
  // patché rendu_atome.js pour qu'il lise en priorité
  // window.ATELIER_<TYPE>.itemActif mais on maintient les miroirs pour
  // les autres lecteurs éventuels.

  set itemActif(val) {
    this._itemActif = val;
    window.ATL_FICHE_ACTIF = val;
  }
  get itemActif() {
    return this._itemActif;
  }

  set liste(val) {
    this._liste = val;
    window.ATL_FICHES = val;
  }
  get liste() {
    return this._liste || [];
  }

  // ── Sidebar : chargerListe hérité (plus de surcharge) ───────────────────
  //
  // v0.13.6.10 — Avant cette version, la route /api/fiches-resume
  // retournait `{fiches: [...]}` (enveloppé), ce qui nécessitait une
  // surcharge de chargerListe pour unwrap. Désormais elle retourne une
  // liste directe `[...]` (alignement avec les autres ateliers). On
  // utilise donc directement AtelierEditeur.chargerListe sans surcharge.

  // ── Sidebar : rendreItem avec spécificités fiche ────────────────────────

  rendreItem(f) {
    const actif = this.itemActif && this.itemActif.id === f.id;

    // v0.13.6.16 — Avant : 'FR' + f.num_fiche calculé localement,
    // f.niveau/f.sequence lus depuis la fiche. Maintenant : f.code
    // arrive déjà préfixé du backend (FR01, FR03…), niveau/sequence
    // viennent des filtres globaux.
    const idLib = [
      window.ATL_FILTRE_NIVEAU || '',
      window.ATL_FILTRE_SEQ || '',
      f.code || '',
    ].filter(Boolean).join('/');

    // v0.13.6.12 — Plus de fallback `f.objectif_nom` : la migration BDD
    // matérialise désormais le libellé d'objectif dans `f.titre` pour
    // toutes les fiches existantes sans titre. Si une fiche se retrouve
    // sans titre malgré tout (cas edge : objectif sans nom renseigné),
    // on affiche '(sans titre)' en italique comme pour les autres atomes.
    const titre = f.titre
      ? f.titre
      : { html: '(sans titre)', derive: true };

    // v0.13.6.10 — PlacedTags depuis le champ `liens` calculé côté serveur
    // par services/liaisons_atomes (alignement avec les autres ateliers).
    // Avant v0.13.6.10 la fiche n'avait pas de champ liens et on construisait
    // une chaîne synthétique côté JS. Le serveur fait maintenant le travail.
    const placedTags = window.atelLiensEnTags
      ? window.atelLiensEnTags(f.liens || [])
      : [];

    const etatCode = f.etat_code || 'en_cours';

    return Atelier.rendreItemHtml({
      actif,
      selected: this.estSelectionne(f.id),
      dataId: f.id,
      onclick: `ATELIER_FICHE.gererClicItem(event, '${Atelier.escAttr(f.id)}')`,
      oncontextmenu: `ATELIER_FICHE.gererClicDroitItem(event, '${Atelier.escAttr(f.id)}')`,
      id: idLib,
      titre,
      placedTags,
      etatCode,
    });
  }

  _htmlListeVide() {
    return '<div style="padding:14px 10px;font-size:12px;' +
           'color:var(--text-muted);text-align:center">Aucune fiche</div>';
  }

  // ── Ouverture d'un item : surcharge pour utiliser GET unitaire ──────────
  //
  // Contrairement à notion/méthode, l'API fiche a un GET unitaire qui
  // renvoie les sections complètes (la liste GET ne les charge pas pour
  // perf). On surcharge ouvrirItem pour TOUJOURS fetcher l'item unitaire
  // (le cache de la liste ne contient pas les sections).

  /**
   * v0.13.6.16 — Surcharge minimale d'ouvrirItem : appelle le parent
   * (qui fait le GET unitaire systématique depuis v0.13.6.16) puis
   * ajoute la spécificité fiche (chargement des titres de zone
   * configurables avant remplirFormulaire).
   *
   * Avant v0.13.6.16 la surcharge réimplémentait entièrement le GET +
   * la mise à jour de l'état + le rendu, dupliquant ainsi le code du
   * parent. Avec le GET unitaire systématique en place dans
   * AtelierEditeur, plus besoin de cette duplication.
   *
   * Plus de `this._texCharge = false` ici : selon la règle générale
   * « invalidation du cache PDF uniquement quand la BdD change »,
   * c'est sauvegarder() / supprimer() qui invalident désormais.
   */
  async ouvrirItem(id) {
    // Spécificité fiche : pré-charger les titres de zone configurables
    // avant remplirFormulaire (sans ça les sélecteurs de titre de zone
    // restent vides à la première ouverture).
    await this._chargerTitresZoneSiBesoin();
    // Délégation au parent pour le GET unitaire et la mise à jour de l'état.
    await super.ouvrirItem(id);
  }

  // ── Nouvel item : surcharge pour charger les caches puis afficher form ──

  async nouvelItem() {
    // Spécificité fiche : chargement titres de zone (idem ouvrirItem).
    await this._chargerTitresZoneSiBesoin();
    // Délégation au parent (POST-direct + ouvrirItem).
    await super.nouvelItem();
  }

  // ── Payload de création (pattern POST-direct unifié, v0.13.6.16) ────────

  _payloadCreation() {
    return {
      niveau:   window.ATL_FILTRE_NIVEAU || '',
      sequence: window.ATL_FILTRE_SEQ || '',
      titre:    '',
      // v0.13.6.14 — objectif_id absent : fiche orpheline à la création.
      // Le rattachement se fait depuis l'atelier d'assemblage de séquence.
    };
  }

  // ── Formulaire : lecture du DOM ─────────────────────────────────────────

  collecterFormulaire() {
    // v0.13.6.14 — Plus de sélecteur d'objectif dans cet atelier. Le
    // rattachement à un objectif se fait depuis l'atelier d'assemblage
    // de séquence.
    //
    // v0.13.7.0e.2 — Convention unifiée pour les 5 ateliers atomiques :
    // pas de niveau/sequence en modification. Le POST de création
    // (via _payloadCreation) les ajoute pour positionner la fiche dans
    // le bon contexte ; le PATCH de modification ne les touche pas.
    const titre = (this.$('titre') || {}).value.trim() || '';
    // Synchroniser this.sections avec le DOM
    this._capturerSectionsDepuisDom();
    return {
      titre,
      sections: this.sections,
    };
  }

  // ── Formulaire : écriture dans le DOM ───────────────────────────────────

  remplirFormulaire(f) {
    // Sections : copie profonde + au minimum 1 zone vide pour avoir un
    // textarea visible (UX historique : on ne montre pas une zone vide
    // « Aucune section. Cliquez pour ajouter. »).
    this.sections = (f.sections || []).map(s => ({
      titre: s.titre || '',
      items: [...(s.items || [])],
    }));
    if (this.sections.length === 0) {
      this.sections = [{ titre: '', items: [''] }];
    }

    // v0.13.6.14 — Plus de sélecteur d'objectif à peupler.

    // Titre
    const inputTitre = this.$('titre');
    if (inputTitre) inputTitre.value = f.titre || '';

    // Rendre les zones de texte
    this._renderSections();
    // v0.13.6.11 — Bouton « reprendre titre objectif » (chantier B)
    this._injecterBoutonReprendreTitre('atl-fiche-titre');
  }

  // ── Cache des titres de zone paramétrables ──────────────────────────────

  async _chargerTitresZoneSiBesoin() {
    if (this.titresZoneCache !== null) return;
    try {
      const resp = await fetch('/api/preferences/titre_zone_fiche');
      if (!resp.ok) {
        this.titresZoneCache = [];
        return;
      }
      const data = await resp.json();
      this.titresZoneCache = (data && data.items)
        ? data.items.map(i => i.valeur)
        : [];
    } catch (e) {
      this.titresZoneCache = [];
    }
  }

  /** Permet aux Préférences de signaler que la liste a changé. */
  invaliderCacheTitres() {
    this.titresZoneCache = null;
  }

  /**
   * Construit le HTML d'un sélecteur de titre de zone.
   *  - Si titre dans la liste paramétrable → <select> avec l'option correspondante
   *  - Si titre hors liste mais non vide → ajout d'une option « (hors liste) »
   *  - Option spéciale « + Personnalisé… » qui bascule en saisie libre
   */
  _renderTitreZoneSelect(idx, titreCourant) {
    const titre = (titreCourant || '').trim();
    const titres = this.titresZoneCache || [];
    const dansListe = titre && titres.includes(titre);
    const opts = ['<option value="">— choisir —</option>'];
    if (titre && !dansListe) {
      opts.push(
        `<option value="${Atelier.escAttr(titre)}" selected>` +
        `${Atelier.escHtml(titre)} (hors liste)</option>`,
      );
    }
    for (const t of titres) {
      const sel = (t === titre) ? ' selected' : '';
      opts.push(
        `<option value="${Atelier.escAttr(t)}"${sel}>` +
        `${Atelier.escHtml(t)}</option>`,
      );
    }
    opts.push('<option value="__personnalise__">+ Personnalisé…</option>');
    return `
      <select class="atl-fiche-section-titre"
              data-idx="${idx}"
              onchange="ATELIER_FICHE.sectionTitreChange(${idx}, this)"
              style="flex:1;font-size:13px;font-weight:500">
        ${opts.join('')}
      </select>`;
  }

  /** Handler : bascule du select titre vers une saisie libre. */
  sectionTitreChange(idx, sel) {
    if (sel.value !== '__personnalise__') {
      this.marquerModifie();
      return;
    }
    const val = prompt(
      'Titre de la zone (saisie libre).\n\n' +
      'Pour ajouter ce titre de manière permanente à la liste, ' +
      'rendez-vous dans Admin > Préférences.',
      '',
    );
    if (val === null) {
      sel.value = '';
      return;
    }
    const trim = val.trim();
    if (!trim) {
      sel.value = '';
      return;
    }
    if ((this.titresZoneCache || []).includes(trim)) {
      sel.value = trim;
      this.marquerModifie();
      return;
    }
    // Reconstruire le wrapper du titre avec la valeur historique
    const cont = this.$('sections');
    if (!cont) return;
    const bloc = cont.querySelectorAll('.atl-fiche-section')[idx];
    if (!bloc) return;
    const wrapper = bloc.querySelector('.atl-fiche-section-titre-wrapper');
    if (!wrapper) return;
    wrapper.innerHTML = this._renderTitreZoneSelect(idx, trim);
    this.marquerModifie();
  }

  // ── Sections (zones de texte) ───────────────────────────────────────────

  _capturerSectionsDepuisDom() {
    const cont = this.$('sections');
    if (!cont) return;
    const blocs = cont.querySelectorAll('.atl-fiche-section');
    const out = [];
    blocs.forEach((bloc) => {
      const inputTitre = bloc.querySelector('.atl-fiche-section-titre');
      const textarea = bloc.querySelector('.atl-fiche-section-corps');
      out.push({
        titre: inputTitre ? (inputTitre.value || '') : '',
        items: [textarea ? (textarea.value || '') : ''],
      });
    });
    this.sections = out;
  }

  _renderSections() {
    const cont = this.$('sections');
    if (!cont) return;
    if (this.sections.length === 0) {
      this.sections = [{ titre: '', items: [''] }];
    }
    // v0.13.6.16 — Le sélecteur « Initialiser depuis » a été retiré
    // (il s'appuyait sur /api/methodes et /api/notions sans filtre,
    // plus supportés depuis l'harmonisation v0.13.6.15). À réintroduire
    // plus tard avec un design propre.
    cont.innerHTML = this.sections.map((sec, i) => {
      const corps = (sec.items && sec.items[0]) || '';
      // v0.13.7.6 — Bouton ✎ Éditer manuel à gauche du « × » sur la ligne
      // du haut, pour cohérence avec les autres ateliers et pour éviter la
      // superposition avec le bouton de suppression que produisait le
      // scanner global. Le textarea porte data-ed-latex-attache="1" pour
      // que le scanner ne pose pas un deuxième bouton flottant.
      return `
        <div class="atl-fiche-section" data-idx="${i}"
             style="border:1px solid var(--border);border-radius:6px;
                    padding:10px;margin-bottom:10px;background:var(--bg-card)">
          <div style="display:flex;gap:8px;align-items:center;margin-bottom:6px">
            <span class="atl-fiche-section-titre-wrapper" style="flex:1">
              ${this._renderTitreZoneSelect(i, sec.titre || '')}
            </span>
            <button class="btn-ed-latex-manuel"
                    onclick="EditeurLatex.ouvrir(this.closest('.atl-fiche-section').querySelector('textarea'))"
                    title="Ouvrir l'éditeur LaTeX">✎ Éditer</button>
            <button class="btn-sm" onclick="ATELIER_FICHE.supprimerSection(${i})"
                    title="Supprimer cette zone"
                    style="color:var(--danger)">×</button>
          </div>
          <textarea class="atl-fiche-section-corps latex-textarea"
                    rows="6"
                    data-contexte-latex="fiche-section"
                    data-ed-latex-attache="1"
                    style="width:100%;font-family:monospace;font-size:12px;
                           resize:vertical"
                    placeholder="Contenu LaTeX de la zone"
          >${Atelier.escHtml(corps)}</textarea>
        </div>`;
    }).join('');
    // v0.13.6.16 — Plus de querySelectorAll('.atl-fiche-section-init')
    // : ce sélecteur a été retiré.
    // v0.13.7.6 — Plus besoin de window.EditeurLatex.scan(cont) : les
    // textareas portent data-ed-latex-attache="1" et un bouton ✎ Éditer
    // manuel est posé sur chaque ligne d'actions. L'appel à scan() est
    // conservé pour ouvrir une éventuelle autre textarea LaTeX libre
    // ajoutée plus tard sans data-ed-latex-attache.
    if (window.EditeurLatex) window.EditeurLatex.scan(cont);
  }

  ajouterSection() {
    this._capturerSectionsDepuisDom();
    this.sections.push({ titre: '', items: [''] });
    this._renderSections();
    this.marquerModifie();
  }

  supprimerSection(idx) {
    this._capturerSectionsDepuisDom();
    if (this.sections.length <= 1) {
      this.sections = [{ titre: '', items: [''] }];
    } else {
      this.sections.splice(idx, 1);
    }
    this._renderSections();
    this.marquerModifie();
  }

  // ── « Initialiser depuis » retiré en v0.13.6.16 ────────────────────────
  // Avant : sélecteur dans chaque zone qui permettait de copier le
  // contenu d'une notion/méthode liée au même objectif dans la zone
  // de la fiche. S'appuyait sur `/api/methodes` et `/api/notions` sans
  // filtre, plus supportés depuis l'harmonisation v0.13.6.15 (le contrat
  // de liste exige niveau+sequence comme paramètres obligatoires).
  // À réintroduire plus tard avec un design propre (probablement via un
  // GET dédié `/api/v2/fiches/<id>/atomes-aplatissables` qui renvoie
  // les atomes éligibles depuis l'objectif lié).

  // v0.17.2 — Génération LaTeX CLIENT retirée. Le LaTeX vient du serveur
  // (route /rendu-tex), affiché par AtelierEditeur.voirLatex() dans la modale
  // commune. Une seule source de vérité (serveur).

  // ── Onglet Rendu PDF ────────────────────────────────────────────────────
  //
  // v0.14.3 — Plus de surcharge de basculerOnglet : le rendu PDF est
  // maintenant entièrement géré par AtelierEditeur (HTML statique
  // #atl-fiche-* + verifierCacheEtAfficher + compilerRendu via
  // endpointRenduPdf='/api/atomes/fiche').

  // ── Handler générique formulaire ────────────────────────────────────────

  formChange() {
    if (!this.itemActif && this.itemActif !== null) return;
    this.marquerModifie();
  }
}

// ── Instance singleton et exposition globale ──────────────────────────────

const ATELIER_FICHE = new AtelierFiche();
window.ATELIER_FICHE = ATELIER_FICHE;

// v0.13.7.0c — Enregistrement dans le registre unifié.
if (typeof window.atelGardeEnregistrer === 'function') {
  window.atelGardeEnregistrer('Fiche de résumé', ATELIER_FICHE);
}

// ── Ponts rétrocompat ─────────────────────────────────────────────────────
//
// Les anciens noms restent dispos. À nettoyer en v0.14.

window.atelFichesCharger              = () => ATELIER_FICHE.chargerListe();
window.atelFicheRenderListe           = () => ATELIER_FICHE.rendreSidebar();
window.atelFicheNouveau               = () => ATELIER_FICHE.nouvelItem();
window.atelFicheCharger               = (id) => ATELIER_FICHE.ouvrirItem(id);
window.atelFicheSauvegarder           = () => ATELIER_FICHE.sauvegarder();
window.atelFicheSupprimer             = () => ATELIER_FICHE.supprimer();
window.atelFicheTab                   = (tab) => ATELIER_FICHE.basculerOnglet(tab);
window.atelFicheAjouterSection        = () => ATELIER_FICHE.ajouterSection();
window.atelFicheSupprimerSection      = (idx) => ATELIER_FICHE.supprimerSection(idx);
window.atelFicheVoirLatex             = () => ATELIER_FICHE.voirLatex();
window.atelFicheBasculerValidationCb  = () => ATELIER_FICHE.basculerValidation();
window.atelFicheSectionTitreChange    = (idx, sel) => ATELIER_FICHE.sectionTitreChange(idx, sel);
// v0.13.6.16 — Alias `atelFicheInitialiserDepuisSelect` retiré : la
// feature « Initialiser depuis » (méthode initialiserDepuisSelect) a
// été supprimée. Cf. commentaire dans la section « Initialiser depuis »
// (à réintroduire plus tard avec un design propre).
window.atelFicheInit                  = () => ATELIER_FICHE.chargerListe();
window.atelFicheInvaliderCacheTitres  = () => ATELIER_FICHE.invaliderCacheTitres();
