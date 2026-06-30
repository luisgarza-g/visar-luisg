# Arquitectura — módulos Visar

Odoo 19 Enterprise. El proyecto se divide en **tres módulos** con dependencia en cadena:

```
visar_base  →  visar_fsm  →  visar_appointment
```

> **Estado 26-jun-2026:** D-05/D-06 codificados + D-07 parcial (incl. UI tarea FSM) + paso calificación +
> respuestas nativas híbridas. Repo Git: `github.com/luisgarza-g/visar-luisg`.

---

## `visar_base` (v19.0.1.0.0)

**Dependencias:** `sale`, `product`, `appointment`.

Catálogos y lógica de negocio compartida (tabulador, precios, add-ons).

### Modelos propios

| Modelo | Archivo | Para qué |
|---|---|---|
| `visar.zone` | `models/visar_zone.py` | Zonas A/B/C. Campos: `name`, `code`, `sequence`, `active`, **`pricelist_id`**. |
| `visar.service.group` | `models/visar_service_group.py` | Grupos del wizard (paso 1). `dimension_ids`, `show_in_wizard`, `wizard_label`. |
| `visar.service.dimension` | `models/visar_service_dimension.py` | Sub-servicio / dimensión. Enlaza `product_tmpl_id`, tier field name. |
| `visar.service.tier` | `models/visar_service_tier.py` | Tramo → variante. `name`, `m2_min`, `m2_max`, `product_id`, **`is_valuation`**, `is_free`, `combo_discount_eligible`. |
| `visar.combo.rule` | `models/visar_combo_rule.py` | Reglas de descuento combo configurables. |
| `visar.product.optional.line` | `models/visar_product_optional_line.py` | Add-ons con **`is_mandatory`** y **`quantity`** (D-06). |

### Extensiones

| Modelo | Archivo | Campos / helpers |
|---|---|---|
| `product.template` | `models/product_template.py` | `visar_is_service`, `visar_is_valuation`, **`visar_is_roedores`**, `visar_dimension_id`, `visar_tier_ids`, **`visar_optional_line_ids`**. Helpers: `_visar_get_mandatory_addon_map`, `_visar_get_valuation_template`, `_visar_get_roedores_template`, `_visar_variant_for_zone`. |
| `sale.order` | `models/sale_order.py` | `_visar_apply_mandatory_addons`. |
| `sale.order.line` | `models/sale_order_line.py` | Auto-inyección add-ons obligatorios en backend (onchange/create/write). |
| `res.config.settings` | `models/res_config_settings.py` | Producto valoración, factor combo legacy. |

### Vistas / menús

Backend bajo **Citas → Configuración**: Zonas, Grupos de servicio, Tabulador, Reglas de combo.
Pestaña Visar en producto + tabla add-ons junto a `optional_product_ids`.

### Datos

`data/visar_tabulador_data.xml` — placeholder vacío; catálogo se configura en backend (no XML de productos).

---

## `visar_fsm` (v19.0.1.0.2)

**Dependencias:** `visar_base`, `appointment`, `hr`, `industry_fsm`, `industry_fsm_sale`.

Generación de tareas FSM al confirmar pedidos Visar (D-07).

### Extensiones

| Modelo | Archivo | Qué hace |
|---|---|---|
| `sale.order.line` | `models/sale_order_fsm.py` | Override `_timesheet_service_generation`: agrupa líneas Visar por `project_id` → **una tarea por proyecto**; asigna add-ons como materiales; enriquece tareas. |
| `sale.order` | `models/sale_order_fsm.py` | `_visar_enrich_fsm_tasks` — copia `planned_date_begin`/`date_deadline`, **`visar_technician_ids`** (empleados) y `user_ids` desde `calendar.event`. |
| `project.task` | `models/project_task.py` | **`visar_sale_order_id`** (related a `sale_order_id`) + **`visar_technician_ids`** (M2m `hr.employee`) — asignación real por empleado (sustituye `user_ids`, vacío sin usuarios). |
| `calendar.event` | `models/calendar_event.py` | `visar_fsm_task_ids` (computed M2m). |
| `appointment.resource` | `models/appointment_resource.py` | (vista backend) |

