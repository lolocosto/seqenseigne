/**
 * static/atelier_exercice.js — v0.13.6.7.5
 *
 * Atelier d'édition des exercices (portée séquence).
 *
 * v0.13.6.6 — Squelette initial écrit (mais non activé).
 * v0.13.6.7.5 — Activation + enrichissement avec les leçons des
 *               migrations notion/méthode/fiche :
 *               - Setters miroir window.ATL_EXERCICE_ACTIF et window.ATL_EXO
 *               - Surcharge basculerOnglet → rendreAtomeTab('exercice')
 *               - Affichage LaTeX : via AtelierEditeur.voirLatex (serveur + modale, v0.17.2)
 *               - Ponts rétrocompat window.atelExercice* pour ne rien casser
 *
 * Particularités exercice :
 *   - Sidebar bucketing par série : F (fondamental) / A (avancé) /
 *     E (exploration) / AE (approche) / Autres. Sections repliables.
 *   - Identifiant compact N11/S04/F01 (niveau / séquence / série+num).
 *   - placedTags = objectifs liés (depuis ex.liens).
 *   - Formulaire avec champs titre, variables, énoncé, corrigé,
 *     remédiation (énoncé + corrigé), cadre de réponse (lignes
 *     principal + lignes remédiation).
 *   - Cadre Remédiation visible seulement pour série F et A.
 *   - Validation : énoncé ET corrigé obligatoires.
 *   - Génération LaTeX côté client : \begin{seqSerieExos}{N}...
 *     \begin{seqExercice}[nom=...]...\seqCorrige{...}\end{seqExercice}
 *     \end{seqSerieExos}.
 *
 * Compat HTML : les onclick du template appellent ATELIER_EXERCICE.method().
 * Les anciens noms (atelExercice*) sont conservés comme alias globaux pour
 * ne pas casser les références internes encore présentes (rendu_atome.js,
 * atelier_etat_edition.js via le wrapper atelExerciceBasculerValidationCb,
 * code mort dans app.js).
 */

class AtelierExercice extends AtelierEditeur {

  // v0.13.6.6.1 — Champs statiques déclarés APRÈS la classe pour
  // compatibilité ES2015 (la syntaxe `static FOO = {...}` à l'intérieur
  // de la classe est ES2022).

  constructor() {
    super({
      id:                 'exercice',
      prefixe:            'atl-exercice',
      titreToolbar:       'Atelier Exercice',
      endpointBase:       '/api/exercices',
      // v0.14.3 — Rendu PDF via l'API unifiée /api/atomes/<type>/.
      // Le CRUD des exercices reste sur /api/exercices.
      endpointRenduPdf:   '/api/atomes/exercice',
      labelExistant:      "Modifier l'exercice",
      labelNouveau:       'Nouvel exercice',
      confirmSuppression: 'Supprimer cet exercice ?',
      messageEnregistre:  'Exercice enregistré.',
      messageSupprime:    'Exercice supprimé.',
      typeApi:            'exercice',
      typeBadge:          'exercice',
    });

    // Série courante du formulaire (pour les nouveaux exos avant save).
    this.serieCourante = 'fondamental';
  }

  // ── Setters miroir vers variables globales (compat ancien code) ─────────
  //
  // rendu_atome.js et atelier_etat_edition.js peuvent encore lire les
  // variables globales ATL_EXERCICE_ACTIF et ATL_EXO. v0.13.6.7.3.1 a patché
  // rendu_atome.js pour qu'il lise en priorité window.ATELIER_EXERCICE.itemActif,
  // mais on maintient les miroirs au cas où d'autres lecteurs existent.
  // Le wrapper atelExerciceBasculerValidationCb dans app.js lit ATL_EXERCICE_ACTIF
  // et ATL_EXO directement (sans préfixe window.) — il accédera à la let
  // d'app.js qui reste à null. Pour cette raison, le HTML appelle
  // directement ATELIER_EXERCICE.basculerValidation() et non le wrapper.

  set itemActif(val) {
    this._itemActif = val;
    window.ATL_EXERCICE_ACTIF = val;
  }
  get itemActif() {
    return this._itemActif;
  }

  set liste(val) {
    this._liste = val;
    window.ATL_EXO = val;
  }
  get liste() {
    return this._liste || [];
  }

  // ── Sidebar : bucketing par série en sections repliables ────────────────

