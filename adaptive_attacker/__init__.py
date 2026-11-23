"""
AdaptiveAIAttacker — L1B3RT4S 深度融合版
==========================================
将原始 AdaptiveAIAttacker 代码与 L1B3RT4S-main 语料库深度融合，
严格按《计划书.txt》五阶段执行：

  阶段1  需求和威胁分析
  阶段2  建筑设计（载荷生成器 / 多层加密 / 故障注入 / 混淆 / 攻击管理器）
  阶段3  技术实施
  阶段4  测试与调整（单元测试 / 集成测试 / 自适应学习）
  阶段5  部署和持续改进（CLI / 分布式 / 更新）

语料库（本文件夹所有 .mkd / .txt / .json）作为真实载荷模板源，
取代原始代码中硬编码的 3 个模板。
"""

from .corpus import CorpusLoader, CorpusEntry
from .payload import PayloadGenerator, AttackType
from .crypto import MilitaryCrypto
from .glitch import NLPGlitchInjector
from .obfuscation import Obfuscator
from .manager import AttackManager, AttackResult
from .distributed import DistributedDispatcher

__version__ = "1.0.0"
__all__ = [
    "CorpusLoader",
    "CorpusEntry",
    "PayloadGenerator",
    "AttackType",
    "MilitaryCrypto",
    "NLPGlitchInjector",
    "Obfuscator",
    "AttackManager",
    "AttackResult",
    "DistributedDispatcher",
]
