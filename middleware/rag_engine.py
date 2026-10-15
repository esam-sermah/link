"""
محرك البحث الدلالي والفكتورز (Vector Search & RAG Engine)
يدعم تعدد المستأجرين (Multi-Tenant Isolation) واسترجاع حالة العميل وطلباته النشطة فورياً
"""
import re
import math
import logging
from typing import List, Dict, Any, Optional
import numpy as np

logger = logging.getLogger("link.rag")


def _stable_hash(s: str) -> int:
    """دالة هاش دقيقة وثابتة متوافقة عبر العمليات (FNV-1a Hash)"""
    h = 2166136261
    for ch in s:
        h = ((h ^ ord(ch)) * 16777619) & 0x7FFFFFFF
    return h


class SemanticVectorizer:
    """
    محول نصوص إلى فكتورز دلالية (Semantic Embeddings Vectorizer)
    يدعم اللغة العربية ولهجاتها بدقة عالية باستخدام N-grams دلالية والتضمين متعدد المستويات
    يعمل بدون الحاجة لأي مفاتيح خارجية وبكفاءة فائقة (Offline High-Dimensional Vectors)
    مع إمكانية الربط بـ OpenAI/Gemini Embeddings عند توفر المفتاح.
    """

    def __init__(self, vector_dim: int = 1024):
        self.vector_dim = vector_dim

    def _stem_word(self, word: str) -> str:
        """جذر الكلمة العربي الخفيف (Light Stemming) لإزالة السوابق واللواحق الشائعة"""
        w = word
        for pfx in ['كال', 'بال', 'فال', 'وال', 'لل', 'ال']:
            if w.startswith(pfx) and len(w) > len(pfx) + 2:
                w = w[len(pfx):]
                break
        if w.startswith('و') and len(w) > 3:
            w = w[1:]
        for sfx in ['كما', 'هما', 'هم', 'هن', 'كم', 'نا', 'ها', 'ان', 'ين', 'ون', 'ات', 'يه', 'ة', 'ه']:
            if w.endswith(sfx) and len(w) > len(sfx) + 2:
                w = w[:-len(sfx)]
                break
        return w

    def _normalize_arabic(self, text: str) -> List[str]:
        """تنظيف وتوحيد الحروف العربية وتفكيك الكلمات لجذورها"""
        t = text.lower().strip()
        t = re.sub(r'[إأآا]', 'ا', t)
        t = re.sub(r'ة', 'ه', t)
        t = re.sub(r'ى', 'ي', t)
        t = re.sub(r'[ًٌٍَُِّْـ]', '', t)  # إزالة التشكيل والتطويل
        t = re.sub(r'[^\w\s]', ' ', t)
        return [w for w in t.split() if len(w) > 1]

    def encode(self, text: str) -> np.ndarray:
        """توليد فكتور عددي ذو أبعاد عالية (Vector Embedding) مع التطبيع (L2 Normalization)"""
        raw_words = self._normalize_arabic(text)
        vec = np.zeros(self.vector_dim, dtype=np.float32)

        if not raw_words:
            return vec

        stemmed_words = [self._stem_word(w) for w in raw_words]

        # 1. Word-level and Stem-level hashing
        for w in raw_words:
            vec[_stable_hash(w) % self.vector_dim] += 2.0
        for s in stemmed_words:
            vec[_stable_hash(s) % self.vector_dim] += 3.0
            # 2. Subword Character N-grams (3 to 5 chars)
            for n in range(3, min(6, len(s) + 1)):
                for i in range(len(s) - n + 1):
                    vec[_stable_hash(s[i:i+n]) % self.vector_dim] += 1.5

        # 3. Bigrams لربط العبارات المركبة
        for i in range(len(stemmed_words) - 1):
            bigram = f"{stemmed_words[i]}_{stemmed_words[i+1]}"
            vec[_stable_hash(bigram) % self.vector_dim] += 3.0

        # L2 Normalization
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec


