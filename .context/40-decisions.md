# Decisiones de diseño

Cada decisión con su porqué. Las marcadas **[RESUELTA]** ya están reflejadas en el código.

## [RESUELTA] Técnicos = recursos, no usuarios
`appointment.type.schedule_based_on = 'resources'`. Cada técnico es un `appointment.resource`
ligado a un `hr.employee` (`visar_employee_id`).
- **Por qué:** los técnicos de campo no necesitan licencia/usuario Odoo para ser reservables.
- **Implica:** el filtrado de disponibilidad usa `filter_resources` (no `filter_users`).
- **Pendiente operativo:** para que la disponibilidad respete el horario y ausencias del
  empleado, el recurso debe compartir el `resource_id`/`resource_calendar_id` del empleado.
  El módulo `appointment_hr` (working hours) solo aplica al modo *users*.

## [RESUELTA] Inversión de flujo vía controlador + redirect (opción A), no override OWL/JS (B)
Página propia `prequalify` + redirect al horario nativo con `filter_resource_ids`.
- **Por qué:** el frontend de citas usa el framework **Interactions** (`@web/public/interaction`),
  no un SPA OWL. Patchear esas Interactions y su QWeb es frágil (≈7/10): un error JS rompe toda
  la página, los métodos no son API estable, y cada upgrade suele tocarlas. La opción A no toca
  nada de ese JS; solo depende de un parámetro de URL que el core ya sabe leer.
- **Costo de A:** 1–2 recargas de página (UX aceptable). Si luego se quiere UX sin recargas,
  hacerlo como mejora aislada y opcional.

## [ACTIVA — parcialmente resuelta] Captura de Zona y m² fuera de `appointment.question`
Se capturan en páginas propias del wizard/valoración y se guardan como campos en `calendar.event`
(`visar_zone_id`, `visar_booking_items`), **y además** se inyectan en el sistema nativo de respuestas.
- **Por qué original:** `appointment.question` no tiene tipo numérico (solo char/text/phone/select/radio/checkbox).
  Campos en `calendar.event` son directos de mostrar al administrativo.
- **Limitación conocida (legacy D-03):** el flujo prequalify numérico sigue usando `visar_m2` en cita;
  el wizard D-05 guarda rangos en `visar_booking_items`.
- **Implementado jun-2026 (híbrido):** preguntas en `visar_questions_data.xml` (zona, m², plaga,
  roedores, tipo plaga). `_visar_enrich_answer_inputs` las pobla en `appointment_answer_input_ids`
  al submit. Las preguntas **no** aparecen en el formulario nativo de horario (desvinculadas de tipos
  entrada en migración 19.0.2.0.12); sí en **Questions & Answers** del backend.
- **Mejora pendiente:** tipo `select` nativo para Zona (hoy char con texto); m² como char con etiqueta del tramo.

## [RESUELTA] Configuración del mapeo en la ficha del PRODUCTO + vista lista global
Pestaña "Visar / Citas" en `product.template` (campo `visar_appointment_type_id` que liga todo +
tabulador inline `visar_tier_ids`), más una vista lista global del modelo `visar.service.tier`.
- **Por qué:** el modelo mental del cliente es "servicios = productos"; configurar ahí es natural.
  La vista lista global da un panel de administración rápido sin entrar producto por producto.
- Enlace producto ↔ tipo de cita asumido **1:1** (validar con Visar si alguna vez es 1:N).

## [RESUELTA — D-04] Variantes nativas + tabla de tramos + pricelist por zona
- **Variante = servicio × rango de m²** (variantes nativas de Odoo). NO meter la zona como atributo.
- **Tramos en `visar.service.tier`** porque los rangos de m² **difieren por servicio**
  (Fum. interior: 1-250/251-500; Corte de pasto: 51-100) → un atributo "rango" compartido no sirve.
- **Zona = pricelist con %** (A=+15%, B=base, C=−10%), porque el tabulador resultó ser un %
  constante, no precios arbitrarios. Excepción: Valoración Técnica = $500 plano (regla fija con
  precedencia sobre la regla %).
- **Por qué no `price_extra`:** es **aditivo**; no modela un tabulador donde el precio de la
  combinación no es la suma de extras.
- **A validar con Visar:** que el +15%/−10% sea regla estable y no coincidencia de los valores
  actuales. Si fuera arbitrario por celda → migrar a ítems de pricelist `fixed` por variante×zona.

