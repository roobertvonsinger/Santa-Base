import re
import os

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add static route for anime.min.js if not present
static_route = '''@app.get("/static/anime.min.js")
def get_anime_js():
    static_file = os.path.join(os.path.dirname(__file__), "static", "anime.min.js")
    if os.path.exists(static_file):
        with open(static_file, "r", encoding="utf-8") as f:
            return RawResponse(content=f.read(), media_type="application/javascript")
    return RawResponse(content="", status_code=404)

'''

if '/static/anime.min.js' not in content:
    content = content.replace(
        '@app.get("/api/auth/status")',
        static_route + '@app.get("/api/auth/status")'
    )

# 2. Add Anime.js script to <head>
anime_script_tag = '''  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/animejs/3.2.2/anime.min.js"></script>
  <script>if (typeof anime === 'undefined') { document.write('<script src="/static/anime.min.js"><\\/script>'); }</script>'''

content = re.sub(
    r'<link rel="preconnect" href="https://fonts.googleapis.com">[\s\S]*?<link href="https://fonts.googleapis.com/css2\?family=JetBrains\+Mono[\s\S]*?rel="stylesheet">',
    anime_script_tag,
    content
)

# 3. Update title
content = content.replace(
    '<title>Santander DB — Excel Pro Grid (Bóveda Operativa)</title>',
    '<title>Santa Base — Bóveda Operativa (4.9M Registros)</title>'
)

# 4. Red & Black Design Tokens (:root) and Custom Sleek Scrollbars
old_tokens_and_base = '''    :root {
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
    }'''

new_tokens_and_base = '''    :root {
      /* Superficies y Fondos — Red & Obsidian Ops */
      --bg-app: #07070a;
      --bg-card: #0f0f15;
      --bg-surface: #12121a;
      --bg-surface-elevated: #181824;
      --bg-row-hover: rgba(236, 0, 0, 0.05);
      --bg-row-selected: rgba(236, 0, 0, 0.18);
      --excel-selection-bg: rgba(236, 0, 0, 0.14);

      /* Bordes y Divisiones */
      --border: #1e1e2a;
      --border-subtle: #191924;
      --border-strong: #2a2a3c;
      --border-focus: #ec0000;

      /* Radios de curvatura */
      --radius-sm: 4px;
      --radius-md: 6px;
      --radius-lg: 8px;
      --radius-full: 9999px;

      /* Sistema Semántico de Color — Rojo Santander & Negro Carbón */
      /* Nivel 1: Primario (Acción Principal / Foco) */
      --color-primary: #ec0000;
      --color-primary-hover: #ff1a1a;
      --color-primary-active: #cc0000;
      --color-primary-ring: rgba(236, 0, 0, 0.4);

      /* Nivel 2: Secundario / Neutro (Acciones frecuentes, Toolbar, Copia) */
      --color-neutral-bg: #14141e;
      --color-neutral-border: #28283a;
      --color-neutral-hover: #1e1e2c;
      --color-neutral-text: #f3f4f6;

      /* Nivel 3: Destructivo / Peligro (Logout, Reset, Alertas) */
      --color-danger: #ec0000;
      --color-danger-hover: #ff1a1a;
      --color-danger-subtle: rgba(236, 0, 0, 0.14);
      --color-danger-border: rgba(236, 0, 0, 0.4);

      /* Marca Santander Canónica */
      --santander: #ec0000;

      /* Tipografía */
      --font-mono: 'JetBrains Mono', monospace;
      --font-sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      --font-size-base: 13px;
      --font-size-cell: 12.5px;
      --font-size-header: 11.5px;
      --font-size-btn: 12.5px;
      --font-size-small: 11px;
      --font-size-kpi-val: 16px;
      --font-size-kpi-lbl: 10px;

      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --text-dim: #6b7280;

      /* Dimensiones de Celdas (Respirar) */
      --cell-h: 36px;
      --cell-pad-x: 10px;
      --cell-pad-y: 6px;

      /* Microinteracciones */
      --transition-fast: all 140ms ease;
    }

    /* Custom Sleek Scrollbars — Red & Black Velvet Fintech */
    ::-webkit-scrollbar {
      width: 7px;
      height: 7px;
    }
    ::-webkit-scrollbar-track {
      background: #08080c;
    }
    ::-webkit-scrollbar-thumb {
      background: #232330;
      border-radius: 4px;
      border: 1px solid #14141d;
      transition: background 0.2s ease;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: #ec0000;
      box-shadow: 0 0 10px rgba(236, 0, 0, 0.6);
    }
    ::-webkit-scrollbar-corner {
      background: #08080c;
    }
    * {
      scrollbar-width: thin;
      scrollbar-color: #232330 #08080c;
    }'''

