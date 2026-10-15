from odoo import fields, models


class LinkServiceRequirement(models.Model):
    _name = 'link.service.requirement'
    _description = 'Service Mandatory Requirement and Document'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)
    catalog_id = fields.Many2one(
        'link.service.catalog',
        string='Service',
        required=True,
        ondelete='cascade',
        index=True,
    )
    name = fields.Char(string='Requirement / Document Name', required=True)
    requirement_code = fields.Char(string='Requirement Code', required=True)
    requirement_type = fields.Selection(
        selection=[
            ('document_image', 'Document Image (ID / Passport / Receipt)'),
            ('document_pdf', 'Official PDF Document'),
            ('text_field', 'Additional Information'),
            ('consent_checkbox', 'Terms & Conditions Consent'),
        ],
        string='Requirement Type',
        default='document_image',
        required=True,
    )
    is_mandatory = fields.Boolean(
        string='Mandatory Before Approval?',
        default=True,
        help='The request will not move to Ready for Review until this requirement is received.',
    )
    instruction_prompt = fields.Text(
        string='Customer WhatsApp Prompt',
        help='Example: Please photograph the passport clearly ensuring full validity dates and personal details are visible.',
    )
