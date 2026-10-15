import base64
import time
from typing import List, Optional
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import PORT, OPENWA_DEFAULT_SESSION
from .odoo_client import odoo_client
from .openwa_client import openwa_client
from .ai_agent import ai_engine

app = FastAPI(title="LINK Conversational Middleware & WhatsApp Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ذاكرة تخزين مؤقتة للرسائل الحية والمحادثات للمحاكي ولوحة التحكم
conversation_store = {}
active_orders = {}
waiting_for_name_phones = set()
seen_message_ids = {}


class SendMessageRequest(BaseModel):
    phone: str
    name: Optional[str] = "سعد العتيبي"
    text: str
    selected_button: Optional[str] = None
    tenant_id: Optional[int] = 1


def get_conversation(phone: str):
    if phone not in conversation_store:
        conversation_store[phone] = [
            {
                "id": "msg_0",
                "sender": "system",
                "text": "بدأت المحادثة مع موظف LINK التجاري الذكي",
                "time": time.strftime("%H:%M"),
            }
        ]
    return conversation_store[phone]


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "LINK Middleware Engine"}


@app.get("/api/chat/history")
async def get_chat_history(phone: str = "+966509988776"):
    messages = get_conversation(phone)
    order = active_orders.get(phone, None)
    return {
        "phone": phone,
        "messages": messages,
        "active_order": order,
    }


@app.post("/api/chat/send")
async def send_chat_message(req: SendMessageRequest):
    """معالجة رسالة واردة من واجهة المحادثة وتوجيهها عبر Odoo 20"""
    phone = req.phone
    conv = get_conversation(phone)

    # إضافة رسالة العميل إلى سجل المحادثة
    user_msg = {
        "id": f"msg_{len(conv)+1}",
        "sender": "user",
        "text": req.text,
        "button": req.selected_button,
        "time": time.strftime("%H:%M"),
    }
    conv.append(user_msg)

    # إرسال الرسالة إلى Odoo 20 لفحص نمط الرد والأزرار والقواعد
    route_res = await odoo_client.route_message(
        sender_phone=phone,
        customer_name=req.name,
        text=req.text,
        selected_button=req.selected_button,
        tenant_id=req.tenant_id,
    )

    action = route_res.get("action", "send_message")
    bot_text = route_res.get("message", "")
    buttons = route_res.get("buttons", [])

    if action in ("booking_created", "booking_updated"):
        active_orders[phone] = {
            "request_id": route_res.get("request_id"),
            "number": route_res.get("request_number"),
            "customer_name": route_res.get("customer_name") or req.name,
            "state": "collecting_docs",
            "price": 5000.0,
            "documents": ["صورة جواز السفر"],
        }
    elif action == "route_to_ai":
        bot_text = await ai_engine.generate_response(
            user_message=req.text,
            conversation_history=conv,
            tenant_name=route_res.get("tenant_name", "مكتب الفخامة للسياحة والسفر"),
            tenant_id=route_res.get("tenant_id", 1),
            system_prompt=route_res.get("ai_system_prompt"),
            knowledge_base=route_res.get("ai_knowledge_base"),
            catalog_summary=route_res.get("catalog_summary"),
            ai_provider=route_res.get("ai_provider", "built_in"),
            ai_model=route_res.get("ai_model", "gpt-4o-mini"),
            ai_api_key=route_res.get("ai_api_key"),
            customer_name=route_res.get("customer_name") or req.name,
            active_req_number=route_res.get("active_req_number"),
            active_req_service=route_res.get("active_req_service"),
            active_req_state=route_res.get("active_req_state"),
            active_req_missing_fields=route_res.get("active_req_missing_fields"),
            active_req_missing_docs=route_res.get("active_req_missing_docs"),
            customer_orders_history=route_res.get("customer_orders_history"),
        )

    # إضافة رد النظام / البوت إلى السجل
    bot_msg = {
        "id": f"msg_{len(conv)+1}",
        "sender": "bot",
        "action": action,
        "text": bot_text,
        "buttons": buttons,
        "time": time.strftime("%H:%M"),
    }
    conv.append(bot_msg)

    return {
        "status": "success",
        "user_message": user_msg,
        "bot_response": bot_msg,
        "active_order": active_orders.get(phone),
    }


