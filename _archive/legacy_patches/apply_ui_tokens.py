#!/usr/bin/env python3
"""
Script de aplicacion automatizada del Design System de Tokens para Santa Base.
Reemplaza el bloque CSS y la estructura HTML de la toolbar y KPIs segun AUDITORIA-UI-SANTANDER-DASHBOARD.md.
"""

import sys
import re

APP_PY_PATH = "app.py"

NEW_CSS = """  <style>
    :root {
      /* Superficies y Fondos */
      --bg-app: #080d1a;
      --bg-card: #0f172a;
      --bg-surface: #131c31;
      --bg-surface-elevated: #1e293b;
      --bg-row-hover: #162238;
      --bg-row-selected: #1e3a5f;
      --excel-selection-bg: rgba(2, 132, 199, 0.15);

      /* Bordes y Divisiones */
      --border: #1e293b;
      --border-subtle: #1e293d;
      --border-strong: #334155;
      --border-focus: #0284c7;

      /* Radios de curvatura */
      --radius-sm: 4px;
      --radius-md: 6px;
      --radius-lg: 8px;
      --radius-full: 9999px;

      /* Sistema Semantico de Color (3 Niveles) */
      /* Nivel 1: Primario (Accion Principal / Foco) */
      --color-primary: #0284c7;
      --color-primary-hover: #0369a1;
      --color-primary-active: #075985;
      --color-primary-ring: rgba(2, 132, 199, 0.35);

      /* Nivel 2: Secundario / Neutro (Acciones frecuentes, Toolbar, Copia) */
      --color-neutral-bg: #1e293b;
      --color-neutral-border: #334155;
      --color-neutral-hover: #27354a;
      --color-neutral-text: #e2e8f0;

      /* Nivel 3: Destructivo / Peligro (Logout, Reset, Alertas) */
      --color-danger: #ec0000;
      --color-danger-hover: #dc2626;
      --color-danger-subtle: rgba(236, 0, 0, 0.12);
      --color-danger-border: rgba(236, 0, 0, 0.35);

      /* Marca Santander (Solo badge oficial) */
      --santander: #ec0000;

      /* Tipografia */
      --font-mono: 'JetBrains Mono', monospace;
      --font-sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      --font-size-base: 13px;
      --font-size-cell: 12.5px;
      --font-size-header: 11.5px;
      --font-size-btn: 12.5px;
      --font-size-small: 11px;
      --font-size-kpi-val: 16px;
      --font-size-kpi-lbl: 10px;

      --text: #f1f5f9;
      --text-muted: #94a3b8;
      --text-dim: #64748b;

      /* Dimensiones de Celdas (Respirar) */
      --cell-h: 36px;
      --cell-pad-x: 10px;
      --cell-pad-y: 6px;

      /* Microinteracciones */
      --transition-fast: all 140ms ease;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg-app);
      color: var(--text);
      font-family: var(--font-sans);
      font-size: var(--font-size-base);
      line-height: 1.4;
      padding: 8px 12px;
      user-select: none;
      height: 100vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    /* Lock Screen Overlay */
    #lock-screen {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(8, 13, 26, 0.96);
      backdrop-filter: blur(12px);
      z-index: 9999;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: opacity 0.3s ease;
    }
    #lock-screen.hidden { display: none; pointer-events: none; }
    .lock-card {
      background: var(--bg-card);
      border: 1px solid var(--border-strong);
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 35px rgba(2, 132, 199, 0.1);
      border-radius: var(--radius-lg);
      padding: 34px 30px;
      width: 380px;
      max-width: 90vw;
      text-align: center;
    }
    .lock-icon-circle {
      width: 54px;
      height: 54px;
      background: rgba(2, 132, 199, 0.12);
      border: 1px solid rgba(2, 132, 199, 0.3);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 24px;
      margin: 0 auto 16px;
      color: var(--color-primary);
    }
    .lock-title {
      font-size: 18px;
      font-weight: 800;
      color: #fff;
      margin-bottom: 6px;
      letter-spacing: -0.2px;
    }
    .lock-subtitle {
      font-size: 12px;
      color: var(--text-muted);
      margin-bottom: 22px;
      line-height: 1.45;
    }
    .password-input-group {
      position: relative;
      margin-bottom: 16px;
    }
    .password-input {
      width: 100%;
      background: var(--bg-app);
      border: 1px solid var(--border-strong);
      color: #fff;
      padding: 11px 42px 11px 14px;
      border-radius: var(--radius-md);
      font-size: 13px;
      font-family: var(--font-mono);
      outline: none;
      transition: var(--transition-fast);
    }
    .password-input:focus {
      border-color: var(--border-focus);
      box-shadow: 0 0 0 3px var(--color-primary-ring);
    }
    .eye-btn {
      position: absolute;
      right: 12px;
      top: 50%;
      transform: translateY(-50%);
      background: transparent;
      border: none;
      color: var(--text-dim);
      cursor: pointer;
      font-size: 16px;
      padding: 4px;
      transition: var(--transition-fast);
    }
    .eye-btn:hover { color: #cbd5e1; }
    .btn-login {
      width: 100%;
      background: var(--color-primary);
      color: #fff;
      border: none;
      padding: 11px;
      border-radius: var(--radius-md);
      font-weight: 600;
      font-size: 13px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      transition: var(--transition-fast);
      box-shadow: 0 2px 8px rgba(2, 132, 199, 0.25);
    }
    .btn-login:hover {
      background: var(--color-primary-hover);
      box-shadow: 0 4px 14px rgba(2, 132, 199, 0.4);
    }
    .lock-error {
      margin-top: 12px;
      color: #f87171;
      font-size: 11.5px;
      display: none;
    }
    .lock-error.show { display: block; }

    /* Top Bar */
    .top-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
      gap: 12px;
    }
    .brand-group {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-shrink: 0;
    }
    .badge-santander {
      background: var(--santander);
      color: #fff;
      font-weight: 800;
      font-size: 10.5px;
      padding: 2px 7px;
      border-radius: var(--radius-sm);
      letter-spacing: 0.5px;
    }
    .badge-excel {
      background: #064e3b;
      color: #34d399;
      border: 1px solid #059669;
      font-size: 10px;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: var(--radius-sm);
    }
    .app-title {
      font-size: 15px;
      font-weight: 700;
      color: #fff;
      letter-spacing: -0.3px;
    }
    .stats-group {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .kpi-card {
      background: var(--bg-surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 3px 10px;
      display: inline-flex;
      flex-direction: column;
      align-items: flex-start;
      min-width: 82px;
      transition: var(--transition-fast);
    }
    .kpi-card:hover {
      border-color: var(--border-strong);
      background: var(--bg-surface-elevated);
    }
    .kpi-label {
      font-size: var(--font-size-kpi-lbl);
      color: var(--text-dim);
      font-weight: 700;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      line-height: 1.1;
      margin-bottom: 1px;
    }
    .kpi-val {
      font-family: var(--font-mono);
      font-size: var(--font-size-kpi-val);
      font-weight: 700;
      color: #f1f5f9;
      line-height: 1.1;
    }
    .kpi-card.curp .kpi-val { color: #34d399; }
    .kpi-card.calc .kpi-val { color: #38bdf8; }
    .kpi-card.missing .kpi-val { color: #fb923c; }
    .kpi-card.results .kpi-val { color: #facc15; }

    /* Compatibilidad retrospectiva para stat-pill */
    .stat-pill {
      background: var(--bg-surface);
      border: 1px solid var(--border);
      padding: 4px 8px;
      border-radius: var(--radius-sm);
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-size: var(--font-size-small);
      font-family: var(--font-mono);
    }
    .stat-pill span { font-weight: 700; color: #38bdf8; }
    .stat-pill.curp span { color: #34d399; }
    .stat-pill.results span { color: #fbbf24; }

    .btn-logout {
      background: transparent;
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 6px 10px;
      border-radius: var(--radius-sm);
      cursor: pointer;
      font-size: var(--font-size-small);
      font-weight: 600;
      transition: var(--transition-fast);
      margin-left: 4px;
    }
    .btn-logout:hover {
      color: #fff;
      background: var(--color-danger);
      border-color: var(--color-danger);
      box-shadow: 0 0 10px rgba(236, 0, 0, 0.4);
    }

    /* Formula Bar */
    .formula-bar-container {
      display: flex;
      align-items: center;
      gap: 8px;
      background: var(--bg-surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 5px 10px;
      margin: 6px 0;
      flex-shrink: 0;
    }
    .cell-coord-box {
      background: var(--bg-app);
      border: 1px solid var(--border-strong);
      color: var(--color-primary);
      font-family: var(--font-mono);
      font-weight: 700;
      font-size: var(--font-size-small);
      padding: 3px 10px;
      border-radius: var(--radius-sm);
      min-width: 140px;
      text-align: center;
      letter-spacing: 0.5px;
      white-space: nowrap;
    }
    .fx-symbol {
      color: var(--text-muted);
      font-family: var(--font-mono);
      font-weight: 700;
      font-style: italic;
      font-size: 13px;
      padding: 0 3px;
    }
    .formula-input {
      flex: 1;
      background: var(--bg-app);
      border: 1px solid var(--border-strong);
      color: #fff;
      font-family: var(--font-mono);
      font-size: var(--font-size-cell);
      padding: 4px 10px;
      border-radius: var(--radius-sm);
      outline: none;
      transition: var(--transition-fast);
    }
    .formula-input:focus {
      border-color: var(--border-focus);
      box-shadow: 0 0 0 2px var(--color-primary-ring);
    }
    .formula-input.readonly {
      color: var(--text-muted);
      background: rgba(13, 18, 28, 0.6);
      cursor: not-allowed;
    }
    .keyboard-hint {
      font-size: 11px;
      color: var(--text-muted);
      white-space: nowrap;
      display: flex;
      align-items: center;
      gap: 5px;
    }
    .kbd {
      background: #1e293b;
      border: 1px solid #334155;
      padding: 2px 5px;
      border-radius: 3px;
      font-family: var(--font-mono);
      font-size: 10px;
      color: #cbd5e1;
    }

    /* Toolbar con 4 Clusters Visuales y Segmented Control */
    .toolbar {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 6px;
      background: var(--bg-card);
      padding: 6px 10px;
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      flex-shrink: 0;
      overflow-x: auto;
    }
    .tb-group {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      white-space: nowrap;
      flex-shrink: 0;
    }
    .tb-sep {
      width: 1px;
      height: 24px;
      background: var(--border-strong);
      margin: 0 4px;
      flex-shrink: 0;
    }
    /* Segmented Control de Filtros Predefinidos */
    .filter-tabs {
      display: inline-flex;
      background: var(--bg-app);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 2px;
      gap: 2px;
    }
    .tab-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 4px 10px;
      border-radius: var(--radius-sm);
      cursor: pointer;
      font-size: var(--font-size-small);
      font-weight: 500;
      transition: var(--transition-fast);
    }
    .tab-btn:hover {
      color: #fff;
      background: rgba(255, 255, 255, 0.05);
    }
    .tab-btn.active {
      background: var(--color-primary);
      color: #fff;
      font-weight: 600;
      box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
    }
    .global-search {
      background: var(--bg-app);
      border: 1px solid var(--border-strong);
      color: #fff;
      padding: 5px 10px;
      border-radius: var(--radius-sm);
      font-size: var(--font-size-small);
      width: 210px;
      outline: none;
      transition: var(--transition-fast);
    }
    .global-search:focus {
      border-color: var(--border-focus);
      box-shadow: 0 0 0 2px var(--color-primary-ring);
    }

    /* Sistema de Botones Semanticos (3 Niveles) */
    .btn {
      background: var(--color-neutral-bg);
      color: var(--color-neutral-text);
      border: 1px solid var(--color-neutral-border);
      padding: 5px 10px;
      border-radius: var(--radius-sm);
      font-size: var(--font-size-btn);
      font-weight: 500;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      transition: var(--transition-fast);
      white-space: nowrap;
    }
    .btn:hover {
      background: var(--color-neutral-hover);
      border-color: #475569;
      color: #fff;
    }
    .btn-primary {
      background: var(--color-primary) !important;
      border-color: var(--color-primary) !important;
      color: #fff !important;
      font-weight: 600;
    }
    .btn-primary:hover {
      background: var(--color-primary-hover) !important;
      border-color: var(--color-primary-hover) !important;
      box-shadow: 0 2px 8px rgba(2, 132, 199, 0.35);
    }
    .btn-excel {
      background: #0f766e;
      border-color: #115e59;
      color: #fff;
      font-weight: 600;
    }
    .btn-excel:hover {
      background: #115e59;
      border-color: #134e4a;
    }
    .btn-curp {
      background: var(--color-neutral-bg);
      border: 1px solid #0d9488;
      color: #2dd4bf;
      font-weight: 600;
    }
    .btn-curp:hover {
      background: rgba(13, 148, 136, 0.15);
      border-color: #14b8a6;
      color: #5eead4;
    }
    .btn-success {
      background: #059669;
      border-color: #047857;
      color: #fff;
      font-weight: 600;
    }
    .btn-success:hover {
      background: #047857;
    }
    .btn-outline {
      background: transparent;
      border: 1px solid var(--border-strong);
      color: var(--text);
    }
    .btn-outline:hover {
      background: var(--bg-surface-elevated);
      border-color: #475569;
      color: #fff;
    }
    .btn-danger-outline {
      background: transparent;
      border: 1px solid var(--color-danger-border);
      color: #f87171;
    }
    .btn-danger-outline:hover {
      background: var(--color-danger);
      border-color: var(--color-danger);
      color: #fff;
      box-shadow: 0 0 8px rgba(236, 0, 0, 0.4);
    }

    /* Active Filters Indicator Bar */
    #active-filters-bar {
      display: none;
      align-items: center;
      gap: 8px;
      padding: 4px 10px;
      background: #101c33;
      border: 1px solid #1e3a8a;
      border-radius: var(--radius-sm);
      margin-bottom: 6px;
      font-size: var(--font-size-small);
      flex-shrink: 0;
    }
    #active-filters-bar.show { display: flex; flex-wrap: wrap; }
    .filter-chip {
      background: #1e3a8a;
      color: #93c5fd;
      padding: 2px 7px;
      border-radius: var(--radius-sm);
      font-family: var(--font-mono);
      font-size: 10.5px;
      display: inline-flex;
      align-items: center;
      gap: 5px;
    }
    .filter-chip-remove {
      cursor: pointer;
      font-weight: bold;
      color: #bfdbfe;
    }
    .filter-chip-remove:hover { color: #fff; }

    /* Grid Table Container */
    .grid-container {
      flex: 1;
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      overflow: auto;
      position: relative;
    }
    table.excel-table {
      border-collapse: separate;
      border-spacing: 0;
      width: max-content;
      min-width: 100%;
      text-align: left;
    }

    /* Cabeceras de Columna */
    th.excel-header {
      position: relative;
      overflow: visible;
      background: #0d1424;
      color: var(--text-muted);
      font-size: var(--font-size-header);
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      padding: 0;
      position: sticky;
      top: 0;
      z-index: 20;
      border-bottom: 2px solid #27354f;
      border-right: 1px solid var(--border-subtle);
      white-space: nowrap;
      user-select: none;
      box-sizing: border-box;
      height: 34px;
    }
    .th-inner {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 4px;
      padding: 6px 8px;
      width: 100%;
      height: 100%;
      box-sizing: border-box;
      overflow: hidden;
    }
    .th-title-wrap {
      display: flex;
      align-items: center;
      gap: 4px;
      min-width: 0;
      flex: 1 1 auto;
      overflow: hidden;
    }
    .col-letter {
      font-size: 10px;
      color: var(--text-dim);
      font-family: var(--font-mono);
      flex-shrink: 0;
    }
    .th-title {
      font-weight: 600;
      color: #cbd5e1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      min-width: 0;
      font-size: var(--font-size-header);
    }
    .th-editable-pill {
      background: #065f46;
      color: #34d399;
      font-size: 9px;
      font-weight: 700;
      padding: 1px 4px;
      border-radius: 2px;
      flex-shrink: 0;
    }
    .header-btns {
      display: flex;
      align-items: center;
      gap: 3px;
      flex-shrink: 0;
    }
    .sort-indicator {
      font-size: 9px;
      color: var(--color-primary);
      flex-shrink: 0;
    }
    .filter-btn {
      background: transparent;
      border: 1px solid transparent;
      color: var(--text-dim);
      padding: 2px 4px;
      border-radius: var(--radius-sm);
      cursor: pointer;
      font-size: 10px;
      line-height: 1;
      transition: var(--transition-fast);
    }
    .filter-btn:hover {
      background: var(--bg-surface-elevated);
      color: #f1f5f9;
      border-color: var(--border-strong);
    }
    .filter-btn.has-filter {
      background: #065f46;
      color: #34d399;
      border-color: #059669;
      box-shadow: 0 0 6px rgba(16, 185, 129, 0.4);
    }

    th.row-num-header {
      width: 38px;
      min-width: 38px;
      max-width: 38px;
      text-align: center;
      background: #0a0f1b;
      color: var(--text-dim);
      font-family: var(--font-mono);
      font-size: 10px;
      position: sticky;
      left: 0;
      z-index: 30;
      border-right: 1px solid #27354f;
    }
    td.row-num-cell {
      position: sticky;
      left: 0;
      z-index: 10;
      background: #0d1424;
      color: var(--text-dim);
      text-align: center;
      font-family: var(--font-mono);
      font-size: var(--font-size-small);
      border-right: 1px solid var(--border-subtle);
      border-bottom: 1px solid var(--border-subtle);
      padding: 0 4px;
      cursor: pointer;
      vertical-align: middle;
      transition: background-color 120ms ease;
    }

    /* Filas y Celdas con Spacing Generoso (Respirar) */
    tr {
      height: var(--cell-h);
      transition: background-color 120ms ease;
    }
    tr:hover td {
      background-color: var(--bg-row-hover);
    }
    tr.row-selected td {
      background-color: var(--bg-row-selected) !important;
    }

    td.excel-cell {
      padding: var(--cell-pad-y) var(--cell-pad-x);
      border-right: 1px solid var(--border-subtle);
      border-bottom: 1px solid var(--border-subtle);
      vertical-align: middle;
      white-space: nowrap;
      font-size: var(--font-size-cell);
      position: relative;
      cursor: cell;
      overflow: hidden;
      text-overflow: ellipsis;
      box-sizing: border-box;
      transition: background-color 120ms ease;
    }
    .mono { font-family: var(--font-mono); }

    td.excel-cell.excel-active {
      outline: 2px solid var(--color-primary) !important;
      outline-offset: -2px;
      background-color: var(--excel-selection-bg) !important;
      z-index: 15;
    }
    td.excel-cell.excel-active::after {
      content: '';
      position: absolute;
      right: -2px;
      bottom: -2px;
      width: 6px;
      height: 6px;
      background: var(--color-primary);
      border: 1px solid #090d16;
      cursor: crosshair;
    }

    @keyframes cellSavedAnim {
      0% { background-color: #065f46; color: #fff; }
      100% { background-color: transparent; }
    }
    .cell-saved { animation: cellSavedAnim 1.2s ease-out; }

    .cell-editor-input {
      position: absolute;
      top: 0; left: 0;
      width: 100%; height: 100%;
      background: var(--bg-surface-elevated);
      color: #fff;
      border: 2px solid var(--color-primary);
      font-family: var(--font-mono);
      font-size: var(--font-size-cell);
      padding: var(--cell-pad-y) var(--cell-pad-x);
      outline: none;
      z-index: 25;
      box-shadow: 0 0 0 3px var(--color-primary-ring);
    }

    .rfc-pill {
      font-weight: 700;
      color: #60a5fa;
      background: #1e293b;
      padding: 2px 5px;
      border-radius: var(--radius-sm);
      border: 1px solid #334155;
    }
    .curp-pill {
      color: #34d399;
      font-weight: 700;
      background: rgba(16, 185, 129, 0.1);
      padding: 2px 6px;
      border-radius: var(--radius-sm);
      border: 1px dashed rgba(16, 185, 129, 0.4);
    }
    .curp-empty {
      color: var(--text-dim);
      font-style: italic;
      font-size: 11px;
    }
    .status-badge {
      font-size: 10px;
      padding: 2px 6px;
      border-radius: var(--radius-sm);
      font-weight: 600;
      text-transform: uppercase;
      font-family: var(--font-mono);
    }
    .status-calculada { background: #064e3b; color: #34d399; border: 1px solid #059669; }
    .status-existente { background: #1e3a8a; color: #93c5fd; border: 1px solid #3b82f6; }
    .status-no_calculable { background: #3b0764; color: #d8b4fe; border: 1px solid #7e22ce; }
    .falta-badge {
      font-size: 10px;
      padding: 2px 6px;
      border-radius: var(--radius-sm);
      background: #27272a;
      color: #a1a1aa;
      font-family: var(--font-mono);
    }
    .tag-btn {
      background: #1e293b;
      border: 1px solid #334155;
      color: #cbd5e1;
      font-size: 9.5px;
      padding: 2px 5px;
      border-radius: var(--radius-sm);
      cursor: pointer;
      margin-left: 3px;
    }
    .tag-btn.hit { border-color: #059669; color: #34d399; background: #064e3b; font-weight: 700; }
    .tag-btn.dead { border-color: #dc2626; color: #f87171; background: #450a0a; font-weight: 700; }

    /* Pagination Bar */
    .pagination-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-top: 8px;
      font-size: var(--font-size-small);
      color: var(--text-muted);
      flex-shrink: 0;
    }
    .page-controls {
      display: flex;
      gap: 8px;
      align-items: center;
    }

    /* Popover */
    .filter-popover {
      display: none;
      position: fixed;
      background: var(--bg-card);
      border: 1px solid var(--border-strong);
      box-shadow: 0 16px 36px rgba(0, 0, 0, 0.7);
      border-radius: var(--radius-md);
      width: 260px;
      z-index: 1000;
      padding: 12px;
      font-family: var(--font-sans);
    }
    .filter-popover.show { display: block; }
    .popover-header {
      font-weight: 700;
      font-size: 12px;
      color: #fff;
      margin-bottom: 8px;
      padding-bottom: 6px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .popover-close { cursor: pointer; color: var(--text-muted); font-size: 14px; }
    .popover-close:hover { color: #fff; }
    .popover-sort-btns { display: flex; flex-direction: column; gap: 5px; margin-bottom: 8px; }
    .sort-menu-btn {
      background: var(--bg-surface-elevated);
      border: 1px solid var(--border-strong);
      color: #e2e8f0;
      text-align: left;
      padding: 5px 8px;
      border-radius: var(--radius-sm);
      font-size: 11px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: var(--transition-fast);
    }
    .sort-menu-btn:hover { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
    .popover-divider { height: 1px; background: var(--border); margin: 8px 0; }
    .popover-input-group { display: flex; flex-direction: column; gap: 5px; margin-bottom: 8px; }
    .popover-select, .popover-input {
      background: var(--bg-app);
      border: 1px solid var(--border-strong);
      color: #fff;
      padding: 5px 8px;
      border-radius: var(--radius-sm);
      font-size: 11.5px;
      outline: none;
      transition: var(--transition-fast);
    }
    .popover-input:focus { border-color: var(--border-focus); }
    .popover-actions { display: flex; justify-content: space-between; gap: 8px; }

    /* Menú contextual */
    .context-menu {
      display: none;
      position: fixed;
      background: var(--bg-card);
      border: 1px solid var(--border-strong);
      border-radius: var(--radius-md);
      box-shadow: 0 12px 28px rgba(0,0,0,0.65);
      width: 190px;
      z-index: 1100;
      padding: 5px 0;
    }
    .context-menu.show { display: block; }
    .ctx-item {
      padding: 6px 12px;
      font-size: 11.5px;
      color: #e2e8f0;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 7px;
      transition: var(--transition-fast);
    }
    .ctx-item:hover { background: var(--color-primary); color: #fff; }
    .ctx-item-danger:hover { background: var(--color-danger); color: #fff; }
    .ctx-sep { height: 1px; background: var(--border); margin: 5px 0; }

    /* Modal */
    .modal {
      display: none;
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0,0,0,0.75);
      backdrop-filter: blur(5px);
      z-index: 1200;
      align-items: center;
      justify-content: center;
    }
    .modal.show { display: flex; }
    .modal-content {
      background: var(--bg-card);
      border: 1px solid var(--border-strong);
      border-radius: var(--radius-lg);
      width: 520px;
      max-width: 90vw;
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .modal-textarea {
      background: var(--bg-app);
      border: 1px solid var(--border-strong);
      color: #fff;
      font-family: var(--font-mono);
      padding: 9px;
      border-radius: var(--radius-sm);
      height: 160px;
      resize: vertical;
      font-size: 11.5px;
      outline: none;
      transition: var(--transition-fast);
    }
    .modal-textarea:focus { border-color: var(--border-focus); }

    #toast {
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: var(--bg-card);
      border: 1px solid var(--border-focus);
      color: #fff;
      padding: 8px 16px;
      border-radius: var(--radius-md);
      font-size: 12px;
      font-weight: 500;
      box-shadow: 0 12px 28px rgba(0,0,0,0.65);
      opacity: 0;
      transform: translateY(10px);
      transition: all 0.2s ease;
      z-index: 2000;
      pointer-events: none;
    }
    #toast.show { opacity: 1; transform: translateY(0); }

    /* Modernized Quieter & Resizable Styles */
    .col-resizer {
      position: absolute;
      top: 0;
      right: 0;
      width: 6px;
      height: 100%;
      cursor: col-resize;
      user-select: none;
      z-index: 25;
    }
    .col-resizer:hover, .col-resizer.resizing {
      background: var(--color-primary);
    }
    body.resizing-col {
      cursor: col-resize !important;
      user-select: none !important;
    }
    body.resizing-col * {
      user-select: none !important;
    }

    /* Quieter Monospace Elements */
    .copyable-text {
      cursor: pointer;
      padding: 2px 4px;
      border-radius: var(--radius-sm);
      transition: var(--transition-fast);
      display: inline-block;
    }
    .copyable-text:hover {
      background: rgba(2, 132, 199, 0.15);
      color: #38bdf8 !important;
      text-decoration: underline;
    }
    .rfc-text {
      color: #cbd5e1;
      font-family: var(--font-mono);
      font-size: var(--font-size-cell);
      letter-spacing: 0.5px;
    }
    .rfc-date {
      color: #38bdf8;
      font-weight: 700;
      background: rgba(56, 189, 248, 0.08);
      padding: 0 2px;
      border-radius: 2px;
    }
    .curp-text {
      color: #34d399;
      font-family: var(--font-mono);
      font-size: var(--font-size-cell);
      font-weight: 600;
      letter-spacing: 0.5px;
    }
    .card-text {
      color: #e2e8f0;
      font-family: var(--font-mono);
      font-size: var(--font-size-cell);
      letter-spacing: 0.8px;
    }
    .limite-text {
      color: #6ee7b7;
      font-family: var(--font-mono);
      font-weight: 600;
      font-size: var(--font-size-cell);
      display: block;
      text-align: right;
      padding-right: 4px;
    }

    /* Large responsive checkbox hitbox */
    td.select-col-cell {
      padding: 0 !important;
      cursor: pointer;
      text-align: center;
      vertical-align: middle;
      user-select: none;
    }
    td.select-col-cell input.row-checkbox {
      cursor: pointer;
      width: 16px;
      height: 16px;
      pointer-events: none;
      accent-color: var(--color-primary);
    }

    /* Floating micro feedback tooltip */
    .inline-copy-feedback {
      position: fixed;
      background: #10b981;
      color: #ffffff;
      font-size: 10.5px;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: var(--radius-sm);
      box-shadow: 0 4px 14px rgba(0,0,0,0.4);
      z-index: 10000;
      pointer-events: none;
      animation: feedbackFade 0.75s forwards;
    }
    @keyframes feedbackFade {
      0% { opacity: 0; transform: translateY(4px); }
      20% { opacity: 1; transform: translateY(0); }
      80% { opacity: 1; transform: translateY(0); }
      100% { opacity: 0; transform: translateY(-6px); }
    }
  </style>"""