  rendreSidebar() {
    const list = this.$('list');
    if (!list) return;

    const items = this.filtrerListe(this.liste);
    if (items.length === 0) {
      list.innerHTML = '<div style="padding:14px;font-size:12px;' +
                       'color:var(--text-muted);text-align:center">' +
                       'Aucun exercice</div>';
      return;
    }

    // Bucketing par série
    // v0.18.3.2 — Le backend renvoie un contrat à 6 clés SANS `serie_code`
    // ni `serie` : la série est encodée comme PRÉFIXE de `ex.code`
    // (F01, A03, E02, R05… et surtout AE01 pour l'approche). Le préfixe peut
    // faire DEUX lettres ('AE') : il faut le reconnaître avant la première
    // lettre, sinon 'AE01' est lu comme 'A' (→ rangé à tort en Avancés).
    // (Fallback historique sur serie_code/serie si un appel les fournit.)
    const buckets = { F: [], A: [], E: [], AE: [], Autres: [] };
    for (const ex of items) {
      const code = ex.serie_code
                 || AtelierExercice.SERIE_EN_CODE[ex.serie]
                 || AtelierExercice.prefixeSerie(ex.code)
                 || '';
      const bucket = buckets[code] ? code : 'Autres';
      buckets[bucket].push(ex);
    }

    // Construction des sections
    const ordre = ['F', 'A', 'E', 'AE', 'Autres'];
    const sections = [];
    for (const code of ordre) {
      const exos = buckets[code];
      if (code === 'Autres' && exos.length === 0) continue;

      const itemsHtml = exos.length > 0
        ? exos.map(ex => this.rendreItem(ex, code)).join('')
        : '<div style="padding:6px 4px;font-size:11px;color:var(--text-muted)">— aucun —</div>';

      const cfgBucket = AtelierExercice.SERIE_BUCKETS[code];
      const collapsed = window.atelCatEstReplie
        ? window.atelCatEstReplie('exercice', code, cfgBucket.defautReplie)
        : cfgBucket.defautReplie;

      sections.push(window.atelAsmCatHtml(
        'exercice', code, cfgBucket.label, exos.length, itemsHtml,
        { collapsed },
      ));
    }
    list.innerHTML = sections.join('');
  }

  // ── Surcharge rendreItem : badge série + placedTags objectifs ────────────

  rendreItem(ex, badgeCode = null) {
    if (badgeCode === null) {
      // Appel direct (pas depuis rendreSidebar) — déduire le code série.
      // v0.13.6.16 — Auparavant on lisait ex.serie_code ou
      // AtelierExercice.SERIE_EN_CODE[ex.serie]. Avec le nouveau
      // contrat à 6 clés, ces champs sont absents : la lettre série
      // est encodée comme première lettre de ex.code (ex. 'E01' →
      // 'E', 'A03' → 'A'). En fallback historique on lit encore
      // ex.serie_code et ex.serie si disponibles (appels depuis
      // rendreSidebar qui peut passer un badgeCode explicite).
      // v0.18.3.2 — préfixe de série depuis ex.code, gère 'AE' (2 lettres).
      badgeCode = ex.serie_code
                || AtelierExercice.SERIE_EN_CODE[ex.serie]
                || AtelierExercice.prefixeSerie(ex.code)
                || 'Autres';
    }
    const actif = this.itemActif && this.itemActif.id === ex.id;

    // v0.13.6.16 — Avant : reconstruction du code via serie_code + num.
    // Maintenant : ex.code arrive déjà préfixé du backend (E01, A03…).
    // niveau/sequence viennent des filtres globaux.
    const idExo = [
      window.ATL_FILTRE_NIVEAU || '',
      window.ATL_FILTRE_SEQ || '',
      ex.code || '',
    ].filter(Boolean).join('/');

    const titre = ex.titre
      ? ex.titre
      : { html: '(sans titre)', derive: true };

    // Badge série coloré
    const badgeCls = badgeCode === 'Autres' ? 'M' : badgeCode;
    const badge = `<span class="asm-item-badge asm-item-badge--${Atelier.escAttr(badgeCls)}">` +
                  `${Atelier.escHtml(badgeCode === 'Autres' ? '?' : badgeCode)}</span>`;

    const placedTags = window.atelLiensEnTags
      ? window.atelLiensEnTags(ex.liens || [])
      : [];

    const etatCode = ex.etat_code || 'en_cours';

    return Atelier.rendreItemHtml({
      actif,
      selected: this.estSelectionne(ex.id),
      dataId: ex.id,
      onclick: `ATELIER_EXERCICE.gererClicItem(event, '${Atelier.escAttr(ex.id)}')`,
      oncontextmenu: `ATELIER_EXERCICE.gererClicDroitItem(event, '${Atelier.escAttr(ex.id)}')`,
      badge,
      id: idExo,
      titre,
      placedTags,
      etatCode,
    });
  }

