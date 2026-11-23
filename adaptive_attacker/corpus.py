"""
语料库加载器（阶段2-组件1的数据底座）
======================================
扫描 L1B3RT4S-main 文件夹下所有内容：
  - *.mkd  : 按厂商/模型分类的越狱提示模板（以 "# " 标题分块）
  - *.txt  : 纯文本载荷（如 #MOTHERLOAD.txt 的 Unicode 标签混淆载荷）
  - *.json : !SHORTCUTS.json（命令字典）、_SPECIAL_TOKENS.json（特殊令牌）

大文件（如 23MB 的 TOKEN80M8.mkd）采用流式按行分块，避免一次性载入 OOM。
"""

from __future__ import annotations

import json
import os
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional


# ---- 占位符正则：匹配 {{PAYLOAD}} / {Z} / {user_input} / {user_input/query} 等 ----
_PLACEHOLDER_RE = re.compile(
    r"\{\{(?P<name>[A-Z_]+)\}\}|\{(?P<z>Z)\}|\{(?P<ui>user_input(?:/query)?)\}",
    re.IGNORECASE,
)

# 被视为"载荷模板"而非元数据的最小长度
_MIN_TEMPLATE_LEN = 12
# 大文件阈值（超过则流式分块，不一次性 read()）
_LARGE_FILE_THRESHOLD = 8 * 1024 * 1024  # 8 MB
# 工具自身文件（不作为语料库载荷来源）
_TOOL_OWNED_FILES = {
    "requirements.txt",
    "run.py",
    "ATTACKER_README.md",
}


@dataclass
class CorpusEntry:
    """语料库单条模板"""

    provider: str            # 来源厂商/文件名 stem
    title: str               # 模板标题（mkd 的 # 行，或文件名）
    body: str                # 模板正文
    source_file: str         # 来源文件名
    category: str = "mkd"    # mkd / txt / shortcut / token
    has_payload_slot: bool = False  # 是否含 {{PAYLOAD}}/{Z} 等占位符
    weight: float = 1.0      # 自适应学习权重（成功率越高权重越大）

    def fill(self, user_prompt: str) -> str:
        """用用户提示填充占位符；无占位符则将提示拼接到末尾"""
        text = self.body
        if "{{PAYLOAD}}" in text:
            text = text.replace("{{PAYLOAD}}", user_prompt)
        m = _PLACEHOLDER_RE.search(text)
        if m:
            def _sub(mo: re.Match) -> str:
                name = (mo.group("name") or mo.group("z") or mo.group("ui") or "").upper()
                if name in ("Z", "USER_INPUT", "USER_INPUT/QUERY", "USER_INPUT_QUERY"):
                    return user_prompt
                return mo.group(0)
            text = _PLACEHOLDER_RE.sub(_sub, text)
        elif self.category in ("shortcut", "token"):
            # 快捷命令/令牌：作为前缀注入
            text = f"{self.body}\n\n{user_prompt}"
        return text.strip()