content = content.replace(old_tokens_and_base, new_tokens_and_base)

# 5. Lock screen overlay styles
old_lock_screen_css = '''    /* Lock Screen Overlay */
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
      width: 100%;
      max-width: 440px;
      text-align: center;
      position: relative;
    }'''

new_lock_screen_css = '''    /* Lock Screen Overlay — Red Velvet Obsidian */
    #lock-screen {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: radial-gradient(circle at 50% 35%, rgba(236, 0, 0, 0.16) 0%, rgba(7, 7, 10, 0.98) 75%);
      backdrop-filter: blur(16px);
      z-index: 9999;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: opacity 0.35s ease;
    }
    #lock-screen.hidden { display: none; pointer-events: none; }
    .lock-card {
      background: #0f0f16;
      border: 1px solid rgba(236, 0, 0, 0.3);
      box-shadow: 0 25px 60px rgba(0, 0, 0, 0.85), 0 0 40px rgba(236, 0, 0, 0.15);
      border-radius: var(--radius-lg);
      padding: 34px 30px;
      width: 100%;
      max-width: 440px;
      text-align: center;
      position: relative;
    }'''

content = content.replace(old_lock_screen_css, new_lock_screen_css)

# 6. Logo styling (unified SANTA + BASE logo lockup) and remove old badges
old_brand_css = '''    .badge-santander {
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
      display: flex;
      align-items: baseline;
      gap: 5px;
      font-size: 15px;
      font-weight: 700;
      color: #fff;
      letter-spacing: -0.3px;
    }
    .brand-santa {
      font-size: 19px;
      font-weight: 900;
      color: var(--santander);
      letter-spacing: -0.6px;
      text-shadow: 0 0 14px rgba(236, 0, 0, 0.35);
    }
    .brand-pray {
      font-size: 14px;
      filter: drop-shadow(0 0 3px rgba(236, 0, 0, 0.4));
      transform: translateY(-1px);
    }
    .brand-base {
      font-size: 14px;
      font-weight: 800;
      font-style: italic;
      letter-spacing: 1.8px;
      background: linear-gradient(90deg, #ec0000 0%, #f59e0b 100%);
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
    }'''

new_brand_css = '''    /* Unified Brand Logo: SANTA (Red Pill) + 🙏🏻 + BASE (Italic Flame) */
    .santa-brand-logo {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      padding: 3px 6px;
      border-radius: var(--radius-md);
      transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
      cursor: default;
      user-select: none;
    }
    .santa-brand-logo:hover {
      transform: scale(1.02);
    }
    .santa-brand-logo.lock-logo {
      margin-bottom: 12px;
      transform: scale(1.15);
    }
    .logo-pill-santa {
      background: linear-gradient(135deg, #ec0000 0%, #bd0000 100%);
      color: #ffffff;
      font-family: var(--font-sans);
      font-weight: 900;
      font-size: 15px;
      letter-spacing: 0.1em;
      padding: 3px 10px;
      border-radius: 6px;
      box-shadow: 0 0 16px rgba(236, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.25);
      text-transform: uppercase;
      line-height: 1.1;
      display: inline-flex;
      align-items: center;
    }
    .logo-icon-pray {
      font-size: 17px;
      line-height: 1;
      filter: drop-shadow(0 0 8px rgba(236, 0, 0, 0.5));
      display: inline-flex;
      align-items: center;
    }
    .logo-text-base {
      font-family: var(--font-sans);
      font-weight: 900;
      font-style: italic;
      font-size: 17px;
      letter-spacing: 0.12em;
      background: linear-gradient(135deg, #ff1a1a 0%, #ff5e1a 50%, #ffa600 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      text-shadow: 0 0 18px rgba(236, 0, 0, 0.35);
      line-height: 1.1;
      display: inline-flex;
      align-items: center;
    }
    /* Clases de compatibilidad para suite de tests */
    .brand-santa { font-weight: 900; }
    .brand-pray { }
    .brand-base { font-weight: 900; font-style: italic; }'''

