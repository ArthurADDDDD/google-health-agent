import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel

from google_health_agent.errors import ProviderUnavailable


class AgentResult(BaseModel):
    agent: str
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    execution_seconds: float


class AgentRunner(ABC):
    name: str

    @abstractmethod
    def run(self, prompt: str, output_file: Path, timeout_seconds: int = 300) -> AgentResult:
        """Run an installed agent CLI without placing secrets in arguments or logs."""


class SubprocessAgentRunner(AgentRunner):
    executable: str

    @abstractmethod
    def command(self, prompt: str, output_file: Path) -> list[str]:
        pass

    def run(self, prompt: str, output_file: Path, timeout_seconds: int = 300) -> AgentResult:
        executable = shutil.which(self.executable)
        if not executable:
            raise ProviderUnavailable(
                f"{self.name} CLI is not installed. "
                "Install it separately before running this agent."
            )
        started = time.monotonic()
        try:
            completed = subprocess.run(
                self.command(prompt, output_file),
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            return AgentResult(
                agent=self.name,
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                timed_out=False,
                execution_seconds=time.monotonic() - started,
            )
        except subprocess.TimeoutExpired as exc:
            return AgentResult(
                agent=self.name,
                exit_code=124,
                stdout=_as_text(exc.stdout),
                stderr=_as_text(exc.stderr),
                timed_out=True,
                execution_seconds=time.monotonic() - started,
            )


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode(errors="replace") if isinstance(value, bytes) else value


class ClaudeRunner(SubprocessAgentRunner):
    name = "claude"
    executable = "claude"

    def command(self, prompt: str, output_file: Path) -> list[str]:
        return [
            self.executable,
            "-p",
            "--output-format",
            "text",
            "--max-turns",
            "12",
            prompt,
        ]


class CodexRunner(SubprocessAgentRunner):
    name = "codex"
    executable = "codex"

    def command(self, prompt: str, output_file: Path) -> list[str]:
        return [
            self.executable,
            "exec",
            "--ephemeral",
            "--output-last-message",
            str(output_file),
            prompt,
        ]


class FakeRunner(AgentRunner):
    name = "fake"

    def __init__(self, facts: dict[str, object]) -> None:
        self.facts = facts

    def run(self, prompt: str, output_file: Path, timeout_seconds: int = 300) -> AgentResult:
        del prompt, timeout_seconds
        started = time.monotonic()
        quality = self.facts["quality"]
        overview = self.facts["overview"]
        sleep = self.facts["sleep"]
        recovery = self.facts["recovery"]
        activity = self.facts["activity"]
        assert isinstance(quality, dict)
        assert isinstance(overview, dict)
        assert isinstance(sleep, dict)
        assert isinstance(recovery, dict)
        assert isinstance(activity, dict)
        text = _fake_markdown(quality, overview, sleep, recovery, activity)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(text, encoding="utf-8")
        return AgentResult(
            agent=self.name,
            exit_code=0,
            stdout=text,
            stderr="",
            timed_out=False,
            execution_seconds=time.monotonic() - started,
        )


def _median(payload: dict[str, object], metric: str) -> str:
    summaries = payload.get("summaries")
    if not isinstance(summaries, dict):
        return "unavailable"
    summary = summaries.get(metric)
    if not isinstance(summary, dict):
        return "unavailable"
    value = summary.get("median")
    return "unavailable" if value is None else str(round(float(value), 2))


def _fake_markdown(
    quality: dict[str, object],
    overview: dict[str, object],
    sleep: dict[str, object],
    recovery: dict[str, object],
    activity: dict[str, object],
) -> str:
    period = overview.get("period")
    end_date = period.get("end_date", "demo") if isinstance(period, dict) else "demo"
    return f"""# Health Brief · {end_date}

> SYNTHETIC DATA — CI demonstration only. No medical interpretation.

## Last night

- Median sleep in the requested window: {_median(sleep, "sleep_minutes")} minutes.

## Recovery

- Median HRV: {_median(recovery, "hrv")} ms.
- Median resting heart rate: {_median(recovery, "resting_heart_rate")} bpm.

## Activity

- Median steps: {_median(activity, "steps")}.

## Recent trend

- Statistical summaries and unusual points are available in the MCP overview.

## Worth noting

- FakeRunner reports observed mathematical facts only; an external agent provides interpretation.

## Data completeness

- Completeness: {quality.get("completeness", "unavailable")}.
- Data label: SYNTHETIC DATA.
"""
