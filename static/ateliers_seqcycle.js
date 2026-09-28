/**
 * static/ateliers_seqcycle.js — R3.
 *
 * Atelier Séquence (cycle) : CRUD complet des séquences du cycle.
 * Sidebar triée par numéro, chaque ligne affiche une pastille de la
 * couleur du thème rattaché.
 *
 * Dépendances : chargé après app.js. Utilise window.api et les familles
 * de couleurs exposées par l'API R2 (/api/couleurs_themes).
 */

(function () {
    'use strict';

    // ── État ─────────────────────────────────────────────────────────────

    let ATL_SC_FAMILLES = [];
    let ATL_SC_LIST = [];
    let ATL_SC_THEMES = [];       // thèmes du cycle courant (pour le select)
    let ATL_SC_EN_COURS = null;
    let ATL_SC_DIRTY = false;

    // Le cycle courant n'est plus stocké localement : on le lit depuis la
    // portée Cycle (refonte v0.10 — moule commun).
    function cycleCourant() {
        const sel = (window.ATL_SELECTIONS && window.ATL_SELECTIONS.cycle) || {};
        return sel.cycle || 'C04';
    }

    // ── Init ─────────────────────────────────────────────────────────────

    async function init() {
        // Familles de couleurs (chargées une seule fois)
        if (ATL_SC_FAMILLES.length === 0) {
            const r = await window.api('/api/couleurs_themes');
            ATL_SC_FAMILLES = r.familles || [];
        }

        await chargerToutPourCycle();
    }

    async function chargerToutPourCycle() {
        // Charger thèmes (pour le sélecteur du formulaire)
        try {
            const rt = await window.api(
                `/api/cycles/${encodeURIComponent(cycleCourant())}/themes/detail`
            );
            ATL_SC_THEMES = rt.themes || [];
        } catch (e) {
            ATL_SC_THEMES = [];
        }
        remplirSelectThemes();

        // Charger les séquences
        try {
            const rs = await window.api(
                `/api/cycles/${encodeURIComponent(cycleCourant())}/sequences/detail`
            );
            ATL_SC_LIST = rs.sequences || [];
        } catch (e) {
            ATL_SC_LIST = [];
        }
        renderListe();
        resetForm();
    }

    function remplirSelectThemes() {
        const sel = document.getElementById('atl-seqcycle-theme-sel');
        if (!sel) return;
        sel.innerHTML = '<option value="">— Aucun thème —</option>'
            + ATL_SC_THEMES.map(t =>
                `<option value="${escHtml(t.id)}">${escHtml(t.code)} — ${escHtml(t.nom)}</option>`
              ).join('');
    }

    // ── Liste ────────────────────────────────────────────────────────────

    function renderListe() {
        const container = document.getElementById('atl-seqcycle-list');
        if (ATL_SC_LIST.length === 0) {
            container.innerHTML = `
                <div style="padding:20px;text-align:center;color:var(--text-muted);font-size:12px">
                    Aucune séquence.<br>Cliquer sur « + Créer ».
                </div>
            `;
            return;
        }
        container.innerHTML = ATL_SC_LIST.map(s => {
            const actif = ATL_SC_EN_COURS && s.id === ATL_SC_EN_COURS.id;
            const famille = familleParSlug(s.theme_couleur);
            // v0.12.2 — Migration vers le design system des sidebars.
            // Particularité conservée : pastille grise (`#ddd`) quand
            // pas de thème (et pas invisible comme pour Thème) — utile
            // visuellement pour signaler l'absence de rattachement.
            const pastille = famille
                ? `<span class="atl-item-pastille" style="background:${famille.hex_principal}" title="${escHtml(s.theme_nom || '')}"></span>`
                : `<span class="atl-item-pastille" style="background:#ddd" title="Pas de thème"></span>`;
            const badge = s.nb_atomes_total > 0
                ? `<span class="atl-item-compteur">${s.nb_atomes_total}</span>`
                : '';
            return `
                <div class="atl-item${actif ? ' active' : ''}"
                     onclick="atelSeqCycleSelectionner('${escHtml(s.id)}')">
                    ${pastille}
                    <span class="atl-item-id atl-item-id--compact">${escHtml(s.code)}</span>
                    <span class="atl-item-titre">${escHtml(s.nom)}</span>
                    ${badge}
                </div>
            `;
        }).join('');
    }

    function familleParSlug(slug) {
        if (!slug) return null;
        return ATL_SC_FAMILLES.find(f => f.slug === slug) || null;
    }

    // ── Sélection / formulaire ───────────────────────────────────────────

    function selectionner(seqId) {
        if (ATL_SC_DIRTY) {
            if (!confirm("Modifications non enregistrées. Continuer ?")) return;
        }
        const s = ATL_SC_LIST.find(x => x.id === seqId);
        if (!s) return;
        ATL_SC_EN_COURS = s;
        afficherForm(s);
        ATL_SC_DIRTY = false;
        renderListe();
    }

    function afficherForm(seq) {
        document.getElementById('atl-seqcycle-empty').style.display = 'none';
        document.getElementById('atl-seqcycle-form').style.display = '';
        document.getElementById('atl-seqcycle-btn-save').style.display = '';
        document.getElementById('atl-seqcycle-btn-suppr').style.display =
            seq.id ? '' : 'none';

        document.getElementById('atl-seqcycle-toolbar-title').textContent =
            seq.id
                ? `Séquence ${seq.code || '(nouvelle)'} — ${seq.nom || ''}`
                : 'Nouvelle séquence';

        document.getElementById('atl-seqcycle-numero').value = seq.numero ?? '';
        document.getElementById('atl-seqcycle-code').value = seq.code || '';
        document.getElementById('atl-seqcycle-nom').value = seq.nom || '';
        document.getElementById('atl-seqcycle-theme-sel').value = seq.theme_id || '';

        // Infos atomes
        const info = document.getElementById('atl-seqcycle-info-atomes');
        if (seq.id && seq.nb_atomes_total > 0) {
            const a = seq.atomes || {};
            const parties = [];
            if (a.objectifs) parties.push(`${a.objectifs} objectif(s)`);
            if (a.methodes)  parties.push(`${a.methodes} méthode(s)`);
            if (a.notions)   parties.push(`${a.notions} notion(s)`);
            if (a.exercices) parties.push(`${a.exercices} exercice(s)`);
            info.style.display = '';
            info.textContent = "Cette séquence est référencée par : "
                + parties.join(", ") + ". La suppression sera refusée tant que "
                + "ces atomes existent.";
        } else {
            info.style.display = 'none';
        }

        // Listeners dirty
        for (const id of ['atl-seqcycle-numero', 'atl-seqcycle-code',
                          'atl-seqcycle-nom', 'atl-seqcycle-theme-sel']) {
            const el = document.getElementById(id);
            el.oninput  = () => { ATL_SC_DIRTY = true; };
            el.onchange = () => { ATL_SC_DIRTY = true; };
        }
    }

    function resetForm() {
        ATL_SC_EN_COURS = null;
        ATL_SC_DIRTY = false;
        document.getElementById('atl-seqcycle-form').style.display = 'none';
        document.getElementById('atl-seqcycle-empty').style.display = '';
        document.getElementById('atl-seqcycle-btn-save').style.display = 'none';
        document.getElementById('atl-seqcycle-btn-suppr').style.display = 'none';
        document.getElementById('atl-seqcycle-toolbar-title').textContent =
            'Atelier Séquence (cycle)';
    }

    // ── Nouveau ──────────────────────────────────────────────────────────

    function nouveau() {
        if (ATL_SC_DIRTY) {
            if (!confirm("Modifications non enregistrées. Continuer ?")) return;
        }
        // Proposer le prochain numéro libre
        const nums = ATL_SC_LIST.map(s => s.numero);
        let prochainNum = 1;
        while (nums.includes(prochainNum)) prochainNum++;

        ATL_SC_EN_COURS = {
            id: null,
            code: '',
            numero: prochainNum,
            nom: '',
            theme_id: null,
            nb_atomes_total: 0,
            atomes: {},
        };
        afficherForm(ATL_SC_EN_COURS);
        ATL_SC_DIRTY = false;
        renderListe();
        document.getElementById('atl-seqcycle-code').focus();
    }

    // ── Sauvegarde ───────────────────────────────────────────────────────

    async function sauvegarder() {
        const numStr = document.getElementById('atl-seqcycle-numero').value;
        const payload = {
            code:     document.getElementById('atl-seqcycle-code').value.trim().toUpperCase(),
            numero:   numStr ? parseInt(numStr, 10) : null,
            nom:      document.getElementById('atl-seqcycle-nom').value.trim(),
            theme_id: document.getElementById('atl-seqcycle-theme-sel').value || null,
        };

        if (!payload.code) { alert("Le code est obligatoire."); return; }
        if (!payload.numero || payload.numero <= 0) {
            alert("Le numéro doit être un entier positif."); return;
        }
        if (!payload.nom)  { alert("Le nom est obligatoire."); return; }

        try {
            let r;
            if (ATL_SC_EN_COURS && ATL_SC_EN_COURS.id) {
                // Pour un PUT, passer explicitement detacher_theme=true si
                // on veut supprimer un thème
                const body = { ...payload };
                if (!payload.theme_id && ATL_SC_EN_COURS.theme_id) {
                    body.detacher_theme = true;
                    delete body.theme_id;
                }
                r = await window.api(
                    `/api/sequences_du_cycle/${encodeURIComponent(ATL_SC_EN_COURS.id)}`,
                    { method: 'PUT', body: body }
                );
            } else {
                r = await window.api(
                    `/api/cycles/${encodeURIComponent(cycleCourant())}/sequences`,
                    { method: 'POST', body: payload }
                );
            }
            ATL_SC_EN_COURS = r.sequence;
            ATL_SC_DIRTY = false;
            await chargerToutPourCycle();
            selectionner(r.sequence.id);
        } catch (e) {
            alert(messageErreur(e));
        }
    }

    // ── Suppression ──────────────────────────────────────────────────────

    async function supprimer() {
        if (!ATL_SC_EN_COURS || !ATL_SC_EN_COURS.id) return;
        if (!confirm(`Supprimer la séquence « ${ATL_SC_EN_COURS.nom} » ?`)) return;
        try {
            await window.api(
                `/api/sequences_du_cycle/${encodeURIComponent(ATL_SC_EN_COURS.id)}`,
                { method: 'DELETE' }
            );
            await chargerToutPourCycle();
        } catch (e) {
            alert(messageErreur(e));
        }
    }

    // ── Helpers ──────────────────────────────────────────────────────────

    function escHtml(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function messageErreur(e) {
        if (e && e.data && e.data.error) {
            const codes = {
                'doublon_code':         "Une séquence avec ce code existe déjà dans le cycle.",
                'doublon_numero':       "Une séquence avec ce numéro existe déjà dans le cycle.",
                'theme_invalide':       "Thème invalide ou dans un autre cycle.",
                'code_vide':            "Le code est obligatoire.",
                'numero_vide':          "Le numéro est obligatoire.",
                'numero_invalide':      "Le numéro doit être un entier positif.",
                'nom_vide':             "Le nom est obligatoire.",
                'en_usage':             e.data.error,
                'sequence_introuvable': "Séquence introuvable.",
                'cycle_introuvable':    "Cycle introuvable.",
            };
            return codes[e.data.code] || e.data.error;
        }
        return String(e);
    }

    // ── Exports ──────────────────────────────────────────────────────────

    window.atelSeqCycleInit        = init;
    window.atelSeqCycleNouveau     = nouveau;
    window.atelSeqCycleSelectionner = selectionner;
    window.atelSeqCycleSauvegarder = sauvegarder;
    window.atelSeqCycleSupprimer   = supprimer;
})();