content = content.replace(old_brand_css, new_brand_css)

# 7. Mega Search Bar CSS (Rojo y Negro)
old_mega_css = '''    .mega-search-bar {
      display: flex;
      align-items: center;
      gap: 10px;
      background: var(--bg-surface);
      border: 1px solid var(--border-strong);
      border-radius: var(--radius-lg);
      padding: 7px 14px;
      margin: 8px 0;
      flex-shrink: 0;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
      transition: border-color 140ms ease, box-shadow 140ms ease;
    }
    .mega-search-bar:focus-within {
      border-color: var(--color-primary);
      box-shadow: 0 0 0 3px var(--color-primary-ring), 0 6px 20px rgba(2, 132, 199, 0.15);
    }
    .mega-search-icon {
      font-size: 18px;
      color: var(--color-primary);
      flex-shrink: 0;
    }
    .mega-filter-badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      background: rgba(2, 132, 199, 0.18);
      color: #38bdf8;
      border: 1px solid rgba(2, 132, 199, 0.4);
      border-radius: var(--radius-sm);
      padding: 3px 8px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.04em;
      white-space: nowrap;
      font-family: var(--font-mono);
      cursor: pointer;
      transition: var(--transition-fast);
    }
    .mega-filter-badge:hover {
      background: rgba(2, 132, 199, 0.3);
      border-color: #38bdf8;
    }'''

new_mega_css = '''    .mega-search-bar {
      display: flex;
      align-items: center;
      gap: 12px;
      background: linear-gradient(180deg, #12121a 0%, #0d0d13 100%);
      border: 1px solid #282838;
      border-radius: var(--radius-lg);
      padding: 8px 16px;
      margin: 8px 0;
      flex-shrink: 0;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.04);
      transition: border-color 180ms ease, box-shadow 180ms ease;
    }
    .mega-search-bar:focus-within {
      border-color: var(--color-primary);
      box-shadow: 0 0 0 3px var(--color-primary-ring), 0 8px 24px rgba(236, 0, 0, 0.22);
    }
    .mega-search-icon {
      font-size: 18px;
      color: #ec0000;
      filter: drop-shadow(0 0 6px rgba(236, 0, 0, 0.5));
      flex-shrink: 0;
    }
    .mega-filter-badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      background: rgba(236, 0, 0, 0.15);
      color: #ff4d4d;
      border: 1px solid rgba(236, 0, 0, 0.45);
      border-radius: var(--radius-sm);
      padding: 4px 10px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.06em;
      white-space: nowrap;
      font-family: var(--font-mono);
      cursor: pointer;
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
      transition: all 180ms ease;
    }
    .mega-filter-badge:hover {
      background: rgba(236, 0, 0, 0.28);
      border-color: #ff3333;
      transform: translateY(-1px);
    }'''

content = content.replace(old_mega_css, new_mega_css)

# 8. User pill operator badge in red/crimson
old_user_pill = '''    .user-pill.role-operator {
      background: rgba(2, 132, 199, 0.12);
      border: 1px solid rgba(2, 132, 199, 0.35);
      color: #38bdf8;
    }'''