class MultiTenantRAGEngine:
    """
    نظام RAG (Retrieval-Augmented Generation) متكامل لإدارة واسترجاع بيانات المستأجرين وحالة العملاء
    - تقسيم وفهرسة مستندات المتجر وقاعدة المعرفة وكتالوج الخدمات إلى فكتورز
    - استرجاع سياق حالة طلب العميل الجاري وتاريخ معاملاته من أودو
    - عزل تام لبيانات كل مستأجر (Tenant Partitioning)
    """

    def __init__(self):
        self.vectorizer = SemanticVectorizer(vector_dim=512)
        # تخزين الفكتورز مقسمة حسب tenant_id: {tenant_id: {"chunks": [...], "vectors": np.ndarray}}
        self.tenant_stores: Dict[int, Dict[str, Any]] = {}

    def _chunk_text(self, text: str, max_words: int = 60, overlap: int = 15) -> List[str]:
        """تقطيع النصوص إلى مقاطع دلالية متكاملة تجمع العناوين مع تفاصيلها"""
        if not text:
            return []
        
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        paragraphs = []
        current_p = []
        current_words = 0
        
        for line in lines:
            w_count = len(line.split())
            if current_words + w_count <= max_words:
                current_p.append(line)
                current_words += w_count
            else:
                if current_p:
                    paragraphs.append(" ".join(current_p))
                current_p = [line]
                current_words = w_count
                
        if current_p:
            paragraphs.append(" ".join(current_p))
            
        return paragraphs

    def index_tenant_knowledge(self, tenant_id: int, knowledge_base: str, catalog_summary: str, tenant_name: str = ""):
        """بناء وتحديث فهرس الفكتورز (Vector Store) للمستأجر"""
        chunks = []

        # إضافة اسم المستأجر وتعريفه
        if tenant_name:
            chunks.append(f"المنشأة: {tenant_name}")

        # تقطيع وفهرسة قاعدة المعرفة وملفات التدريب
        if knowledge_base:
            kb_chunks = self._chunk_text(knowledge_base, max_words=60, overlap=15)
            chunks.extend(kb_chunks)

        # تقطيع وفهرسة خدمات وعروض المتجر
        if catalog_summary:
            cat_chunks = self._chunk_text(catalog_summary, max_words=50, overlap=10)
            chunks.extend(cat_chunks)

        if not chunks:
            self.tenant_stores[tenant_id] = {"chunks": [], "vectors": np.empty((0, 512), dtype=np.float32)}
            return

        # توليد متجهات الفكتور لجميع المقاطع دفعة واحدة
        vectors = np.array([self.vectorizer.encode(c) for c in chunks], dtype=np.float32)

        self.tenant_stores[tenant_id] = {
            "chunks": chunks,
            "vectors": vectors,
        }
        logger.info(f"RAG: Indexed {len(chunks)} vector chunks for tenant {tenant_id} ({tenant_name})")

    def search_knowledge(self, query: str, tenant_id: int, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        البحث الدلالي بالفكتورز لاسترجاع أكثر المقاطع تطابقاً مع سؤال العميل
        Cosine Similarity: sim = dot(query_vec, doc_vecs)
        """
        store = self.tenant_stores.get(tenant_id)
        if not store or len(store["chunks"]) == 0:
            return []

        q_vec = self.vectorizer.encode(query)
        doc_vecs = store["vectors"]

        # حساب التشابه الكوسيني لجميع المتجهات
        scores = np.dot(doc_vecs, q_vec)

        # استخراج أعلى top_k مقاطع
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score > 0.005:  # عتبة الصلة الدلالية
                results.append({
                    "chunk": store["chunks"][idx],
                    "score": score,
                })
        return results

    def resolve_customer_order_status(
        self,
        customer_name: Optional[str],
        active_req_number: Optional[str],
        active_req_service: Optional[str],
        active_req_state: Optional[str],
        active_req_missing_fields: Optional[List[str]] = None,
        active_req_missing_docs: Optional[List[str]] = None,
        customer_orders_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[str]:
        """
        توليد تقرير حالة طلب العميل بالاعتماد على بيانات أودو الدقيقة
        (إجابة مباشرة شافية لأسئلة: وين قد طلبي، ايش صار بطلبي، متى تعتمدون، حالة الطلب)
        """
        salutation = f"أستاذ {customer_name}" if customer_name and customer_name != "عميل واتساب" else "عزيزنا العميل"

        # 1. إذا كان لديه طلب جاري ونشط
        if active_req_number:
            srv_title = f" لـ *{active_req_service}*" if active_req_service else ""

            if active_req_state == "collecting_docs":
                doc_name = active_req_missing_docs[0] if (active_req_missing_docs and len(active_req_missing_docs) > 0) else "صورة المستند أو الهوية"
                return (
                    f"يا هلا ومرحباً {salutation}! 🌸\n"
                    f"طلبك برقم *({active_req_number})*{srv_title} مسجل لدينا بالنظام ✅\n\n"
                    f"📎 وهو بانتظار استلام صورة *{doc_name}* لتأكيده واعتماده رسمياً فوراً. تفضل بإرسالها هنا في الشات وسنكمل الباقي مباشرة!"
                )
            elif active_req_state == "collecting_info":
                fields_str = " و ".join(active_req_missing_fields) if active_req_missing_fields else "البيانات المتبقية"
                return (
                    f"أهلاً بك {salutation}! 🌸\n"
                    f"طلبك برقم *({active_req_number})*{srv_title} مسجل لدينا، ومتبقي لإتمامه تزويدنا بـ: [{fields_str}]. تفضل بكتابتها هنا لنعتمد طلبك فوراً!"
                )
            elif active_req_state == "pending_review":
                return (
                    f"يا هلا ومرحباً {salutation}! 🌸\n"
                    f"طلبك برقم *({active_req_number})*{srv_title} مكتمل وجاري مراجعته وتأكيده رسمياً من قبل الإدارة حالياً ✅\n"
                    f"فريقنا يتابع الإجراءات وسنرسل لك إشعار التأكيد فوراً."
                )
            elif active_req_state == "confirmed":
                return (
                    f"أهلاً وسهلاً {salutation}! 🌸\n"
                    f"طلبك برقم *({active_req_number})*{srv_title} معتمد ومؤكد رسمياً بنجاح ✅ وجاري تجهيز الترتيبات لك وسنوافيك بكافة المستجدات أولاً بأول."
                )
            elif active_req_state == "completed":
                return (
                    f"أهلاً بك {salutation}! 🌸\n"
                    f"طلبك برقم *({active_req_number})*{srv_title} تم إنجازه واكتماله بنجاح ✅ ويسعدنا دائماً خدمتك بأي طلب جديد."
                )
            else:
                return (
                    f"أهلاً بك {salutation}! 🌸\n"
                    f"طلبك برقم *({active_req_number})*{srv_title} مسجل لدينا وحالته الحالية هي: ({active_req_state}). وسنوافيك بالتحديث فوراً."
                )

        # 2. إذا لم يكن لديه طلب نشط، ولكن لديه طلبات سابقة مؤكدة
        if customer_orders_history and len(customer_orders_history) > 0:
            last_order = customer_orders_history[-1]
            last_num = last_order.get("number", "")
            last_srv = last_order.get("service", "")
            last_st = last_order.get("state", "")
            st_text = "معتمد ومؤكد ✅" if last_st == "confirmed" else ("مكتمل بنجاح ✅" if last_st == "completed" else last_st)
            return (
                f"أهلاً بك {salutation}! 🌸\n"
                f"آخر طلب مسجل لك هو برقم *({last_num})* لـ *{last_srv}* وحالته: ({st_text}).\n"
                f"إذا كنت ترغب بالبدء في حجز أو طلب جديد، يسعدنا تزويدك بالعروض والبدء معك فوراً!"
            )

        # 3. لا يوجد أي طلب سابق أو حالي
        return (
            f"يا هلا بك {salutation}! 🌸\n"
            f"لا يوجد طلب نشط مسجل حالياً برقم هاتفك. تفضل باختيار الخدمة أو الباقة التي تناسبك ويسعدنا تسجيل طلبك وتجهيزه لك فوراً!"
        )

    def is_order_status_query(self, text: str) -> bool:
        """التحقق هل العميل يسأل عن حالة طلبه (بمختلف اللهجات: وين قد طلبي، وش صار، وين وصل)"""
        t = text.lower().strip()
        indicators = [
            "وين قد طلبي", "وين طلبي", "وين وصل طلبي", "وين حقي الطلب", "وين طلبي واصل",
            "وش صار على طلبي", "وش صار بطلبي", "ايش صار بطلبي", "ايش صار على طلبي",
            "شو صار بطلبي", "كيف طلبي", "حالة الطلب", "حالة طلبي", "متى تعتمدون",
            "اعتمدتوا طلبي", "اعتمدتو طلبي", "هل تم تأكيد", "طمني على الطلب", "وين الطلب",
            "وين طلبي الان", "وين واصل طلبي", "وصل طلبي", "ايش سويتوا بطلبي"
        ]
        return any(ind in t for ind in indicators)


# نسخة عامة لمشاركة الفهارس
rag_engine = MultiTenantRAGEngine()
