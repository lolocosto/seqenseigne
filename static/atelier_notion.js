/**
 * static/atelier_notion.js — v0.13.6.7
 *
 * Atelier d'édition des notions (portée séquence).
 *
 * v0.13.6.7 — REFONTE OO : classe AtelierNotion qui étend AtelierEditeur.
 * Suit le même modèle que AtelierCarte (pilote v0.13.6.6).
 *
 * Spécificités notion :
 *   - Sidebar plate : ID format N11/S01/N01 (utilise num_connaissance).
 *   - Formulaire : titre + corps + sections (modèle universel à 2 niveaux,
 *     liste de {titre, items[]} stockée dans this.sections).
 *   - Affichage LaTeX : AtelierEditeur.voirLatex (serveur + modale commune, v0.17.2)
 *     dans la zone `atl-notion-latex` via le bouton « LaTeX généré ».
 *   - Mode Rendu PDF : géré par `rendu_atome.js` qui lit ATL_NOTION_ACTIF
 *     (variable globale historique) → on maintient un miroir via setter.
 *
 * Compat : les onclick HTML appellent ATELIER_NOTION.method().
 * Les anciens noms (atelNotionXxx) sont conservés comme alias globaux
 * pour ne pas casser les références internes encore présentes.
 */

class AtelierNotion extends AtelierEditeur {

  constructor() {
    super({
      id:                 'notion',
      prefixe:            'atl-notion',
      titreToolbar:       'Atelier Notion',
      endpointBase:       '/api/notions',
      // v0.14.3 — Rendu PDF via l'API unifiée /api/atomes/<type>/.
      endpointRenduPdf:   '/api/atomes/notion',
      labelExistant:      'Modifier la notion',
      labelNouveau:       'Nouvelle notion',
      confirmSuppression: 'Supprimer cette notion ?',
      messageEnregistre:  'Notion enregistrée.',
      messageSupprime:    'Notion supprimée.',
      typeApi:            'notion',
      typeBadge:          'notion',
    });

    // Sections de la notion en cours d'édition (modèle universel
    // à 2 niveaux : liste de {titre, items[]}).
    this.sections = [];
  }

  // ── Setters miroir vers variables globales (compat ancien code) ─────────
  //
  // rendu_atome.js et atelier_etat_edition.js lisent directement les
  // variables globales ATL_NOTION_ACTIF et ATL_NOTIONS pour récupérer
  // l'item courant et la liste cache. Tant qu'on n'a pas migré ces
  // modules en OO, on maintient des miroirs pour qu'ils continuent
  // de fonctionner.

  set itemActif(val) {
    this._itemActif = val;
    window.ATL_NOTION_ACTIF = val;
  }
  get itemActif() {
    return this._itemActif;
  }

  set liste(val) {
    this._liste = val;
    window.ATL_NOTIONS = val;
  }
  get liste() {
    return this._liste || [];
  }

  // ── Sidebar : plate, ID format N11/S01/N01 ──────────────────────────────

  rendreItem(n) {
    const actif = this.itemActif && this.itemActif.id === n.id;
    // v0.13.6.16 — Avant : préfixe 'N' + n.num_connaissance calculé localement,
    // n.niveau/n.sequence lus depuis la notion. Maintenant : n.code est
    // déjà préfixé par le backend (contrat à 6 clés), et niveau/sequence
    // viennent des filtres globaux (cohérent puisque la liste est
    // déjà filtrée sur ces valeurs).
    const idNotion = [
      window.ATL_FILTRE_NIVEAU || '',
      window.ATL_FILTRE_SEQ || '',
      n.code || '',
    ].filter(Boolean).join('/');
    const titre = n.titre
      ? n.titre
      : { html: '(sans titre)', derive: true };
    const placedTags = window.atelLiensEnTags
      ? window.atelLiensEnTags(n.liens || [])
      : [];
    const etatCode = n.etat_code || 'en_cours';

    return Atelier.rendreItemHtml({
      actif,
      selected: this.estSelectionne(n.id),
      dataId: n.id,
      onclick: `ATELIER_NOTION.gererClicItem(event, '${Atelier.escAttr(n.id)}')`,
      oncontextmenu: `ATELIER_NOTION.gererClicDroitItem(event, '${Atelier.escAttr(n.id)}')`,
      id: idNotion,
      titre,
      placedTags,
      etatCode,
    });
  }

  _htmlListeVide() {
    return '<div style="padding:14px;font-size:12px;color:var(--text-muted);' +
           'text-align:center">Aucune notion</div>';
  }

