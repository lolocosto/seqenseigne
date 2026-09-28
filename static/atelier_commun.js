/**
 * static/atelier_commun.js — utilitaires UX partagés par les 3 ateliers (v0.6.4).
 *
 * Fonctionnalités :
 *
 *   1. atelierAfficherLatex(type, contenu)
 *      Ouvre une modale qui affiche le LaTeX généré pour un atome.
 *      Une seule modale dans le DOM, créée à la 1re demande puis réutilisée.
 *
 *   2. atelierAutosizeTextarea(textarea)
 *      Active la croissance automatique de hauteur d'un <textarea> en fonction
 *      de son contenu. Idempotent : un appel multiple ne pose pas de problème
 *      (l'écouteur 'input' est posé une seule fois).
 *      v0.9.3 : skippe les textareas avec la classe `latex-textarea`,
 *      pris en charge par atelierFixerHauteurLatex.
 *
 *   3. atelierAutosizeTous(racine)
 *      Active l'autosize sur tous les <textarea> contenus dans `racine`
 *      (par défaut : document.body). À appeler après chaque rendu d'écran
 *      qui ajoute des textareas au DOM.
 *
 *   4. atelierFixerHauteurLatex(textarea, lignes)  — v0.9.3
 *      Hauteur fixe + scroll pour un textarea LaTeX. Remplace l'autosize
 *      sur les zones de saisie volumineuses (variables, énoncé, corrigé,
 *      corps notion/méthode, items de section).
 *
 *   5. atelierFixerHauteurLatexTous(racine, lignes)  — v0.9.3
 *      Idem pour tous les textareas `.latex-textarea` dans `racine`.
 *
 *   6. Hook Tab/Shift+Tab pour les textareas LaTeX (v0.9.3, automatique)
 *      Tab insère 2 espaces ; Shift+Tab désindente. Permet d'indenter
 *      du LaTeX sans que la touche Tab navigue au champ suivant.
 *      Esc puis Tab préserve la navigation HTML standard pour
 *      l'accessibilité clavier. Posé sur document via délégation —
 *      fonctionne sur les textareas dynamiquement ajoutés.
 *
 * Conventions :
 *   - Pas d'import — chargé via <script src> dans index.html avant app.js.
 *   - Aucune dépendance à d'autres fichiers JS.
 *   - Expose ses fonctions via `window.*`.
 *   - Suit le pattern existant (closure IIFE pour les helpers privés).
 */
