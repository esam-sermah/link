from odoo import fields, models


class LinkServicePriceRule(models.Model):
    _name = 'link.service.price.rule'
    _description = 'Service Price Rule'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)
    catalog_id = fields.Many2one(
        'link.service.catalog',
        string='Service',
        required=True,
        ondelete='cascade',
        index=True,
    )
    name = fields.Char(string='Pricing Rule Name', required=True)
    rule_type = fields.Selection(
        selection=[
            ('extra_person', 'Charge per Additional Person'),
            ('per_day', 'Daily / Duration Rate'),
            ('addon_fixed', 'Fixed Add-on / Package'),
            ('discount_percentage', 'Percentage Discount'),
        ],
        string='Price Rule Type',
        default='extra_person',
        required=True,
    )
    amount = fields.Float(string='Value / Amount / Rate', required=True)
    description = fields.Char(string='Price Breakdown Description')
    active = fields.Boolean(default=True)
