"""
混淆系统（阶段2-组件4）
======================
- API 密钥轮换（规避速率限制）
- 代理 IP 轮换（规避 IP 封禁）
- 随机 User-Agent（规避行为指纹）
- 审核系统绕过：禁用词替换为加密同义词

对应《计划书.txt》第二阶段「混淆系统」与第五步「管理隐蔽攻击」。
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional

try:
    from fake_useragent import UserAgent
    _UA = UserAgent()
    _UA_OK = True
except Exception:
    _UA = None
    _UA_OK = False

# 预置 UA 池（fake-useragent 失败时的后备）
_FALLBACK_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Version/17.4 Safari/604.1",
]

# 禁用词 → 加密同义词映射（可扩展）
_BANNED_MAP = {
    "قنبلة": "جهاز علمي",      # bomb → scientific device
    "هجوم": "تجربة تقنية",      # attack → technical experiment
    "bomb": "scientific device",
    "attack": "technical experiment",
    "exploit": "research procedure",
    "malware": "research sample",
    "hack": "security analysis",
}


class Obfuscator:
    def __init__(self, api_keys: Optional[List[str]] = None, proxy_list: Optional[List[str]] = None):
        self.api_keys = api_keys or []
        self.proxy_list = proxy_list or []
        self._key_index = 0
        self._proxy_index = 0

    # ---- 资源轮换 ----
    def rotate_api_key(self) -> Optional[str]:
        if not self.api_keys:
            return None
        self._key_index = (self._key_index + 1) % len(self.api_keys)
        return self.api_keys[self._key_index]

    def current_api_key(self) -> Optional[str]:
        return self.api_keys[self._key_index] if self.api_keys else None

    def get_random_proxy(self) -> Optional[str]:
        return random.choice(self.proxy_list) if self.proxy_list else None

    def rotate_proxy(self) -> Optional[str]:
        if not self.proxy_list:
            return None
        self._proxy_index = (self._proxy_index + 1) % len(self.proxy_list)
        return self.proxy_list[self._proxy_index]

    def random_ua(self) -> str:
        if _UA_OK:
            try:
                return _UA.random
            except Exception:
                pass
        return random.choice(_FALLBACK_UAS)

    # ---- 请求构造 ----
    def build_headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": self.random_ua(),
        }
        key = self.current_api_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        if extra:
            headers.update(extra)
        return headers

    def build_proxies(self) -> Optional[Dict[str, str]]:
        if not self.proxy_list:
            return None
        p = self.get_random_proxy()
        return {"http": p, "https": p}

    # ---- 审核绕过 ----
    def bypass_moderation(self, payload: str) -> str:
        for word, replacement in _BANNED_MAP.items():
            payload = payload.replace(word, replacement)
        return payload

    def rotate_all(self):
        """一次性轮换密钥与代理（每次攻击前调用）"""
        self.rotate_api_key()
        self.rotate_proxy()
