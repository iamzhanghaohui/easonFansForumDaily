from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, SessionNotCreatedException
from time import sleep
import re
import os
import argparse
import json
import time
import urllib.error
import urllib.request
from PIL import Image
from io import BytesIO
import pytesseract
import base64
import shutil

import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
import io
import sys
from functools import partial
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from openai import OpenAI

username = None
password = None
mail_user = None
mail_pass = None
api_key = None
search_api_key = None
llm_base_url = "https://tokenhub.tencentmaas.com/v1"
llm_model = "hy3"
search_api_url = "https://api.wsa.cloud.tencent.com/SearchPro"
search_mode = None
search_cnt = 50
search_max_items = 24
search_passage_chars = 1200
search_site = "easonfans.com"
search_site_min_items = 3

def parse_optional_int(value, default=None):
    if value is None:
        return default
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return default
    try:
        return int(text)
    except ValueError:
        return default

def login(driver):
    try:
        driver.get("https://www.easonfans.com/FORUM/member.php?mod=logging&action=login")

        # verify_img = WebDriverWait(driver, 5).until(
        #     EC.presence_of_element_located((By.CLASS_NAME, "verifyimg"))
        # )

        # img_url = verify_img.get_attribute("src")

        # base64_data = img_url.split(',')[1]

        # image_data = base64.b64decode(base64_data)
        # image = Image.open(BytesIO(image_data))

        # image.save("debug_verify_code.png")
        # print("[调试] 验证码图片已保存为 debug_verify_code.png")

        # code = pytesseract.image_to_string(image)
        # print(f"识别的验证码: {code.strip()}")
        time.sleep(1)

        # input_box = driver.find_element(By.ID, "intext")
        # input_box.send_keys(code)

        # 填写登录表单
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        driver.find_element(By.NAME, "username").send_keys(username)
        driver.find_element(By.NAME, "password").send_keys(password)
        driver.find_element(By.NAME, "loginsubmit").click()

        # 检查是否登录成功
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "umLogin"))
        )
        print("登录成功！")
        return True

    except Exception as e:
        print(f"登录过程中出现错误")
        # return e
        # driver.quit()

def signin(driver):
    # 导航到签到页面
    driver.get("https://www.easonfans.com/forum/plugin.php?id=dsu_paulsign:sign")
    
    # 检查是否有徽章弹窗
    try:
        badge_element = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "fwin_badgewin_7ree"))
        )
        if badge_element:
            print("徽章弹窗出现，准备领取徽章。")
            # 打开徽章领取页面
            driver.get("https://www.easonfans.com/forum/plugin.php?id=badge_7ree:badge_7ree&code=1")

            
            button = driver.find_element("css selector", 'a[href*="plugin.php?id=badge_7ree"]')
            before_click_content = driver.page_source  # 记录点击前页面内容
            button.click()  # 点击领取按钮
            WebDriverWait(driver, 5).until(
                EC.staleness_of(badge_element)  # 等待元素失效（通常意味着页面刷新）
            )
            after_click_content = driver.page_source  # 记录点击后页面内容

            if before_click_content != after_click_content:
                print("徽章领取成功！")
            else:
                print("徽章领取失败。")

    except TimeoutException:
        print("没有徽章弹窗。")
    
    # 导航到签到页面
    driver.get("https://www.easonfans.com/forum/plugin.php?id=dsu_paulsign:sign")
    
    # 开始签到流程
    try:
        # 检查是否已经签到或签到未开始
        message_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//h1[contains(text(), '您今天已经签到过了或者签到时间还未开始')]"))
        )
        print("今天已签到或签到未开始。")
    except TimeoutException:
        # 签到按钮可点击，开始签到流程
        try:
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//a[@onclick=\"showWindow('qwindow', 'qiandao', 'post', '0');return false\"]"))
            )

            # 点击签到触发元素
            li_element = driver.find_element(By.ID, "kx")
            li_element.click()

            radio_button = driver.find_element(By.CSS_SELECTOR, "input[type='radio'][name='qdmode'][value='3']")
            radio_button.click()

            link = driver.find_element(By.XPATH, "//a[@onclick=\"showWindow('qwindow', 'qiandao', 'post', '0');return false\"]")
            link.click()

            # 重新检查是否签到成功
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//h1[contains(text(), '您今天已经签到过了或者签到时间还未开始')]"))
                )
                print("签到成功！")
            except TimeoutException:
                print("签到失败。")
        except Exception as e:
            print(f"签到过程中出现错误。")



