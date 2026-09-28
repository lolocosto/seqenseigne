/**
 * seqenseigne — Design System
 * Version : 0.1 — avril 2026
 * Adapté du design system "Parcours Avenir" (v0.67)
 * Police : Inter · Palette : bleu #2E5090
 */

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

/* ============================================================================
   1. VARIABLES
   ============================================================================ */
:root {
    --primary:         #2E5090;
    --primary-light:   #4472C4;
    --primary-dark:    #1e3a6f;
    --primary-bg:      #e8eef7;

    --success:         #70AD47;
    --success-bg:      #e8f5e9;
    --warning:         #d9a832;
    --warning-bg:      #fffbeb;
    --warning-text:    #7a4f10;
    --danger:          #dc2626;
    --danger-bg:       #fee2e2;
    --danger-dark:     #b91c1c;

    /* Séries d'exercices */
    --serie-F:         #5a8a1a;
    --serie-A:         #1d5fa8;
    --serie-E:         #5b4ab3;
    --serie-cours:     #0f766e;

    /* Niveaux de maîtrise */
    --niv-TB-bg:   #14532d; --niv-TB-text: #ffffff;  /* vert foncé */
    --niv-S-bg:    #dcfce7; --niv-S-text:  #166534;  /* vert clair */
    --niv-F-bg:    #fef9c3; --niv-F-text:  #854d0e;  /* jaune */
    --niv-I-bg:    #fee2e2; --niv-I-text:  #7f1d1d;  /* rouge */
    --niv-NE-bg:   #f0efe9; --niv-NE-text: #999;

    /* Surfaces */
    --bg-main:     #f5f7fa;
    --surface:     #ffffff;
    --surface-light: #e8eef7;
    --surface-medium:#d4dce8;

    /* Textes */
    --text:         #2c3e50;
    --text-light:   #7f8c8d;
    --text-muted:   #95a5a6;
    --text-on-primary: #ffffff;
    --text-secondary:  #475569;
    --text-tertiary:   #666;

    /* Bordures */
    --border:       #e1e8ed;
    --border-light: #ecf0f3;
    --border-medium:#cbd5e0;

    /* Typographie */
    --font-family:  'Inter', 'Segoe UI', system-ui, sans-serif;
    --font-2xs: 11px; --font-xs: 12px; --font-sm: 13px;
    --font-base: 14px; --font-md: 15px; --font-lg: 16px; --font-xl: 18px;
    --fw-normal: 400; --fw-medium: 500; --fw-semibold: 600;

    /* Espacements */
    --sp-xs: 4px; --sp-sm: 8px; --sp-md: 16px;
    --sp-lg: 24px; --sp-xl: 32px;

    /* Rayons */
    --radius-sm: 4px; --radius: 8px; --radius-lg: 12px; --radius-pill: 20px;

    /* Ombres */
    --shadow-sm: 0 1px 3px rgba(0,0,0,.08);
    --shadow:    0 2px 6px rgba(0,0,0,.10);
    --shadow-md: 0 4px 12px rgba(0,0,0,.12);

    /* Transitions */
    --t-fast: 150ms ease-in-out;
    --t-base: 200ms ease-in-out;

    /* Focus */
    --focus-ring: rgba(46,80,144,.15);
}

/* ============================================================================
   2. RESET & BASE
   ============================================================================ */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: var(--font-family);
    font-size: var(--font-base);
    background: var(--bg-main);
    color: var(--text);
    line-height: 1.5;
}

::-webkit-scrollbar       { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: var(--bg-main); }
::-webkit-scrollbar-thumb { background: var(--border-medium); border-radius: var(--radius-sm); }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

button { cursor: pointer; border: none; background: transparent; font-family: var(--font-family); font-size: var(--font-base); }
button:disabled { opacity: .5; cursor: not-allowed; }
input, select { font-family: var(--font-family); font-size: var(--font-sm); }
code { font-family: 'Consolas','Courier New',monospace; font-size: var(--font-xs); background: var(--surface-light); padding: 1px 5px; border-radius: var(--radius-sm); }

/* ============================================================================
   3. LAYOUT
   ============================================================================ */
header {
    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
    color: var(--text-on-primary);
    position: sticky; top: 0; z-index: 100;
    box-shadow: var(--shadow-md);
}
.header-inner { display: flex; align-items: center; gap: var(--sp-md); padding: 0 var(--sp-lg); height: 50px; flex-wrap: wrap; }
.logo { font-size: var(--font-lg); font-weight: var(--fw-semibold); letter-spacing: -.02em; color: var(--text-on-primary); }