(function () {
  'use strict';

  // ── 1. Modale LaTeX ────────────────────────────────────────────────────────
  //
  // Une seule modale est insérée dans le DOM au 1er appel. Les appels suivants
  // réutilisent les mêmes éléments en mettant à jour leur contenu.

  let _modale = null;       // élément racine de la modale (créé paresseusement)
  let _preLatex = null;     // <pre> qui contient le code à afficher
  let _titreModale = null;  // <h3> en tête

  function _creerModale() {
    const overlay = document.createElement('div');
    overlay.className = 'atelier-modale-overlay';
    overlay.style.display = 'none';
    // Fermeture en cliquant sur le fond (pas sur le contenu)
    overlay.addEventListener('click', (ev) => {
      if (ev.target === overlay) _fermerModale();
    });

    const boite = document.createElement('div');
    boite.className = 'atelier-modale';
    overlay.appendChild(boite);

    const entete = document.createElement('div');
    entete.className = 'atelier-modale-entete';
    boite.appendChild(entete);

    const titre = document.createElement('h3');
    titre.textContent = 'LaTeX généré';
    entete.appendChild(titre);

    const actions = document.createElement('div');
    actions.className = 'atelier-modale-actions';
    entete.appendChild(actions);

    const btnCopier = document.createElement('button');
    btnCopier.className = 'btn-sm';
    btnCopier.textContent = 'Copier';
    btnCopier.addEventListener('click', () => {
      navigator.clipboard.writeText(_preLatex.textContent).then(() => {
        btnCopier.textContent = 'Copié ✓';
        setTimeout(() => { btnCopier.textContent = 'Copier'; }, 1500);
      });
    });
    actions.appendChild(btnCopier);

    const btnFermer = document.createElement('button');
    btnFermer.className = 'btn-sm';
    btnFermer.textContent = 'Fermer';
    btnFermer.addEventListener('click', _fermerModale);
    actions.appendChild(btnFermer);

    const corps = document.createElement('div');
    corps.className = 'atelier-modale-corps';
    boite.appendChild(corps);

    const pre = document.createElement('pre');
    pre.className = 'atelier-modale-pre';
    corps.appendChild(pre);

    document.body.appendChild(overlay);

    // Échap pour fermer
    document.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape' && _modale && _modale.style.display !== 'none') {
        _fermerModale();
      }
    });

    _modale = overlay;
    _preLatex = pre;
    _titreModale = titre;
  }

  function _fermerModale() {
    if (_modale) _modale.style.display = 'none';
  }

  /**
   * Ouvre la modale et y affiche le LaTeX généré pour un atome.
   * @param {string} type    — 'exercice', 'notion' ou 'methode' (libellé du titre)
   * @param {string} contenu — code LaTeX à afficher
   */
  function atelierAfficherLatex(type, contenu) {
    if (!_modale) _creerModale();
    const libelle = {
      exercice:          'Exercice',
      notion:            'Notion',
      methode:           'Méthode',
      fiche:             'Fiche de résumé',
      evaluation:        'Évaluation',
      carte_automatisme: "Carte d'automatisme",
      livret_sequence:   'Livret de séquence',
    }[type] || 'Atome';
    _titreModale.textContent = `LaTeX généré — ${libelle}`;
    _preLatex.textContent = contenu || '(vide)';
    _modale.style.display = 'flex';
  }

  // ── 2. Autosize textarea ───────────────────────────────────────────────────
  //
  // Stratégie : à chaque modification, on remet la hauteur à 'auto' pour que
  // le navigateur recalcule scrollHeight, puis on cale la hauteur sur ce
  // scrollHeight (avec un mini pour préserver une zone confortable).
  //
  // L'écouteur 'input' n'est posé qu'UNE seule fois par textarea — un drapeau
  // dataset.atelierAutosize signale qu'un textarea a déjà été équipé.

  const _MIN_HAUTEUR_PX = 60;     // ~3 lignes : laisse une zone confortable
  const _MARGE_PX = 2;            // marge pour éviter une scrollbar parasite

  function _ajusterHauteur(ta) {
    // 'auto' force un reflow qui réinitialise scrollHeight
    ta.style.height = 'auto';
    const cible = Math.max(_MIN_HAUTEUR_PX, ta.scrollHeight + _MARGE_PX);
    ta.style.height = cible + 'px';
  }

  /**
   * Active l'autosize sur un textarea. Idempotent.
   *
   * v0.9.3 — Si le textarea porte la classe `latex-textarea`, on skippe :
   * ces textareas reçoivent une hauteur fixe paramétrée par
   * `atl_textarea_lignes` (cf. atelierFixerHauteurLatex). L'autosize est
   * pénible quand on saisit du LaTeX en volume car la zone grandit avec
   * le contenu et fait défiler tout le formulaire à chaque saut de ligne.
   *
   * @param {HTMLTextAreaElement} ta
   */
  function atelierAutosizeTextarea(ta) {
    if (!ta || ta.dataset.atelierAutosize === '1') return;
    if (ta.classList && ta.classList.contains('latex-textarea')) return;
    ta.dataset.atelierAutosize = '1';
    // overflow-y caché évite la scrollbar inutile (la hauteur s'adapte)
    ta.style.overflowY = 'hidden';
    // Resize CSS désactivé : c'est nous qui pilotons la hauteur
    ta.style.resize = 'none';
    _ajusterHauteur(ta);
    ta.addEventListener('input', () => _ajusterHauteur(ta));
  }

  /**
   * v0.9.3 — Fixe la hauteur d'un textarea LaTeX en lignes (rows).
   * Idempotent : reposer cette fonction met à jour la hauteur si la
   * config a changé.
   *
   * @param {HTMLTextAreaElement} ta
   * @param {number} lignes - nombre de lignes (rows HTML)
   */
  function atelierFixerHauteurLatex(ta, lignes) {
    if (!ta) return;
    ta.rows = lignes;
    // overflow-y auto : scrollbar quand le contenu déborde
    ta.style.overflowY = 'auto';
    // Resize vertical autorisé pour permettre à l'utilisateur d'agrandir
    // ponctuellement un textarea sans toucher la config globale.
    ta.style.resize = 'vertical';
    // On efface une éventuelle hauteur inline héritée d'un précédent
    // autosize : sinon `rows` est ignoré au profit de la hauteur calculée.
    ta.style.height = '';
  }

  /**
   * v0.9.3 — Fixe la hauteur de tous les textareas LaTeX dans `racine`,
   * en lisant la config `atl_textarea_lignes` (défaut 25).
   *
   * Appelée à chaque entrée dans un atelier : la valeur peut avoir changé
   * en Préférences entre-temps.
   *
   * @param {Element|Document} [racine=document]
   * @param {number}           [lignes=25]
   */
  function atelierFixerHauteurLatexTous(racine, lignes) {
    racine = racine || document;
    lignes = lignes || 25;
    const taList = racine.querySelectorAll('textarea.latex-textarea');
    taList.forEach(ta => atelierFixerHauteurLatex(ta, lignes));
  }

  /**
   * Active l'autosize sur tous les <textarea> dans `racine`.
   * @param {Element|Document} [racine=document]
   */
  function atelierAutosizeTous(racine) {
    racine = racine || document;
    const taList = racine.querySelectorAll('textarea');
    taList.forEach(atelierAutosizeTextarea);
  }

  // ── v0.9.3 — Hook Tab/Shift+Tab pour textareas LaTeX ────────────────────────
  //
  // Comportement par défaut HTML : Tab quitte le textarea pour aller au
  // champ suivant. C'est génant quand on saisit du LaTeX, où on veut
  // indenter avec Tab.
  //
  // Stratégie :
  //   - Délégation au niveau document : un seul keydown listener pour
  //     tous les textareas LaTeX, présents et à venir.
  //   - Tab seul → insère 2 espaces à la position du curseur ;
  //     si une sélection multi-lignes est active, indente toutes les
  //     lignes de la sélection.
  //   - Shift+Tab → désindente (retire jusqu'à 2 espaces en début de
  //     chaque ligne sélectionnée, ou de la ligne courante).
  //   - Esc → flag interne qui fait que le PROCHAIN Tab utilise le
  //     comportement natif (navigation au champ suivant). Ce flag se
  //     dissipe à la prochaine frappe ou changement de focus, pour ne
  //     pas piéger l'utilisateur. Garde l'accessibilité clavier.
  //
  // Cible : uniquement les textareas avec la classe `latex-textarea`.
  // Les autres champs (titre, recherche, etc.) gardent Tab natif.

  const _INDENT = '  ';  // 2 espaces (cohérent avec CSS tab-size: 2)
  let _bypassTabSuivant = false;

  document.addEventListener('keydown', (e) => {
    // Esc dans un latex-textarea → autorise un Tab natif au prochain coup
    if (e.key === 'Escape' && e.target instanceof HTMLTextAreaElement
        && e.target.classList.contains('latex-textarea')) {
      _bypassTabSuivant = true;
      // On ne preventDefault PAS l'Esc ; il peut servir ailleurs (modal)
      return;
    }
    if (e.key !== 'Tab') return;
    const ta = e.target;
    if (!(ta instanceof HTMLTextAreaElement)) return;
    if (!ta.classList.contains('latex-textarea')) return;
    if (_bypassTabSuivant) {
      // Coup d'après Esc : on laisse passer le Tab natif (navigation)
      _bypassTabSuivant = false;
      return;
    }
    e.preventDefault();
    const start = ta.selectionStart;
    const end   = ta.selectionEnd;
    const valeur = ta.value;
    if (e.shiftKey) {
      // Désindentation
      _desindenter(ta, start, end, valeur);
    } else if (start === end) {
      // Curseur seul : insère 2 espaces
      ta.value = valeur.slice(0, start) + _INDENT + valeur.slice(end);
      ta.selectionStart = ta.selectionEnd = start + _INDENT.length;
    } else {
      // Sélection : indente toutes les lignes de la sélection
      _indenterSelection(ta, start, end, valeur);
    }
    // Notifie 'input' pour que les listeners (autosize, autosave, etc.)
    // se mettent à jour
    ta.dispatchEvent(new Event('input', { bubbles: true }));
  });

  // Réinitialise le flag de bypass au moindre changement de focus
  document.addEventListener('focusout', () => { _bypassTabSuivant = false; });

  /**
   * Indente toutes les lignes intersectant la sélection [start, end].
   */
  function _indenterSelection(ta, start, end, valeur) {
    // Étend [start, end] aux frontières de lignes
    const debutLigne = valeur.lastIndexOf('\n', start - 1) + 1;
    let finLigne = valeur.indexOf('\n', end);
    if (finLigne === -1) finLigne = valeur.length;

    const lignes = valeur.slice(debutLigne, finLigne).split('\n');
    const lignesIndentees = lignes.map(l => _INDENT + l);
    const blocIndente = lignesIndentees.join('\n');
    ta.value = valeur.slice(0, debutLigne) + blocIndente + valeur.slice(finLigne);
    // Restaure la sélection avec décalage
    const dec = _INDENT.length;
    ta.selectionStart = start + dec;
    ta.selectionEnd   = end + dec * lignes.length;
  }

  /**
   * Désindente toutes les lignes intersectant la sélection [start, end].
   * Retire jusqu'à 2 espaces (ou 1 tabulation) en tête de chaque ligne.
   */
  function _desindenter(ta, start, end, valeur) {
    const debutLigne = valeur.lastIndexOf('\n', start - 1) + 1;
    let finLigne = valeur.indexOf('\n', end);
    if (finLigne === -1) finLigne = valeur.length;
    const lignes = valeur.slice(debutLigne, finLigne).split('\n');
    let totalRetire = 0;
    let retiraitPremiere = 0;
    const lignesDes = lignes.map((l, i) => {
      let retire = 0;
      if (l.startsWith(_INDENT))    retire = _INDENT.length;
      else if (l.startsWith(' '))   retire = 1;
      else if (l.startsWith('\t'))  retire = 1;
      totalRetire += retire;
      if (i === 0) retiraitPremiere = retire;
      return l.slice(retire);
    });
    const blocDes = lignesDes.join('\n');
    ta.value = valeur.slice(0, debutLigne) + blocDes + valeur.slice(finLigne);
    // Restaure la sélection avec décalage négatif
    ta.selectionStart = Math.max(debutLigne, start - retiraitPremiere);
    ta.selectionEnd   = Math.max(ta.selectionStart, end - totalRetire);
  }


  // ── Exports ───────────────────────────────────────────────────────────────

  window.atelierAfficherLatex      = atelierAfficherLatex;
  window.atelierAutosizeTextarea   = atelierAutosizeTextarea;
  window.atelierAutosizeTous       = atelierAutosizeTous;
  // v0.9.3 — Hauteur fixe pour les textareas LaTeX
  window.atelierFixerHauteurLatex     = atelierFixerHauteurLatex;
  window.atelierFixerHauteurLatexTous = atelierFixerHauteurLatexTous;

  // ── 3. Splitters cliquer-tirer (v0.6.4) ────────────────────────────────────
  //
  // Insère une poignée de redimensionnement entre deux panneaux frères
  // dans un conteneur flex horizontal. La poignée est un <div> de quelques
  // pixels de large, avec un curseur col-resize, qui pilote la largeur du
  // panneau de gauche (le panneau de droite suit en flex:1).
  //
  // Persistance : la largeur du panneau de gauche est mémorisée dans le
  // localStorage sous une clé fournie par l'appelant.
  //
  // Bornes : largeur min du panneau de gauche, et largeur min du panneau de
  // droite (calculée comme conteneur.width - largeur_gauche - poignée).
  //
  // Usage :
  //   atelierInstallerSplitter({
  //     gauche: document.getElementById('atl-exercice-aside'),
  //     droite: document.getElementById('atl-exercice-main'),
  //     cleStockage: 'split:atl-exercice:aside',
  //     largeurMinGauche: 200,
  //     largeurMinDroite: 300,
  //   });

  /**
   * Installe une poignée de redimensionnement entre `gauche` et `droite`.
   * Les deux éléments doivent être des frères dans un parent flex horizontal.
   * Idempotent : si une poignée a déjà été installée pour cette paire, ne
   * fait rien (détecté par marqueur dataset).
   */
  function atelierInstallerSplitter(opts) {
    const gauche = opts.gauche;
    const droite = opts.droite;
    if (!gauche || !droite) return;
    if (gauche.dataset.atelierSplitter === '1') return;

    const cleStockage      = opts.cleStockage     || '';
    const largeurMinGauche = opts.largeurMinGauche || 150;
    const largeurMinDroite = opts.largeurMinDroite || 200;

    gauche.dataset.atelierSplitter = '1';

    // Restaurer la largeur sauvegardée si présente.
    if (cleStockage) {
      const sauvee = localStorage.getItem(cleStockage);
      if (sauvee) {
        const px = parseInt(sauvee, 10);
        if (!isNaN(px) && px >= largeurMinGauche) {
          gauche.style.flex = '0 0 ' + px + 'px';
        }
      }
    }

    // Créer la poignée et l'insérer juste après `gauche`.
    const poignee = document.createElement('div');
    poignee.className = 'atelier-splitter';
    poignee.title = 'Cliquer-tirer pour redimensionner';
    gauche.parentNode.insertBefore(poignee, droite);

    let dragActif    = false;
    let xDepart      = 0;
    let largeurDepart = 0;

    poignee.addEventListener('mousedown', (ev) => {
      dragActif = true;
      xDepart = ev.clientX;
      largeurDepart = gauche.getBoundingClientRect().width;
      // Empêcher la sélection de texte pendant le drag
      document.body.style.userSelect = 'none';
      document.body.style.cursor = 'col-resize';
      ev.preventDefault();
    });

    document.addEventListener('mousemove', (ev) => {
      if (!dragActif) return;
      const parent = gauche.parentNode;
      const largeurParent = parent.getBoundingClientRect().width;
      const dx = ev.clientX - xDepart;
      let nouvelleLargeur = largeurDepart + dx;

      // Bornes
      const max = largeurParent - largeurMinDroite - poignee.getBoundingClientRect().width;
      if (nouvelleLargeur < largeurMinGauche) nouvelleLargeur = largeurMinGauche;
      if (nouvelleLargeur > max)              nouvelleLargeur = max;

      gauche.style.flex = '0 0 ' + Math.round(nouvelleLargeur) + 'px';
    });

    document.addEventListener('mouseup', () => {
      if (!dragActif) return;
      dragActif = false;
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
      // Persister la largeur courante
      if (cleStockage) {
        const px = Math.round(gauche.getBoundingClientRect().width);
        localStorage.setItem(cleStockage, String(px));
      }
    });
  }

  window.atelierInstallerSplitter = atelierInstallerSplitter;

  /**
   * Installe une poignée de redimensionnement DANS UN GRID 3-colonnes
   * (form | poignée | rendu). Différent de atelierInstallerSplitter qui
   * gère un flex. Ici, on pilote la variable CSS `--split-ratio` posée
   * sur le conteneur grid, qui contrôle la 1re colonne.
   *
   * Usage :
   *   atelierInstallerSplitterGrid({
   *     conteneur: document.querySelector('#atl-exercice .atl-main'),
   *     cleStockage: 'split:atl-exercice:formrendu',
   *     ratioMinPct: 25,
   *     ratioMaxPct: 75,
   *   });
   */
  function atelierInstallerSplitterGrid(opts) {
    const conteneur = opts.conteneur;
    if (!conteneur) return;
    if (conteneur.dataset.atelierSplitterGrid === '1') return;

    const cleStockage  = opts.cleStockage  || '';
    const ratioMinPct  = opts.ratioMinPct  || 25;
    const ratioMaxPct  = opts.ratioMaxPct  || 75;

    conteneur.dataset.atelierSplitterGrid = '1';

    // Restaurer le ratio sauvegardé
    if (cleStockage) {
      const sauve = localStorage.getItem(cleStockage);
      if (sauve) {
        const pct = parseFloat(sauve);
        if (!isNaN(pct) && pct >= ratioMinPct && pct <= ratioMaxPct) {
          conteneur.style.setProperty('--split-ratio', pct + '%');
        }
      }
    }

    // Insérer la poignée. Le CSS la positionne via grid-area: splitter.
    const poignee = document.createElement('div');
    poignee.className = 'atelier-splitter-split';
    poignee.title = 'Cliquer-tirer pour redimensionner';
    conteneur.appendChild(poignee);

    let dragActif = false;

    poignee.addEventListener('mousedown', (ev) => {
      // Ne réagir qu'en mode split actif
      if (!document.body.classList.contains('atelier-mode-split')) return;
      dragActif = true;
      document.body.style.userSelect = 'none';
      document.body.style.cursor = 'col-resize';
      ev.preventDefault();
    });

    document.addEventListener('mousemove', (ev) => {
      if (!dragActif) return;
      const rect = conteneur.getBoundingClientRect();
      const offsetX = ev.clientX - rect.left;
      let pct = (offsetX / rect.width) * 100;
      if (pct < ratioMinPct) pct = ratioMinPct;
      if (pct > ratioMaxPct) pct = ratioMaxPct;
      conteneur.style.setProperty('--split-ratio', pct.toFixed(2) + '%');
    });

    document.addEventListener('mouseup', () => {
      if (!dragActif) return;
      dragActif = false;
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
      if (cleStockage) {
        const valeur = conteneur.style.getPropertyValue('--split-ratio');
        if (valeur) localStorage.setItem(cleStockage, parseFloat(valeur).toString());
      }
    });
  }

  window.atelierInstallerSplitterGrid = atelierInstallerSplitterGrid;

  // ── window.showToast — point d'entrée unifié des notifications (v0.16.8) ──
  //
  // La classe de base Atelier.toast() délègue à window.showToast(message,
  // estErreur) si elle existe (cf. atelier.js). Or cette fonction n'était
  // DÉFINIE NULLE PART : tous les toasts émis par les ateliers OO
  // (carte/notion/méthode/fiche/exercice — via AtelierEditeur.basculerValidation
  // notamment) tombaient donc dans le `else` → console.error, INVISIBLE à
  // l'écran. Conséquence concrète : un échec de validation pédagogique
  // (HTTP 400 + {raisons:[…]}) ne s'affichait pas (« le serveur renvoie 400,
  // aucune erreur ne s'affiche »).
  //
  // Le projet dispose déjà d'un toast fonctionnel : atelToast(msg, err)
  // (défini dans app.js, coin bas-droite, variante erreur rouge). On fait
  // donc de window.showToast un simple adaptateur de signature vers lui.
  //
  // Délégation PARESSEUSE (au moment de l'appel, pas au chargement) : ainsi
  // l'ordre de chargement atelier_commun.js (tôt) / app.js (juste après) n'a
  // pas d'importance — tout appel à showToast provient d'une interaction
  // utilisateur, donc bien après que app.js soit chargé. Fallback console si
  // atelToast venait à manquer.
  window.showToast = function (message, estErreur) {
    if (typeof window.atelToast === 'function') {
      window.atelToast(message, !!estErreur);
    } else if (estErreur) {
      console.error('[showToast]', message);
    } else {
      console.log('[showToast]', message);
    }
  };

})();
