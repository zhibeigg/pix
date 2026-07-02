"""受保护文件的归属判定。

统一判断某个已解析的本地文件路径是否属于指定用户，供 ``/files`` 越权校验
（IDOR 修复）和任务创建时的输入图归属校验（LFI 修复）复用，避免两处逻辑分叉。

判定规则（任一成立即视为该用户可访问）：

1. 路径位于 ``storage_root/uploads/{user.id}/`` 下 —— 用户自己上传的文件；
2. 路径位于 ``storage_root/runs/job-{jid}/`` 下，且 ``GenerationJob.id == jid`` 存在且
   ``job.user_id == user.id`` —— 用户自己任务的产物（本地像素化 / 重新像素化 / 复用源图等
   合法链路会把这些路径回填到 ``input_image_path``）；
3. 管理员（``user.role == "admin"``）放行。
"""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from pix_web.config import WebSettings
from pix_web.models import GenerationJob, User

_JOB_DIR_RE = re.compile(r"^job-(\d+)$")


def _relative_parts(resolved: Path, root: Path) -> tuple[str, ...] | None:
    """返回 ``resolved`` 相对 ``root`` 的路径片段；不在 root 内则返回 None。"""
    try:
        return resolved.relative_to(root).parts
    except ValueError:
        return None


def user_owns_file(resolved: Path, user: User, db: Session, settings: WebSettings) -> bool:
    """判断已解析的绝对路径 ``resolved`` 是否归属 ``user``。

    ``resolved`` 必须是已 ``resolve()`` 的绝对路径（调用方先经过 ``resolve_web_file``
    做过 allowed roots 包含校验，这里只补充“归属”这一层）。
    """
    if user.role == "admin":
        return True

    storage_root = settings.storage_root.resolve()

    uploads_root = (storage_root / "uploads").resolve()
    upload_parts = _relative_parts(resolved, uploads_root)
    if upload_parts and len(upload_parts) >= 1 and upload_parts[0] == str(user.id):
        return True

    runs_root = (storage_root / "runs").resolve()
    run_parts = _relative_parts(resolved, runs_root)
    if run_parts:
        match = _JOB_DIR_RE.match(run_parts[0])
        if match:
            job_id = int(match.group(1))
            owner_id = db.scalar(
                select(GenerationJob.user_id).where(GenerationJob.id == job_id)
            )
            if owner_id is not None and owner_id == user.id:
                return True

    return False


def resolve_owned_input_path(raw_path: str, user: User, db: Session, settings: WebSettings) -> Path:
    """解析用户提交的输入图路径并校验归属，返回解析后的绝对路径。

    仅允许指向用户自己的上传目录或自己任务的 run 目录，阻止任意文件读取。
    非法路径抛 :class:`ValueError`，由调用方转换为合适的 HTTP 错误。
    """
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    resolved = candidate.resolve()
    if not user_owns_file(resolved, user, db, settings):
        raise ValueError("输入图片路径不合法")
    return resolved