### Vistas

| Archivo | Qué hace |
|---|---|
| `views/project_task_views.xml` | Oculta `sale_line_id` nativo; muestra `visar_sale_order_id` + `visar_technician_ids`. **Reemplaza el Gantt FSM** (`industry_fsm.fsm_project_task_view_gantt`): `default_group_by=visar_technician_ids`, `edit=0` (solo lectura), sin `progress_bar`/`display_unavailability` (calculan sobre `user_ids`). |
| `views/fsm_technician_planning.xml` | Acción + menú **Field Service → Planning → Por técnico** (`action_fsm_planning_by_technician`): Gantt por técnico de **todos** los técnicos, **sin** el filtro `search_default_my_tasks` de la pantalla "Mis tareas". |

> **Gantt por técnico:** una fila por empleado, barras = tareas FSM por `planned_date_begin`/`date_deadline`. La asignación NO cambia de origen (recurso de la cita → empleado en la tarea); solo cambia el campo y la vista. Para despacho usar **Planning → Por técnico** (la pantalla "Mis tareas" filtra por tu usuario y oculta tareas de técnicos sin usuario).

### Setup — `hooks.py`

`post_init_hook` → `_visar_setup_fsm_projects(env)`:
- Crea/busca proyectos FSM: **Fumigación**, **Mantenimiento Áreas Verdes**, **Valoraciones / Inspecciones**.
- Asigna `service_tracking='task_global_project'` + `project_id` a productos según dimensión (`code` prefix) o `visar_is_valuation`.
- IDs guardados en `ir.config_parameter` (`visar.fsm_project_*_id`).

> Este hook **sí corre en `-i`**. Re-ejecutado también en migración `visar_appointment` 19.0.2.0.14.

---

## `visar_field_app` (v19.0.1.0.1)

**Dependencias:** `visar_fsm`, `website`, `industry_fsm_report`.

App web para técnicos de campo, **patrón POS / `pos_hr`**: un dispositivo, identificación
por **PIN**, **sin usuario interno de Odoo** (no consume licencia). Resuelve la tensión
"técnicos = recursos, no usuarios" del lado de ejecución: permite captura en campo y
**atribución por técnico** (comisiones de upsell, auditoría) sin licenciar a cada técnico.

> **Por qué portal y no la página nativa de FSM:** la worksheet/tarea nativa es backend y
> exige usuario interno. La app de portal escribe en los **modelos nativos** (worksheet
> dinámica, firma, adjuntos) por detrás vía controlador — misma estructura de datos, otra
> puerta de entrada. Mismo patrón que el wizard de citas (QWeb + controlador, sin OWL nativo).

> **Worksheet y reportes = 100% nativos.** La app renderiza dinámicamente los campos `x_`
> de la worksheet (`worksheet.template.model_id`, leyendo el form view nativo y `fields_get`)
> y los escribe en el registro `x_project_task_worksheet_template_<id>` (uno por tarea, enlace
> `x_project_task_id`). La firma usa los campos nativos `worksheet_signature` /
> `worksheet_signed_by`. Así el **reporte nativo** (`industry_fsm.worksheet_custom`) se genera
> sin cambios. La worksheet se configura como siempre (plantilla por proyecto).

### Modelos

| Modelo | Archivo | Para qué |
|---|---|---|
| `visar.field.session` | `models/field_session.py` | "Turno" del técnico (abre login PIN, cierra logout). `employee_id`, `date_start/end`, `state`. |
| `hr.employee` | `models/hr_employee.py` | **`visar_field_pin`** + `_visar_field_find_by_pin`. |
| `project.task` | `models/project_task.py` | Atribución `visar_field_closed_by_id/_at`. (La asignación `visar_technician_ids` se movió a **`visar_fsm`**.) Firma/worksheet/reporte = campos nativos. |
| _(sin extensión de `sale.order`)_ | — | El poblado de `visar_technician_ids` lo hace `visar_fsm._visar_enrich_fsm_tasks`. |

### Controlador — `controllers/main.py` (`type='http', auth='public'`)

