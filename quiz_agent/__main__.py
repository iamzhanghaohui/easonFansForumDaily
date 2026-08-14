from __future__ import annotations

import argparse
import json
import os
import sys

from .agent import answer_quiz
from .settings import AgentSettings, configure


SAMPLE_PROMPT = """题目："曾迷途才怕追不上满街赶路人。"是哪首歌的歌词？

选项：
a3. 人车志
a1. 一个旅人
a4. 人生马拉松
a2. 任我行

请从上述选项中选择一个最合理的答案，并只返回选项标签。"""


def main() -> int:
    parser = argparse.ArgumentParser(description="运行陈奕迅论坛答题 Agent（检索后作答）")
    parser.add_argument("--local", action="store_true", help="从本地 config.json 读取配置")
    parser.add_argument("prompt", nargs="?", help="题面文本；省略则使用内置样例题")
    args = parser.parse_args()

    config = None
    if args.local:
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    configure(AgentSettings.from_mapping(config))
    prompt = args.prompt or SAMPLE_PROMPT
    print(prompt)
    print("---")
    label = answer_quiz(prompt)
    if not label:
        print("未能得到有效答案。")
        return 1
    print(f"结果: {label}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