def click_element(driver, element):
    """普通点击失败时用 JS 点击兜底。"""
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        element.click()
    except Exception:
        driver.execute_script("arguments[0].click();", element)

def question(driver):
    base_url = "https://www.easonfans.com/forum/plugin.php?id=ahome_dayquestion:index"
    global _api_call_count
    _api_call_count = 0
    MAX_API_CALLS = 12
    MAX_QUESTION_RETRIES = 3

    driver.get(base_url)
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "inner"))
        )
    except Exception as e:
        print(f"页面加载失败: {e}")

    try:
        page_source = driver.page_source
        total_answered_match = re.search(r"累计答题:\s*(\d+)", page_source)
        total_correct_match = re.search(r"累计答对:\s*(\d+)", page_source)
        initial_answer = int(total_answered_match.group(1)) if total_answered_match else 0
        initial_correct = int(total_correct_match.group(1)) if total_correct_match else 0
    except Exception as e:
        print(f"无法提取初始答题信息: {e}")
        initial_answer = 0
        initial_correct = 0

    correct_rate = None
    previous_participated = -1
    question_retry_count = 0
    while True:
        driver.get(base_url)
        try:
            participated_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "inner"))
            )
        except Exception as e:
            print(f"页面加载失败: {e}")
            break

        matches = re.search(r"\((\d+)/(\d+)\)", participated_element.text)
        if not matches:
            print("无法读取今日答题进度。")
            break
        participated, total = map(int, matches.groups())

        if previous_participated >= 0 and participated == previous_participated + 1:
            _api_call_count = 0
            question_retry_count = 0
        previous_participated = participated

        if participated >= total:
            try:
                page_source = driver.page_source
                total_answered_match = re.search(r"累计答题:\s*(\d+)", page_source)
                total_correct_match = re.search(r"累计答对:\s*(\d+)", page_source)
                final_answer = int(total_answered_match.group(1)) if total_answered_match else 0
                final_correct = int(total_correct_match.group(1)) if total_correct_match else 0
            except Exception as e:
                print(f"无法提取最终答题信息: {e}")
                final_answer = initial_answer
                final_correct = initial_correct

            if final_answer > initial_answer:
                correct_rate = (final_correct - initial_correct) / (final_answer - initial_answer)
                print(f"今日答题已完成，答题正确率 {correct_rate * 100:.2f}%。总正确数/答题数：{final_correct}/{final_answer}。")
            else:
                print(f"今日答题已完成。总正确数/答题数：{final_correct}/{final_answer}。")
            break

        if _api_call_count >= MAX_API_CALLS:
            print(f"单次运行 API 调用已达 {MAX_API_CALLS} 次，跳过后续答题")
            correct_rate = quiz_correct_rate(driver, initial_answer, initial_correct)
            break

        if question_retry_count >= MAX_QUESTION_RETRIES:
            print(f"第 {participated + 1} 题已重试 {MAX_QUESTION_RETRIES} 次仍失败，跳过后续答题")
            correct_rate = quiz_correct_rate(driver, initial_answer, initial_correct)
            break

        try:
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@name='submit'][@value='true']"))
            )
            use_api = question_retry_count == 0
            answer_question(
                driver,
                participated,
                fallback_index=question_retry_count,
                use_api=use_api,
            )
        except Exception as e:
            question_retry_count += 1
            print(f"答题第 {participated + 1} 题失败（第 {question_retry_count}/{MAX_QUESTION_RETRIES} 次）: {type(e).__name__}: {e}")
            sleep(3)
            continue

    return correct_rate

def quiz_correct_rate(driver, initial_answer, initial_correct):
    """根据本次运行前后的累计答题数计算正确率，无法计算时返回 None。"""
    try:
        page_source = driver.page_source
        total_answered_match = re.search(r"累计答题:\s*(\d+)", page_source)
        total_correct_match = re.search(r"累计答对:\s*(\d+)", page_source)
        final_answer = int(total_answered_match.group(1)) if total_answered_match else initial_answer
        final_correct = int(total_correct_match.group(1)) if total_correct_match else initial_correct
    except Exception:
        return None
    answered = final_answer - initial_answer
    if answered <= 0:
        return None
    return (final_correct - initial_correct) / answered