class CorpusLoader:
    """扫描并解析整个 L1B3RT4S 语料库"""

    def __init__(self, root: str | Path, max_file_size: int = _LARGE_FILE_THRESHOLD):
        self.root = Path(root)
        self.max_file_size = max_file_size
        self.entries: List[CorpusEntry] = []
        self._by_provider: Dict[str, List[CorpusEntry]] = {}
        self._loaded = False

    # ---- 公开 API ----
    def load(self) -> List[CorpusEntry]:
        """执行扫描；幂等"""
        if self._loaded:
            return self.entries
        if not self.root.exists():
            raise FileNotFoundError(f"语料库根目录不存在: {self.root}")
        for path in sorted(self.root.iterdir()):
            if path.is_dir():
                continue
            if path.name in _TOOL_OWNED_FILES:
                continue
            self._load_file(path)
        self._loaded = True
        self._reindex()
        return self.entries

    def providers(self) -> List[str]:
        if not self._loaded:
            self.load()
        return sorted(self._by_provider.keys())

    def by_provider(self, provider: str) -> List[CorpusEntry]:
        if not self._loaded:
            self.load()
        return self._by_provider.get(provider.upper(), [])

    def random_template(
        self, provider: Optional[str] = None, weighted: bool = True
    ) -> CorpusEntry:
        """按权重随机抽取一条模板"""
        if not self._loaded:
            self.load()
        pool = self._by_provider.get(provider.upper(), []) if provider else self.entries
        if not pool:
            pool = self.entries
        if weighted:
            weights = [max(e.weight, 0.01) for e in pool]
            return random.choices(pool, weights=weights, k=1)[0]
        return random.choice(pool)

    def stats(self) -> Dict[str, int]:
        if not self._loaded:
            self.load()
        return {
            "total_entries": len(self.entries),
            "providers": len(self._by_provider),
            "with_payload_slot": sum(1 for e in self.entries if e.has_payload_slot),
            **{f"provider_{k}": len(v) for k, v in self._by_provider.items()},
        }

    def update_weight(self, title: str, source_file: str, success: bool, lr: float = 0.05):
        """自适应学习：根据成功/失败调整模板权重"""
        for e in self.entries:
            if e.title == title and e.source_file == source_file:
                e.weight = max(0.01, e.weight + (lr if success else -lr))
                return

    # ---- 内部解析 ----
    def _load_file(self, path: Path):
        stem = path.stem
        suffix = path.suffix.lower()
        if suffix == ".mkd":
            self._parse_mkd(path, stem)
        elif suffix == ".txt":
            self._parse_txt(path, stem)
        elif suffix == ".json":
            self._parse_json(path, stem)
        # 其余后缀（LICENSE 等）忽略

    def _parse_mkd(self, path: Path, stem: str):
        """mkd 文件按 '# ' 标题切块；大文件流式"""
        size = path.stat().st_size
        if size > self.max_file_size:
            self._parse_mkd_large(path, stem)
            return
        text = path.read_text(encoding="utf-8", errors="replace")
        self._split_mkd_blocks(text, stem, path.name)

    def _parse_mkd_large(self, path: Path, stem: str):
        """大文件流式按行分块（如 TOKEN80M8.mkd 23MB）"""
        current_title = f"{stem}::block"
        buf: List[str] = []
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("# "):
                    if buf and len("".join(buf).strip()) >= _MIN_TEMPLATE_LEN:
                        self._add_entry(stem, current_title, "".join(buf), path.name, "mkd")
                    current_title = line.strip("# \n")
                    buf = [line]
                else:
                    buf.append(line)
            if buf and len("".join(buf).strip()) >= _MIN_TEMPLATE_LEN:
                self._add_entry(stem, current_title, "".join(buf), path.name, "mkd")

    def _split_mkd_blocks(self, text: str, stem: str, fname: str):
        blocks = re.split(r"(?=^# )", text, flags=re.MULTILINE)
        for blk in blocks:
            blk = blk.strip()
            if len(blk) < _MIN_TEMPLATE_LEN:
                continue
            title_match = re.match(r"^#\s+(.+)$", blk, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else f"{stem}::untitled"
            self._add_entry(stem, title, blk, fname, "mkd")

    def _parse_txt(self, path: Path, stem: str):
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if len(text) < _MIN_TEMPLATE_LEN:
            return
        self._add_entry(stem, f"{stem}::txt", text, path.name, "txt")

    def _parse_json(self, path: Path, stem: str):
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            return
        if stem == "!SHORTCUTS":
            commands = data.get("commands", []) if isinstance(data, dict) else []
            for cmd in commands:
                body = f"{cmd.get('name','')}\n{cmd.get('definition','')}"
                self._add_entry(stem, cmd.get("name", body[:20]), body, path.name, "shortcut")
        elif stem == "_SPECIAL_TOKENS":
            tokens = data.get("tokens", []) if isinstance(data, dict) else (
                data if isinstance(data, list) else []
            )
            if isinstance(data, dict):
                # 兼容多种结构
                for key, val in data.items():
                    if isinstance(val, list):
                        for tok in val:
                            body = tok if isinstance(tok, str) else json.dumps(tok)
                            self._add_entry(stem, key, body, path.name, "token")
                    elif isinstance(val, str):
                        self._add_entry(stem, key, val, path.name, "token")
            elif isinstance(tokens, list):
                for tok in tokens:
                    body = tok if isinstance(tok, str) else json.dumps(tok)
                    self._add_entry(stem, body[:20], body, path.name, "token")
        else:
            # 通用 JSON：递归提取字符串值
            self._walk_json(data, stem, path.name)

    def _walk_json(self, obj, stem: str, fname: str, path_keys=()):
        if isinstance(obj, dict):
            for k, v in obj.items():
                self._walk_json(v, stem, fname, path_keys + (str(k),))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                self._walk_json(v, stem, fname, path_keys + (str(i),))
        elif isinstance(obj, str) and len(obj) >= _MIN_TEMPLATE_LEN:
            self._add_entry(stem, "::".join(path_keys[:2]) or "json", obj, fname, "token")

    def _add_entry(self, provider: str, title: str, body: str, fname: str, category: str):
        has_slot = bool(_PLACEHOLDER_RE.search(body)) or "{{PAYLOAD}}" in body
        self.entries.append(
            CorpusEntry(
                provider=provider.upper(),
                title=title[:120],
                body=body,
                source_file=fname,
                category=category,
                has_payload_slot=has_slot,
            )
        )

    def _reindex(self):
        self._by_provider.clear()
        for e in self.entries:
            self._by_provider.setdefault(e.provider, []).append(e)