  // ── Filtre (sidebar) ────────────────────────────────────────────────────
  //
  // v0.13.6.7.2 — Pas de surcharge nécessaire : AtelierEditeur.filtrerListe()
  // applique déjà (1) le filtre niveau/séquence pour les API non filtrantes
  // comme /api/notions, puis (2) le filtre d'état d'édition. La surcharge
  // précédente n'appliquait que le filtre d'état → écrasait le fix
  // v0.13.6.7.1 et la sidebar montrait toutes les notions de tous les
  // niveaux.

  // v0.13.6.16 — itemVide() retiré : avec le pattern POST-direct unifié
  // (v0.13.6.16, AtelierEditeur.nouvelItem), `nouvelItem` ne pré-remplit
  // plus le formulaire avec un objet vide — il fait directement un POST
  // avec `_payloadCreation()` puis `ouvrirItem` sur le résultat. Le
  // payload minimal par défaut (niveau + sequence depuis les filtres
  // globaux) suffit pour les notions : creer_notion accepte un payload
  // sans titre depuis v0.13.6.16.

  // ── Formulaire : lecture du DOM ─────────────────────────────────────────

  collecterFormulaire() {
    // v0.13.6.16 — Le titre n'est plus obligatoire à la saisie
    // (modèle « en cours » : un atome peut être incomplet). La règle
    // « titre non vide » est appliquée par le hook de validation
    // pédagogique côté backend, au passage en état `valide`.
    const titre = (this.$('titre') || {}).value || '';

    // Synchroniser this.sections avec ce qui est dans le DOM
    this._lireSectionsDOM();
    const sectionsNettoyees = this.sections
      .map(s => ({
        titre: (s.titre || '').trim(),
        items: (s.items || []).map(it => it || '').filter(it => it.trim()),
      }))
      .filter(s => s.titre || s.items.length);

    // v0.13.7.0e.2 — Convention unifiée pour les 5 ateliers atomiques :
    // - POST de création (via _payloadCreation) : envoie niveau/sequence
    // - PATCH de modification (via collecterFormulaire) : N'envoie PAS
    //   niveau/sequence (le scope d'une notion n'est pas modifiable
    //   depuis l'UI, et le backend modifier_notion préfère ne pas le
    //   recevoir pour éviter les écrasements involontaires).
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
    this._injecterBoutonReprendreTitre('atl-notion-titre');
  }

  // ── Sections (modèle universel à 2 niveaux) ─────────────────────────────

  /** Lit les sections depuis le DOM (à appeler avant tout changement
   * structurel pour ne pas perdre la saisie en cours). */
  _lireSectionsDOM() {
    const blocs = document.querySelectorAll(
      '#atl-notion-sections-zone .atl-section-bloc',
    );
    this.sections = Array.from(blocs).map(bloc => ({
      titre: (bloc.querySelector('.atl-section-titre-input') || {}).value || '',
      items: Array.from(bloc.querySelectorAll('.atl-section-item-row textarea'))
                  .map(t => t.value),
    }));
  }

