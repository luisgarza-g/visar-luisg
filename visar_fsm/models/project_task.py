# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # Orden de venta completa que originó este servicio externo.
    # Related sobre el nativo sale_order_id (que el core computa desde sale_line_id).
    # Reemplaza en la UI al campo nativo `sale_line_id`, que se conserva OCULTO y se
    # sigue asignando en _visar_create_grouped_tasks (no eliminar esa asignación).
    visar_sale_order_id = fields.Many2one(
        'sale.order',
        string="Orden de venta",
        related='sale_order_id',
        store=True,
        readonly=True,
        help="Orden de venta completa de la que proviene este servicio externo "
             "(incluye las dos podas, fumigaciones y add-ons de la misma cita).")
