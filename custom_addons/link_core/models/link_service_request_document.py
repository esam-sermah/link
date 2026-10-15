from odoo import fields, models, _


class LinkServiceRequestDocument(models.Model):
    _name = 'link.service.request.document'
    _description = 'Service Request Document'
    _order = 'id'

    request_id = fields.Many2one(
        'link.service.request',
        string='Service Request',
        required=True,
        ondelete='cascade',
        index=True,
    )
    requirement_id = fields.Many2one(
        'link.service.requirement',
        string='Original Requirement',
        ondelete='set null',
    )
    name = fields.Char(string='Document / Attachment Name', required=True)
    state = fields.Selection(
        selection=[
            ('missing', 'Missing / Required'),
            ('received', 'Received / Pending Review'),
            ('approved', 'Approved & Valid'),
            ('rejected', 'Rejected / Re-upload Needed'),
        ],
        string='Document Status',
        default='missing',
        required=True,
    )
    attachment_id = fields.Many2one(
        'ir.attachment',
        string='Odoo Attachment',
        ondelete='set null',
    )
    file_url = fields.Char(string='Direct File URL')
    rejection_reason = fields.Char(string='Rejection Reason')

    def action_approve(self):
        self.write({'state': 'approved', 'rejection_reason': False})
        self.request_id._check_documents_completion()

    def action_reject(self, reason=None):
        reason = reason or _('Document is not clear or illegible')
        self.write({'state': 'rejected', 'rejection_reason': reason})
        self.request_id._check_documents_completion()