.tabs { display: flex; gap: 2px; }
.tab { padding: 6px 16px; border: none; border-radius: var(--radius-sm); font-size: var(--font-sm); font-weight: var(--fw-medium); cursor: pointer; transition: background var(--t-fast); color: rgba(255,255,255,.8); background: transparent; }
.tab:hover  { background: rgba(255,255,255,.15); color: #fff; }
.tab.active { background: rgba(255,255,255,.25); color: #fff; }
.header-actions { display: flex; gap: var(--sp-sm); margin-left: auto; }

.tab-content { padding: var(--sp-md) var(--sp-lg); }
.two-col { display: grid; grid-template-columns: 300px minmax(0,1fr); gap: var(--sp-lg); align-items: start; }
@media (max-width: 768px) { .two-col { grid-template-columns: 1fr; } }

/* ============================================================================
   4. BOUTONS
   ============================================================================ */
.btn-prim {
    display: inline-flex; align-items: center; padding: 6px 14px;
    border: none; border-radius: var(--radius-sm); cursor: pointer;
    background: var(--primary); color: var(--text-on-primary);
    font-size: var(--font-sm); font-weight: var(--fw-medium); font-family: var(--font-family);
    transition: background var(--t-fast), transform var(--t-fast);
}
.btn-prim:hover:not(:disabled) { background: var(--primary-dark); transform: translateY(-1px); }
.btn-prim:active { transform: translateY(0); }

.btn-sm {
    padding: 5px 10px; border: 1px solid var(--border-medium); border-radius: var(--radius-sm);
    background: var(--surface); color: var(--text); font-size: var(--font-xs);
    transition: background var(--t-fast);
}
.btn-sm:hover { background: var(--surface-light); }

.btn-danger {
    padding: 5px 12px; border: 1px solid #fca5a5; border-radius: var(--radius-sm);
    background: var(--surface); color: var(--danger); font-size: var(--font-xs);
}
.btn-danger:hover { background: var(--danger-bg); }

.btn-calc {
    padding: 6px 12px; background: var(--warning-bg); border: 1px solid var(--warning);
    border-radius: var(--radius-sm); color: var(--warning-text);
    font-size: var(--font-xs); font-weight: var(--fw-medium);
}
.btn-calc:hover { background: #fef3c7; }

.btn-yes { padding: 4px 10px; background: #b45309; color: #fff; border: none; border-radius: var(--radius-sm); font-size: var(--font-2xs); }
.btn-no  { padding: 4px 10px; background: transparent; border: 1px solid var(--warning); border-radius: var(--radius-sm); font-size: var(--font-2xs); color: var(--warning-text); }

/* ============================================================================
   5. FORMULAIRES
   ============================================================================ */
input:not([type=file]):not([type=range]):not([type=checkbox]) {
    padding: 6px 10px; border: 1px solid var(--border-medium); border-radius: var(--radius-sm);
    background: var(--surface); color: var(--text);
    transition: border-color var(--t-fast), box-shadow var(--t-fast);
}
input:not([type=file]):not([type=range]):not([type=checkbox]):focus,
select:focus {
    outline: none; border-color: var(--primary);
    box-shadow: 0 0 0 3px var(--focus-ring);
}
select { padding: 6px 10px; border: 1px solid var(--border-medium); border-radius: var(--radius-sm); background: var(--surface); color: var(--text); cursor: pointer; }

.field-row { display: flex; align-items: center; gap: var(--sp-sm); margin-bottom: var(--sp-sm); }
.field-row label { width: 105px; font-size: var(--font-xs); color: var(--text-secondary); flex-shrink: 0; }
.field-row input, .field-row select { flex: 1; }

/* ============================================================================
   6. CARTES
   ============================================================================ */
.card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 14px 16px; margin-bottom: var(--sp-sm); }
.card h3 { font-size: var(--font-sm); font-weight: var(--fw-semibold); margin-bottom: var(--sp-sm); color: var(--text); }
.card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--sp-sm); }
.card-header h2 { font-size: var(--font-md); font-weight: var(--fw-semibold); color: var(--text); }
.import-zone { background: var(--bg-main); }

/* ============================================================================
   7. BARRE DE CALCUL & CONFIRMATION
   ============================================================================ */
.calc-bar { display: flex; align-items: center; gap: var(--sp-md); padding: var(--sp-sm) var(--sp-md); background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); margin-bottom: var(--sp-sm); flex-wrap: wrap; }
.confirm-strip { display: none; align-items: center; gap: var(--sp-sm); font-size: var(--font-xs); color: var(--warning-text); flex-wrap: wrap; }
.confirm-strip.show { display: flex; }

