from odoo import fields, models


class LinkServiceAttribute(models.Model):
    _name = 'link.service.attribute'
    _description = 'Service Dynamic Attribute'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)
    catalog_id = fields.Many2one(
        'link.service.catalog',
        string='Service',
        required=True,
        ondelete='cascade',
        index=True,
    )
    name = fields.Char(string='Attribute Name', required=True)
    field_key = fields.Char(
        string='Field Key',
        required=True,
        help='Technical identifier used by tool calls and WhatsApp flow, e.g. passengers_count.',
    )
    field_type = fields.Selection(
        selection=[
            ('char', 'Single Line Text'),
            ('integer', 'Integer Number'),
            ('float', 'Decimal / Amount'),
            ('date', 'Date'),
            ('selection', 'Selection Options'),
            ('boolean', 'Yes / No (Boolean)'),
        ],
        string='Field Type',
        default='char',
        required=True,
    )
    selection_options = fields.Text(
        string='Selection Options',
        help='Comma-separated values if selection type is chosen, e.g. Economy, VIP, Family.',
    )
    is_required = fields.Boolean(string='Required for Approval', default=True)
    help_text = fields.Char(
        string='Customer / AI Prompt',
        help='Example: Ask the customer for the number of accompanying adults and children.',
    )