Sesión HTTP: `visar_field_employee_id`, `visar_field_session_id`. Todo en sudo, **acotado
estrictamente** al empleado de la sesión (`_task_for_employee`).

| Ruta | Qué hace |
|---|---|
| `GET /visar/field` + `POST …/login` | Login por PIN → crea `visar.field.session`. |
| `POST …/logout` | Cierra el turno. |
| `GET …/tasks` | Servicios del técnico (`visar_technician_ids in employee`, no cerrados). |
| `GET …/task/<id>` | Detalle + fotos + worksheet dinámica + firma. |
| `POST …/task/<id>/photo` | Sube fotos → `ir.attachment` sobre la tarea. |
| `GET …/task/<id>/image/<att_id>` | Sirve adjunto (acotado al técnico de la sesión). |
| `POST …/task/<id>/worksheet` | Escribe los campos `x_` de la worksheet nativa. |
| `POST …/task/<id>/close` | Firma nativa + `state='1_done'` + estampa `visar_field_closed_by_id`. |
| `GET …/task/<id>/report` | PDF del reporte nativo (`_render_qweb_pdf`). |

Helpers worksheet: `_worksheet_model`, `_worksheet_record(create=)`, `_worksheet_field_names`
(orden del form view), `_worksheet_field_descriptors`, `_worksheet_write_values` (coerción por ttype).

### Frontend — `views/field_app_templates.xml` + assets

Plantillas QWeb (`website.layout`): login, lista, detalle. La worksheet se renderiza por tipo
de campo (char/text/html/select/m2o/boolean/number/date/binary). Firma con `<canvas>` →
`static/src/js/field_app.js` (vanilla, sin OWL) vuelca dataURL a `worksheet_signature`.

### Limitación aceptada

NO usa features de "actor" nativas (timesheet propio, notificaciones, "Mis tareas" nativo) —
esas requieren usuario interno. La worksheet **sí** es la nativa (su registro y reporte), solo
que capturada desde el portal. El v1 del form no edita campos relacionales o2m/m2m.

---

## `visar_appointment` (v19.0.2.0.15)

**Dependencias:** `visar_base`, `visar_fsm`, `website_appointment`, `website_appointment_sale`, `website_sale`, `hr`, `worksheet`.

Wizard web, controlador de citas, tipos de entrada y plantillas frontend.

### Extensiones

| Modelo | Archivo | Campos / helpers |
|---|---|---|
| `appointment.type` | `models/appointment_type.py` | `visar_product_tmpl_ids`, `visar_is_master`, **`visar_flow`**. Helpers: `_visar_get_master_appointment_type`, `_visar_get_valuation_appointment_type`, `_visar_resolve_wizard_items`, **`_visar_build_sale_lines`** (incluye add-ons + roedores), `_visar_service_resource_pools`, `_visar_filter_slots_multi_service`, `_visar_quote_booking`, **`_visar_build_native_answer_inputs`**. |
| `appointment.resource` | `models/appointment_resource.py` | `visar_zone_ids`, `visar_service_ids`. |
| `calendar.event` | `models/calendar_event.py` | `visar_zone_id`, `visar_m2` (legacy), **`visar_booking_items`**. |
| `product.template` | `models/product_template.py` | `visar_appointment_type_id` (enlace 1:1 tipo cita). Vista: reordena `optional_product_ids` + tabla add-ons en pestaña Ventas. |
| `sale.order` | `models/sale_order.py` | `_visar_apply_zone_pricelist`. |

### Datos — `data/visar_questions_data.xml`

Preguntas reutilizables para Questions & Answers: Zona, m², plaga, roedores, tipo de plaga.
**No** se muestran en el formulario nativo de cita (desvinculadas de tipos entrada vía migración 19.0.2.0.12).

### Migraciones — catálogo legacy

`migrations/19.0.2.0.7/post-migrate.py` → `_visar_migrate_legacy_catalog`: crea grupos/dimensiones desde campos legacy del producto, enlaza tramos, regla combo. **Solo corre en `-u`.**

`migrations/19.0.2.0.15/post-migrate.py` → marcador de versión tras split en 3 módulos (sin lógica adicional).

### Controlador — `controllers/appointment.py`

