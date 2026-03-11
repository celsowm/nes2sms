"""CLI main entry point."""

import argparse
import sys
from pathlib import Path

from .commands.ingest import cmd_ingest
from .commands.analyze_mapper import cmd_analyze_mapper
from .commands.convert_gfx import cmd_convert_gfx
from .commands.convert_audio import cmd_convert_audio
from .commands.generate import cmd_generate
from .commands.build import cmd_build
from .commands.translate_asm import cmd_translate_asm
from .commands.convert import cmd_convert


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="nes2sms", description="NES to Sega Master System conversion pipeline"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # One-step convert command (simple mode)
    p_convert = subparsers.add_parser("convert", help="One-step NES to SMS conversion")
    p_convert.add_argument("--nes", required=True, help="Path to .nes ROM file")
    p_convert.add_argument("--out", required=True, help="Output directory")
    p_convert.add_argument("--flip-strategy", default="cache", choices=["cache", "none"])
    p_convert.add_argument("--build", action="store_true", help="Build SMS ROM after conversion")
    p_convert.add_argument("--run", action="store_true", help="Open in emulator after conversion")
    p_convert.add_argument("--emulator", help="Path to emulator executable (default: auto-detect)")

    # Ingest command
    p_ingest = subparsers.add_parser("ingest", help="Ingest NES ROM file")
    p_ingest.add_argument("--nes", required=True, help="Path to .nes ROM file")
    p_ingest.add_argument("--out", required=True, help="Output directory")
    p_ingest.add_argument("--disasm-dir", help="Optional nes-disasm output directory")

    # Analyze mapper command
    p_mapper = subparsers.add_parser(
        "analyze-mapper", help="Analyze NES mapper and generate bank map"
    )
    p_mapper.add_argument("--manifest", required=True, help="Path to manifest_sms.json")
    p_mapper.add_argument("--out", required=True, help="Output directory")

    # Convert graphics command
    p_gfx = subparsers.add_parser("convert-gfx", help="Convert graphics (CHR to VDP tiles)")
    p_gfx.add_argument("--chr", required=True, help="Path to chr.bin")
    p_gfx.add_argument("--prg", required=True, help="Path to prg.bin")
    p_gfx.add_argument("--palette-strategy", default="global-fit", help="Palette mapping strategy")
    p_gfx.add_argument(
        "--sprite-flip-strategy",
        default="cache",
        choices=["cache", "none"],
        help="Sprite flip handling",
    )
    p_gfx.add_argument("--out", required=True, help="Output directory")

    # Convert audio command
    p_audio = subparsers.add_parser("convert-audio", help="Convert audio (APU to PSG)")
    p_audio.add_argument("--prg", required=True, help="Path to prg.bin")
    p_audio.add_argument("--trace", help="Optional APU trace file")
    p_audio.add_argument(
        "--audio-strategy",
        default="rearrange",
        choices=["rearrange", "simplified", "stub"],
        help="Audio conversion strategy",
    )
    p_audio.add_argument("--out", required=True, help="Output directory")

    # Generate command
    p_gen = subparsers.add_parser("generate", help="Generate WLA-DX project scaffold")
    p_gen.add_argument("--manifest", required=True, help="Path to manifest_sms.json")
    p_gen.add_argument("--assets", help="Path to assets directory")
    p_gen.add_argument("--out", required=True, help="Output directory")
    p_gen.add_argument(
        "--backend", default="wla-dx", choices=["wla-dx", "sdcc"], help="Assembler backend"
    )

    # Build command
    p_build = subparsers.add_parser("build", help="Build SMS ROM")
    p_build.add_argument("--dir", required=True, help="Build directory with Makefile")

    # Translate assembly command
    p_trans = subparsers.add_parser("translate-asm", help="Translate 6502 assembly to Z80")
    p_trans.add_argument("--input", required=True, help="Input 6502 assembly file")
    p_trans.add_argument("--output", help="Output Z80 assembly file (optional)")
    p_trans.add_argument("--out", help="Output directory (if --output not specified)")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "convert":
            cmd_convert(args)
        elif args.command == "ingest":
            cmd_ingest(args)
        elif args.command == "analyze-mapper":
            cmd_analyze_mapper(args)
        elif args.command == "convert-gfx":
            cmd_convert_gfx(args)
        elif args.command == "convert-audio":
            cmd_convert_audio(args)
        elif args.command == "generate":
            cmd_generate(args)
        elif args.command == "build":
            cmd_build(args)
        elif args.command == "translate-asm":
            cmd_translate_asm(args)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
