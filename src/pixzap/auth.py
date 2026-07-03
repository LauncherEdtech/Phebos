"""Links mágicos: tokens assinados (HMAC) com validade, sem senha.

O vendedor pede *painel* no chat e recebe um link único. Quem tem o link
(e só ele) vê as métricas — se vazar, expira em 24h e um novo pode ser
gerado a qualquer momento.
"""

import base64
import hashlib
import hmac
import time
from typing import Optional

TOKEN_TTL_SECONDS = 24 * 3600


def _sign(secret: str, payload: str) -> str:
    digest = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def make_token(secret: str, subject: str, ttl_seconds: int = TOKEN_TTL_SECONDS,
               now: Optional[float] = None) -> str:
    expiry = int((now or time.time()) + ttl_seconds)
    payload = f"{subject}:{expiry}"
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    return f"{payload_b64}.{_sign(secret, payload)}"


def verify_token(secret: str, token: str,
                 now: Optional[float] = None) -> Optional[str]:
    """Devolve o subject se o token for válido e não expirado; senão None."""
    try:
        payload_b64, signature = token.split(".", 1)
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = base64.urlsafe_b64decode(padded).decode()
    except (ValueError, UnicodeDecodeError):
        return None
    if not hmac.compare_digest(_sign(secret, payload), signature):
        return None
    subject, _, expiry_str = payload.rpartition(":")
    if not expiry_str.isdigit() or int(expiry_str) < (now or time.time()):
        return None
    return subject or None
