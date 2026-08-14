from __future__ import annotations

import re
from typing import Optional

from agents import (
    Agent,
    ModelSettings,
    OpenAIChatCompletionsModel,
    Runner,
    set_tracing_disabled,
)
from openai import AsyncOpenAI

from .settings import get_settings
from .tools import search_bank, search_site, search_web

VALID_OPTIONS = ("a1", "a2", "a3", "a4")

INSTRUCTIONS = """你是陈奕迅粉丝论坛每日答题助手。必须先检索再作答，禁止不查资料直接猜。

可用工具：
- search_bank：查询本地题库里做过的题、已知正确答案和错误选项。优先使用。
- search_site：优先在 easonfans.com 检索歌词、歌名、专辑、演出资料。
- search_web：全网多轮检索（自动补检索词交叉验证）。站内不足、或要对选项逐一核实时使用。

检索策略：
1. 先用 search_bank 查本地题库；若命中且正确答案能对应到当前选项，直接采用。
2. 题库未命中或只有错误选项时，再根据题目抽出关键词搜索。
3. 歌词题用完整歌词句检索；歌名/专辑题用「歌名 陈奕迅」或「歌名 专辑」。
4. 「哪首不是 / 哪项错误」类题：对每个选项分别 search_web（例如「歌名 陈奕迅」），用能否搜到可靠资料来交叉判断。
5. search_web 单次调用会自动做 2～3 轮补充检索；若结果仍矛盾，换更短关键词再搜一次。
6. 以可核对的资料为准，忽略明显广告、无关视频标题和噪声。
7. 四个选项里选一个最有依据的答案；题库里记过的错误选项不要再选。

输出要求：
- 先用一两句话说明依据。
- 最后单独一行：ANSWER: a1
- ANSWER 只能是 a1、a2、a3、a4 之一。
"""


def build_agent() -> Agent:
    settings = get_settings()
    if not settings.api_key:
        raise RuntimeError("未配置 API_KEY，无法创建答题 Agent")

    set_tracing_disabled(disabled=True)
    client = AsyncOpenAI(api_key=settings.api_key, base_url=settings.llm_base_url)
    return Agent(
        name="EasonQuizAgent",
        instructions=INSTRUCTIONS,
        model=OpenAIChatCompletionsModel(
            model=settings.llm_model,
            openai_client=client,
        ),
        tools=[search_bank, search_site, search_web],
        model_settings=ModelSettings(temperature=0, tool_choice="auto"),
    )


def _extract_label(text: str) -> Optional[str]:
    if not text:
        return None
    answer_match = re.search(r"ANSWER\s*[:：]\s*(a[1-4])\b", text, re.IGNORECASE)
    if answer_match:
        return answer_match.group(1).lower()
    matches = re.findall(r"\ba[1-4]\b", text.lower())
    if matches:
        return matches[-1]
    return None


def _log_tool_calls(result) -> None:
    try:
        for item in getattr(result, "new_items", []) or []:
            raw = getattr(item, "raw_item", None)
            name = getattr(raw, "name", None)
            if not name:
                continue
            args = getattr(raw, "arguments", "")
            print(f"[Agent] 工具调用 {name}({args})")
    except Exception:
        return


def answer_quiz(prompt: str) -> Optional[str]:
    """运行检索 Agent，成功返回 a1-a4，失败返回 None。"""
    settings = get_settings()
    agent = build_agent()
    user_input = (
        f"{prompt.strip()}\n\n"
        "请先检索再作答。如果提供了本地题库提示，必须优先采信。"
        "最后一行输出 ANSWER: a1/a2/a3/a4。"
    )
    print(
        f"启动答题 Agent（model={settings.llm_model}, "
        f"max_turns={settings.max_turns}, backend={settings.search_backend}）"
    )
    try:
        result = Runner.run_sync(agent, user_input, max_turns=settings.max_turns)
    except Exception as e:
        print(f"Agent 运行失败（{type(e).__name__}）: {e}")
        return None

    _log_tool_calls(result)
    raw_text = str(getattr(result, "final_output", "") or "")
    if raw_text:
        preview = raw_text.strip().replace("\n", " ")
        print(f"Agent 最终输出: {preview[:300]}")
    label = _extract_label(raw_text)
    if label in VALID_OPTIONS:
        print(f"Agent 返回的答案标签: {label}")
        return label
    print("Agent 未返回有效选项标签。")
    return None
