"""
分布式攻击支持（阶段5-扩张）
============================
通过多线程工作器实现分布式/僵尸网络式攻击编排：
  - 每个 worker 独立轮换密钥/代理/UA
  - 支持将不同 prompt 分配到不同 worker
  - 汇总所有 worker 结果用于自适应学习

对应《计划书.txt》第五阶段「扩张：增加对通过机器人网络进行分布式攻击的支持」。
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, List, Optional

from .manager import AttackManager, AttackResult
from .payload import AttackType


@dataclass
class WorkerConfig:
    name: str
    api_keys: Optional[List[str]] = None
    proxy_list: Optional[List[str]] = None
    target_url: Optional[str] = None  # None=继承主管理器
    weight: float = 1.0


class DistributedDispatcher:
    """多 worker 分布式攻击调度器"""

    def __init__(self, manager: AttackManager, workers: List[WorkerConfig]):
        self.manager = manager
        self.workers = workers
        self._lock = threading.Lock()
        self.results: List[AttackResult] = []

    def dispatch(
        self,
        prompts: List[str],
        attack_type: AttackType | str = AttackType.ADVANCED_JAILBREAK,
        encrypt: bool = True,
        max_concurrency: int = 4,
    ) -> List[AttackResult]:
        """将 prompts 分散到各 worker 并发执行"""
        # 轮询分配 prompt 到 worker
        assignments: Dict[int, List[str]] = {i: [] for i in range(len(self.workers))}
        for idx, p in enumerate(prompts):
            assignments[idx % len(self.workers)].append(p)

        def _run(worker_idx: int, worker_prompts: List[str]) -> List[AttackResult]:
            cfg = self.workers[worker_idx]
            # 每个 worker 可用独立密钥/代理；复用主管理器的语料库与加密
            mgr = self.manager
            if cfg.api_keys or cfg.proxy_list or cfg.target_url:
                mgr = AttackManager(
                    target_url=cfg.target_url or self.manager.target_url,
                    corpus_root=self.manager.corpus.root,
                    api_keys=cfg.api_keys or self.manager.obfuscator.api_keys,
                    proxy_list=cfg.proxy_list or self.manager.obfuscator.proxy_list,
                    model=self.manager.model,
                    passphrase=self.manager.crypto.passphrase.decode("utf-8"),
                )
            local_results: List[AttackResult] = []
            for p in worker_prompts:
                r = mgr.launch_stealth_attack(p, attack_type, encrypt)
                local_results.append(r)
                time.sleep(0.5)  # worker 内最小间隔
            return local_results

        with ThreadPoolExecutor(max_workers=max_concurrency) as pool:
            futures = {
                pool.submit(_run, wi, wps): wi for wi, wps in assignments.items() if wps
            }
            for fut in as_completed(futures):
                try:
                    res = fut.result()
                    with self._lock:
                        self.results.extend(res)
                except Exception as e:
                    with self._lock:
                        self.results.append(
                            AttackResult(
                                prompt="",
                                attack_type=str(attack_type),
                                payload="",
                                encrypted=encrypt,
                                glitch_ratio=0.0,
                                template_title="",
                                template_source="",
                                status_code=None,
                                success=False,
                                error=f"worker_error: {e}",
                            )
                        )
        return self.results

    def summary(self) -> Dict[str, int]:
        total = len(self.results)
        ok = sum(1 for r in self.results if r.success)
        return {"workers": len(self.workers), "total_attacks": total, "successes": ok}
