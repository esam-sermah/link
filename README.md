# LINK SaaS Platform & WhatsApp AI Automation (Odoo 20)
منظومة التجارة والمبيعات الذكية متعددة المستأجرين مع أتمتة الواتساب عبر الذكاء الاصطناعي و Odoo 20

---

## 🌟 نظرة عامة (Overview)
منظومة برمجية متكاملة تدمج بين قوة **نظام إدارة الموارد Odoo 20**، وسرعة **منصة FastAPI Middleware**، ومحرك **البحث الدلالي بالفكتورز والـ RAG**، وبوابة **OpenWA الرسمية للواتساب**، لتمكين الشركات والتجار من تقديم تجربة بيع وحجوزات آلية ذكية وواقعية 100% عبر الواتساب على مدار الساعة.

---

## 📁 هيكلية المستودع (Repository Structure)

```text
link/
├── custom_addons/
│   └── link_core/               # موديول Odoo 20 الكامل (المستأجرين، الكتالوج، الطلبات، الـ APIs)
├── middleware/
│   ├── ai_agent.py              # محرك المحادثة البشري والذاكرة اللحظية
│   ├── rag_engine.py            # محرك الفكتورز والبحث الدلالي وتتبع حالة الطلبات ("وين قد طلبي")
│   ├── openwa_client.py         # عميل التواصل مع بوابة واتساب OpenWA
│   ├── odoo_client.py           # عميل التواصل عبر JSON-RPC مع Odoo 20
│   ├── main.py                  # خادم FastAPI ونقاط اتصال Webhook
│   └── static/                  # لوحة التحكم التفاعلية للويب (HTML5, Modern CSS, JS)
├── openwa/                      # الكود المصدري الكامل لبوابة OpenWA Gateway مع Dockerfile
├── scripts/
│   ├── start_all.sh             # تشغيل كافة السيرفرات بضغطة زر
│   └── stop_all.sh              # إيقاف المنظومة
├── docs/
│   ├── DEVELOPER_SETUP_GUIDE.md # دليل التشغيل الفني والتثبيت والربط من الصفر للمطورين
│   └── MERCHANT_USER_MANUAL.md  # دليل المستخدم والتاجر واستخدام المنصة
├── DEVELOPER_SETUP_GUIDE.md     # نسخة مباشرة من دليل المطورين
├── MERCHANT_USER_MANUAL.md      # نسخة مباشرة من دليل المستخدم
├── docker-compose.yml           # تشغيل المنظومة الكاملة عبر Docker Compose
├── odoo.conf.example            # ملف إعدادات Odoo 20
└── requirements.txt             # متطلبات بايثون الأساسية
```

---

## 🚀 البدء السريع (Quick Start)

### 1. تثبيت المتطلبات:
```bash
pip install -r requirements.txt
```

### 2. تشغيل كافة الخدمات:
```bash
bash scripts/start_all.sh
```

### 3. الروابط المباشرة:
* **لوحة تحكم المنصة:** `http://localhost:8000/`
* **نظام Odoo 20 لإدارة المبيعات:** `http://localhost:8020/`
* **بوابة واتساب والتوثيق:** `http://localhost:2785/api-docs`
* **دليل التثبيت والربط الفني:** راجع ملف `DEVELOPER_SETUP_GUIDE.md`
* **دليل التاجر والمستخدم:** راجع ملف `MERCHANT_USER_MANUAL.md`