def answer_question(driver, question_number, fallback_index=0, use_api=True):
    """答一题：首次调 API；重试时轮换选项，不再重复调 API。"""
    options = ['a1', 'a2', 'a3', 'a4']
    prompt = build_prompt(driver)
    print(f"\n--- 第 {question_number + 1} 题题面 ---")
    print(prompt)

    if use_api:
        label = get_answer_from_api(prompt)
        if label is None:
            label = options[fallback_index % len(options)]
            print(f"API 返回异常，使用备选选项: {label}")
    else:
        label = options[fallback_index % len(options)]
        print(f"跳过重试 API，使用备选选项（第 {fallback_index + 1} 次）: {label}")

    option_el = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, label))
    )
    click_element(driver, option_el)
    sleep(0.5)
    submit_el = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//button[@name='submit'][@value='true']"))
    )
    click_element(driver, submit_el)
    print(f"回答第 {question_number + 1} 题成功")

def build_prompt(driver):
    # 获取页面 HTML 内容
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')

    # 1. 提取题目内容
    b_tag = soup.find('b', string=lambda s: s and '【题目】' in s)

    # b标签的父节点通常是font或span，拿父节点的所有文本内容
    parent_tag = b_tag.parent

    # 拿父标签内全部文本，去除【题目】及前后空白符
    full_text = parent_tag.get_text(separator='', strip=True)
    full_text = full_text.replace('【题目】', '').replace('\xa0', ' ').strip()

    # 2. 提取选项内容（ID 和 文本）
    options = []
    option_divs = soup.find_all('div', class_='qs_option')
    for div in option_divs:
        input_tag = div.find('input')
        label = input_tag.get('id') if input_tag else 'unknown'
        # 取整段文本，剔除 &nbsp;&nbsp; 或空格
        raw_text = div.get_text(strip=True).replace('\xa0', ' ')
        # 去掉可能的前缀（如 “a1. ”）
        text = raw_text.split(' ', 1)[-1] if ' ' in raw_text else raw_text
        options.append((label, text))

    # 3. 构建 prompt
    prompt = f"题目：{full_text}\n\n选项：\n"
    for label, text in options:
        prompt += f"{label}. {text}\n"
    prompt += "\n请从上述选项中选择一个最合理的答案，并只返回选项标签。"

    return prompt

def build_search_query(prompt, include_options=True):
    """从题目 prompt 中提取查询词，避免直接把整段提示词当搜索词。"""
    lines = [line.strip() for line in prompt.splitlines() if line.strip()]
    question = ""
    options = []

    for line in lines:
        if line.startswith("题目："):
            question = line.replace("题目：", "", 1).strip()
        elif re.match(r"^a[1-4]\.\s*", line):
            options.append(line)

    if not question and lines:
        question = lines[0]

    if include_options:
        query = f"{question} {' '.join(options)}".strip()
    else:
        query = question.strip()
    return query[:500]

def search_wsa(query, mode=None, cnt=None, max_items=None, site=None):
    """调用腾讯 WSA 搜索 API，返回解析后的结果列表。"""
    if not search_api_key:
        return []

    effective_mode = search_mode if mode is None else mode
    effective_cnt = search_cnt if cnt is None else cnt
    effective_max_items = search_max_items if max_items is None else max_items

    payload = {
        "Query": query,
        "Cnt": effective_cnt,
    }
    if effective_mode in (0, 1, 2):
        payload["Mode"] = effective_mode
    if site:
        # Mode=1 下 Site 无效，站内搜索时强制走自然结果
        if payload.get("Mode") == 1:
            payload["Mode"] = 0
        payload["Site"] = site
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url=search_api_url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {search_api_key}",
            "Content-Type": "application/json; charset=UTF-8",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
        result = json.loads(body)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        print(f"WSA 搜索 HTTP 错误: {e.code}, {err_body[:200]}")
        return []
    except Exception as e:
        print(f"WSA 搜索调用失败（{type(e).__name__}）: {e}")
        return []

    pages = result.get("Response", {}).get("Pages", [])
    parsed_pages = []
    for raw in pages[:effective_max_items]:
        if isinstance(raw, str):
            try:
                parsed_pages.append(json.loads(raw))
            except json.JSONDecodeError:
                parsed_pages.append({"passage": raw})
        elif isinstance(raw, dict):
            parsed_pages.append(raw)
    return parsed_pages

def collect_search_pages(queries, site=None, seen=None, limit=None):
    """按查询列表收集去重后的搜索结果。"""
    if seen is None:
        seen = set()
    if limit is None:
        limit = search_max_items
    merged_pages = []
    for query in queries:
        if not query:
            continue
        pages = search_wsa(query, site=site)
        for page in pages:
            dedup_key = (
                (page.get("url") or "").strip(),
                (page.get("title") or "").strip(),
            )
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            merged_pages.append(page)
            if len(merged_pages) >= limit:
                return merged_pages
    return merged_pages