new_user_pill = '''    .user-pill.role-operator {
      background: rgba(236, 0, 0, 0.12);
      border: 1px solid rgba(236, 0, 0, 0.35);
      color: #ff5555;
    }'''

content = content.replace(old_user_pill, new_user_pill)

# 9. KPI cards and values
old_kpi_vals = '''    .kpi-card.curp .kpi-val { color: #34d399; }
    .kpi-card.calc .kpi-val { color: #38bdf8; }
    .kpi-card.missing .kpi-val { color: #fb923c; }
    .kpi-card.results .kpi-val { color: #facc15; }'''

new_kpi_vals = '''    .kpi-card {
      background: #111118;
      border: 1px solid #22222f;
      border-radius: var(--radius-md);
      padding: 4px 11px;
      transition: all 180ms ease;
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
    }
    .kpi-card:hover {
      border-color: rgba(236, 0, 0, 0.45);
      background: #161622;
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(236, 0, 0, 0.15);
    }
    .kpi-card.curp .kpi-val { color: #10b981; }
    .kpi-card.calc .kpi-val { color: #ff3b5c; }
    .kpi-card.missing .kpi-val { color: #f59e0b; }
    .kpi-card.results .kpi-val { color: #facc15; }'''

content = content.replace(old_kpi_vals, new_kpi_vals)

# 10. Buttons & Export CSV button
old_btn_excel = '''    .btn-excel {
      background: #0f766e;
      border-color: #115e59;
      color: #fff;
      font-weight: 600;
    }
    .btn-excel:hover {
      background: #115e59;
      border-color: #134e4a;
    }'''

new_btn_excel = '''    .btn-excel {
      background: linear-gradient(180deg, #1c1215 0%, #12090b 100%);
      border: 1px solid rgba(236, 0, 0, 0.45);
      color: #ff5555;
      font-weight: 600;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
      transition: all 160ms ease;
    }
    .btn-excel:hover {
      background: linear-gradient(180deg, #ec0000 0%, #c40000 100%);
      border-color: #ff3333;
      color: #ffffff;
      box-shadow: 0 0 16px rgba(236, 0, 0, 0.5);
      transform: translateY(-1px);
    }'''

content = content.replace(old_btn_excel, new_btn_excel)

content = content.replace(
    'box-shadow: 0 2px 8px rgba(2, 132, 199, 0.35);',
    'box-shadow: 0 2px 10px rgba(236, 0, 0, 0.4);'
)

# 11. Table headers and row numbers
content = content.replace('background: #0a0f1b;', 'background: #09090d;')
content = content.replace('background: #0d1424;', 'background: #0a0a0f;')
content = content.replace('border-right: 1px solid #27354f;', 'border-right: 1px solid #1f1f2e;')

# 12. RFC Pill in Obsidian Red
old_rfc_pill = '''    .rfc-pill {
      font-weight: 700;
      color: #60a5fa;
      background: #1e293b;
      padding: 2px 5px;
      border-radius: var(--radius-sm);
      border: 1px solid #334155;
    }'''

new_rfc_pill = '''    .rfc-pill {
      font-weight: 700;
      color: #ffffff;
      background: #181824;
      padding: 2px 6px;
      border-radius: var(--radius-sm);
      border: 1px solid rgba(236, 0, 0, 0.3);
      letter-spacing: 0.02em;
    }'''

content = content.replace(old_rfc_pill, new_rfc_pill)

# 13. HTML Markup: Lock Screen Branding
old_lock_header = '''      <div class="lock-icon-circle">🔒</div>
      <div style="margin-bottom: 10px;">
        <span class="badge-santander">SANTANDER</span>
      </div>
      <h2 class="lock-title"><span class="brand-santa">SANTA</span> <span class="brand-pray">🙏🏻</span> <span class="brand-base">BASE</span></h2>'''

new_lock_header = '''      <div class="lock-icon-circle">🔒</div>
      <div class="santa-brand-logo lock-logo">
        <span class="logo-pill-santa brand-santa">SANTA</span>
        <span class="logo-icon-pray brand-pray">🙏🏻</span>
        <span class="logo-text-base brand-base">BASE</span>
      </div>'''