/* ============================================================================
   8. LISTE DES CLASSES
   ============================================================================ */
.classe-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 10px 14px; margin-bottom: 6px; cursor: pointer; display: flex; align-items: center; gap: var(--sp-sm); transition: border-color var(--t-fast), background var(--t-fast); }
.classe-card:hover  { background: var(--surface-light); border-color: var(--border-medium); }
.classe-card.active { border-color: var(--primary); background: var(--primary-bg); }
.classe-badge { background: var(--primary-bg); color: var(--primary); font-size: var(--font-2xs); font-weight: var(--fw-semibold); padding: 2px 8px; border-radius: var(--radius-pill); flex-shrink: 0; }
.classe-info { flex: 1; min-width: 0; }
.classe-nom  { font-weight: var(--fw-medium); font-size: var(--font-sm); }
.classe-meta { font-size: var(--font-xs); color: var(--text-muted); }

.eleve-item { display: flex; align-items: center; gap: var(--sp-sm); padding: 5px 0; border-bottom: 1px solid var(--border-light); font-size: var(--font-sm); }
.eleve-item:last-child { border-bottom: none; }
.eleve-item .nom { flex: 1; font-weight: var(--fw-medium); }
.eleve-num { font-size: var(--font-xs); color: var(--text-muted); width: 24px; text-align: right; flex-shrink: 0; }

/* ============================================================================
   9. BARRE D'OUTILS SUIVI
   ============================================================================ */
.toolbar { display: flex; align-items: center; gap: var(--sp-sm); margin-bottom: var(--sp-sm); flex-wrap: wrap; }
#classe-sel { min-width: 160px; font-weight: var(--fw-medium); }
#seq-sel    { min-width: 220px; }
.view-btns  { display: flex; gap: 2px; }
.vbtn { padding: 5px 12px; border: 1px solid var(--border-medium); border-radius: var(--radius-sm); background: var(--surface); font-size: var(--font-xs); cursor: pointer; color: var(--text-secondary); transition: all var(--t-fast); }
.vbtn:hover  { background: var(--surface-light); color: var(--text); }
.vbtn.active { background: var(--primary-bg); color: var(--primary); border-color: var(--primary-light); font-weight: var(--fw-medium); }

/* ============================================================================
   10. LÉGENDE
   ============================================================================ */
.legend { display: flex; align-items: center; gap: var(--sp-sm); margin-bottom: var(--sp-sm); font-size: var(--font-xs); color: var(--text-secondary); flex-wrap: wrap; }
.dot { display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin-right: 2px; }
.dot-F { background: var(--serie-F); }
.dot-A { background: var(--serie-A); }
.dot-E { background: var(--serie-E); }
.sep  { display: inline-block; width: 1px; height: 14px; background: var(--border-medium); margin: 0 4px; }
.pts  { color: var(--text-muted); font-size: 10px; margin-left: 2px; margin-right: 4px; }

/* ============================================================================
   11. BADGES DE NIVEAU
   ============================================================================ */
.badge, .badge-niveau {
    display: inline-flex; align-items: center; justify-content: center;
    min-width: 28px; padding: 2px 6px;
    border-radius: var(--radius-pill);
    font-size: var(--font-xs); font-weight: var(--fw-semibold); line-height: 1.4;
    white-space: nowrap;
}
.badge-TB, .b-TB { background: var(--niv-TB-bg); color: var(--niv-TB-text); }
.badge-S,  .b-S  { background: var(--niv-S-bg);  color: var(--niv-S-text); }
.badge-F,  .b-F  { background: var(--niv-F-bg);  color: var(--niv-F-text); }
.badge-I,  .b-I  { background: var(--niv-I-bg);  color: var(--niv-I-text); }
.badge-NE, .b-NE { background: var(--niv-NE-bg); color: var(--niv-NE-text); }

/* ============================================================================
   12. TABLEAU DE SUIVI
   ============================================================================ */
.tbl-wra