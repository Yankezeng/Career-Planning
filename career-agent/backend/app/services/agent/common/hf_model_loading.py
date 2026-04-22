from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def quiet_hf_model_load(*, suppress_output: bool = True) -> Iterator[None]:
    """Temporarily silence noisy HuggingFace model loading output."""

    try:
        from transformers.utils import logging as hf_logging
    except Exception:
        yield
        return

    previous_verbosity = hf_logging.get_verbosity()
    progress_bar_enabled = (
        hf_logging.is_progress_bar_enabled()
        if hasattr(hf_logging, "is_progress_bar_enabled")
        else None
    )

    hf_logging.set_verbosity_error()
    if hasattr(hf_logging, "disable_progress_bar"):
        hf_logging.disable_progress_bar()

    try:
        if suppress_output:
            with _suppress_output_streams():
                yield
        else:
            yield
    finally:
        hf_logging.set_verbosity(previous_verbosity)
        if progress_bar_enabled is True and hasattr(hf_logging, "enable_progress_bar"):
            hf_logging.enable_progress_bar()
        elif progress_bar_enabled is False and hasattr(hf_logging, "disable_progress_bar"):
            hf_logging.disable_progress_bar()


@contextmanager
def _suppress_output_streams() -> Iterator[None]:
    stdout = sys.stdout
    stderr = sys.stderr
    saved_stdout_fd = os.dup(1)
    saved_stderr_fd = os.dup(2)

    with open(os.devnull, "w", encoding="utf-8") as devnull:
        try:
            stdout.flush()
            stderr.flush()
            os.dup2(devnull.fileno(), 1)
            os.dup2(devnull.fileno(), 2)
            sys.stdout = devnull
            sys.stderr = devnull
            yield
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            os.dup2(saved_stdout_fd, 1)
            os.dup2(saved_stderr_fd, 2)
            os.close(saved_stdout_fd)
            os.close(saved_stderr_fd)
            sys.stdout = stdout
            sys.stderr = stderr
