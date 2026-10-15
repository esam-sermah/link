import httpx
from .config import ODOO_URL, DEFAULT_TENANT_ID


class OdooClient:
    def __init__(self, base_url: str = ODOO_URL):
        self.base_url = base_url

    async def _post_jsonrpc(self, endpoint: str, params: dict):
        url = f"{self.base_url}{endpoint}"
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": params,
            "id": None,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
            if "error" in data:
                return {"error": data["error"].get("data", {}).get("message", "Odoo RPC Error")}
            return data.get("result", {})

    async def route_message(self, sender_phone: str, text: str, selected_button: str = None, tenant_id: int = None, customer_name: str = None, session_id: str = None, whatsapp_chat_id: str = None, has_prior_messages: bool = False):
        """توجيه الرسالة في Odoo لفحص الأزرار والترحيب والردود التلقائية والذكاء الاصطناعي"""
        params = {
            "sender_phone": sender_phone,
            "customer_name": customer_name,
            "text": text,
            "selected_button": selected_button,
            "has_prior_messages": has_prior_messages,
        }
        if whatsapp_chat_id:
            params["whatsapp_chat_id"] = whatsapp_chat_id
        if tenant_id:
            params["tenant_id"] = tenant_id
        if session_id:
            params["session_id"] = session_id
        return await self._post_jsonrpc("/api/link/v1/message/route", params)

    async def check_availability(self, service_id: int, date_from: str = None, date_to: str = None, quantity: int = 1, tenant_id: int = DEFAULT_TENANT_ID):
        """فحص التوفر الحتمي لخدمة"""
        params = {
            "tenant_id": tenant_id,
            "service_id": service_id,
            "date_from": date_from,
            "date_to": date_to,
            "quantity": quantity,
        }
        return await self._post_jsonrpc("/api/link/v1/availability", params)

    async def calculate_price(self, service_id: int, options: dict, tenant_id: int = DEFAULT_TENANT_ID):
        """حساب السعر الحتمي من أودو 20"""
        params = {
            "tenant_id": tenant_id,
            "service_id": service_id,
            "options": options,
        }
        return await self._post_jsonrpc("/api/link/v1/price", params)

    async def create_request_draft(self, partner_phone: str, service_id: int, customer_name: str = None, initial_data: dict = None, tenant_id: int = DEFAULT_TENANT_ID):
        """إنشاء بطاقة طلب في أودو 20"""
        params = {
            "tenant_id": tenant_id,
            "partner_phone": partner_phone,
            "customer_name": customer_name,
            "service_id": service_id,
            "data": initial_data or {},
        }
        return await self._post_jsonrpc("/api/link/v1/request/draft", params)

    async def update_request_data(self, request_id: int, new_data: dict):
        """تحديث بيانات الطلب المجمعة"""
        params = {
            "request_id": request_id,
            "data": new_data,
        }
        return await self._post_jsonrpc("/api/link/v1/request/update", params)

    async def attach_document(self, request_id: int, requirement_code: str, file_base64: str, filename: str):
        """رفع مستند للطلب"""
        params = {
            "request_id": request_id,
            "requirement_code": requirement_code,
            "file_base64": file_base64,
            "filename": filename,
        }
        return await self._post_jsonrpc("/api/link/v1/request/document", params)

    async def approve_request(self, request_id: int):
        """اعتماد الطلب"""
        params = {"request_id": request_id}
        return await self._post_jsonrpc("/api/link/v1/request/approve", params)

    async def attach_by_phone(self, phone: str, file_base64: str, filename: str = "whatsapp_image.jpg", session_id: str = None, tenant_id: int = None, whatsapp_chat_id: str = None):
        """رفع مستند أو صورة تلقائياً للطلب النشط برقم الهاتف"""
        params = {
            "phone": phone,
            "file_base64": file_base64,
            "filename": filename,
        }
        if whatsapp_chat_id:
            params["whatsapp_chat_id"] = whatsapp_chat_id
        if session_id:
            params["session_id"] = session_id
        if tenant_id:
            params["tenant_id"] = tenant_id
        return await self._post_jsonrpc("/api/link/v1/request/attach_by_phone", params)


odoo_client = OdooClient()
