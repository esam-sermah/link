import base64
import json
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class LinkServiceRequest(models.Model):
    _name = 'link.service.request'
    _description = 'Customer Business Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Request Number',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: self.env._('New Request'),
    )
    tenant_id = fields.Many2one(
        'link.tenant',
        string='Tenant',
        required=True,
        default=lambda self: self.env.user.tenant_id.id,
        ondelete='cascade',
        index=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        tracking=True,
        index=True,
    )
    partner_phone = fields.Char(string='WhatsApp Phone', tracking=True)
    whatsapp_chat_id = fields.Char(string='WhatsApp Chat ID', tracking=True, help='WhatsApp JID or LID for direct messaging')
    service_id = fields.Many2one(
        'link.service.catalog',
        string='Requested Service',
        required=True,
        tracking=True,
    )
    chatwoot_conversation_id = fields.Char(
        string='Chatwoot Conversation ID',
        index=True,
        help='Links real-time chat ticket with this request.',
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('collecting_info', 'Collecting Information'),
            ('collecting_docs', 'Collecting Documents'),
            ('pending_review', 'Ready for Review & Approval'),
            ('confirmed', 'Confirmed & Approved'),
            ('completed', 'Completed'),
            ('rejected', 'Rejected'),
            ('cancelled', 'Cancelled'),
        ],
        string='Request Status',
        default='draft',
        required=True,
        tracking=True,
    )

    currency_id = fields.Many2one(
        related='tenant_id.currency_id',
        string='Currency',
        readonly=True,
    )
    total_price = fields.Monetary(
        string='Official Total Amount',
        currency_field='currency_id',
        tracking=True,
    )

    collected_data = fields.Text(
        string='Collected Data (JSON)',
        default='{}',
        help='Values extracted from WhatsApp Flow and conversational AI agent.',
    )

    document_ids = fields.One2many(
        'link.service.request.document',
        'request_id',
        string='Documents & Attachments',
    )
    audit_log_ids = fields.One2many(
        'link.service.audit.log',
        'request_id',
        string='Audit & Action Logs',
    )

    reviewed_by = fields.Many2one('res.users', string='Reviewed By')
    confirmed_at = fields.Datetime(string='Confirmation Date')
    rejection_reason = fields.Text(string='Rejection Reason')

    missing_requirements_summary = fields.Char(
        string='Pending Requirements',
        compute='_compute_missing_summary',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', self.env._('New Request')) == self.env._('New Request'):
                vals['name'] = self.env['ir.sequence'].next_by_code('link.service.request') or 'REQ/NEW'
        records = super().create(vals_list)
        for record in records:
            record._setup_required_documents()
        return records

    def _setup_required_documents(self):
        """Prepare mandatory document slots based on service requirements."""
        self.ensure_one()
        for req in self.service_id.requirement_ids:
            self.env['link.service.request.document'].create({
                'request_id': self.id,
                'requirement_id': req.id,
                'name': req.name,
                'state': 'missing',
            })

    @api.depends('document_ids.state', 'state')
    def _compute_missing_summary(self):
        for record in self:
            missing_docs = record.document_ids.filtered(lambda d: d.state in ('missing', 'rejected'))
            if missing_docs:
                record.missing_requirements_summary = ", ".join(missing_docs.mapped('name'))
            else:
                record.missing_requirements_summary = _('All requirements completed')

    def _log_action(self, actor, action, payload=""):
        """Record audit event in the unified audit log."""
        self.ensure_one()
        self.env['link.service.audit.log'].create({
            'request_id': self.id,
            'tenant_id': self.tenant_id.id,
            'actor': actor,
            'action': action,
            'payload': str(payload),
        })

    # ==========================================
    # Atomic Business Methods
    # ==========================================

    @api.model
    def create_request_draft(self, tenant_id, partner_phone, customer_name, service_id, chatwoot_conv_id=None, initial_data=None, whatsapp_chat_id=None):
        """Create draft request from AI / WhatsApp and match or create partner."""
        Tenant = self.env['link.tenant'].browse(tenant_id)
        if not Tenant.exists():
            raise UserError(_('Tenant does not exist.'))

        Service = self.env['link.service.catalog'].browse(service_id)
        if not Service.exists():
            raise UserError(_('Requested service is not available.'))

        # Match or create customer partner
        clean_p = partner_phone.replace('+', '').strip() if partner_phone else ''
        partner_domain = ['|', ('phone', '=', partner_phone), ('phone', 'like', clean_p[-8:] if len(clean_p) >= 8 else clean_p)]
        Partner = self.env['res.partner'].sudo().search(partner_domain, limit=1)

        is_real_name = bool(
            customer_name 
            and customer_name.strip() 
            and customer_name not in ('عميل واتساب', 'WhatsApp Customer', 'Customer', 'None', '', 'e') 
            and not customer_name.startswith('عميل واتساب')
            and len(customer_name.strip()) >= 3
        )

        fallback_name = customer_name.strip() if is_real_name else (f"عميل واتساب ({partner_phone})" if partner_phone else "عميل واتساب")
        if not Partner:
            Partner = self.env['res.partner'].sudo().create({
                'name': fallback_name,
                'phone': partner_phone,
            })
        elif is_real_name:
            Partner.sudo().write({'name': customer_name.strip()})

        # Calculate initial deterministic price
        price_info = Service.calculate_price(initial_data or {})

        # Create request record
        req = self.create({
            'tenant_id': Tenant.id,
            'partner_id': Partner.id,
            'partner_phone': partner_phone,
            'whatsapp_chat_id': whatsapp_chat_id or (f"{partner_phone}@c.us" if partner_phone else False),
            'service_id': Service.id,
            'chatwoot_conversation_id': chatwoot_conv_id,
            'state': 'collecting_info',
            'total_price': price_info.get('total_price', 0.0),
            'collected_data': json.dumps(initial_data or {}, ensure_ascii=False),
        })

        req._log_action(
            actor='ai',
            action='create_request_draft',
            payload=json.dumps({
                'initial_data': initial_data,
                'price_info': price_info,
            }, ensure_ascii=False),
        )

        return {
            'request_id': req.id,
            'request_number': req.name,
            'state': req.state,
            'total_price': req.total_price,
            'missing_data': req.get_missing_requirements(),
        }

    def update_customer_name(self, customer_name):
        """Update customer partner name, request, and audit log."""
        self.ensure_one()
        is_real_name = bool(
            customer_name 
            and customer_name.strip() 
            and customer_name not in ('عميل واتساب', 'WhatsApp Customer', 'Customer', 'None', '', 'e') 
            and not customer_name.startswith('عميل واتساب')
            and len(customer_name.strip()) >= 3
        )
        if is_real_name:
            clean_name = customer_name.strip()
            self.partner_id.sudo().write({'name': clean_name})
            self._log_action(actor='ai', action='update_customer_name', payload=f"Customer name updated: {clean_name}")
            return True
        return False

    def update_collected_data(self, new_data):
        """Update fields and collected data and check transition to next state."""
        self.ensure_one()
        current_data = {}
        if self.collected_data:
            try:
                current_data = json.loads(self.collected_data)
            except Exception:
                current_data = {}

        current_data.update(new_data)
        self.collected_data = json.dumps(current_data, ensure_ascii=False)

        # Recalculate price with new parameters
        price_info = self.service_id.calculate_price(current_data)
        self.total_price = price_info.get('total_price', self.total_price)

        self._log_action(actor='ai', action='update_collected_data', payload=json.dumps(new_data, ensure_ascii=False))

        # Check required attributes completion
        missing_attrs = []
        for attr in self.service_id.attribute_ids.filtered(lambda a: a.is_required):
            if attr.field_key not in current_data or not current_data[attr.field_key]:
                missing_attrs.append(attr)

        if not missing_attrs:
            if self.document_ids:
                if any(doc.state in ('missing', 'rejected') for doc in self.document_ids):
                    self.state = 'collecting_docs'
                else:
                    self.state = 'pending_review'
            else:
                self.state = 'pending_review'

        return self.get_missing_requirements()

    def attach_document(self, requirement_code_or_name, file_base64, filename, mime_type='image/jpeg'):
        """Receive attachment and tie it to the corresponding document requirement."""
        self.ensure_one()
        doc = self.document_ids.filtered(
            lambda d: (d.requirement_id.requirement_code == requirement_code_or_name or d.name == requirement_code_or_name)
        )
        if not doc:
            doc = self.document_ids.filtered(lambda d: d.state in ('missing', 'rejected'))[:1]

        if not doc:
            doc = self.env['link.service.request.document'].create({
                'request_id': self.id,
                'name': filename or _('Additional Attachment'),
                'state': 'received',
            })

        raw_bytes = base64.b64decode(file_base64) if isinstance(file_base64, str) else file_base64
        attachment = self.env['ir.attachment'].sudo().create({
            'name': filename or f"{doc.name}_{self.name}",
            'type': 'binary',
            'raw': raw_bytes,
            'res_model': 'link.service.request',
            'res_id': self.id,
            'mimetype': mime_type,
        })

        doc.write({
            'attachment_id': attachment.id,
            'state': 'received',
            'rejection_reason': False,
        })

        self._log_action(
            actor='customer',
            action='attach_document',
            payload=f"Uploaded: {doc.name} (Attachment ID: {attachment.id})",
        )

        self._check_documents_completion()
        return {
            'document_id': doc.id,
            'document_name': doc.name,
            'status': doc.state,
            'all_complete': self.state == 'pending_review',
        }

    def _check_documents_completion(self):
        """Check if all documents are uploaded to move request to pending review."""
        self.ensure_one()
        missing = self.document_ids.filtered(lambda d: d.state in ('missing', 'rejected'))
        if not missing and self.state in ('collecting_info', 'collecting_docs'):
            self.state = 'pending_review'
            self._log_action(actor='system', action='moved_to_pending_review', payload='All documents received')

    def get_missing_requirements(self):
        """Return pending requirements list to guide conversational agent."""
        self.ensure_one()
        current_data = {}
        if self.collected_data:
            try:
                current_data = json.loads(self.collected_data)
            except Exception:
                pass

        missing_fields = []
        for attr in self.service_id.attribute_ids.filtered(lambda a: a.is_required):
            if attr.field_key not in current_data or not current_data[attr.field_key]:
                missing_fields.append({
                    'key': attr.field_key,
                    'name': attr.name,
                    'type': attr.field_type,
                    'options': attr.selection_options,
                    'prompt': attr.help_text or (_('Please specify %s') % attr.name),
                })

        missing_docs = []
        for doc in self.document_ids.filtered(lambda d: d.state in ('missing', 'rejected')):
            missing_docs.append({
                'code': doc.requirement_id.requirement_code if doc.requirement_id else str(doc.id),
                'name': doc.name,
                'prompt': doc.requirement_id.instruction_prompt if doc.requirement_id else (_('Please send a copy of %s') % doc.name),
                'state': doc.state,
                'rejection_reason': doc.rejection_reason,
            })

        return {
            'request_id': self.id,
            'request_number': self.name,
            'state': self.state,
            'total_price': self.total_price,
            'currency': self.currency_id.name or 'SAR',
            'is_ready_for_review': (not missing_fields and not missing_docs),
            'missing_fields': missing_fields,
            'missing_documents': missing_docs,
        }

    def action_approve(self):
        """Approve request by merchant and trigger confirmation."""
        self.ensure_one()
        if self.state == 'confirmed':
            return True

        avail = self.service_id.check_availability()
        if not avail.get('available'):
            raise UserError(self.env._("Cannot approve request: %s", avail.get('reason')))

        self.write({
            'state': 'confirmed',
            'reviewed_by': self.env.user.id,
            'confirmed_at': fields.Datetime.now(),
        })

        self._log_action(
            actor='merchant',
            action='action_approve',
            payload=f"Approved by user {self.env.user.name}",
        )

        # إرسال إشعار فوري للعميل على واتساب يفيد باعتماد وتأكيد طلبه
        self._send_whatsapp_approval_notification()

        return True

    def _send_whatsapp_approval_notification(self):
        """إرسال إشعار اعتماد الطلب للعميل عبر بوابة الواتساب OpenWA"""
        self.ensure_one()
        tenant = self.tenant_id
        target = self.whatsapp_chat_id or (f"{self.partner_phone}@c.us" if self.partner_phone else None)
        if not target or not tenant.openwa_session_id:
            return False

        currency_str = self.currency_id.name or 'SAR'
        customer_name = self.partner_id.name if self.partner_id and not self.partner_id.name.startswith('عميل واتساب') and self.partner_id.name not in ('e', 'None') else ''
        salutation = f"أستاذ {customer_name}" if customer_name else "عزيزنا العميل"

        msg = (
            f"🎉 *تهانينا {salutation}! تم اعتماد وتأكيد طلب حجزك رسمياً* ✅\n\n"
            f"📋 *تفاصيل الحجز المؤكد:*\n"
            f"• رقم الحجز: *{self.name}*\n"
            f"• الخدمة: *{self.service_id.name}*\n"
            f"• المبلغ الإجمالي: *{self.total_price:,.0f} {currency_str}*\n\n"
            f"يسعدنا إبلاغك بأن جميع المستندات تم تدقيقها والموافقة عليها بنجاح. "
            f"فريقنا بدأ الترتيبات الرسمية لرحلتك، ونتمنى لك تجربة ممتعة ورحلة سعيدة! 🌸\n\n"
            f"💡 *يسعدنا دائماً خدمتك! وإذا رغبت في أي وقت بحجز رحلة جديدة أو استكشاف عروضنا، فقط اكتب لنا وسنرسل لك العروض ونبدأ معك الترتيبات فوراً.*"
        )

        try:
            import urllib.request
            import urllib.error
            import json
            import time
            base_url = (tenant.openwa_api_url or 'http://localhost:2785').rstrip('/')
            if ':3000' in base_url:
                base_url = base_url.replace(':3000', ':2785')
            url = f"{base_url}/api/sessions/{tenant.openwa_session_id}/messages/send-text"
            payload = json.dumps({
                "chatId": target,
                "text": msg
            }).encode('utf-8')
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": tenant.openwa_api_key or "owa_k1_3bd33a7be0780dca218cadb8941b2506df6f0c43ef69e50d1932e28c5c3f760a",
            }

            def _post(u, p):
                r = urllib.request.Request(u, data=p, headers=headers, method='POST')
                return urllib.request.urlopen(r, timeout=10)

            try:
                response = _post(url, payload)
            except urllib.error.HTTPError as err:
                if err.code in (400, 404, 502):
                    start_url = f"{base_url}/api/sessions/{tenant.openwa_session_id}/start"
                    try:
                        _post(start_url, b"{}")
                    except Exception:
                        pass
                    time.sleep(2.5)
                    response = _post(url, payload)
                else:
                    raise err

            status_code = response.getcode()
            self._log_action(
                actor='system',
                action='whatsapp_approval_sent',
                payload=f"Approval notification sent to {target} (Status: {status_code})"
            )
            return True
        except Exception as e:
            self._log_action(
                actor='system',
                action='whatsapp_approval_failed',
                payload=f"Failed to send WhatsApp approval to {target}: {str(e)}"
            )
            return False

    def action_reject(self, reason=''):
        """Reject request with reason."""
        self.ensure_one()
        self.write({
            'state': 'rejected',
            'rejection_reason': reason,
        })
        self._log_action(actor='merchant', action='action_reject', payload=reason)
        return True

    def action_complete(self):
        """Mark request as completed."""
        self.ensure_one()
        self.write({'state': 'completed'})
        self._log_action(actor='system', action='action_complete')
