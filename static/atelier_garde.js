/* static/atelier_garde.js — v0.13.7.0c
 *
 * Système unifié de garde de sortie pour tous les ateliers atomiques.
 *
 * Remplace les anciens fichiers atelier_garde_sortie.js (système à
 * snapshots, jamais alimenté depuis la migration OO de v0.13.6.7+) et
 * atelier_atome_generique.js (legacy court-circuité).
 *
 * Architecture
 * ────────────
 *
 * 1. Registre global window.ATELIER_REGISTRE
 *    Liste des singletons d'ateliers OO actifs. Chaque sous-classe
 *    d'AtelierEditeur s'enregistre à son constructeur via
 *    window.atelGardeEnregistrer(libelle, ref).
 *
 *      ATELIER_REGISTRE = [
 *        { libelle: 'Exercice', ref: <AtelierExercice>, … },
 *        { libelle: 'Notion',   ref: <AtelierNotion>,   … },
 *        … (5 ateliers)
 *      ]
 *
 *    Source de vérité unique : on lit ref.modifie pour savoir si un
 *    atelier a des modifications non sauvegardées. On appelle
 *    ref.sauvegarder() pour les enregistrer.
 *
 * 2. Modale 3 boutons window.atelGardeDemander({ ateliersModifies })
 *    Renvoie une Promise qui résout avec 'sauvegarder' | 'ignorer' |
 *    'annuler'. Affichage unifié pour tous les cas (intra-atelier et
 *    inter-atelier).
 *
 * 3. window.atelGardeAvantTransition(continuation)
 *    Appelée AVANT toute transition (changement d'atelier via menu du
 *    haut, changement de portée). Vérifie tous les ateliers du
 *    registre, propose la modale si modifs, exécute continuation()
 *    selon le choix de l'utilisateur.
 *
 * 4. AtelierEditeur (ailleurs) appelle atelGardeDemander() AUSSI pour
 *    les transitions intra-atelier (changement d'item dans la sidebar,
 *    création nouvel item, fermeture éditeur), à la place de l'ancien
 *    confirm() natif. Unifie l'UX.
 *
 * UX
 * ──
 *
 * Modale 3 boutons :
 *   [ Sauvegarder ] [ Ne pas sauvegarder ] [ Annuler ]
 *
 *   - "Sauvegarder"        : appelle ref.sauvegarder() sur chaque atelier
 *                            modifié, vérifie le succès, puis continue.
 *   - "Ne pas sauvegarder" : RESET les .modifie à false et continue.
 *                            (Ce reset était le bug de v0.13.7.0a :
 *                            on continuait mais les modifs restaient
 *                            en RAM, donc la modale revenait à la
 *                            transition suivante.)
 *   - "Annuler"            : ne fait rien, l'utilisateur reste sur place.
 *
 * Échap = Annuler (UX courante).
 */

