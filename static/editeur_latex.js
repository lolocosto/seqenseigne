/* static/editeur_latex.js — v0.13.7.6.1
 *
 * Éditeur LaTeX spécialisé sur le paquet seqenseigne.
 *
 * Architecture
 * ────────────
 *
 * 1. Scanner les textareas avec attribut data-contexte-latex et attacher
 *    un bouton « ✎ Éditer » à droite du label associé.
 * 2. Au clic, ouvrir une modale plein écran avec 3 onglets :
 *      - Outils : barre d'outils pédagogique selon le contexte
 *      - Tout le paquet : liste exhaustive du paquet seqenseigne
 *      - Aides : placeholder Phase 1, contenu Phase 3
 * 3. À la fermeture (OK), réinjecter dans le textarea d'origine.
 * 4. La détection « modifié » et la garde de sortie sont fournies par
 *    AtelierEditeur (v0.13.7.0d) — l'éditeur LaTeX n'a qu'à dispatcher
 *    un événement `input` après réinjection.
 *
 * API publique exposée :
 *   - window.EditeurLatex.scan(racine?)      — scanne et équipe
 *   - window.EditeurLatex.ouvrir(textarea)   — ouvre la modale
 *
 * Idempotence : marqueur dataset `data-ed-latex-attache="1"` posé sur
 * chaque textarea équipé.
 *
 * Historique des versions
 * ───────────────────────
 *   v0.13.7.1  Squelette éditeur + onglet « Tout le paquet »
 *   v0.13.7.2  JSON 9 contextes + engrenage masquage
 *   v0.13.7.2.x Hotfixes parseur (compteurs, choicekey)
 *   v0.13.7.3  Wrapping de sélection • + générateurs QCM/Liste
 *   v0.13.7.4  Navigateur d'images + élargissement modales
 *   v0.13.7.5  Icônes SVG (mise en forme, mise en page, maths, listes)
 *              + italique + picker de taille + 4 styles maths
 *                (\mathcal, \mathbb, \mathbf, \mathrm)
 *              + générateur de tableau longtblr complet
 *              + groupe Image disponible dans tous les contextes
 *   v0.13.7.6  Slider largeur de colonne visible (label « Largeur : » +
 *              CSS rail bleu/poignée ronde), groupe « Listes » retiré
 *              (redondant avec le générateur ☰ Liste), tooltip Tableau
 *              mis à jour.
 *   v0.13.7.6.1 Slider remplacé par stepper [−] ×N [+] (le slider natif
 *              restait invisible sur certains navigateurs/thèmes malgré
 *              le style explicite des pseudo-éléments webkit/moz).
 *              Boutons d'alignement à largeur fixe pour supprimer la
 *              scrollbar horizontale parasite.
 */