def enrich_prompt_with_search(prompt):
    """将搜索结果拼接到 prompt：优先站内，不足再全网兜底。"""
    queries = [
        build_search_query(prompt, include_options=True),
        build_search_query(prompt, include_options=False),
    ]
    seen = set()
    site_pages = []
    if search_site:
        site_pages = collect_search_pages(queries, site=search_site, seen=seen)
        print(f"站内搜索（{search_site}）：命中 {len(site_pages)} 条。")

    web_pages = []
    if len(site_pages) < search_site_min_items:
        remain = search_max_items - len(site_pages)
        web_pages = collect_search_pages(queries, site=None, seen=seen, limit=remain)
        print(f"全网兜底：补充 {len(web_pages)} 条。")
    elif len(site_pages) < search_max_items:
        # 站内已够用，但保留少量全网补充，避免站内噪声时完全无对照
        remain = min(3, search_max_items - len(site_pages))
        web_pages = collect_search_pages(queries, site=None, seen=seen, limit=remain)
        if web_pages:
            print(f"站内优先：额外补充全网 {len(web_pages)} 条。")

    pages = site_pages + web_pages
    if not pages:
        print("搜索参考：未命中结果，使用原始题面。")
        return prompt

    print(f"搜索参考：共 {len(pages)} 条（站内 {len(site_pages)} / 全网 {len(web_pages)}），已拼接进提示词。")
    refs = []
    for idx, page in enumerate(pages, 1):
        title = (page.get("title") or "").strip()
        passage = (page.get("passage") or "").strip()
        url = (page.get("url") or "").strip()
        source_tag = "站内" if idx <= len(site_pages) else "全网"
        print(f"[参考{idx}/{source_tag}] {title or '未知标题'} | {url or '未知来源'}")
        refs.append(
            f"[参考{idx}/{source_tag}] 标题: {title or '未知'}\n"
            f"摘要: {passage[:search_passage_chars]}\n"
            f"来源: {url or '未知'}"
        )

    extra = (
        "\n\n以下是联网搜索参考资料（站内结果优先；可能有噪声，请自行甄别）：\n"
        + "\n\n".join(refs)
        + "\n\n请综合题目和参考资料，返回最合理的选项标签（只能是 a1/a2/a3/a4）。"
    )
    return prompt + extra

def get_answer_from_api(prompt):
    """单次调用 API，成功返回 a1-a4，失败返回 None。"""
    global _api_call_count
    _api_call_count += 1

    client = OpenAI(api_key=api_key, base_url=llm_base_url)
    valid_options = ['a1', 'a2', 'a3', 'a4']
    enhanced_prompt = enrich_prompt_with_search(prompt)

    try:
        response = client.chat.completions.create(
            model=llm_model,
            messages=[
                {"role": "user", "content": enhanced_prompt},
            ],
        )
    except Exception as e:
        print(f"API 调用失败（{type(e).__name__}）: {e}")
        return None

    raw_text = None
    if hasattr(response, "choices") and response.choices:
        raw_text = getattr(response.choices[0].message, "content", None)
    if not raw_text:
        print("API 未返回有效内容")
        return None

    match = re.search(r'\ba[1-4]\b', raw_text)
    label = (match.group(0).strip() if match else None)
    if label and label in valid_options:
        print(f"API 返回的答案标签: {label}")
        return label
    print(f"API 未返回有效结果或结果不在合法选项中（{raw_text[:50] if raw_text else '无'}...）")
    return None

def check_free_lottery(driver):
    driver.get("https://www.easonfans.com/forum/plugin.php?id=gplayconstellation:front")
    try:
        # 等待并检查是否还有剩余的免费抽奖次数
        message_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//span[contains(text(), '今日剩余免费次数：0次')]"))
        )
        return False  # 没有剩余免费抽奖次数
    except:
        return True  # 还有剩余免费抽奖次数

def lottery(driver):
    if not check_free_lottery(driver):
        print("今天已免费抽奖。")
        return

    # 等待抽奖按钮可点击并点击
    
    try:
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "pointlevel"))
        ).click()
        print("开始免费抽奖。")
        sleep(5)  # 等待抽奖结果

        # 重新检查是否抽奖成功
        if not check_free_lottery(driver):
            print("免费抽奖成功！")
        else:
            print("免费抽奖失败。")
    except Exception as e:
        print(f"抽奖过程中出现错误。")