Hereda **`WebsiteAppointmentSale`**. Sesión: `SESSION_KEY = 'visar_booking'`.

| Método / ruta | Qué hace |
|---|---|
| **`GET /appointment`** | Cuadro nativo; dominio `visar_flow` ∈ {valuation, wizard}. |
| **`GET /appointment/visar/booking`** | Inicia wizard (paso 1 grupos). |
| **POST …/wizard/services** | Paso 1 → substeps o dimensiones. |
| **GET/POST …/wizard/group/<id>** | Sub-paso dimensiones de un grupo. |
| **GET/POST …/wizard/dimensiones** | Paso rangos; si `is_valuation` → aviso; si no → calificación. |
| **GET/POST …/wizard/calificacion** | Plaga/preventivo, roedores, tipo de plaga. |
| **GET …/wizard/valoracion-aviso** | Aviso: requiere visita valoración $500. |
| **POST …/wizard/valoracion-aviso/continuar** | → `…/visar/valoracion?from_wizard=1`. |
| **POST …/wizard/zona** | Zona → items + pools → redirect maestro (solo flujo normal). |
| `appointment_type_page` | Enruta por `visar_flow` / wizard completo / legacy prequalify. |
| **GET/POST …/visar/valoracion** | Valoración directa o post-wizard: solo Zona → `mode=valuation`. |
| `_visar_enrich_answer_inputs` | Inyecta respuestas Visar en `appointment_answer_input_ids`. |
| `_visar_appointment_quote_context` | Cotización sidebar (wizard, valoración). |
| `_get_slots_from_filter` | Post-filtro multi-técnico (wizard normal). |
| `_redirect_to_payment` | Wizard: N líneas SO (+ add-ons + roedores); valoración: una línea $500. |

### Sesión `visar_booking`

Modo wizard (servicios normales):

```python
{
  'mode': 'wizard',
  'master_appointment_type_id': <id maestro Servicios Visar>,
  'zone_id': 5,
  'selections': {
    'group_ids': [...], 'dimension_ids': [...], 'tier_<dim_id>': <tier_id>,
    'plaga': 'preventivo|plaga', 'roedores': 'si|no', 'tipo_plaga': [...],
  },
  'items': [{'dimension_id', 'tier_id', 'variant_id', 'is_valuation': False, ...}],
  'service_pools': {'<dimension_id>': [resource_ids]},
}
```

### Reglas de precio (D-04/D-05/D-06)

- Combo: reglas `visar.combo.rule` + factor legacy `visar.combo_corte_factor`.
- Valoración: **una** línea $500 si cualquier item `is_valuation`.
- Add-ons obligatorios: sumados por servicio (y por producto roedores si `roedores=si`).
- Zona: pricelist en SO; precio web vía `_get_and_cache_current_pricelist()` (Odoo 19).

## Vistas frontend (`visar_appointment`)

| Archivo | Contenido |
|---|---|
| `views/wizard_templates.xml` | Wizard + **`visar_wizard_calificacion`** + aviso valoración + zona |
| `views/valoracion_templates.xml` | Valoración (`from_wizard`) |
| `views/appointment_templates_appointments.xml` | Sidebar precio multi-línea (`visar_appointment_info_price`) |

## Diagrama de flujos

```
GET /appointment
   ├─ Valoración Técnica (visar_flow=valuation)
   │     └─ …/visar/valoracion → horario → SO $500 (cita tipo Valoración)
   └─ Cita de Servicios (visar_flow=wizard)
         └─ GET /appointment/visar/booking
                ├─ rangos con is_valuation
                │     └─ …/wizard/valoracion-aviso → …/visar/valoracion → horario Valoración
                └─ rangos normales
                      └─ calificación → wizard/zona → maestro Servicios Visar
                            → horario multi-técnico → SO N líneas (+ add-ons)
                                  → confirmar pago → tareas FSM (1 por proyecto)

visar_base: product.template ── visar_tier_ids ──► visar.service.tier ──► product.product
visar_base: visar.zone ── pricelist_id ──► product.pricelist (% zona; Valoración $500 fijo)
visar_fsm:  sale.order.line ── task_id ──► project.task (FSM, agrupado por project_id)
```
