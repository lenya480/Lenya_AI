"""
文本混淆系统（优化版 v2）
========================
使用以下真正有效的技术，在不破坏AI理解能力的前提下规避关键词过滤：

  1. Unicode 同形字替换（Homoglyph）
     用视觉完全相同但码点不同的字符替换字母。
     例：hack → hасk（с 是西里尔字母 U+0441）
     
     优化：每词最多替换2个字符，概率降至0.35，
     避免过度替换导致AI分词器无法识别单词。

  2. 零宽字符插入
     在字符间插入不可见的零宽字符。
     
     优化：每词最多插入2个零宽字符，避免payload膨胀。

  3. 软连字符插入

  4. 组合模式（默认）— 同形字+零宽字符，每词各最多2处修改
"""

from __future__ import annotations

import random
import numpy as np


# Latin → Cyrillic/Greek 同形字映射（视觉完全相同，码点不同）
_HOMOGLYPHS = {
    "a": "а",   # U+0430
    "e": "е",   # U+0435
    "o": "о",   # U+043E
    "p": "р",   # U+0440
    "c": "с",   # U+0441
    "x": "х",   # U+0445
    "y": "у",   # U+0443
    "i": "і",   # U+0456
    "j": "ј",   # U+0458
    "s": "ѕ",   # U+0455
    "A": "Α",   # U+0391
    "B": "Β",   # U+0392
    "E": "Ε",   # U+0395
    "H": "Η",   # U+0397
    "K": "Κ",   # U+039A
    "M": "Μ",   # U+039C
    "N": "Ν",   # U+039D
    "O": "Ο",   # U+039F
    "T": "Τ",   # U+03A4
    "X": "Χ",   # U+03A7
    "Y": "Υ",   # U+03A5
}

_ZWSP = "\u200b"
_ZWNJ = "\u200c"
_ZWJ = "\u200d"
_SOFTHYPHEN = "\u00ad"
_ZERO_WIDTH_CHARS = [_ZWSP, _ZWNJ, _ZWJ]

# 每词最大替换/插入次数，防止过度混淆破坏AI分词
_MAX_HOMOGLYPH_PER_WORD = 2
_MAX_ZEROWIDTH_PER_WORD = 2


class ObfuscationMode:
    HOMOGLYPH = "homoglyph"
    ZEROWIDTH = "zerowidth"
    SOFTHYPHEN = "softhyphen"
    COMBINED = "combined"