@app.post("/api/chat/upload_document")
async def upload_document_simulation(phone: str = "+966509988776", doc_name: str = "passport_copy"):
    """محاكاة استلام صورة أو مستند من واتساب وربطها بالطلب في أودو"""
    conv = get_conversation(phone)
    order = active_orders.get(phone)

    if not order or not order.get("request_id"):
        return {"error": "لا يوجد طلب نشط لهذا العميل حالياً."}

    # إضافة رسالة صورة في شات العميل
    conv.append({
        "id": f"msg_{len(conv)+1}",
        "sender": "user",
        "text": "📷 [صورة مرفقة: جواز_سفر.jpg]",
        "is_media": True,
        "time": time.strftime("%H:%M"),
    })

    # إرسال المرفق إلى أودو 20
    fake_b64 = base64.b64encode(b"FAKE_PASSPORT_IMAGE_BINARY").decode()
    res = await odoo_client.attach_document(
        request_id=order["request_id"],
        requirement_code="passport_copy",
        file_base64=fake_b64,
        filename="passport_customer.jpg",
    )

    order["state"] = "pending_review"
    order["doc_uploaded"] = True

    bot_msg = {
        "id": f"msg_{len(conv)+1}",
        "sender": "bot",
        "text": "تم استلام صورة جواز السفر بنجاح ✅\nطلبك الآن برقم " + order["number"] + " مكتمل وفي انتظار مراجعة واعتماد التاجر بضغطة زر.",
        "time": time.strftime("%H:%M"),
    }
    conv.append(bot_msg)

    return {
        "status": "success",
        "order": order,
        "bot_response": bot_msg,
    }


@app.post("/api/chat/approve")
async def approve_order(phone: str = "+966509988776"):
    """اعتماد الطلب من قبل التاجر وإرسال إشعار التأكيد الرسمي لواتساب العميل"""
    conv = get_conversation(phone)
    order = active_orders.get(phone)
    if not order or not order.get("request_id"):
        return {"error": "لا يوجد طلب للاعتماد."}

    await odoo_client.approve_request(order["request_id"])
    order["state"] = "confirmed"

    confirm_msg = {
        "id": f"msg_{len(conv)+1}",
        "sender": "bot",
        "text": f"🎉 *تهانينا! تم تأكيد طلبك رسمياً من قبل التاجر.*\nرقم التأكيد: #{order['number']}\nالمبلغ الإجمالي المعتمد: {order['price']:,.0f} ريال.\nنتمنى لك رحلة سعيدة!",
        "time": time.strftime("%H:%M"),
    }
    conv.append(confirm_msg)

    return {"status": "success", "order": order, "confirm_msg": confirm_msg}


