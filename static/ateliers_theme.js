/**
 * static/ateliers_theme.js — R2.
 *
 * Atelier Thème : CRUD complet des thèmes d'un cycle.
 *
 * Dépendances : doit être chargé après app.js.
 * Utilise la fonction globale `api(path, options)` définie dans app.js
 * pour les appels JSON.
 *
 * Activation : appelé par atelSwitch('theme') (voir patch de app.js).
 */

(function () {
    'use strict';

    // ── État local du panneau ────────────────────────────────────────────

    let ATL_THEME_FAMILLES = [];         // familles de couleurs
    let ATL_THEME_LIST = [];             // liste des thèmes du cycle courant
    let ATL_THEME_EN_COURS = null;       // thème actuellement en édition
    let ATL_THEME_DIRTY = false;         // true si formulaire modifié depuis le load

    // Le cycle courant n'est plus stocké localement : on le lit depuis la
    // portée Cycle (refonte v0.10 — moule commun).
    function cycleCourant() {
        const sel = (window.ATL_SELECTIONS && window.ATL_SELECTIONS.cycle) || {};
        return sel.cycle || 'C04';
    }

    // ── Initialisation (appelée depuis atelSwitch) ───────────────────────

    async function init() {
        // Charger les familles une seule fois
        if (ATL_THEME_FAMILLES.length === 0) {
            const r = await window.api('/api/couleurs_themes');
            ATL_THEME_FAMILLES = r.familles || [];
        }

        renderCouleursOptions();
        await chargerListe();
    }

    // ── Chargement de la liste des thèmes du cycle courant ───────────────

    async function chargerListe() {
        try {
            const r = await window.api(
                `/api/cycles/${encodeURIComponent(cycleCourant())}/themes/detail`
            );
            ATL_THEME_LIST = r.themes || [];
        } catch (e) {
            console.error(e);
            ATL_THEME_LIST = [];
        }
        renderListe();
        resetForm();
    }

    function renderListe() {
        const container = document.getElementById('atl-theme-list');
        if (ATL_THEME_LIST.length === 0) {
            container.innerHTML = `
                <div style="padding:20px;text-align:center;color:var(--text-muted);font-size:12px">
                    Aucun thème.<br>Cliquer sur « + Créer ».
                </div>
            `;
            return;
        }
        container.innerHTML = ATL_THEME_LIST.map(t => {
            const actif = ATL_THEME_EN_COURS && t.id === ATL_THEME_EN_COURS.id;
            const couleur = familleParSlug(t.code_couleur);
            // v0.12.2 — Migration vers le design system des sidebars :
            // .atl-item-pastille / .atl-item-id--compact / .atl-item-titre
            // / .atl-item-compteur. Plus de styles inline pour le layout.
            const pastille = couleur
                ? `<span class="atl-item-pastille" style="background:${couleur.hex_principal}"></span>`
                : `<span class="atl-item-pastille atl-item-pastille--vide"></span>`;
            const badge = t.nb_sequences > 0
                ? `<span class="atl-item-compteur">${t.nb_sequences} seq</span>`
                : '';
            return `
                <div class="atl-item${actif ? ' active' : ''}"
                     onclick="atelThemeSelectionner('${escHtml(t.id)}')">
                    ${pastille}
                    <span class="atl-item-id atl-item-id--compact">${escHtml(t.code)}</span>
                    <span class="atl-item-titre">${escHtml(t.nom)}</span>
                    ${badge}
                </div>
            `;
        }).join('');
    }

    // ── Rendu du sélecteur de couleurs (radio buttons avec pastilles) ────

    function renderCouleursOptions() {
        const container = document.getElementById('atl-theme-couleur-liste');
        if (!container) return;
        const options = [
            { slug: "",  libelle: "(aucune)", hex_principal: null },
            ...ATL_THEME_FAMILLES
        ];
        container.innerHTML = options.map((f, i) => `
            <label style="display:flex;align-items:center;gap:8px;padding:4px 8px;
                         border:1px solid var(--border);border-radius:4px;cursor:pointer">
                <input type="radio" name="atl-theme-couleur" value="${escHtml(f.slug)}"
                       onchange="atelThemeDirty()">
                <span style="display:inline-block;width:16px;height:16px;border-radius:50%;
                           background:${f.hex_principal || 'transparent'};
                           border:1px solid var(--border-medium)"></span>
                <span style="font-size:13px">${escHtml(f.libelle)}</span>
            </label>
        `).join('');
    }

    function familleParSlug(slug) {
        return ATL_THEME_FAMILLES.find(f => f.slug === slug) || null;
    }

    // ── Sélection d'un thème dans la liste ───────────────────────────────

    function selectionner(themeId) {
        if (ATL_THEME_DIRTY) {
            if (!confirm("Modifications non enregistrées. Continuer et perdre les changements ?")) {
                return;
            }
        }
        const t = ATL_THEME_LIST.find(x => x.id === themeId);
        if (!t) return;
        ATL_THEME_EN_COURS = t;
        afficherForm(t);
        ATL_THEME_DIRTY = false;
        renderListe();
    }

    function afficherForm(theme) {
        document.getElementById('atl-theme-empty').style.display = 'none';
        document.getElementById('atl-theme-form').style.display = '';
        document.getElementById('atl-theme-btn-save').style.display = '';
        document.getElementById('atl-theme-btn-suppr').style.display = theme.id ? '' : 'none';

        document.getElementById('atl-theme-toolbar-title').textContent =
            theme.id
                ? `Thème ${theme.code || '(nouveau)'} — ${theme.nom || ''}`
                : 'Nouveau thème';

        document.getElementById('atl-theme-code').value = theme.code || '';
        document.getElementById('atl-theme-nom').value = theme.nom || '';
        document.getElementById('atl-theme-description').value = theme.description || '';

        // Cocher la bonne couleur (par défaut : aucune)
        const radios = document.querySelectorAll('input[name="atl-theme-couleur"]');
        radios.forEach(r => {
            r.checked = (r.value === (theme.code_couleur || ''));
        });

        // Affichage infos séquences rattachées
        const info = document.getElementById('atl-theme-info-sequences');
        if (theme.id && theme.nb_sequences > 0) {
            info.style.display = '';
            info.textContent = `${theme.nb_sequences} séquence(s) du cycle sont rattachées à ce thème. ` +
                                `La suppression du thème ne sera possible qu'après détachement.`;
        } else {
            info.style.display = 'none';
        }

        // Listeners "dirty"
        for (const id of ['atl-theme-code', 'atl-theme-nom', 'atl-theme-description']) {
            document.getElementById(id).oninput = () => { ATL_THEME_DIRTY = true; };
        }
    }

    function resetForm() {
        ATL_THEME_EN_COURS = null;
        ATL_THEME_DIRTY = false;
        document.getElementById('atl-theme-form').style.display = 'none';
        document.getElementById('atl-theme-empty').style.display = '';
        document.getElementById('atl-theme-btn-save').style.display = 'none';
        document.getElementById('atl-theme-btn-suppr').style.display = 'none';
        document.getElementById('atl-theme-toolbar-title').textContent = 'Atelier Thème';
    }

    // ── Création d'un nouveau thème ──────────────────────────────────────

    function nouveau() {
        if (ATL_THEME_DIRTY) {
            if (!confirm("Modifications non enregistrées. Continuer ?")) return;
        }
        ATL_THEME_EN_COURS = {
            id: null,
            code: '',
            nom: '',
            code_couleur: '',
            description: '',
            nb_sequences: 0,
        };
        afficherForm(ATL_THEME_EN_COURS);
        ATL_THEME_DIRTY = false;
        renderListe();
        document.getElementById('atl-theme-code').focus();
    }

    // ── Sauvegarde (POST si nouveau, PUT sinon) ──────────────────────────

    async function sauvegarder() {
        const payload = {
            code:         document.getElementById('atl-theme-code').value.trim().toUpperCase(),
            nom:          document.getElementById('atl-theme-nom').value.trim(),
            description:  document.getElementById('atl-theme-description').value,
            code_couleur: getCouleurChoisie(),
        };

        if (!payload.code) { alert("Le code est obligatoire."); return; }
        if (!payload.nom)  { alert("Le nom est obligatoire."); return; }

        try {
            let r;
            if (ATL_THEME_EN_COURS && ATL_THEME_EN_COURS.id) {
                r = await window.api(`/api/themes/${encodeURIComponent(ATL_THEME_EN_COURS.id)}`, {
                    method: 'PUT',
                    body: payload,
                });
            } else {
                r = await window.api(
                    `/api/cycles/${encodeURIComponent(cycleCourant())}/themes`, {
                    method: 'POST',
                    body: payload,
                });
            }
            ATL_THEME_EN_COURS = r.theme;
            ATL_THEME_DIRTY = false;
            await chargerListe();
            selectionner(r.theme.id);
        } catch (e) {
            alert(messageErreur(e));
        }
    }

    function getCouleurChoisie() {
        const radios = document.querySelectorAll('input[name="atl-theme-couleur"]');
        for (const r of radios) if (r.checked) return r.value;
        return '';
    }

    // ── Suppression ──────────────────────────────────────────────────────

    async function supprimer() {
        if (!ATL_THEME_EN_COURS || !ATL_THEME_EN_COURS.id) return;
        if (!confirm(`Supprimer le thème « ${ATL_THEME_EN_COURS.nom} » ?`)) return;
        try {
            await window.api(`/api/themes/${encodeURIComponent(ATL_THEME_EN_COURS.id)}`, {
                method: 'DELETE',
            });
            await chargerListe();
        } catch (e) {
            alert(messageErreur(e));
        }
    }

    // ── Helpers ──────────────────────────────────────────────────────────

    function escHtml(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function messageErreur(e) {
        if (e && e.data && e.data.error) {
            const codes = {
                'doublon_code':      'Un thème avec ce code existe déjà dans le cycle.',
                'doublon_nom':       'Un thème avec ce nom existe déjà dans le cycle.',
                'en_usage':          'Impossible de supprimer : des séquences sont rattachées à ce thème.',
                'couleur_invalide':  'Code couleur invalide.',
                'code_vide':         'Le code est obligatoire.',
                'nom_vide':          'Le nom est obligatoire.',
                'theme_introuvable': 'Thème introuvable.',
                'cycle_introuvable': 'Cycle introuvable.',
            };
            return codes[e.data.code] || e.data.error;
        }
        return String(e);
    }

    // ── Exports globaux ──────────────────────────────────────────────────

    window.atelThemeInit        = init;
    window.atelThemeNouveau     = nouveau;
    window.atelThemeSelectionner = selectionner;
    window.atelThemeSauvegarder = sauvegarder;
    window.atelThemeSupprimer   = supprimer;
    window.atelThemeDirty       = () => { ATL_THEME_DIRTY = true; };
})();
