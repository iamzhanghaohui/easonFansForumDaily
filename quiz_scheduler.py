from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from question_bank import QuestionBank
from quiz_agent import answer_quiz
from submit_answer import submit_answer

QUIZ_URL = "https://www.easonfans.com/forum/plugin.php?id=ahome_dayquestion:index"


@dataclass
class QuizItemResult:
    index: int
    question: str
    options: dict[str, str]
    label: Optional[str]
    choice_text: str = ""
    source: str = ""
    reason: str = ""
    correct: Optional[bool] = None
    ok: bool = False
    skipped: bool = False


@dataclass
class QuizRunResult:
    items: list[QuizItemResult] = field(default_factory=list)
    already_done: bool = False
    participated: int = 0
    total: int = 3
    skip_reason: str = ""

    @property
    def attempted(self) -> int:
        return sum(1 for item in self.items if item.ok)

    @property
    def correct_count(self) -> int:
        return sum(1 for item in self.items if item.correct is True)

    @property
    def wrong_count(self) -> int:
        return sum(1 for item in self.items if item.correct is False)

    @property
    def correct_rate(self) -> Optional[float]:
        if self.attempted <= 0:
            return None
        return self.correct_count / self.attempted


def _read_totals(driver) -> tuple[int, int]:
    page_source = driver.page_source
    total_answered_match = re.search(r"累计答题:\s*(\d+)", page_source)
    total_correct_match = re.search(r"累计答对:\s*(\d+)", page_source)
    total_answer = int(total_answered_match.group(1)) if total_answered_match else 0
    total_correct = int(total_correct_match.group(1)) if total_correct_match else 0
    return total_answer, total_correct


def _fields_from_prompt(prompt: str) -> tuple[str, dict[str, str]]:
    question = ""
    options: dict[str, str] = {}
    for line in prompt.splitlines():
        text = line.strip()
        if text.startswith("题目："):
            question = text.replace("题目：", "", 1).strip()
        match = re.match(r"^(a[1-4])\.\s*(.*)$", text)
        if match:
            options[match.group(1)] = match.group(2)
    return question, options


def _ask_agent(prompt: str, hint) -> tuple[Optional[str], str]:
    extra_lines = []
    if hint.correct_label and hint.correct_text:
        extra_lines.append(f"本地题库已记录正确答案：{hint.correct_text}")
    if hint.wrong_texts:
        extra_lines.append("本地题库已验证为错误的选项：" + "、".join(hint.wrong_texts))
    extra = "\n".join(extra_lines)
    if extra:
        prompt = prompt + "\n\n" + extra
        print(extra)
    label = answer_quiz(prompt)
    return label, extra


def _mark_skip(result: QuizRunResult, reason: str, item: Optional[QuizItemResult] = None) -> None:
    result.skip_reason = reason
    if item is not None:
        item.skipped = True
        item.ok = False
        if reason and reason not in (item.reason or ""):
            item.reason = f"{item.reason}；{reason}" if item.reason else reason
    print(f"跳过后续答题：{reason}")