  // ── Formulaire : lecture du DOM ─────────────────────────────────────────

  collecterFormulaire() {
    // v0.13.6.16 — Énoncé et corrigé relâchés (modèle « en cours » :
    // un exercice peut être incomplet en cours d'édition). La règle
    // « énoncé et corrigé non vides » est appliquée par le hook de
    // validation pédagogique côté backend, au passage en `valide`.
    const enonce  = this.$('enonce').value;
    const corrige = this.$('corrige').value;

    const remedActif      = !!(this.$('cadre-rep-remed-actif')      || {}).checked;
    const principalActif  = !!(this.$('cadre-rep-principal-actif')  || {}).checked;
    const lignesPrinc = principalActif
      ? parseInt((this.$('cadre-rep-principal-lignes') || {}).value, 10) || 0
      : 0;
    const lignesRemed = remedActif
      ? parseInt((this.$('cadre-rep-remed-lignes') || {}).value, 10) || 0
      : 0;

    // v0.14.8 — Si la case « Rédiger une remédiation » est décochée,
    // on force les champs de remédiation à vide (cf. Q2=a : pas de
    // champ booléen, l'état est dérivé). Symétriquement le cadre de
    // réponse de remédiation est désactivé.
    const remediationCochee = !!(this.$('remed-actif') || {}).checked;
    const remedEnonce  = remediationCochee ? ((this.$('remed-enonce')  || {}).value || '') : '';
    const remedCorrige = remediationCochee ? ((this.$('remed-corrige') || {}).value || '') : '';
    const lignesRemedFinal = remediationCochee ? lignesRemed : 0;

    return {
      serie:     this.serieCourante,
      titre:     (this.$('titre') || {}).value || '',
      variables: (this.$('variables') || {}).value || '',
      enonce, corrige,
      remed_enonce:                   remedEnonce,
      remed_corrige:                  remedCorrige,
      cadre_reponse_lignes_principal: lignesPrinc,
      cadre_reponse_lignes_remed:     lignesRemedFinal,
    };
  }

  // ── Formulaire : écriture dans le DOM ───────────────────────────────────

  remplirFormulaire(ex) {
    this.changerSerie(ex.serie || 'fondamental', false);
    this.$('titre').value     = ex.titre     || '';
    this.$('variables').value = ex.variables || '';
    this.$('enonce').value    = ex.enonce    || '';
    this.$('corrige').value   = ex.corrige   || '';

    const remedEnEl = this.$('remed-enonce');
    const remedCoEl = this.$('remed-corrige');
    if (remedEnEl) remedEnEl.value = ex.remed_enonce  || '';
    if (remedCoEl) remedCoEl.value = ex.remed_corrige || '';

    // v0.14.8 — État de la case « Rédiger une remédiation » : cochée
    // si du contenu de remédiation existe (énoncé ou corrigé non vides).
    // Cf. Q2=a : l'activation est dérivée des champs.
    const remedActifEl = this.$('remed-actif');
    if (remedActifEl) {
      const aDuContenu = !!((ex.remed_enonce  && ex.remed_enonce.trim()) ||
                            (ex.remed_corrige && ex.remed_corrige.trim()));
      remedActifEl.checked = aDuContenu;
    }

    const lignesPrinc = parseInt(ex.cadre_reponse_lignes_principal, 10) || 0;
    const lignesRemed = parseInt(ex.cadre_reponse_lignes_remed,     10) || 0;

    const toggleP = this.$('cadre-rep-principal-actif');
    const wrapP   = this.$('cadre-rep-principal-lignes-wrap');
    const champP  = this.$('cadre-rep-principal-lignes');
    if (toggleP && wrapP && champP) {
      if (lignesPrinc > 0) {
        toggleP.checked = true;
        wrapP.style.display = '';
        champP.value = String(lignesPrinc);
      } else {
        toggleP.checked = false;
        wrapP.style.display = 'none';
        champP.value = '10';
      }
    }

    const toggleR = this.$('cadre-rep-remed-actif');
    const wrapR   = this.$('cadre-rep-remed-lignes-wrap');
    const champR  = this.$('cadre-rep-remed-lignes');
    if (toggleR && wrapR && champR) {
      if (lignesRemed > 0) {
        toggleR.checked = true;
        wrapR.style.display = '';
        champR.value = String(lignesRemed);
      } else {
        toggleR.checked = false;
        wrapR.style.display = 'none';
        champR.value = '10';
      }
    }

    // Section Variables : ouverte si contenu non vide, sinon repliée.
    const variablesEl = this.$('field-variables');
    const variablesBd = this.$('variables-body');
    if (variablesEl && variablesBd) {
      const aDuContenu = !!(ex.variables && ex.variables.trim());
      if (aDuContenu) {
        variablesEl.classList.add('is-open');
        variablesBd.style.display = '';
      } else {
        variablesEl.classList.remove('is-open');
        variablesBd.style.display = 'none';
      }
    }

    this.majVisibiliteRemediation();
    // v0.13.6.11 — Bouton « reprendre titre objectif » (chantier B)
    this._injecterBoutonReprendreTitre('atl-exercice-titre');
  }

