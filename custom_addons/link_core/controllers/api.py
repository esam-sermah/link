import re
from odoo import http
from odoo.http import request


NAME_REJECT_TOKENS = {
    'او', 'أو', 'وش', 'ايش', 'كيف', 'طريقه', 'طريقة', 'شروط', 'لخبطه', 'لخبطة', 'غلط', 'خطأ',
    'سياره', 'سيارة', 'سيارات', 'فندق', 'فنادق', 'حجز', 'احجز', 'سعر', 'اسعار', 'أسعار',
    'كم', 'بكم', 'تكلفة', 'وين', 'متى', 'هل', 'ليش', 'ليه', 'عرض', 'عروض', 'باقة', 'باقات',
    'رقم', 'طلب', 'ماذا', 'ابي', 'ابغى', 'اريد', 'ودي', 'تمام', 'شكرا', 'شكراً', 'هلا',
    'مرحبا', 'سلام', 'السلام', 'عليكم', 'طيران', 'تذاكر', 'سياحة', 'رحلة', 'رحلات', 'بوسنة',
    'البوسنة', 'صين', 'الصين', 'توصيل', 'سائق', 'يوم', 'ايام', 'أيام', 'شهر', 'معلومات',
    'هههه', 'ههههه', 'هههههه', 'ههههههه', 'الو', 'ألو', 'اوك', 'اوكي', 'طيب', 'لا', 'نعم',
    'ايوه', 'اي', 'سمعت', 'اليوم', 'امس', 'بكره', 'جلس', 'يزيد', 'بكلم', 'تراك', 'اشغلتني',
    'المطورين', 'اقروب', 'جروب', 'هنا', 'في', 'من', 'على', 'عن', 'مع', 'مقاس', 'عنوان',
    'عباية', 'طقم', 'ملابس', 'فستان', 'سند', 'رسوم', 'تحويل', 'إيصال', 'ايصال', 'كلام',
    'يرسل', 'ارسل', 'رساله', 'رسالة', 'رسايل', 'رسائل', 'خطا', 'خطأ', 'اشتي', 'اعرب', 'اشوف',
    'شوف', 'اسمع', 'ياخي', 'اخي', 'يا', 'انت', 'انا', 'هو', 'هي', 'كذا', 'كذاا', 'حق', 'حقي',
    'مالك', 'عندي', 'عندك', 'مخبوط', 'مخربط', 'جالس', 'قاعد', 'عميل', 'عميلنا', 'عزيزنا',
    'مسؤول', 'مسئول', 'حجوزات', 'مبيعات', 'تدريب', 'كلامات', 'بيانات', 'متجر', 'مستاجر',
    'مستأجر', 'منتج', 'منتجات', 'صورة', 'مقاسات', 'موظف', 'رفع', 'صحيح', 'صحيحة', 'حياك',
    'الله', 'استاذ', 'أستاذ', 'ياخوي', 'والله', 'ضحكتني', 'بروح', 'برجع', 'احبطك', 'احبط',
    'ينسى', 'ذا', 'افعله', 'افعل', 'معلي', 'معليه', 'اصلن', 'وارجع', 'ارجع', 'سالفة', 'سالفه'
}


