# Tarea — Ir al carrito (no al checkout) tras "Detalles sobre ti"

> Tarea accionable para aplicar con Cursor. Cambio acotado al redirect final del
> flujo de citas. **No** requiere tocar la construcción del carrito (ya está armado).

## Objetivo

En el flujo de pago de las citas del sitio web, después de que el cliente llena el
formulario nativo **"Detalles sobre ti"** (nombre / email / teléfono), **no** saltar
directo al checkout de pago. En su lugar, redirigir a la **página del carrito**
(`/shop/cart`) para que el cliente revise y desde ahí avance con el flujo normal de
ecommerce (carrito → checkout → pago).

## Contexto técnico

- Archivo: `visar_appointment/controllers/appointment.py`
- Método: `_redirect_to_payment(self, calendar_booking)`
- En ese punto el carrito **ya está construido** (líneas del SO con servicios, add-ons,
  roedores, pricelist de zona y `calendar.booking` asociado). Lo único que cambia es el
  destino del `request.redirect(...)` final.
- Seguro respecto al horario: lo creado es un `calendar.booking` (reserva temporal), no la
  cita confirmada. La `calendar.event` real se confirma al pagar; si el cliente abandona
  el carrito, la reserva temporal expira sola (mecanismo nativo Odoo). No se "quema" el slot.

## Cambio exacto

Hay **dos** `return request.redirect("/shop/checkout?try_skip_step=true")` al final del
método, uno por flujo. **Ambos** deben cambiar a `/shop/cart`:

1. Flujo **Valoración** (`booking.mode == 'valuation'`) — al cierre de ese bloque.
2. Flujo **Cita de Servicios** wizard (`booking.mode == 'wizard'`) — al cierre del método.

Reemplazo en ambos:

```python
# Antes
return request.redirect("/shop/checkout?try_skip_step=true")

# Después
return request.redirect("/shop/cart")
```

> Se elimina `try_skip_step=true` a propósito: ese parámetro saltaba el paso de dirección
> dentro del checkout; yendo al carrito ya no aplica y el cliente pasa por el flujo
> estándar de dirección/pago.

## Alcance

Aplica a **ambos** flujos (Valoración + Cita de Servicios). No tocar el bloque
`super()._redirect_to_payment(...)` (citas legacy sin booking Visar): ese mantiene su
comportamiento nativo.

## Validación

```bash
python -m py_compile visar_appointment/controllers/appointment.py
```

Prueba manual (servidor con módulos actualizados):
1. Hacer una "Cita de Servicios" completa hasta "Detalles sobre ti" → enviar.
2. Confirmar que cae en `/shop/cart` mostrando las líneas (servicios + add-ons) y que
   desde "Proceso de compra" continúa a checkout → pago.
3. Repetir con "Valoración Técnica" ($500) → debe caer también en `/shop/cart`.
