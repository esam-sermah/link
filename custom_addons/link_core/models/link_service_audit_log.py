from odoo import fields, models


class LinkServiceAuditLog(models.Model):
    _name = 'link.service.audit.log'
    _description = 'Service Audit and Tool Call Log'
    _order = 'id desc'

    request_id = fields.Many2one(
        'link.service.request',
        string='Associated Request',
        ondelete='cascade',
        index=True,
    )
    tenant_id = fields.Many2one(
        'link.tenant',
        string='Tenant',
        required=True,
        ondelete='cascade',
        index=True,
    )
    actor = fields.Selection(
        selection=[
            ('ai', 'AI Assistant (Dify / AI)'),
            ('customer', 'Customer (WhatsApp)'),
            ('merchant', 'Merchant / Agent (Dashboard)'),
            ('system', 'System (Middleware / Odoo)'),
        ],
        string='Actor',
        default='system',
        required=True,
    )
    action = fields.Char(string='Action Performed', required=True)
    payload = fields.Text(string='Payload Details (JSON / Context)')
