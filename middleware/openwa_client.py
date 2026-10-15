import logging
import httpx
from .config import OPENWA_URL, OPENWA_API_KEY, OPENWA_DEFAULT_SESSION

logger = logging.getLogger("link.openwa")


class OpenWAClient:
    def __init__(self, base_url: str = OPENWA_URL, api_key: str = OPENWA_API_KEY):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _get_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _normalize_chat_id(self, to: str) -> str:
        clean = to.strip().replace("+", "")
        if "@" in clean:
            return clean
        return f"{clean}@c.us"

    async def ensure_session_ready(self, session_id: str):
        """التأكد من تشغيل جلسة واتساب تلقائياً إذا كانت متوقفة"""
        sess = session_id or OPENWA_DEFAULT_SESSION
        url = f"{self.base_url}/api/sessions/{sess}/start"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                await client.post(url, headers=self._get_headers())
        except Exception:
            pass

    async def send_text(self, session_id: str, to: str, text: str, retry_on_inactive: bool = True):
        """إرسال رسالة نصية عبر OpenWA Gateway API مع إعادة تشغيل الجلسة تلقائياً إذا كانت غير نشطة"""
        sess = session_id or OPENWA_DEFAULT_SESSION
        url = f"{self.base_url}/api/sessions/{sess}/messages/send-text"
        chat_id = self._normalize_chat_id(to)
        payload = {
            "chatId": chat_id,
            "text": text,
        }
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.post(url, json=payload, headers=self._get_headers())
                if resp.status_code in (200, 201):
                    return resp.json()
                if retry_on_inactive and ("not active" in resp.text or resp.status_code in (400, 404, 502)):
                    logger.warning(f"Session {sess} not ready, initiating auto-start and retrying in 3s...")
                    await self.ensure_session_ready(sess)
                    import asyncio
                    await asyncio.sleep(3)
                    retry_resp = await client.post(url, json=payload, headers=self._get_headers())
                    if retry_resp.status_code in (200, 201):
                        return retry_resp.json()
                logger.error(f"OpenWA send_text error [{resp.status_code}]: {resp.text}")
                return {"error": resp.text, "status_code": resp.status_code}
        except Exception as e:
            logger.exception("Failed to connect to OpenWA Gateway")
            return {"error": f"OpenWA Gateway unreachable: {e}"}

    async def send_buttons(self, session_id: str, to: str, text: str, buttons: list):
        """
        إرسال خيارات تفاعلية عبر واتساب.
        نظراً لقيود واتساب الرسمية على أزرار الويب، نقوم بتنسيق الخيارات بأسلوب تفاعلي جذاب وواضح
        يتيح للعميل الرد برقم الخيار أو الضغط عليه.
        """
        lines = [text, ""]
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        for idx, btn in enumerate(buttons):
            emoji = number_emojis[idx] if idx < len(number_emojis) else f"{idx+1}."
            title = btn.get("title") or btn.get("text") or ""
            lines.append(f"{emoji} {title}")
        lines.append("\n👉 _أرسل رقم الخيار (1 أو 2 أو 3) أو اكتب استفسارك مباشرة:_")
        formatted_text = "\n".join(lines)
        return await self.send_text(session_id=session_id, to=to, text=formatted_text)

    async def resolve_contact(self, session_id: str, contact_id: str) -> dict:
        """
        حل معرف جهة الاتصال (سواء كان @lid أو رقم هاتف عادي)
        لإرجاع رقم الهاتف الفعلي الحقيقي والاسم المحفوظ في دفتر العناوين.
        """
        sess = session_id or OPENWA_DEFAULT_SESSION
        clean_id = contact_id.strip()
        url = f"{self.base_url}/api/sessions/{sess}/contacts/{clean_id}"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, headers=self._get_headers())
                if resp.status_code == 200:
                    data = resp.json()
                    real_jid = data.get("id") or ""
                    real_phone = ""
                    if "@c.us" in real_jid:
                        real_phone = real_jid.split("@")[0].replace("+", "")
                    elif "@s.whatsapp.net" in real_jid:
                        real_phone = real_jid.split("@")[0].replace("+", "")
                    
                    contact_name = data.get("name") or data.get("pushName") or ""
                    return {
                        "real_phone": real_phone,
                        "name": contact_name,
                        "pushName": data.get("pushName") or "",
                        "raw": data,
                    }
        except Exception as e:
            logger.warning(f"Failed to resolve contact {contact_id}: {e}")
        return {"real_phone": "", "name": "", "pushName": ""}


openwa_client = OpenWAClient()