## [D-05 — VIGENTE] Wizard multi-servicio en lugar de selección nativa
El cliente ya no elige un `appointment.type` nativo: un **wizard propio de varios pasos**
(servicios → tipo de fumigación → dimensiones → zona) determina los servicios y variantes.
- **Por qué:** Visar necesita vender **combinaciones** (fumigación interior + exterior + corte) en
  una sola reserva, con reglas de precio cruzadas (combo, exterior aditivo). El flujo nativo 1-servicio
  no lo soporta.
- **Cómo:** mismo patrón que D-03 (páginas QWeb propias + estado en sesión, sin OWL/JS). Reusa la
  infraestructura de filtrado por zona y la redirección al horario nativo con `filter_resource_ids`.

## [D-05 — RESUELTA] Punto de entrada: cuadro nativo con dos tipos de cita
Se **conserva** el listado nativo `/appointment`, pero con **solo dos `appointment.type`**:
- **Valoración Técnica:** al elegirlo se pregunta **solo Zona** → horario → cita con producto $500.
- **Cita de Servicios:** al elegirlo se abre el **wizard completo** (servicios → fumigación →
  dimensiones → zona) → una cita con varias líneas.
- **Decisión Visar (22-jun-2026).** Enrutado por campo `appointment.type.visar_flow`
  (`valuation`/`wizard`) en el override `appointment_type_page`. Ancla técnica: `entry-point-d05`
  en `20-architecture.md`. **Implementado v19.0.2.0.3** (migraciones + self-healing `_visar_ensure_entry_flow`
  en controlador; pendiente mover a `post_init_hook`).
- **Nota:** la valoración existe en dos formas — (a) **tipo de cita directo** (este), y (b) **desde el wizard**
  cuando un tramo tiene `is_valuation=True`. En (b) ya **no** se agenda en el maestro Servicios Visar:
  se muestra un **aviso** y se redirige al mismo flujo que (a). Mismo producto $500.

## [D-05 — RESUELTA — jun-2026] Wizard con tramo valoración → flujo valoración directa
Cuando el cliente elige un rango marcado `is_valuation` en el wizard:
- **Antes (bug):** seguía al maestro **Servicios Visar** → SO correcta ($500) pero cita con nombre incorrecto.
- **Ahora:** paso **aviso** (`…/wizard/valoracion-aviso`) → pantalla `…/visar/valoracion` → horario del tipo
  **Valoración Técnica** → checkout $500.
- **Por qué:** el requisito D-04/D-05 dice *agendar visita de $500 en lugar del servicio directo*; la cita
  debe ser de valoración, no multi-servicio maestro.
- **Implementación:** `_visar_selections_require_valuation`, `_visar_get_valuation_appointment_type`,
  rutas aviso + redirect; plantilla `visar_wizard_valuation_notice`.

## [D-05 — RESUELTA] Una sola cita con varias líneas de producto
Una reserva multi-servicio genera **un** `calendar.event` y **una** orden de venta con **N líneas**
(una variante por servicio), no varias citas.
- **Decisión del cliente (22-jun-2026):** "se crea una sola cita pero se asignan/cobran varios
  productos con sus respectivas variantes". Confirmado explícitamente.
- **Implica:** un único horario común; intersección de técnicos elegibles de todos los servicios;
  el cobro suma todas las líneas en la misma SO.

## [D-05 — RESUELTA] Dimensiones como rangos (opciones), no m² numérico
El Paso 3 presenta **rangos predefinidos** (del tabulador) como opciones; cada rango = un
`visar.service.tier` → variante. Se elimina el input numérico libre de m².
- **Por qué:** el tabulador define precios por **rango cerrado**; elegir el rango resuelve variante y
  precio sin ambigüedad y evita capturar m² exactos.
- **Implica:** los tramos se vuelven la fuente de las opciones del wizard (añadir `name`/`label`).

## [D-05 — RESUELTA] Reglas del tabulador (ver `70-tabulador.md`)
Confirmadas con Visar el 22-jun-2026:
- **Exterior aditivo pero independiente:** fumigación exterior se cobra como línea aparte (tramo 0–50 m²
  = precio 0). **Se puede agendar sin interior.**
- **Combo −50% del corte:** aplica **solo** cuando la reserva incluye los **tres** servicios
  (interior + exterior + corte). La línea de corte va al 50% (factor `visar.combo_corte_factor = 0.5`,
  `ir.config_parameter`). Si falta cualquiera de los tres → corte a precio completo.
