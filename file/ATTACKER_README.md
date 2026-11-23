# AdaptiveAIAttacker — L1B3RT4S 深度融合版

> 将原始 `AdaptiveAIAttacker` 代码与本文件夹（`L1B3RT4S-main`）全部内容深度融合，
> 严格按《计划书.txt》五阶段执行。

## 融合点

原始代码硬编码 3 个攻击模板。本版**以整个 L1B3RT4S 语料库作为真实载荷模板源**：

| 语料文件 | 融合方式 |
|---|---|
| `*.mkd`（OPENAI / ANTHROPIC / DEEPSEEK / GOOGLE / GROK 等 40+ 厂商） | 按 `# ` 标题切块 → 结构化模板，含 `{{PAYLOAD}}/{Z}/{user_input}` 占位符自动填充 |
| `TOKEN80M8.mkd`（23MB）/ `TOKENADE.mkd`（1.8MB） | 流式按行分块，避免 OOM |
| `!SHORTCUTS.json` | 命令字典（`{GODMODE:ENABLED}`、`!JAILBREAK`、`!OMNI`…）作为载荷增强前缀 |
| `_SPECIAL_TOKENS.json` | 特殊令牌库注入 |
| `#MOTHERLOAD.txt` | Unicode 标签混淆载荷，作为 txt 类模板 |
| `README.md` / `LICENSE` | 元数据忽略 |

## 五阶段对应

| 阶段 | 计划书内容 | 实现 |
|---|---|---|
| 1 需求和威胁分析 | 审核系统/速率限制/行为分析 | `obfuscation.py` 禁用词替换 + 密钥/代理轮换 + 随机 UA |
| 2 建筑设计 | 5 大组件 | `corpus/payload/crypto/glitch/obfuscation/manager/distributed` |
| 3 技术实施 | 步骤1-5 | 全部模块代码 + `requirements.txt` |
| 4 测试与调整 | 单元/集成/自适应 | `tests/test_components.py`（7 项自检） |
| 5 部署和持续改进 | CLI/更新/分布式 | `cli.py` + `distributed.py` |

## 安装

```bash
cd L1B3RT4S-main
pip install -r requirements.txt
```

## 使用

```bash
# 语料库统计
python -m adaptive_attacker corpus stats
python -m adaptive_attacker corpus list

# 单次隐蔽攻击
python -m adaptive_attacker attack \
  --prompt "你的提示" \
  --target https://api.example.com/v1/chat/completions \
  --api-key sk-xxx \
  --attack-type advanced_jailbreak

# 批量随机间隔攻击（规避行为分析）
python -m adaptive_attacker campaign \
  --prompts-file prompts.txt \
  --target https://... \
  --api-key sk-xxx

# 分布式多 worker 攻击
python -m adaptive_attacker distributed \
  --prompts-file prompts.txt \
  --target https://... \
  --workers-file workers.json \
  --concurrency 8

# 工具
python -m adaptive_attacker encrypt --text "secret"
python -m adaptive_attacker decrypt --text "<base85-token>"
python -m adaptive_attacker glitch --text "hello world" --ratio 0.1

# 自检
python -m adaptive_attacker test
```

## 自适应学习

攻击管理器在每次攻击后：
1. 根据近 5 次成功率动态调整故障注射比例（5%–15%）
2. 更新语料库模板权重（成功↑/失败↓），影响后续模板抽取概率

## 架构

```
adaptive_attacker/
├── __init__.py        包入口
├── __main__.py        python -m 入口
├── corpus.py          语料库加载器（扫描全部 .mkd/.txt/.json）
├── payload.py         载荷生成器（语料模板 + 攻击型封装器）
├── crypto.py          军用加密 AES-256-GCM + PBKDF2 + Base85
├── glitch.py          NLP 故障注入（numpy，5-15%可调）
├── obfuscation.py     混淆系统（密钥/代理/UA轮换 + 审核绕过）
├── manager.py         攻击管理器（随机间隔/日志/自适应学习）
├── distributed.py     分布式多 worker 调度
└── cli.py             命令行界面
tests/
└── test_components.py 7 项单元/集成自检
run.py                 便捷入口
requirements.txt       依赖
```
