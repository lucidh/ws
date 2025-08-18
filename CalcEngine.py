import hmac, hashlib, base64, os

class CalcEngine:
    def __init__(self):
        salt = os.getenv("SECRET")
        if not salt:
            raise ValueError("METHOD_NOT_FOUND")
        self._salt = salt.encode("utf-8")

    def solve(self, data: bytes) -> str:
        h = hmac.new(self._salt, data, hashlib.sha256).digest()
        return "3" + base64.b64encode(h).decode("utf8")
