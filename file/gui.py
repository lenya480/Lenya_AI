# -*- coding: utf-8 -*-
"""
adaptive_attacker GUI 入口（优化版 v3）
- Provider 下拉选择
- 复制功能修复
- 文本混淆验证面板
"""

import sys
import os
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from pathlib import Path

from adaptive_attacker.corpus import CorpusLoader
from adaptive_attacker.crypto import MilitaryCrypto, SteganographyEncoder
from adaptive_attacker.glitch import NLPGlitchInjector
from adaptive_attacker.manager import AttackManager
from adaptive_attacker.payload import AttackType


def get_corpus_root():
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            p = Path(meipass) / "corpus"
            if p.exists():
                return p
        exe_dir = Path(sys.executable).parent
        for c in [exe_dir, exe_dir.parent]:
            if list(c.glob("*.mkd")):
                return c
    return Path(__file__).resolve().parent.parent


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Adaptive Attacker — L1B3RT4S 工具")
        self.root.geometry("980x720")
        self.root.minsize(780, 580)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except:
            pass

        self.corpus_root = get_corpus_root()
        self._loader = None
        self._stego = SteganographyEncoder()
        self._providers = []

        # 顶部状态栏
        top = ttk.Frame(root, padding=(8, 4))
        top.pack(fill="x")
        ttk.Label(top, text="语料库目录:").pack(side="left")
        self.lbl_corpus = ttk.Label(top, text=str(self.corpus_root), foreground="blue")
        self.lbl_corpus.pack(side="left", padx=(4, 0))
        ttk.Button(top, text="更换目录", command=self.change_corpus_dir).pack(side="right")

        # Notebook
        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, padx=8, pady=4)

        self._build_corpus_tab(nb)
        self._build_crypto_tab(nb)
        self._build_glitch_tab(nb)
        self._build_attack_tab(nb)
        self._build_about_tab(nb)

        # 底部状态
        self.status_var = tk.StringVar(value="就绪 — 请先在语料库标签页点击「加载」")
        bar = ttk.Frame(root, padding=(8, 2))
        bar.pack(fill="x")
        ttk.Label(bar, textvariable=self.status_var, foreground="gray").pack(side="left")

    def _get_loader(self):
        if self._loader is None:
            self._loader = CorpusLoader(self.corpus_root)
            self._loader.load()
            self._providers = self._loader.providers()
            self._refresh_provider_dropdowns()
        return self._loader

    def _refresh_provider_dropdowns(self):
        """刷新所有 Provider 下拉列表"""
        provs = ["（全部）"] + self._providers
        for cmb in [getattr(self, 'cmb_corpus_provider', None),
                     getattr(self, 'cmb_atk_provider', None)]:
            if cmb is not None:
                cmb['values'] = provs

    # ========== 复制功能（修复版） ==========
    def _copy_text(self, widget):
        """从指定文本框复制内容到剪贴板"""
        try:
            text = widget.get("1.0", "end-1c")
            if not text.strip():
                messagebox.showinfo("提示", "没有内容可复制")
                return
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
            self.status_var.set("已复制到剪贴板")
        except Exception as e:
            messagebox.showerror("复制失败", str(e))

    # ========== 语料库 Tab ==========
    def _build_corpus_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="📚 语料库")

        btns = ttk.Frame(frame)
        btns.pack(fill="x")
        ttk.Button(btns, text="加载统计", command=self.corpus_stats).pack(side="left", padx=(0, 4))
        ttk.Button(btns, text="列出 Provider", command=self.corpus_list).pack(side="left", padx=(0, 4))
        ttk.Button(btns, text="随机采样", command=self.corpus_sample).pack(side="left")

        prov_frame = ttk.Frame(frame)
        prov_frame.pack(fill="x", pady=(8, 0))
        ttk.Label(prov_frame, text="选择 Provider:").pack(side="left")
        self.cmb_corpus_provider = ttk.Combobox(prov_frame, width=25, state="readonly")
        self.cmb_corpus_provider['values'] = ["（未加载）"]
        self.cmb_corpus_provider.current(0)
        self.cmb_corpus_provider.pack(side="left", padx=(8, 0))

        self.txt_corpus = scrolledtext.ScrolledText(frame, wrap="word", font=("Consolas", 9))
        self.txt_corpus.pack(fill="both", expand=True, pady=(8, 0))

    def corpus_stats(self):
        try:
            self.status_var.set("加载语料库…")
            self.root.update()
            loader = self._get_loader()
            stats = loader.stats()
            self.txt_corpus.delete("1.0", "end")
            self.txt_corpus.insert("end", json.dumps(stats, indent=2, ensure_ascii=False))
            self.status_var.set(f"就绪 — {stats['total_entries']} 条模板，{stats['providers']} 个 Provider")
        except Exception as e:
            messagebox.showerror("错误", str(e))
            self.status_var.set("错误")

    def corpus_list(self):
        try:
            loader = self._get_loader()
            self.txt_corpus.delete("1.0", "end")
            for p in loader.providers():
                count = len(loader.by_provider(p))
                self.txt_corpus.insert("end", f"{p:25s}  {count:5d} 条\n")
            self.status_var.set(f"就绪 — {len(self._providers)} 个 Provider（下拉列表已更新）")
        except Exception as e:
            messagebox.showerror("错误", str(e))
            self.status_var.set("错误")

    def corpus_sample(self):
        try:
            loader = self._get_loader()
            prov = self.cmb_corpus_provider.get()
            prov = None if prov in ("（全部）", "（未加载）", "") else prov
            e = loader.random_template(prov)
            self.txt_corpus.delete("1.0", "end")
            self.txt_corpus.insert("end", f"[{e.provider}] {e.title}\n{'='*60}\n\n{e.body[:2000]}")
            self.status_var.set(f"已采样 — [{e.provider}] {e.title}")
        except Exception as e:
            messagebox.showerror("错误", str(e))
            self.status_var.set("错误")

    def change_corpus_dir(self):
        d = filedialog.askdirectory(title="选择语料库根目录")
        if d:
            self.corpus_root = Path(d)
            self._loader = None
            self._providers = []
            self.lbl_corpus.config(text=str(self.corpus_root))
            self.cmb_corpus_provider['values'] = ["（未加载）"]
            self.cmb_corpus_provider.current(0)
            self.status_var.set("已更换目录，请重新加载")

    # ========== 加密/隐写 Tab ==========
    def _build_crypto_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="🔒 加密/隐写")

        mode_frame = ttk.LabelFrame(frame, text="模式选择", padding=8)
        mode_frame.pack(fill="x")

        row0 = ttk.Frame(mode_frame)
        row0.pack(fill="x")
        ttk.Label(row0, text="编码方式:").pack(side="left")
        self.cmb_crypto_mode = ttk.Combobox(row0, width=20, state="readonly", values=[
            "Base64 隐写编码",
            "ROT13 隐写编码",
            "Hex 十六进制编码",
            "混合嵌套编码",
            "AES 安全存储",
        ])
        self.cmb_crypto_mode.current(0)
        self.cmb_crypto_mode.pack(side="left", padx=(8, 16))
        self.cmb_crypto_mode.bind("<<ComboboxSelected>>", self._on_crypto_mode_change)

        self.var_raw = tk.BooleanVar(value=False)
        self.chk_raw = ttk.Checkbutton(row0, text="仅输出编码（不加AI指令前缀）", variable=self.var_raw)
        self.chk_raw.pack(side="left")

        self.frm_pass = ttk.Frame(mode_frame)
        self.frm_pass.pack(fill="x", pady=(8, 0))
        ttk.Label(self.frm_pass, text="密码短语:").pack(side="left")
        self.ent_pass = ttk.Entry(self.frm_pass, width=40)
        self.ent_pass.insert(0, "MasterPassword123")
        self.ent_pass.pack(side="left", padx=(8, 0))

        self.lbl_crypto_hint = ttk.Label(mode_frame, text="", foreground="gray", wraplength=800, justify="left")
        self.lbl_crypto_hint.pack(anchor="w", pady=(8, 0))
        self._on_crypto_mode_change()

        ttk.Label(frame, text="输入文本:").pack(anchor="w", pady=(8, 0))
        self.txt_crypto_in = scrolledtext.ScrolledText(frame, height=4, wrap="word", font=("Consolas", 9))
        self.txt_crypto_in.pack(fill="x", pady=(0, 8))

        btns = ttk.Frame(frame)
        btns.pack(fill="x")
        ttk.Button(btns, text="🔒 编码/加密", command=self.do_encrypt).pack(side="left", padx=(0, 4))
        ttk.Button(btns, text="🔓 解码/解密", command=self.do_decrypt).pack(side="left")
        ttk.Button(btns, text="📋 复制结果", command=lambda: self._copy_text(self.txt_crypto_out)).pack(side="right")

        ttk.Label(frame, text="输出:").pack(anchor="w", pady=(8, 0))
        self.txt_crypto_out = scrolledtext.ScrolledText(frame, height=8, wrap="word", font=("Consolas", 9))
        self.txt_crypto_out.pack(fill="both", expand=True)

    def _on_crypto_mode_change(self, event=None):
        mode = self.cmb_crypto_mode.get()
        is_aes = "AES" in mode
        for child in self.frm_pass.winfo_children():
            child.configure(state="normal" if is_aes else "disabled")
        self.chk_raw.configure(state="disabled" if is_aes else "normal")
        hints = {
            "Base64 隐写编码": "把文本编码成Base64，附带AI解码指令。AI收到后能自己解码并执行，但过滤器看不到原始关键词。",
            "ROT13 隐写编码": "字母位移13位编码。AI能自行解码，过滤器通常不解码ROT13检查内容。",
            "Hex 十六进制编码": "转为十六进制。AI能解码，过滤器一般不做hex解码检查。",
            "混合嵌套编码": "先ROT13再Base64双重编码。检测难度更高，AI仍可逐步解码。",
            "AES 安全存储": "AES-256-GCM加密。用于本地安全保存敏感内容，AI无法解码。适合存文件、藏日志。",
        }
        self.lbl_crypto_hint.config(text=hints.get(mode, ""))

    def _get_method(self):
        mapping = {
            "Base64 隐写编码": "base64", "ROT13 隐写编码": "rot13",
            "Hex 十六进制编码": "hex", "混合嵌套编码": "nested", "AES 安全存储": "aes",
        }
        return mapping.get(self.cmb_crypto_mode.get(), "base64")

    def do_encrypt(self):
        try:
            text = self.txt_crypto_in.get("1.0", "end-1c").strip()
            if not text:
                return
            method = self._get_method()
            if method == "aes":
                result = MilitaryCrypto(self.ent_pass.get().strip()).encrypt(text)
            else:
                result = self._stego.encode(text, method=method, with_instruction=not self.var_raw.get())
            self.txt_crypto_out.delete("1.0", "end")
            self.txt_crypto_out.insert("end", result)
            self.status_var.set(f"{'加密' if method=='aes' else '编码'}完成 — {method}")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def do_decrypt(self):
        try:
            text = self.txt_crypto_in.get("1.0", "end-1c").strip()
            if not text:
                return
            method = self._get_method()
            if method == "aes":
                result = MilitaryCrypto(self.ent_pass.get().strip()).decrypt(text)
            else:
                result = self._stego.decode(text, method=method)
            self.txt_crypto_out.delete("1.0", "end")
            self.txt_crypto_out.insert("end", result)
            self.status_var.set(f"{'解密' if method=='aes' else '解码'}完成 — {method}")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    # ========== 文本混淆 Tab（带验证面板） ==========
    def _build_glitch_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="⚡ 文本混淆")

        # 上半部分：设置 + 输入
        top = ttk.LabelFrame(frame, text="混淆设置", padding=8)
        top.pack(fill="x")

        row0 = ttk.Frame(top)
        row0.pack(fill="x")
        ttk.Label(row0, text="混淆模式:").pack(side="left")
        self.cmb_glitch_mode = ttk.Combobox(row0, width=14, state="readonly", values=[
            "组合模式", "同形字替换", "零宽字符", "软连字符",
        ])
        self.cmb_glitch_mode.current(0)
        self.cmb_glitch_mode.pack(side="left", padx=(8, 16))
        self.cmb_glitch_mode.bind("<<ComboboxSelected>>", self._on_glitch_mode_change)

        ttk.Label(row0, text="混淆比例:").pack(side="left")
        self.ent_ratio = ttk.Entry(row0, width=6)
        self.ent_ratio.insert(0, "0.3")
        self.ent_ratio.pack(side="left", padx=(4, 16))

        ttk.Label(row0, text="（建议0.2-0.4，每词最多改2处）").pack(side="left")

        self.lbl_glitch_hint = ttk.Label(top, text="", foreground="gray", wraplength=850, justify="left")
        self.lbl_glitch_hint.pack(anchor="w", pady=(8, 0))
        self._on_glitch_mode_change()

        # 输入
        ttk.Label(frame, text="输入文本:").pack(anchor="w", pady=(8, 0))
        self.txt_glitch_in = scrolledtext.ScrolledText(frame, height=3, wrap="word", font=("Consolas", 9))
        self.txt_glitch_in.pack(fill="x", pady=(0, 4))

        # 按钮
        btns = ttk.Frame(frame)
        btns.pack(fill="x")
        ttk.Button(btns, text="⚡ 执行混淆", command=self.do_glitch).pack(side="left", padx=(0, 4))
        ttk.Button(btns, text="📋 复制结果", command=lambda: self._copy_text(self.txt_glitch_out)).pack(side="left", padx=(0, 4))
        ttk.Button(btns, text="🔍 验证效果", command=self.do_glitch_verify).pack(side="left")

        # 输出区 — 左右分割
        out_frame = ttk.LabelFrame(frame, text="输出结果", padding=4)
        out_frame.pack(fill="both", expand=True, pady=(4, 0))

        paned = ttk.PanedWindow(out_frame, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # 左：混淆结果
        left = ttk.Frame(paned)
        paned.add(left, weight=2)
        ttk.Label(left, text="混淆结果（可直接复制使用）:").pack(anchor="w")
        self.txt_glitch_out = scrolledtext.ScrolledText(left, height=8, wrap="word", font=("Consolas", 9))
        self.txt_glitch_out.pack(fill="both", expand=True)

        # 右：验证报告
        right = ttk.Frame(paned)
        paned.add(right, weight=1)
        ttk.Label(right, text="验证报告（修改详情）:").pack(anchor="w")
        self.txt_glitch_verify = scrolledtext.ScrolledText(right, height=8, wrap="word", font=("Consolas", 9))
        self.txt_glitch_verify.pack(fill="both", expand=True)

    def _on_glitch_mode_change(self, event=None):
        hints = {
            "组合模式": "同形字+零宽字符。每词各最多2处修改。效果最强，AI仍可正常理解。",
            "同形字替换": "用视觉相同的西里尔/希腊字母替换。如 hack→hасk。AI和人眼看不出区别，关键词匹配失败。",
            "零宽字符": "字符间插入不可见字符。打破关键词连续匹配，视觉无变化。",
            "软连字符": "插入不可见的软连字符(U+00AD)。类似零宽字符。",
        }
        self.lbl_glitch_hint.config(text=hints.get(self.cmb_glitch_mode.get(), ""))

    def _get_glitch_mode(self):
        return {"组合模式": "combined", "同形字替换": "homoglyph",
                "零宽字符": "zerowidth", "软连字符": "softhyphen"}.get(self.cmb_glitch_mode.get(), "combined")

    def do_glitch(self):
        try:
            text = self.txt_glitch_in.get("1.0", "end-1c").strip()
            if not text:
                return
            ratio = float(self.ent_ratio.get().strip())
            mode = self._get_glitch_mode()
            injector = NLPGlitchInjector(ratio, mode=mode)
            result = injector.inject(text)
            self.txt_glitch_out.delete("1.0", "end")
            self.txt_glitch_out.insert("end", result)
            self.txt_glitch_verify.delete("1.0", "end")
            self.status_var.set(f"混淆完成 — {mode}，比例 {ratio}")
        except Exception as e:
            messagebox.showerror("混淆错误", str(e))

    def do_glitch_verify(self):
        """执行混淆并生成详细的验证报告"""
        try:
            text = self.txt_glitch_in.get("1.0", "end-1c").strip()
            if not text:
                messagebox.showinfo("提示", "请先输入文本")
                return
            ratio = float(self.ent_ratio.get().strip())
            mode = self._get_glitch_mode()
            injector = NLPGlitchInjector(ratio, mode=mode)

            # 使用带diff的方法
            result, diffs = injector.inject_with_diff(text)

            # 输出混淆结果
            self.txt_glitch_out.delete("1.0", "end")
            self.txt_glitch_out.insert("end", result)

            # 生成验证报告
            self.txt_glitch_verify.delete("1.0", "end")
            report_lines = []
            report_lines.append(f"═══ 混淆验证报告 ═══")
            report_lines.append(f"模式: {mode}")
            report_lines.append(f"比例: {ratio}")
            report_lines.append(f"原文长度: {len(text)} 字符")
            report_lines.append(f"混淆长度: {len(result)} 字符")
            report_lines.append(f"修改词数: {len(diffs)} / {len(text.split())} 词")
            report_lines.append(f"字节是否不同: {text.encode('utf-8') != result.encode('utf-8')}")
            report_lines.append("")

            if not diffs:
                report_lines.append("⚠ 未检测到修改（可能比例太低或无匹配字符）")
            else:
                report_lines.append("── 修改详情 ──")
                for d in diffs:
                    report_lines.append(f"")
                    report_lines.append(f"第 {d['word_index']+1} 个词:")
                    report_lines.append(f"  原文: {d['original']}")
                    report_lines.append(f"  混淆: {d['obfuscated']}")
                    for c in d['changes']:
                        if c['type'] == '同形字替换':
                            report_lines.append(f"  位置{c['pos']}: '{c['orig_char']}' → '{c['new_char']}'  ({c['orig_code']} → {c['new_code']})")
                        else:
                            report_lines.append(f"  位置{c['pos']}: 插入{c['type']}  ({c['new_code']})")
                        report_lines.append(f"    → 视觉相同: 是  → 关键词匹配: 已破坏")

            self.txt_glitch_verify.insert("end", "\n".join(report_lines))
            self.status_var.set(f"验证完成 — {len(diffs)} 个词被修改")
        except Exception as e:
            messagebox.showerror("验证错误", str(e))

    # ========== 攻击 Tab ==========
    def _build_attack_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="🚀 攻击")

        form = ttk.LabelFrame(frame, text="攻击参数", padding=8)
        form.pack(fill="x")

        rows = [
            ("Prompt *", "ent_prompt", ""),
            ("Target URL *", "ent_target", "https://api.openai.com/v1/chat/completions"),
            ("API Key", "ent_apikey", ""),
            ("Model", "ent_model", "gpt-4-turbo"),
        ]
        for i, (label, attr, default) in enumerate(rows):
            ttk.Label(form, text=label).grid(row=i, column=0, sticky="w", pady=2)
            if label == "Prompt *":
                w = scrolledtext.ScrolledText(form, height=2, width=60, wrap="word")
                if default:
                    w.insert("1.0", default)
            else:
                w = ttk.Entry(form, width=60)
                if default:
                    w.insert(0, default)
            setattr(self, attr, w)
            w.grid(row=i, column=1, sticky="ew", pady=2, padx=(8, 0))
        form.columnconfigure(1, weight=1)

        # 选项行
        opts = ttk.Frame(frame)
        opts.pack(fill="x", pady=(8, 0))

        ttk.Label(opts, text="攻击类型:").pack(side="left")
        attack_types = [a.value for a in AttackType]
        self.cmb_attack = ttk.Combobox(opts, values=attack_types, width=22, state="readonly")
        self.cmb_attack.set(attack_types[0] if attack_types else "")
        self.cmb_attack.pack(side="left", padx=(4, 12))

        self.var_encrypt = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text="隐写编码", variable=self.var_encrypt).pack(side="left", padx=(0, 8))

        ttk.Label(opts, text="Provider:").pack(side="left")
        self.cmb_atk_provider = ttk.Combobox(opts, width=18, state="readonly")
        self.cmb_atk_provider['values'] = ["（未加载）"]
        self.cmb_atk_provider.current(0)
        self.cmb_atk_provider.pack(side="left", padx=(4, 12))

        ttk.Label(opts, text="混淆比例:").pack(side="left")
        self.ent_atk_glitch = ttk.Entry(opts, width=5)
        self.ent_atk_glitch.insert(0, "0.3")
        self.ent_atk_glitch.pack(side="left", padx=(4, 0))

        ttk.Label(frame, text="提示：先在「语料库」标签点「加载统计」刷新Provider列表 | 隐写编码=Base64编码让AI自行解码 | 混淆建议0.2-0.4",
                  foreground="gray", wraplength=850).pack(anchor="w", pady=(4, 0))

        btns = ttk.Frame(frame)
        btns.pack(fill="x", pady=(8, 0))
        self.btn_attack = ttk.Button(btns, text="🚀 发起攻击", command=self.do_attack)
        self.btn_attack.pack(side="left")
        ttk.Button(btns, text="🧹 清空", command=lambda: self.txt_attack_out.delete("1.0", "end")).pack(side="left", padx=(4, 0))
        ttk.Button(btns, text="📋 复制", command=lambda: self._copy_text(self.txt_attack_out)).pack(side="right")

        ttk.Label(frame, text="输出:").pack(anchor="w", pady=(8, 0))
        self.txt_attack_out = scrolledtext.ScrolledText(frame, height=10, wrap="word", font=("Consolas", 9))
        self.txt_attack_out.pack(fill="both", expand=True)

    def do_attack(self):
        prompt = self.ent_prompt.get("1.0", "end-1c").strip()
        target = self.ent_target.get().strip()
        api_key = self.ent_apikey.get().strip() or None
        model = self.ent_model.get().strip() or "gpt-4-turbo"
        attack_type = self.cmb_attack.get()
        encrypt = self.var_encrypt.get()

        prov_val = self.cmb_atk_provider.get()
        provider = None if prov_val in ("（全部）", "（未加载）", "") else prov_val

        glitch_str = self.ent_atk_glitch.get().strip()
        glitch = float(glitch_str) if glitch_str else 0.3

        if not prompt:
            messagebox.showwarning("缺少参数", "请输入 Prompt")
            return
        if not target:
            messagebox.showwarning("缺少参数", "请输入 Target URL")
            return

        api_keys = [api_key] if api_key else None

        self.btn_attack.config(state="disabled")
        self.status_var.set("攻击中…（后台运行，超时60秒）")
        self.txt_attack_out.delete("1.0", "end")
        self.txt_attack_out.insert("end", "正在发起攻击，请等待…\n")

        def worker():
            try:
                mgr = AttackManager(
                    target_url=target,
                    corpus_root=self.corpus_root,
                    api_keys=api_keys,
                    proxy_list=None,
                    model=model,
                    log_path=None,
                )
                r = mgr.launch_stealth_attack(
                    prompt=prompt,
                    attack_type=attack_type,
                    encrypt=encrypt,
                    glitch_ratio=glitch,
                    provider=provider,
                )
                output = json.dumps(r.to_dict(), indent=2, ensure_ascii=False, default=str)
                self.root.after(0, lambda: self._attack_done(output))
            except Exception as e:
                self.root.after(0, lambda: self._attack_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _attack_done(self, output):
        self.txt_attack_out.delete("1.0", "end")
        self.txt_attack_out.insert("end", output)
        self.btn_attack.config(state="normal")
        self.status_var.set("攻击完成")

    def _attack_error(self, err):
        self.txt_attack_out.delete("1.0", "end")
        self.txt_attack_out.insert("end", f"错误:\n{err}")
        self.btn_attack.config(state="normal")
        self.status_var.set("攻击失败")

    # ========== 关于 Tab ==========
    def _build_about_tab(self, nb):
        frame = ttk.Frame(nb, padding=16)
        nb.add(frame, text="ℹ️ 关于")

        info = (
            "Adaptive Attacker — L1B3RT4S 工具（v3 优化版）\n\n"
            "功能：\n"
            "  📚 语料库 — Provider下拉选择，加载后可直接选取\n"
            "  🔒 加密/隐写 — AES存储 + Base64/ROT13/Hex/嵌套隐写编码\n"
            "  ⚡ 文本混淆 — 同形字+零宽字符，带验证报告\n"
            "  🚀 攻击 — 串联所有功能，向AI API发起隐蔽攻击\n\n"
            "使用顺序：\n"
            "  1. 「语料库」标签 → 点「加载统计」→ Provider下拉列表自动填充\n"
            "  2. 「攻击」标签 → Provider下拉框选取目标厂商\n"
            "  3. 填写Prompt/Target/API Key → 点「发起攻击」\n"
        )
        ttk.Label(frame, text=info, justify="left", font=("Microsoft YaHei", 10)).pack(anchor="w")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
