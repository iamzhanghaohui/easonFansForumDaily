from __future__ import annotations

from agents import function_tool

from question_bank import QuestionBank

from .search import format_pages, search_pages, search_pages_multi
from .settings import get_settings


@function_tool
def search_bank(query: str) -> str:
    """查询本地题库里已做过的题目、正确答案和错误选项。

    先查题库再决定要不要上网搜。query 可以是题干关键词、歌词句或某个选项原文。
    """
    print(f"[Agent tool] search_bank query={query!r}")
    return QuestionBank().search(query)


@function_tool
def search_site(query: str) -> str:
    """在粉丝站 easonfans.com 内检索歌词、歌名、专辑、演出资料。

    适合先查站内资料。query 应是简短检索词，例如完整歌词句、歌名+陈奕迅。
    """
    settings = get_settings()
    site = settings.search_site or "easonfans.com"
    print(f"[Agent tool] search_site query={query!r} site={site}")
    pages = search_pages(query, site=site)
    print(f"站内搜索（{site}）：命中 {len(pages)} 条。")
    return format_pages(pages, f"站内:{site}")


@function_tool
def search_web(query: str) -> str:
    """全网多轮检索：先按原词搜索，再自动补歌手名、歌词出处和相关标题做交叉验证。

    站内结果不足、互相矛盾，或需要对选项逐一核对时使用。
    query 应是简短检索词；「哪首不是」类题请对每个选项分别调用一次。
    """
    print(f"[Agent tool] search_web query={query!r}")
    pages = search_pages_multi(query, site=None)
    print(f"全网多轮搜索：合计 {len(pages)} 条。")
    return format_pages(pages, "全网")
