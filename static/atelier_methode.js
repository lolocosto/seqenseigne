/**
 * static/atelier_methode.js — v0.13.6.7.3
 *
 * Atelier d'édition des méthodes (portée séquence).
 *
 * v0.13.6.7.3 — REFONTE OO : classe AtelierMethode qui étend AtelierEditeur.
 * Suit le même modèle que AtelierNotion (v0.13.6.7).
 *
 * Spécificités méthode :
 *   - Sidebar plate : ID format N11/S01/M01 (utilise num_methode).
 *   - Formulaire : titre + corps + sections (modèle universel à 2 niveaux,
 *     liste de {titre, items[]} stockée dans this.sections).
 *   - Affichage LaTeX : AtelierEditeur.voirLatex (serveur + modale commune, v0.17.2)
 *     dans la zone `atl-methode-latex` via le bouton « LaTeX généré ».
 *   - Mode Rendu PDF : géré par `rendu_atome.js` qui lit ATL_METHODE_ACTIF
 *     (variable globale historique) → on maintient un miroir via setter.
 *
 * Compat : les onclick HTML appellent ATELIER_METHODE.method().
 * Les anciens noms (atelMethodeXxx) sont conservés comme alias globaux
 * pour ne pas casser les références internes encore présentes
 * (rendu_atome.js, atelier_etat_edition.js, code mort dans app.js).
 */

class AtelierMethode extends AtelierEditeur {

  constructor() {
    super({
      id:                 'methode',
      prefixe:            'atl-methode',
      titreToolbar:       'Atelier Méthode',
      endpointBase:       '/api/methodes',
      // v0.14.3 — Rendu PDF via l'API unifiée /api/atomes/<type>/.
      endpointRenduPdf:   '/api/atomes/methode',
      labelExistant:      'Modifier la méthode',
      labelNouveau:       'Nouvelle méthode',
      confirmSuppression: 'Supprimer cette méthode ?',
      messageEnregistre:  'Méthode enregistrée.',
      messageSupprime:    'Méthode supprimée.',
      typeApi:            'methode',
      typeBadge:          'methode',
    });

    // Sections de la méthode en cours d'édition (modèle universel
    // à 2 niveaux : liste de {titre, items[]}).
    this.sections = [];
  }

  // ── Setters miroir vers variables globales (compat ancien code) ─────────
  //
  // rendu_atome.js et atelier_etat_edition.js lisent directement les
  // variables globales ATL_METHODE_ACTIF et ATL_METHODES pour récupérer
  // l'item courant et la liste cache. Tant qu'on n'a pas migré ces
  // modules en OO, on maintient des miroirs pour qu'ils continuent
  // de fonctionner.

  set itemActif(val) {
    this._itemActif = val;
    window.ATL_METHODE_ACTIF = val;
  }
  get itemActif() {
    return this._itemActif;
  }

  set liste(val) {
    this._liste = val;
    window.ATL_METHODES = val;
  }
  get liste() {
    return this._liste || [];
  }

  // ── Sidebar : plate, ID format N11/S01/M01 ──────────────────────────────

  rendreItem(m) {
    const actif = this.itemActif && this.itemActif.id === m.id;
    // Identification : N11/S01/M01 (M = méthode). Cf. notion qui utilise N01
    // v0.13.6.16 — Avant : préfixe 'M' + m.num_methode calculé localement,
    // m.niveau/m.sequence lus depuis la méthode. Maintenant : m.code est
    // déjà préfixé par le backend, niveau/sequence viennent des filtres
    // globaux.
    const idMethode = [
      window.ATL_FILTRE_NIVEAU || '',
      window.ATL_FILTRE_SEQ || '',
      m.code || '',
    ].filter(Boolean).join('/');
    const titre = m.titre
      ? m.titre
      : { html: '(sans titre)', derive: true };
    const placedTags = window.atelLiensEnTags
      ? window.atelLiensEnTags(m.liens || [])
      : [];
    const etatCode = m.etat_code || 'en_cours';

    return Atelier.rendreItemHtml({
      actif,
      selected: this.estSelectionne(m.id),
      dataId: m.id,
      onclick: `ATELIER_METHODE.gererClicItem(event, '${Atelier.escAttr(m.id)}')`,
      oncontextmenu: `ATELIER_METHODE.gererClicDroitItem(event, '${Atelier.escAttr(m.id)}')`,
      id: idMethode,
      titre,
      placedTags,
      etatCode,
    });
  }