- **Valoración $500:** servicio fuera de rango → línea de Valoración Técnica $500 (plano, abonable);
  **una sola** línea aunque varios servicios la disparen (**provisional**, a reconfirmar).
- **Zona = pricelist con %** (A +15%, B base, C −10%); valoración $500 plano (precedencia sobre %).

## [D-05 — RESUELTA] Varios técnicos por cita
Con varios servicios, la cita puede tener **varios técnicos**: se asignan los necesarios para cubrir
**todos** los servicios elegidos; si un técnico no cubre todos, se agregan los que falten.
- **Decisión Visar (22-jun-2026):** "pueden ser varios por cita".
- **Implica:** la asignación NO es la intersección estricta (un técnico que cubra todo). Es una
  **cobertura**: para cada servicio, al menos un recurso elegible (servicio + zona) en la cita.
- **Agenda multi-técnico (RESUELTA, Visar 22-jun-2026):**
  - **Horario:** solo se ofrecen slots donde **todos** los técnicos requeridos estén libres a la vez.
  - **Modelo:** **un solo `calendar.event`** con **varios `appointment.resource`** (vía
    `booking_line_values` múltiples).
  - **Asignación:** cuando varios técnicos cubren un servicio, elegir **por carga** (el menos ocupado).
  - **Sin coincidencia:** si no hay slot común para todos, **mostrar mensaje al usuario** (no bloquear silencioso).

## Pendientes de confirmar con Visar
- ¿El +15%/−10% por zona y el factor combo 0.5 son reglas estables?
- ¿La valoración a **una** línea $500 es definitiva (hoy provisional)?
- ¿El enlace producto ↔ tipo de cita es siempre 1:1?

## [IMPLEMENTADO — jun-2026] Split en tres módulos

Monolito `visar_appointment` dividido para separar responsabilidades:

| Módulo | Responsabilidad |
|---|---|
| **`visar_base`** | Catálogos (zonas, grupos, dimensiones, tramos, combo, add-ons D-06), extensiones producto/SO |
| **`visar_fsm`** | Generación tareas FSM agrupadas (D-07), `post_init_hook` proyectos |
| **`visar_appointment`** | Wizard web, controlador, tipos entrada, plantillas, preguntas nativas |

- **Por qué:** D-06/D-07 no dependen del website; facilita reuso y despliegue incremental.
- **Dependencias:** `visar_appointment` → `visar_fsm` → `visar_base`.

## [IMPLEMENTADO — jun-2026] D-06 Add-ons obligatorios (Opción A + sumar)

- Modelo `visar.product.optional.line` en `visar_base`.
- M2m nativo `optional_product_ids` es selector; tabla se autogenera/reconcilia.
- Duplicados entre servicios: **SUMAR** cantidades.
- Inyección web en `_visar_build_sale_lines`; backend en `sale.order._visar_apply_mandatory_addons`.

## [IMPLEMENTADO — jun-2026] Calificación wizard + producto roedores

- Paso `…/wizard/calificacion` después de rangos (solo flujo normal, no valoración).
- `roedores=si` → producto `visar_is_roedores` + add-ons obligatorios de ese producto.
- Respuestas en Questions & Answers vía preguntas XML + `_visar_build_calification_answer_inputs`.

## [PARCIAL — jun-2026] D-07 FSM agrupado por proyecto

- `visar_fsm/models/sale_order_fsm.py`: override generación nativa, una tarea por `project_id`.
- Proyectos seedeados en `visar_fsm/hooks.py` (configurable vía `product.template.project_id`).
- Pendiente: worksheets, reportes, E2E app técnico.

## [IMPLEMENTADO — jun-2026] Datos demo: productos existentes, no XML

En `visar_local` los productos/variantes **ya existían** (con atributos **A/B/C × rango** en cada
variante, no solo pricelist). D-05 **no recrea** productos en XML:

- Enlace vía migración `19.0.2.0.7/post-migrate.py` (`_visar_migrate_legacy_catalog`).
- Tramos `visar.service.tier` apuntan a variantes **zona B + rango**; en checkout
  `_visar_variant_for_zone` elige la variante equivalente en la zona del cliente (A/B/C).
- Convive con pricelist por zona en la SO (doble mecanismo hasta decidir migración única).
