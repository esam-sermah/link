#!/usr/bin/env bash
# ==============================================================================
# سكربت تشغيل منظومة LINK SaaS المتكاملة (Odoo 20 + Middleware + WhatsApp Gateway)
# ==============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT_ODOO_DIR="$(cd "$PROJECT_DIR/.." && pwd)"

echo "=================================================="
echo "🚀 بدء تشغيل منظومة LINK SaaS والربط مع الواتساب"
echo "=================================================="

# 1. التحقق من حاوية OpenWA أو تشغيلها عبر Docker
echo "1️⃣ فحص بوابة الواتساب (OpenWA Docker Gateway)..."
if ! docker ps --filter "name=openwa-api" --filter "status=running" | grep -q openwa-api; then
    echo "تشغيل حاوية openwa-api..."
    docker start openwa-api || (cd "$PROJECT_DIR/whatsapp_gateway" && docker compose up -d)
    echo "✅ تم تشغيل بوابة واتساب بنجاح."
else
    echo "✅ بوابة واتساب تعمل بالفعل."
fi

# 2. تشغيل Odoo 20 في الخلفية إذا لم يكن يعمل
echo "2️⃣ فحص سيرفر أودو Odoo 20..."
if ! curl -s http://127.0.0.1:8020/web/login > /dev/null; then
    echo "بدء تشغيل سيرفر Odoo 20 على المنفذ 8020..."
    nohup /home/esam/PycharmProjects/odoo20/.venv/bin/python3 "$ROOT_ODOO_DIR/odoo-bin" -c "$ROOT_ODOO_DIR/odoo.conf" -d odoo20 > "$PROJECT_DIR/odoo.log" 2>&1 &
    echo "انتظار إقلاع أودو..."
    sleep 3
    echo "✅ تم إطلاق سيرفر Odoo 20."
else
    echo "✅ سيرفر Odoo 20 يعمل بالفعل."
fi

# 3. تشغيل منصة Middleware (FastAPI + RAG + Web UI) في الخلفية
echo "3️⃣ فحص سيرفر المنصة والـ Middleware (المنفذ 8000)..."
if ! curl -s http://127.0.0.1:8000/api/health > /dev/null; then
    echo "بدء تشغيل Middleware Platform..."
    nohup /home/esam/PycharmProjects/odoo20/.venv/bin/uvicorn middleware.main:app --host 0.0.0.0 --port 8000 > "$PROJECT_DIR/middleware.log" 2>&1 &
    sleep 2
    echo "✅ تم تشغيل المنصة بنجاح."
else
    echo "✅ منصة Middleware تعمل بالفعل."
fi

echo ""
echo "=================================================="
echo "🎉 اكتمل التشغيل بنجاح! الروابط النشطة:"
echo "• واجهة لوحة تحكم المنصة والدردشة: http://localhost:8000/"
echo "• نظام إدارة المبيعات Odoo 20:       http://localhost:8020/"
echo "• بوابة واتساب والـ Swagger Docs:   http://localhost:2785/api-docs"
echo "=================================================="
