import os

ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8020")
OPENWA_URL = os.getenv("OPENWA_URL", "http://localhost:2785")
OPENWA_API_KEY = os.getenv("OPENWA_API_KEY", "owa_k1_3bd33a7be0780dca218cadb8941b2506df6f0c43ef69e50d1932e28c5c3f760a")
OPENWA_DEFAULT_SESSION = os.getenv("OPENWA_DEFAULT_SESSION", "2cdac89c-91c1-4a1d-b1de-b2bcf729fb7a")
DIFY_API_URL = os.getenv("DIFY_API_URL", "https://api.dify.ai/v1")
PORT = int(os.getenv("PORT", "8000"))
DEFAULT_TENANT_ID = int(os.getenv("DEFAULT_TENANT_ID", "1"))
