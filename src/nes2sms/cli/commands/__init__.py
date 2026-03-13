"""CLI commands."""

from .ingest import cmd_ingest
from .analyze_mapper import cmd_analyze_mapper
from .convert_gfx import cmd_convert_gfx
from .convert_audio import cmd_convert_audio
from .generate import cmd_generate
from .build import cmd_build
from .bootstrap_hello import cmd_bootstrap_hello

__all__ = [
    "cmd_ingest",
    "cmd_analyze_mapper",
    "cmd_convert_gfx",
    "cmd_convert_audio",
    "cmd_generate",
    "cmd_build",
    "cmd_bootstrap_hello",
]
