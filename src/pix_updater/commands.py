from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from pix_updater.redaction import redact


class CommandRejected(ValueError):
    pass


class CommandFailed(RuntimeError):
    def __init__(self, result: "CommandResult") -> None:
        super().__init__(f"command failed ({result.returncode}): {result.stderr or result.stdout}")
        self.result = result


@dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class AsyncCommandRunner:
    """Executes only updater-owned command shapes, never a shell string."""

    _executables = {"docker", "gh", "pg_dump", "pg_restore"}

    @classmethod
    def validate(cls, args: Sequence[str]) -> tuple[str, ...]:
        normalized = tuple(str(arg) for arg in args)
        if not normalized or normalized[0] not in cls._executables:
            raise CommandRejected("executable is not allowlisted")
        if any("\x00" in arg or "\n" in arg or "\r" in arg for arg in normalized):
            raise CommandRejected("command argument contains control characters")
        executable = normalized[0]
        if executable == "gh" and normalized[1:3] != ("attestation", "verify"):
            raise CommandRejected("only gh attestation verify is allowed")
        if executable == "docker":
            if len(normalized) < 2 or normalized[1] not in {"info", "pull", "compose"}:
                raise CommandRejected("docker subcommand is not allowlisted")
            if normalized[1] == "compose" and any(arg in {"exec", "run"} for arg in normalized[2:]):
                if "run" not in normalized[2:]:
                    raise CommandRejected("docker compose exec is forbidden")
                run_index = normalized.index("run", 2)
                if normalized[run_index + 1 : run_index + 3] != ("--rm", "migrate"):
                    raise CommandRejected("only the fixed migrate run is allowed")
        return normalized

    async def run(
        self,
        args: Sequence[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float = 600,
        check: bool = True,
        secrets: Sequence[str] = (),
    ) -> CommandResult:
        command = self.validate(args)
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd) if cwd else None,
            env=dict(env) if env else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout)
        except TimeoutError:
            process.kill()
            await process.wait()
            raise RuntimeError(f"command timed out: {command[0]}")
        result = CommandResult(
            args=command,
            returncode=process.returncode or 0,
            stdout=redact(stdout_bytes.decode("utf-8", "replace"), secrets).strip(),
            stderr=redact(stderr_bytes.decode("utf-8", "replace"), secrets).strip(),
        )
        if check and result.returncode != 0:
            raise CommandFailed(result)
        return result
