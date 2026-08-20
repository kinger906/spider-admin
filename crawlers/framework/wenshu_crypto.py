"""裁判文书网请求参数生成与响应解密（3DES）。"""

from __future__ import annotations

import base64
import random
import time
from datetime import datetime

from Crypto.Cipher import DES3
from Crypto.Util.Padding import pad, unpad


CHARS = "ABCDEFGHIGKLMNOPQRSTUVWXYZabcdefghigklmnopqrstuvwxyz0123456789"


def today_iv() -> str:
    return datetime.now().strftime("%Y%m%d")


def random_str(n: int = 24) -> str:
    return "".join(random.choice(CHARS) for _ in range(n))


def _des3(key: str, iv: str) -> DES3.DES3Cipher:
    key_bytes = key.encode("utf-8")[:24].ljust(24, b"\0")
    iv_bytes = iv.encode("utf-8")[:8].ljust(8, b"\0")
    return DES3.new(key_bytes, DES3.MODE_CBC, iv_bytes)


def encrypt(plaintext: str, key: str, iv: str) -> str:
    cipher = _des3(key, iv)
    data = pad(plaintext.encode("utf-8"), DES3.block_size)
    return base64.b64encode(cipher.encrypt(data)).decode("utf-8")


def decrypt(ciphertext: str, key: str, iv: str | None = None) -> str:
    iv = iv or today_iv()
    cipher = _des3(key, iv)
    raw = cipher.decrypt(base64.b64decode(ciphertext))
    return unpad(raw, DES3.block_size).decode("utf-8")


def str_to_binary(text: str) -> str:
    return " ".join(format(ord(ch), "b") for ch in text)


def make_ciphertext() -> str:
    timestamp = str(int(time.time() * 1000))
    salt = random_str(24)
    iv = today_iv()
    enc = encrypt(timestamp, salt, iv)
    return str_to_binary(salt + iv + enc)


def make_page_id() -> str:
    return random_str(32).lower()


def make_token() -> str:
    return random_str(24)
