#!/usr/bin/env bash
# ==============================================================================
# سكربت إيقاف منظومة LINK SaaS والخدمات المرتبطة
# ==============================================================================

echo "🛑 إيقاف منظومة LINK SaaS..."

echo "إيقاف Middleware..."
pkill -f "uvicorn middleware.main:app" || true

echo "إيقاف Odoo 20..."
pkill -f "odoo-bin -c" || true

echo "إيقاف بوابة OpenWA (اختياري، اتركها تعمل لحفظ جلسة الواتساب)..."
# docker stop openwa-api || true

echo "✅ تم إيقاف الخدمات بنجاح."
