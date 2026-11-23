# -*- coding: utf-8 -*-
"""
便捷入口脚本（阶段5-部署）
python run.py corpus stats
python run.py attack --prompt "..." --target https://api.example.com/v1/chat/completions
python run.py test
"""
from adaptive_attacker.cli import main

if __name__ == "__main__":
    main()