  _htmlListeVide() {
    return '<div style="padding:14px;font-size:12px;color:var(--text-muted);' +
           'text-align:center">Aucune méthode</div>';
  }

  // ── Filtre (sidebar) ────────────────────────────────────────────────────
  //
  // Pas de surcharge nécessaire : AtelierEditeur.filtrerListe() applique
  // déjà (1) le filtre niveau/séquence pour les API non filtrantes comme
  // /api/methodes, puis (2) le filtre d'état d'édition. La leçon
  // v0.13.6.7.2 (notion) s'applique aussi ici : on ne surcharge pas.

  // v0.13.6.16 — itemVide() retiré : pattern POST-direct unifié dans
  // AtelierEditeur.nouvelItem. Le payload minimal par défaut (niveau +
  // sequence) suffit ; creer_methode accepte tout en optionnel depuis
  // v0.13.6.16.

  // ── Formulaire : lecture du DOM ─────────────────────────────────────────

  collecterFormulaire() {
    // v0.13.6.16 — Titre relâché (modèle en cours). Validation reportée
    // au hook côté backend.
    const titre = (this.$('titre') || {}).value || '';

    // Synchroniser this.sections avec ce qui est dans le DOM
    this._lireSectionsDOM();
    const sectionsNettoyees = this.sections
      .map(s => ({
        titre: (s.titre || '').trim(),
        items: (s.items || []).map(it => it || '').filter(it => it.trim()),
      }))
      .filter(s => s.titre || s.items.length);

    // v0.13.7.0e.2 — Convention unifiée : pas de niveau/sequence en
    // modification (cf. atelier_notion.js).
    return {
      titre: titre.trim(),
      corps: (this.$('corps') || {}).value || '',
      sections: sectionsNettoyees,
    };
  }

  // ── Formulaire : écriture dans le DOM ───────────────────────────────────

  remplirFormulaire(n) {
    if (this.$('titre')) this.$('titre').value = n.titre || '';
    if (this.$('corps')) this.$('corps').value = n.corps || '';
    this.sections = (n.sections || []).map(s => ({
      titre: s.titre || '',
      items: [...(s.items || [])],
    }));
    this.rendreSections();
    // v0.13.6.11 — Bouton « reprendre titre objectif » (chantier B)
    this._injecterBoutonReprendreTitre('atl-methode-titre');
  }

  // ── Sections (modèle universel à 2 niveaux) ─────────────────────────────

  /** Lit les sections depuis le DOM (à appeler avant tout changement
   * structurel pour ne pas perdre la saisie en cours). */
  _lireSectionsDOM() {
    const blocs = document.querySelectorAll(
      '#atl-methode-sections-zone .atl-section-bloc',
    );
    this.sections = Array.from(blocs).map(bloc => ({
      titre: (bloc.querySelector('.atl-section-titre-input') || {}).value || '',
      items: Array.from(bloc.querySelectorAll('.atl-section-item-row textarea'))
                  .map(t => t.value),
    }));
  }