def _clean_customer_name(text):
    """استخراج اسم العميل بشكل صارم ومحدد فقط إذا كان تعبيراً صريحاً ببادئة عن الاسم الشخصي"""
    if not text:
        return None
    t = text.strip()
    prefixes = [
        r'^(?:اسمي\s+هو|اسمي:|اسمي)\s+([^\n\.,!؟?]+)$',
        r'^(?:أنا\s+اسمي|انا\s+اسمي)\s+([^\n\.,!؟?]+)$',
        r'^(?:معك\s+الأخ|معك\s+الاخ|معاك\s+الأخ|معاك\s+الاخ)\s+([^\n\.,!؟?]+)$',
        r'(?:سجل\s+الحجز\s+باسم|سجل\s+الطلب\s+باسم|الحجز\s+باسم|الطلب\s+باسم)\s+([^\n\.,!؟?]+)',
    ]
    candidate = None
    for p in prefixes:
        m = re.search(p, t, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            break

    if not candidate:
        return None

    # تجريد أي بادئات زائدة من المرشح لضمان اسم شخصي نقي
    candidate = re.sub(r'^(?:أنا\s+اسمي|انا\s+اسمي|اسمي\s+هو|اسمي:|اسمي|معك|معاك)\s+', '', candidate, flags=re.IGNORECASE).strip()
    candidate = re.split(r'\s+(?:وابغى|واريد|وابي|وارغب|وحاب|ودي|احجز|لكي|عشان|من أجل|لتسجيل)\b', candidate)[0].strip()
    words = candidate.split()
    if not (2 <= len(words) <= 4):
        return None

    for w in words:
        w_clean = re.sub(r'[^\w]', '', w.lower())
        if len(w_clean) < 2 or w_clean in NAME_REJECT_TOKENS or any(d.isdigit() for d in w):
            return None

    return " ".join(words)


def _match_service(text, services):
    """مطابقة الخدمة أو المنتج المناسب بدقة استناداً لكلمات العميل عبر كافة الأنشطة"""
    if not text or not services:
        return None
    t = text.lower()

    # 1. مطابقة مباشرة بالاسم أو الكود
    for s in services:
        s_name = (s.name or '').lower()
        s_code = (s.code or '').lower()
        if s_name in t or s_code in t:
            return s

    # 2. ملابس وأزياء وعبايات
    if any(k in t for k in ['عباي', 'عباية', 'عبايه', 'فستان', 'ملابس', 'طقم', 'قميص', 'أزياء', 'ازياء', 'ثوب', 'موضة', 'مقاس']):
        fashion = services.filtered(lambda s: any(x in (s.name or '').lower() or x in (s.category or '').lower() for x in ['عباي', 'ملابس', 'طقم', 'فستان', 'أزياء']))
        if fashion:
            return fashion[0]

    # 3. سيارات واستئجار ونقل
    if any(k in t for k in ['سيار', 'سيارة', 'سياره', 'سيارات', 'سائق', 'سواق', 'تأجير', 'استئجار', 'توصيل', 'توصيلات']):
        car = services.filtered(lambda s: any(x in (s.name or '').lower() or x in (s.code or '').lower() for x in ['سيار', 'car', 'سائق']))
        if car:
            return car[0]

    # 4. فنادق وإقامة ومنتجعات
    if any(k in t for k in ['فندق', 'فنادق', 'منتجع', 'منتجعات', 'سكن', 'شقة', 'شقق', 'غرفة', 'غرف', 'ريزورت']):
        hotel = services.filtered(lambda s: any(x in (s.name or '').lower() or x in (s.code or '').lower() for x in ['فندق', 'hotel', 'منتجع', 'resort']))
        if hotel:
            return hotel[0]

    # 5. رحلات وبكجات سياحية محددة
    if any(k in t for k in ['بوسنة', 'البوسنة', 'سراييفو']):
        bosnia = services.filtered(lambda s: any(x in (s.name or '').lower() or x in (s.code or '').lower() for x in ['بوسنة', 'bosnia']))
        if bosnia:
            return bosnia[0]

    if any(k in t for k in ['صين', 'الصين', 'شنغهاي', 'كوانزو', 'بكين']):
        china = services.filtered(lambda s: any(x in (s.name or '').lower() or x in (s.code or '').lower() for x in ['صين', 'china']))
        if china:
            return china[0]

    # 6. مطابقة بالكلمات المميزة في اسم الخدمة
    for s in services:
        s_words = [w for w in (s.name or '').lower().split() if len(w) >= 3 and w not in ('باقة', 'خدمة', 'حجز', 'طلب', 'عرض', 'خاص', 'أيام', 'يوم')]
        if any(w in t for w in s_words):
            return s

    return None


class LinkApiController(http.Controller):

    def _authenticate_tenant(self, tenant_id=None, tenant_slug=None, secret=None):
        """التحقق الأمني من هوية المستأجر وصلاحية الطبقة الوسيطة"""
        domain = []
        if tenant_id:
            domain.append(('id', '=', int(tenant_id)))
        elif tenant_slug:
            domain.append(('code', '=', tenant_slug))
        else:
            return None, {'error': 'Tenant ID or Slug is required.'}

        tenant = request.env['link.tenant'].sudo().search(domain, limit=1)
        if not tenant:
            return None, {'error': 'Tenant not found.'}

        if secret and tenant.webhook_secret and tenant.webhook_secret != secret:
            return None, {'error': 'Invalid webhook secret authorization.'}

        return tenant, None

    @http.route('/api/link/v1/availability', type='jsonrpc', auth='none', methods=['POST'], csrf=False)
    def api_check_availability(self, **kwargs):
        """فحص التوفر الفعلي لخدمة"""
        tenant_id = kwargs.get('tenant_id')
        service_id = kwargs.get('service_id')
        service_code = kwargs.get('service_code')
        secret = kwargs.get('secret')
        date_from = kwargs.get('date_from')
        date_to = kwargs.get('date_to')
        quantity = kwargs.get('quantity', 1)

        tenant, err = self._authenticate_tenant(tenant_id=tenant_id, secret=secret)
        if err:
            return err

        service_domain = [('tenant_id', '=', tenant.id)]
        if service_id:
            service_domain.append(('id', '=', int(service_id)))
        elif service_code:
            service_domain.append(('code', '=', service_code))
        else:
            return {'error': 'Service ID or Service Code is required.'}

        service = request.env['link.service.catalog'].sudo().search(service_domain, limit=1)
        if not service:
            return {'error': 'Service not found in tenant catalog.'}

        result = service.check_availability(date_from_str=date_from, date_to_str=date_to, quantity=quantity)
        result['service_id'] = service.id
        result['service_name'] = service.name
        return result

    @http.route('/api/link/v1/price', type='jsonrpc', auth='none', methods=['POST'], csrf=False)
    def api_calculate_price(self, **kwargs):
        """حساب السعر الرسمي الحتمي"""
        tenant_id = kwargs.get('tenant_id')
        service_id = kwargs.get('service_id')
        service_code = kwargs.get('service_code')
        options = kwargs.get('options', {})
        secret = kwargs.get('secret')

        tenant, err = self._authenticate_tenant(tenant_id=tenant_id, secret=secret)
        if err:
            return err

        service_domain = [('tenant_id', '=', tenant.id)]
        if service_id:
            service_domain.append(('id', '=', int(service_id)))
        elif service_code:
            service_domain.append(('code', '=', service_code))
        else:
            return {'error': 'Service ID or Service Code is required.'}

        service = request.env['link.service.catalog'].sudo().search(service_domain, limit=1)
        if not service:
            return {'error': 'Service not found in tenant catalog.'}

        return service.calculate_price(options=options)

    @http.route('/api/link/v1/request/draft', type='jsonrpc', auth='none', methods=['POST'], csrf=False)
    def api_create_request_draft(self, **kwargs):
        """إنشاء مسودة طلب جديدة من واتساب أو Dify"""
        tenant_id = kwargs.get('tenant_id')
        secret = kwargs.get('secret')
        partner_phone = kwargs.get('partner_phone')
        customer_name = kwargs.get('customer_name')
        service_id = kwargs.get('service_id')
        chatwoot_conv_id = kwargs.get('chatwoot_conversation_id')
        initial_data = kwargs.get('data', {})

        tenant, err = self._authenticate_tenant(tenant_id=tenant_id, secret=secret)
        if err:
            return err

        if not partner_phone or not service_id:
            return {'error': 'partner_phone and service_id are required.'}

        return request.env['link.service.request'].sudo().create_request_draft(
            tenant_id=tenant.id,
            partner_phone=partner_phone,
            customer_name=customer_name,
            service_id=int(service_id),
            chatwoot_conv_id=chatwoot_conv_id,
            initial_data=initial_data,
        )

    @http.route('/api/link/v1/request/update', type='jsonrpc', auth='none', methods=['POST'], csrf=False)
    def api_update_request_data(self, **kwargs):
        """تحديث بيانات الطلب المجمعة من العميل"""
        request_id = kwargs.get('request_id')
        new_data = kwargs.get('data', {})

        req = request.env['link.service.request'].sudo().browse(int(request_id))
        if not req.exists():
            return {'error': 'Request record not found.'}

        return req.update_collected_data(new_data)

    @http.route('/api/link/v1/request/document', type='jsonrpc', auth='none', methods=['POST'], csrf=False)
    def api_attach_document(self, **kwargs):
        """رفع مستند أو صورة من واتساب"""
        request_id = kwargs.get('request_id')
        requirement_code = kwargs.get('requirement_code')
        file_base64 = kwargs.get('file_base64')
        filename = kwargs.get('filename')
        mime_type = kwargs.get('mime_type', 'image/jpeg')

        req = request.env['link.service.request'].sudo().browse(int(request_id))
        if not req.exists():
            return {'error': 'Request record not found.'}

        return req.attach_document(
            requirement_code_or_name=requirement_code,
            file_base64=file_base64,
            filename=filename,
            mime_type=mime_type,
        )

    @http.route('/api/link/v1/request/approve', type='jsonrpc', auth='none', methods=['POST'], csrf=False)
    def api_approve_request(self, **kwargs):
        """اعتماد الطلب برمجياً (من زر الماكرو في Chatwoot أو لوحة التاجر)"""
        request_id = kwargs.get('request_id')
        req = request.env['link.service.request'].sudo().browse(int(request_id))
        if not req.exists():
            return {'error': 'Request record not found.'}

        try:
            req.action_approve()
            return {
                'success': True,
                'request_id': req.id,
                'request_number': req.name,
                'state': req.state,
                'partner_phone': req.partner_phone,
                'total_price': req.total_price,
            }
        except Exception as e:
            return {'error': str(e)}

    @http.route('/api/link/v1/request/attach_by_phone', type='jsonrpc', auth='none', methods=['POST'], csrf=False)
    def api_attach_by_phone(self, **kwargs):
        """رفع مستند أو صورة تلقائياً للطلب النشط برقم الهاتف"""
        phone = kwargs.get('phone') or kwargs.get('sender_phone') or ''
        file_base64 = kwargs.get('file_base64')
        filename = kwargs.get('filename') or 'whatsapp_photo.jpg'
        tenant_id = kwargs.get('tenant_id')
        session_id = kwargs.get('session_id')

        clean_phone = phone.replace('@c.us', '').replace('@s.whatsapp.net', '').replace('@lid', '').replace('+', '')
        domain = [
            '|',
            ('partner_phone', 'like', clean_phone[-8:] if len(clean_phone) >= 8 else clean_phone),
            ('whatsapp_chat_id', '=', phone),
        ]
        if tenant_id:
            domain.append(('tenant_id', '=', int(tenant_id)))
        elif session_id:
            domain.append(('tenant_id.openwa_session_id', '=', session_id))

        req = request.env['link.service.request'].sudo().search(domain, order='id desc', limit=1)
        if not req:
            req = request.env['link.service.request'].sudo().search([], order='id desc', limit=1)
            if not req:
                return {'error': 'No request found in system.'}

        res = req.attach_document(
            requirement_code_or_name=kwargs.get('requirement_code') or 'passport_copy',
            file_base64=file_base64,
            filename=filename,
        )
        return {
            'success': True,
            'request_id': req.id,
            'request_number': req.name,
            'state': req.state,
            'doc_result': res,
        }

    @http.route('/api/link/v1/customer/update_name', type='jsonrpc', auth='none', methods=['POST'], csrf=False)
    def api_update_customer_name(self, **kwargs):
        """تحديث اسم العميل للطلب النشط ولجهة الاتصال"""
        phone = kwargs.get('phone') or kwargs.get('sender_phone') or ''
        customer_name = kwargs.get('customer_name') or kwargs.get('name') or ''
        clean_phone = phone.replace('@c.us', '').replace('@s.whatsapp.net', '').replace('@lid', '').replace('+', '')

        if not clean_phone or not customer_name:
            return {'error': 'Phone and customer_name are required.'}

        clean_name = customer_name.strip()
        partner_domain = ['|', ('phone', '=', clean_phone), ('phone', 'like', clean_phone[-8:] if len(clean_phone) >= 8 else clean_phone)]
        partner = request.env['res.partner'].sudo().search(partner_domain, limit=1)
        if not partner:
            partner = request.env['res.partner'].sudo().create({
                'name': clean_name,
                'phone': clean_phone,
            })
        else:
            partner.sudo().write({'name': clean_name})

        req = request.env['link.service.request'].sudo().search([
            ('partner_phone', 'like', clean_phone[-8:] if len(clean_phone) >= 8 else clean_phone)
        ], order='id desc', limit=1)

        if req:
            req.partner_id.sudo().write({'name': clean_name})
            req.update_customer_name(clean_name)

        return {
            'success': True,
            'partner_id': partner.id,
            'customer_name': clean_name,
            'request_id': req.id if req else None,
            'request_number': req.name if req else None,
        }

    @http.route('/api/link/v1/message/route', type='jsonrpc', auth='none', methods=['POST'], csrf=False)
    def api_route_incoming_message(self, **kwargs):
        """توجيه الرسائل الذكي: فحص نمط الرد (أزرار ترحيبية / ردود سريعة / حجز فوري / ذكاء اصطناعي)"""
        tenant_id = kwargs.get('tenant_id')
        tenant_slug = kwargs.get('tenant_slug')
        session_id = kwargs.get('session_id')
        secret = kwargs.get('secret')
        sender_phone = kwargs.get('sender_phone') or kwargs.get('sender')
        customer_name = kwargs.get('customer_name') or kwargs.get('name')
        message_text = (kwargs.get('message_text') or kwargs.get('text') or '').strip()
        selected_button = kwargs.get('selected_button')
        whatsapp_chat_id = kwargs.get('whatsapp_chat_id') or kwargs.get('chat_id') or kwargs.get('chatId') or (sender_phone if '@' in (sender_phone or '') else False)

        # استخراج المستأجر إما بالمعرف أو برمز الجلسة في OpenWA
        domain = []
        if tenant_id:
            domain.append(('id', '=', int(tenant_id)))
        elif tenant_slug:
            domain.append(('code', '=', tenant_slug))
        elif session_id:
            domain.append(('openwa_session_id', '=', session_id))
        else:
            tenant = request.env['link.tenant'].sudo().search([], limit=1)
            if not tenant:
                return {'error': 'No tenant configured in system.'}

        if domain:
            tenant = request.env['link.tenant'].sudo().search(domain, limit=1)
            if not tenant:
                tenant = request.env['link.tenant'].sudo().search([], limit=1)

        # تنظيف رقم الهاتف
        clean_phone = sender_phone.replace('@c.us', '').replace('@s.whatsapp.net', '').replace('@lid', '').replace('+', '') if sender_phone else ''

        # مطابقة زر محدد أو نصوص البدء والقوائم
        text_lower = message_text.lower()
        is_greeting = any(g in text_lower for g in ['مرحبا', 'مرحب', 'هلا', 'سلام', 'السلام', 'start', 'menu', 'قائمة', 'ابدأ', 'أهلا', 'أهلاً', 'صباح الخير', 'مساء الخير'])

        # 1. إذا اختار العميل زر "تصفح العروض والخدمات" أو كتب "1" أو "عروض" أو "باقات"
        if selected_button == 'btn_catalog' or message_text in ('1', tenant.welcome_button_1) or any(w in text_lower for w in ['عروض', 'عرض', 'باقات', 'باقة', 'خدمات']):
            services = request.env['link.service.catalog'].sudo().search([
                ('tenant_id', '=', tenant.id),
                ('state', '=', 'active'),
            ])
            lines = [f"🌟 *عروض وخدمات {tenant.name}:*"]
            for idx, s in enumerate(services, 1):
                price_str = f"{s.base_price:,.0f} {tenant.currency_id.name}" if s.base_price else "حسب الطلب"
                lines.append(f"{idx}. *{s.name}* ({price_str})")
            lines.append("\n💡 يسعدنا خدمتكم في أي باقة تناسبكم، اكتب لي اسم الباقة ونبدأ الترتيبات فوراً!")
            return {
                'action': 'send_message',
                'type': 'text',
                'message': "\n".join(lines),
            }

        # 2. إذا اختار زر "التحدث مع موظف" أو كتب "3"
        if selected_button == 'btn_human' or message_text in ('3', tenant.welcome_button_3) or any(w in text_lower for w in ['موظف', 'بشري', 'انسان', 'اكلم موظف']):
            return {
                'action': 'human_takeover',
                'type': 'text',
                'message': "أهلاً بك! تم تحويل المحادثة لأحد مسؤولي المبيعات وسيتواصل معك مباشرة الآن إن شاء الله.",
            }

        # 3. إذا اختار زر "استفسار وحجز ذكي" أو كتب "2"
        if selected_button == 'btn_ai' or message_text in ('2', tenant.welcome_button_2):
            return {
                'action': 'send_message',
                'type': 'text',
                'message': "أهلاً وسهلاً بك! تفضل، كيف أقدر أخدمك بخصوص رحلاتنا أو الحجوزات؟ يسعدني أجاوبك على أي استفسار.",
            }

        # 4. فحص الردود التلقائية الثابتة (Quick Replies & Keyword Matching)
        for qr in tenant.quick_reply_ids.filtered(lambda r: r.active):
            keywords = [k.strip().lower() for k in qr.trigger_keywords.split(',') if k.strip()]
            if any(k in text_lower for k in keywords):
                if qr.action_type == 'send_catalog':
                    services = request.env['link.service.catalog'].sudo().search([
                        ('tenant_id', '=', tenant.id),
                        ('state', '=', 'active'),
                    ])
                    lines = [f"🌟 *دليل خدماتنا:*"]
                    for idx, s in enumerate(services, 1):
                        lines.append(f"{idx}. {s.name} ({s.base_price:,.0f} {tenant.currency_id.name})")
                    return {
                        'action': 'send_message',
                        'type': 'text',
                        'message': (qr.response_text or '') + "\n\n" + "\n".join(lines),
                    }
                elif qr.action_type == 'handoff_human':
                    return {
                        'action': 'human_takeover',
                        'type': 'text',
                        'message': qr.response_text or "تم تحويل المحادثة لأحد ممثلي خدمة العملاء.",
                    }
                elif qr.action_type == 'handoff_ai':
                    return {
                        'action': 'route_to_ai',
                        'type': 'handoff',
                        'message': qr.response_text or "يسعدنا خدمتكم على مدار الساعة.",
                    }
                else:
                    return {
                        'action': 'send_message',
                        'type': 'text',
                        'message': qr.response_text,
                    }

        # فحص الشريك وجهة الاتصال في النظام
        partner_domain = ['|', ('phone', '=', clean_phone), ('phone', 'like', clean_phone[-8:] if len(clean_phone) >= 8 else clean_phone)]
        partner = request.env['res.partner'].sudo().search(partner_domain, limit=1) if clean_phone else None
        has_real_name = bool(
            partner and partner.name 
            and not partner.name.startswith('عميل واتساب') 
            and partner.name != 'عميل واتساب' 
            and len(partner.name.strip()) >= 3 
            and partner.name not in ('e', 'None')
        )
        customer_salutation = f"أستاذ {partner.name}" if (has_real_name and partner) else "عزيزنا العميل"

        # فحص الطلب النشط غير المكتمل (قيد الجمع أو قيد المراجعة)
        in_progress_domain = [
            ('state', 'in', ['draft', 'collecting_info', 'collecting_docs', 'pending_review']),
            '|',
            ('partner_phone', 'like', clean_phone[-8:] if len(clean_phone) >= 8 else clean_phone),
            ('whatsapp_chat_id', '=', whatsapp_chat_id or 'NONE'),
        ]
        active_req = request.env['link.service.request'].sudo().search(in_progress_domain, order='id desc', limit=1) if clean_phone else None
        if active_req and whatsapp_chat_id and not active_req.whatsapp_chat_id:
            active_req.sudo().write({'whatsapp_chat_id': whatsapp_chat_id})

        # استخراج اسم العميل الحقيقي من شريك الطلب النشط إذا لم يكن محدداً من قبل
        if active_req and active_req.partner_id and not has_real_name:
            p_name = active_req.partner_id.name or ''
            if p_name and not p_name.startswith('عميل واتساب') and len(p_name.strip()) >= 3 and p_name not in ('e', 'None'):
                partner = active_req.partner_id
                has_real_name = True
                customer_salutation = f"أستاذ {p_name}"

        # فحص آخر طلب للعميل عموماً لمعرفة هل تم اعتماده مسبقاً
        last_req = request.env['link.service.request'].sudo().search([
            '|',
            ('partner_phone', 'like', clean_phone[-8:] if len(clean_phone) >= 8 else clean_phone),
            ('whatsapp_chat_id', '=', whatsapp_chat_id or 'NONE'),
        ], order='id desc', limit=1) if clean_phone else None

        last_req_is_confirmed = bool(not active_req and last_req and last_req.state == 'confirmed')

        # جلب خدمات المستأجر النشطة
        tenant_services = request.env['link.service.catalog'].sudo().search([
            ('tenant_id', '=', tenant.id),
            ('state', '=', 'active'),
        ])
        matched_service = _match_service(text_lower, tenant_services)

        tokens = set(re.findall(r'[\w]+', text_lower))
        question_tokens = {'كيف', 'وش', 'ايش', 'هل', 'وين', 'متى', 'ليه', 'ليش', 'نلبس', 'رايك', 'رأيك', 'تنصحني', 'نصيحة', 'معلومات', 'طبيعة', 'طقس', 'جو', 'أكل', 'اكل', 'حلال', 'شروط', 'مكان', 'طريقة', 'طريقه'}
        has_price_q = bool({'بكم', 'كم'} & tokens) and not any(g in text_lower for g in ['عليكم', 'مرحبا بكم', 'اهلا بكم', 'أهلا بكم'])
        is_question = bool(tokens & question_tokens) or has_price_q or ('؟' in text_lower) or ('?' in text_lower)

        # 5. إذا تم اعتماد الطلب السابق ويبدأ العميل محادثة جديدة، نرحب به ونرسل له العروض من البداية
        if last_req_is_confirmed and not matched_service and (not is_question or is_greeting):
            customer_salutation = f"أستاذ {partner.name}" if has_real_name else "عزيزنا العميل"
            lines = [
                f"يا هلا ومرحباً بك مجدداً {customer_salutation}! 🌸",
                f"يسعدنا دائماً تواصلك معنا بعد اعتماد وتأكيد طلبك السابق ({last_req.name}).\n",
                f"🌟 *إليك قائمة عروضنا وخدماتنا المتاحة حالياً:*",
            ]
            for idx, s in enumerate(tenant_services, 1):
                price_str = f"{s.base_price:,.0f} {tenant.currency_id.name}" if s.base_price else "حسب الطلب"
                lines.append(f"{idx}. *{s.name}* ({price_str})")
            lines.append("\n💡 يسعدنا خدمتك في أي وجهة أو حجز جديد، اكتب لي اسم الخدمة أو رقمها ونبدأ الترتيبات فوراً!")
            return {
                'action': 'send_message',
                'type': 'text',
                'message': "\n".join(lines),
            }

        # 6. إذا كانت أول رسالة أو تحية والنمط هجين أو قواعد فقط (ولا ترسل إطلاقاً إذا كانت المحادثة جارية)
        has_prior_messages = kwargs.get('has_prior_messages', False)
        if is_greeting and tenant.bot_mode in ('hybrid', 'rules_only') and not has_prior_messages and not active_req:
            return {
                'action': 'send_interactive_buttons',
                'type': 'buttons',
                'message': tenant.welcome_message or "أهلاً بك! يسعدنا تواصلك معنا 🌸\nكيف نقدر نخدمك اليوم؟",
                'buttons': [
                    {'id': 'btn_catalog', 'title': tenant.welcome_button_1 or '🌟 العروض والخدمات'},
                    {'id': 'btn_ai', 'title': tenant.welcome_button_2 or '💬 استفسار وحجز'},
                    {'id': 'btn_human', 'title': tenant.welcome_button_3 or '👨‍💼 التحدث مع موظف'},
                ]
            }

        # تحديد مسمى القسم / الموظف ديناميكياً حسب نوع النشاط
        is_retail = (tenant.business_category in ('retail', 'other') or any(s.category == 'ملابس وأزياء' for s in tenant_services))
        dept_title = "مسؤول المبيعات" if is_retail else "مسؤول الحجوزات والرحلات"

        # 7. فحص رسائل التصحيح أو الاعتراض على الطلب السابق (Complaints & Corrections)
        complaint_keywords = ['لخبطه', 'لخبطة', 'غلط', 'خطأ', 'ما طلبت', 'مو كذا', 'مو هذا', 'ليس هذا', 'خربطة', 'خربطه', 'غير صحيح', 'عكست', 'كنسل', 'إلغاء']
        if any(c in text_lower for c in complaint_keywords):
            if active_req and active_req.state in ('collecting_info', 'collecting_docs'):
                active_req.sudo().write({'state': 'cancelled'})
            return {
                'action': 'send_message',
                'type': 'text',
                'message': f"العذر والسموحة منك {customer_salutation}، حقك علينا! تم إلغاء أي طلب سابق. تفضل اكتب لي بالضبط طلبك وبنرتبه لك فوراً 🌸",
            }

        # 8. فحص إذا كان العميل يرسل اسمه الشخصي استجابة لطلب الاسم أو ببادئة صريحة
        explicit_name = _clean_customer_name(message_text)
        if explicit_name:
            if not partner:
                partner = request.env['res.partner'].sudo().create({
                    'name': explicit_name,
                    'phone': clean_phone,
                })
            else:
                partner.sudo().write({'name': explicit_name})
            has_real_name = True
            customer_salutation = f"أستاذ {explicit_name}"

            if active_req:
                active_req.partner_id.sudo().write({'name': explicit_name})
                active_req.update_customer_name(explicit_name)
                req_info = active_req.get_missing_requirements()
                missing_fields = req_info.get('missing_fields', [])
                missing_docs = req_info.get('missing_documents', [])

                if missing_fields:
                    f_names = " و ".join([f"[{f['name']}]" for f in missing_fields])
                    msg = (
                        f"حياك الله {customer_salutation}! يسعدنا خدمتك 🌸\n"
                        f"معك {dept_title}. تم تسجيل طلبك لـ *{active_req.service_id.name}* برقم ({active_req.name}) باسمك الكريم.\n\n"
                        f"📋 لتجهيز طلبك بدقة، لطفاً حدد لنا: {f_names}."
                    )
                elif missing_docs:
                    doc_name = missing_docs[0]['name']
                    msg = (
                        f"حياك الله {customer_salutation}! يسعدنا خدمتك 🌸\n"
                        f"معك {dept_title}. تم تسجيل طلبك لـ *{active_req.service_id.name}* برقم ({active_req.name}) باسمك الكريم.\n\n"
                        f"📎 لإكمال وتأكيد الطلب رسمياً، لطفاً أرسل لنا صورة *{doc_name}* هنا مباشرة 🧾"
                    )
                else:
                    msg = f"حياك الله {customer_salutation}! معك {dept_title}. طلبك برقم ({active_req.name}) مسجل باسمك الكريم وهو قيد المراجعة والاعتماد ✅"

                return {
                    'action': 'booking_updated',
                    'type': 'text',
                    'message': msg,
                    'customer_name': explicit_name,
                    'request_id': active_req.id,
                    'request_number': active_req.name,
                }

        # 9. إدارة الطلب النشط خطوة بخطوة إذا كان العميل يكمل متطلبات طلبه الجاري
        if active_req:
            # فحص استفسار العميل عن حالة طلبه بمختلف الصيغ واللهجات (وين قد طلبي، وش صار، وين وصل)
            order_inquiry_tokens = [
                'وين قد طلبي', 'وين طلبي', 'وين وصل طلبي', 'وين حقي الطلب', 'وين طلبي واصل',
                'وش صار على طلبي', 'وش صار بطلبي', 'ايش صار بطلبي', 'ايش صار على طلبي',
                'شو صار بطلبي', 'كيف طلبي', 'حالة الطلب', 'حالة طلبي', 'متى تعتمدون',
                'اعتمدتوا', 'اعتمدتو', 'هل تم تأكيد', 'طمني على الطلب', 'وين واصل طلبي'
            ]
            if any(w in text_lower for w in order_inquiry_tokens):
                req_info = active_req.get_missing_requirements()
                missing_fields = req_info.get('missing_fields', [])
                missing_docs = req_info.get('missing_documents', [])

                if active_req.state == 'collecting_docs':
                    doc_name = missing_docs[0]['name'] if missing_docs else "المستند المطلوب أو الهوية"
                    return {
                        'action': 'send_message',
                        'type': 'text',
                        'message': (
                            f"يا هلا ومرحباً {customer_salutation}! 🌸\n"
                            f"طلبك برقم *({active_req.name})* لـ *{active_req.service_id.name}* مسجل لدينا بالنظام ✅\n\n"
                            f"📎 وهو بانتظار استلام صورة *{doc_name}* لتأكيده واعتماده رسمياً فوراً. تفضل بإرسالها هنا في الشات وسنكمل الباقي مباشرة 🧾"
                        ),
                    }
                elif active_req.state == 'collecting_info':
                    f_guide = " و ".join([f"[{f['name']}]" for f in missing_fields])
                    return {
                        'action': 'send_message',
                        'type': 'text',
                        'message': (
                            f"أهلاً بك {customer_salutation}! 🌸\n"
                            f"طلبك برقم *({active_req.name})* لـ *{active_req.service_id.name}* مسجل لدينا، ومتبقي لإتمامه تزويدنا بـ: {f_guide}.\n"
                            f"تفضل بكتابتها هنا لنعتمد طلبك فوراً!"
                        ),
                    }
                elif active_req.state == 'pending_review':
                    return {
                        'action': 'send_message',
                        'type': 'text',
                        'message': (
                            f"يا هلا ومرحباً {customer_salutation}! 🌸\n"
                            f"طلبك برقم *({active_req.name})* لـ *{active_req.service_id.name}* مكتمل وجاري مراجعته وتأكيده رسمياً من قبل الإدارة حالياً ✅\n"
                            f"فريقنا يتابع الإجراءات وسنوافيك بالتحديث فوراً."
                        ),
                    }
                elif active_req.state == 'confirmed':
                    return {
                        'action': 'send_message',
                        'type': 'text',
                        'message': (
                            f"أهلاً وسهلاً {customer_salutation}! 🌸\n"
                            f"طلبك برقم *({active_req.name})* لـ *{active_req.service_id.name}* معتمد ومؤكد رسمياً بنجاح ✅ وجاري تجهيز الترتيبات لك وسنوافيك بكافة المستجدات أولاً بأول."
                        ),
                    }

            # ب) إذا كان الطلب في مرحلة جمع البيانات (المقاسات / العنوان / التواريخ)
            elif active_req.state == 'collecting_info':
                # رصد الكلام الجانبي والسوالف لتوجيه المدخل بدقة ومنع رفع بيانات عشوائية
                side_talk_tokens = {'جو', 'الجو', 'طقس', 'الطقس', 'حر', 'برد', 'مطر', 'حلو', 'جميل', 'ضحك', 'ضحكتني', 'هههه', 'ههههه', 'سلطان', 'يزيد', 'بكلم', 'جلس', 'سالفة', 'كلام'}
                is_side_chatter = any(st in text_lower for st in side_talk_tokens)

                new_collected = {}
                if not is_side_chatter:
                    size_match = re.search(r'\b(52|54|56|58|60|xxl|xl|l|m|s|صغير|وسط|كبير)\b', text_lower)
                    if size_match:
                        new_collected['size'] = size_match.group(1).upper()

                    addr_indicators = ['حي', 'شارع', 'طريق', 'مربع', 'مخطط', 'عنوان', 'العنوان', 'توصيل الى', 'توصيل ل', 'توصيل:']
                    if any(c in text_lower for c in addr_indicators):
                        new_collected['delivery_address'] = message_text.strip()

                if new_collected:
                    active_req.update_collected_data(new_collected)
                    req_info = active_req.get_missing_requirements()
                    missing_fields = req_info.get('missing_fields', [])
                    missing_docs = req_info.get('missing_documents', [])

                    if missing_fields:
                        rem_fields = " و ".join([f"[{f['name']}]" for f in missing_fields])
                        return {
                            'action': 'send_message',
                            'type': 'text',
                            'message': f"تم تسجيل البيانات بنجاح 👍 بقي خطوة لتجهيز طلبك ({active_req.name})، لطفاً زودنا بـ: {rem_fields} 🌸",
                        }
                    elif missing_docs:
                        doc_name = missing_docs[0]['name']
                        return {
                            'action': 'send_message',
                            'type': 'text',
                            'message': f"ممتاز تم تسجيل كافة بيانات طلبك ({active_req.name}) بنجاح ✅\n\n📎 الخطوة الأخيرة: لطفاً أرسل لنا صورة *{doc_name}* لتأكيد الطلب فوراً 🧾",
                        }
                    else:
                        return {
                            'action': 'send_message',
                            'type': 'text',
                            'message': f"تم استلام وتأكيد بيانات طلبك برقم ({active_req.name}) بنجاح ✅ وهو الآن قيد المراجعة والاعتماد.",
                        }
                elif not is_question or is_side_chatter:
                    req_info = active_req.get_missing_requirements()
                    missing_fields = req_info.get('missing_fields', [])
                    if missing_fields:
                        f_guide = " و ".join([f"[{f['name']}: {f['options'] or 'تحديد'}]" if f.get('options') else f"[{f['name']}]" for f in missing_fields])
                        return {
                            'action': 'send_message',
                            'type': 'text',
                            'message': (
                                f"لتجهيز وتأكيد طلبك لـ *{active_req.service_id.name}* برقم ({active_req.name}) بدقة وتفادي أي أخطاء في البيانات، لطفاً كتابة البيانات المطلوبة بالطريقة التالية:\n"
                                f"• {f_guide}\n\n"
                                f"مثال: (المقاس: 56، العنوان: الرياض حي النرجس شارع عثمان) 🌸"
                            ),
                        }

            # ج) إذا كان الطلب في مرحلة انتظار المستند / السند
            elif active_req.state == 'collecting_docs':
                if any(w in text_lower for w in ['وش ارسل', 'المطلوب', 'ايش باقي', 'المستند', 'سند']):
                    missing_docs = active_req.document_ids.filtered(lambda d: d.state in ('missing', 'rejected'))
                    doc_name = missing_docs[:1].name if missing_docs else "المستند المطلوب"
                    return {
                        'action': 'send_message',
                        'type': 'text',
                        'message': f"طلبك برقم ({active_req.name}) جاهز وبانتظار صورة *{doc_name}* لتأكيده واعتماده فوراً 🌸",
                    }

        # 10. فحص نية الحجز والطلب الصريحة لبدء طلب جديد
        booking_keywords = ['احجز', 'حجز', 'اشتراك', 'أود البدء', 'ابدأ', 'تأكيد', 'اعتمد', 'ابغى احجز', 'اريد احجز', 'اريد حجز', 'احجز لي', 'اعتمد الحجز', 'اريد شراء', 'ابغى اشتري', 'طلب', 'اشتري', 'اطلب']
        has_explicit_booking = any(w in text_lower for w in booking_keywords)

        is_booking_action = False
        if has_explicit_booking and not (is_question and not any(w in text_lower for w in ['اريد احجز', 'ابغى احجز', 'احجز لي', 'اعتمد الحجز', 'اريد شراء', 'ابغى اطلب', 'اطلب لي'])):
            is_booking_action = True
        elif matched_service and not is_question and any(w in text_lower for w in ['اريد', 'ابغى', 'ابي', 'ودي', 'احجز', 'حجز', 'طلب', 'شراء']):
            is_booking_action = True

        if is_booking_action:
            if not matched_service:
                lines = [f"أبشر ويسعدنا خدمتك {customer_salutation}! 🌸\nأي خدمة أو منتج ترغب في طلبه اليوم؟ لدينا:"]
                for idx, s in enumerate(tenant_services, 1):
                    price_str = f"{s.base_price:,.0f} {tenant.currency_id.name}" if s.base_price else "حسب الطلب"
                    lines.append(f"{idx}. *{s.name}* ({price_str})")
                lines.append("\nاكتب لي اسم الخدمة أو المنتج ونبدأ معك فوراً!")
                return {
                    'action': 'send_message',
                    'type': 'text',
                    'message': "\n".join(lines),
                }

            if not has_real_name:
                req = request.env['link.service.request'].sudo().create_request_draft(
                    tenant_id=tenant.id,
                    service_id=matched_service.id,
                    partner_phone=clean_phone,
                    customer_name='عميل واتساب',
                    initial_data={'source': 'WhatsApp Direct Chat'},
                    whatsapp_chat_id=whatsapp_chat_id,
                )
                req_rec = request.env['link.service.request'].sudo().browse(req['request_id'])
                return {
                    'action': 'ask_customer_name',
                    'type': 'text',
                    'message': f"أهلاً وسهلاً بك في {tenant.name} 🌸\nمعك {dept_title}. لتسجيل طلبك لـ *{matched_service.name}* برقم ({req_rec.name}) وتأكيده رسمياً، ما هو اسمك الكريم ثلاثياً؟",
                    'request_id': req_rec.id,
                    'request_number': req_rec.name,
                }

            req = request.env['link.service.request'].sudo().create_request_draft(
                tenant_id=tenant.id,
                service_id=matched_service.id,
                partner_phone=clean_phone,
                customer_name=partner.name,
                initial_data={'source': 'WhatsApp Direct Chat'},
                whatsapp_chat_id=whatsapp_chat_id,
            )
            req_rec = request.env['link.service.request'].sudo().browse(req['request_id'])
            curr_sym = tenant.currency_id.symbol or tenant.currency_id.name
            req_info = req_rec.get_missing_requirements()
            missing_fields = req_info.get('missing_fields', [])
            missing_docs = req_info.get('missing_documents', [])

            if missing_fields:
                f_list = "\n".join([f"• {f['name']}: ({f['options']})" if f.get('options') else f"• {f['name']}" for f in missing_fields])
                msg = (
                    f"أبشر ويسعدنا خدمتك {customer_salutation}! تم تجهيز مسودة طلبك لـ *{matched_service.name}* برقم ({req_rec.name}).\n"
                    f"المبلغ: {req_rec.total_price:,.0f} {curr_sym}.\n\n"
                    f"📋 لتجهيز طلبك بدقة، لطفاً حدد لنا:\n{f_list}"
                )
            elif missing_docs:
                doc_name = missing_docs[0]['name']
                msg = (
                    f"أبشر ويسعدنا خدمتك {customer_salutation}! تم تسجيل طلبك لـ *{matched_service.name}* برقم ({req_rec.name}).\n"
                    f"المبلغ: {req_rec.total_price:,.0f} {curr_sym}.\n\n"
                    f"📎 لإكمال وتأكيد الطلب رسمياً، لطفاً أرسل لنا صورة *{doc_name}* هنا مباشرة 🧾"
                )
            else:
                msg = f"أبشر ويسعدنا خدمتك {customer_salutation}! تم تسجيل طلبك لـ *{matched_service.name}* برقم ({req_rec.name}) وهو قيد المراجعة والاعتماد ✅"

            return {
                'action': 'booking_created',
                'type': 'text',
                'message': msg,
                'customer_name': partner.name,
                'request_id': req_rec.id,
                'request_number': req_rec.name,
                'total_price': req_rec.total_price,
            }

        # 7. التوجيه لمحرك الذكاء الاصطناعي مع قاعدة المعرفة وتفاصيل النشاط التجاري
        services = request.env['link.service.catalog'].sudo().search([
            ('tenant_id', '=', tenant.id),
            ('state', '=', 'active'),
        ])
        catalog_summary = "\n".join([f"- {s.name}: {s.base_price:,.0f} {tenant.currency_id.name}. {s.description or ''}" for s in services])

        active_missing_fields = []
        active_missing_docs = []
        if active_req:
            r_info = active_req.get_missing_requirements()
            active_missing_fields = [f['name'] for f in r_info.get('missing_fields', [])]
            active_missing_docs = [d['name'] for d in r_info.get('missing_documents', [])]

        history_recs = request.env['link.service.request'].sudo().search([
            '|',
            ('partner_phone', 'like', clean_phone[-8:] if len(clean_phone) >= 8 else clean_phone),
            ('whatsapp_chat_id', '=', whatsapp_chat_id or 'NONE'),
        ], order='id desc', limit=5)
        orders_history = [{'number': r.name, 'service': r.service_id.name, 'state': r.state} for r in history_recs]

        return {
            'action': 'route_to_ai',
            'type': 'handoff',
            'tenant_id': tenant.id,
            'tenant_name': tenant.name,
            'ai_provider': getattr(tenant, 'ai_provider', 'built_in') or 'built_in',
            'ai_model': getattr(tenant, 'ai_model', 'gpt-4o-mini') or 'gpt-4o-mini',
            'ai_api_key': getattr(tenant, 'ai_api_key', '') or '',
            'ai_system_prompt': getattr(tenant, 'ai_system_prompt', '') or '',
            'ai_knowledge_base': getattr(tenant, 'ai_knowledge_base', '') or '',
            'catalog_summary': catalog_summary,
            'sender_phone': clean_phone,
            'customer_name': partner.name if (has_real_name and partner) else (customer_name if customer_name and customer_name != 'عميل واتساب' else ''),
            'message_text': message_text,
            'active_req_number': active_req.name if active_req else None,
            'active_req_service': active_req.service_id.name if active_req else None,
            'active_req_state': active_req.state if active_req else None,
            'active_req_missing_fields': active_missing_fields,
            'active_req_missing_docs': active_missing_docs,
            'customer_orders_history': orders_history,
            'last_req_is_confirmed': last_req_is_confirmed,
        }

