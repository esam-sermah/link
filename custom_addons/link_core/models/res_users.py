from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    tenant_id = fields.Many2one(
        'link.tenant',
        string='Assigned Business (Tenant)',
        help='Specifies the SaaS tenant for data isolation.',
    )
