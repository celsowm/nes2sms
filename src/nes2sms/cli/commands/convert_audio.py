"""Convert audio command."""

from pathlib import Path

from ...infrastructure.asset_writer import AssetWriter


def cmd_convert_audio(args):
    """
    Convert NES APU to SMS PSG.

    TODO: Implement full APU → PSG conversion.
    Currently generates stub files.
    """
    prg_path = Path(args.prg)
    if not prg_path.exists():
        raise FileNotFoundError(f"PRG file not found: {prg_path}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # TODO: Implement APU scanning and PSG encoding
    # For now, create placeholder files

    writer = AssetWriter(out_dir)

    # Create events.json placeholder
    writer.write_json("events.json", [], subdir="audio")

    # Create psg_data.asm placeholder
    psg_asm = """; PSG Data
; TODO: Convert APU events to PSG data
; Strategy: {strategy}

.section "PSGData" FREE

PSG_Data:
    ; TODO: Add PSG tone/volume data
    ret

.ends
""".format(strategy=args.audio_strategy)

    writer.write_text("psg_data.asm", psg_asm, subdir="audio")

    print(f"[convert-audio] Audio conversion not yet implemented.")
    print(f"[convert-audio] Strategy: {args.audio_strategy}")
    print(f"[convert-audio] Created stub files in {out_dir}/audio/")
