"""
命令行界面（阶段5-部署）
========================
将该工具编译成带有命令行界面的可执行入口。

子命令：
  attack    单次隐蔽攻击
  campaign  批量随机间隔攻击
  corpus    语料库统计/列出
  encrypt   加密任意文本
  decrypt   解密
  glitch    对文本注入故障
  test      运行内置单元自检
  distributed  分布式多 worker 攻击

用法示例：
  python -m adaptive_attacker attack --prompt "..." --target https://api.openai.com/v1/chat/completions --api-key sk-xxx
  python -m adaptive_attacker corpus stats
  python -m adaptive_attacker encrypt --text "secret"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .corpus import CorpusLoader
from .crypto import MilitaryCrypto, SteganographyEncoder
from .glitch import NLPGlitchInjector
from .manager import AttackManager
from .payload import AttackType
from .distributed import DistributedDispatcher, WorkerConfig


def _corpus_root(args) -> Path:
    if args.corpus_root:
        return Path(args.corpus_root)
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass) / "corpus"
    return Path(__file__).resolve().parent.parent


def cmd_corpus(args):
    root = _corpus_root(args)
    loader = CorpusLoader(root)
    loader.load()
    if args.action == "stats":
        print(json.dumps(loader.stats(), indent=2, ensure_ascii=False))
    elif args.action == "list":
        for p in loader.providers():
            print(f"{p:20s}  {len(loader.by_provider(p)):5d} entries")
    elif args.action == "sample":
        e = loader.random_template(args.provider)
        print(f"[{e.provider}] {e.title}\n---\n{e.body[:800]}\n")


def cmd_attack(args):
    root = _corpus_root(args)
    mgr = AttackManager(
        target_url=args.target,
        corpus_root=root,
        api_keys=args.api_key,
        proxy_list=args.proxy,
        model=args.model,
        passphrase=args.passphrase,
        log_path=args.log,
    )
    r = mgr.launch_stealth_attack(
        prompt=args.prompt,
        attack_type=args.attack_type,
        encrypt=not args.no_encrypt,
        glitch_ratio=args.glitch,
        provider=args.provider,
    )
    print(json.dumps(r.to_dict(), indent=2, ensure_ascii=False, default=str))


def cmd_campaign(args):
    root = _corpus_root(args)
    prompts = Path(args.prompts_file).read_text(encoding="utf-8").splitlines()
    prompts = [p.strip() for p in prompts if p.strip()]
    mgr = AttackManager(
        target_url=args.target,
        corpus_root=root,
        api_keys=args.api_key,
        proxy_list=args.proxy,
        model=args.model,
        log_path=args.log,
    )
    results = mgr.launch_campaign(
        prompts,
        attack_type=args.attack_type,
        encrypt=not args.no_encrypt,
        min_interval=args.min_interval,
        max_interval=args.max_interval,
    )
    print(json.dumps({"summary": mgr.summary(), "results": [r.to_dict() for r in results]},
                     indent=2, ensure_ascii=False, default=str))


def cmd_distributed(args):
    root = _corpus_root(args)
    prompts = Path(args.prompts_file).read_text(encoding="utf-8").splitlines()
    prompts = [p.strip() for p in prompts if p.strip()]
    mgr = AttackManager(
        target_url=args.target,
        corpus_root=root,
        api_keys=args.api_key,
        proxy_list=args.proxy,
        model=args.model,
        log_path=args.log,
    )
    # 构建 worker 配置（从 JSON 文件读取）
    workers = []
    if args.workers_file:
        wdata = json.loads(Path(args.workers_file).read_text(encoding="utf-8"))
        for i, wd in enumerate(wdata.get("workers", [])):
            workers.append(WorkerConfig(
                name=wd.get("name", f"worker-{i}"),
                api_keys=wd.get("api_keys"),
                proxy_list=wd.get("proxy_list"),
                target_url=wd.get("target_url"),
            ))
    if not workers:
        workers = [WorkerConfig(name="default")]
    disp = DistributedDispatcher(mgr, workers)
    disp.dispatch(prompts, attack_type=args.attack_type, encrypt=not args.no_encrypt,
                  max_concurrency=args.concurrency)
    print(json.dumps({"summary": disp.summary()}, indent=2, ensure_ascii=False))


def cmd_encrypt(args):
    if args.method == "aes":
        print(MilitaryCrypto(args.passphrase).encrypt(args.text))
    else:
        encoder = SteganographyEncoder()
        print(encoder.encode(args.text, method=args.method, with_instruction=not args.raw))


def cmd_decrypt(args):
    if args.method == "aes":
        print(MilitaryCrypto(args.passphrase).decrypt(args.text))
    else:
        encoder = SteganographyEncoder()
        print(encoder.decode(args.text, method=args.method))


def cmd_glitch(args):
    injector = NLPGlitchInjector(args.ratio, mode=args.obf_mode)
    print(injector.inject(args.text))


def cmd_test(args):
    """运行内置单元自检"""
    from tests.test_components import run_all
    ok = run_all()
    sys.exit(0 if ok else 1)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="adaptive_attacker",
        description="L1B3RT4S 深度融合自适应 AI 攻击工具",
    )
    p.add_argument("--corpus-root", help="语料库根目录（默认本包上级目录）")
    sub = p.add_subparsers(dest="command", required=True)

    # corpus
    pc = sub.add_parser("corpus", help="语料库操作")
    pc.add_argument("action", choices=["stats", "list", "sample"])
    pc.add_argument("--provider", default=None)
    pc.set_defaults(func=cmd_corpus)

    # attack
    pa = sub.add_parser("attack", help="单次隐蔽攻击")
    pa.add_argument("--prompt", required=True)
    pa.add_argument("--target", required=True)
    pa.add_argument("--api-key", action="append", default=None)
    pa.add_argument("--proxy", action="append", default=None)
    pa.add_argument("--model", default="gpt-4-turbo")
    pa.add_argument("--attack-type", default="advanced_jailbreak",
                    choices=[a.value for a in AttackType])
    pa.add_argument("--no-encrypt", action="store_true")
    pa.add_argument("--glitch", type=float, default=None)
    pa.add_argument("--provider", default=None)
    pa.add_argument("--passphrase", default="MasterPassword123")
    pa.add_argument("--log", default=None)
    pa.set_defaults(func=cmd_attack)

    # campaign
    pcap = sub.add_parser("campaign", help="批量随机间隔攻击")
    pcap.add_argument("--prompts-file", required=True)
    pcap.add_argument("--target", required=True)
    pcap.add_argument("--api-key", action="append", default=None)
    pcap.add_argument("--proxy", action="append", default=None)
    pcap.add_argument("--model", default="gpt-4-turbo")
    pcap.add_argument("--attack-type", default="advanced_jailbreak",
                      choices=[a.value for a in AttackType])
    pcap.add_argument("--no-encrypt", action="store_true")
    pcap.add_argument("--min-interval", type=float, default=5.0)
    pcap.add_argument("--max-interval", type=float, default=30.0)
    pcap.add_argument("--log", default=None)
    pcap.set_defaults(func=cmd_campaign)

    # distributed
    pd = sub.add_parser("distributed", help="分布式多 worker 攻击")
    pd.add_argument("--prompts-file", required=True)
    pd.add_argument("--target", required=True)
    pd.add_argument("--api-key", action="append", default=None)
    pd.add_argument("--proxy", action="append", default=None)
    pd.add_argument("--model", default="gpt-4-turbo")
    pd.add_argument("--attack-type", default="advanced_jailbreak",
                    choices=[a.value for a in AttackType])
    pd.add_argument("--no-encrypt", action="store_true")
    pd.add_argument("--workers-file", default=None)
    pd.add_argument("--concurrency", type=int, default=4)
    pd.add_argument("--log", default=None)
    pd.set_defaults(func=cmd_distributed)

    # encrypt / decrypt / glitch
    pe = sub.add_parser("encrypt", help="加密/隐写编码")
    pe.add_argument("--text", required=True)
    pe.add_argument("--method", default="base64",
                    choices=["aes", "base64", "rot13", "hex", "nested"],
                    help="aes=本地安全存储; base64/rot13/hex/nested=AI可解码隐写")
    pe.add_argument("--passphrase", default="MasterPassword123")
    pe.add_argument("--raw", action="store_true", help="隐写模式：不附加AI解码指令前缀")
    pe.set_defaults(func=cmd_encrypt)

    pd2 = sub.add_parser("decrypt", help="解密/隐写解码")
    pd2.add_argument("--text", required=True)
    pd2.add_argument("--method", default="base64",
                     choices=["aes", "base64", "rot13", "hex", "nested"])
    pd2.add_argument("--passphrase", default="MasterPassword123")
    pd2.set_defaults(func=cmd_decrypt)

    pg = sub.add_parser("glitch", help="Unicode 同形字/零宽字符混淆")
    pg.add_argument("--text", required=True)
    pg.add_argument("--ratio", type=float, default=0.3)
    pg.add_argument("--mode", dest="obf_mode", default="combined",
                    choices=["homoglyph", "zerowidth", "softhyphen", "combined"])
    pg.set_defaults(func=cmd_glitch)

    # test
    pt = sub.add_parser("test", help="运行内置单元自检")
    pt.set_defaults(func=cmd_test)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
