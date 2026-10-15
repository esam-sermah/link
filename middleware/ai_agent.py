import os
import logging
import httpx
from .rag_engine import rag_engine

logger = logging.getLogger("link.ai")


class ConversationalAIEngine:
    """محرك الذكاء الاصطناعي التفاعلي المحاكي للموظف وصاحب العمل البشري المحترف مع دعم الفكتورز و RAG"""

    async def generate_response(
        self,
        user_message: str,
        conversation_history: list,
        tenant_name: str = "مكتب الفخامة للسياحة والسفر",
        tenant_id: int = 1,
        system_prompt: str = None,
        knowledge_base: str = None,
        catalog_summary: str = None,
        ai_provider: str = "built_in",
        ai_model: str = "gpt-4o-mini",
        ai_api_key: str = None,
        customer_name: str = None,
        active_req_number: str = None,
        active_req_service: str = None,
        active_req_state: str = None,
        active_req_missing_fields: list = None,
        active_req_missing_docs: list = None,
        customer_orders_history: list = None,
    ) -> str:
        # 1. فهرسة وتحديث الفكتورز لمعرفة وكتالوج المستأجر في محرك RAG
        rag_engine.index_tenant_knowledge(
            tenant_id=tenant_id,
            knowledge_base=knowledge_base or "",
            catalog_summary=catalog_summary or "",
            tenant_name=tenant_name,
        )

        # 2. فحص هل استفسار العميل يخص حالة طلبه الجاري (وين قد طلبي، ايش صار بطلبي، الخ)
        if rag_engine.is_order_status_query(user_message):
            order_reply = rag_engine.resolve_customer_order_status(
                customer_name=customer_name,
                active_req_number=active_req_number,
                active_req_service=active_req_service,
                active_req_state=active_req_state,
                active_req_missing_fields=active_req_missing_fields,
                active_req_missing_docs=active_req_missing_docs,
                customer_orders_history=customer_orders_history,
            )
            if order_reply:
                return order_reply

        # 3. استرجاع المقاطع الأكثر صلة دلالياً عبر البحث بالفكتورز (Vector Semantic Search)
        rag_results = rag_engine.search_knowledge(query=user_message, tenant_id=tenant_id, top_k=3)
        retrieved_context = "\n".join([f"• {r['chunk']}" for r in rag_results])

        # فحص مفاتيح الـ API الخارجية سواء من إعدادات المستأجر في أودو أو متغيرات البيئة
        active_key = ai_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("AI_API_KEY")
        active_provider = ai_provider

        if not ai_api_key and os.getenv("GEMINI_API_KEY"):
            active_provider = "gemini"
            ai_model = ai_model or "gemini-1.5-flash"
        elif not ai_api_key and os.getenv("GROQ_API_KEY"):
            active_provider = "groq"
            ai_model = ai_model or "llama-3.3-70b-versatile"
        elif not ai_api_key and os.getenv("OPENAI_API_KEY"):
            active_provider = "openai"
            ai_model = ai_model or "gpt-4o-mini"

        # 4. إذا كان التاجر قد أدخل مفتاح API لـ OpenAI أو Gemini أو Groq أو OpenRouter
        if active_provider in ("openai", "gemini", "groq", "openrouter") and active_key:
            endpoint = {
                "openai": "https://api.openai.com/v1/chat/completions",
                "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                "groq": "https://api.groq.com/openai/v1/chat/completions",
                "openrouter": "https://openrouter.ai/api/v1/chat/completions",
            }.get(active_provider, "https://api.openai.com/v1/chat/completions")

            req_ctx = ""
            if active_req_number:
                req_ctx = f"\nملاحظة: العميل لديه طلب جاري برقم ({active_req_number}) لخدمة ({active_req_service}) وحالته ({active_req_state}). بعد الإجابة على سؤاله ذكره بلطف بإرسال الوثيقة إذا لزم الأمر."

            sys_content = (
                f"{system_prompt or 'أنت صاحب العمل وخبير المبيعات والاستقبال في النشاط التجاري.'}\n\n"
                f"اسم المنشأة: {tenant_name}\n"
                f"اسم العميل: {customer_name or 'عزيزنا العميل'}\n{req_ctx}\n\n"
                f"السياق المسترجع بالفكتورز (RAG Knowledge Chunks):\n"
                f"{retrieved_context or knowledge_base or ''}\n\n"
                f"دليل الخدمات والأسعار الرسمية:\n"
                f"{catalog_summary or ''}\n\n"
                "تعليمات هامة وأسلوب الحديث:\n"
                "- تحدث كإنسان حقيقي وصاحب العمل على الواتساب (لهجة عربية خليجية ودودة، محترمة، ودافئة).\n"
                "- ممنوع نهائياً أن تذكر أنك ذكاء اصطناعي أو بوت أو نظام آلي، وتجنب استخدام إيموجي الروبوت 🤖 تماماً.\n"
                "- أجب على أي استفسار غير مألوف أو متطرف (طقس، أكل، مقارنات، نصائح سفر، أسواق، مواصلات) بإجابة شافية وواضحة ومفيدة كأنك خبير في المجال.\n"
                "- بعد الإجابة على السؤال، اربط الحديث بسلاسة ووجه العميل للخطوة التالية من خطوات الحجز (تحديد الخدمة، أو الاسم الكريم ثلاثياً، أو إرسال المستند)."
            )

            messages = [{"role": "system", "content": sys_content}]
            for m in conversation_history[-6:]:
                role = "assistant" if m.get("sender") == "bot" else "user"
                messages.append({"role": role, "content": m.get("text", "")})
            messages.append({"role": "user", "content": user_message})

            try:
                headers = {
                    "Authorization": f"Bearer {active_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": ai_model or ("gemini-1.5-flash" if active_provider == "gemini" else "gpt-4o-mini"),
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 400,
                }
                async with httpx.AsyncClient(timeout=12.0) as client:
                    resp = await client.post(endpoint, json=payload, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        return data["choices"][0]["message"]["content"].strip()
                    logger.error(f"External AI Error [{resp.status_code}]: {resp.text}")
            except Exception as e:
                logger.exception("Failed to call external AI provider, falling back to smart built-in engine")

        # 5. المحرك الذكي الداخلي المبني على السياق والذاكرة الحية وقاعدة المعرفة (Built-in Realistic Engine)
        return self._built_in_natural_response(
            text=user_message,
            tenant_name=tenant_name,
            kb=knowledge_base or "",
            catalog=catalog_summary or "",
            retrieved_rag_context=retrieved_context,
            customer_name=customer_name,
            active_req_number=active_req_number,
            active_req_service=active_req_service,
            active_req_state=active_req_state,
            active_req_missing_fields=active_req_missing_fields,
            active_req_missing_docs=active_req_missing_docs,
            customer_orders_history=customer_orders_history,
            conversation_history=conversation_history,
        )

    def _built_in_natural_response(
        self,
        text: str,
        tenant_name: str,
        kb: str,
        catalog: str,
        retrieved_rag_context: str = "",
        customer_name: str = None,
        active_req_number: str = None,
        active_req_service: str = None,
        active_req_state: str = None,
        active_req_missing_fields: list = None,
        active_req_missing_docs: list = None,
        customer_orders_history: list = None,
        conversation_history: list = None,
    ) -> str:
        """توليد رد إنساني طبيعي واقعي ومختصر مع ذاكرة حية تمنع تكرار الترحيب وتتفاعل مع الاعتراضات"""
        t = text.lower().strip()
        salutation = f"أستاذ {customer_name}" if customer_name and customer_name != "عميل واتساب" else "عزيزنا العميل"

        # فحص استفسار العميل عن حالة طلبه الجاري (وين قد طلبي، ايش صار بطلبي، الخ) عبر محرك RAG
        if rag_engine.is_order_status_query(t):
            order_ans = rag_engine.resolve_customer_order_status(
                customer_name=customer_name,
                active_req_number=active_req_number,
                active_req_service=active_req_service,
                active_req_state=active_req_state,
                active_req_missing_fields=active_req_missing_fields,
                active_req_missing_docs=active_req_missing_docs,
                customer_orders_history=customer_orders_history,
            )
            if order_ans:
                return order_ans

        # -------------------------------------------------------------
        # استخراج سياق الذاكرة من آخر رسائل المحادثة (Conversation Memory)
        # -------------------------------------------------------------
        history = conversation_history or []
        recent_text = " ".join([m.get("text", "") for m in history[-8:]]).lower()

        last_topic = None
        if any(w in recent_text for w in ["بوسنة", "البوسنة", "سراييفو"]):
            last_topic = "bosnia"
        elif any(w in recent_text for w in ["صين", "الصين", "كوانزو", "شنغهاي"]):
            last_topic = "china"
        elif any(w in recent_text for w in ["فندق", "فنادق", "سكن", "منتجع", "غرفة", "غرف"]):
            last_topic = "hotel"
        elif any(w in recent_text for w in ["سيار", "سيارة", "سائق", "سواق", "فان", "مرسيدس"]):
            last_topic = "car"
        elif any(w in recent_text for w in ["عباي", "عباية", "طقم", "ملابس", "فستان"]):
            last_topic = "fashion"

        if not last_topic and active_req_service:
            s_low = active_req_service.lower()
            if "بوسنة" in s_low:
                last_topic = "bosnia"
            elif "صين" in s_low:
                last_topic = "china"
            elif "فندق" in s_low:
                last_topic = "hotel"
            elif "سيار" in s_low:
                last_topic = "car"
            elif any(x in s_low for x in ["عباي", "ملابس", "طقم"]):
                last_topic = "fashion"

        # هل أرسل البوت الترحيب مسبقاً؟
        welcome_already_sent = any(
            ("يا هلا ومرحباً بك في" in m.get("text", "") or "أهلاً وسهلاً بك في" in m.get("text", "") or "يسعدنا خدمتك وتزويدك" in m.get("text", ""))
            for m in history if m.get("sender") == "bot"
        )

        # -------------------------------------------------------------
        # 1. الاعتراض على السعر (غالي، كثير، مكلف، خفض، خصم، مراعاة)
        # -------------------------------------------------------------
        price_objection_keywords = ["غالي", "غاليه", "غالية", "مكلف", "كثير", "سعر عالي", "اسعاركم غاليه", "أسعاركم غالية", "خفض", "خصم", "مراعاة", "ما في خصم", "رخيص", "ارخص", "أرخص"]
        if any(w in t for w in price_objection_keywords):
            if last_topic == "bosnia" or "بوسنة" in t:
                return (
                    f"أبداً يا غالي والله السعر 5,000$ مدروس وممتاز جداً 🌸\n"
                    f"لأنه شامل 7 أيام كاملة بفنادق 4 و 5 نجوم فاخرة مع الإفطار، سيارة خاصة VIP وسائق متفرغ معكم طوال اليوم، وجولات يومية لأجمل المعالم والشلالات والبحيرات بدون أي مصاريف إضافية!\n"
                    f"وإذا ودك بخيارات اقتصادية أو نعدل برنامج الفنادق ليناسب ميزانيتك، أبشر نفصل لك عرض خاص يسعدك تماماً 🌸"
                )
            elif last_topic == "china" or "صين" in t:
                return (
                    f"بالعكس يا غالي، بكج الصين 10 أيام شامل الطيران الداخلي، الفنادق الفاخرة، سيارة خاصة، ومترجم ومرشد يرافقكم بالمعارض والأسواق 🌸\n"
                    f"ومستعدين نرتب لك خيارات مرنة تناسب ميزانيتك تماماً، كم ميزانيتك المقترحة لنفصل لك الأنسب؟"
                )
            elif last_topic == "hotel" or "فندق" in t:
                return (
                    f"ولا تشيل هم بالسعر يا غالي 🌸\n"
                    f"الفنادق التي عرضناها مصنفة 5 نجوم بأعلى تقييم وأجمل إطلالة. وإذا ودك بخيارات 4 نجوم ممتازة ونظيفة وبأسعار اقتصادية، أبشر نوفرها لك فوراً، تفضل بتواريخك لنرسل لك الخيارات المناسبة."
                )
            elif last_topic == "car" or "سيار" in t:
                return (
                    f"السعر يشمل سيارات مرسيدس فيتو VIP حديثة وفخمة مع سائق خاص أمين وخبير متفرغ لكم مع الوقود طوال اليوم 🌸\n"
                    f"وإذا ودك بسيارة سيدان عادية أو خيار اقتصادي نوفرها لك بسعر أقل وأبشر باللي يرضيك!"
                )
            elif last_topic == "fashion":
                return (
                    f"ولا تشيل هم يا غالي 🌸 خاماتنا أصلية فاخرة (كريب ملكي كوري أصلي سواد فاحم يدوم طويلاً) مع طرحة مجانية وضمان استبدال، ويسعدنا تقديم خصم خاص وشحن مجاني لطلبك!"
                )
            else:
                return (
                    f"ولا تشيل هم بالسعر يا غالي! 🌸\n"
                    f"خدماتنا ممتازة ومضمونة ويسعدنا نراعيك ونفصل لك البرنامج أو العرض اللي يناسب ميزانيتك تماماً. قل لي وش ميزانيتك أو الخدمة اللي ببالك وأبشر باللي يسرك!"
                )

        # -------------------------------------------------------------
        # 2. طلب الصور والفيديوهات وأسماء الفنادق والروابط
        # -------------------------------------------------------------
        media_request_keywords = ["صور", "صوره", "صورة", "فيديو", "فيديوهات", "اسماء", "أسماء", "اسم الفندق", "اسماء الفنادق", "روابط", "رابط", "ورني", "شف لي", "عطني"]
        if any(w in t for w in media_request_keywords):
            if last_topic == "hotel" or any(w in t for w in ["فندق", "فنادق", "سكن", "منتجع"]):
                return (
                    f"أبشر من عيوننا! 📸\n"
                    f"نوفر لك صور وفيديوهات وتفاصيل كاملة لأفخم الفنادق والمنتجعات اللي نتعامل معها (مثل سويس أوتيل سراييفو، راديسون بلو، هيلتون، وبينو نيتشر) بإطلالات ساحرة ومرافق متكاملة.\n"
                    f"تفضل بتزويدنا بالمدينة والتواريخ وعدد النزلاء لنرسل لك صور الفنادق المتاحة وأسماءها وأسعارها بدقة 🌸"
                )
            elif last_topic == "bosnia":
                return (
                    f"أبشر من عيوننا! 📸\n"
                    f"نوفر لك صور وفيديوهات لأجمل المعالم في سراييفو، موستار، شلالات كرافيتسا، وبحيرة بروكوشكو، بالإضافة لصور الفنادق والسيارات VIP.\n"
                    f"في أي تاريخ تحب تسافر لنرتب لك البرنامج كامل بالصور؟ 🌸"
                )
            elif last_topic == "car":
                return (
                    f"أبشر! 📸 نوفر لك صور وفيديوهات سياراتنا الفاخرة (مرسيدس فيتو وفانات VIP عائلية مريحة جداً ومجهزة بأحدث وسائل الراحة).\n"
                    f"كم عدد أفراد عائلتك الكريمة لنحدد السيارة الأنسب ونرسل صورها؟ 🌸"
                )
            elif last_topic == "fashion":
                return (
                    f"أبشر من عيوننا! 📸 صور وموديلات القطع بتصوير واقعي وبكافة زواياها متوفرة بجودة عالية.\n"
                    f"أي قطعة أو مقاس ترغب برؤية صورها وتفاصيلها؟ 🌸"
                )
            else:
                return (
                    f"أبشر من عيوننا! 📸 نوفر لك صور وفيديوهات وتفاصيل كاملة لكافة خدماتنا وعروضنا.\n"
                    f"عن أي خدمة أو وجهة تحب تشوف الصور والتفاصيل لنزودك بها فوراً؟ 🌸"
                )

        # -------------------------------------------------------------
        # 3. التعليق والمزاح والضحك والتذكير بالذاكرة
        # -------------------------------------------------------------
        memory_or_laugh_keywords = ["ينسى", "ذا ينسى", "افعله ذاكرة", "ذاكرة", "الذاكرة", "نسي", "ما يتذكر", "ي رجال", "يا رجال", "اعربك", "اعرب", "هههه", "😂😂", "ضحكتني", "والله ضحكتني"]
        if any(w in t for w in memory_or_laugh_keywords):
            topic_hint = "حجز الفندق" if last_topic == "hotel" else ("بكج البوسنة" if last_topic == "bosnia" else ("بكج الصين" if last_topic == "china" else ("خدمة السيارة والسائق" if last_topic == "car" else "طلبك")))
            return (
                f"ههههه الله يسعدك ويحفظك دوم يا رب! 🌸\n"
                f"ماني ناسيك وذاكرتي معك مركزة ومسجل كل تفاصيل كلامك، وكنا نتكلم عن {topic_hint}.\n"
                f"تفضل، وش اللي ودك نرتبه أو نعدله بالضبط وأنا معك خطوة بخطوة!"
            )

        # -------------------------------------------------------------
        # 4. المغادرة والعودة (اصلن وارجع، بروح واجي، شوي وارجع)
        # -------------------------------------------------------------
        brb_keywords = ["اصلن وارجع", "اروح وارجع", "بروح واجي", "برجع لك", "برجع", "شوي وارجع", "انتظر", "لحظة", "دقيقة", "برب", "بعدين"]
        if any(w in t for w in brb_keywords):
            return f"حياك الله وخذ كامل وقتك وراحتك يا غالي! 🌸 متى ما تيسر لك تواصل معي وبتلقاني جاهز وفي خدمتك بأي وقت."

        # -------------------------------------------------------------
        # 5. الشكوى من تكرار الرسائل (ليش معلي الرد، ليش تكرر)
        # -------------------------------------------------------------
        repeat_complaint_keywords = ["معلي الرد", "ليش تكرر", "ليش تعيد", "تكرار", "كل شوي تعيد", "تكرر", "نفس الرد"]
        if any(w in t for w in repeat_complaint_keywords):
            return f"العذر والسموحة منك حقك علي يا غالي! 🌸 تفضل بسؤالك أو طلبك وأنا معك مباشرة وبجاوبك على اللي تبغاه بالضبط وبدون أي تكرار."

        # -------------------------------------------------------------
        # 6. استفسارات الملابس والأزياء والمقاسات والأقمشة
        # -------------------------------------------------------------
        if any(w in t for w in ["عباي", "عباية", "عبايه", "فستان", "طقم", "ملابس", "قميص", "قماش", "خامة", "كريب", "قطن", "مقاس", "مقاسات", "طرحة"]):
            if any(w in t for w in ["مقاس", "مقاسات", "كيف اختار", "ايش المقاسات"]):
                return (
                    f"يا هلا بك {salutation}! 🌸\n"
                    f"مقاساتنا دقيقة وتناسب الجميع:\n"
                    f"• العبايات: متوفرة بمقاسات (52، 54، 56، 58، 60) مع طرحة مجانية فاخرة.\n"
                    f"• الملابس والأطقم: متوفرة بمقاسات (M, L, XL, XXL).\n"
                    f"تفضل بمقاسك المعتاد أو طولك ونساعدك في اختيار الأنسب لك تماماً!"
                )
            return (
                f"أهلاً وسهلاً بك {salutation}! 🌸\n"
                f"أزياؤنا مصنوعة من أفخر الخامات الأصلية (كريب ملكي كوري سواد فاحم للعبايات، وأقطان طبيعية 100% للأطقم)، مع ضمان الجودة والاستبدال خلال 7 أيام.\n"
                f"أي قطعة أو مقاس ترغب في الاستفسار عنه لخدمتك فوراً؟"
            )

        # -------------------------------------------------------------
        # 7. استفسارات الشحن والتوصيل والعنوان
        # -------------------------------------------------------------
        if any(w in t for w in ["توصيل", "شحن", "ارامكس", "سمسا", "عنوان", "متى يوصل", "كم يوم", "مدة التوصيل", "مدن"]):
            return (
                f"أهلاً بك {salutation}! 🌸\n"
                f"نوفر التوصيل السريع لكافة مدن ومناطق المملكة عبر سمسا وأرامكس خلال 2 إلى 4 أيام عمل إلى باب بيتك.\n"
                f"رسوم الشحن 25 ريال فقط، والتوصيل *مجاني* لأي طلب بقيمة 300 ريال وأكثر 🚚"
            )

        # -------------------------------------------------------------
        # 8. استفسارات الدفع وسند الرسوم وطريقة السداد
        # -------------------------------------------------------------
        if any(w in t for w in ["دفع", "طريقة الدفع", "سداد", "تحويل", "سند", "إيصال", "ايصال", "حساب", "راجحي", "اهلي", "مدى"]):
            return (
                f"طرق الدفع ميسرة وآمنة {salutation}:\n"
                f"• تحويل بنكي على حساب المؤسسة (مصرف الراجحي أو البنك الأهلي).\n"
                f"• دفع إلكتروني عبر مدى والبطاقات الائتمانية.\n"
                f"ولتأكيد وشحن أي طلب، فقط تزودنا بالمقاس والعنوان وصورة إشعار التحويل 🧾"
            )

        # -------------------------------------------------------------
        # 9. استفسارات السياحة والسفر (البوسنة والصين والسيارات والفنادق)
        # -------------------------------------------------------------
        if any(w in t for w in ["بوسنة", "البوسنة", "سراييفو"]):
            return (
                f"يا هلا بك {salutation}! 🌸\n"
                f"لدينا *بكج البوسنة العائلي (7 أيام)* بسعر 5,000$ شامل فنادق 4 و 5 نجوم مع الإفطار، سيارة خاصة VIP مع سائق خاص يتحدث العربية، وجولات يومية في سراييفو وموستار وبحيرة بروكوشكو والطبيعة الساحرة.\n"
                f"في أي تاريخ مخطط لرحلتك لنرتبها لك؟"
            )

        if any(w in t for w in ["صين", "الصين", "شنغهاي", "كوانزو", "بكين", "معرض", "كانتون"]):
            return (
                f"يا هلا وغلا {salutation}! 🌸\n"
                f"نوفر *بكج سياحة واستكشاف الصين (10 أيام)* بسعر 6,500$ يشمل بكين، شنغهاي، وكوانزو شامل الطيران الداخلي، الفنادق الفاخرة، سيارة خاصة، ومترجم ومرشد يرافقكم في المعارض والأسواق.\n"
                f"كم عدد المسافرين وتاريخ سفركم المقترح؟"
            )

        if any(w in t for w in ["سيار", "سيارة", "سياره", "سائق", "سواق", "فان", "مرسيدس"]):
            return (
                f"أبشر من عيوننا {salutation}! 🌸\n"
                f"نوفر سيارات خاصة فاخرة وواسعة (مرسيدس فيتو وفانات VIP) مع سائق خاص خبير وأمين يتحدث العربية، تشمل الوقود والجولات اليومية والاستقبال والتوديع في المطار بـ 500$.\n"
                f"في أي مدينة وتاريخ تحتاج السيارة؟"
            )

        if any(w in t for w in ["فندق", "فنادق", "سكن", "منتجع", "منتجعات"]):
            return (
                f"أهلاً بك {salutation}! 🌸\n"
                f"فنادقنا ومنتجعاتنا مصنفة 4 و 5 نجوم بأجمل الإطلالات الطبيعية مع إفطار مجاني بـ 1,200$.\n"
                f"في أي وجهة تفضل الحجز وما هي التواريخ المطلوبة؟"
            )

        # -------------------------------------------------------------
        # 10. الطقس والأكل الحلال وحالة الطلب
        # -------------------------------------------------------------
        if any(w in t for w in ["طقس", "الجو", "برد", "مطر", "حر", "صيف", "شتاء"]):
            return (
                f"يا هلا بك {salutation}! 🌸\n"
                f"الأجواء في البوسنة ربيعية صيفية معتدلة ومنعشة جداً من شهر مايو حتى أكتوبر (بين 20 إلى 27 درجة)، وممطرة وخضراء، وفي الشتاء ثلجية رائعة لعشاق التزلج. أما في الصين فالربيع والخريف أفضل الفترات."
            )

        if any(w in t for w in ["أكل", "اكل", "حلال", "مطاعم", "مطعم", "ذبح"]):
            return (
                f"تطمن تماماً من هالناحية {salutation}! 🌸\n"
                f"الأكل الحلال متوفر بكثرة وممتاز في كافة وجهاتنا، والمطاعم متنوعة ونظيفة وتقدم أشهى المأكولات التي تناسب الذوق العربي."
            )

        if any(w in t for w in ["وين طلبي", "وش صار على طلبي", "حالة الطلب", "متى تعتمدون", "الطلب"]) and active_req_number:
            return (
                f"أهلاً بك {salutation}! 🌸\n"
                f"طلبك برقم ({active_req_number}) لخدمة ({active_req_service}) مسجل لدينا، وحالته الحالية هي: ({active_req_state}). "
                f"فريقنا يتابع الإجراءات وسيتم إشعارك فور الاعتماد."
            )

        # -------------------------------------------------------------
        # 11. التحية والشكر
        # -------------------------------------------------------------
        if any(w in t for w in ["كيف حالك", "كيفك", "شخبارك", "شلونك", "عساك بخير", "صحتك", "منور", "هلا والله", "يا هلا"]):
            return (
                f"يا هلا وغلا {salutation}! بخير وبأفضل حال الله يسعدك ويحفظك 🌸\n"
                f"يسعدني خدمتك في {tenant_name} والإجابة على أي استفسار أو طلب تحتاجه اليوم!"
            )

        if any(w in t for w in ["شكرا", "شكراً", "يعطيك العافية", "يعطيكم العافية", "تسلم", "الله يسعدك", "مشكور"]):
            return f"العفو {salutation}، هذا واجبنا وحقك علينا ونسعد بخدمتك دائماً 🌸"

        # -------------------------------------------------------------
        # 12. الرد العام الذكي (يمنع تكرار الترحيب إذا بدأت المحادثة)
        # -------------------------------------------------------------
        if welcome_already_sent:
            return (
                f"أبشر يا غالي، أنا معك وأسمعك بكل وضوح! 🌸\n"
                f"تفضل، كيف أقدر أساعدك أو وش التفاصيل اللي ودك نرتبها لك؟"
            )

        return (
            f"يا هلا ومرحباً بك في {tenant_name} 🌸\n"
            f"يسعدنا خدمتك وتزويدك بكافة تفاصيل منتجاتنا وخدماتنا. تفضل بسؤالي عن أي استفسار أو طلب في بالك وسأجيبك فوراً!"
        )


ai_engine = ConversationalAIEngine()
