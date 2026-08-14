#!/usr/bin/env python3
"""本地提交脚本：沿用 dailyMission.answer_question 的点击提交方式。"""

from __future__ import annotations

import argparse
import json
import sys
from time import sleep

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def submit_answer(driver, label: str) -> bool:
    """在当前已打开的答题页上选中选项并提交，逻辑与原 answer_question 一致。"""
    from dailyMission import click_element

    print(f"本地脚本提交答案：{label}")
    option_el = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, label))
    )
    click_element(driver, option_el)
    sleep(0.5)
    submit_el = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//button[@name='submit'][@value='true']"))
    )
    click_element(driver, submit_el)
    print(f"回答提交成功")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="提交论坛每日答题选项")
    parser.add_argument("--label", required=True, help="选项标签，如 a1/a2/a3/a4")
    args = parser.parse_args()
    print("submit_answer.py 需要由调度器在已登录的浏览器会话中调用。")
    print(json.dumps({"label": args.label}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