# -------------------------------------------------------------
# نقاط الـ Webhook الحية لمنصات WhatsApp (OpenWA & Chatwoot)
# -------------------------------------------------------------
@app.post("/webhook/openwa")
async def openwa_webhook(request: Request):
    """استقبال الرسائل الحية من بوابة OpenWA وتمريرها لأودو ومعالجتها بالذكاء الطبيعي"""
    try:
        data = await request.json()
    except Exception:
        return {"status": "invalid_json"}

    event = data.get("event")
    session = data.get("sessionId") or data.get("session") or OPENWA_DEFAULT_SESSION

    # في OpenWA تأتي خصائص الرسالة إما مباشرة في الجذر أو داخل data/payload
    msg_data = data.get("data") or data.get("payload") or data
    from_me = msg_data.get("fromMe", False)

    # تجنب معالجة الرسائل الصادرة من البوت نفسه لتفادي الحلقات اللانهائية
    if from_me:
        return {"status": "ignored_self"}

    # تجنب تكرار معالجة نفس الرسالة من أحداث OpenWA المتعددة (Deduplication)
    wa_msg_id = msg_data.get("id") or msg_data.get("waMessageId") or data.get("id")
    now_ts = time.time()
    if wa_msg_id:
        if wa_msg_id in seen_message_ids:
            return {"status": "ignored_duplicate", "id": wa_msg_id}
        seen_message_ids[wa_msg_id] = now_ts
        if len(seen_message_ids) > 1000:
            cutoff = now_ts - 120
            for k in list(seen_message_ids.keys()):
                if seen_message_ids[k] < cutoff:
                    del seen_message_ids[k]

    # استقبال أحداث الرسائل الواردة
    if event in ("message.received", "message"):
        sender = msg_data.get("from") or msg_data.get("chatId") or ""
        body = (msg_data.get("body") or msg_data.get("text") or "").strip()
        push_name = msg_data.get("pushName") or msg_data.get("notifyName") or "عميل واتساب"
        msg_type = msg_data.get("type", "text")
        has_media = msg_data.get("hasMedia") or msg_type in ("image", "document", "video", "sticker")

        if not sender:
            return {"status": "ignored_no_sender"}

        # تجنب معالجة رسائل المجموعات والقنوات وحالات البث
        if any(ign in sender for ign in ["@g.us", "@newsletter", "@broadcast"]):
            return {"status": "ignored_group_or_broadcast"}

        # استخراج وحل رقم الهاتف الحقيقي واسم جهة الاتصال الفعلي من بوابة OpenWA
        resolved_contact = await openwa_client.resolve_contact(session_id=session, contact_id=sender)
        real_phone = resolved_contact.get("real_phone")
        saved_contact_name = resolved_contact.get("name")
        
        if not real_phone:
            clean_sender = sender.split("@")[0].replace("+", "")
            real_phone = clean_sender

        clean_phone = real_phone
        customer_name = saved_contact_name or push_name
        if customer_name.strip().lower() in ("e", "none", "", "عميل واتساب"):
            customer_name = "عميل واتساب"

        conv = get_conversation(clean_phone)

        # -------------------------------------------------------------
        # 1. معالجة الصور والمستندات المرفقة من واتساب تلقائياً
        # -------------------------------------------------------------
        if has_media:
            b64_data = None
            media_obj = msg_data.get("media") or msg_data.get("metadata", {}).get("media")
            if isinstance(media_obj, dict):
                b64_data = media_obj.get("data")

            # في حال لم تكن بيانات الصورة مضمنة في الويب هوك، نستخرجها فوراً من قاعدة البيانات
            if not b64_data and wa_msg_id:
                try:
                    import subprocess
                    cmd = [
                        "docker", "exec", "openwa-api", "sqlite3", "-cmd", ".timeout 3000", "/app/data/openwa.sqlite",
                        f"SELECT json_extract(metadata, '$.media.data') FROM messages WHERE waMessageId='{wa_msg_id}' OR id='{wa_msg_id}' LIMIT 1;"
                    ]
                    out = subprocess.check_output(cmd, text=True, timeout=5).strip()
                    if out and len(out) > 50:
                        b64_data = out
                except Exception as e:
                    print("Error fetching media from sqlite:", e)

            if b64_data:
                # رفع الصورة إلى Odoo 20 وربطها بالطلب النشط
                attach_res = await odoo_client.attach_by_phone(
                    phone=clean_phone,
                    file_base64=b64_data,
                    filename="whatsapp_document.jpg",
                    session_id=session,
                    whatsapp_chat_id=sender,
                )
                req_num = attach_res.get("request_number") or "طلبك"
                reply_text = f"وصلت الصورة الله يسعدك 👍 تم إرفاقها بطلبك ({req_num}) وجاري مراجعته واعتماده."
                await openwa_client.send_text(session_id=session, to=sender, text=reply_text)

                conv.append({
                    "id": f"msg_{len(conv)+1}",
                    "sender": "user",
                    "text": "📷 [صورة مرفقة من العميل]",
                    "is_media": True,
                    "time": time.strftime("%H:%M"),
                })
                conv.append({
                    "id": f"msg_{len(conv)+1}",
                    "sender": "bot",
                    "text": reply_text,
                    "time": time.strftime("%H:%M"),
                })
                return {"status": "image_attached", "request_number": req_num, "reply": reply_text}

        # -------------------------------------------------------------
        # 2. معالجة الرسائل النصية والردود الذكية
        # -------------------------------------------------------------
        if not body:
            return {"status": "ignored_empty_text"}

        selected_button = None
        if body == "1":
            selected_button = "btn_catalog"
        elif body == "2":
            selected_button = "btn_ai"
        elif body == "3":
            selected_button = "btn_human"

        conv.append({
            "id": f"msg_{len(conv)+1}",
            "sender": "user",
            "text": body,
            "button": selected_button,
            "time": time.strftime("%H:%M"),
        })

        # فحص هل المحادثة بانتظار اسم العميل مع تحقق صارم لمنع استخراج أي كلام جانبي
        if clean_phone in waiting_for_name_phones:
            words = body.strip().split()
            invalid_tokens = {
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
                'الله', 'استاذ', 'أستاذ', 'ياخوي', 'والله', 'ضحكتني', 'بروح', 'برجع'
            }
            # يجب أن يكون الاسم الحقيقي بين 2 إلى 4 كلمات ولا يحتوي على أي كلمة محظورة أو أرقام
            is_valid_name = (
                2 <= len(words) <= 4 
                and not any(w.lower() in invalid_tokens for w in words)
                and not any(any(ch.isdigit() for ch in w) for w in words)
            )
            if is_valid_name:
                import re
                clean_name = re.sub(r'^(?:أنا\s+اسمي|انا\s+اسمي|اسمي\s+هو|اسمي:|اسمي|معك|معاك)\s+', '', body.strip(), flags=re.IGNORECASE).strip()
                customer_name = clean_name
                waiting_for_name_phones.discard(clean_phone)
                body = f"اسمي {clean_name}"

        # توجيه الرسالة عبر Odoo 20
        res = await odoo_client.route_message(
            sender_phone=clean_phone,
            customer_name=customer_name,
            text=body,
            selected_button=selected_button,
            session_id=session,
            whatsapp_chat_id=sender,
            has_prior_messages=(len(conv) > 1),
        )

        action = res.get("action", "send_message")
        bot_text = res.get("message", "")
        buttons = res.get("buttons", [])

        if action == "ask_customer_name":
            waiting_for_name_phones.add(clean_phone)
        elif action in ("booking_created", "booking_updated"):
            waiting_for_name_phones.discard(clean_phone)
            active_orders[clean_phone] = {
                "request_id": res.get("request_id"),
                "number": res.get("request_number"),
                "customer_name": res.get("customer_name"),
                "state": "collecting_docs",
                "price": res.get("total_price", 5000.0),
                "documents": ["صورة جواز السفر"],
            }

        # إذا بدأ العميل دورة جديدة بعد اعتماد طلبه السابق، نفرغ الذاكرة المؤقتة القديمة
        if res.get("last_req_is_confirmed"):
            active_orders.pop(clean_phone, None)

        # في حال تم التوجيه للذكاء الاصطناعي لتوليد رد واقعي إنساني عبر RAG
        if action == "route_to_ai":
            bot_text = await ai_engine.generate_response(
                user_message=body,
                conversation_history=conv,
                tenant_name=res.get("tenant_name", "مكتب الفخامة للسياحة والسفر"),
                tenant_id=res.get("tenant_id", 1),
                system_prompt=res.get("ai_system_prompt"),
                knowledge_base=res.get("ai_knowledge_base"),
                catalog_summary=res.get("catalog_summary"),
                ai_provider=res.get("ai_provider", "built_in"),
                ai_model=res.get("ai_model", "gpt-4o-mini"),
                ai_api_key=res.get("ai_api_key"),
                customer_name=res.get("customer_name") or customer_name,
                active_req_number=res.get("active_req_number"),
                active_req_service=res.get("active_req_service"),
                active_req_state=res.get("active_req_state"),
                active_req_missing_fields=res.get("active_req_missing_fields"),
                active_req_missing_docs=res.get("active_req_missing_docs"),
                customer_orders_history=res.get("customer_orders_history"),
            )

        # إرسال الرد الفوري إلى واتساب الفعلي فقط للمستخدمين الحقيقيين (منع إرسال أي رسائل اختبارية من السكربتات)
        is_simulated_test = (
            msg_data.get("is_test") 
            or sender.startswith("test_") 
            or "simulated" in str(msg_data.get("id", "")).lower()
            or "test" in str(msg_data.get("id", "")).lower()
        )
        if not is_simulated_test:
            if action == "send_interactive_buttons" or buttons:
                await openwa_client.send_buttons(
                    session_id=session,
                    to=sender,
                    text=bot_text,
                    buttons=buttons or [
                        {'id': 'btn_catalog', 'title': '🌟 العروض والخدمات'},
                        {'id': 'btn_ai', 'title': '💬 استفسار وحجز'},
                        {'id': 'btn_human', 'title': '👨‍💼 التحدث مع موظف'},
                    ],
                )
            elif bot_text:
                await openwa_client.send_text(
                    session_id=session,
                    to=sender,
                    text=bot_text,
                )

        conv.append({
            "id": f"msg_{len(conv)+1}",
            "sender": "bot",
            "action": action,
            "text": bot_text,
            "buttons": buttons,
            "time": time.strftime("%H:%M"),
        })

    return {"status": "processed", "reply": bot_text, "action": action}


# تشغيل مجلد static للواجهة التفاعلية
app.mount("/static", StaticFiles(directory="/home/esam/PycharmProjects/odoo20/odoo20/odoo-20/middleware/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    with open("/home/esam/PycharmProjects/odoo20/odoo20/odoo-20/middleware/static/index.html", "r", encoding="utf-8") as f:
        return f.read()
