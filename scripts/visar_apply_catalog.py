# -*- coding: utf-8 -*-
"""Catálogo Visar — productos unificados del dump main (como en prod).

Un solo producto con variantes por servicio; NO productos split legacy:
  • Fumigación interior o exterior (interior + exterior = dimensiones del mismo producto)
  • Mantenimiento de áreas verdes (corte del combo)
  • Visita de valoración técnica, Control de roedores, Estación antirroedores

Legacy a desactivar: Fumigación interior, Fumigación exterior, Corte de pasto, COMBO split.

  odoo shell -d visar_main_dump --no-http < scripts/visar_apply_catalog.py
"""
import json
from datetime import datetime, timezone

# Variantes zona B — fallback IDs (se resuelven dinámicamente si cambian)
TIER_VARIANTS = {
    'fumigacion_interior': {
        (1, 250): 504,
        (251, 500): 508,
        (501, 1000): 512,
        (1001, 99999): 614,
    },
    'fumigacion_exterior': {
        (0, 50): 504,
        (51, 100): 505,
        (101, 500): 506,
        (501, 99999): 614,
    },
    'corte_poda': {
        (0, 50): 544,
        (51, 100): 545,
        (101, 150): 546,
        (151, 200): 547,
        (201, 99999): 614,
    },
}

TIER_LABELS = {
    ('fumigacion_interior', (1, 250)): '1 – 250 m²',
    ('fumigacion_interior', (251, 500)): '251 – 500 m²',
    ('fumigacion_interior', (501, 1000)): '501 – 1,000 m²',
    ('fumigacion_interior', (1001, 99999)): 'Más de 1,000 m² (valoración técnica)',
    ('fumigacion_exterior', (0, 50)): '0 – 50 m² (incluida)',
    ('fumigacion_exterior', (51, 100)): '51 – 100 m²',
    ('fumigacion_exterior', (101, 500)): '101 – 500 m²',
    ('fumigacion_exterior', (501, 99999)): 'Más de 500 m² (valoración técnica)',
    ('corte_poda', (0, 50)): '0 – 50 m²',
    ('corte_poda', (51, 100)): '51 – 100 m²',
    ('corte_poda', (101, 150)): '101 – 150 m²',
    ('corte_poda', (151, 200)): '151 – 200 m²',
    ('corte_poda', (201, 99999)): 'Más de 200 m² (valoración técnica)',
}

TIER_PRICES_B = {
    ('fumigacion_interior', (1, 250)): 600,
    ('fumigacion_interior', (251, 500)): 800,
    ('fumigacion_interior', (501, 1000)): 1000,
    ('fumigacion_exterior', (0, 50)): 0,
    ('fumigacion_exterior', (51, 100)): 800,
    ('fumigacion_exterior', (101, 500)): 1000,
    ('corte_poda', (0, 50)): 800,
    ('corte_poda', (51, 100)): 1000,
    ('corte_poda', (101, 150)): 1200,
    ('corte_poda', (151, 200)): 1400,
}

APT_TYPES = {
    'interior': 4,
    'corte': 8,
    'wizard': 6,
    'master': 7,
    'valuation': 5,
    'mantenimiento_legacy': 9,
}

FSM_PROJECTS = {'fumigacion': 17, 'corte': 18, 'valoracion': 19}

LEGACY_PRODUCT_PATTERNS = [
    ('Fumigación interior', ('interior o exterior', 'interior + exterior')),
    ('Fumigación exterior', ()),
    ('Fumigación correctiva', ()),
    ('Corte de pasto y poda', ()),
    ('COMBO - Fumigación', ()),
]

_INTERIOR_HINT = {
    (1, 250): '1-250',
    (251, 500): '251 - 500',
    (501, 1000): '501 - 1000',
    (1001, 99999): None,
}
_GARDEN_HINT = {
    (0, 50): '0 - 50',
    (51, 100): '51 - 100',
    (101, 500): '101 - 500',
    (501, 99999): None,
}
_CORTE_HINT = {
    (0, 50): '0 - 50',
    (51, 100): '51 - 100',
    (101, 150): '101 - 150',
    (151, 200): '151 - 200',
    (201, 99999): None,
}


