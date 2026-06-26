# Mejoras para después (backlog)

> Lista viva de mejoras/deuda técnica **no bloqueantes**. Ir agregando aquí cosas que surjan.
> Lo **crítico para el go-live** va en `80-deploy-prod.md`, no aquí.
> Formato sugerido por ítem: qué, por qué, opción/recomendación, prioridad.

## I-01 — Quitar self-healing de `visar_flow` y fallback de config params
- **Qué:** `_visar_ensure_entry_flow` escribe `visar_flow` en la BD durante un **GET público**;
  `_visar_resolve_entry_flow` añade un fallback por `ir.config_parameter`.
- **Por qué:** es un parche por la fragilidad del setup actual. Escribir en requests de lectura es
  *smell* (efectos colaterales, locking, perf).
- **Recomendación:** una vez el setup sea confiable en install (ver `80-deploy-prod.md` #1), eliminar
  ambos. Queda atado a ese fix.
- **Prioridad:** Media (depende del fix de deploy).

## I-02 — Aislar y testear `_visar_filter_slots_multi_service`
- **Qué:** re-camina y reconstruye el árbol nativo de slots (months/weeks/days/slots,
  `url_parameters`, `available_resources`). Es lo más sensible a upgrades de Odoo.
- **Por qué:** es el corazón frágil del multi-técnico; lo primero que se rompe en una actualización.
- **Recomendación:** (a) aislarlo + prueba unitaria; (b) evaluar mostrar la **unión** de recursos en la
  lista y validar la coincidencia **solo en el submit** (ya se re-eligen recursos ahí), para quitar el
  override más pesado.
- **Prioridad:** Media.

## I-03 — Simplificar `visar.combo.rule` (o su doble elegibilidad)
- **Qué:** modelo genérico (required/discount dimensions + factor + vista + menú + ACL + seeding +
  flag `combo_discount_eligible` en tier) para **una** regla del spec (interior+exterior+corte → 50%
  al corte).
- **Por qué:** más superficie de la necesaria si el combo es fijo. Además hay **doble mecanismo** de
  elegibilidad: `discount_dimension_ids` y `tier.combo_discount_eligible` hacen lo mismo.
- **Recomendación (criterio):** ¿Visar prevé más de un combo o ajustarlo sin redeploy?
  - **Sí** → conservar el modelo, pero **dejar un solo** mecanismo de elegibilidad.
  - **No (regla fija)** → colapsar a `ir.config_parameter visar.combo_corte_factor` + check por código
    de dimensión en `_visar_build_sale_lines`.
## I-04 — Hook de install para catálogo `visar_appointment`
- **Qué:** `_visar_migrate_legacy_catalog` y setup tipos entrada solo en migraciones; no hay `post_init_hook` en `visar_appointment`.
- **Por qué:** install limpio en prod queda sin grupos/dimensiones/combo. `visar_fsm` ya tiene hook; falta el equivalente citas.
- **Recomendación:** ver `80-deploy-prod.md` Parte 1.
- **Prioridad:** Alta (bloqueante go-live).
</content>
