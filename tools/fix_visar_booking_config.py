# -*- coding: utf-8 -*-
"""
Repara config de reservas Visar en una BD (datos, no código).
Corrige dos problemas que aparecen en instalaciones/dumps frescos:

  1. Preguntas 'Zona' y 'Metros cuadrados' marcadas obligatorias en los tipos
     de cita: el wizard las captura aparte, así que como obligatorias bloquean
     el submit ("Some required answers are missing").
  2. Reglas de pricelist DUPLICADas para una misma variante donde una tiene
     precio fijo 0: gana la de 0 -> la línea sale gratis -> el carrito la
     rechaza -> "no disponibilidad".

Uso (ajusta -d a tu BD):
  PYTHONPATH=/ruta/odoo:/ruta/repo .venv/bin/python setup/odoo shell \
      -c odoo.visar.conf -d <BD> --no-http < tools/fix_visar_booking_config.py
"""
from collections import defaultdict

# --- FIX 1: Zona/m² no obligatorias en todos los tipos de cita ---
qs = env['appointment.question'].search([
    ('name', 'in', ['Zona', 'Metros cuadrados']),
    ('question_required', '=', True),
])
print('FIX1 preguntas desactivadas:',
      [(q.appointment_type_id.name, q.name) for q in qs] or 'ninguna (ya estaban OK)')
qs.write({'question_required': False})

# --- FIX 2: borrar reglas de variante con precio fijo 0 cuando existe otra
#            regla (no-0) para la misma variante en la misma pricelist ---
borradas = 0
for pl in env['product.pricelist'].search([]):
    by_variant = defaultdict(list)
    for it in pl.item_ids.filtered(
            lambda i: i.applied_on == '0_product_variant' and i.product_id):
        by_variant[it.product_id.id].append(it)
    for vid, items in by_variant.items():
        if len(items) <= 1:
            continue
        zero = [i for i in items if i.compute_price == 'fixed' and not i.fixed_price]
        nonzero = [i for i in items if not (i.compute_price == 'fixed' and not i.fixed_price)]
        if zero and nonzero:   # duplicado con $0 -> quitar el $0
            print('FIX2 pricelist %r variante %s: borrando %d regla(s) $0' % (
                pl.name, vid, len(zero)))
            for i in zero:
                i.unlink()
                borradas += 1
print('FIX2 reglas $0 borradas:', borradas)

env.cr.commit()
print('--- COMMIT OK ---')