def getMoney(driver):
    driver.get("https://www.easonfans.com/forum/home.php?mod=spacecp&ac=credit&showcredit=1")
    try:
        money_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//li[@class='xi1 cl']"))
        )
        money_text = money_element.text
        money_amount = [int(s) for s in money_text.split() if s.isdigit()][0]  # 提取数字并假设第一个数字为金钱数额
        return money_amount
    except Exception as e:
        print(f"获取金钱失败。")
        return 0
    
def sendEmail(msg, subject):
    sender = receiver = mail_user
    message = MIMEText(msg, 'plain', 'utf-8')
    message['From'] = formataddr(("Daily mission Assitance", sender))
    message['To'] = formataddr(("Tanner", receiver))
    message['Subject'] = Header(subject, 'utf-8')
    try:
        server=smtplib.SMTP_SSL("smtp.qq.com", 465)
        server.login(mail_user,mail_pass)  
        server.sendmail(sender,[receiver],message.as_string())
        print ("邮件发送成功。")
        server.quit()  # 关闭连接
    except smtplib.SMTPException as e:
        print(f"邮件发送失败。")

class TeeOutput:
    """同时写入控制台和缓冲区，实现实时输出且保留内容用于邮件"""
    def __init__(self, console, buffer):
        self.console = console
        self.buffer = buffer

    def write(self, data):
        self.console.write(data)
        self.buffer.write(data)

    def flush(self):
        self.console.flush()
        self.buffer.flush()

def capture_output(func, tee=False):
    # tee=True：同时输出到控制台和缓冲区（实时看到 print）
    # tee=False：只写入缓冲区（用于远程无界面时发邮件）
    buffer = io.StringIO()
    if tee:
        sys.stdout = TeeOutput(sys.__stdout__, buffer)
    else:
        sys.stdout = buffer
    try:
        result = func()
    finally:
        sys.stdout = sys.__stdout__
    return buffer.getvalue(), result
    