(function () {
  'use strict';

  // ── Constantes ────────────────────────────────────────────────────────────

  const SEUIL_PICTO_COMPACT = 3;  // rows <= seuil → bouton avec ✎ seul
  const URL_DEFINITIONS = '/api/paquet/definitions';
  const URL_TOOLBAR_JSON = '/static/data/toolbar_seqenseigne.json';
  const LS_PREFIX = 'ed-latex:groupes-visibles:';

  // ── Bibliothèque d'icônes SVG (v0.13.7.5) ────────────────────────────────
  //
  // Chaque icône est un fragment SVG (sans wrapper <svg>) dessiné dans la
  // boîte 16×16. Le wrapper <svg viewBox="0 0 16 16" ...> est ajouté
  // automatiquement par _htmlIconeSvg().
  //
  // Convention de style :
  //   - Trait fin (stroke-width=1.5), couleur currentColor pour suivre
  //     la couleur du bouton (texte sombre par défaut, ajusté au hover).
  //   - Pour les caractères mathématiques, on s'autorise un <text> SVG
  //     plutôt que de re-dessiner chaque glyphe à la main.
  //
  // Si un item du JSON porte une clé "icone" non listée ici, le bouton
  // affiche le label texte (dégradation silencieuse).
  const ICONES_SVG = {
    // Mise en forme
    bold:      '<text x="8" y="13" text-anchor="middle" font-family="serif" font-weight="900" font-size="14" fill="currentColor">B</text>',
    italic:    '<text x="8" y="13" text-anchor="middle" font-family="serif" font-style="italic" font-weight="700" font-size="14" fill="currentColor">I</text>',
    mono:      '<text x="8" y="12" text-anchor="middle" font-family="monospace" font-size="10" fill="currentColor">&lt;&gt;</text>',
    underline: '<text x="8" y="11" text-anchor="middle" font-family="serif" font-size="13" fill="currentColor">U</text><line x1="3" y1="14" x2="13" y2="14" stroke="currentColor" stroke-width="1.5"/>',
    sup:       '<text x="4" y="13" font-family="serif" font-size="11" fill="currentColor">x</text><text x="9" y="8" font-family="serif" font-size="8" fill="currentColor">2</text>',
    sub:       '<text x="4" y="11" font-family="serif" font-size="11" fill="currentColor">x</text><text x="9" y="14" font-family="serif" font-size="8" fill="currentColor">2</text>',
    taille:    '<text x="3" y="14" font-family="sans-serif" font-size="9"  fill="currentColor">A</text>'
             + '<text x="9" y="13" font-family="sans-serif" font-size="11" fill="currentColor">A</text>',

    // Mise en page
    center:    '<line x1="3" y1="4"  x2="13" y2="4"  stroke="currentColor" stroke-width="1.5"/>'
             + '<line x1="5" y1="8"  x2="11" y2="8"  stroke="currentColor" stroke-width="1.5"/>'
             + '<line x1="3" y1="12" x2="13" y2="12" stroke="currentColor" stroke-width="1.5"/>',
    right:     '<line x1="3" y1="4"  x2="13" y2="4"  stroke="currentColor" stroke-width="1.5"/>'
             + '<line x1="6" y1="8"  x2="13" y2="8"  stroke="currentColor" stroke-width="1.5"/>'
             + '<line x1="3" y1="12" x2="13" y2="12" stroke="currentColor" stroke-width="1.5"/>',
    left:      '<line x1="3" y1="4"  x2="13" y2="4"  stroke="currentColor" stroke-width="1.5"/>'
             + '<line x1="3" y1="8"  x2="10" y2="8"  stroke="currentColor" stroke-width="1.5"/>'
             + '<line x1="3" y1="12" x2="13" y2="12" stroke="currentColor" stroke-width="1.5"/>',
    smallskip: '<line x1="2" y1="5" x2="14" y2="5" stroke="currentColor" stroke-width="1.5"/>'
             + '<line x1="2" y1="9" x2="14" y2="9" stroke="currentColor" stroke-width="1.5"/>'
             + '<text x="13" y="15" font-family="sans-serif" font-size="6" fill="currentColor">s</text>',
    medskip:   '<line x1="2" y1="4"  x2="14" y2="4"  stroke="currentColor" stroke-width="1.5"/>'
             + '<line x1="2" y1="10" x2="14" y2="10" stroke="currentColor" stroke-width="1.5"/>'
             + '<text x="13" y="15" font-family="sans-serif" font-size="6" fill="currentColor">m</text>',
    bigskip:   '<line x1="2" y1="3"  x2="14" y2="3"  stroke="currentColor" stroke-width="1.5"/>'
             + '<line x1="2" y1="12" x2="14" y2="12" stroke="currentColor" stroke-width="1.5"/>'
             + '<text x="13" y="9" font-family="sans-serif" font-size="6" fill="currentColor">b</text>',
    newline:   '<path d="M 12 4 L 12 9 L 5 9" stroke="currentColor" stroke-width="1.5" fill="none"/>'
             + '<path d="M 7 7 L 4 9 L 7 11" stroke="currentColor" stroke-width="1.5" fill="none"/>',
    par:       '<text x="2" y="13" font-family="serif" font-size="13" font-weight="bold" fill="currentColor">¶</text>',

    // Maths
    mathinline:  '<text x="8" y="13" text-anchor="middle" font-family="serif" font-style="italic" font-size="12" fill="currentColor">$x$</text>',
    mathdisplay: '<rect x="2" y="3" width="12" height="10" stroke="currentColor" stroke-width="1" fill="none" stroke-dasharray="1.5,1"/>'
              +  '<text x="8" y="11" text-anchor="middle" font-family="serif" font-style="italic" font-size="8" fill="currentColor">y=ax+b</text>',
    frac:        '<text x="8" y="7"  text-anchor="middle" font-family="serif" font-size="6" fill="currentColor">a</text>'
              +  '<line x1="3" y1="8" x2="13" y2="8" stroke="currentColor" stroke-width="1.2"/>'
              +  '<text x="8" y="14" text-anchor="middle" font-family="serif" font-size="6" fill="currentColor">b</text>',
    fracSeq:     '<text x="8" y="7"  text-anchor="middle" font-family="serif" font-size="6" fill="currentColor">a</text>'
              +  '<line x1="3" y1="8" x2="13" y2="8" stroke="currentColor" stroke-width="1.6"/>'
              +  '<text x="8" y="14" text-anchor="middle" font-family="serif" font-size="6" fill="currentColor">b</text>'
              +  '<circle cx="13" cy="3" r="2" fill="currentColor"/>'
              +  '<text x="13" y="4.2" text-anchor="middle" font-family="sans-serif" font-size="3" fill="white">s</text>',
    sqrt:        '<path d="M 2 9 L 5 12 L 8 4 L 14 4" stroke="currentColor" stroke-width="1.4" fill="none"/>',
    mathsExposant: '<text x="3" y="13" font-family="serif" font-style="italic" font-size="11" fill="currentColor">x</text>'
                +  '<text x="8" y="7"  font-family="serif" font-size="7" fill="currentColor">n</text>',
    mathsIndice:   '<text x="3" y="11" font-family="serif" font-style="italic" font-size="11" fill="currentColor">x</text>'
                +  '<text x="8" y="14" font-family="serif" font-size="7" fill="currentColor">i</text>',
    times:    '<text x="8" y="13" text-anchor="middle" font-family="serif" font-size="14" fill="currentColor">×</text>',
    div:      '<text x="8" y="13" text-anchor="middle" font-family="serif" font-size="14" fill="currentColor">÷</text>',
    leq:      '<text x="8" y="13" text-anchor="middle" font-family="serif" font-size="13" fill="currentColor">≤</text>',
    geq:      '<text x="8" y="13" text-anchor="middle" font-family="serif" font-size="13" fill="currentColor">≥</text>',
    neq:      '<text x="8" y="13" text-anchor="middle" font-family="serif" font-size="13" fill="currentColor">≠</text>',
    pi:       '<text x="8" y="13" text-anchor="middle" font-family="serif" font-style="italic" font-size="14" fill="currentColor">π</text>',
    degree:   '<text x="8" y="13" text-anchor="middle" font-family="serif" font-size="13" fill="currentColor">°C</text>',
    ldots:    '<text x="8" y="13" text-anchor="middle" font-family="serif" font-size="14" fill="currentColor">…</text>',
    // Lettres spéciales en mode math. Unicode mathématique : caractères
    // calligraphiques (𝒜, U+1D49C) et ajourés (ℝ, U+211D). Rendu fidèle
    // pour les polices système qui les ont (la plupart) ; sinon le
    // tooltip reste lisible.
    mathcal:  '<text x="8" y="13" text-anchor="middle" font-family="serif" font-size="14" fill="currentColor">𝒜</text>',
    mathbb:   '<text x="8" y="13" text-anchor="middle" font-family="serif" font-size="14" fill="currentColor">ℝ</text>',
    mathbf:   '<text x="8" y="13" text-anchor="middle" font-family="sans-serif" font-weight="900" font-size="13" fill="currentColor">A</text>',
    mathrm:   '<text x="8" y="13" text-anchor="middle" font-family="serif" font-size="13" fill="currentColor">A</text>',

    // Listes
    itemize:   '<circle cx="3" cy="4"  r="1.2" fill="currentColor"/>'
            +  '<line x1="6" y1="4"  x2="13" y2="4"  stroke="currentColor" stroke-width="1.2"/>'
            +  '<circle cx="3" cy="8"  r="1.2" fill="currentColor"/>'
            +  '<line x1="6" y1="8"  x2="13" y2="8"  stroke="currentColor" stroke-width="1.2"/>'
            +  '<circle cx="3" cy="12" r="1.2" fill="currentColor"/>'
            +  '<line x1="6" y1="12" x2="13" y2="12" stroke="currentColor" stroke-width="1.2"/>',
    enumerate: '<text x="2" y="6"  font-family="sans-serif" font-size="5" fill="currentColor">1.</text>'
            +  '<line x1="6" y1="4"  x2="13" y2="4"  stroke="currentColor" stroke-width="1.2"/>'
            +  '<text x="2" y="10" font-family="sans-serif" font-size="5" fill="currentColor">2.</text>'
            +  '<line x1="6" y1="8"  x2="13" y2="8"  stroke="currentColor" stroke-width="1.2"/>'
            +  '<text x="2" y="14" font-family="sans-serif" font-size="5" fill="currentColor">3.</text>'
            +  '<line x1="6" y1="12" x2="13" y2="12" stroke="currentColor" stroke-width="1.2"/>',
    item:      '<circle cx="4" cy="8" r="1.5" fill="currentColor"/>'
            +  '<line x1="7" y1="8" x2="13" y2="8" stroke="currentColor" stroke-width="1.5"/>',
    colItem:   '<circle cx="2" cy="4"  r="1" fill="currentColor"/>'
            +  '<line x1="4" y1="4"  x2="7" y2="4"  stroke="currentColor" stroke-width="1"/>'
            +  '<circle cx="9" cy="4"  r="1" fill="currentColor"/>'
            +  '<line x1="11" y1="4" x2="14" y2="4" stroke="currentColor" stroke-width="1"/>'
            +  '<circle cx="2" cy="8"  r="1" fill="currentColor"/>'
            +  '<line x1="4" y1="8"  x2="7" y2="8"  stroke="currentColor" stroke-width="1"/>'
            +  '<circle cx="9" cy="8"  r="1" fill="currentColor"/>'
            +  '<line x1="11" y1="8" x2="14" y2="8" stroke="currentColor" stroke-width="1"/>'
            +  '<circle cx="2" cy="12" r="1" fill="currentColor"/>'
            +  '<line x1="4" y1="12" x2="7" y2="12" stroke="currentColor" stroke-width="1"/>'
            +  '<circle cx="9" cy="12" r="1" fill="currentColor"/>'
            +  '<line x1="11" y1="12" x2="14" y2="12" stroke="currentColor" stroke-width="1"/>',
    colEnum:   '<text x="1" y="5"  font-family="sans-serif" font-size="4" fill="currentColor">1</text>'
            +  '<line x1="3" y1="4"  x2="7" y2="4"  stroke="currentColor" stroke-width="1"/>'
            +  '<text x="8" y="5"  font-family="sans-serif" font-size="4" fill="currentColor">2</text>'
            +  '<line x1="10" y1="4" x2="14" y2="4" stroke="currentColor" stroke-width="1"/>'
            +  '<text x="1" y="9"  font-family="sans-serif" font-size="4" fill="currentColor">3</text>'
            +  '<line x1="3" y1="8"  x2="7" y2="8"  stroke="currentColor" stroke-width="1"/>'
            +  '<text x="8" y="9"  font-family="sans-serif" font-size="4" fill="currentColor">4</text>'
            +  '<line x1="10" y1="8" x2="14" y2="8" stroke="currentColor" stroke-width="1"/>'
  };

  function _htmlIconeSvg(nomIcone) {
    const corps = ICONES_SVG[nomIcone];
    if (!corps) return '';
    return '<svg class="ed-latex-icone" viewBox="0 0 16 16" '
         + 'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
         + corps + '</svg>';
  }

  // ── Cache des données chargées paresseusement ────────────────────────────

  let _definitionsPaquet = { false: null, true: null };  // cache par booléen inclure_structurelles
  let _toolbarConfig = null;       // {contextes: {...}, groupes: {...}} ou null
  let _modale = null;              // élément DOM de la modale (singleton)
  let _textareaCible = null;       // textarea d'origine en cours d'édition

  // ── Scan et attachement ───────────────────────────────────────────────────

  /**
   * Scanne le DOM (depuis `racine` ou document.body par défaut) et
   * équipe tous les textareas avec data-contexte-latex d'un bouton
   * « ✎ Éditer ».
   *
   * Idempotent : un textarea déjà équipé est ignoré.
   */
  function scan(racine) {
    racine = racine || document.body;
    const textareas = racine.querySelectorAll(
      'textarea[data-contexte-latex]:not([data-ed-latex-attache])'
    );
    textareas.forEach(_attacherBouton);
  }

  function _attacherBouton(textarea) {
    textarea.dataset.edLatexAttache = '1';
    const rows = parseInt(textarea.getAttribute('rows') || '6', 10);
    const compact = rows <= SEUIL_PICTO_COMPACT;

    const bouton = document.createElement('button');
    bouton.type = 'button';
    bouton.className = 'btn-ed-latex' + (compact ? ' btn-ed-latex--compact' : '');
    bouton.textContent = compact ? '✎' : '✎ Éditer';
    bouton.title = 'Ouvrir l\'éditeur LaTeX';
    bouton.onclick = function (ev) {
      ev.preventDefault();
      ouvrir(textarea);
    };

    // Placement : à droite du label associé (via for=) ou de
    // l'élément <label> précédent immédiatement le textarea.
    const id = textarea.id;
    let label = id ? document.querySelector('label[for="' + id + '"]') : null;
    if (!label) {
      // Cherche un <label> dans le parent direct.
      const parent = textarea.parentElement;
      if (parent) {
        const candidats = parent.querySelectorAll(':scope > label, :scope > .atl-label');
        if (candidats.length > 0) label = candidats[candidats.length - 1];
      }
    }
    if (label) {
      // Espace entre le texte du label et le bouton.
      label.appendChild(document.createTextNode(' '));
      label.appendChild(bouton);
    } else {
      // Pas de label visible. Bouton flottant en haut-droite absolu.
      // Le parent doit être position:relative pour que ça marche ;
      // sinon, le bouton flotte par rapport au body, ce qui est moche
      // mais pas critique pour la Phase 1.
      bouton.classList.add('btn-ed-latex--flottant');
      const parent = textarea.parentElement;
      if (parent) {
        const cs = window.getComputedStyle(parent);
        if (cs.position === 'static') parent.style.position = 'relative';
        parent.appendChild(bouton);
      }
    }
  }

  // ── Modale ────────────────────────────────────────────────────────────────

  /**
   * Ouvre la modale d'édition LaTeX sur le textarea cible.
   */
  function ouvrir(textarea) {
    _textareaCible = textarea;
    const contexte = textarea.dataset.contexteLatex || '';
    _construireModale(contexte);
    _modale.querySelector('.ed-latex-zone').value = textarea.value;
    _modale.style.display = 'flex';
    // Focus dans la zone d'édition après ouverture.
    setTimeout(() => _modale.querySelector('.ed-latex-zone').focus(), 50);
  }

  function _fermer(reinjecter) {
    if (reinjecter && _textareaCible) {
      const zone = _modale.querySelector('.ed-latex-zone');
      _textareaCible.value = zone.value;
      // Dispatch input pour que la garde-de-sortie (snapshot v0.13.7.0d)
      // détecte le changement et l'autosave éventuel se déclenche.
      _textareaCible.dispatchEvent(new Event('input', { bubbles: true }));
    }
    _modale.style.display = 'none';
    _textareaCible = null;
  }

  function _construireModale(contexte) {
    if (_modale) {
      // Modale déjà construite : rebascule onglet Outils par défaut et
      // recharge la barre d'outils selon le nouveau contexte.
      _modale.dataset.contexte = contexte;
      _basculerOnglet('outils');
      _peuplerOngletOutils(contexte);
      return;
    }
    _modale = document.createElement('div');
    _modale.className = 'ed-latex-modale';
    _modale.dataset.contexte = contexte;
    _modale.innerHTML = `
      <div class="ed-latex-modale-fond"></div>
      <div class="ed-latex-modale-contenu">
        <div class="ed-latex-modale-header">
          <div class="ed-latex-modale-titre">Éditeur LaTeX</div>
          <div class="ed-latex-modale-onglets">
            <button type="button" class="ed-latex-onglet" data-onglet="outils">Outils</button>
            <button type="button" class="ed-latex-onglet" data-onglet="paquet">Tout le paquet</button>
            <button type="button" class="ed-latex-onglet" data-onglet="aides">Aides</button>
          </div>
          <button type="button" class="ed-latex-modale-engrenage"
                  title="Configurer les groupes d'outils visibles">⚙</button>
          <button type="button" class="ed-latex-modale-fermer" title="Fermer (Esc)">×</button>
        </div>
        <div class="ed-latex-panneau" data-panneau="outils"></div>
        <div class="ed-latex-panneau" data-panneau="paquet" style="display:none"></div>
        <div class="ed-latex-panneau" data-panneau="aides" style="display:none"></div>
        <textarea class="latex-textarea ed-latex-zone" rows="20"
                  style="width:100%;font-family:monospace;font-size:13px;
                         flex:1;resize:none;margin-top:8px"></textarea>
        <div class="ed-latex-modale-actions">
          <button type="button" class="btn-sm ed-latex-btn-annuler">Annuler</button>
          <button type="button" class="btn-prim ed-latex-btn-ok">OK — Réinjecter</button>
        </div>
        <!-- Mini-modale interne (overlay générique) — v0.13.7.3 :
             un seul DOM réutilisé pour 3 usages :
             - config-groupes (engrenage v0.13.7.2)
             - generateur-qcm  (v0.13.7.3)
             - generateur-liste (v0.13.7.3)
             Le type courant est stocké en data-type. -->
        <div class="ed-latex-conf" style="display:none" data-type="">
          <div class="ed-latex-conf-fond"></div>
          <div class="ed-latex-conf-contenu">
            <div class="ed-latex-conf-titre"></div>
            <p class="ed-latex-conf-aide"></p>
            <div class="ed-latex-conf-liste"></div>
            <div class="ed-latex-conf-actions">
              <button type="button" class="btn-sm ed-latex-conf-reset" style="display:none">Tout afficher</button>
              <button type="button" class="btn-sm ed-latex-conf-annuler" style="margin-left:auto">Annuler</button>
              <button type="button" class="btn-prim ed-latex-conf-valider">Valider</button>
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(_modale);
    // Câblage des handlers.
    _modale.querySelectorAll('.ed-latex-onglet').forEach(btn => {
      btn.onclick = () => _basculerOnglet(btn.dataset.onglet);
    });
    _modale.querySelector('.ed-latex-modale-fermer').onclick = () => _fermer(false);
    _modale.querySelector('.ed-latex-btn-annuler').onclick = () => _fermer(false);
    _modale.querySelector('.ed-latex-btn-ok').onclick = () => _fermer(true);
    _modale.querySelector('.ed-latex-modale-fond').onclick = () => _fermer(false);
    // v0.13.7.2 — Engrenage de configuration des groupes visibles.
    // v0.13.7.3 — Étendu en mini-modale générique (type config-groupes/qcm/liste/tableau).
    _modale.querySelector('.ed-latex-modale-engrenage').onclick = () => _ouvrirMiniModale('config-groupes');
    _modale.querySelector('.ed-latex-conf-fond').onclick = () => _fermerMiniModale();
    _modale.querySelector('.ed-latex-conf-annuler').onclick = () => _fermerMiniModale();
    _modale.querySelector('.ed-latex-conf-valider').onclick = () => _validerMiniModale();
    _modale.querySelector('.ed-latex-conf-reset').onclick = () => _resetMiniModale();
    // Raccourcis clavier : Esc = annuler, Ctrl+Enter = OK.
    document.addEventListener('keydown', _gestionnaireClavier);

    // Initialisation des panneaux.
    _basculerOnglet('outils');
    _peuplerOngletOutils(contexte);
    _peuplerOngletAides();
    // L'onglet paquet est peuplé paresseusement à sa première ouverture.
  }

  function _gestionnaireClavier(ev) {
    if (!_modale || _modale.style.display === 'none') return;
    // v0.13.7.2 — Si la mini-modale config est ouverte, Esc la ferme
    // (au lieu de fermer la modale principale).
    // v0.13.7.3 — La mini-modale couvre désormais aussi les générateurs.
    const conf = _modale.querySelector('.ed-latex-conf');
    if (conf && conf.style.display !== 'none') {
      if (ev.key === 'Escape') {
        ev.preventDefault();
        _fermerMiniModale();
      }
      return;
    }
    if (ev.key === 'Escape') {
      ev.preventDefault();
      _fermer(false);
    } else if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) {
      ev.preventDefault();
      _fermer(true);
    }
  }

  function _basculerOnglet(nom) {
    _modale.querySelectorAll('.ed-latex-onglet').forEach(btn => {
      btn.classList.toggle('ed-latex-onglet--actif', btn.dataset.onglet === nom);
    });
    _modale.querySelectorAll('.ed-latex-panneau').forEach(p => {
      p.style.display = (p.dataset.panneau === nom) ? 'block' : 'none';
    });
    // v0.13.7.2 — Engrenage visible seulement sur l'onglet Outils
    // (les autres onglets n'ont pas de groupes configurables).
    const engr = _modale.querySelector('.ed-latex-modale-engrenage');
    if (engr) engr.style.display = (nom === 'outils') ? '' : 'none';
    // Lazy load paquet
    if (nom === 'paquet' && !_modale._paquetCharge) {
      _peuplerOngletPaquet();
      _modale._paquetCharge = true;
    }
  }

  // ── Onglet « Outils » ─────────────────────────────────────────────────────

  function _peuplerOngletOutils(contexte) {
    const panneau = _modale.querySelector('[data-panneau="outils"]');
    _chargerToolbarConfig().then(config => {
      // v0.13.7.3 — Rangée de générateurs en tête du panneau, indépendante
      // du contexte (les générateurs marchent dans n'importe quel champ
      // texte : QCM dans un énoncé, liste dans une notion, tableau partout).
      const generateursHtml = `
        <div class="ed-latex-generateurs">
          <span class="ed-latex-generateurs-label">Générateurs :</span>
          <button type="button" class="ed-latex-btn-generateur"
                  data-generateur="qcm" title="Générer un QCM seqQcm avec ses paramètres">
            ⊞ QCM
          </button>
          <button type="button" class="ed-latex-btn-generateur"
                  data-generateur="liste" title="Générer une liste avec items et puce \\ding">
            ☰ Liste
          </button>
          <button type="button" class="ed-latex-btn-generateur"
                  data-generateur="tableau" title="Générateur de tableau longtblr (1-6 colonnes, alignement, largeur relative, filets)">
            ▦ Tableau
          </button>
        </div>
      `;

      const groupes = (config.contextes && config.contextes[contexte]) || null;
      if (!groupes || groupes.length === 0) {
        panneau.innerHTML = generateursHtml + `
          <p class="ed-latex-placeholder">
            Barre d'outils pédagogique non encore configurée pour ce contexte
            (<code>${_escapeHtml(contexte)}</code>).
            En attendant, utilisez les générateurs ci-dessus ou l'onglet « Tout le paquet ».
          </p>
        `;
        _cablerBoutonsGenerateurs(panneau);
        return;
      }
      // v0.13.7.2 — Filtrer les groupes selon les préférences localStorage.
      const visibles = _lireVisibilites(contexte, groupes);
      const groupesAffiches = groupes.filter(g => visibles[g] !== false);
      const nbCaches = groupes.length - groupesAffiches.length;

      const groupesHtml = groupesAffiches.map(nomGroupe => {
        const grp = config.groupes && config.groupes[nomGroupe];
        if (!grp) return '';
        return `
          <div class="ed-latex-groupe">
            <div class="ed-latex-groupe-titre">${_escapeHtml(grp.label || nomGroupe)}</div>
            <div class="ed-latex-groupe-items">
              ${grp.items.map(item => _htmlBoutonOutil(item)).join('')}
            </div>
          </div>
        `;
      }).join('');
      const piedHtml = nbCaches > 0
        ? `<div class="ed-latex-groupes-caches">${nbCaches} groupe${nbCaches > 1 ? 's' : ''} masqué${nbCaches > 1 ? 's' : ''} — utiliser ⚙ pour configurer</div>`
        : '';
      panneau.innerHTML = generateursHtml + groupesHtml + piedHtml;
      panneau.querySelectorAll('.ed-latex-btn-outil').forEach(btn => {
        btn.onclick = () => _gererClicSnippet(btn.dataset.snippet);
      });
      _cablerBoutonsGenerateurs(panneau);
    });
  }

  // v0.13.7.4 — Aiguille un clic sur bouton d'outil vers l'insertion
  // classique OU vers une mini-modale interactive selon le snippet.
  //   - __NAVIGATEUR_IMAGES__  ouvre le navigateur d'images (v0.13.7.4)
  //   - __PICKER_TAILLE__      ouvre le picker de tailles de texte (v0.13.7.5)
  function _gererClicSnippet(snippet) {
    if (snippet === '__NAVIGATEUR_IMAGES__') {
      _ouvrirMiniModale('image');
      return;
    }
    if (snippet === '__PICKER_TAILLE__') {
      _ouvrirMiniModale('taille');
      return;
    }
    _insererSnippet(snippet);
  }

  function _cablerBoutonsGenerateurs(panneau) {
    panneau.querySelectorAll('.ed-latex-btn-generateur').forEach(btn => {
      btn.onclick = () => _ouvrirMiniModale(btn.dataset.generateur);
    });
  }

  function _htmlBoutonOutil(item) {
    const snippet = item.snippet || '';
    const tooltip = item.tooltip || item.label || snippet;
    // v0.13.7.5 — Si l'item porte une clé 'icone' reconnue, on affiche
    // l'icône SVG et le bouton prend une classe modifier qui fixe sa
    // largeur (carré 28×28 environ). Sinon, comportement classique
    // (label texte avec largeur libre).
    if (item.icone && ICONES_SVG[item.icone]) {
      return `<button type="button"
                      class="ed-latex-btn-outil ed-latex-btn-outil--icone"
                      data-snippet="${_escapeAttr(snippet)}"
                      title="${_escapeAttr(tooltip)}">${_htmlIconeSvg(item.icone)}</button>`;
    }
    const lib = _escapeHtml(item.label || snippet || '?');
    return `<button type="button" class="ed-latex-btn-outil"
                    data-snippet="${_escapeAttr(snippet)}"
                    title="${_escapeAttr(tooltip)}">${lib}</button>`;
  }

  // ── Onglet « Tout le paquet » ────────────────────────────────────────────

  // v0.13.7.2.1 — Clé localStorage pour la préférence « afficher les
  // macros structurelles ». Globale (pas par contexte) : c'est une
  // préférence d'expertise utilisateur, indépendante du contexte courant.
  const LS_STRUCTURELLES = 'ed-latex:afficher-structurelles';

  function _lireStructurellesPref() {
    try {
      return window.localStorage
        && window.localStorage.getItem(LS_STRUCTURELLES) === '1';
    } catch (e) {
      return false;
    }
  }
  function _ecrireStructurellesPref(actif) {
    try {
      if (window.localStorage) {
        window.localStorage.setItem(LS_STRUCTURELLES, actif ? '1' : '0');
      }
    } catch (e) {
      // ignore
    }
  }

  function _peuplerOngletPaquet() {
    const panneau = _modale.querySelector('[data-panneau="paquet"]');
    panneau.innerHTML = '<p class="ed-latex-placeholder">Chargement...</p>';
    const afficherStruct = _lireStructurellesPref();
    _chargerDefinitions(afficherStruct).then(data => {
      const fichiers = data.fichiers || [];
      panneau.innerHTML = `
        <div class="ed-latex-paquet">
          <div class="ed-latex-paquet-nav">
            ${fichiers.map((f, i) => `
              <button type="button" class="ed-latex-paquet-fichier${i === 0 ? ' ed-latex-paquet-fichier--actif' : ''}"
                      data-idx="${i}">${_escapeHtml(f.label)}</button>
            `).join('')}
            <label class="ed-latex-paquet-toggle-struct" title="Affiche les macros que l'app ajoute automatiquement autour du contenu (seqExercice, seqCorrige, seqNotion, etc.). Ces macros ne doivent normalement pas être insérées manuellement, mais sont utiles pour comprendre ce qui se passe ou dans des cas avancés.">
              <input type="checkbox" class="ed-latex-paquet-toggle-struct-cb" ${afficherStruct ? 'checked' : ''}>
              <span>Afficher les macros structurelles</span>
            </label>
          </div>
          <div class="ed-latex-paquet-liste"></div>
        </div>
      `;
      panneau.querySelectorAll('.ed-latex-paquet-fichier').forEach(btn => {
        btn.onclick = () => _selectionnerFichierPaquet(fichiers, parseInt(btn.dataset.idx, 10));
      });
      // v0.13.7.2.1 — Toggle case structurelles : re-fetch et re-render
      const cb = panneau.querySelector('.ed-latex-paquet-toggle-struct-cb');
      if (cb) {
        cb.onchange = () => {
          _ecrireStructurellesPref(cb.checked);
          _peuplerOngletPaquet();  // rebuild complet du panneau
        };
      }
      _selectionnerFichierPaquet(fichiers, 0);
    }).catch(err => {
      panneau.innerHTML = `<p class="ed-latex-erreur">Erreur de chargement : ${_escapeHtml(err.message || String(err))}</p>`;
    });
  }

  function _selectionnerFichierPaquet(fichiers, idx) {
    const f = fichiers[idx];
    const panneau = _modale.querySelector('[data-panneau="paquet"]');
    panneau.querySelectorAll('.ed-latex-paquet-fichier').forEach((btn, i) => {
      btn.classList.toggle('ed-latex-paquet-fichier--actif', i === idx);
    });
    const liste = panneau.querySelector('.ed-latex-paquet-liste');
    const blocs = [];
    if (f.commands.length > 0) {
      blocs.push('<div class="ed-latex-paquet-cat">Commandes</div>');
      blocs.push(...f.commands.map(c => _htmlItemPaquet(c, 'command')));
    }
    if (f.environments.length > 0) {
      blocs.push('<div class="ed-latex-paquet-cat">Environnements</div>');
      blocs.push(...f.environments.map(e => _htmlItemPaquet(e, 'environment')));
    }
    if (f.tcolorbox.length > 0) {
      blocs.push('<div class="ed-latex-paquet-cat">Boîtes (tcolorbox)</div>');
      blocs.push(...f.tcolorbox.map(t => _htmlItemPaquet(t, 'environment')));
    }
    liste.innerHTML = blocs.join('');
    liste.querySelectorAll('.ed-latex-paquet-item').forEach(btn => {
      btn.onclick = () => _gererClicSnippet(btn.dataset.snippet);
    });
  }

  /**
   * Génère un snippet d'insertion par défaut depuis (nom, args_spec).
   *   '\\seqFrac', '[2]' → '\\seqFrac{}{}'
   *   'seqDefinition', '[2]' → '\\begin{seqDefinition}{}{}\\n\\n\\end{seqDefinition}'
   */
  function _genererSnippet(nom, args_spec, kind) {
    // Compte les arguments obligatoires depuis args_spec ('[2]', '[1][def]', '[3][a][b]')
    const m = (args_spec || '').match(/^\[(\d+)\]/);
    const n = m ? parseInt(m[1], 10) : 0;
    const args = '{}'.repeat(n);
    if (kind === 'command') {
      return nom + args;
    }
    // environment / tcolorbox : on retire un éventuel backslash initial
    const e = nom.replace(/^\\/, '');
    return `\\begin{${e}}${args}\n\n\\end{${e}}`;
  }

  function _htmlItemPaquet(item, kind) {
    const snippet = _genererSnippet(item.nom, item.args_spec, kind);
    const spec = item.args_spec ? ` <span class="ed-latex-paquet-spec">${_escapeHtml(item.args_spec)}</span>` : '';
    return `<button type="button" class="ed-latex-paquet-item"
                    data-snippet="${_escapeAttr(snippet)}"
                    title="${_escapeAttr(snippet)}">
              <code>${_escapeHtml(item.nom)}</code>${spec}
            </button>`;
  }

  // ── Onglet « Aides » ─────────────────────────────────────────────────────

  function _peuplerOngletAides() {
    const panneau = _modale.querySelector('[data-panneau="aides"]');
    panneau.innerHTML = `
      <p class="ed-latex-placeholder">
        Guides Markdown disponibles en v0.13.7.3.<br>
        À terme : aides détaillées pour xint, tkz-euclide, et autres
        outils qui ne sont pas exposés dans les barres d'outils.
      </p>
    `;
  }

  // ── Insertion de snippet ─────────────────────────────────────────────────

  // v0.13.7.3 — Marqueur de position de la sélection dans un snippet.
  // Convention héritée de Texmaker : le caractère • (BULLET, U+2022) indique
  // où le texte sélectionné par l'utilisateur doit être inséré.
  //   - Si une sélection est active, • est remplacé par la sélection.
  //   - Sinon, • est retiré et le curseur est positionné à sa place
  //     (pour que l'utilisateur tape directement à l'emplacement attendu).
  // Si un snippet contient plusieurs •, seul le PREMIER reçoit la sélection /
  // le curseur ; les autres sont remplacés par une chaîne vide (sécurité).
  const MARQUEUR_SELECTION = '\u2022';  // •

  function _insererSnippet(snippet) {
    const zone = _modale.querySelector('.ed-latex-zone');
    const debut = zone.selectionStart;
    const fin = zone.selectionEnd;
    const selection = zone.value.substring(debut, fin);
    const avant = zone.value.substring(0, debut);
    const apres = zone.value.substring(fin);

    let texteInsere;
    let posCurseur;
    if (snippet.indexOf(MARQUEUR_SELECTION) >= 0) {
      // ── Snippet avec marqueur • : wrapping de la sélection ──
      const idxMarqueur = snippet.indexOf(MARQUEUR_SELECTION);
      // Remplace le PREMIER • par la sélection, puis nettoie les • suivants
      const avantMarqueur = snippet.substring(0, idxMarqueur);
      const apresMarqueur = snippet.substring(idxMarqueur + 1)
                                   .replace(/\u2022/g, '');
      texteInsere = avantMarqueur + selection + apresMarqueur;
      if (selection.length > 0) {
        // Sélection présente : curseur juste après le texte inséré
        posCurseur = debut + texteInsere.length;
      } else {
        // Pas de sélection : curseur à la place du marqueur (pour taper)
        posCurseur = debut + avantMarqueur.length;
      }
    } else {
      // ── Snippet sans marqueur : comportement classique ──
      // La sélection est ÉCRASÉE par le snippet (cf. décision cadrage Q2 :
      // pour les snippets multi-lignes en particulier, écrasement simple).
      texteInsere = snippet;
      // Repositionne le curseur : si le snippet contient '{}', curseur entre
      // les accolades du premier {} pour faciliter la frappe.
      const posVide = snippet.indexOf('{}');
      if (posVide >= 0) {
        posCurseur = debut + posVide + 1;
      } else {
        posCurseur = debut + snippet.length;
      }
    }

    zone.value = avant + texteInsere + apres;
    zone.setSelectionRange(posCurseur, posCurseur);
    zone.focus();
  }

  // ── Chargement paresseux des données ─────────────────────────────────────

  function _chargerDefinitions(inclureStructurelles) {
    inclureStructurelles = !!inclureStructurelles;
    if (_definitionsPaquet[inclureStructurelles]) {
      return Promise.resolve(_definitionsPaquet[inclureStructurelles]);
    }
    const url = URL_DEFINITIONS
      + (inclureStructurelles ? '?inclure_structurelles=1' : '');
    return fetch(url)
      .then(r => {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(data => { _definitionsPaquet[inclureStructurelles] = data; return data; });
  }

  function _chargerToolbarConfig() {
    if (_toolbarConfig) return Promise.resolve(_toolbarConfig);
    return fetch(URL_TOOLBAR_JSON)
      .then(r => {
        if (!r.ok) {
          // Pas de config = pas grave en Phase 1, on retourne un objet vide.
          return { contextes: {}, groupes: {} };
        }
        return r.json();
      })
      .then(data => { _toolbarConfig = data; return data; })
      .catch(() => ({ contextes: {}, groupes: {} }));
  }

  // ── Configuration des groupes visibles (v0.13.7.2) ───────────────────────

  /**
   * Lit l'état de visibilité des groupes pour un contexte donné depuis
   * localStorage. Retourne un objet { nomGroupe: bool }.
   *
   * Par défaut tous les groupes sont visibles. Les groupes explicitement
   * masqués sont stockés (true = visible, false = caché).
   *
   * Robuste à un localStorage indisponible (mode privé) ou corrompu.
   */
  function _lireVisibilites(contexte, listeGroupes) {
    const cle = LS_PREFIX + contexte;
    let stocke = {};
    try {
      const raw = window.localStorage && window.localStorage.getItem(cle);
      if (raw) stocke = JSON.parse(raw) || {};
    } catch (e) {
      stocke = {};
    }
    // Construit un objet complet : tous les groupes du contexte avec
    // leur visibilité (défaut true).
    const out = {};
    (listeGroupes || []).forEach(g => {
      out[g] = stocke[g] !== false;
    });
    return out;
  }

  function _ecrireVisibilites(contexte, visibilites) {
    const cle = LS_PREFIX + contexte;
    try {
      if (window.localStorage) {
        window.localStorage.setItem(cle, JSON.stringify(visibilites));
      }
    } catch (e) {
      // Mode privé ou quota dépassé : on ignore. La config sera perdue
      // au prochain rechargement, ce n'est pas critique.
    }
  }

  /**
   * Ouvre la mini-modale dans un mode donné.
   * v0.13.7.3 — `type` peut être 'config-groupes', 'qcm', 'liste', 'tableau'.
   * Chaque type configure son propre titre, son aide et son contenu de
   * formulaire. La validation est dispatchée selon le type au moment du
   * clic sur le bouton « Valider » (cf. _validerMiniModale).
   */
  function _ouvrirMiniModale(type) {
    const conf = _modale.querySelector('.ed-latex-conf');
    conf.dataset.type = type;
    const titre = conf.querySelector('.ed-latex-conf-titre');
    const aide = conf.querySelector('.ed-latex-conf-aide');
    const liste = conf.querySelector('.ed-latex-conf-liste');
    const btnReset = conf.querySelector('.ed-latex-conf-reset');
    const btnValider = conf.querySelector('.ed-latex-conf-valider');

    // Réinitialisation visuelle
    btnReset.style.display = 'none';
    btnValider.textContent = 'Valider';

    if (type === 'config-groupes') {
      titre.textContent = 'Groupes d\'outils affichés';
      aide.textContent = 'Décochez pour masquer un groupe dans ce contexte. '
                       + 'La préférence est mémorisée par contexte.';
      btnReset.style.display = '';
      _construireFormulaireConfig(liste);
    } else if (type === 'qcm') {
      titre.textContent = 'Générateur de QCM';
      aide.textContent = 'Génère le squelette d\'un QCM seqQcm avec ses '
                       + 'paramètres. Les questions, le \\midrule séparateur, '
                       + 'le \\\\ de fin de ligne et le \\bottomrule sont '
                       + 'écrits comme attendu par le paquet.';
      btnValider.textContent = 'Insérer le QCM';
      _construireFormulaireQcm(liste);
    } else if (type === 'liste') {
      titre.textContent = 'Générateur de liste';
      aide.textContent = 'Génère une liste avec ses items pré-remplis. '
                       + 'Choisis le type, le nombre d\'items, et '
                       + 'éventuellement une puce personnalisée.';
      btnValider.textContent = 'Insérer la liste';
      _construireFormulaireListe(liste);
    } else if (type === 'image') {
      // v0.13.7.4 — Navigateur d'images depuis data/images/.
      titre.textContent = 'Choisir une image';
      aide.textContent = 'Images du dossier data/images/. Cliquer sur '
                       + 'une image pour insérer \\includegraphics{nom.png}. '
                       + 'Le \\graphicspath du préambule trouvera le fichier.';
      // L'insertion se fait directement au clic sur une image (pas
      // besoin de bouton valider distinct). On masque donc le bouton
      // Valider, on garde Annuler.
      btnValider.style.display = 'none';
      _construireFormulaireImage(liste);
    } else if (type === 'tableau') {
      titre.textContent = 'Générateur de tableau';
      aide.textContent = 'Génère un tableau longtblr (multi-pages auto) '
                       + 'avec ses colonnes X[…]. 1 ligne d\'en-tête vide + '
                       + '2 lignes de corps sont pré-remplies.';
      btnValider.textContent = 'Insérer le tableau';
      _construireFormulaireTableau(liste);
    } else if (type === 'taille') {
      // v0.13.7.5 — Picker de taille de texte. Affiche les 10 commandes
      // standard de LaTeX (\tiny → \Huge) sous forme de tuiles avec un
      // aperçu visuel (« Aa » à la taille correspondante). L'insertion
      // se fait directement au clic (pas de bouton valider).
      titre.textContent = 'Choisir une taille de texte';
      aide.textContent = 'Insère {\\\\taille •} autour de la sélection. '
                       + 'L\'effet s\'arrête à la fin du groupe { }, '
                       + 'donc la portée est limitée au texte sélectionné.';
      btnValider.style.display = 'none';
      _construireFormulaireTaille(liste);
    } else {
      console.warn('[editeur_latex] type de mini-modale inconnu :', type);
      return;
    }

    // Réafficher le bouton valider (a pu être masqué par image / taille)
    if (type !== 'image' && type !== 'taille') btnValider.style.display = '';
    conf.style.display = 'flex';
  }

  function _fermerMiniModale() {
    _modale.querySelector('.ed-latex-conf').style.display = 'none';
  }

  /**
   * Dispatch sur le type courant pour la validation.
   */
  function _validerMiniModale() {
    const conf = _modale.querySelector('.ed-latex-conf');
    const type = conf.dataset.type;
    if (type === 'config-groupes') return _validerConfig();
    if (type === 'qcm')            return _validerQcm();
    if (type === 'liste')          return _validerListe();
    if (type === 'tableau')        return _validerTableau();
    // 'image' et 'taille' n'ont pas de bouton valider visible
    // (insertion directe au clic sur une tuile)
  }

  /**
   * Dispatch sur le type courant pour le bouton « Tout afficher » qui
   * n'existe qu'en mode config-groupes (les autres types n'ont pas de
   * reset). Le bouton est masqué dans les autres modes par _ouvrirMiniModale.
   */
  function _resetMiniModale() {
    const type = _modale.querySelector('.ed-latex-conf').dataset.type;
    if (type === 'config-groupes') return _resetConfig();
  }

  // ── Mode : config-groupes (engrenage v0.13.7.2) ─────────────────────────

  function _construireFormulaireConfig(liste) {
    const contexte = _modale.dataset.contexte;
    _chargerToolbarConfig().then(config => {
      const groupes = (config.contextes && config.contextes[contexte]) || [];
      const visibles = _lireVisibilites(contexte, groupes);
      if (groupes.length === 0) {
        liste.innerHTML = '<p class="ed-latex-placeholder">Aucun groupe défini pour ce contexte.</p>';
      } else {
        liste.innerHTML = groupes.map(nomGroupe => {
          const grp = config.groupes && config.groupes[nomGroupe];
          const label = (grp && grp.label) || nomGroupe;
          const checked = visibles[nomGroupe] !== false ? 'checked' : '';
          return `
            <label class="ed-latex-conf-item">
              <input type="checkbox" data-groupe="${_escapeAttr(nomGroupe)}" ${checked}>
              <span>${_escapeHtml(label)}</span>
            </label>
          `;
        }).join('');
      }
    });
  }

  function _validerConfig() {
    const contexte = _modale.dataset.contexte;
    const visibilites = {};
    _modale.querySelectorAll('.ed-latex-conf-liste input[type=checkbox]')
      .forEach(cb => {
        visibilites[cb.dataset.groupe] = cb.checked;
      });
    _ecrireVisibilites(contexte, visibilites);
    _fermerMiniModale();
    _peuplerOngletOutils(contexte);
  }

  function _resetConfig() {
    _modale.querySelectorAll('.ed-latex-conf-liste input[type=checkbox]')
      .forEach(cb => { cb.checked = true; });
  }

  // ── Mode : générateur QCM (v0.13.7.3) ───────────────────────────────────

  function _construireFormulaireQcm(liste) {
    liste.innerHTML = `
      <div class="ed-latex-gen-champ">
        <label for="gen-qcm-questions">Nombre de questions :</label>
        <input type="number" id="gen-qcm-questions" min="1" max="20" value="3">
      </div>
      <div class="ed-latex-gen-champ">
        <label for="gen-qcm-nbreps">Nombre de réponses (colonnes) :</label>
        <select id="gen-qcm-nbreps">
          <option value="2">2</option>
          <option value="3" selected>3</option>
          <option value="4">4</option>
          <option value="5">5</option>
        </select>
      </div>
      <div class="ed-latex-gen-champ">
        <label for="gen-qcm-explication">Bloc d'explication :</label>
        <select id="gen-qcm-explication">
          <option value="oui">Afficher (texte standard)</option>
          <option value="non" selected>Masquer</option>
        </select>
      </div>
      <details class="ed-latex-gen-details">
        <summary>Scoring (évaluation, optionnel)</summary>
        <p class="ed-latex-gen-aide-mini">
          Affichage en bloc tout-ou-rien : si l'un des trois champs est
          rempli, les trois doivent l'être pour que les règles de scoring
          apparaissent dans le QCM compilé.
        </p>
        <div class="ed-latex-gen-champ">
          <label for="gen-qcm-ptok">Toutes bonnes réponses (ptOK) :</label>
          <input type="text" id="gen-qcm-ptok" placeholder="ex. 1 point">
        </div>
        <div class="ed-latex-gen-champ">
          <label for="gen-qcm-ptpartiel">Partiellement (ptPartiel) :</label>
          <input type="text" id="gen-qcm-ptpartiel" placeholder="ex. 0,5 point">
        </div>
        <div class="ed-latex-gen-champ">
          <label for="gen-qcm-ptko">Au moins une mauvaise (ptKO) :</label>
          <input type="text" id="gen-qcm-ptko" placeholder="ex. 0,5 point">
        </div>
      </details>
    `;
  }

  function _validerQcm() {
    const nbQuestions = parseInt(_modale.querySelector('#gen-qcm-questions').value, 10) || 3;
    const nbReps = parseInt(_modale.querySelector('#gen-qcm-nbreps').value, 10) || 3;
    const explication = _modale.querySelector('#gen-qcm-explication').value;
    const ptOK = _modale.querySelector('#gen-qcm-ptok').value.trim();
    const ptPartiel = _modale.querySelector('#gen-qcm-ptpartiel').value.trim();
    const ptKO = _modale.querySelector('#gen-qcm-ptko').value.trim();

    // Construction des options de \begin{seqQcm}[...]
    // Convention paquet : nbReps + explication toujours présents ; les
    // 3 scoring uniquement si TOUS remplis (logique tout-ou-rien côté .dtx).
    const opts = [`nbReps=${nbReps}`, `explication=${explication}`];
    if (ptOK && ptPartiel && ptKO) {
      opts.push(`ptOK=${ptOK}`);
      opts.push(`ptPartiel=${ptPartiel}`);
      opts.push(`ptKO=${ptKO}`);
    }
    // Note : si l'utilisateur a rempli 1 ou 2 champs scoring sur 3, on
    // les ignore silencieusement (cohérent avec le comportement du paquet).

    // Construction du corps : une ligne par question, séparées par \midrule.
    // Chaque ligne : \seqQcmQuestion{} & ... & ... \\
    // (le nombre de cellules de réponse = nbReps)
    const cellules = Array(nbReps).fill('').join(' & ');
    const lignes = [];
    for (let i = 0; i < nbQuestions; i++) {
      lignes.push(`    \\midrule \\seqQcmQuestion{} & ${cellules} \\\\`);
    }
    lignes.push('            \\bottomrule');

    const snippet =
      `\\begin{seqQcm}[${opts.join(',')}]\n`
      + lignes.join('\n') + '\n'
      + `\\end{seqQcm}`;

    _fermerMiniModale();
    _insererSnippet(snippet);
  }

  // ── Mode : générateur Liste (v0.13.7.3) ─────────────────────────────────

  // Palette \ding utile (8 codes pédagogiquement les plus courants)
  // Visuel approximé via les caractères Unicode équivalents — vrai rendu
  // au moment de la compilation LaTeX via le paquet pifont.
  const DING_PALETTE = [
    {code: 52,  apercu: '✔', label: 'Coche pleine'},
    {code: 51,  apercu: '✓', label: 'Coche légère'},
    {code: 56,  apercu: '✘', label: 'Croix pleine'},
    {code: 55,  apercu: '✗', label: 'Croix légère'},
    {code: 43,  apercu: '✏', label: 'Crayon'},
    {code: 234, apercu: '→', label: 'Flèche droite'},
    {code: 110, apercu: '▪', label: 'Carré plein'},
    {code: 192, apercu: '●', label: 'Disque'}
  ];

  function _construireFormulaireListe(liste) {
    const ding = DING_PALETTE.map(d => `
      <label class="ed-latex-gen-ding" title="${_escapeAttr(d.label)} (\\ding{${d.code}})">
        <input type="radio" name="gen-liste-ding" value="${d.code}">
        <span class="ed-latex-gen-ding-apercu">${_escapeHtml(d.apercu)}</span>
        <span class="ed-latex-gen-ding-code">${d.code}</span>
      </label>
    `).join('');

    liste.innerHTML = `
      <div class="ed-latex-gen-champ">
        <label for="gen-liste-type">Type de liste :</label>
        <select id="gen-liste-type">
          <option value="itemize">À puces (itemize)</option>
          <option value="enumerate">Numérotée (enumerate)</option>
          <option value="seqColItem">À puces, multi-colonnes (seqColItem)</option>
          <option value="seqColEnum">Numérotée, multi-colonnes (seqColEnum)</option>
        </select>
      </div>
      <div class="ed-latex-gen-champ">
        <label for="gen-liste-items">Nombre d'items :</label>
        <input type="number" id="gen-liste-items" min="1" max="20" value="3">
      </div>
      <div class="ed-latex-gen-champ ed-latex-gen-champ-cols" style="display:none">
        <label for="gen-liste-cols">Nombre de colonnes :</label>
        <input type="number" id="gen-liste-cols" min="2" max="4" value="2">
      </div>
      <div class="ed-latex-gen-champ">
        <label>Puce personnalisée (optionnelle) :</label>
        <div class="ed-latex-gen-ding-palette">
          <label class="ed-latex-gen-ding" title="Aucune puce personnalisée">
            <input type="radio" name="gen-liste-ding" value="" checked>
            <span class="ed-latex-gen-ding-apercu">∅</span>
            <span class="ed-latex-gen-ding-code">défaut</span>
          </label>
          ${ding}
          <label class="ed-latex-gen-ding ed-latex-gen-ding-libre">
            <input type="radio" name="gen-liste-ding" value="__libre__">
            <span class="ed-latex-gen-ding-apercu">N°</span>
            <input type="number" id="gen-liste-ding-libre" min="0" max="255"
                   placeholder="code"
                   class="ed-latex-gen-ding-input"
                   onfocus="this.parentNode.querySelector('input[type=radio]').checked=true">
          </label>
        </div>
      </div>
    `;

    // Afficher/masquer le champ "colonnes" selon le type sélectionné
    const selType = liste.querySelector('#gen-liste-type');
    const champCols = liste.querySelector('.ed-latex-gen-champ-cols');
    const ajusterCols = () => {
      const t = selType.value;
      champCols.style.display = (t === 'seqColItem' || t === 'seqColEnum') ? '' : 'none';
    };
    selType.onchange = ajusterCols;
    ajusterCols();
  }

  function _validerListe() {
    const type = _modale.querySelector('#gen-liste-type').value;
    const nbItems = parseInt(_modale.querySelector('#gen-liste-items').value, 10) || 3;
    const cols = parseInt(_modale.querySelector('#gen-liste-cols').value, 10) || 2;
    const dingRadio = _modale.querySelector('input[name=gen-liste-ding]:checked');
    let dingCode = '';
    if (dingRadio) {
      if (dingRadio.value === '__libre__') {
        dingCode = (_modale.querySelector('#gen-liste-ding-libre').value || '').trim();
      } else {
        dingCode = dingRadio.value;
      }
    }

    // Construction de l'option [label=\ding{N}] si applicable.
    // - itemize : option [label=\ding{N}]
    // - enumerate : option [label=\ding{N}] (rare mais possible)
    // - seqColItem/seqColEnum : option [nbCols=N] + label=\ding{N} si applicable
    const opts = [];
    if (type === 'seqColItem' || type === 'seqColEnum') {
      opts.push(`nbCols=${cols}`);
    }
    if (dingCode) {
      opts.push(`label=\\ding{${dingCode}}`);
    }
    const optsStr = opts.length > 0 ? `[${opts.join(',')}]` : '';

    // Construction des \item
    const items = [];
    for (let i = 0; i < nbItems; i++) {
      items.push('  \\item ');
    }

    const snippet =
      `\\begin{${type}}${optsStr}\n`
      + items.join('\n') + '\n'
      + `\\end{${type}}`;

    _fermerMiniModale();
    _insererSnippet(snippet);
  }

  // ── Mode : générateur Tableau (v0.13.7.5) ───────────────────────────────
  //
  // Génère un environnement longtblr avec :
  //  - colspec construit dynamiquement depuis les alignements et ratios
  //    de chaque colonne (1 à 6 colonnes)
  //  - rowspec=… absent (lignes auto)
  //  - hlines / vlines optionnels (par défaut tous les deux cochés)
  //  - 1 ligne d'en-tête vide + 2 lignes de corps vides (cf. cadrage)
  //
  // Pas de caption / label : l'enseignant les ajoute après coup s'il
  // en a besoin (cf. cadrage v0.13.7.5).
  //
  // Bouton « ⚡ Aide tabularray » : ouvre une zone d'aide dépliée
  // dans la même modale avec des extraits du guide tabularray pour
  // personnaliser hlines/vlines (couleur, épaisseur, filets sélectifs).

  const TABLEAU_NB_COL_MIN = 1;
  const TABLEAU_NB_COL_MAX = 6;
  const TABLEAU_NB_COL_DEFAUT = 3;
  const TABLEAU_RATIO_MIN = 1;
  const TABLEAU_RATIO_MAX = 4;
  const TABLEAU_RATIO_DEFAUT = 1;

  function _construireFormulaireTableau(liste) {
    liste.innerHTML = `
      <div class="ed-latex-gen-champ">
        <label for="gen-tab-nbcols">Nombre de colonnes :</label>
        <input type="number" id="gen-tab-nbcols"
               min="${TABLEAU_NB_COL_MIN}" max="${TABLEAU_NB_COL_MAX}"
               value="${TABLEAU_NB_COL_DEFAUT}">
      </div>
      <div class="ed-latex-gen-champ">
        <label>Colonnes — alignement et largeur relative (×1 à ×4) :</label>
        <div class="ed-latex-tab-colonnes"></div>
      </div>
      <div class="ed-latex-gen-champ ed-latex-tab-filets">
        <label class="ed-latex-tab-filet-cb">
          <input type="checkbox" id="gen-tab-hlines" checked>
          <span>Filets horizontaux (<code>hlines</code>)</span>
        </label>
        <label class="ed-latex-tab-filet-cb">
          <input type="checkbox" id="gen-tab-vlines" checked>
          <span>Filets verticaux (<code>vlines</code>)</span>
        </label>
      </div>
      <div class="ed-latex-gen-champ">
        <button type="button" class="ed-latex-tab-aide-btn" aria-expanded="false">
          ⚡ Aide tabularray (personnaliser hlines / vlines)
        </button>
        <div class="ed-latex-tab-aide" hidden></div>
      </div>
    `;

    const champNbCols = liste.querySelector('#gen-tab-nbcols');
    const conteneurCols = liste.querySelector('.ed-latex-tab-colonnes');
    const _rendrePanneauCols = () => {
      // Préserve les choix existants (alignement et ratio) lors d'un
      // changement du nombre de colonnes — sauf si on déborde, auquel
      // cas on initialise les nouvelles colonnes à (c, 1).
      const ancien = _lireConfigColonnes(conteneurCols);
      let n = parseInt(champNbCols.value, 10);
      if (!Number.isFinite(n)) n = TABLEAU_NB_COL_DEFAUT;
      n = Math.max(TABLEAU_NB_COL_MIN, Math.min(TABLEAU_NB_COL_MAX, n));
      champNbCols.value = String(n);
      conteneurCols.innerHTML = '';
      for (let i = 0; i < n; i++) {
        const a = (ancien[i] && ancien[i].align) || 'c';
        const r = (ancien[i] && ancien[i].ratio) || TABLEAU_RATIO_DEFAUT;
        conteneurCols.appendChild(_construireLigneColonne(i + 1, a, r));
      }
    };
    champNbCols.oninput = _rendrePanneauCols;
    _rendrePanneauCols();

    // Aide tabularray dépliable
    const btnAide = liste.querySelector('.ed-latex-tab-aide-btn');
    const zoneAide = liste.querySelector('.ed-latex-tab-aide');
    btnAide.onclick = () => {
      const ouvert = !zoneAide.hidden;
      if (ouvert) {
        zoneAide.hidden = true;
        btnAide.setAttribute('aria-expanded', 'false');
      } else {
        if (!zoneAide._peuple) {
          zoneAide.innerHTML = _htmlAideTabularray();
          zoneAide._peuple = true;
        }
        zoneAide.hidden = false;
        btnAide.setAttribute('aria-expanded', 'true');
      }
    };
  }

  /**
   * Construit une ligne de contrôles pour une colonne (3 boutons radio
   * d'alignement + un slider de ratio 1–4 + un affichage de la valeur).
   * Retourne un élément DOM prêt à être inséré.
   *
   * v0.13.7.6 — Ajout d'un label « Largeur : » devant le slider (sans
   * lui, le contrôle n'était pas découvrable selon le retour utilisateur).
   * Le slider lui-même est stylisé via CSS (rail bleu, poignée ronde)
   * pour rester visible quel que soit le thème du navigateur.
   */
  function _construireLigneColonne(num, alignDefaut, ratioDefaut) {
    const div = document.createElement('div');
    div.className = 'ed-latex-tab-colonne';
    div.dataset.numero = String(num);
    div.innerHTML = `
      <span class="ed-latex-tab-colonne-num">Col. ${num}</span>
      <span class="ed-latex-tab-colonne-aligns">
        <label class="ed-latex-tab-align" title="Aligné à gauche">
          <input type="radio" name="gen-tab-align-${num}" value="l" ${alignDefaut === 'l' ? 'checked' : ''}>
          <span class="ed-latex-tab-align-pict">${_htmlIconeSvg('left')}</span>
        </label>
        <label class="ed-latex-tab-align" title="Centré">
          <input type="radio" name="gen-tab-align-${num}" value="c" ${alignDefaut === 'c' ? 'checked' : ''}>
          <span class="ed-latex-tab-align-pict">${_htmlIconeSvg('center')}</span>
        </label>
        <label class="ed-latex-tab-align" title="Aligné à droite">
          <input type="radio" name="gen-tab-align-${num}" value="r" ${alignDefaut === 'r' ? 'checked' : ''}>
          <span class="ed-latex-tab-align-pict">${_htmlIconeSvg('right')}</span>
        </label>
      </span>
      <span class="ed-latex-tab-colonne-largeur-label">Largeur :</span>
      <span class="ed-latex-tab-colonne-ratio">
        <button type="button" class="ed-latex-tab-stepper-btn"
                data-direction="-1"
                title="Diminuer la largeur (×1 minimum)">−</button>
        <span class="ed-latex-tab-ratio-valeur"
              data-ratio="${ratioDefaut}">×${ratioDefaut}</span>
        <button type="button" class="ed-latex-tab-stepper-btn"
                data-direction="1"
                title="Augmenter la largeur (×4 maximum)">+</button>
      </span>
    `;
    // v0.13.7.6.1 — Stepper [−] ×N [+] à la place du slider natif.
    // Le slider <input type=range> était invisible sur certains
    // navigateurs/thèmes (notamment Firefox sur PC pro Windows), même
    // avec un style explicite des pseudo-éléments webkit/moz. Le
    // stepper bouton+bouton est rendu de manière fiable partout.
    const aff = div.querySelector('.ed-latex-tab-ratio-valeur');
    div.querySelectorAll('.ed-latex-tab-stepper-btn').forEach(btn => {
      btn.onclick = () => {
        const direction = parseInt(btn.dataset.direction, 10);
        const courant = parseInt(aff.dataset.ratio, 10) || TABLEAU_RATIO_DEFAUT;
        let nouveau = courant + direction;
        if (nouveau < TABLEAU_RATIO_MIN) nouveau = TABLEAU_RATIO_MIN;
        if (nouveau > TABLEAU_RATIO_MAX) nouveau = TABLEAU_RATIO_MAX;
        aff.dataset.ratio = String(nouveau);
        aff.textContent = '×' + nouveau;
      };
    });
    return div;
  }

  /**
   * Lit l'état courant des colonnes depuis le DOM du formulaire tableau.
   * Retourne un tableau d'objets {align, ratio}.
   *
   * Robuste à une lecture partielle (utilisée pendant le _rendrePanneauCols
   * pour préserver les choix lors d'un changement de nb de colonnes).
   *
   * v0.13.7.6.1 — Lit le ratio depuis dataset.ratio du <span> d'affichage
   * (le slider a été remplacé par un stepper [−] ×N [+]).
   */
  function _lireConfigColonnes(conteneur) {
    const res = [];
    if (!conteneur) return res;
    conteneur.querySelectorAll('.ed-latex-tab-colonne').forEach(col => {
      const num = parseInt(col.dataset.numero, 10);
      const alignInput = col.querySelector('input[type=radio]:checked');
      const aff = col.querySelector('.ed-latex-tab-ratio-valeur');
      const ratio = aff ? parseInt(aff.dataset.ratio, 10) : TABLEAU_RATIO_DEFAUT;
      res[num - 1] = {
        align: alignInput ? alignInput.value : 'c',
        ratio: Number.isFinite(ratio) ? ratio : TABLEAU_RATIO_DEFAUT,
      };
    });
    return res;
  }

  /**
   * Renvoie le HTML d'aide tabularray pliable. Contenu volontairement
   * compact : on cite les usages les plus utiles dans le contexte
   * pédagogique cycle 4, pas la doc exhaustive.
   */
  function _htmlAideTabularray() {
    return `
      <p class="ed-latex-tab-aide-intro">
        Une fois le tableau inséré, on peut personnaliser
        <code>hlines</code> et <code>vlines</code> dans la zone
        <code>{…}</code> du <code>\\begin{longtblr}</code>.
      </p>
      <table class="ed-latex-tab-aide-table">
        <thead>
          <tr><th>Effet</th><th>Syntaxe</th></tr>
        </thead>
        <tbody>
          <tr>
            <td>Tous les filets, fins</td>
            <td><code>hlines, vlines</code></td>
          </tr>
          <tr>
            <td>Tous les filets, épais</td>
            <td><code>hlines={1pt}, vlines={1pt}</code></td>
          </tr>
          <tr>
            <td>Filets de couleur</td>
            <td><code>hlines={red}, vlines={blue!50}</code></td>
          </tr>
          <tr>
            <td>Seulement la 1re ligne (en-tête)</td>
            <td><code>hline{2}</code> (filet sous la ligne 1)</td>
          </tr>
          <tr>
            <td>Filets autour de la 2e colonne</td>
            <td><code>vline{2,3}</code></td>
          </tr>
          <tr>
            <td>Filet épais haut + bas, fin au milieu</td>
            <td><code>hline{1,Z}={1pt}, hlines={0.4pt}</code></td>
          </tr>
        </tbody>
      </table>
      <p class="ed-latex-tab-aide-fin">
        <code>Z</code> = dernière ligne. On peut aussi remplacer
        <code>X[c]</code> par <code>X[c,m]</code> pour centrer
        verticalement, ou par <code>l</code>/<code>c</code>/<code>r</code>
        (sans <code>X</code>) pour des colonnes à largeur naturelle.
      </p>
    `;
  }

  function _validerTableau() {
    const conteneurCols = _modale.querySelector('.ed-latex-tab-colonnes');
    const colonnes = _lireConfigColonnes(conteneurCols);
    const nb = colonnes.length;
    if (nb === 0) return;  // garde-fou
    const hlines = _modale.querySelector('#gen-tab-hlines').checked;
    const vlines = _modale.querySelector('#gen-tab-vlines').checked;
    const snippet = _genererSnippetTableau(colonnes, hlines, vlines);
    _fermerMiniModale();
    _insererSnippet(snippet);
  }

  /**
   * Génère le snippet LaTeX longtblr depuis la config colonnes + filets.
   *
   *   _genererSnippetTableau(
   *     [{align:'c', ratio:1}, {align:'r', ratio:2}],
   *     true, false)
   *   →
   *     \begin{longtblr}{
   *       colspec={X[c] X[r,2]},
   *       hlines,
   *     }
   *      &  \\
   *      &  \\
   *      &  \\
   *     \end{longtblr}
   *
   * Convention : si ratio = 1, on n'écrit pas le ratio (X[c] et non
   * X[c,1]) — c'est l'écriture canonique de tabularray.
   * On génère 3 lignes vides : 1 en-tête + 2 corps (cf. cadrage).
   */
  function _genererSnippetTableau(colonnes, hlines, vlines) {
    const specs = colonnes.map(c => {
      const a = (c.align === 'l' || c.align === 'r') ? c.align : 'c';
      const r = parseInt(c.ratio, 10);
      if (!Number.isFinite(r) || r <= 1) return 'X[' + a + ']';
      return 'X[' + a + ',' + r + ']';
    });
    const lignesOpts = ['  colspec={' + specs.join(' ') + '},'];
    if (hlines) lignesOpts.push('  hlines,');
    if (vlines) lignesOpts.push('  vlines,');

    const nb = colonnes.length;
    const cellules = Array(nb).fill(' ').join('&');
    const lignesCorps = [
      '  ' + cellules + ' \\\\',  // en-tête
      '  ' + cellules + ' \\\\',  // ligne corps 1
      '  ' + cellules + ' \\\\'   // ligne corps 2
    ];

    return '\\begin{longtblr}{\n'
         + lignesOpts.join('\n') + '\n'
         + '}\n'
         + lignesCorps.join('\n') + '\n'
         + '\\end{longtblr}';
  }

  // ── Mode : picker de Taille (v0.13.7.5) ─────────────────────────────────
  //
  // Affiche les 10 commandes standard de taille LaTeX sous forme de
  // tuiles avec aperçu visuel (« Aa » à la taille correspondante).
  // L'insertion se fait au clic sur une tuile : le snippet « {\X •} »
  // entoure la sélection. Pas de \par à la fin : la portée reste limitée
  // au groupe { } courant et la commande marche aussi en inline.

  // Liste de référence des tailles LaTeX, ordonnée du plus petit au plus
  // grand. Chaque entrée :
  //   - cmd     : nom de la commande LaTeX (sans backslash)
  //   - pct     : taille relative pour l'aperçu CSS (% de la taille de base)
  //   - libelle : texte de la légende sous l'aperçu
  const TAILLES_LATEX = [
    {cmd: 'tiny',         pct: 50,  libelle: 'tiny'},
    {cmd: 'scriptsize',   pct: 60,  libelle: 'scriptsize'},
    {cmd: 'footnotesize', pct: 70,  libelle: 'footnotesize'},
    {cmd: 'small',        pct: 85,  libelle: 'small'},
    {cmd: 'normalsize',   pct: 100, libelle: 'normalsize'},
    {cmd: 'large',        pct: 115, libelle: 'large'},
    {cmd: 'Large',        pct: 130, libelle: 'Large'},
    {cmd: 'LARGE',        pct: 150, libelle: 'LARGE'},
    {cmd: 'huge',         pct: 175, libelle: 'huge'},
    {cmd: 'Huge',         pct: 200, libelle: 'Huge'}
  ];

  function _construireFormulaireTaille(liste) {
    const tuiles = TAILLES_LATEX.map(t => `
      <button type="button" class="ed-latex-taille-tuile"
              data-cmd="${t.cmd}"
              title="Insère {\\${t.cmd} sélection} (entoure la sélection)">
        <span class="ed-latex-taille-apercu"
              style="font-size:${t.pct}%">Aa</span>
        <span class="ed-latex-taille-cmd">\\${t.cmd}</span>
      </button>
    `).join('');

    liste.innerHTML = '<div class="ed-latex-taille-grille">' + tuiles + '</div>';

    liste.querySelectorAll('.ed-latex-taille-tuile').forEach(btn => {
      btn.onclick = () => {
        const cmd = btn.dataset.cmd;
        _fermerMiniModale();
        // Convention : {\cmd •} — • marque la position de la sélection.
        // Pas de \par à la fin pour que la commande puisse aussi
        // s'utiliser en inline (changement de taille au milieu d'un
        // paragraphe).
        _insererSnippet('{\\' + cmd + ' •}');
      };
    });
  }

  // ── Mode : navigateur d'images (v0.13.7.4) ──────────────────────────────

  // Cache JS de la liste d'images (rechargée à chaque ouverture si null).
  // Invalidé en cas d'erreur. Pas de TTL : si Laurent ajoute une image
  // pendant la session, il devra fermer/rouvrir l'éditeur pour la voir.
  // Acceptable : c'est un usage hors ligne, pas un service partagé.
  let _imagesCache = null;

  // Préférence d'affichage : 'liste' (défaut, rapide) ou 'grille' (miniatures).
  // Persisté en localStorage, globale (pas par contexte).
  const LS_VUE_IMAGES = 'ed-latex:images-vue';

  function _lireVueImagesPref() {
    try {
      if (window.localStorage) {
        const v = window.localStorage.getItem(LS_VUE_IMAGES);
        if (v === 'grille' || v === 'liste') return v;
      }
    } catch (e) { /* ignore */ }
    return 'liste';
  }
  function _ecrireVueImagesPref(v) {
    try {
      if (window.localStorage) {
        window.localStorage.setItem(LS_VUE_IMAGES, v);
      }
    } catch (e) { /* ignore */ }
  }

  function _construireFormulaireImage(liste) {
    // Pendant le chargement, on affiche un placeholder ; une fois la
    // liste reçue, on render selon la préférence (liste ou grille).
    liste.innerHTML = '<p class="ed-latex-placeholder">Chargement des images…</p>';

    const fetcher = _imagesCache
      ? Promise.resolve(_imagesCache)
      : fetch('/api/images').then(r => {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.json();
        }).then(data => {
          _imagesCache = data;
          return data;
        });

    fetcher.then(data => {
      const images = (data && data.images) || [];
      if (images.length === 0) {
        liste.innerHTML = `
          <p class="ed-latex-placeholder">
            Aucune image dans <code>data/images/</code>.
            Importer des images via l'onglet Admin avant d'utiliser ce navigateur.
          </p>
        `;
        return;
      }

      const vue = _lireVueImagesPref();
      liste.innerHTML = `
        <div class="ed-latex-img-toolbar">
          <input type="search" class="ed-latex-img-recherche"
                 placeholder="Filtrer par nom…">
          <div class="ed-latex-img-vue-btns">
            <button type="button" class="ed-latex-img-vue-btn${vue === 'liste' ? ' ed-latex-img-vue-btn--actif' : ''}"
                    data-vue="liste" title="Affichage en liste">☰ Liste</button>
            <button type="button" class="ed-latex-img-vue-btn${vue === 'grille' ? ' ed-latex-img-vue-btn--actif' : ''}"
                    data-vue="grille" title="Affichage en grille avec miniatures">⊞ Grille</button>
          </div>
          <span class="ed-latex-img-compteur">${images.length} image${images.length > 1 ? 's' : ''}</span>
        </div>
        <div class="ed-latex-img-contenu" data-vue="${vue}"></div>
      `;
      _rendreContenuImages(liste, images, vue);

      // Recherche live
      const recherche = liste.querySelector('.ed-latex-img-recherche');
      recherche.oninput = () => {
        const terme = recherche.value.trim().toLowerCase();
        const filtre = terme
          ? images.filter(i => i.nom.toLowerCase().includes(terme))
          : images;
        const vueCourante = liste.querySelector('.ed-latex-img-contenu').dataset.vue;
        _rendreContenuImages(liste, filtre, vueCourante);
      };

      // Bascule liste/grille
      liste.querySelectorAll('.ed-latex-img-vue-btn').forEach(btn => {
        btn.onclick = () => {
          const nouvelleVue = btn.dataset.vue;
          _ecrireVueImagesPref(nouvelleVue);
          liste.querySelectorAll('.ed-latex-img-vue-btn').forEach(b => {
            b.classList.toggle('ed-latex-img-vue-btn--actif', b.dataset.vue === nouvelleVue);
          });
          const contenu = liste.querySelector('.ed-latex-img-contenu');
          contenu.dataset.vue = nouvelleVue;
          // Recalcule selon le filtre courant
          const terme = recherche.value.trim().toLowerCase();
          const filtre = terme
            ? images.filter(i => i.nom.toLowerCase().includes(terme))
            : images;
          _rendreContenuImages(liste, filtre, nouvelleVue);
        };
      });
    }).catch(err => {
      liste.innerHTML = `<p class="ed-latex-erreur">Erreur de chargement des images : ${_escapeHtml(err.message || String(err))}</p>`;
    });
  }

  /**
   * Rend le contenu (liste ou grille) dans le conteneur dédié.
   * `images` est déjà filtré par la recherche le cas échéant.
   */
  function _rendreContenuImages(panneau, images, vue) {
    const contenu = panneau.querySelector('.ed-latex-img-contenu');
    if (!contenu) return;
    if (images.length === 0) {
      contenu.innerHTML = '<p class="ed-latex-placeholder">Aucune image ne correspond.</p>';
      return;
    }
    if (vue === 'grille') {
      contenu.innerHTML = images.map(img => `
        <button type="button" class="ed-latex-img-vignette"
                data-nom="${_escapeAttr(img.nom)}"
                title="${_escapeAttr(img.nom)} (${_formaterTaille(img.taille)})">
          <img src="/api/images/preview/${encodeURIComponent(img.nom)}"
               alt="${_escapeAttr(img.nom)}"
               loading="lazy">
          <span class="ed-latex-img-vignette-nom">${_escapeHtml(img.nom)}</span>
        </button>
      `).join('');
    } else {
      // Vue liste
      contenu.innerHTML = images.map(img => `
        <button type="button" class="ed-latex-img-ligne"
                data-nom="${_escapeAttr(img.nom)}"
                title="Cliquer pour insérer \\includegraphics{${_escapeAttr(img.nom)}}">
          <span class="ed-latex-img-ligne-nom">${_escapeHtml(img.nom)}</span>
          <span class="ed-latex-img-ligne-taille">${_formaterTaille(img.taille)}</span>
        </button>
      `).join('');
    }
    contenu.querySelectorAll('[data-nom]').forEach(btn => {
      btn.onclick = () => _validerImage(btn.dataset.nom);
    });
  }

  function _validerImage(nom) {
    // Insertion brute : \includegraphics{nom.png} (sans options, cf. cadrage Q3).
    // Le \graphicspath du préambule de seqenseigne se charge de retrouver le fichier.
    const snippet = `\\includegraphics{${nom}}`;
    _fermerMiniModale();
    _insererSnippet(snippet);
  }

  function _formaterTaille(octets) {
    if (octets < 1024) return `${octets} o`;
    if (octets < 1024 * 1024) return `${(octets / 1024).toFixed(0)} ko`;
    return `${(octets / 1024 / 1024).toFixed(1)} Mo`;
  }

  // ── Helpers utilitaires ──────────────────────────────────────────────────

  function _escapeHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function _escapeAttr(s) {
    return String(s || '')
      .replace(/&/g, '&amp;').replace(/"/g, '&quot;')
      .replace(/\n/g, '&#10;');
  }

  // ── Auto-scan au démarrage ───────────────────────────────────────────────

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => scan());
  } else {
    scan();
  }

  // ── API publique ─────────────────────────────────────────────────────────

  window.EditeurLatex = { scan, ouvrir };

})();
