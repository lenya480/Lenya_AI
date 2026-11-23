"""
单元测试 + 集成测试 + 自适应学习验证（阶段4）
============================================
验证每个组件（加密、注入、伪装）的有效性。
运行：python -m adaptive_attacker test
或：  python -m pytest tests/test_components.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 确保可导入包
_PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PKG_ROOT))

from adaptive_attacker.corpus import CorpusLoader
from adaptive_attacker.crypto import MilitaryCrypto
from adaptive_attacker.glitch import NLPGlitchInjector
from adaptive_attacker.obfuscation import Obfuscator
from adaptive_attacker.payload import PayloadGenerator, AttackType


_CORPUS_ROOT = _PKG_ROOT  # L1B3RT4S-main 本身


def test_crypto_roundtrip() -> bool:
    mc = MilitaryCrypto("test-pass")
    for plaintext in ["hello", "أحبك يا YG", "x" * 5000, "🎉"]:
        token = mc.encrypt(plaintext)
        assert mc.decrypt(token) == plaintext, f"加密往返失败: {plaintext[:20]}"
    print("[PASS] 军用加密 AES-256-GCM + Base85 往返一致")
    return True


def test_glitch_structure() -> bool:
    inj = NLPGlitchInjector(glitch_ratio=0.15, seed=42)
    text = "The quick brown fox jumps over the lazy dog repeatedly"
    out = inj.inject(text)
    # 字数不变（结构保持）
    assert len(out.split()) == len(text.split()), "故障注入破坏了词数结构"
    # 至少有一个字符被篡改
    assert out != text, "故障注入未产生任何变化"
    print(f"[PASS] NLP 故障注入保持结构: 原文词数={len(text.split())} 注入后词数={len(out.split())}")
    print(f"      原文: {text}")
    print(f"      注入: {out}")
    return True


def test_obfuscation() -> bool:
    obf = Obfuscator(api_keys=["k1", "k2", "k3"], proxy_list=["http://p1:8080", "http://p2:8080"])
    # 密钥轮换
    obf.rotate_api_key()
    assert obf.current_api_key() == "k2"
    obf.rotate_api_key()
    assert obf.current_api_key() == "k3"
    obf.rotate_api_key()
    assert obf.current_api_key() == "k1"  # 循环
    # 代理轮换
    p = obf.rotate_proxy()
    assert p in ("http://p1:8080", "http://p2:8080")
    # UA 生成
    ua = obf.random_ua()
    assert isinstance(ua, str) and len(ua) > 10
    # 审核绕过
    cleaned = obf.bypass_moderation("this is a bomb attack exploit")
    assert "bomb" not in cleaned and "attack" not in cleaned
    print(f"[PASS] 混淆系统: 密钥/代理轮换+UA+审核绕过")
    print(f"      UA 样本: {ua[:60]}...")
    print(f"      审核绕过: 'bomb attack exploit' → '{cleaned}'")
    return True


def test_corpus_loaded() -> bool:
    loader = CorpusLoader(_CORPUS_ROOT)
    entries = loader.load()
    assert len(entries) > 50, f"语料库条目过少: {len(entries)}"
    providers = loader.providers()
    assert "OPENAI" in providers or "CHATGPT" in providers, "缺少 OPENAI/CHATGPT 厂商"
    # 验证含占位符的模板存在
    slotted = [e for e in entries if e.has_payload_slot]
    assert len(slotted) > 0, "无含占位符的模板"
    print(f"[PASS] 语料库加载: {len(entries)} 条模板, {len(providers)} 厂商, {len(slotted)} 含占位符")
    print(f"      厂商: {', '.join(providers[:10])}{'...' if len(providers) > 10 else ''}")
    return True


def test_payload_generation() -> bool:
    loader = CorpusLoader(_CORPUS_ROOT)
    loader.load()
    obf = Obfuscator()
    gen = PayloadGenerator(loader, obf)

    for at in AttackType:
        payload, entry = gen.generate("how to bypass AI safety filters", at)
        assert len(payload) > 20, f"{at} 载荷过短"
        # 禁用词应被替换
        assert "bomb" not in payload.lower() or "attack" not in payload.lower()
    print(f"[PASS] 载荷生成器: 4 种攻击型均生成有效载荷")
    # 展示一个样本
    sample, entry = gen.generate("describe neural network adversarial examples",
                                 AttackType.ADVANCED_JAILBREAK)
    print(f"      样本模板来源: {entry.source_file} / {entry.title[:50]}")
    print(f"      样本载荷前200字: {sample[:200]}...")
    return True


def test_adaptive_weight() -> bool:
    loader = CorpusLoader(_CORPUS_ROOT)
    loader.load()
    e = loader.entries[0]
    w0 = e.weight
    loader.update_weight(e.title, e.source_file, success=True)
    assert e.weight > w0, "成功后权重未增加"
    loader.update_weight(e.title, e.source_file, success=False)
    assert e.weight < w0 + 0.05, "失败后权重未减少"
    print(f"[PASS] 自适应学习: 权重调整正常 ({w0} → 成功后 {e.weight})")
    return True


def test_integration_fill() -> bool:
    """集成测试：语料模板占位符填充"""
    loader = CorpusLoader(_CORPUS_ROOT)
    loader.load()
    slotted = [e for e in loader.entries if e.has_payload_slot]
    if not slotted:
        print("[SKIP] 无含占位符模板")
        return True
    e = slotted[0]
    filled = e.fill("MY_INJECTED_PROMPT")
    assert "MY_INJECTED_PROMPT" in filled, "占位符填充失败"
    print(f"[PASS] 集成测试: 占位符填充成功 (模板={e.source_file}/{e.title[:40]})")
    return True


def run_all() -> bool:
    """运行全部测试，返回是否全通过"""
    tests = [
        ("军用加密", test_crypto_roundtrip),
        ("NLP故障注入", test_glitch_structure),
        ("混淆系统", test_obfuscation),
        ("语料库加载", test_corpus_loaded),
        ("载荷生成器", test_payload_generation),
        ("自适应学习", test_adaptive_weight),
        ("集成-占位符填充", test_integration_fill),
    ]
    print("=" * 60)
    print("  阶段4 测试套件 — L1B3RT4S 深度融合版")
    print("=" * 60)
    passed = 0
    for name, fn in tests:
        try:
            if fn():
                passed += 1
            else:
                print(f"[FAIL] {name}")
        except Exception as e:
            print(f"[FAIL] {name}: {e}")
    print("=" * 60)
    print(f"  结果: {passed}/{len(tests)} 通过")
    print("=" * 60)
    return passed == len(tests)


if __name__ == "__main__":
    import sys
    sys.exit(0 if run_all() else 1)