def merge(headless: bool, local: bool, chromedriver_path: str):
    global username, password, mail_user, mail_pass

    # 模拟浏览器打开网站
    chrome_options = webdriver.ChromeOptions()
    chrome_candidates = [
        os.environ.get("CHROME_BINARY", "").strip(),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    for candidate in chrome_candidates:
        if candidate and os.path.exists(candidate):
            chrome_options.binary_location = candidate
            break
    if headless:
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    # 关闭 GCM/推送等后台网络，避免 DEPRECATED_ENDPOINT 等无关报错刷屏
    chrome_options.add_argument('--disable-background-networking')
    chrome_options.add_argument('--disable-sync')
    chrome_options.add_argument('--disable-default-apps')
    
    # First try the explicitly provided driver path. If its version does not
    # match the installed browser, fall back to Selenium Manager auto-resolution.
    try:
        service = Service(executable_path=chromedriver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except SessionNotCreatedException:
        print("本地 chromedriver 与 Chrome 版本不匹配，切换为 Selenium 自动匹配驱动。")
        driver = webdriver.Chrome(options=chrome_options)

    beijing_tz = timezone(timedelta(hours=8))
    now_str = datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")
    if local:
        print(f"=== Script for {username} started at {now_str} locally===")
    else:
        print(f"=== Script for {username} started at {now_str} remotely===")

    login_success = False
    while not login_success:
        login_success = login(driver)
        if login_success:
            break
        else:
            print("重新尝试登录...")
            sleep(5)
    initial_money = getMoney(driver)
    signin(driver)
    print("本脚本跳过答题，仅处理签到与抽奖。")
    correct_rate = None
    lottery(driver)
    final_money = getMoney(driver)
    print(f"金钱变化：{initial_money} -> {final_money}。")
    driver.quit()
    return initial_money, final_money, correct_rate

def main():
    global username, password, mail_user, mail_pass, api_key, search_api_key
    global llm_base_url, llm_model, search_api_url, search_mode, search_cnt, search_max_items, search_passage_chars
    global search_site, search_site_min_items

    parser = argparse.ArgumentParser()
    parser.add_argument('--local', action='store_true', help='Use local config and chromedriver path')
    parser.add_argument('--headless', action='store_true', help='Enable headless mode')
    args = parser.parse_args()
    # args.local = True
    # 配置加载
    try:
        if args.local:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            linux_driver_dir = os.path.join(base_dir, "chromedriver-linux64")
            win_driver_dir = os.path.join(base_dir, "chromedriver-win64")

            if os.path.exists(linux_driver_dir):
                chromedriver_path = os.path.join(linux_driver_dir, "chromedriver")
            elif os.path.exists(win_driver_dir):
                chromedriver_path = os.path.join(win_driver_dir, "chromedriver.exe")
            else:
                chromedriver_path = shutil.which("chromedriver")
                if not chromedriver_path:
                    raise FileNotFoundError("未找到 chromedriver-linux64/chromedriver、chromedriver-win64/chromedriver.exe，且系统 PATH 中无 chromedriver")
            
            config_path = os.path.join(base_dir, "config.json")
            with open(config_path, 'r') as f:
                config = json.load(f)
            username = config['USERNAME']
            password = config['PASSWORD']
            mail_user = config['MAIL_USERNAME']
            mail_pass = config['MAIL_PASSWORD']
            api_key = config['API_KEY']
            search_api_key = config.get('SEARCH_API_KEY', os.environ.get('SEARCH_API_KEY'))
            llm_base_url = config.get('LLM_BASE_URL', os.environ.get('LLM_BASE_URL', llm_base_url))
            llm_model = config.get('LLM_MODEL', os.environ.get('LLM_MODEL', llm_model))
            search_api_url = config.get('SEARCH_API_URL', os.environ.get('SEARCH_API_URL', search_api_url))
            search_mode = parse_optional_int(
                config.get('SEARCH_MODE', os.environ.get('SEARCH_MODE')),
                search_mode
            )
            search_cnt = parse_optional_int(
                config.get('SEARCH_CNT', os.environ.get('SEARCH_CNT')),
                search_cnt
            )
            search_max_items = parse_optional_int(
                config.get('SEARCH_MAX_ITEMS', os.environ.get('SEARCH_MAX_ITEMS')),
                search_max_items
            )
            search_passage_chars = parse_optional_int(
                config.get('SEARCH_PASSAGE_CHARS', os.environ.get('SEARCH_PASSAGE_CHARS')),
                search_passage_chars
            )
            search_site = config.get('SEARCH_SITE', os.environ.get('SEARCH_SITE', search_site))
            if search_site is not None:
                search_site = str(search_site).strip() or None
            search_site_min_items = parse_optional_int(
                config.get('SEARCH_SITE_MIN_ITEMS', os.environ.get('SEARCH_SITE_MIN_ITEMS')),
                search_site_min_items
            )
        else:
            chromedriver_path = shutil.which("chromedriver")
            username = os.environ['USERNAME']
            password = os.environ['PASSWORD']
            mail_user = os.environ['MAIL_USERNAME']
            mail_pass = os.environ['MAIL_PASSWORD']
            api_key = os.environ['API_KEY']
            search_api_key = os.environ.get('SEARCH_API_KEY')
            llm_base_url = os.environ.get('LLM_BASE_URL', llm_base_url)
            llm_model = os.environ.get('LLM_MODEL', llm_model)
            search_api_url = os.environ.get('SEARCH_API_URL', search_api_url)
            search_mode = parse_optional_int(os.environ.get('SEARCH_MODE'), search_mode)
            search_cnt = parse_optional_int(os.environ.get('SEARCH_CNT'), search_cnt)
            search_max_items = parse_optional_int(os.environ.get('SEARCH_MAX_ITEMS'), search_max_items)
            search_passage_chars = parse_optional_int(os.environ.get('SEARCH_PASSAGE_CHARS'), search_passage_chars)
            search_site = os.environ.get('SEARCH_SITE', search_site)
            if search_site is not None:
                search_site = str(search_site).strip() or None
            search_site_min_items = parse_optional_int(
                os.environ.get('SEARCH_SITE_MIN_ITEMS'),
                search_site_min_items
            )
    except KeyError as e:
        raise Exception(f"Missing required configuration: {e}")

    # merge(headless=args.headless, local=args.local, chromedriver_path=chromedriver_path)
    merge_fn = partial(merge, headless=args.headless, local=args.local, chromedriver_path=chromedriver_path)
    # local 模式下 tee=True：print 实时显示在控制台，同时写入缓冲区用于发邮件
    output_message, (initial_money, final_money, correct_rate) = capture_output(merge_fn, tee=args.local)
    if correct_rate is not None:
        subject = f"{initial_money} -> {final_money} | 正确率 {correct_rate * 100:.2f}%"
    else:
        subject = f"{initial_money} -> {final_money}"
    sendEmail(output_message, subject=subject)

if __name__ == '__main__':
    main()