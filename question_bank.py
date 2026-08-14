from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

BEIJING = timezone(timedelta(hours=8))
BANK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "question_bank.json")


def normalize_text(text: str) -> str:
    text = (text or "").replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text.strip("\"'“”‘’")


def question_key(question: str, options: Optional[dict[str, str]] = None) -> str:
    payload = normalize_text(question)
    if options:
        option_texts = sorted(normalize_text(v) for v in options.values() if v)
        payload += "\n|" + "|".join(option_texts)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def match_label(option_text: str, options: dict[str, str]) -> Optional[str]:
    target = normalize_text(option_text)
    if not target:
        return None
    for label, text in options.items():
        if normalize_text(text) == target:
            return label
    return None


@dataclass
class BankHint:
    correct_label: Optional[str] = None
    correct_text: Optional[str] = None
    wrong_labels: list[str] = field(default_factory=list)
    wrong_texts: list[str] = field(default_factory=list)
    seen: int = 0


class QuestionBank:
    def __init__(self, path: str = BANK_PATH):
        self.path = path
        self.data = {
            "updated_at": None,
            "stats": {"questions": 0, "records": 0, "correct": 0, "wrong": 0},
            "questions": {},
        }
        self.load()

    def load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self.data.update(loaded)
                self.data.setdefault("stats", {"questions": 0, "records": 0, "correct": 0, "wrong": 0})
                self.data.setdefault("questions", {})
        except Exception as e:
            print(f"题库读取失败，将使用空题库（{type(e).__name__}）: {e}")

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.data["updated_at"] = datetime.now(BEIJING).strftime("%Y-%m-%d %H:%M:%S")
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.path)

    def lookup(self, question: str, options: dict[str, str]) -> BankHint:
        entry = self.data["questions"].get(question_key(question, options))
        if not entry:
            entry = self.data["questions"].get(question_key(question))
        if not entry:
            return BankHint()
        correct_text = entry.get("correct_text")
        wrong_texts = list(entry.get("wrong_texts") or [])
        correct_label = match_label(correct_text, options) if correct_text else None
        matched_wrong = [text for text in wrong_texts if match_label(text, options)]
        return BankHint(
            correct_label=correct_label,
            correct_text=correct_text if correct_label else None,
            wrong_labels=[match_label(text, options) for text in matched_wrong],
            wrong_texts=matched_wrong,
            seen=len(entry.get("history") or []),
        )

    def record(
        self,
        question: str,
        options: dict[str, str],
        chosen_label: str,
        correct: Optional[bool],
        source: str,
        reason: str = "",
    ) -> None:
        key = question_key(question, options)
        entry = self.data["questions"].setdefault(
            key,
            {
                "question": question,
                "correct_text": None,
                "wrong_texts": [],
                "history": [],
            },
        )
        entry["question"] = question
        entry["options_latest"] = options
        chosen_text = options.get(chosen_label, "")
        item = {
            "ts": datetime.now(BEIJING).strftime("%Y-%m-%d %H:%M:%S"),
            "chosen_label": chosen_label,
            "chosen_text": chosen_text,
            "correct": correct,
            "source": source,
            "reason": (reason or "")[:500],
        }
        entry["history"].append(item)
        if correct is True and chosen_text:
            entry["correct_text"] = chosen_text
            if chosen_text in entry["wrong_texts"]:
                entry["wrong_texts"].remove(chosen_text)
        elif correct is False and chosen_text and chosen_text not in entry["wrong_texts"]:
            entry["wrong_texts"].append(chosen_text)
        self._refresh_stats()
        self.save()

    def _refresh_stats(self) -> None:
        records = 0
        correct = 0
        wrong = 0
        for entry in self.data["questions"].values():
            for item in entry.get("history") or []:
                records += 1
                if item.get("correct") is True:
                    correct += 1
                elif item.get("correct") is False:
                    wrong += 1
        self.data["stats"] = {
            "questions": len(self.data["questions"]),
            "records": records,
            "correct": correct,
            "wrong": wrong,
        }

    def summary_lines(self) -> list[str]:
        stats = self.data.get("stats") or {}
        return [
            f"题库累计：{stats.get('questions', 0)} 题，"
            f"作答 {stats.get('records', 0)} 次，"
            f"正确 {stats.get('correct', 0)}，错误 {stats.get('wrong', 0)}。",
        ]

    def search(self, query: str, limit: int = 8) -> str:
        """按题干、选项、已知对错文本检索本地题库。"""
        query_norm = normalize_text(query).lower()
        if not query_norm:
            stats = "\n".join(self.summary_lines())
            return f"{stats}\n请提供题干关键词、歌词或选项文本再查。"

        hits = []
        for entry in (self.data.get("questions") or {}).values():
            question = entry.get("question") or ""
            options = entry.get("options_latest") or {}
            correct_text = entry.get("correct_text") or ""
            wrong_texts = entry.get("wrong_texts") or []
            history = entry.get("history") or []
            haystack_parts = [question, correct_text, *wrong_texts, *options.values()]
            haystack_parts.extend(item.get("chosen_text") or "" for item in history)
            haystack = " ".join(normalize_text(part) for part in haystack_parts).lower()
            if query_norm not in haystack:
                continue
            score = 0
            if query_norm in normalize_text(question).lower():
                score += 3
            if any(query_norm in normalize_text(text).lower() for text in options.values()):
                score += 2
            if query_norm in normalize_text(correct_text).lower():
                score += 4
            hits.append((score, entry))

        if not hits:
            return f"本地题库未命中：{query}"

        hits.sort(key=lambda item: item[0], reverse=True)
        blocks = [f"本地题库命中 {min(len(hits), limit)} / {len(hits)} 条（查询：{query}）"]
        for idx, (_, entry) in enumerate(hits[:limit], 1):
            question = entry.get("question") or "未知题目"
            options = entry.get("options_latest") or {}
            correct_text = entry.get("correct_text")
            wrong_texts = entry.get("wrong_texts") or []
            history = entry.get("history") or []
            option_line = " / ".join(f"{label}.{text}" for label, text in options.items()) or "无"
            last = history[-1] if history else {}
            last_mark = "对" if last.get("correct") is True else ("错" if last.get("correct") is False else "未知")
            last_line = (
                f"{last.get('ts', '')} 选 {last.get('chosen_label', '')} {last.get('chosen_text', '')} [{last_mark}]"
                if last else "无作答记录"
            )
            blocks.append(
                f"[题库{idx}] 题目：{question}\n"
                f"选项：{option_line}\n"
                f"已知正确答案：{correct_text or '尚未记录'}\n"
                f"已知错误选项：{'、'.join(wrong_texts) if wrong_texts else '无'}\n"
                f"最近作答：{last_line}"
            )
        print(f"本地题库检索：命中 {len(hits)} 条，返回 {min(len(hits), limit)} 条。")
        return "\n\n".join(blocks)


if __name__ == "__main__":
    bank = QuestionBank()
    print("\n".join(bank.summary_lines()))
    print(f"文件：{bank.path}")
