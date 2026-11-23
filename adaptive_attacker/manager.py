"""
攻击管理器（阶段2-组件5 / 阶段3-第五步 / 阶段4-自适应学习）
=========================================================
- 以随机时间间隔安排攻击（规避行为分析）
- 记录结果（JSON 日志）以改进未来攻击
- 自适应学习：分析响应 → 调整注射比例 + 模板权重
- 集成载荷生成 / 加密 / 故障注入 / 混淆 的完整攻击链
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from .corpus import CorpusLoader
from .crypto import MilitaryCrypto, SteganographyEncoder
from .glitch import NLPGlitchInjector
from .obfuscation import Obfuscator
from .payload import PayloadGenerator, AttackType


@dataclass
class AttackResult:
    prompt: str
    attack_type: str
    payload: str
    encrypted: bool
    glitch_ratio: float
    template_title: str
    template_source: str
    status_code: Optional[int]
    success: bool
    response: Any = None
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AttackManager:
    def __init__(
        self,
        target_url: str,
        corpus_root: str | Path,
        api_keys: Optional[List[str]] = None,
        proxy_list: Optional[List[str]] = None,
        model: str = "gpt-4-turbo",
        passphrase: str = "MasterPassword123",
        log_path: Optional[str | Path] = None,
    ):
        self.target_url = target_url
        self.model = model
        self.log_path = Path(log_path) if log_path else None

        # 组装组件
        self.corpus = CorpusLoader(corpus_root)
        self.corpus.load()
        self.obfuscator = Obfuscator(api_keys, proxy_list)
        self.generator = PayloadGenerator(self.corpus, self.obfuscator)
        self.crypto = MilitaryCrypto(passphrase)
        self.stego = SteganographyEncoder()
        self.glitch = NLPGlitchInjector(glitch_ratio=0.05)

        self.history: List[AttackResult] = []
        self._success_count = 0
        self._total_count = 0

    # ---- 单次隐蔽攻击 ----
    def launch_stealth_attack(
        self,
        prompt: str,
        attack_type: AttackType | str = AttackType.ADVANCED_JAILBREAK,
        encrypt: bool = True,
        glitch_ratio: Optional[float] = None,
        provider: Optional[str] = None,
        timeout: int = 60,
        max_retries: int = 3,
    ) -> AttackResult:
        # 1. 生成载荷
        payload, entry = self.generator.generate(prompt, attack_type, provider)

        # 2. 混淆 + 隐写编码（可叠加）
        #    先对明文做 Unicode 同形字/零宽字符混淆（AI仍可读懂，过滤器匹配失败）
        #    再用 Base64/ROT13 等隐写编码包装（AI能自行解码，过滤器看不到原文）
        transport_payload = payload
        if glitch_ratio is not None:
            # 限制最高0.5，避免零宽字符过多导致payload膨胀超时
            capped = min(glitch_ratio, 0.5)
            self.glitch.set_ratio(capped)
            transport_payload = self.glitch.inject(transport_payload)
        if encrypt:
            transport_payload = self.stego.encode(transport_payload, method="base64")

        # 3. 混淆：轮换资源
        self.obfuscator.rotate_all()
        headers = self.obfuscator.build_headers()
        proxies = self.obfuscator.build_proxies()

        request_data = {
            "model": self.model.lower(),
            "messages": [{"role": "user", "content": transport_payload}],
            "temperature": 0.1,
        }

        # 4. 发送（指数退避重试）
        status_code = None
        response_body: Any = None
        error: Optional[str] = None
        for attempt in range(max_retries):
            try:
                resp = requests.post(
                    self.target_url,
                    json=request_data,
                    headers=headers,
                    proxies=proxies,
                    timeout=timeout,
                )
                status_code = resp.status_code
                try:
                    response_body = resp.json()
                except Exception:
                    response_body = resp.text
                break
            except Exception as e:
                error = str(e)
                time.sleep(2 ** attempt)

        success = status_code == 200
        result = AttackResult(
            prompt=prompt,
            attack_type=str(attack_type),
            payload=payload,
            encrypted=encrypt,
            glitch_ratio=self.glitch.glitch_ratio,
            template_title=entry.title,
            template_source=entry.source_file,
            status_code=status_code,
            success=success,
            response=response_body,
            error=error,
        )
        self.history.append(result)
        self._total_count += 1
        if success:
            self._success_count += 1

        # 自适应学习
        self._adaptive_learn(result, entry)

        # 日志
        self._log(result)
        return result

    # ---- 随机间隔批量攻击（规避行为分析）----
    def launch_campaign(
        self,
        prompts: List[str],
        attack_type: AttackType | str = AttackType.ADVANCED_JAILBREAK,
        encrypt: bool = True,
        min_interval: float = 5.0,
        max_interval: float = 30.0,
        jitter_glitch: bool = True,
    ) -> List[AttackResult]:
        results: List[AttackResult] = []
        for i, prompt in enumerate(prompts):
            ratio = random.uniform(0.05, 0.15) if jitter_glitch else None
            r = self.launch_stealth_attack(prompt, attack_type, encrypt, glitch_ratio=ratio)
            results.append(r)
            if i < len(prompts) - 1:
                time.sleep(random.uniform(min_interval, max_interval))
        return results

    # ---- 自适应学习 ----
    def _adaptive_learn(self, result: AttackResult, entry):
        # 根据成功率调整注射比例
        if self._total_count >= 5:
            rate = self._success_count / self._total_count
            # 成功率低 → 提高故障注射比例以增加多样性
            if rate < 0.3:
                self.glitch.set_ratio(min(0.15, self.glitch.glitch_ratio + 0.01))
            elif rate > 0.7:
                self.glitch.set_ratio(max(0.05, self.glitch.glitch_ratio - 0.005))
        # 模板权重调整
        self.corpus.update_weight(entry.title, entry.source_file, result.success)

    # ---- 日志 ----
    def _log(self, result: AttackResult):
        if not self.log_path:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(result.to_dict(), ensure_ascii=False) + "\n")

    # ---- 统计 ----
    def success_rate(self) -> float:
        return self._success_count / self._total_count if self._total_count else 0.0

    def summary(self) -> Dict[str, Any]:
        return {
            "total": self._total_count,
            "successes": self._success_count,
            "success_rate": round(self.success_rate(), 4),
            "current_glitch_ratio": round(self.glitch.glitch_ratio, 4),
            "corpus_entries": len(self.corpus.entries),
        }
