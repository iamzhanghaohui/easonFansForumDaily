# easonFansForumDaily

自动完成 [神经研究所](https://www.easonfans.com) 每日任务：登录、签到、答题、免费抽奖，并把结果发到邮箱。

答题使用 OpenAI Agents SDK：先查本地题库，再搜 `easonfans.com`，不够再全网检索，最后选出 `a1`–`a4`。题目加载失败或提交失败时跳过后续题，在邮件里说明，方便之后手动补做。

---

## 1. 环境要求

- Ubuntu（当前脚本按服务器/本机 Ubuntu 写的）
- Python 3.10（由 `uv` 安装，不必系统自带）
- Chrome / Chromium，以及匹配的 ChromeDriver
- 能访问论坛、LLM API、搜索 API 的网络
- 一份 QQ 邮箱 SMTP 授权码（用于发结果邮件）

Windows 也能跑 `--local`，需要自行准备 `chromedriver-win64`。下面以 Ubuntu 为准。

---

## 2. 安装环境

### 2.1 克隆仓库

```bash
git clone git@github.com:iamzhanghaohui/easonFansForumDaily.git
cd easonFansForumDaily
```

### 2.2 一键安装（推荐）

```bash
chmod +x setup_ubuntu.sh
./setup_ubuntu.sh
```

脚本会依次：

1. 安装系统包：`curl`、`unzip`、`ca-certificates`、`tesseract-ocr`、`chromium-browser`、`chromium-chromedriver`
2. 安装 [`uv`](https://github.com/astral-sh/uv)（没有才装）
3. 用 uv 安装并钉死 Python 3.10
4. 创建 `.venv`，按 `requirements.txt` 装依赖
5. 检查 Python 包、Chromium、ChromeDriver 是否可用

装完后确认：

```bash
export PATH="$HOME/.local/bin:$PATH"
uv run python --version          # 期望 3.10.x
uv run python -c "import selenium, bs4, pytesseract, openai, agents; print('ok')"
```

### 2.3 手动安装（等价步骤）

不跑脚本时，可以自己执行：

```bash
sudo apt-get update
sudo apt-get install -y curl unzip ca-certificates tesseract-ocr chromium-browser chromium-chromedriver

curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

uv python install 3.10
uv python pin 3.10
uv venv --python 3.10 .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

Python 依赖见 `requirements.txt`：

- `selenium` / `beautifulsoup4` / `pytesseract`：浏览器自动化与页面解析
- `openai` / `openai-agents`：答题 Agent（tool-calling 循环）
- `tencentcloud-sdk-python-wsa`：腾讯搜索
- `dashscope`：历史兼容，当前主路径走 OpenAI 兼容接口

---

## 3. 配置

在项目根目录新建 `config.json`（已在 `.gitignore` 中，不要提交）：

```json
{
  "USERNAME": "论坛用户名",
  "PASSWORD": "论坛密码",
  "MAIL_USERNAME": "你的QQ邮箱@qq.com",
  "MAIL_PASSWORD": "QQ邮箱SMTP授权码",
  "API_KEY": "LLM API Key",
  "SEARCH_API_KEY": "搜索 API Key",
  "LLM_BASE_URL": "https://tokenhub.tencentmaas.com/v1",
  "LLM_MODEL": "hy3",
  "SEARCH_API_URL": "https://api.wsa.cloud.tencent.com/SearchPro",
  "SEARCH_SITE": "easonfans.com",
  "SEARCH_SITE_MIN_ITEMS": 3,
  "SEARCH_BACKEND": "auto",
  "AGENT_MAX_TURNS": 12,
  "AGENT_SEARCH_ITEMS": 10,
  "SEARCH_WEB_ROUNDS": 3
}
```

必填：

| 字段 | 说明 |
| --- | --- |
| `USERNAME` / `PASSWORD` | 论坛账号 |
| `MAIL_USERNAME` / `MAIL_PASSWORD` | 发信邮箱。当前代码走 `smtp.qq.com:465`，密码是 SMTP 授权码，不是 QQ 登录密码 |
| `API_KEY` | 答题用的 LLM Key（OpenAI 兼容接口） |

常用可选：

| 字段 | 默认 | 说明 |
| --- | --- | --- |
| `LLM_BASE_URL` / `LLM_MODEL` | TokenHub / `hy3` | 模型地址与名称 |
| `SEARCH_API_KEY` | 空 | 没有则 Agent 搜不到网页，只能靠题库和模型本身 |
| `SEARCH_SITE` | `easonfans.com` | 站内优先搜索站点 |
| `AGENT_MAX_TURNS` | `12` | Agent 最多检索轮数 |
| `SEARCH_WEB_ROUNDS` | `3` | 全网一次调用里的补充检索轮数 |

不带 `--local` 时，上述字段从环境变量读取（适合 CI）。本地定时任务请用 `--local`。

---

## 4. ChromeDriver

`--local` 会按这个顺序找驱动：

1. 项目目录 `chromedriver-linux64/chromedriver`
2. 项目目录 `chromedriver-win64/chromedriver.exe`
3. 系统 `PATH` 里的 `chromedriver`

版本必须和浏览器一致。对不上时，脚本会改走 Selenium 自动匹配。

需要手动下载时，到 [Chrome for Testing](https://googlechromelabs.github.io/chrome-for-testing/#stable) 选与本机 Chrome/Chromium 相同的版本，解压到项目根目录。这两个目录已在 `.gitignore` 中。

浏览器二进制会依次尝试 `CHROME_BINARY` 环境变量、`google-chrome`、`chromium`、`chromium-browser`。

---

## 5. 运行

### 5.1 完整每日任务

```bash
cd /path/to/easonFansForumDaily
export PATH="$HOME/.local/bin:$PATH"

# 无头（服务器 / crontab 用这个）
uv run python dailyMission.py --local --headless

# 弹出浏览器窗口，方便排错
uv run python dailyMission.py --local
```

一次运行会：登录 → 记金钱 → 签到 → 答题 → 免费抽奖 → 再记金钱 → 发邮件。

只做签到和抽奖、不答题：

```bash
uv run python dailyMissionNoQuiz.py --local --headless
```

### 5.2 单独测试答题 Agent

不登录论坛，只给题目和选项：

```bash
uv run python -m quiz_agent --local '题目：《富士山下》最初拟定的歌名十分直白，请问原名叫什么?

选项：
a1. 爱恨两难
a2. 心已成灰
a3. 旧梦难寻
a4. 悲哀无用

请从上述选项中选择一个最合理的答案，并只返回选项标签。'
```

省略题目时会跑内置样例。Agent 会调 `search_bank` / `search_site` / `search_web`，最后输出 `ANSWER: a1` 这类标签。

### 5.3 查看题库

做过的题记在 `data/question_bank.json`（不入库）。下次遇到相同题会优先用已知答案。

```bash
uv run python question_bank.py
```

---

## 6. 定时任务（crontab）

每天早上 9:30 的例子：

```cron
30 9 * * * cd /home/ubuntu/easonFansForumDaily && /home/ubuntu/.local/bin/uv run python dailyMission.py --local --headless >> /home/ubuntu/easonFansForumDaily/cron.log 2>&1
```

写入当前用户 crontab：

```bash
crontab -e
```

改完后用 `crontab -l` 确认。日志在项目根目录 `cron.log`。

crontab 环境很干净，命令里请写 `uv` 的绝对路径（常见是 `$HOME/.local/bin/uv`）。

---

## 7. 答题与失败策略

每题流程：

1. 打开每日问答页，读进度 `(已答/总数)`
2. 先查本地题库；未命中再启动 Agent 检索
3. Agent 给出 `a1`–`a4` 后，由 `submit_answer.py` 在当前浏览器会话里点击提交
4. 刷新页面，看累计答题数是否增加，据此判断对错并写入题库

加载不出来（页面、题目、选项、提交按钮）或提交失败（点击报错、提交后进度不变）时：

- 不再对同一题反复盲交
- 跳过后续题目
- 邮件正文写明跳过原因，标题带 `有题目跳过，请重试`

有空打开论坛手动补做即可。签到和抽奖不受答题跳过影响。

---

## 8. 邮件

发到 `MAIL_USERNAME` 自己。标题大致为：

```text
金钱变化 | 答题 正确数/作答数 正确率 xx.xx% | 有题目跳过，请重试
```

正文是今日小结，后面附详细日志。日志里检索链接很多时，QQ 有可能把邮件丢进垃圾箱或延迟投递，可在垃圾箱搜金钱数字或「正确率」。

---

## 9. 目录说明

| 路径 | 作用 |
| --- | --- |
| `setup_ubuntu.sh` | Ubuntu 一键装环境 |
| `dailyMission.py` | 每日任务入口 |
| `dailyMissionNoQuiz.py` | 不含答题的每日任务 |
| `quiz_scheduler.py` | 取题、调 Agent、提交、跳过、写小结 |
| `quiz_agent/` | 检索 Agent（`search_bank` / `search_site` / `search_web`） |
| `submit_answer.py` | 在已打开的答题页上点选项并提交 |
| `question_bank.py` | 本地题库读写 |
| `config.json` | 本地密钥（不入库） |
| `data/question_bank.json` | 题库数据（不入库） |
| `cron.log` | crontab 输出（不入库） |

---

## 10. 常见问题

**ChromeDriver 版本不匹配**  
日志会出现 `本地 chromedriver 与 Chrome 版本不匹配`，随后改用 Selenium 自动匹配。仍失败就按第 4 节换成同版本驱动。

**crontab 没跑**  
确认 `crontab -l` 里的路径、`uv` 绝对路径、以及 `cron.log` 是否在预定时间更新。系统日志可查：`grep dailyMission /var/log/syslog`。

**Agent 超时 `MaxTurnsExceeded`**  
单题检索超过 `AGENT_MAX_TURNS`（默认 12）仍没有合法标签时，会用备选选项交一次；若页面没推进，按失败跳过，不会连交多次。

**题库没命中**  
`search_bank` 按整段关键词做子串匹配。题干里没有你搜的那几个字连在一起，就会显示未命中。
