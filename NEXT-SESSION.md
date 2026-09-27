# 🧭 Santa Base — Next Session Roadmap

> **Estado:** Operativo en Producción (`https://2puty.tech/santander`)  
> **Repositorio Oficial:** [github.com/roobertvonsinger/Santa-Base](https://github.com/roobertvonsinger/Santa-Base)  
> **Última sincronización:** 2026-09-27  

---

## 📌 Contexto Inmediato
- El visor de 4.89M registros ya cuenta con orden jerárquico (`SELECTION` | `CURP` | `RFC` | `NOMBRE` | `ESTADO` | `CIUDAD` | `CP` | `DIRECCIÓN` | `LÍMITE` | `RESTO`), rescate y contraste de fecha de nacimiento dentro del RFC, multiselección con `Ctrl` / `Shift` / arrastre, tiradores de resize de columnas en Excel, y exportación TSV matricial.
- **Rendimiento SQLite**: Mapeo en RAM (`mmap_size = 2GB`), WAL activo e índice funcional `idx_santander_licrea_int` logrando ordenamiento numérico en **0.55 ms**.
- **Pruebas Automatizadas**: Suite en verde (`pytest tests/test_api.py`) y prueba Chromium Playwright validada.

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
