"""Translate assembly command: 6502 to Z80 translation."""

from pathlib import Path

from ...core.assembly.instruction_translator import InstructionTranslator
from ...infrastructure.asset_writer import AssetWriter


def cmd_translate_asm(args):
    """
    Translate 6502 assembly to Z80.

    Can translate a single file or integrate with existing disassembly.
    """
    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    out_dir = Path(args.out) if args.out else input_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # Read input file
    content = input_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Translate
    translator = InstructionTranslator()
    translated_lines = []

    for i, line in enumerate(lines):
        if line.strip().endswith(":") or not line.strip() or line.strip().startswith(";"):
            translated_lines.append(line)
        else:
            translated = translator.translate_line(line, address=i)
            translated_lines.append(translated)

    translated_content = "\n".join(translated_lines)

    # Write output
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = out_dir / f"{input_path.stem}_z80{input_path.suffix}"

    output_path.write_text(translated_content, encoding="utf-8")

    print(f"[translate-asm] OK — Translated {len(lines)} lines")
    print(f"[translate-asm] Output: {output_path}")
