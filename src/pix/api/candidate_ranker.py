"""VL 候选图评分排序。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from pix.api.packy_client import PackyClient, PackyError
from pix.config import AppConfig, require_vl_api_key
from pix.io_utils import image_to_base64_data_url

_JSON_BLOCK_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL)
_LOOSE_JSON_RE = re.compile(r"\{[\s\S]*\}")


@dataclass(frozen=True)
class CandidateScore:
    index: int
    rank: int
    score: float
    reason: str = ""

    def to_metadata(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "rank": self.rank,
            "score": self.score,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class CandidateRanking:
    selected_index: int
    candidates: list[CandidateScore]
    model: str
    mode: str = "model"
    error: str | None = None

    @property
    def selected_score(self) -> CandidateScore | None:
        for item in self.candidates:
            if item.index == self.selected_index:
                return item
        return self.candidates[0] if self.candidates else None

    def to_metadata(self) -> dict[str, Any]:
        return {
            "selected_index": self.selected_index,
            "model": self.model,
            "mode": self.mode,
            "error": self.error,
            "candidates": [item.to_metadata() for item in self.candidates],
        }


class CandidateRankingParseError(RuntimeError):
    pass


def _extract_json(text: str) -> str:
    match = _JSON_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()
    match = _LOOSE_JSON_RE.search(text)
    if match:
        return match.group(0).strip()
    return text.strip()


def _extract_content(resp: dict[str, Any]) -> str:
    choices = resp.get("choices") or []
    if not choices:
        raise PackyError(f"响应缺少 choices: {str(resp)[:500]}")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    raise PackyError(f"无法解析响应 content: {str(resp)[:500]}")


def _clamp_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(100.0, score))


def _normalize_ranked_payload(raw: str, candidate_indexes: list[int], *, model: str) -> CandidateRanking:
    try:
        data = json.loads(_extract_json(raw))
    except json.JSONDecodeError as exc:
        raise CandidateRankingParseError("候选评分不是合法 JSON") from exc
    if not isinstance(data, dict):
        raise CandidateRankingParseError("候选评分 JSON 根节点必须是对象")
    raw_items = data.get("candidates")
    if not isinstance(raw_items, list):
        raise CandidateRankingParseError("候选评分缺少 candidates 数组")

    allowed = set(candidate_indexes)
    by_index: dict[int, CandidateScore] = {}
    for pos, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        if index not in allowed or index in by_index:
            continue
        try:
            rank = int(item.get("rank") or pos)
        except (TypeError, ValueError):
            rank = pos
        score = _clamp_score(item.get("score"))
        reason = str(item.get("reason") or "").strip()[:500]
        by_index[index] = CandidateScore(index=index, rank=max(1, rank), score=score, reason=reason)

    if not by_index:
        raise CandidateRankingParseError("候选评分没有有效条目")

    # 补全模型漏评的候选，避免 Web 列表缺项。
    next_rank = len(by_index) + 1
    for index in candidate_indexes:
        if index not in by_index:
            by_index[index] = CandidateScore(index=index, rank=next_rank, score=0.0, reason="VL 未返回该候选的评分")
            next_rank += 1

    ordered = sorted(by_index.values(), key=lambda item: (item.rank, -item.score, item.index))
    # 重新规范化 rank，保证 1..N 连续且与展示顺序一致。
    ordered = [CandidateScore(index=item.index, rank=rank, score=item.score, reason=item.reason) for rank, item in enumerate(ordered, start=1)]

    try:
        selected_index = int(data.get("selected_index"))
    except (TypeError, ValueError):
        selected_index = ordered[0].index
    if selected_index not in allowed:
        selected_index = ordered[0].index
    # 如果模型的 selected_index 与 rank 不一致，优先用 rank 第一，保持“按效果高到低排序”的语义。
    selected_index = ordered[0].index
    return CandidateRanking(selected_index=selected_index, candidates=ordered, model=model)


def fallback_ranking(candidate_indexes: Iterable[int], *, model: str, error: str | None = None) -> CandidateRanking:
    indexes = list(candidate_indexes)
    if not indexes:
        return CandidateRanking(selected_index=0, candidates=[], model=model, mode="fallback", error=error)
    scores = [CandidateScore(index=index, rank=rank, score=0.0, reason="VL 评分不可用，按原始候选顺序回退") for rank, index in enumerate(indexes, start=1)]
    return CandidateRanking(selected_index=indexes[0], candidates=scores, model=model, mode="fallback", error=error)


def rank_candidates(
    cfg: AppConfig,
    candidates: Iterable[tuple[int, str | Path]],
    *,
    user_prompt: str,
    target_size: tuple[int, int],
    model: str | None = None,
) -> CandidateRanking:
    """用 VL 对多个候选图一次性评分排序。"""
    model_name = model or cfg.image_gen.candidate_vl_ranking_model or cfg.vision.model
    candidate_items = [(int(index), Path(path)) for index, path in candidates]
    if not candidate_items:
        return CandidateRanking(selected_index=0, candidates=[], model=model_name)

    api_key = require_vl_api_key(cfg)
    client = PackyClient(
        base_url=cfg.api.base_url,
        api_key=api_key,
        timeout=cfg.api.timeout,
        max_retries=cfg.api.max_retries,
    )
    width, height = target_size
    criteria = (
        "你是游戏像素素材美术总监。请对候选图按最终像素化质量从高到低排序。\n"
        f"用户原始需求：{user_prompt}\n"
        f"目标输出尺寸：{int(width)}x{int(height)}。\n"
        "评分标准：1) 符合用户描述；2) 单一主体、居中、无文字/水印/UI；"
        "3) 透明或绿幕抠图后边缘干净；4) 低分辨率下轮廓可读；"
        "5) 高对比、形态辨识度强；6) 无残留背景、裁切错误、多主体或噪声。\n"
        "只返回 JSON，不要 Markdown。格式："
        "{\"selected_index\":5,\"candidates\":[{\"index\":5,\"rank\":1,\"score\":92,\"reason\":\"原因\"}]}。"
        "必须包含所有候选，score 为 0-100，rank=1 表示最好。"
    )
    content: list[dict[str, Any]] = [{"type": "text", "text": criteria}]
    for index, path in candidate_items:
        content.append({"type": "text", "text": f"candidate_{index:02d}"})
        content.append({"type": "image_url", "image_url": {"url": image_to_base64_data_url(path)}})

    payload: dict[str, Any] = {
        "model": model_name,
        "messages": [{"role": "user", "content": content}],
        "temperature": min(float(cfg.vision.temperature), 0.2),
        "max_tokens": max(int(cfg.vision.max_tokens), 1800),
    }
    raw = _extract_content(client.post_json("/v1/chat/completions", payload))
    return _normalize_ranked_payload(raw, [index for index, _ in candidate_items], model=model_name)