NEW_HTML_BODY_START = """<body>

  <!-- Lock Screen Overlay -->
  <div id="lock-screen">
    <div class="lock-card">
      <div class="lock-icon-circle">🔒</div>
      <div style="margin-bottom: 10px;">
        <span class="badge-santander">SANTANDER</span>
      </div>
      <h2 class="lock-title">Bóveda Operativa</h2>
      <p class="lock-subtitle">Ingresa la contraseña para desbloquear los controles tipo Excel y la base de datos de 4.9M de registros.</p>
      
      <div class="password-input-group">
        <input type="password" id="login-password" class="password-input" placeholder="Contraseña de acceso..." onkeydown="if(event.key==='Enter') submitLogin()">
        <button class="eye-btn" onclick="togglePasswordVisibility()" title="Mostrar/Ocultar">👁</button>
      </div>

      <button class="btn-login" onclick="submitLogin()">Desbloquear Bóveda ➔</button>
      <div id="lock-error" class="lock-error">Contraseña incorrecta. Intenta de nuevo.</div>
    </div>
  </div>

  <!-- Top Bar -->
  <div class="top-bar">
    <div class="brand-group">
      <span class="badge-santander">SANTANDER</span>
      <h1 class="app-title">Bóveda Operativa</h1>
      <span class="badge-excel">📊 EXCEL PRO GRID</span>
    </div>
    <div class="stats-group">
      <div class="kpi-card" title="Total de registros en base de datos">
        <span class="kpi-label">Total</span>
        <span class="kpi-val" id="stat-total">...</span>
      </div>
      <div class="kpi-card curp" title="CURPs totales registradas">
        <span class="kpi-label">Con CURP</span>
        <span class="kpi-val" id="stat-curp">...</span>
      </div>
      <div class="kpi-card calc" title="CURPs calculadas por el motor">
        <span class="kpi-label">Calculadas</span>
        <span class="kpi-val" id="stat-calc">...</span>
      </div>
      <div class="kpi-card missing" title="Falta CURP por calcular">
        <span class="kpi-label">Falta CURP</span>
        <span class="kpi-val" id="stat-no-curp">...</span>
      </div>
      <div class="kpi-card results" title="Con resultados de consulta">
        <span class="kpi-label">Resultados</span>
        <span class="kpi-val" id="stat-results">...</span>
      </div>
      <button class="btn-logout" onclick="doLogout()" title="Cerrar sesión">Cerrar Sesión</button>
    </div>
  </div>

  <!-- Excel Formula & Value Bar -->
  <div class="formula-bar-container">
    <div class="cell-coord-box" id="cell-coord">C1 (CURP)</div>
    <span class="fx-symbol">fx</span>
    <input type="text" id="formula-input" class="formula-input" placeholder="Selecciona una celda...">
    <div class="keyboard-hint">
      <span class="kbd">↑↓←→</span> Navegar
      <span class="kbd">Enter</span>/<span class="kbd">F2</span> Editar CURP
      <span class="kbd">Tab</span> Avanzar
      <span class="kbd">Ctrl+C/V</span> Copiar/Pegar <span class="kbd">Arrastrar / Ctrl+Clic</span> Multiselección
    </div>
  </div>

  <!-- Toolbar con 4 Clusters Visuales y Segmented Control -->
  <div class="toolbar">
    <!-- 1. Búsqueda y Filtros Predefinidos (Segmented Control) -->
    <div class="tb-group">
      <div class="filter-tabs">
        <button class="tab-btn active" onclick="setPresetFilter('all')">Todos</button>
        <button class="tab-btn" onclick="setPresetFilter('no_curp')">Falta CURP</button>
        <button class="tab-btn" onclick="setPresetFilter('has_curp')">Con CURP</button>
        <button class="tab-btn" onclick="setPresetFilter('calculada')">Calculadas</button>
        <button class="tab-btn" onclick="setPresetFilter('no_calculable')">No Calculables</button>
        <button class="tab-btn" onclick="setPresetFilter('has_results')">Con Result</button>
      </div>
      <input type="text" id="global-search" class="global-search" placeholder="🔍 Buscar RFC, Nombre, Ciudad..." onkeydown="if(event.key==='Enter') applyGlobalSearch()">
      <button class="btn btn-primary" onclick="applyGlobalSearch()">Buscar</button>
    </div>

    <div class="tb-sep"></div>

    <!-- 2. Selección / Copia RFCs & CURPs -->
    <div class="tb-group">
      <button class="btn" onclick="copySelectedRfcs()" title="Copiar RFCs de filas seleccionadas">📋 Copiar RFCs (<span id="sel-count">0</span>)</button>
      <button class="btn btn-curp" onclick="copySelectedCurps()" title="Copiar CURPs de filas seleccionadas">📋 Copiar CURPs (<span id="sel-curp-count">0</span>)</button>
      <button class="btn btn-outline" onclick="copyPageRfcs()" title="Copiar todos los RFCs de la página">📄 RFCs Pág</button>
      <button class="btn btn-outline" onclick="copyPageCurps()" title="Copiar todas las CURPs de la página">📄 CURPs Pág</button>
      <button class="btn btn-danger-outline" id="btn-clear-selection" onclick="clearSelection()" title="Limpiar selección" style="display:none; padding: 4px 8px;">✕</button>
    </div>

    <div class="tb-sep"></div>

    <!-- 3. Acciones CURP Masivas -->
    <div class="tb-group">
      <button class="btn btn-outline" onclick="openBulkCurpModal()">📥 Pegar CURPs (/cep)</button>
    </div>

    <div class="tb-sep"></div>

    <!-- 4. Exportar & Reset -->
    <div class="tb-group">
      <button class="btn btn-excel" onclick="exportCsv()">⬇️ Exportar CSV</button>
      <button class="btn btn-danger-outline" id="btn-clear-all-filters" onclick="clearAllFilters()" style="display:none;">✖ Limpiar Filtros</button>
    </div>
  </div>"""

def main():
    with open(APP_PY_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Replace <style>...</style>
    style_pattern = re.compile(r"  <style>.*?</style>", re.DOTALL)
    if not style_pattern.search(content):
        print("ERROR: No se encontro el bloque <style>...</style>")
        sys.exit(1)
    
    content = style_pattern.sub(NEW_CSS, content, count=1)

    # 2. Replace from <body> to <!-- Active Filters Indicator Bar -->
    body_pattern = re.compile(
        r"<body>.*?<!-- Active Filters Indicator Bar -->",
        re.DOTALL
    )
    if not body_pattern.search(content):
        print("ERROR: No se encontro el bloque HTML de body hasta active-filters-bar")
        sys.exit(1)
    
    replacement_body = NEW_HTML_BODY_START + "\n\n  <!-- Active Filters Indicator Bar -->"
    content = body_pattern.sub(replacement_body, content, count=1)

    with open(APP_PY_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    
    print("SUCCESS: app.py actualizado con éxito.")

if __name__ == "__main__":
    main()
