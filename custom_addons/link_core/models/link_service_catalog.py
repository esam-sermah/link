from datetime import date
from odoo import api, fields, models, _


class LinkServiceCatalog(models.Model):
    _name = 'link.service.catalog'
    _description = 'Service Catalog Entry'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    tenant_id = fields.Many2one(
        'link.tenant',
        string='Tenant',
        required=True,
        default=lambda self: self.env.user.tenant_id.id,
        ondelete='cascade',
        index=True,
    )
    name = fields.Char(string='Service / Offer Name', required=True, tracking=True)
    code = fields.Char(string='Service Code (Slug / SKU)', required=True, copy=False)
    active = fields.Boolean(default=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Published & Active'),
            ('archived', 'Archived'),
        ],
        string='Service Status',
        default='active',
        tracking=True,
    )
    category = fields.Char(string='Internal Category')
    description = fields.Text(
        string='Detailed Description & Policies',
        help='Used to feed the AI Knowledge Base (RAG) to answer general customer inquiries.',
    )

    # Official Pricing
    currency_id = fields.Many2one(
        related='tenant_id.currency_id',
        string='Currency',
        readonly=True,
    )
    pricing_type = fields.Selection(
        selection=[
            ('fixed', 'Fixed Price'),
            ('per_person', 'Per Person Price'),
            ('per_day', 'Per Day / Duration Price'),
            ('custom', 'Custom Rule Formula'),
        ],
        string='Pricing Type',
        default='fixed',
        required=True,
    )
    base_price = fields.Monetary(string='Approved Base Price', currency_field='currency_id', default=0.0)

    # Requirements, Attributes, and Availability
    attribute_ids = fields.One2many(
        'link.service.attribute',
        'catalog_id',
        string='Required Attributes & Fields',
    )
    requirement_ids = fields.One2many(
        'link.service.requirement',
        'catalog_id',
        string='Mandatory Documents & Requirements',
    )
    availability_rule_ids = fields.One2many(
        'link.service.availability.rule',
        'catalog_id',
        string='Availability & Schedule Rules',
    )
    price_rule_ids = fields.One2many(
        'link.service.price.rule',
        'catalog_id',
        string='Price Rules & Addons',
    )

    request_ids = fields.One2many('link.service.request', 'service_id', string='Customer Requests')
    request_count = fields.Integer(string='Bookings Count', compute='_compute_request_count')

    _check_tenant_code_uniq = models.Constraint(
        'UNIQUE(tenant_id, code)',
        'Service code must be unique per tenant!',
    )

    def _compute_request_count(self):
        for record in self:
            record.request_count = len(record.request_ids)

    def check_availability(self, date_from_str=None, date_to_str=None, quantity=1):
        """Atomic deterministic availability check preventing LLM hallucination."""
        self.ensure_one()
        if not self.active or self.state != 'active':
            return {
                'available': False,
                'reason': _('Service is currently inactive in the system.'),
            }

        # Check Blackout Dates
        if date_from_str:
            try:
                target_date = date.fromisoformat(date_from_str)
                for rule in self.availability_rule_ids.filtered(lambda r: r.active and r.rule_type == 'blackout_dates'):
                    if rule.date_from and rule.date_to and rule.date_from <= target_date <= rule.date_to:
                        return {
                            'available': False,
                            'reason': rule.note or _('Selected date is currently not available for booking.'),
                        }
            except (ValueError, TypeError):
                pass

        return {
            'available': True,
            'reason': _('Service is available and ready for booking.'),
        }

    def calculate_price(self, options=None):
        """Deterministic pricing calculation without any LLM guess."""
        self.ensure_one()
        options = options or {}
        unit_price = self.base_price
        total_price = unit_price
        breakdown = [{'label': _('Base Price'), 'amount': unit_price}]

        quantity = float(options.get('quantity') or options.get('passengers_count') or 1)
        days = float(options.get('days') or options.get('duration_days') or 1)

        if self.pricing_type == 'per_person':
            total_price = unit_price * quantity
            breakdown = [{'label': _('Price for %s Persons') % int(quantity), 'amount': total_price}]
        elif self.pricing_type == 'per_day':
            total_price = unit_price * days
            breakdown = [{'label': _('Price for %s Days') % int(days), 'amount': total_price}]

        # Apply Price Rules
        for rule in self.price_rule_ids.filtered(lambda r: r.active):
            if rule.rule_type == 'extra_person' and quantity > 1:
                extra_people = quantity - 1
                addon_amount = rule.amount * extra_people
                total_price += addon_amount
                breakdown.append({'label': _('Extra Persons (%s)') % int(extra_people), 'amount': addon_amount})
            elif rule.rule_type == 'addon_fixed' and options.get(rule.name):
                total_price += rule.amount
                breakdown.append({'label': rule.name, 'amount': rule.amount})

        return {
            'currency': self.currency_id.name or 'SAR',
            'unit_price': unit_price,
            'total_price': total_price,
            'breakdown': breakdown,
        }
