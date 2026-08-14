from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Optional

from .settings import get_settings


def resolve_backend() -> str:
    settings = get_settings()
    backend = (settings.search_backend or "auto").lower()
    has_sdk = bool(settings.tencent_secret_id and settings.tencent_secret_key)
    has_bearer = bool(settings.search_api_key)
    if backend == "auto":
        if has_sdk:
            return "tencentcloud"
        if has_bearer:
            return "bearer"
        raise RuntimeError(
            "未配置搜索密钥。请在 config.json 填写 SEARCH_API_KEY，"
            "或开通腾讯云联网搜索 API 后填写 TENCENTCLOUD_SECRET_ID / TENCENTCLOUD_SECRET_KEY。"
        )
    if backend == "tencentcloud" and not has_sdk:
        raise RuntimeError("SEARCH_BACKEND=tencentcloud 但未配置 TENCENTCLOUD_SECRET_ID / TENCENTCLOUD_SECRET_KEY")
    if backend == "bearer" and not has_bearer:
        raise RuntimeError("SEARCH_BACKEND=bearer 但未配置 SEARCH_API_KEY")
    return backend


def search_pages(
    query: str,
    site: Optional[str] = None,
    cnt: Optional[int] = None,
    mode: Optional[int] = None,
) -> list[dict[str, Any]]:
    query = (query or "").strip()
    if not query:
        return []
    settings = get_settings()
    effective_cnt = cnt or settings.search_cnt
    allowed_cnt = [10, 20, 30, 40, 50]
    effective_cnt = min(allowed_cnt, key=lambda x: abs(x - int(effective_cnt)))
    effective_mode = settings.search_mode if mode is None else mode
    if site:
        effective_mode = 0
    backend = resolve_backend()
    if backend == "tencentcloud":
        pages = _search_tencentcloud(query, site=site, cnt=effective_cnt, mode=effective_mode)
    else:
        pages = _search_bearer(query, site=site, cnt=effective_cnt, mode=effective_mode)
    return pages[: settings.search_max_items]


def _page_key(page: dict[str, Any]) -> str:
    return ((page.get("url") or "").strip() or (page.get("title") or "").strip())


def _dedupe_pages(pages: list[dict[str, Any]], seen: set[str]) -> list[dict[str, Any]]:
    unique = []
    for page in pages:
        key = _page_key(page)
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(page)
    return unique


def _clean_title(title: str) -> str:
    title = re.split(r"[_|｜【\-]", (title or "").strip())[0].strip()
    title = re.sub(r"\s+", " ", title)
    return title[:80]


def _followup_queries(query: str, pages: list[dict[str, Any]]) -> list[str]:
    """根据首轮结果生成补充检索词：补歌手名、歌词出处，以及前几条标题。"""
    query = (query or "").strip()
    candidates: list[str] = []
    lowered = query.lower()
    if "陈奕迅" not in query and "eason" not in lowered:
        candidates.append(f"{query} 陈奕迅")
    if any(token in query for token in ("歌词", "哪首", "出自", "是哪")):
        candidates.append(f"{query} 歌词 出处")
    for page in pages[:3]:
        title = _clean_title(page.get("title") or "")
        if len(title) < 6 or title in query:
            continue
        if "陈奕迅" in title or "eason" in title.lower():
            candidates.append(title)
        else:
            candidates.append(f"{title} 陈奕迅")

    followups: list[str] = []
    seen = {query}
    for item in candidates:
        item = item.strip()[:80]
        if item and item not in seen:
            seen.add(item)
            followups.append(item)
    return followups


def search_pages_multi(
    query: str,
    site: Optional[str] = None,
    rounds: Optional[int] = None,
) -> list[dict[str, Any]]:
    """多轮全网检索：首轮用原查询，后续用自动生成的补充词交叉验证。"""
    settings = get_settings()
    rounds = rounds or settings.search_web_rounds
    rounds = max(1, min(int(rounds), 4))

    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    first = search_pages(query, site=site)
    for page in _dedupe_pages(first, seen):
        item = dict(page)
        item["_round"] = 1
        item["_query"] = query
        merged.append(item)
    print(f"全网第1轮（{query}）：新增 {len(merged)} 条。")

    followups = _followup_queries(query, first)[: max(0, rounds - 1)]
    for idx, followup in enumerate(followups, 2):
        extra = search_pages(followup, site=site)
        added = 0
        for page in _dedupe_pages(extra, seen):
            item = dict(page)
            item["_round"] = idx
            item["_query"] = followup
            merged.append(item)
            added += 1
        print(f"全网第{idx}轮（{followup}）：新增 {added} 条。")
    return merged[: max(settings.search_max_items * 2, settings.search_max_items)]