def run_quiz(driver) -> QuizRunResult:
    """取题/进度完全沿用 dailyMission.question 的原流程，中间插入 Agent 与本地提交。"""
    from dailyMission import build_prompt

    print("=== 答题调度开始 ===")
    bank = QuestionBank()
    result = QuizRunResult()

    driver.get(QUIZ_URL)
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "inner"))
        )
    except Exception as e:
        _mark_skip(result, f"答题页加载失败，已跳过，请稍后手动重试（{type(e).__name__}: {e}）")
        print("\n=== 今日答题小结 ===")
        print(format_quiz_summary(result, bank))
        print("=== 答题调度结束 ===")
        return result

    initial_answer, initial_correct = _read_totals(driver)
    pending_item: Optional[QuizItemResult] = None
    pending_before: Optional[tuple[int, int]] = None

    while True:
        driver.get(QUIZ_URL)
        try:
            participated_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "inner"))
            )
        except Exception as e:
            _mark_skip(
                result,
                f"答题页加载失败，已跳过，请稍后手动重试（{type(e).__name__}: {e}）",
                pending_item,
            )
            break

        matches = re.search(r"\((\d+)/(\d+)\)", participated_element.text)
        if not matches:
            _mark_skip(result, "无法读取今日答题进度，已跳过，请稍后手动重试", pending_item)
            break
        participated, total = map(int, matches.groups())
        result.participated = participated
        result.total = total
        current_answer, current_correct = _read_totals(driver)

        if pending_item is not None and pending_before is not None:
            answered = current_answer > pending_before[0] or participated > pending_item.index - 1
            if current_correct > pending_before[1]:
                pending_item.correct = True
            elif answered:
                pending_item.correct = False
            pending_item.ok = bool(answered)
            bank.record(
                question=pending_item.question,
                options=pending_item.options,
                chosen_label=pending_item.label or "",
                correct=pending_item.correct,
                source=pending_item.source,
                reason=pending_item.reason,
            )
            mark = "对" if pending_item.correct else ("错" if pending_item.correct is False else "未知")
            print(f"已写入题库：第 {pending_item.index} 题 [{mark}] {pending_item.label} {pending_item.choice_text}")
            if not answered:
                _mark_skip(
                    result,
                    f"第 {pending_item.index} 题提交失败（页面未更新），已跳过，请稍后手动重试",
                    pending_item,
                )
                pending_item = None
                pending_before = None
                break
            pending_item = None
            pending_before = None

        if participated >= total:
            if not result.items:
                result.already_done = True
            if current_answer > initial_answer:
                rate = (current_correct - initial_correct) / (current_answer - initial_answer)
                print(f"今日答题已完成，答题正确率 {rate * 100:.2f}%。总正确数/答题数：{current_correct}/{current_answer}。")
            else:
                print(f"今日答题已完成。总正确数/答题数：{current_correct}/{current_answer}。")
            break

        index = participated + 1
        if any(item.index == index for item in result.items):
            _mark_skip(result, f"第 {index} 题已尝试过，不再重复提交，请稍后手动重试")
            break

        try:
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@name='submit'][@value='true']"))
            )
        except Exception as e:
            _mark_skip(
                result,
                f"第 {index} 题加载失败（提交按钮不可用），已跳过，请稍后手动重试（{type(e).__name__}: {e}）",
            )
            result.items.append(
                QuizItemResult(
                    index=index,
                    question="",
                    options={},
                    label=None,
                    skipped=True,
                    reason=result.skip_reason,
                )
            )
            break

        try:
            prompt = build_prompt(driver)
            question_text, options = _fields_from_prompt(prompt)
            if not question_text or not options:
                raise ValueError("题目或选项为空")
        except Exception as e:
            _mark_skip(
                result,
                f"第 {index} 题加载失败，已跳过，请稍后手动重试（{type(e).__name__}: {e}）",
            )
            result.items.append(
                QuizItemResult(
                    index=index,
                    question="",
                    options={},
                    label=None,
                    skipped=True,
                    reason=result.skip_reason,
                )
            )
            break

        print(f"\n--- 调度第 {index}/{total} 题 ---")
        print("1. 已获取题目，告诉 Agent：")
        print(prompt)

        hint = bank.lookup(question_text, options)
        if hint.correct_label:
            label = hint.correct_label
            source = "题库"
            reason = f"本地题库已记录正确答案：{hint.correct_text}"
            print(f"2. 题库命中，直接使用 {label} {options.get(label, '')}")
        else:
            print("2. 题库未命中正确答案，启动 Agent 检索作答。")
            label, reason = _ask_agent(prompt, hint)
            source = "agent"
            if not label:
                unused = [item for item in options if item not in hint.wrong_labels]
                label = (unused or list(options) or ["a1"])[0]
                source = "fallback"
                reason = "Agent 未返回有效答案，使用备选选项"
                print(f"Agent 无结果，使用备选选项 {label}")

        print(f"3. Agent 拿到答案后，调用本地脚本 submit_answer.py 提交 {label}")
        before_totals = _read_totals(driver)
        ok = False
        try:
            ok = bool(submit_answer(driver, label))
        except Exception as e:
            print(f"本地脚本提交失败（{type(e).__name__}）: {e}")

        item = QuizItemResult(
            index=index,
            question=question_text,
            options=options,
            label=label,
            choice_text=options.get(label, ""),
            source=source,
            reason=reason,
            ok=ok,
        )
        result.items.append(item)
        if not ok:
            bank.record(question_text, options, label, None, source, reason)
            _mark_skip(
                result,
                f"第 {index} 题提交失败，已跳过，请稍后手动重试",
                item,
            )
            break
        pending_item = item
        pending_before = before_totals

    print("\n=== 今日答题小结 ===")
    print(format_quiz_summary(result, bank))
    print("=== 答题调度结束 ===")
    return result


def format_quiz_summary(result: QuizRunResult, bank: Optional[QuestionBank] = None) -> str:
    bank = bank or QuestionBank()
    lines = [f"今日进度：{result.participated}/{result.total}"]
    if result.skip_reason:
        lines.append(f"已跳过：{result.skip_reason}")
        lines.append("有空请手动打开论坛，重试未完成的题目。")
    if result.already_done and not result.items:
        lines.append("本次未新作答，题目此前已完成。")
    else:
        lines.append(
            f"本次作答：{result.attempted} 题，正确 {result.correct_count}，错误 {result.wrong_count}。"
        )
        if result.correct_rate is not None:
            lines.append(f"本次正确率：{result.correct_rate * 100:.2f}%")
        for item in result.items:
            if item.skipped:
                mark = "跳过"
            elif item.correct is True:
                mark = "对"
            elif item.correct is False:
                mark = "错"
            else:
                mark = "?"
            title = item.question or "题目未加载"
            choice = f"{item.label} {item.choice_text}".strip() if item.label else "未提交"
            source = f"（来源：{item.source}）" if item.source else ""
            lines.append(f"{item.index}. [{mark}] {title}\n   选择 {choice}{source}")
            if item.reason:
                lines.append(f"   依据：{item.reason}")
    lines.extend(bank.summary_lines())
    return "\n".join(lines)
