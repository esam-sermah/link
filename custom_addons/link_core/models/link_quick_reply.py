from odoo import fields, models


class LinkQuickReply(models.Model):
    _name = 'link.quick.reply'
    _description = 'Automated Quick Reply & Keyword Rule'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence & Priority', default=10)
    tenant_id = fields.Many2one(
        'link.tenant',
        string='Tenant',
        required=True,
        ondelete='cascade',
        index=True,
    )
    name = fields.Char(string='Rule / Reply Title', required=True)
    active = fields.Boolean(default=True)
    trigger_keywords = fields.Char(
        string='Trigger Keywords (Comma-separated)',
        required=True,
        help='Example: offers, prices, cost, packages, booking.',
    )
    response_text = fields.Text(
        string='Automated Response Message',
        help='The message sent to the customer upon matching the keywords.',
    )
    action_type = fields.Selection(
        selection=[
            ('text', 'Send Fixed Response Only'),
            ('send_catalog', 'Send Available Offers & Catalog'),
            ('handoff_ai', 'Route Conversation to AI Agent'),
            ('handoff_human', 'Route Conversation to Human Agent'),
        ],
        string='Action Type',
        default='text',
        required=True,
    )
