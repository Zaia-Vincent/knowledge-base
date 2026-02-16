"""Colored pipeline logger — ANSI-colored console logging for the file processing pipeline.

Provides a PipelineLogger with color-coded output per pipeline stage,
making it easy to visually trace file processing in the terminal.

Color scheme:
    🟢 Green   — Upload / Storage
    🟡 Yellow  — Text Extraction
    🟣 Magenta — PDF LLM Processing
    🔵 Blue    — Classification
    🟠 Cyan    — Metadata Extraction
    🔴 Red     — Errors
    ⚪ Gray    — Timing / Stats
"""

import logging
import time
from contextlib import contextmanager
from typing import Any


# ── ANSI Color Codes ─────────────────────────────────────────────────

class _Colors:
    """ANSI escape codes for terminal colors."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"

    # Background (subtle)
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"


# ── Pipeline Stage Definitions ───────────────────────────────────────

class PipelineStage:
    """Predefined pipeline stages with colors and icons."""

    UPLOAD = ("UPLOAD", _Colors.GREEN, "📁")
    STORAGE = ("STORAGE", _Colors.GREEN, "💾")
    TEXT_EXTRACTION = ("TEXT_EXTRACT", _Colors.YELLOW, "📄")
    PDF_LLM = ("PDF_LLM", _Colors.MAGENTA, "🤖")
    CLASSIFICATION = ("CLASSIFY", _Colors.BLUE, "🏷️")
    METADATA = ("METADATA", _Colors.CYAN, "📊")
    PIPELINE = ("PIPELINE", _Colors.WHITE, "⚙️")
    ERROR = ("ERROR", _Colors.RED, "❌")
    COMPLETE = ("COMPLETE", _Colors.GREEN, "✅")


# ── PipelineLogger ───────────────────────────────────────────────────

class PipelineLogger:
    """Color-coded logger for the file processing pipeline.

    Usage:
        log = PipelineLogger("FileProcessingService")
        log.step_start(PipelineStage.UPLOAD, "Processing invoice.pdf")
        log.detail("File size: 2.4 MB")
        log.step_complete(PipelineStage.UPLOAD, "Stored at uploads/abc123/")
    """

    def __init__(self, component_name: str):
        self._logger = logging.getLogger(component_name)
        self._component = component_name

    def step_start(self, stage: tuple[str, str, str], message: str, **kwargs: Any) -> None:
        """Log the start of a pipeline step with its stage color."""
        label, color, icon = stage
        formatted = (
            f"{color}{_Colors.BOLD}{icon} [{label}]{_Colors.RESET} "
            f"{color}{message}{_Colors.RESET}"
        )
        if kwargs:
            details = " | ".join(f"{k}={v}" for k, v in kwargs.items())
            formatted += f" {_Colors.GRAY}({details}){_Colors.RESET}"
        self._logger.info(formatted)

    def step_complete(self, stage: tuple[str, str, str], message: str, **kwargs: Any) -> None:
        """Log the successful completion of a pipeline step."""
        label, color, icon = stage
        formatted = (
            f"{color}{icon} [{label}]{_Colors.RESET} "
            f"{_Colors.GREEN}✓ {message}{_Colors.RESET}"
        )
        if kwargs:
            details = " | ".join(f"{k}={v}" for k, v in kwargs.items())
            formatted += f" {_Colors.GRAY}({details}){_Colors.RESET}"
        self._logger.info(formatted)

    def step_error(self, stage: tuple[str, str, str], message: str, error: Exception | None = None) -> None:
        """Log a pipeline step error in red."""
        label, _, icon = stage
        formatted = (
            f"{_Colors.RED}{_Colors.BOLD}❌ [{label}]{_Colors.RESET} "
            f"{_Colors.RED}{message}{_Colors.RESET}"
        )
        if error:
            formatted += f" {_Colors.DIM}→ {type(error).__name__}: {error}{_Colors.RESET}"
        self._logger.error(formatted)

    def detail(self, message: str, **kwargs: Any) -> None:
        """Log additional detail (gray/dimmed)."""
        formatted = f"   {_Colors.GRAY}├─ {message}{_Colors.RESET}"
        if kwargs:
            details = " | ".join(f"{k}={v}" for k, v in kwargs.items())
            formatted += f" {_Colors.DIM}({details}){_Colors.RESET}"
        self._logger.info(formatted)

    def separator(self, title: str = "") -> None:
        """Log a visual separator line."""
        if title:
            self._logger.info(
                f"{_Colors.GRAY}{'─' * 10} {title} {'─' * (50 - len(title))}{_Colors.RESET}"
            )
        else:
            self._logger.info(f"{_Colors.GRAY}{'─' * 60}{_Colors.RESET}")

    def stats(self, **kwargs: Any) -> None:
        """Log statistics / timing information."""
        parts = [f"{_Colors.GRAY}{k}: {v}" for k, v in kwargs.items()]
        formatted = f"   {_Colors.GRAY}📈 {' | '.join(parts)}{_Colors.RESET}"
        self._logger.info(formatted)

    @contextmanager
    def timed_step(self, stage: tuple[str, str, str], message: str, **kwargs: Any):
        """Context manager that logs start/end with elapsed time.

        Usage:
            with log.timed_step(PipelineStage.CLASSIFICATION, "Classifying document"):
                result = await classifier.classify(...)
        """
        self.step_start(stage, message, **kwargs)
        start = time.perf_counter()
        try:
            yield
        except Exception as e:
            elapsed = time.perf_counter() - start
            self.step_error(stage, f"{message} — failed after {elapsed:.2f}s", error=e)
            raise
        else:
            elapsed = time.perf_counter() - start
            self.step_complete(stage, f"{message} — {elapsed:.2f}s", **kwargs)