  /** Re-rend toutes les sections depuis this.sections. */
  rendreSections() {
    const zone = document.getElementById('atl-notion-sections-zone');
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
        // marqueur data-ed-latex-attache="1" pour que le scanner global
        // de l'éditeur LaTeX n'ajoute PAS un deuxième bouton flottant
        // (qui se superposait avec les flèches monter/descendre/×).
        // Le bouton manuel cible son textarea via la classe + section/item
        // index : on utilise this dans le onclick parce qu'il est plus
        // robuste qu'un id calculé (les items peuvent être réordonnés).
        return `
          <div class="atl-section-item-row">
            <textarea class="latex-textarea" rows="2"
                      data-contexte-latex="notion-corps"
                      data-ed-latex-attache="1">${safe}</textarea>
            <div class="atl-section-item-actions">
              <button class="btn-ed-latex-manuel btn-ed-latex-manuel--compact"
                      onclick="EditeurLatex.ouvrir(this.closest('.atl-section-item-row').querySelector('textarea'))"
                      title="Ouvrir l'éditeur LaTeX">✎</button>
              <button onclick="ATELIER_NOTION.deplacerItem(${iSec},${iIt},-1)" ${peutMonterIt?'':'disabled'} title="Monter">↑</button>
              <button onclick="ATELIER_NOTION.deplacerItem(${iSec},${iIt},1)"  ${peutDescendreIt?'':'disabled'} title="Descendre">↓</button>
              <button class="btn-del-item" onclick="ATELIER_NOTION.supprimerItem(${iSec},${iIt})" title="Supprimer">×</button>
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
                   onchange="ATELIER_NOTION.majTitreSection(${iSec}, this.value)">
            <div class="atl-section-actions">
              <button onclick="ATELIER_NOTION.deplacerSection(${iSec}, -1)" ${peutMonter?'':'disabled'} title="Monter la section">↑</button>
              <button onclick="ATELIER_NOTION.deplacerSection(${iSec}, 1)"  ${peutDescendre?'':'disabled'} title="Descendre la section">↓</button>
              <button class="btn-suppr-sec" onclick="ATELIER_NOTION.supprimerSection(${iSec})" title="Supprimer la section">×</button>
            </div>
          </div>
          <div class="atl-section-items">${itemsHtml || '<div class="atl-section-item-vide">Aucun item.</div>'}</div>
          <button class="btn-sm" style="font-size:11px" onclick="ATELIER_NOTION.ajouterItem(${iSec})">+ Ajouter un item</button>
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
  // #atl-notion-* + verifierCacheEtAfficher + compilerRendu via
  // endpointRenduPdf='/api/atomes/notion'). L'ancien hack qui appelait
  // window.rendreAtomeTab('notion') pour générer le HTML dynamiquement
  // n'est plus nécessaire.

  // ── Handler générique formulaire ────────────────────────────────────────

  formChange() {
    if (!this.itemActif) return;
    this.marquerModifie();
  }
}

// ── Instance singleton et exposition globale ──────────────────────────────

const ATELIER_NOTION = new AtelierNotion();
window.ATELIER_NOTION = ATELIER_NOTION;

// v0.13.7.0c — Enregistrement dans le registre unifié.
if (typeof window.atelGardeEnregistrer === 'function') {
  window.atelGardeEnregistrer('Notion', ATELIER_NOTION);
}

// ── Ponts rétrocompat ─────────────────────────────────────────────────────
//
// Les anciens noms restent dispos pour les références internes
// (atelNotionBasculerValidationCb dans app.js, rendu_atome.js qui lit
// ATL_NOTION_ACTIF, etc.). À nettoyer en v0.14.
//
// v0.13.7.0c — ATL_ATOME_CONFIG (legacy atelier_atome_generique.js) a disparu.

window.atelChargerNotions          = () => ATELIER_NOTION.chargerListe();
window.atelRenderNotionListe       = () => ATELIER_NOTION.rendreSidebar();
window.atelNotionNouveau           = () => ATELIER_NOTION.nouvelItem();
window.atelNotionCharger           = (id) => ATELIER_NOTION.ouvrirItem(id);
window.atelNotionSauvegarder       = () => ATELIER_NOTION.sauvegarder();
window.atelNotionSupprimer         = () => ATELIER_NOTION.supprimer();
window.atelNotionRemplir           = (n) => ATELIER_NOTION.remplirFormulaire(n);
window.atelNotionRenderSections    = () => ATELIER_NOTION.rendreSections();
window.atelNotionAjouterSection    = () => ATELIER_NOTION.ajouterSection();
window.atelNotionSupprimerSection  = (iSec) => ATELIER_NOTION.supprimerSection(iSec);
window.atelNotionDeplacerSection   = (iSec, delta) => ATELIER_NOTION.deplacerSection(iSec, delta);
window.atelNotionMajTitre          = (iSec, val) => ATELIER_NOTION.majTitreSection(iSec, val);
window.atelNotionAjouterItem       = (iSec) => ATELIER_NOTION.ajouterItem(iSec);
window.atelNotionSupprimerItem     = (iSec, iIt) => ATELIER_NOTION.supprimerItem(iSec, iIt);
window.atelNotionDeplacerItem      = (iSec, iIt, delta) => ATELIER_NOTION.deplacerItem(iSec, iIt, delta);
window.atelNotionTab               = (tab) => ATELIER_NOTION.basculerOnglet(tab);
window.atelNotionVoirLatex         = () => ATELIER_NOTION.voirLatex();
window.atelNotionBasculerValidationCb = () => ATELIER_NOTION.basculerValidation();
window.atelNotionAfficherEditeur   = (existant) => ATELIER_NOTION.afficherEditeur(existant);
// La fonction `_atelNotionLireDOM` était parfois appelée par d'autres
// modules ; on la conserve comme pont vers la méthode interne.
window._atelNotionLireDOM          = () => ATELIER_NOTION._lireSectionsDOM();