  /** Re-rend toutes les sections depuis this.sections. */
  rendreSections() {
    const zone = document.getElementById('atl-methode-sections-zone');
    if (!zone) return;
    if (!this.sections.length) {
      zone.innerHTML = '<div class="atl-section-item-vide">' +
                       'Aucune section. Cliquez sur « + Ajouter une section ».' +
                       '</div>';
      return;
    }
    const html = this.sections.map((sec, iSec) => {
      const peutMonter   = iSec > 0;
      const peutDescendre = iSec < this.sections.length - 1;
      const itemsHtml = (sec.items || []).map((item, iIt) => {
        const peutMonterIt = iIt > 0;
        const peutDescendreIt = iIt < sec.items.length - 1;
        const safe = (item || '')
          .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        // v0.13.7.6 — Bouton ✎ Éditer manuel inline dans les actions, et
        // marqueur data-ed-latex-attache="1" pour skip scanner global
        // (sinon double bouton, le flottant se superposait avec les flèches).
        return `
          <div class="atl-section-item-row">
            <textarea class="latex-textarea" rows="2"
                      data-contexte-latex="methode-corps"
                      data-ed-latex-attache="1">${safe}</textarea>
            <div class="atl-section-item-actions">
              <button class="btn-ed-latex-manuel btn-ed-latex-manuel--compact"
                      onclick="EditeurLatex.ouvrir(this.closest('.atl-section-item-row').querySelector('textarea'))"
                      title="Ouvrir l'éditeur LaTeX">✎</button>
              <button onclick="ATELIER_METHODE.deplacerItem(${iSec},${iIt},-1)" ${peutMonterIt?'':'disabled'} title="Monter">↑</button>
              <button onclick="ATELIER_METHODE.deplacerItem(${iSec},${iIt},1)"  ${peutDescendreIt?'':'disabled'} title="Descendre">↓</button>
              <button class="btn-del-item" onclick="ATELIER_METHODE.supprimerItem(${iSec},${iIt})" title="Supprimer">×</button>
            </div>
          </div>`;
      }).join('');
      const titreSafe = (sec.titre || '')
        .replace(/&/g, '&amp;').replace(/"/g, '&quot;');
      return `
        <div class="atl-section-bloc" data-section-idx="${iSec}">
          <div class="atl-section-tete">
            <input type="text" class="atl-section-titre-input"
                   value="${titreSafe}"
                   list="atl-vocab-sections"
                   placeholder="Titre de la section"
                   onchange="ATELIER_METHODE.majTitreSection(${iSec}, this.value)">
            <div class="atl-section-actions">
              <button onclick="ATELIER_METHODE.deplacerSection(${iSec}, -1)" ${peutMonter?'':'disabled'} title="Monter la section">↑</button>
              <button onclick="ATELIER_METHODE.deplacerSection(${iSec}, 1)"  ${peutDescendre?'':'disabled'} title="Descendre la section">↓</button>
              <button class="btn-suppr-sec" onclick="ATELIER_METHODE.supprimerSection(${iSec})" title="Supprimer la section">×</button>
            </div>
          </div>
          <div class="atl-section-items">${itemsHtml || '<div class="atl-section-item-vide">Aucun item.</div>'}</div>
          <button class="btn-sm" style="font-size:11px" onclick="ATELIER_METHODE.ajouterItem(${iSec})">+ Ajouter un item</button>
        </div>`;
    }).join('');
    zone.innerHTML = html;
    if (typeof window.atelierAutosizeTous === 'function') {
      window.atelierAutosizeTous(zone);
    }
    if (typeof window.atelierFixerHauteurLatexTous === 'function'
        && window._ATL_TEXTAREA_LIGNES) {
      const lignesItem = Math.max(3, Math.round(window._ATL_TEXTAREA_LIGNES / 4));
      window.atelierFixerHauteurLatexTous(zone, lignesItem);
    }
    // v0.13.7.1 — Équiper les textareas générées d'un bouton « ✎ Éditer ».
    if (window.EditeurLatex) window.EditeurLatex.scan(zone);
  }

  ajouterSection() {
    this._lireSectionsDOM();
    this.sections.push({ titre: 'Exemples', items: [''] });
    this.rendreSections();
    this.marquerModifie();
  }

  supprimerSection(iSec) {
    this._lireSectionsDOM();
    if (iSec < 0 || iSec >= this.sections.length) return;
    if (!confirm(
      `Supprimer la section « ${this.sections[iSec].titre} » et tous ses items ?`,
    )) return;
    this.sections.splice(iSec, 1);
    this.rendreSections();
    this.marquerModifie();
  }

  deplacerSection(iSec, delta) {
    this._lireSectionsDOM();
    const j = iSec + delta;
    if (j < 0 || j >= this.sections.length) return;
    const tmp = this.sections[iSec];
    this.sections[iSec] = this.sections[j];
    this.sections[j] = tmp;
    this.rendreSections();
    this.marquerModifie();
  }

  majTitreSection(iSec, val) {
    if (iSec < 0 || iSec >= this.sections.length) return;
    this.sections[iSec].titre = val;
    this.marquerModifie();
  }

  ajouterItem(iSec) {
    this._lireSectionsDOM();
    if (iSec < 0 || iSec >= this.sections.length) return;
    this.sections[iSec].items.push('');
    this.rendreSections();
    this.marquerModifie();
  }

  supprimerItem(iSec, iIt) {
    this._lireSectionsDOM();
    if (iSec < 0 || iSec >= this.sections.length) return;
    const items = this.sections[iSec].items;
    if (iIt < 0 || iIt >= items.length) return;
    items.splice(iIt, 1);
    this.rendreSections();
    this.marquerModifie();
  }

  deplacerItem(iSec, iIt, delta) {
    this._lireSectionsDOM();
    if (iSec < 0 || iSec >= this.sections.length) return;
    const items = this.sections[iSec].items;
    const j = iIt + delta;
    if (j < 0 || j >= items.length) return;
    const tmp = items[iIt]; items[iIt] = items[j]; items[j] = tmp;
    this.rendreSections();
    this.marquerModifie();
  }

  // ── Génération LaTeX côté client (bouton « LaTeX généré ») ──────────────

  // v0.17.2 — Génération LaTeX CLIENT retirée. Le LaTeX vient du serveur
  // (route /rendu-tex), affiché par AtelierEditeur.voirLatex() dans la modale
  // commune. Une seule source de vérité (serveur).

  // ── Onglet Rendu PDF ────────────────────────────────────────────────────
  //
  // v0.14.3 — Plus de surcharge de basculerOnglet : le rendu PDF est
  // maintenant entièrement géré par AtelierEditeur (HTML statique
  // #atl-methode-* + verifierCacheEtAfficher + compilerRendu via
  // endpointRenduPdf='/api/atomes/methode').

  // ── Handler générique formulaire ────────────────────────────────────────

  formChange() {
    if (!this.itemActif) return;
    this.marquerModifie();
  }
}

// ── Instance singleton et exposition globale ──────────────────────────────

const ATELIER_METHODE = new AtelierMethode();
window.ATELIER_METHODE = ATELIER_METHODE;

// v0.13.7.0c — Enregistrement dans le registre unifié.
if (typeof window.atelGardeEnregistrer === 'function') {
  window.atelGardeEnregistrer('Méthode', ATELIER_METHODE);
}

// ── Ponts rétrocompat ─────────────────────────────────────────────────────
//
// Les anciens noms restent dispos pour les références internes
// (atelMethodeBasculerValidationCb dans app.js, rendu_atome.js qui lit
// ATL_METHODE_ACTIF, etc.). À nettoyer en v0.14.
//
// v0.13.7.0c — ATL_ATOME_CONFIG (legacy atelier_atome_generique.js) a disparu.

window.atelChargerMethodes          = () => ATELIER_METHODE.chargerListe();
window.atelRenderMethodeListe       = () => ATELIER_METHODE.rendreSidebar();
window.atelMethodeNouveau           = () => ATELIER_METHODE.nouvelItem();
window.atelMethodeCharger           = (id) => ATELIER_METHODE.ouvrirItem(id);
window.atelMethodeSauvegarder       = () => ATELIER_METHODE.sauvegarder();
window.atelMethodeSupprimer         = () => ATELIER_METHODE.supprimer();
window.atelMethodeRemplir           = (n) => ATELIER_METHODE.remplirFormulaire(n);
window.atelMethodeRenderSections    = () => ATELIER_METHODE.rendreSections();
window.atelMethodeAjouterSection    = () => ATELIER_METHODE.ajouterSection();
window.atelMethodeSupprimerSection  = (iSec) => ATELIER_METHODE.supprimerSection(iSec);
window.atelMethodeDeplacerSection   = (iSec, delta) => ATELIER_METHODE.deplacerSection(iSec, delta);
window.atelMethodeMajTitre          = (iSec, val) => ATELIER_METHODE.majTitreSection(iSec, val);
window.atelMethodeAjouterItem       = (iSec) => ATELIER_METHODE.ajouterItem(iSec);
window.atelMethodeSupprimerItem     = (iSec, iIt) => ATELIER_METHODE.supprimerItem(iSec, iIt);
window.atelMethodeDeplacerItem      = (iSec, iIt, delta) => ATELIER_METHODE.deplacerItem(iSec, iIt, delta);
window.atelMethodeTab               = (tab) => ATELIER_METHODE.basculerOnglet(tab);
window.atelMethodeVoirLatex         = () => ATELIER_METHODE.voirLatex();
window.atelMethodeBasculerValidationCb = () => ATELIER_METHODE.basculerValidation();
window.atelMethodeAfficherEditeur   = (existant) => ATELIER_METHODE.afficherEditeur(existant);
// La fonction `_atelMethodeLireDOM` était parfois appelée par d'autres
// modules ; on la conserve comme pont vers la méthode interne.
window._atelMethodeLireDOM          = () => ATELIER_METHODE._lireSectionsDOM();
