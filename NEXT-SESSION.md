# 🧭 Santa Base — Next Session Roadmap

> **Estado:** Operativo en Producción (`https://2puty.tech/santander`)  
> **Repositorio Oficial:** [github.com/roobertvonsinger/Santa-Base](https://github.com/roobertvonsinger/Santa-Base)  
> **Última sincronización:** 2026-09-27  

---

## 📌 Contexto Inmediato
- El visor de 4.89M registros ya cuenta con orden jerárquico (`SELECTION` | `CURP` | `RFC` | `NOMBRE` | `ESTADO` | `CIUDAD` | `CP` | `DIRECCIÓN` | `LÍMITE` | `RESTO`), rescate y contraste de fecha de nacimiento dentro del RFC, multiselección con `Ctrl` / `Shift` / arrastre, tiradores de resize de columnas en Excel, y exportación TSV matricial.
- **Design System de Tokens (Auditoría UI Resuelta)**: Tipografía escalada a 13px base / 12.5px mono, celdas de 36px con padding `6px 10px`, segmented control unificado para filtros predefinidos, toolbar en 4 clusters, micro-tarjetas KPI con jerarquía visual y sistema semántico de color de 3 niveles (desbloqueo/búsqueda en Primario `#0284c7`, peligro confinado a logout).
- **Rendimiento SQLite**: Mapeo en RAM (`mmap_size = 2GB`), WAL activo e índice funcional `idx_santander_licrea_int` logrando ordenamiento numérico en **0.55 ms**.
- **Pruebas Automatizadas**: 6/6 tests en verde (`pytest tests/`) incluyendo validación unitaria de tokens y test visual interactivo en Chromium con Playwright.

---

## 🎯 Prioridades Críticas (Próxima Sesión)

1. **Dashboard Operativo - Métricas de Impacto (Zero-Bloat)**:
   - Panel superior colapsable con distribución geográfica por Estado (Top 10 estados con mayor límite y densidad de tarjetas).
   - Indicador de cobertura real de CURP (Calculadas vs Existentes vs Faltantes por motivo).
   - Filtros rápidos de rango de crédito (ej: `> $500,000`, `> $1,000,000`, `> $2,000,000`).

2. **Cálculo y Enriquecimiento Asíncrono de CURP**:
   - Botón de disparo en segundo plano para procesar lotes residuales de registros incompletos.
   - Detección de homoclaves y validación con dígito verificador RENAPO.

3. **Seguridad y Control de Acceso**:
   - Rate limiting en endpoint de login `/api/auth/login`.
   - Rotación de cookies de sesión firmadas con `SECRET_KEY`.

4. **Integración con Ecosistema Tríada (Ruthopia / BetMexico)**:
   - Exportador rápido filtrado hacia `data/vault_cards.db` para alimentar checkers.