(function () {
  'use strict';

  // ── Registre des ateliers actifs ────────────────────────────────────────

  window.ATELIER_REGISTRE = window.ATELIER_REGISTRE || [];

  /**
   * Enregistre un atelier dans le registre. Appelé par chaque sous-classe
   * de AtelierEditeur à la fin du constructeur.
   *
   * @param {string} libelle — Affichable, ex. "Exercice", "Notion"
   * @param {object} ref     — Singleton (ATELIER_EXERCICE, etc.)
   */
  window.atelGardeEnregistrer = function (libelle, ref) {
    // Idempotence : si déjà enregistré, remplace.
    const existant = window.ATELIER_REGISTRE.findIndex(a => a.ref === ref);
    const entree = { libelle: libelle, ref: ref };
    if (existant >= 0) {
      window.ATELIER_REGISTRE[existant] = entree;
    } else {
      window.ATELIER_REGISTRE.push(entree);
    }
  };

  /**
   * Retourne la liste des ateliers actuellement modifiés.
   * Un atelier est "modifié" si ref.modifie === true.
   */
  function _ateliersModifies() {
    return window.ATELIER_REGISTRE.filter(a => a.ref && a.ref.modifie === true);
  }

  // ── Modale 3 boutons ────────────────────────────────────────────────────

  /**
   * Affiche la modale et résout avec le choix de l'utilisateur.
   *
   * @param {object} opts
   * @param {Array<{libelle, ref}>} opts.ateliersModifies — pour le libellé
   * @param {string} [opts.titre]   — titre de la modale (override)
   * @param {string} [opts.message] — message principal (override)
   * @returns {Promise<'sauvegarder'|'ignorer'|'annuler'>}
   */
  window.atelGardeDemander = function (opts) {
    opts = opts || {};
    const ateliers = opts.ateliersModifies || [];
    const libelles = ateliers.map(a => a.libelle).join(', ');
    const titre = opts.titre || 'Modifications non sauvegardées';
    const message = opts.message ||
      `Vous avez des modifications non enregistrées dans : <strong>${libelles}</strong>.<br><br>Que voulez-vous faire ?`;

    return new Promise(function (resolve) {
      let modale = document.getElementById('atl-garde-modale');
      if (!modale) {
        modale = document.createElement('div');
        modale.id = 'atl-garde-modale';
        modale.className = 'atl-garde-modale';
        document.body.appendChild(modale);
      }
      modale.innerHTML =
        '<div class="atl-garde-modale-fond"></div>' +
        '<div class="atl-garde-modale-contenu">' +
          '<div class="atl-garde-modale-titre">' + titre + '</div>' +
          '<div class="atl-garde-modale-corps">' + message + '</div>' +
          '<div class="atl-garde-modale-actions">' +
            '<button class="btn-prim" id="atl-garde-modale-save">Sauvegarder</button>' +
            '<button class="btn-sm"   id="atl-garde-modale-ignore">Ne pas sauvegarder</button>' +
            '<button class="btn-sm"   id="atl-garde-modale-annuler" style="margin-left:auto">Annuler</button>' +
          '</div>' +
        '</div>';
      modale.style.display = 'flex';

      function close(resultat) {
        modale.style.display = 'none';
        document.removeEventListener('keydown', onKey);
        resolve(resultat);
      }
      function onKey(ev) {
        if (modale.style.display === 'none') {
          document.removeEventListener('keydown', onKey);
          return;
        }
        if (ev.key === 'Escape') close('annuler');
      }

      document.getElementById('atl-garde-modale-save').onclick    = () => close('sauvegarder');
      document.getElementById('atl-garde-modale-ignore').onclick  = () => close('ignorer');
      document.getElementById('atl-garde-modale-annuler').onclick = () => close('annuler');
      document.addEventListener('keydown', onKey);
    });
  };

  // ── Helpers haut-niveau pour les ateliers ───────────────────────────────

  /**
   * Garde universelle : avant toute transition, vérifie le registre,
   * propose la modale si modifs, exécute la continuation selon le choix.
   *
   * Appelée par app.js avant un changement d'atelier (menu du haut),
   * une bascule de portée, etc.
   *
   * @param {Function} continuation — code à exécuter si l'utilisateur accepte
   */
  window.atelGardeAvantTransition = async function (continuation) {
    const ateliers = _ateliersModifies();
    if (ateliers.length === 0) {
      return continuation();
    }
    const choix = await window.atelGardeDemander({ ateliersModifies: ateliers });
    if (choix === 'annuler') return;
    if (choix === 'ignorer') {
      // v0.13.7.0d — On RESTAURE le formulaire à l'état persistant (DOM
      // ré-écrit depuis itemActif via remplirFormulaire), pas juste
      // un reset de flag. Conséquence visuelle : au retour dans
      // l'atelier, l'utilisateur retrouve l'état d'origine, pas ses
      // modifs en cours.
      ateliers.forEach(a => {
        if (a.ref && typeof a.ref._restaurerForm === 'function') {
          a.ref._restaurerForm();
        } else if (a.ref) {
          // Repli : juste reset le flag.
          a.ref.modifie = false;
          if (typeof a.ref.majToolbar === 'function') a.ref.majToolbar();
        }
      });
      return continuation();
    }
    // 'sauvegarder' : essayer de sauvegarder chaque atelier modifié
    try {
      await Promise.all(ateliers.map(a => {
        if (a.ref && typeof a.ref.sauvegarder === 'function') {
          return Promise.resolve(a.ref.sauvegarder());
        }
        return Promise.resolve();
      }));
    } catch (e) {
      alert('Erreur lors de la sauvegarde : ' + (e && e.message ? e.message : e));
      return;
    }
    // Vérification : un atelier peut avoir échoué silencieusement
    // (sauvegarder() qui capture ses erreurs et ne rejette pas).
    const encoreModifies = _ateliersModifies();
    if (encoreModifies.length > 0) {
      // Toast d'erreur de l'atelier concerné déjà affiché.
      return;
    }
    return continuation();
  };

  /**
   * Garde intra-atelier : appelée par AtelierEditeur avant ouvrirItem,
   * nouvelItem, fermerEditeur, etc. Limite la portée à l'atelier passé
   * en argument (sinon l'utilisateur verrait des modales pour des
   * ateliers qu'il n'a pas touchés directement).
   *
   * @param {object} atelier — l'instance AtelierEditeur appelante
   * @returns {Promise<boolean>} true = continuer, false = abandonner
   */
  window.atelGardeAvantAction = async function (atelier) {
    if (!atelier || !atelier.modifie) return true;
    const libelle = _libelleDuRef(atelier);
    const choix = await window.atelGardeDemander({
      ateliersModifies: [{ libelle: libelle, ref: atelier }],
    });
    if (choix === 'annuler') return false;
    if (choix === 'ignorer') {
      atelier.modifie = false;
      if (typeof atelier.majToolbar === 'function') atelier.majToolbar();
      return true;
    }
    // 'sauvegarder'
    try {
      await Promise.resolve(atelier.sauvegarder());
    } catch (e) {
      alert('Erreur lors de la sauvegarde : ' + (e && e.message ? e.message : e));
      return false;
    }
    // Échec silencieux : modifie toujours true
    if (atelier.modifie) return false;
    return true;
  };

  function _libelleDuRef(ref) {
    const e = window.ATELIER_REGISTRE.find(a => a.ref === ref);
    return e ? e.libelle : 'Atelier';
  }

})();