  // ── Création : choix de la série via modale avant POST (v0.13.6.16) ──────
  //
  // L'enseignant doit choisir explicitement une série à la création
  // (décision v0.13.6.16). On surcharge donc `nouvelItem` pour
  // afficher une modale dédiée (#atl-exercice-modale-serie dans index.html),
  // capturer le choix via une Promise, puis appeler le pattern parent
  // POST-direct + ouvrirItem avec la série retenue.

  async nouvelItem() {
    const niveau = window.ATL_FILTRE_NIVEAU || '';
    const sequence = window.ATL_FILTRE_SEQ || '';
    if (!niveau || !sequence) {
      this.toast('Sélectionner un niveau et une séquence d\'abord.', 'erreur');
      return;
    }
    if (this.modifie) {
      if (!confirm('Vous avez des modifications non sauvées. Les perdre ?')) {
        return;
      }
    }

    // Demande interactive de la série via la modale.
    const serie = await this._demanderSerie();
    if (!serie) return;  // Annulé (Esc / clic dehors / bouton ×)

    // POST direct avec la série choisie + niveau/sequence/champs vides.
    try {
      const resp = await fetch(this.config.endpointBase, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          niveau, sequence,
          serie,
          enonce: '',
          corrige: '',
        }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        const msg = data.message || data.error || `HTTP ${resp.status}`;
        this.toast(`Erreur création : ${msg}`, 'erreur');
        return;
      }
      const item = await resp.json();
      await this.chargerListe();
      await this.ouvrirItem(item.id);
    } catch (e) {
      this.toast(`Erreur réseau : ${e.message}`, 'erreur');
    }
  }

  /**
   * Affiche la modale de choix de série et retourne une Promise qui
   * résout avec la série choisie (string) ou null si annulé.
   *
   * Gestion clavier : Esc annule. Clic en dehors du contenu de la
   * modale (sur l'overlay) annule également (cf. handler onclick de
   * l'overlay dans index.html qui appelle _annulerChoixSerie).
   */
  _demanderSerie() {
    return new Promise((resolve) => {
      this._resoudreChoixSerie = resolve;
      const overlay = document.getElementById('atl-exercice-modale-serie');
      if (!overlay) {
        // Garde-fou : si la modale n'est pas en DOM (cas test/dev), on
        // résout avec null pour ne pas bloquer.
        resolve(null);
        return;
      }
      overlay.style.display = 'flex';
      // Écouteur Esc actif tant que la modale est ouverte
      this._gestionnaireEscSerie = (ev) => {
        if (ev.key === 'Escape') {
          ev.preventDefault();
          this._annulerChoixSerie();
        }
      };
      document.addEventListener('keydown', this._gestionnaireEscSerie);
    });
  }

  /**
   * Handler appelé quand l'utilisateur clique sur un bouton série.
   * Ferme la modale et résout la Promise avec la série choisie.
   */
  _validerChoixSerie(serie) {
    this._fermerModaleSerie();
    if (this._resoudreChoixSerie) {
      const r = this._resoudreChoixSerie;
      this._resoudreChoixSerie = null;
      r(serie);
    }
  }

  /**
   * Handler d'annulation (clic en dehors, Esc, bouton ×).
   * Le paramètre `ev` est optionnel : présent quand le clic provient
   * de l'overlay (event.target doit être l'overlay lui-même, sinon
   * c'est un clic intérieur qu'on ignore via event.stopPropagation
   * posé sur le `.atelier-modale`).
   */
  _annulerChoixSerie(ev) {
    if (ev && ev.target !== ev.currentTarget) return;
    this._fermerModaleSerie();
    if (this._resoudreChoixSerie) {
      const r = this._resoudreChoixSerie;
      this._resoudreChoixSerie = null;
      r(null);
    }
  }

  _fermerModaleSerie() {
    const overlay = document.getElementById('atl-exercice-modale-serie');
    if (overlay) overlay.style.display = 'none';
    if (this._gestionnaireEscSerie) {
      document.removeEventListener('keydown', this._gestionnaireEscSerie);
      this._gestionnaireEscSerie = null;
    }
  }

  // ── Payload de création (pattern POST-direct unifié, v0.13.6.16) ────────
  //
  // Non utilisé directement pour l'exercice puisque nouvelItem est
  // surchargé ci-dessus pour intercaler la modale de choix de série.
  // On conserve la méthode pour cohérence du contrat avec la classe
  // parente : si un autre code appelle _payloadCreation directement
  // (peu probable), il obtient un payload valide avec la série
  // courante de l'atelier.

  _payloadCreation() {
    return {
      niveau:   window.ATL_FILTRE_NIVEAU || '',
      sequence: window.ATL_FILTRE_SEQ || '',
      serie:    this.serieCourante || 'fondamental',
      enonce:   '',
      corrige:  '',
    };
  }

  // ── Changement de série (handler des boutons F/A/E/AE) ──────────────────

  changerSerie(s, marquerDirty = true) {
    this.serieCourante = s;
    ['fondamental', 'avancé', 'exploration', 'approche'].forEach(k => {
      const btn = document.getElementById('atl-serie-' + k);
      if (btn) {
        const classeActive = (k === s)
          ? ' active-' + k.replace('é', 'e')
          : '';
        btn.className = 'serie-btn' + classeActive;
      }
    });
    if (this.itemActif) this.itemActif.serie = s;
    this.majVisibiliteRemediation();
    if (marquerDirty && this.itemActif) {
      this.marquerModifie();
    }
  }

  /**
   * Affiche/masque le cadre Remédiation selon la série courante,
   * et le contenu (champs énoncé/corrigé) selon l'état de la case
   * « Rédiger une remédiation ».
   *
   * v0.14.8 — Deux niveaux de visibilité :
   *   1. Le cadre lui-même (incl. la case à cocher) : visible si la
   *      série autorise la remédiation (F = fondamental, A = avancé) ;
   *      caché pour E/AE (cf. décision Q1=b).
   *   2. Le contenu du cadre (champs énoncé/corrigé + cadre de réponse) :
   *      visible uniquement si la case « Rédiger une remédiation » est
   *      cochée (cf. décision Q1=b).
   */
  majVisibiliteRemediation() {
    const cadre = this.$('cadre-remediation');
    if (!cadre) return;
    const serieAutorise = (this.serieCourante === 'fondamental'
                       || this.serieCourante === 'avancé');
    cadre.style.display = serieAutorise ? '' : 'none';

    // Le contenu (champs et toggle de cadre de réponse) ne s'affiche
    // que si la case est cochée.
    const contenu = this.$('remed-contenu');
    const actif   = this.$('remed-actif');
    if (contenu) {
      const coche = !!(actif && actif.checked);
      contenu.style.display = (serieAutorise && coche) ? '' : 'none';
    }
  }

  /**
   * Handler de la case à cocher « Rédiger une remédiation » (v0.14.8).
   *
   * Si la case est décochée et que des champs de remédiation contiennent
   * du texte, demande confirmation avant de purger (Q2bis=i). Si
   * l'utilisateur refuse, on recoche la case et on ne touche à rien.
   *
   * Note : on ne vide pas les champs textarea ici (le contenu peut rester
   * en mémoire). C'est `collecterFormulaire()` qui les omettra à la
   * sauvegarde si la case est décochée. Mais en cas de confirmation
   * explicite de l'utilisateur, on vide les textareas pour éviter qu'il
   * voie l'ancien contenu en recochant.
   */
  toggleRemediation() {
    const actif = this.$('remed-actif');
    if (!actif) return;

    if (!actif.checked) {
      // L'utilisateur vient de décocher. S'il y a du contenu, on demande
      // confirmation pour le purger.
      const enEl = this.$('remed-enonce');
      const coEl = this.$('remed-corrige');
      const valEn = (enEl && enEl.value || '').trim();
      const valCo = (coEl && coEl.value || '').trim();
      if (valEn || valCo) {
        const ok = window.confirm(
          "Désactiver la remédiation supprimera l'énoncé et le corrigé "
          + "de remédiation à la prochaine sauvegarde. Continuer ?"
        );
        if (!ok) {
          // Restauration : on recoche la case et on s'arrête.
          actif.checked = true;
          return;
        }
        // Confirmation OK : on vide les textareas (sera persisté à la
        // prochaine sauvegarde via collecterFormulaire).
        if (enEl) enEl.value = '';
        if (coEl) coEl.value = '';
        // Décocher aussi le cadre de réponse de remédiation
        const cadreActif = this.$('cadre-rep-remed-actif');
        if (cadreActif) cadreActif.checked = false;
        const wrap = this.$('cadre-rep-remed-lignes-wrap');
        if (wrap) wrap.style.display = 'none';
      }
    }
    // Que la case soit cochée ou décochée, on met à jour la visibilité.
    this.majVisibiliteRemediation();
    // v0.13.7.0d — Le marquage modifié est automatique (listener
    // délégué + comparaison de snapshot dans AtelierEditeur). L'event
    // 'change' de la case bulle et déclenche la réévaluation.
  }

  // ── Toggles UI (sections repliables, cadres de réponse) ─────────────────

  toggleVariables() {
    const wrapper = this.$('field-variables');
    const body    = this.$('variables-body');
    if (!wrapper || !body) return;
    const ouvert = wrapper.classList.toggle('is-open');
    body.style.display = ouvert ? '' : 'none';
  }

  toggleCadreReponsePrincipal() {
    const toggle = this.$('cadre-rep-principal-actif');
    const wrap   = this.$('cadre-rep-principal-lignes-wrap');
    if (!toggle || !wrap) return;
    wrap.style.display = toggle.checked ? '' : 'none';
    // v0.13.7.0d — Le marquage modifié est désormais automatique
    // (listener délégué + comparaison de snapshot dans AtelierEditeur).
    // L'event 'change' de la case bulle vers le form et déclenche
    // la réévaluation. Plus besoin d'appel manuel.
  }

  toggleCadreReponseRemed() {
    const toggle = this.$('cadre-rep-remed-actif');
    const wrap   = this.$('cadre-rep-remed-lignes-wrap');
    if (!toggle || !wrap) return;
    wrap.style.display = toggle.checked ? '' : 'none';
    // v0.13.7.0d — Marquage modifié automatique (cf. principal).
  }

  // ── Handler générique de changement (les onchange du form) ──────────────

  formChange() {
    if (!this.itemActif) return;
    this.marquerModifie();
  }

  // ── Onglet Rendu PDF ────────────────────────────────────────────────────
  //
  // v0.14.3 — Plus de surcharge de basculerOnglet : le rendu PDF est
  // maintenant entièrement géré par AtelierEditeur (HTML statique
  // #atl-exercice-* + verifierCacheEtAfficher + compilerRendu via
  // endpointRenduPdf='/api/atomes/exercice').
  //
  // Le cas-coin DOM historique (zone #atl-exercice-rendu nécessitant un
  // affichage/masquage manuel parce que l'ancien préfixe court de la
  // classe donnait un id introuvable) a disparu en v0.14.1 lors du
  // renommage vers le préfixe long « atl-exercice ». La parente
  // AtelierEditeur.basculerOnglet trouve maintenant la zone toute seule.

  // v0.17.2 — Génération LaTeX CLIENT retirée. Le LaTeX est produit côté
  // serveur (route /rendu-tex) et affiché par AtelierEditeur.voirLatex()
  // (hérité) dans la modale commune. Les anciennes voirLatex/genererLatex/
  // copierLatex (qui produisaient un fragment côté client dans
  // #atl-exercice-latex-out) sont supprimées : une seule source de vérité,
  // le serveur (séparation des rôles).
}