def _tname(record):
    if not record:
        return ''
    return record.name if isinstance(record.name, str) else (record.name or '')


def _find_product(env, *name_patterns, exclude=None):
    Product = env['product.template'].sudo()
    exclude = [e.lower() for e in (exclude or [])]
    for pattern in name_patterns:
        for product in Product.search([('name', 'ilike', pattern)]):
            n = _tname(product).lower()
            if any(ex in n for ex in exclude):
                continue
            return product
    return Product.browse()


def _find_mantenimiento(env):
    Product = env['product.template'].sudo()
    for product in Product.search([('name', 'ilike', 'Mantenimiento de áreas verdes')]):
        if 'especializado' not in _tname(product).lower():
            return product
    for product in Product.search([('name', 'ilike', 'Corte de pasto')]):
        n = _tname(product).lower()
        if 'y poda' in n or 'combo' in n:
            continue
        if len(product.product_variant_ids) >= 4:
            return product
    return Product.browse()


def _resolve_catalog_products(env):
    fumigacion = _find_product(
        env,
        'Fumigación interior o exterior',
        'Fumigación interior + exterior',
        'interior + exterior',
    )
    mantenimiento = _find_mantenimiento(env)
    valoracion = _find_product(env, 'Visita de valoración técnica', 'valoración técnica')
    roedores = _find_product(env, 'Control de roedores')
    estacion = _find_product(env, 'Estación antirroedores')

    missing = []
    for key, rec in [
        ('fumigacion', fumigacion),
        ('mantenimiento', mantenimiento),
        ('valoracion', valoracion),
        ('roedores', roedores),
        ('estacion', estacion),
    ]:
        if not rec:
            missing.append(key)
    if missing:
        raise ValueError('Productos no encontrados en catálogo: %s' % ', '.join(missing))

    return {
        'fumigacion': fumigacion,
        'mantenimiento': mantenimiento,
        'valoracion': valoracion,
        'control_roedores': roedores,
        'estacion_antirroedores': estacion,
    }


def _tier_tmpl_map(products):
    fum = products['fumigacion'].id
    mant = products['mantenimiento'].id
    return {
        'fumigacion_interior': fum,
        'fumigacion_exterior': fum,
        'corte_poda': mant,
    }


def _set_record_translations(record, field_values_by_lang):
    """Escribe campos traducibles en cada idioma instalado."""
    for lang, values in field_values_by_lang.items():
        record.with_context(lang=lang).write(values)


def _set_appointment_type_labels(apt, es_name, en_name=None):
    _set_record_translations(apt, {
        'es_MX': {'name': es_name},
        'en_US': {'name': en_name or es_name},
    })


def _deactivate_legacy_products(env):
    Product = env['product.template'].sudo()
    for pattern, skip_if in LEGACY_PRODUCT_PATTERNS:
        for product in Product.search([('name', 'ilike', pattern)]):
            n = _tname(product).lower()
            if any(s in n for s in skip_if):
                continue
            product.write({'active': False, 'visar_is_service': False})


def _price_zone(base, zone_code):
    if base == 500:
        return 500
    if zone_code == 'A':
        return round(base * 1.15, 2)
    if zone_code == 'C':
        return round(base * 0.90, 2)
    return base


