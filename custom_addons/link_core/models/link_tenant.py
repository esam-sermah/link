import uuid
from odoo import api, fields, models, _


class LinkTenant(models.Model):
    _name = 'link.tenant'
    _description = 'LINK SaaS Tenant'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Business Name', required=True, tracking=True)
    code = fields.Char(string='Unique Identifier (Slug)', required=True, copy=False, index=True)
    active = fields.Boolean(default=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('suspended', 'Suspended'),
        ],
        string='Account Status',
        default='active',
        tracking=True,
    )
    phone = fields.Char(string='Official WhatsApp Phone', tracking=True)
    business_category = fields.Selection(
        selection=[
            ('travel', 'Travel & Tourism'),
            ('clinic', 'Clinics & Aesthetics'),
            ('rental', 'Car & Real Estate Rental'),
            ('consulting', 'Consulting & Professional Services'),
            ('maintenance', 'Maintenance & Spare Parts'),
            ('other', 'Other Businesses'),
        ],
        string='Business Category',
        default='travel',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Official Currency',
        default=lambda self: self.env.company.currency_id,
        required=True,
    )

    # Response Mode & Chat Flow
    bot_mode = fields.Selection(
        selection=[
            ('hybrid', 'Hybrid Mode (Interactive Welcome + Buttons + Smart AI)'),
            ('ai_only', 'AI Agent Only'),
            ('rules_only', 'Automated Rules & Menus Only'),
        ],
        string='Bot Response Mode',
        default='hybrid',
        required=True,
        help='Define whether messages are handled by AI only, automated rules, or a hybrid of both.',
    )
    welcome_message = fields.Text(
        string='Initial Welcome Message',
        default='Welcome! We are delighted to connect with you.\nHow can we help you today? Please choose an option below or type your inquiry directly:',
    )
    welcome_button_1 = fields.Char(string='Button 1 (Offers & Catalog)', default='Browse Offers & Services')
    welcome_button_2 = fields.Char(string='Button 2 (AI Inquiry & Booking)', default='Inquiry & Smart Booking')
    welcome_button_3 = fields.Char(string='Button 3 (Customer Support)', default='Speak with an Agent')

    # WhatsApp Gateway Integration (OpenWA)
    openwa_session_id = fields.Char(string='OpenWA Session ID', default='default')
    openwa_api_url = fields.Char(string='OpenWA Gateway URL', default='http://localhost:3000')
    openwa_api_key = fields.Char(string='OpenWA API Key')

    # AI Knowledge Base & LLM Configuration
    ai_provider = fields.Selection(
        selection=[
            ('built_in', 'Advanced Built-in Smart Engine (No Cost)'),
            ('openai', 'OpenAI (GPT-4o / GPT-4o-mini)'),
            ('gemini', 'Google Gemini Pro / Flash'),
            ('groq', 'Groq (Ultra-fast LLaMA-3)'),
            ('openrouter', 'OpenRouter'),
            ('dify', 'Dify AI Platform'),
        ],
        string='AI Provider',
        default='built_in',
        required=True,
    )
    ai_model = fields.Char(string='AI Model', default='gpt-4o-mini')
    ai_api_key = fields.Char(string='AI API Key')
    ai_system_prompt = fields.Text(
        string='Agent Persona & Style (System Prompt)',
        default=(
            "You are a professional, warm, and courteous customer service agent representing this business.\n"
            "Communicate naturally and warmly as a knowledgeable human agent over WhatsApp.\n"
            "Never use robotic phrases, robot emojis, or mechanical repetitions.\n"
            "Keep replies concise, helpful, and focused on assisting the customer with their booking."
        ),
    )
    ai_knowledge_base = fields.Text(
        string='Business Knowledge Base & FAQs',
        default=(
            "Business Information and Services:\n"
            "- Business: Luxury Travel & Tourism, specializing in customized family and private travel.\n"
            "- Bosnia Package (7 Days): Includes 4 and 5-star hotels with breakfast, private car and driver throughout, daily tours in Sarajevo, Mostar, and Prokosko Lake. Price $5,000.\n"
            "- Booking Requirements: Passport copy for all travelers to issue flight tickets and hotel vouchers.\n"
            "- Payment: 30% deposit upon booking confirmation, balance one week before departure.\n"
            "- Cancellation: 100% full refund up to 15 days before departure.\n"
            "- Working Hours: Daily from 9:00 AM to 11:00 PM."
        ),
    )

    # Chatwoot & Dify Technical Integrations
    chatwoot_account_id = fields.Char(string='Chatwoot Account ID')
    chatwoot_inbox_id = fields.Char(string='Chatwoot Inbox ID')
    dify_api_key = fields.Char(string='Dify API Key', groups='base.group_system')
    dify_app_id = fields.Char(string='Dify App ID')
    dify_dataset_id = fields.Char(string='Dify Dataset ID')
    webhook_secret = fields.Char(
        string='Webhook Secret',
        default=lambda self: uuid.uuid4().hex,
        copy=False,
    )

    # Relational Fields
    quick_reply_ids = fields.One2many('link.quick.reply', 'tenant_id', string='Quick Replies & Rules')
    catalog_ids = fields.One2many('link.service.catalog', 'tenant_id', string='Service Catalog')
    request_ids = fields.One2many('link.service.request', 'tenant_id', string='Requests')
    user_ids = fields.One2many('res.users', 'tenant_id', string='Authorized Staff')
    service_count = fields.Integer(string='Services Count', compute='_compute_counts')
    request_count = fields.Integer(string='Total Requests', compute='_compute_counts')

    _check_code_unique = models.Constraint(
        'UNIQUE(code)',
        'The tenant identifier (Slug) must be unique!',
    )

    @api.depends('catalog_ids', 'request_ids')
    def _compute_counts(self):
        for record in self:
            record.service_count = len(record.catalog_ids)
            record.request_count = len(record.request_ids)

    def action_activate(self):
        self.write({'state': 'active'})

    def action_suspend(self):
        self.write({'state': 'suspended'})