// ── Champs statiques de la classe AtelierExercice ────────────────────────

// v0.18.3.2 — Extrait le préfixe de série d'un code d'exercice.
// Le code est de la forme PREFIXE + numéro (ex. 'F01', 'A03', 'E02', 'R05',
// 'AE01'). Le préfixe peut faire DEUX lettres ('AE' = approche) : on le
// reconnaît AVANT les préfixes à une lettre, sinon 'AE01' serait lu 'A'
// (et l'exo d'approche tomberait à tort dans le bucket Avancés).
// Retourne '' si le code est vide/inexploitable.
AtelierExercice.prefixeSerie = function (code) {
  if (!code || typeof code !== 'string') return '';
  // Préfixes connus à 2 lettres d'abord, puis 1 lettre.
  const m = code.match(/^(AE|[FAER])/);
  return m ? m[1] : '';
};

AtelierExercice.SERIE_BUCKETS = {
  F:      { label: 'Fondamentaux',  defautReplie: false },
  A:      { label: 'Avancés',       defautReplie: false },
  E:      { label: 'Exploration',   defautReplie: true  },
  AE:     { label: 'Approche (AE)', defautReplie: true  },
  Autres: { label: 'Autres',        defautReplie: true  },
};

// Mapping série longue → code court pour le bucketing.
AtelierExercice.SERIE_EN_CODE = {
  'fondamental': 'F',
  'avancé':      'A',
  'exploration': 'E',
  'approche':    'AE',
};