def _variant_b_zone(env, dim_code, m2_range, zone_code, tier_tmpl):
    Product = env['product.product'].sudo()
    tmpl_id = tier_tmpl[dim_code]
    fallback = TIER_VARIANTS[dim_code].get(m2_range)
    if m2_range[1] >= 99999:
        return Product.browse(fallback)

    if dim_code in ('fumigacion_interior', 'fumigacion_exterior'):
        interior_hint = _INTERIOR_HINT.get(m2_range) if dim_code == 'fumigacion_interior' else '1-250'
        garden_hint = _GARDEN_HINT.get(m2_range) if dim_code == 'fumigacion_exterior' else '0 - 50'
        if dim_code == 'fumigacion_interior' and not interior_hint:
            return Product.browse(fallback)
        if dim_code == 'fumigacion_exterior' and not garden_hint:
            return Product.browse(fallback)
        for variant in Product.search([('product_tmpl_id', '=', tmpl_id)]):
            attrs = variant.product_template_attribute_value_ids.mapped('name')
            if zone_code not in attrs:
                continue
            if interior_hint and interior_hint not in attrs:
                continue
            if garden_hint and garden_hint not in attrs:
                continue
            return variant
    else:
        hint = _CORTE_HINT.get(m2_range)
        for variant in Product.search([('product_tmpl_id', '=', tmpl_id)]):
            attrs = variant.product_template_attribute_value_ids.mapped('name')
            if zone_code in attrs and hint and hint in attrs:
                return variant
    return Product.browse(fallback)