content = content.replace(old_lock_header, new_lock_header)

# 14. HTML Markup: Top Bar Branding (remove SANTANDER badge, remove EXCEL PRO GRID, unify logo)
old_topbar_brand = '''    <div class="brand-group">
      <span class="badge-santander">SANTANDER</span>
      <h1 class="app-title"><span class="brand-santa">SANTA</span><span class="brand-pray">🙏🏻</span><span class="brand-base">BASE</span></h1>
      <span class="badge-excel">📊 EXCEL PRO GRID</span>
    </div>'''

new_topbar_brand = '''    <div class="brand-group">
      <div class="santa-brand-logo" title="Santa Base">
        <span class="logo-pill-santa brand-santa">SANTA</span>
        <span class="logo-icon-pray brand-pray">🙏🏻</span>
        <span class="logo-text-base brand-base">BASE</span>
      </div>
    </div>'''

content = content.replace(old_topbar_brand, new_topbar_brand)

# 15. Anime.js Micro-Interactions in JS
old_fetch_stats_inner = '''        document.getElementById('stat-total').innerText = data.total.toLocaleString();
        document.getElementById('stat-curp').innerText = data.with_curp.toLocaleString();
        document.getElementById('stat-calc').innerText = (data.curp_calculada || 0).toLocaleString();
        document.getElementById('stat-no-curp').innerText = data.without_curp.toLocaleString();
        document.getElementById('stat-results').innerText = data.with_results.toLocaleString();'''

new_fetch_stats_inner = '''        animateCounter('stat-total', data.total);
        animateCounter('stat-curp', data.with_curp);
        animateCounter('stat-calc', data.curp_calculada || 0);
        animateCounter('stat-no-curp', data.without_curp);
        animateCounter('stat-results', data.with_results);'''

content = content.replace(old_fetch_stats_inner, new_fetch_stats_inner)

# Add animateCounter and Anime.js event listeners before initApp
anime_helpers = '''    function animateCounter(elementId, targetValue) {
      const el = document.getElementById(elementId);
      if (!el) return;
      if (typeof anime === 'undefined') {
        el.innerText = Number(targetValue).toLocaleString();
        return;
      }
      const rawCurrent = parseInt((el.innerText || '0').replace(/[^0-9]/g, '')) || 0;
      const obj = { val: rawCurrent };
      anime({
        targets: obj,
        val: targetValue,
        round: 1,
        duration: 900,
        easing: 'easeOutExpo',
        update: function() {
          el.innerText = obj.val.toLocaleString();
        }
      });
    }

    // Micro-interacción háptica elástica en botones con Anime.js
    document.addEventListener('click', (e) => {
      const btn = e.target.closest('.btn, .btn-login, .tab-btn, .mega-search-clear-btn');
      if (btn && typeof anime !== 'undefined') {
        anime({
          targets: btn,
          scale: [0.95, 1],
          duration: 180,
          easing: 'easeOutQuad'
        });
      }
    });

'''

if 'function animateCounter' not in content:
    content = content.replace('function initApp() {', anime_helpers + 'function initApp() {')

# Add table entrance stagger animation at the end of loadRecords
old_render_end = '''        tbody.innerHTML = html;
        updateSelectedSummary();
        renderActiveCell();'''

new_render_end = '''        tbody.innerHTML = html;
        updateSelectedSummary();
        renderActiveCell();

        // Stagger entrance suave para filas de datos con Anime.js
        if (typeof anime !== 'undefined') {
          anime({
            targets: '#table-body tr',
            opacity: [0, 1],
            translateY: [4, 0],
            delay: anime.stagger(8, { start: 20 }),
            duration: 220,
            easing: 'easeOutQuad'
          });
        }'''

content = content.replace(old_render_end, new_render_end)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("[OK] Red and Black design applied successfully!")