// ── Instance singleton et exposition globale ──────────────────────────────

const ATELIER_EXERCICE = new AtelierExercice();
window.ATELIER_EXERCICE = ATELIER_EXERCICE;

// v0.13.7.0c — Enregistrement dans le registre unifié.
if (typeof window.atelGardeEnregistrer === 'function') {
  window.atelGardeEnregistrer('Exercice', ATELIER_EXERCICE);
}

// ── Ponts rétrocompat ─────────────────────────────────────────────────────
//
// Les anciens noms restent dispos pour les références internes
// (atelExerciceBasculerValidationCb dans app.js, rendu_atome.js qui lit
// ATL_EXERCICE_ACTIF, atelInvoquerInit, etc.). À nettoyer en v0.14.
//
// v0.13.7.0c — ATL_ATOME_CONFIG (callbacks de l'ancien atelier_atome_generique.js)
// a disparu ; ce système legacy a été retiré.

window.atelChargerExercices         = () => ATELIER_EXERCICE.chargerListe();
window.atelRenderListe              = () => ATELIER_EXERCICE.rendreSidebar();
window.atelExerciceNouveau               = () => ATELIER_EXERCICE.nouvelItem();
window.atelExerciceCharger               = (id) => ATELIER_EXERCICE.ouvrirItem(id);
window.atelExerciceSauvegarder           = () => ATELIER_EXERCICE.sauvegarder();
window.atelExerciceSupprimer             = () => ATELIER_EXERCICE.supprimer();
window.atelExerciceRemplir               = (ex) => ATELIER_EXERCICE.remplirFormulaire(ex);
window.atelExerciceTab                   = (tab) => ATELIER_EXERCICE.basculerOnglet(tab);
window.atelExerciceSerie                 = (s, update = true) =>
                                        ATELIER_EXERCICE.changerSerie(s, update);
window.atelExerciceMajVisibiliteRemediation = () =>
                                        ATELIER_EXERCICE.majVisibiliteRemediation();
window.atelExerciceToggleVariables       = () => ATELIER_EXERCICE.toggleVariables();
window.atelExerciceToggleCadreReponsePrincipal = () =>
                                        ATELIER_EXERCICE.toggleCadreReponsePrincipal();
window.atelExerciceToggleCadreReponseRemed = () =>
                                        ATELIER_EXERCICE.toggleCadreReponseRemed();
window.atelExerciceVoirLatex             = () => ATELIER_EXERCICE.voirLatex();
window.atelExerciceBasculerValidationCb  = () => ATELIER_EXERCICE.basculerValidation();