def apply_visar_catalog(env):
    products = _resolve_catalog_products(env)
    tier_tmpl = _tier_tmpl_map(products)
    tmpl_ids = list({products['fumigacion'].id, products['mantenimiento'].id})

    Group = env['visar.service.group'].sudo()
    Dimension = env['visar.service.dimension'].sudo()
    Zone = env['visar.zone'].sudo()
    Tier = env['visar.service.tier'].sudo()
    ComboRule = env['visar.combo.rule'].sudo()
    Product = env['product.template'].sudo()
    AptType = env['appointment.type'].sudo()
    Resource = env['appointment.resource'].sudo()
    Param = env['ir.config_parameter'].sudo()
    Pricelist = env['product.pricelist'].sudo()

    _deactivate_legacy_products(env)

    for extra_id in (10, 11, 12):
        extra = AptType.browse(extra_id)
        if extra.exists():
            extra.write({'active': False, 'visar_is_master': False, 'visar_flow': False})

    groups_spec = [
        ('fumigacion', 'Fumigación', 10, [
            ('fumigacion_interior', 'Interior', 10),
            ('fumigacion_exterior', 'Exterior', 20),
        ]),
        ('corte', 'Mantenimiento de áreas verdes', 20, [
            ('corte_poda', 'Corte de pasto (combo)', 10),
        ]),
    ]
    dim_by_code = {}
    for g_code, g_name, g_seq, dims in groups_spec:
        group = Group.search([('code', '=', g_code)], limit=1)
        gvals = {'name': g_name, 'code': g_code, 'sequence': g_seq,
                 'show_in_wizard': True, 'wizard_label': g_name, 'active': True}
        group.write(gvals) if group else Group.create(gvals)
        group = Group.search([('code', '=', g_code)], limit=1)
        for d_code, d_name, d_seq in dims:
            dimension = Dimension.search([('code', '=', d_code)], limit=1)
            tmpl_id = tier_tmpl[d_code]
            dvals = {'group_id': group.id, 'name': d_name, 'code': d_code,
                     'sequence': d_seq, 'product_tmpl_id': tmpl_id, 'active': True}
            dimension.write(dvals) if dimension else Dimension.create(dvals)
            dim_by_code[d_code] = Dimension.search([('code', '=', d_code)], limit=1)

    fumigacion = products['fumigacion']
    mantenimiento = products['mantenimiento']
    valoracion = products['valoracion']
    roedores = products['control_roedores']
    estacion = products['estacion_antirroedores']

    website_publish = {'sale_ok': True, 'is_published': True}
    fumigacion.write({
        'active': True, 'visar_is_service': True,
        'visar_appointment_type_id': APT_TYPES['interior'],
        'name': 'Fumigación interior o exterior (anti-rastreros, anti-voladores y anti-roedores)',
        **website_publish,
    })
    mantenimiento.write({
        'active': True, 'visar_is_service': True,
        'visar_dimension_id': dim_by_code['corte_poda'].id,
        'visar_appointment_type_id': APT_TYPES['corte'],
        'name': 'Mantenimiento de áreas verdes',
        **website_publish,
    })
    valoracion.write({
        'active': True, 'visar_is_valuation': True, 'visar_is_service': True,
        'visar_appointment_type_id': APT_TYPES['valuation'],
        'list_price': 500.0,
        **website_publish,
    })
    roedores.write({'active': True, 'visar_is_roedores': True, **website_publish})
    estacion.write({'active': True, 'sale_ok': True, 'is_published': True})

    roedores.write({'optional_product_ids': [(4, estacion.id)]})
    OptionalLine = env['visar.product.optional.line'].sudo()
    line = OptionalLine.search([
        ('product_tmpl_id', '=', roedores.id),
        ('optional_product_id', '=', estacion.id),
    ], limit=1)
    if line:
        line.write({'is_mandatory': True, 'quantity': 3})
    else:
        OptionalLine.create({
            'product_tmpl_id': roedores.id,
            'optional_product_id': estacion.id,
            'is_mandatory': True, 'quantity': 3,
        })

    Tier.search([('product_tmpl_id', 'in', tmpl_ids)]).unlink()
    val_variant = valoracion.product_variant_id.id
    for dim_code, ranges in TIER_VARIANTS.items():
        tmpl_id = tier_tmpl[dim_code]
        for m2_range, variant_id_b in ranges.items():
            m2_min, m2_max = m2_range
            is_valuation = m2_max >= 99999
            is_free = dim_code == 'fumigacion_exterior' and m2_range == (0, 50)
            Tier.create({
                'product_tmpl_id': tmpl_id,
                'name': TIER_LABELS.get((dim_code, m2_range), ''),
                'm2_min': m2_min, 'm2_max': m2_max,
                'product_id': val_variant if is_valuation else variant_id_b,
                'is_valuation': is_valuation,
                'is_free': is_free,
                'combo_discount_eligible': dim_code == 'corte_poda' and not is_valuation,
            })

    zone_by_code = {}
    for code, name, seq in [
        ('A', 'Zona A (San Pedro)', 10),
        ('B', 'Zona B (base)', 20),
        ('C', 'Zona C (periferia)', 30),
    ]:
        pl_name = 'VISAR Zona %s' % code if code != 'B' else 'VISAR base (Zona B)'
        pl = Pricelist.search([('name', 'ilike', pl_name)], limit=1)
        if not pl:
            pl = Pricelist.create({'name': pl_name, 'currency_id': env.company.currency_id.id})
        zone = Zone.search([('code', '=', code)], limit=1)
        zvals = {'name': name, 'code': code, 'sequence': seq,
                 'pricelist_id': pl.id, 'active': True}
        zone.write(zvals) if zone else Zone.create(zvals)
        zone = Zone.search([('code', '=', code)], limit=1)
        zone_by_code[code] = zone

        pl.item_ids.unlink()
        items = [(0, 0, {
            'product_id': val_variant, 'fixed_price': 500, 'applied_on': '0_product_variant',
        })]
        for dim_code, ranges in TIER_VARIANTS.items():
            for m2_range in ranges:
                if m2_range[1] >= 99999:
                    continue
                base = TIER_PRICES_B.get((dim_code, m2_range), 0)
                variant = _variant_b_zone(env, dim_code, m2_range, code, tier_tmpl)
                if variant:
                    items.append((0, 0, {
                        'product_id': variant.id,
                        'fixed_price': _price_zone(base, code),
                        'applied_on': '0_product_variant',
                    }))
        pl.write({'item_ids': items})

    ComboRule.search([]).unlink()
    ComboRule.create({
        'name': 'Combo fumigación interior + exterior + corte',
        'discount_factor': 0.5,
        'required_dimension_ids': [(6, 0, [
            dim_by_code['fumigacion_interior'].id,
            dim_by_code['fumigacion_exterior'].id,
            dim_by_code['corte_poda'].id,
        ])],
        'discount_dimension_ids': [(6, 0, [dim_by_code['corte_poda'].id])],
    })

    resources = Resource.search([('active', '=', True)])
    service_type_ids = [APT_TYPES['interior'], APT_TYPES['corte'], APT_TYPES['valuation']]
    internal_service_types = AptType.browse([APT_TYPES['interior'], APT_TYPES['corte']])
    master = AptType.browse(APT_TYPES['master'])
    wizard = AptType.browse(APT_TYPES['wizard'])
    val_apt = AptType.browse(APT_TYPES['valuation'])
    val_variant = valoracion.product_variant_id
    fumigacion_variant = env['product.product'].sudo().browse(
        TIER_VARIANTS['fumigacion_interior'][(1, 250)]
    )
    if not fumigacion_variant.exists():
        fumigacion_variant = fumigacion.product_variant_id
    apt_common = {
        'appointment_duration': 1.0, 'max_schedule_days': 30,
        'min_schedule_hours': 1.0, 'is_auto_assign': True, 'active': True,
        'has_payment_step': True, 'is_published': False,
    }
    master.write({
        **apt_common,
        'visar_is_master': True,
        'visar_flow': False,
        'resource_ids': [(6, 0, resources.ids)],
        'name': 'Visar — cita multi-servicio',
    })
    _set_appointment_type_labels(
        master,
        es_name='Visar — cita multi-servicio',
        en_name='Visar — multi-service appointment',
    )
    wizard.write({
        **apt_common,
        'visar_flow': 'wizard',
        'visar_is_master': False,
        'is_published': True,
        'resource_ids': [(6, 0, resources.ids)],
        'product_id': fumigacion_variant.id,
    })
    _set_appointment_type_labels(
        wizard,
        es_name='Fumigación interior o exterior',
        en_name='Indoor or outdoor fumigation',
    )
    val_apt.write({
        **apt_common,
        'visar_flow': 'valuation',
        'visar_is_master': False,
        'is_published': True,
        'resource_ids': [(6, 0, resources.ids)],
        'product_id': val_variant.id,
    })
    _set_appointment_type_labels(
        val_apt,
        es_name='Valoración técnica',
        en_name='Technical assessment visit',
    )
    for apt in internal_service_types:
        apt.write({
            **apt_common,
            'visar_flow': False,
            'visar_is_master': False,
            'resource_ids': [(6, 0, resources.ids)],
        })
    for internal_id in (APT_TYPES['mantenimiento_legacy'],):
        internal = AptType.browse(internal_id)
        if internal.exists():
            internal.write({**apt_common, 'visar_flow': False, 'visar_is_master': False})

    zone_ids = [zone_by_code[c].id for c in ('A', 'B', 'C')]
    for res in resources:
        res.write({
            'visar_zone_ids': [(6, 0, zone_ids)],
            'visar_service_ids': [(6, 0, service_type_ids)],
        })

    AptType._visar_unlink_questions_from_entry_types()

    Param.set_param('visar.master_appointment_type_id', str(APT_TYPES['master']))
    Param.set_param('visar.wizard_entry_appointment_type_id', str(APT_TYPES['wizard']))
    Param.set_param('visar.valuation_entry_appointment_type_id', str(APT_TYPES['valuation']))
    Param.set_param('visar.valuation_product_tmpl_id', str(valoracion.id))
    Param.set_param('visar.roedores_product_tmpl_id', str(roedores.id))
    Param.set_param('visar.combo_corte_factor', '0.5')
    Param.set_param('visar.fsm_project_fumigacion_id', str(FSM_PROJECTS['fumigacion']))
    Param.set_param('visar.fsm_project_corte_id', str(FSM_PROJECTS['corte']))
    Param.set_param('visar.fsm_project_valoracion_id', str(FSM_PROJECTS['valoracion']))
    Param.set_param('web.base.url', 'http://localhost:8071')

    from odoo.addons.visar_fsm.hooks import post_init_hook
    post_init_hook(env)
    env.cr.commit()
    return export_catalog_json(env, products)


