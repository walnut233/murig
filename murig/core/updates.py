# -*- coding: utf-8 -*-
"""软件更新检查：向 GitHub Releases 接口查询最新版本并与当前版本比较。

只用 Python 标准库 + 已有的 http.get（含重试与证书降级），不引入新依赖；
查询失败时抛异常，由调用方（后台线程）转成界面提示。
"""

from __future__ import annotations

import re
from typing import NamedTuple, Tuple

from .constants import APP_VERSION, RELEASES_API, RELEASES_LATEST_URL
from .http import get as http_get

__all__ = ["UpdateInfo", "fetch_latest", "version_key", "is_newer"]


class UpdateInfo(NamedTuple):
    """一个已发布版本的信息。"""

    version: str      # tag_name，如 "v1.2.2"
    url: str          # 发布页地址（供用户跳转下载）
    notes: str        # 更新说明（已截断）
    published: str    # 发布日期，如 "2026-10-15"


def version_key(text: str) -> Tuple[int, ...]:
    """把版本号转成可比较的元组：v1.2.1 -> (1, 2, 1)。

    非数字后缀（如 1.2.0-beta）会被忽略，只比较主干数字部分；
    完全解析不出数字时返回 (0,)，保证比较不抛异常。
    """
    nums = re.findall(r"\d+", text or "")
    return tuple(int(n) for n in nums) or (0,)


def is_newer(latest: str, current: str = APP_VERSION) -> bool:
    """latest 是否比 current 新（位数不同时按 0 补齐比较）。"""
    a, b = version_key(latest), version_key(current)
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def fetch_latest(timeout: int = 10,
                 on_note=None) -> UpdateInfo:
    """查询 GitHub 上最新的 Release。

    失败时抛出 requests 的原始异常（网络错误 / 404 无发布 / 限流等）。
    """
    resp = http_get(
        RELEASES_API,
        timeout=timeout,
        headers={"User-Agent": "MuRig", "Accept": "application/vnd.github+json"},
        on_note=on_note,
    )
    data = resp.json()
    tag = str(data.get("tag_name") or "").strip()
    if not tag:
        raise ValueError("接口未返回版本号（tag_name 为空）")
    body = (data.get("body") or "").strip()
    # 更新说明可能很长，界面上只展示前若干行
    lines = [ln.rstrip() for ln in body.splitlines()]
    notes = "\n".join(ln for ln in lines if ln)[:1200]
    return UpdateInfo(
        version=tag,
        url=str(data.get("html_url") or RELEASES_LATEST_URL),
        notes=notes,
        published=str(data.get("published_at") or "")[:10],
    )