def format_pages(pages: list[dict[str, Any]], source_tag: str) -> str:
    settings = get_settings()
    if not pages:
        return f"[{source_tag}] 未命中结果。"

    blocks = []
    for idx, page in enumerate(pages, 1):
        title = (page.get("title") or "").strip() or "未知标题"
        url = (page.get("url") or "").strip() or "未知来源"
        passage = (page.get("content") or page.get("passage") or "").strip()
        passage = passage[: settings.search_passage_chars]
        site = (page.get("site") or "").strip()
        score = page.get("score")
        round_no = page.get("_round")
        round_query = page.get("_query")
        tag = f"{source_tag}R{round_no}" if round_no else source_tag
        print(f"[参考{idx}/{tag}] {title} | {url}")
        meta = [f"[{idx}/{tag}] 标题: {title}", f"来源: {url}"]
        if round_query and round_no and int(round_no) > 1:
            meta.append(f"补充检索词: {round_query}")
        if site:
            meta.append(f"站点: {site}")
        if score is not None:
            meta.append(f"相关度: {score}")
        meta.append(f"摘要: {passage or '无'}")
        blocks.append("\n".join(meta))
    return "\n\n".join(blocks)


def _parse_pages(raw_pages: Any) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for raw in raw_pages or []:
        if isinstance(raw, str):
            try:
                parsed.append(json.loads(raw))
            except json.JSONDecodeError:
                parsed.append({"passage": raw})
        elif isinstance(raw, dict):
            parsed.append(raw)
    return parsed


def _search_bearer(
    query: str,
    site: Optional[str] = None,
    cnt: int = 20,
    mode: Optional[int] = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    payload: dict[str, Any] = {"Query": query, "Cnt": cnt}
    if mode in (0, 1, 2):
        payload["Mode"] = mode
    if site:
        payload["Site"] = site
        payload["Mode"] = 0
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url=settings.search_api_url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.search_api_key}",
            "Content-Type": "application/json; charset=UTF-8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
        result = json.loads(body)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        print(f"WSA Bearer 搜索 HTTP 错误: {e.code}, {err_body[:200]}")
        return []
    except Exception as e:
        print(f"WSA Bearer 搜索失败（{type(e).__name__}）: {e}")
        return []
    return _parse_pages(result.get("Response", {}).get("Pages", []))


def _search_tencentcloud(
    query: str,
    site: Optional[str] = None,
    cnt: int = 20,
    mode: Optional[int] = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    try:
        from tencentcloud.common import credential
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.common.profile.http_profile import HttpProfile
        from tencentcloud.wsa.v20250508 import models, wsa_client
    except ImportError as e:
        print(f"未安装腾讯云 SDK，无法使用标准密钥接入: {e}")
        return []

    try:
        cred = credential.Credential(settings.tencent_secret_id, settings.tencent_secret_key)
        http_profile = HttpProfile()
        http_profile.endpoint = "wsa.tencentcloudapi.com"
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        client = wsa_client.WsaClient(cred, "", client_profile)

        params: dict[str, Any] = {"Query": query, "Cnt": cnt}
        if mode in (0, 1, 2):
            params["Mode"] = mode
        if site:
            params["Site"] = site
            params["Mode"] = 0
        req = models.SearchProRequest()
        req.from_json_string(json.dumps(params, ensure_ascii=False))
        resp = client.SearchPro(req)
        payload = json.loads(resp.to_json_string())
        return _parse_pages(payload.get("Pages", []))
    except Exception as e:
        print(f"腾讯云 WSA 搜索失败（{type(e).__name__}）: {e}")
        return []