def export_catalog_json(env, products=None):
    if products is None:
        products = _resolve_catalog_products(env)

    Group = env['visar.service.group'].sudo()
    Dimension = env['visar.service.dimension'].sudo()
    Zone = env['visar.zone'].sudo()
    Tier = env['visar.service.tier'].sudo()
    ComboRule = env['visar.combo.rule'].sudo()
    Param = env['ir.config_parameter'].sudo()
    AptType = env['appointment.type'].sudo()
    OptionalLine = env['visar.product.optional.line'].sudo()

    product_export = {
        k: {'tmpl_id': v.id, 'name': _tname(v)} for k, v in products.items()
    }

    return {
        'meta': {
            'version': '2.1',
            'description': 'Catálogo Visar — productos unificados prod (fumigación 30, mantenimiento 31)',
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'reference_db': env.cr.dbname,
        },
        'ir_config_parameter': {k: Param.get_param(k) for k in [
            'visar.master_appointment_type_id', 'visar.wizard_entry_appointment_type_id',
            'visar.valuation_entry_appointment_type_id', 'visar.valuation_product_tmpl_id',
            'visar.roedores_product_tmpl_id', 'visar.combo_corte_factor',
            'visar.fsm_project_fumigacion_id', 'visar.fsm_project_corte_id',
            'visar.fsm_project_valoracion_id',
        ]},
        'service_dimensions': [{
            'code': d.code, 'group_code': d.group_id.code, 'name': _tname(d),
            'product_tmpl_id': d.product_tmpl_id.id, 'product_name': _tname(d.product_tmpl_id),
        } for d in Dimension.search([])],
        'service_tiers': [{
            'product_tmpl_id': t.product_tmpl_id.id, 'name': _tname(t),
            'm2_min': t.m2_min, 'm2_max': t.m2_max, 'variant_id': t.product_id.id,
            'is_valuation': t.is_valuation, 'is_free': t.is_free,
        } for t in Tier.search([])],
        'zones': [{'code': z.code, 'name': _tname(z)} for z in Zone.search([])],
        'combo_rules': [{
            'name': r.name, 'discount_factor': r.discount_factor,
            'required_dimension_codes': r.required_dimension_ids.mapped('code'),
            'discount_dimension_codes': r.discount_dimension_ids.mapped('code'),
        } for r in ComboRule.search([])],
        'products': product_export,
        'appointment_types': {k: {'id': i, 'name': _tname(AptType.browse(i)), 'active': AptType.browse(i).active,
                                  'visar_flow': AptType.browse(i).visar_flow or False,
                                  'visar_is_master': AptType.browse(i).visar_is_master}
                              for k, i in APT_TYPES.items() if AptType.browse(i).exists()},
        'optional_lines': [{
            'service_tmpl_id': l.product_tmpl_id.id, 'addon_tmpl_id': l.optional_product_id.id,
            'is_mandatory': l.is_mandatory, 'quantity': l.quantity,
        } for l in OptionalLine.search([])],
        'notes': [
            'Producto único fumigación (interior+exterior = dimensiones, no productos split).',
            'Mantenimiento de áreas verdes = corte del combo (producto 31 en main).',
            'Legacy desactivados: Fumigación interior/exterior, Corte de pasto, COMBO split.',
        ],
    }


if 'env' in dir():
    catalog = apply_visar_catalog(env)
    out = '/Users/luisgarza27/Documents/HANOVA/VISAR/repo/.context/visar-catalog-config.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
    print('OK — catalog applied. JSON:', out)
    print('Products:', {k: v['tmpl_id'] for k, v in catalog['products'].items()})
