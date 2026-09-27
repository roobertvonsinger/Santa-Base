#!/usr/bin/env python3
"""
Script de aplicacion automatizada de la Fase 2 para Santa Base:
1. Layout responsive sin traslapes (CSS media queries y flex wrapping).
2. Jerarquia de filtros con buscador ergonómico (limpiar con ✕, atajo Ctrl+K).
3. Menu contextual enriquecido (soporte para copia de rangos, atajos visuales y deteccion de limites de pantalla).
4. Branding unificado en Lock Screen (SANTA 🙏🏻 BASE).
"""

import sys
import re

APP_PY_PATH = "app.py"

def main():
    with open(APP_PY_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Update CSS: Add responsive queries, search wrap, and upgraded context menu
    old_ctx_css = """    /* Menú contextual */
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
    .ctx-sep { height: 1px; background: var(--border); margin: 5px 0; }"""

    new_ctx_css = """    /* Search Input Wrapper with Instant Clear */
    .search-input-wrap {
      position: relative;
      display: inline-flex;
      align-items: center;
    }
    .global-search {
      background: var(--bg-app);
      border: 1px solid var(--border-strong);
      color: #fff;
      padding: 5px 28px 5px 10px;
      border-radius: var(--radius-sm);
      font-size: var(--font-size-small);
      width: 220px;
      outline: none;
      transition: var(--transition-fast);
    }
    .global-search:focus {
      border-color: var(--border-focus);
      box-shadow: 0 0 0 2px var(--color-primary-ring);
    }
    .search-clear-btn {
      position: absolute;
      right: 6px;
      background: transparent;
      border: none;
      color: var(--text-dim);
      font-size: 11px;
      cursor: pointer;
      padding: 2px 4px;
      border-radius: 50%;
      line-height: 1;
      transition: var(--transition-fast);
    }
    .search-clear-btn:hover {
      color: #fff;
      background: rgba(255, 255, 255, 0.1);
    }

    /* Context Menu Modern Acrylic & Shortcut Badges */
    .context-menu {
      display: none;
      position: fixed;
      background: rgba(15, 23, 42, 0.96);
      backdrop-filter: blur(14px);
      border: 1px solid var(--border-strong);
      border-radius: var(--radius-md);
      box-shadow: 0 16px 36px -4px rgba(0, 0, 0, 0.75), 0 0 0 1px rgba(255, 255, 255, 0.05);
      min-width: 215px;
      z-index: 1100;
      padding: 5px;
    }
    .context-menu.show { display: block; }
    .ctx-header {
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--text-dim);
      padding: 4px 8px 5px;
      font-weight: 700;
      border-bottom: 1px solid var(--border);
      margin-bottom: 3px;
    }
    .ctx-item {
      padding: 6px 10px;
      font-size: 12px;
      color: #e2e8f0;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-radius: var(--radius-sm);
      transition: var(--transition-fast);
      gap: 12px;
    }
    .ctx-item:hover {
      background: var(--color-primary);
      color: #fff;
    }
    .ctx-item.ctx-highlight {
      background: rgba(2, 132, 199, 0.15);
      color: #38bdf8;
      font-weight: 600;
    }
    .ctx-item.ctx-highlight:hover {
      background: var(--color-primary);
      color: #fff;
    }
    .ctx-item-danger:hover {
      background: var(--color-danger) !important;
      color: #fff !important;
    }
    .ctx-shortcut {
      font-family: var(--font-mono);
      font-size: 10px;
      color: var(--text-dim);
      background: rgba(255, 255, 255, 0.06);
      padding: 1px 5px;
      border-radius: 3px;
    }
    .ctx-item:hover .ctx-shortcut {
      color: #fff;
      background: rgba(0, 0, 0, 0.25);
    }
    .ctx-badge {
      font-family: var(--font-mono);
      font-size: 10px;
      color: #38bdf8;
      font-weight: 700;
    }
    .ctx-item:hover .ctx-badge {
      color: #fff;
    }
    .ctx-sep { height: 1px; background: var(--border); margin: 4px 0; }

    /* Layout Responsive (Zero Overlaps) */
    @media (max-width: 1280px) {
      .global-search { width: 170px; }
      .kpi-card { min-width: 72px; padding: 2px 7px; }
      .kpi-val { font-size: 14px; }
    }
    @media (max-width: 1050px) {
      .top-bar { flex-wrap: wrap; }
      .keyboard-hint { display: none; }
      .toolbar { gap: 6px; }
      .tb-sep { margin: 0 2px; }
    }"""

    if old_ctx_css in content:
        content = content.replace(old_ctx_css, new_ctx_css)
        print("CSS Context Menu & Responsive rules actualizadas.")
    else:
        print("WARN: No se encontro el bloque exacto de CSS context-menu, buscando regex...")
        content = re.sub(r"/\* Menú contextual \*/\s+\.context-menu\s*\{.*?\.ctx-sep \{ height: 1px; background: var\(--border\); margin: 5px 0; \}", new_ctx_css, content, flags=re.DOTALL)

    # 2. Lock screen title branding
    old_lock_title = '<h2 class="lock-title">Bóveda Operativa</h2>'
    new_lock_title = '<h2 class="lock-title"><span class="brand-santa">SANTA</span> <span class="brand-pray">🙏🏻</span> <span class="brand-base">BASE</span></h2>'
    if old_lock_title in content:
        content = content.replace(old_lock_title, new_lock_title)
        print("Lock screen brand title actualizado.")

    # 3. Search input in Toolbar: wrap with clear button
    old_search = '<input type="text" id="global-search" class="global-search" placeholder="🔍 Buscar RFC, Nombre, Ciudad..." onkeydown="if(event.key===\'Enter\') applyGlobalSearch()">'
    new_search = '''<div class="search-input-wrap">
        <input type="text" id="global-search" class="global-search" placeholder="🔍 Buscar RFC, Nombre... (Ctrl+K)" onkeydown="if(event.key==='Enter') applyGlobalSearch()" oninput="toggleSearchClearBtn()">
        <button id="btn-clear-search" class="search-clear-btn" onclick="clearGlobalSearch()" title="Limpiar búsqueda" style="display:none;">✕</button>
      </div>'''
    if old_search in content:
        content = content.replace(old_search, new_search)
        print("Buscador enriquecido con atajo Ctrl+K y boton de limpieza.")

    # 4. Context Menu HTML: Add header, shortcuts, and range item
    old_ctx_html = """  <!-- Custom Context Menu -->
  <div class="context-menu" id="context-menu">
    <div class="ctx-item" onclick="ctxCopyCell()">📋 Copiar Celda (Ctrl+C)</div>
    <div class="ctx-item" onclick="ctxCopyRfc()">📄 Copiar RFC de Fila</div>
    <div class="ctx-item" onclick="ctxCopyRow()">📑 Copiar Fila Completa</div>
    <div class="ctx-sep"></div>
    <div class="ctx-item" id="ctx-paste-item" onclick="ctxPasteCell()">📥 Pegar CURP (Ctrl+V)</div>
    <div class="ctx-item ctx-item-danger" id="ctx-clear-item" onclick="ctxClearCell()">🧹 Borrar CURP (Supr)</div>
    <div class="ctx-sep"></div>
    <div class="ctx-item" onclick="ctxMarkResult('HIT')">🟢 Marcar HIT</div>
    <div class="ctx-item" onclick="ctxMarkResult('DEAD')">🔴 Marcar DEAD</div>
  </div>"""

    new_ctx_html = """  <!-- Custom Context Menu -->
  <div class="context-menu" id="context-menu">
    <div class="ctx-header">Acciones Rápidas</div>
    <div class="ctx-item ctx-highlight" id="ctx-range-item" onclick="copyCellRangeSelection()" style="display:none;">
      <span>🎯 Copiar Rango</span>
      <span class="ctx-badge" id="ctx-range-badge">0</span>
    </div>
    <div class="ctx-item" onclick="ctxCopyCell()">
      <span>📋 Copiar Celda</span>
      <span class="ctx-shortcut">Ctrl+C</span>
    </div>
    <div class="ctx-item" onclick="ctxCopyRfc()">
      <span>📄 Copiar RFC</span>
      <span class="ctx-shortcut">RFC</span>
    </div>
    <div class="ctx-item" onclick="ctxCopyRow()">
      <span>📑 Copiar Fila TSV</span>
      <span class="ctx-shortcut">TSV</span>
    </div>
    <div class="ctx-sep"></div>
    <div class="ctx-item" id="ctx-paste-item" onclick="ctxPasteCell()">
      <span>📥 Pegar CURP</span>
      <span class="ctx-shortcut">Ctrl+V</span>
    </div>
    <div class="ctx-item ctx-item-danger" id="ctx-clear-item" onclick="ctxClearCell()">
      <span>🧹 Borrar CURP</span>
      <span class="ctx-shortcut">Supr</span>
    </div>
    <div class="ctx-sep"></div>
    <div class="ctx-item" onclick="ctxMarkResult('HIT')">
      <span>🟢 Marcar HIT</span>
      <span class="ctx-shortcut">HIT</span>
    </div>
    <div class="ctx-item" onclick="ctxMarkResult('DEAD')">
      <span>🔴 Marcar DEAD</span>
      <span class="ctx-shortcut">DEAD</span>
    </div>
  </div>"""

    if old_ctx_html in content:
        content = content.replace(old_ctx_html, new_ctx_html)
        print("HTML Context Menu actualizado con jerarquia y atajos.")

    # 5. Update JavaScript handleCellContextMenu: collision detection and range item support
    old_ctx_js = """      const menu = document.getElementById('context-menu');
      menu.style.top = `${e.clientY}px`;
      menu.style.left = `${e.clientX}px`;
      menu.classList.add('show');"""

    new_ctx_js = """      const menu = document.getElementById('context-menu');
      const rangeItem = document.getElementById('ctx-range-item');
      const rangeBadge = document.getElementById('ctx-range-badge');
      if (typeof cellRangeSelection !== 'undefined' && cellRangeSelection.segments.length > 0 && rangeItem && rangeBadge) {
        rangeItem.style.display = 'flex';
        rangeBadge.innerText = `${getCellRangeCount()} celdas`;
      } else if (rangeItem) {
        rangeItem.style.display = 'none';
      }

      menu.classList.add('show');
      const rect = menu.getBoundingClientRect();
      let top = e.clientY;
      let left = e.clientX;
      if (left + rect.width > window.innerWidth) left = window.innerWidth - rect.width - 10;
      if (top + rect.height > window.innerHeight) top = window.innerHeight - rect.height - 10;
      menu.style.top = `${Math.max(10, top)}px`;
      menu.style.left = `${Math.max(10, left)}px`;"""

    if old_ctx_js in content:
        content = content.replace(old_ctx_js, new_ctx_js)
        print("JS Context Menu con deteccion de colisiones y soporte de rangos activo.")

    # 6. Add JS helpers for Search Clear and Ctrl+K shortcut
    search_helpers = """
    function toggleSearchClearBtn() {
      const val = document.getElementById('global-search').value;
      const btn = document.getElementById('btn-clear-search');
      if (btn) btn.style.display = val ? 'block' : 'none';
    }

    function clearGlobalSearch() {
      const input = document.getElementById('global-search');
      if (input) {
        input.value = '';
        toggleSearchClearBtn();
        applyGlobalSearch();
      }
    }

    window.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        const searchInput = document.getElementById('global-search');
        if (searchInput) {
          searchInput.focus();
          searchInput.select();
        }
      }
    });
"""
    if "function toggleSearchClearBtn" not in content:
        content = content.replace("function applyGlobalSearch() {", search_helpers + "\n    function applyGlobalSearch() {")
        print("JS helpers para busqueda y atajo Ctrl+K inyectados.")

    with open(APP_PY_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print("SUCCESS: app.py actualizado con mejoras de Fase 2.")

if __name__ == "__main__":
    main()
