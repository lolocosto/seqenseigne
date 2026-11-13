/**
 * static/atelier_carte_mentale.js — v0.55.0
 *
 * Atelier « Carte mentale » (portée Séquence) : une carte mentale par partie de
 * séquence, pour tous les modèles de référentiel (Fiches de résumé par objectif et
 * Notions et méthodes). Demande de Laurent du 12 novembre 2026 (décision CM-ATELIER,
 * doc/redemarrage_v0_55_0.md).
 *
 *   - niveau et séquence : sélecteurs de la portée Séquence (ATL_FILTRE_NIVEAU/SEQ) ;
 *   - liste des parties de la séquence, avec l'état de la carte et son nombre de branches ;
 *   - éditeur LaTeX (titre, état, source) : Enregistrer, Enregistrer et voir (aperçu
 *     à compléter ou complet), Supprimer ;
 *   - Compiler : la carte de la partie, ou toutes celles de la séquence.
 *
 * Routes : GET/PUT/DELETE /api/v2/livret-sequence/<niveau>/<séquence>/cartes-mentales[/<n>] ;
 * PDF : …/rendu-pdf?document=cartes_mentales&version=…&partie=… (même générateur que
 * « Tout compiler » et la publication).
 */
(function (root) {
  'use strict';

  // ── Logique pure (testée par tests_js/atelier_carte_mentale.test.js) ──────────

  function nbBranches(latex) {
    return ((latex || '').match(/\\seqCMBranche(?![A-Za-z])/g) || []).length;
  }

  function urlListe(niveau, sequence, numero) {
    return `/api/v2/livret-sequence/${encodeURIComponent(niveau)}`
         + `/${encodeURIComponent(sequence)}/cartes-mentales`
         + (numero ? `/${encodeURIComponent(numero)}` : '');
  }

  function urlPdf(niveau, sequence, version, partie) {
    const q = [`document=cartes_mentales`,
               `version=${version === 'corrigee' ? 'corrigee' : 'eleve'}`];
    if (partie) q.push(`partie=${encodeURIComponent(partie)}`);
    return `/api/v2/livret-sequence/${encodeURIComponent(niveau)}`
         + `/${encodeURIComponent(sequence)}/rendu-pdf?` + q.join('&');
  }

  function libelleEtat(carte) {
    if (!carte) return 'sans carte';
    return (carte.etat_code === 'valide' ? 'validée' : 'en cours')
         + ` · ${nbBranches(carte.latex)} branche(s)`;
  }

  const MODELE = '\\begin{seqCarteMentaleSix}{Titre central}\n'
    + '  \\seqCMBranche{Branche 1}{contenu avec un \\seqACompleter{trou}}\n'
    + '  \\seqCMBranche{Branche 2}{contenu}\n'
    + '  \\seqCMBranche{Branche 3}{contenu}\n'
    + '  \\seqCMBranche{Branche 4}{contenu}\n'
    + '\\end{seqCarteMentaleSix}';

  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // ── Atelier ──────────────────────────────────────────────────────────────────

  class AtelierCarteMentale {
    constructor() {
      this.parties = [];
      this.modifiable = true;
      this.numero = null;            // partie sélectionnée
      this._blob = null;
    }

    _el(id) { return document.getElementById(id); }

    _seq() {
      return { niveau: root.ATL_FILTRE_NIVEAU || '', sequence: root.ATL_FILTRE_SEQ || '' };
    }

    _toast(msg, type) {
      if (typeof root.showToast === 'function') root.showToast(msg, type);
      const m = this._el('atl-cm-message');
      if (m) m.textContent = msg;
    }

    async _json(method, url, body) {
      const r = await fetch(url, {
        method, headers: body ? { 'Content-Type': 'application/json' } : {},
        body: body ? JSON.stringify(body) : undefined,
      });
      const data = await r.json().catch(() => ({}));
      return { ok: r.ok, status: r.status, data };
    }

    async chargerListe() {
      const { niveau, sequence } = this._seq();
      const liste = this._el('atl-cm-liste');
      if (!liste) return;
      if (!niveau || !sequence) {
        this.parties = [];
        liste.innerHTML = '<div class="atl-vide">Choisis un niveau et une séquence.</div>';
        this._afficherEditeur();
        return;
      }
      const rep = await this._json('GET', urlListe(niveau, sequence));
      if (!rep.ok) {
        this.parties = [];
        liste.innerHTML = `<div class="atl-vide">${esc(rep.data.message || 'Séquence absente de l\'atelier.')}</div>`;
        this._afficherEditeur();
        return;
      }
      this.parties = rep.data.parties || [];
      this.modifiable = rep.data.modifiable !== false;
      if (!this.parties.some(p => p.numero === this.numero)) {
        this.numero = this.parties.length ? this.parties[0].numero : null;
      }
      this._afficherListe();
      this._afficherEditeur();
    }

    _afficherListe() {
      const liste = this._el('atl-cm-liste');
      if (!liste) return;
      liste.innerHTML = this.parties.map(p => `
        <div class="asm-item atl-cm-item${p.numero === this.numero ? ' active' : ''}"
             data-numero="${p.numero}" onclick="ATELIER_CARTE_MENTALE.choisir(${p.numero})"
             style="cursor:pointer;padding:4px 6px">
          <strong>Partie ${p.numero}</strong>${p.libelle ? ' — ' + esc(p.libelle) : ''}
          <div style="font-size:11px;color:var(--text-muted)">${esc(p.carte ? (p.carte.titre || '(sans titre)') : '')}
            <span class="atl-cm-etat">${esc(libelleEtat(p.carte))}</span></div>
        </div>`).join('') || '<div class="atl-vide">Aucune partie.</div>';
    }

    _partie() { return this.parties.find(p => p.numero === this.numero) || null; }

    choisir(numero) {
      this.numero = numero;
      this._afficherListe();
      this._afficherEditeur();
    }

    _afficherEditeur() {
      const p = this._partie();
      const titre = this._el('atl-cm-titre-partie');
      if (titre) titre.textContent = p ? `Carte mentale — partie ${p.numero}`
        + (this.modifiable ? '' : ' (séquence validée : lecture seule)') : 'Carte mentale';
      const c = (p && p.carte) || null;
      const set = (id, v) => { const e = this._el(id); if (e) e.value = v; };
      set('atl-cm-titre', c ? c.titre : '');
      set('atl-cm-etat-code', c ? c.etat_code : 'en_cours');
      set('atl-cm-latex', c ? c.latex : (p ? MODELE : ''));
      ['atl-cm-btn-enregistrer', 'atl-cm-btn-voir', 'atl-cm-btn-supprimer'].forEach(id => {
        const b = this._el(id);
        if (b) b.disabled = !p || !this.modifiable || (id === 'atl-cm-btn-supprimer' && !c);
      });
      const m = this._el('atl-cm-message');
      if (m) m.textContent = p && !c ? 'Pas encore de carte : modèle proposé.' : '';
    }

    async enregistrer(voir) {
      const { niveau, sequence } = this._seq();
      const p = this._partie();
      if (!p) return;
      const rep = await this._json('PUT', urlListe(niveau, sequence, p.numero), {
        titre: this._el('atl-cm-titre').value,
        latex: this._el('atl-cm-latex').value,
        etat_code: this._el('atl-cm-etat-code').value,
      });
      if (!rep.ok) {
        this._toast('Non enregistrée : ' + (rep.data.message || rep.data.error || rep.status), 'erreur');
        return;
      }
      const av = rep.data.avertissements || [];
      await this.chargerListe();
      this._toast(`Carte ${rep.data.etat || 'enregistrée'}` + (av.length ? ' — attention : ' + av.join(' ; ') : ''));
      if (voir) await this.compiler(true);
    }

    async supprimer() {
      const { niveau, sequence } = this._seq();
      const p = this._partie();
      if (!p || !p.carte) return;
      if (root.confirm && !root.confirm(`Supprimer la carte mentale de la partie ${p.numero} ?`)) return;
      const rep = await this._json('DELETE', urlListe(niveau, sequence, p.numero));
      if (!rep.ok) { this._toast('Erreur : ' + (rep.data.message || rep.status), 'erreur'); return; }
      await this.chargerListe();
      this._toast('Carte supprimée.');
    }

    // seule = true : la carte de la partie choisie ; sinon selon le sélecteur « Compiler ».
    async compiler(seule) {
      const { niveau, sequence } = this._seq();
      if (!niveau || !sequence) return;
      const version = (this._el('atl-cm-version') || {}).value || 'eleve';
      const portee = seule ? 'partie' : ((this._el('atl-cm-portee') || {}).value || 'partie');
      const partie = portee === 'partie' && this.numero ? this.numero : '';
      const etat = this._el('atl-cm-rendu-etat');
      if (etat) etat.textContent = 'Compilation en cours…';
      try {
        const r = await fetch(urlPdf(niveau, sequence, version, partie), { method: 'POST' });
        if (!r.ok) {
          const d = await r.json().catch(() => ({}));
          let msg = d.message || d.error || `Erreur HTTP ${r.status}`;
          if (Array.isArray(d.erreurs) && d.erreurs.length) {
            msg += ' — ' + d.erreurs.slice(0, 3).map(e => `ligne ${e.ligne || '?'} : ${e.message}`).join(' ; ');
          }
          if (etat) etat.textContent = '✗ ' + msg;
          return;
        }
        const blob = await r.blob();
        if (this._blob) { try { URL.revokeObjectURL(this._blob); } catch (_) {} }
        this._blob = URL.createObjectURL(blob);
        const iframe = this._el('atl-cm-pdf');
        if (iframe) {
          iframe.src = '/static/vendor/pdfjs/web/viewer.html?file=' + encodeURIComponent(this._blob);
          iframe.style.display = 'block';
        }
        if (etat) etat.textContent = '✓ Compilé';
      } catch (e) {
        if (etat) etat.textContent = '✗ Erreur réseau : ' + (e.message || e);
      }
    }
  }

  root.CarteMentalePur = { nbBranches, urlListe, urlPdf, libelleEtat, MODELE };
  root.AtelierCarteMentale = AtelierCarteMentale;
  root.ATELIER_CARTE_MENTALE = new AtelierCarteMentale();
  root.atelCarteMentaleInit = () => root.ATELIER_CARTE_MENTALE.chargerListe();
})(typeof window !== 'undefined' ? window : globalThis);