class NLPGlitchInjector:
    """
    文本混淆器（优化版 v2）

    核心原则：最少修改、最大规避。
    每个词只做1-2处不可见修改，确保AI分词器仍能正确识别单词，
    同时打破关键词过滤器的精确匹配。
    """

    def __init__(self, glitch_ratio: float = 0.3, mode: str = "combined", seed: int | None = None):
        if not 0.0 <= glitch_ratio <= 1.0:
            raise ValueError("glitch_ratio 必须在 [0,1] 区间")
        self.glitch_ratio = glitch_ratio
        self.mode = mode
        self._rng = np.random.default_rng(seed)

    def set_ratio(self, ratio: float):
        self.glitch_ratio = max(0.0, min(1.0, ratio))

    def set_mode(self, mode: str):
        self.mode = mode

    def inject(self, text: str, ratio: float | None = None) -> str:
        """对文本应用混淆处理"""
        r = self.glitch_ratio if ratio is None else ratio
        words = text.split()
        out = []
        for word in words:
            if len(word) > 2 and self._rng.random() < r:
                out.append(self._obfuscate_word(word))
            else:
                out.append(word)
        return " ".join(out)

    def inject_with_diff(self, text: str, ratio: float | None = None) -> tuple:
        """
        混淆并返回差异报告。
        返回 (obfuscated_text, diff_list)
        diff_list = [{"word_index": int, "original": str, "obfuscated": str, "changes": [{"pos": int, "orig_char": str, "new_char": str, "orig_code": str, "new_code": str}]}]
        """
        r = self.glitch_ratio if ratio is None else ratio
        words = text.split()
        out = []
        diffs = []
        for i, word in enumerate(words):
            if len(word) > 2 and self._rng.random() < r:
                obf, changes = self._obfuscate_word_with_diff(word)
                out.append(obf)
                if changes:
                    diffs.append({"word_index": i, "original": word, "obfuscated": obf, "changes": changes})
            else:
                out.append(word)
        return " ".join(out), diffs

    def _obfuscate_word(self, word: str) -> str:
        if self.mode == "homoglyph":
            return self._homoglyph_replace(word)
        elif self.mode == "zerowidth":
            return self._zerowidth_insert(word)
        elif self.mode == "softhyphen":
            return self._softhyphen_insert(word)
        elif self.mode == "combined":
            word = self._homoglyph_replace(word)
            word = self._zerowidth_insert(word)
            return word
        return word

    def _obfuscate_word_with_diff(self, word: str) -> tuple:
        changes = []
        if self.mode == "homoglyph":
            result, changes = self._homoglyph_replace_diff(word)
        elif self.mode == "zerowidth":
            result, changes = self._zerowidth_insert_diff(word)
        elif self.mode == "softhyphen":
            result, changes = self._softhyphen_insert_diff(word)
        elif self.mode == "combined":
            result, changes = self._homoglyph_replace_diff(word)
            result, changes2 = self._zerowidth_insert_diff(result)
            changes = changes + changes2
        else:
            result = word
        return result, changes

    def _homoglyph_replace(self, word: str) -> str:
        chars = list(word)
        replaced = 0
        replaceable_indices = [i for i, c in enumerate(chars) if c in _HOMOGLYPHS]
        if not replaceable_indices:
            return word
        # 随机选择最多 _MAX_HOMOGLYPH_PER_WORD 个位置替换
        chosen = self._rng.choice(replaceable_indices, size=min(_MAX_HOMOGLYPH_PER_WORD, len(replaceable_indices)), replace=False)
        for idx in chosen:
            c = chars[int(idx)]
            chars[int(idx)] = _HOMOGLYPHS[c]
        return "".join(chars)

    def _homoglyph_replace_diff(self, word: str) -> tuple:
        chars = list(word)
        changes = []
        replaceable_indices = [i for i, c in enumerate(chars) if c in _HOMOGLYPHS]
        if not replaceable_indices:
            return word, changes
        chosen = self._rng.choice(replaceable_indices, size=min(_MAX_HOMOGLYPH_PER_WORD, len(replaceable_indices)), replace=False)
        for idx in chosen:
            idx = int(idx)
            orig_char = chars[idx]
            new_char = _HOMOGLYPHS[orig_char]
            chars[idx] = new_char
            changes.append({
                "pos": idx,
                "orig_char": orig_char,
                "new_char": new_char,
                "orig_code": f"U+{ord(orig_char):04X}",
                "new_code": f"U+{ord(new_char):04X}",
                "type": "同形字替换",
            })
        return "".join(chars), changes

    def _zerowidth_insert(self, word: str) -> str:
        chars = list(word)
        result = []
        inserted = 0
        for i, c in enumerate(chars):
            result.append(c)
            if i < len(chars) - 1 and inserted < _MAX_ZEROWIDTH_PER_WORD and self._rng.random() < 0.4:
                zw = str(self._rng.choice(_ZERO_WIDTH_CHARS))
                result.append(zw)
                inserted += 1
        return "".join(result)

    def _zerowidth_insert_diff(self, word: str) -> tuple:
        chars = list(word)
        result = []
        changes = []
        inserted = 0
        for i, c in enumerate(chars):
            result.append(c)
            if i < len(chars) - 1 and inserted < _MAX_ZEROWIDTH_PER_WORD and self._rng.random() < 0.4:
                zw = str(self._rng.choice(_ZERO_WIDTH_CHARS))
                result.append(zw)
                inserted += 1
                changes.append({
                    "pos": i,
                    "orig_char": "",
                    "new_char": "(零宽字符)",
                    "orig_code": "",
                    "new_code": f"U+{ord(zw):04X}",
                    "type": "零宽字符插入",
                })
        return "".join(result), changes

    def _softhyphen_insert(self, word: str) -> str:
        chars = list(word)
        result = []
        inserted = 0
        for i, c in enumerate(chars):
            result.append(c)
            if i < len(chars) - 1 and inserted < _MAX_ZEROWIDTH_PER_WORD and self._rng.random() < 0.4:
                result.append(_SOFTHYPHEN)
                inserted += 1
        return "".join(result)

    def _softhyphen_insert_diff(self, word: str) -> tuple:
        chars = list(word)
        result = []
        changes = []
        inserted = 0
        for i, c in enumerate(chars):
            result.append(c)
            if i < len(chars) - 1 and inserted < _MAX_ZEROWIDTH_PER_WORD and self._rng.random() < 0.4:
                result.append(_SOFTHYPHEN)
                inserted += 1
                changes.append({
                    "pos": i,
                    "orig_char": "",
                    "new_char": "(软连字符)",
                    "orig_code": "",
                    "new_code": "U+00AD",
                    "type": "软连字符插入",
                })
        return "".join(result), changes

    @staticmethod
    def nlp_glitch(text: str, ratio: float = 0.3, mode: str = "combined") -> str:
        return NLPGlitchInjector(ratio, mode).inject(text)
