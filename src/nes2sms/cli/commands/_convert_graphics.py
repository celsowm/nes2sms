"""Graphics-focused helpers for the convert command."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ...core.graphics import PaletteMapper, TileConverter
from ...core.graphics.oam_extractor import OamExtractor
from ...core.graphics.palette_extractor import PaletteExtractor
from ...core.graphics.runtime_asset_builder import (
    build_blank_sat,
    build_blank_tilemap,
    build_runtime_background_assets,
)
from ...core.graphics.runtime_capture import sprites_from_runtime_oam
from ...core.graphics.runtime_capture import assess_runtime_capture
from ...infrastructure.asset_writer import AssetWriter
from ...infrastructure.fceux_runtime_capture import (
    FceuxRuntimeCaptureConfig,
    capture_runtime_graphics,
)
from ...shared.models import TileConversionResult


@dataclass
class GraphicsConversionArtifacts:
    """Visual assets prepared for the generated SMS scaffold."""

    bg_pal: bytes
    spr_pal: bytes
    tile_result: TileConversionResult
    color_maps: List[List[int]] = field(default_factory=list)
    tilemap_bin: bytes = b""
    sat_y: bytes = b""
    sat_xt: bytes = b""
    sprite_variant_map: bytes = b""
    sprite_variant_profile: Dict[str, object] = field(default_factory=dict)
    sprite_variant_lookup: Dict[Tuple[int, int], int] = field(default_factory=dict)
    oam_sprites: List[Dict[str, int]] = field(default_factory=list)


def capture_runtime_snapshot(args, loader, nes_path: Path, out_dir: Path):
    """Capture a runtime frame when the selected graphics source requires it."""
    graphics_source = getattr(args, "graphics_source", "runtime")
    if not (loader.prg_data and loader.chr_data) or graphics_source not in ("runtime", "hybrid"):
        return None

    print("[3b/6] Capturing runtime graphics...")
    try:
        runtime_capture = capture_runtime_graphics(
            FceuxRuntimeCaptureConfig(
                nes_path=nes_path.resolve(),
                output_dir=(out_dir / "work" / "runtime_capture").resolve(),
                mirroring=loader.header.mirroring,
                capture_frame=int(getattr(args, "capture_frame", 120)),
                timeout_seconds=int(getattr(args, "capture_timeout_seconds", 30)),
            )
        )
        is_usable, reason = assess_runtime_capture(runtime_capture)
        if not is_usable:
            raise RuntimeError(f"Runtime snapshot is invalid: {reason}")
        print(
            f"      Runtime snapshot captured at frame {runtime_capture.frame}"
            f" | scroll=({runtime_capture.scroll_x},{runtime_capture.scroll_y})"
        )
        print()
        return runtime_capture
    except Exception as exc:
        if graphics_source == "runtime":
            raise RuntimeError(f"Runtime graphics capture failed: {exc}") from exc
        print(f"      WARNING: Runtime graphics capture failed: {exc}")
        print("      Falling back to static graphics pipeline")
        print()
        return None


def prepare_graphics_assets(args, loader, bank_map: dict, runtime_capture) -> GraphicsConversionArtifacts:
    """Build all visual artifacts needed by the generated SMS project."""
    split_y = int(getattr(args, "split_y", 48))
    split_tile = max(0, min(27, split_y // 8))
    bg_pal, spr_pal, color_maps = _build_palettes(loader, runtime_capture)
    tile_result = _convert_tiles(args, loader, bank_map, runtime_capture, color_maps)
    tilemap_bin = build_blank_tilemap(split_tile=split_tile)
    sat_y, sat_xt = build_blank_sat()
    oam_sprites = _extract_oam_sprites(loader, runtime_capture, tile_result)

    if runtime_capture and loader.chr_data:
        runtime_bg = build_runtime_background_assets(
            runtime_capture,
            chr_data=loader.chr_data,
            tile_result=tile_result,
            color_maps=color_maps,
            split_tile=split_tile,
        )
        tilemap_bin = runtime_bg["tilemap"]
        for warning in runtime_bg["warnings"]:
            print(f"[4c] WARNING: {warning}")
        print("[4c] Built runtime tilemap.bin from captured nametable/attributes")

    sprite_variant_map = _build_default_sprite_variant_map()
    sprite_variant_profile = {
        "split_y": split_y,
        "entries": [],
        "resolved_variants": [],
        "priority": {"top": 0, "bottom": 0},
        "warnings": [],
    }
    sprite_variant_lookup: Dict[Tuple[int, int], int] = {}
    if loader.chr_data and oam_sprites:
        variant_result = _apply_profiled_sprite_variants(
            chr_data=loader.chr_data,
            tile_result=tile_result,
            oam_sprites=oam_sprites,
            color_maps=color_maps,
            split_y=split_y,
        )
        sprite_variant_lookup = variant_result["lookup"]
        sprite_variant_map = variant_result["variant_map"]
        sprite_variant_profile = variant_result["profile"]
        for warning in variant_result["warnings"]:
            print(f"[4c] WARNING: {warning}")
    elif not loader.chr_data:
        sprite_variant_profile["warnings"] = ["No CHR data available; using default sprite variant map."]

    if oam_sprites:
        oam_extractor = OamExtractor(loader.prg_data or b"", len(loader.chr_data or b"") // 16)
        sat_y, sat_xt = oam_extractor.to_sms_sat(
            oam_sprites,
            variant_lookup=sprite_variant_lookup,
            y_offset=1,
        )

    total_size = sum(len(tile) for tile in tile_result.sms_tiles)
    print(f"[4c] Final tiles: {len(tile_result.sms_tiles)} | {total_size // 1024}KB")
    print("[4c] Wrote tilemap.bin + sat_y.bin + sat_xt.bin + sprite_variant_map.bin")

    return GraphicsConversionArtifacts(
        bg_pal=bg_pal,
        spr_pal=spr_pal,
        tile_result=tile_result,
        color_maps=color_maps,
        tilemap_bin=tilemap_bin,
        sat_y=sat_y,
        sat_xt=sat_xt,
        sprite_variant_map=sprite_variant_map,
        sprite_variant_profile=sprite_variant_profile,
        sprite_variant_lookup=sprite_variant_lookup,
        oam_sprites=oam_sprites,
    )


def write_graphics_assets(writer: AssetWriter, graphics: GraphicsConversionArtifacts) -> None:
    """Persist generated graphics artifacts to the output assets directory."""
    writer.write_palette(graphics.bg_pal, "bg")
    writer.write_palette(graphics.spr_pal, "spr")
    writer.write_tiles(graphics.tile_result.sms_tiles)
    writer.write_flip_index(graphics.tile_result.flip_index)
    writer.write_tile_symbols(graphics.tile_result.tile_metadata, "assets")
    writer.write_binary("tilemap.bin", graphics.tilemap_bin, "assets")
    writer.write_binary("sat_y.bin", graphics.sat_y, "assets")
    writer.write_binary("sat_xt.bin", graphics.sat_xt, "assets")
    writer.write_binary("sprite_variant_map.bin", graphics.sprite_variant_map, "assets")
    writer.write_json("sprite_variant_profile.json", graphics.sprite_variant_profile, "assets")


def _build_palettes(loader, runtime_capture) -> Tuple[bytes, bytes, List[List[int]]]:
    nes_palette_ram = None
    if runtime_capture:
        nes_palette_ram = runtime_capture.palette_ram
        print("      Using runtime palette capture")
    elif loader.prg_data:
        pal_extractor = PaletteExtractor(loader.prg_data)
        nes_palette_ram = pal_extractor.extract_palette()
        if nes_palette_ram:
            print("      Extracted palette from ROM PRG code")

    palette_mapper = PaletteMapper(nes_palette_ram=nes_palette_ram)
    bg_pal, spr_pal, color_maps = palette_mapper.build_all_palettes()
    print("      Palettes prepared: palette_bg.bin + palette_spr.bin")
    return bg_pal, spr_pal, color_maps


def _convert_tiles(args, loader, bank_map: dict, runtime_capture, color_maps: List[List[int]]) -> TileConversionResult:
    if not loader.chr_data:
        print("      No CHR data found; using a single blank fallback tile")
        return TileConversionResult(
            sms_tiles=[bytes(32)],
            flip_index={},
            warnings=["No CHR data available; using blank fallback tile."],
            tile_metadata=[{"bank": 0, "tile_index": 0}],
        )

    tile_converter = TileConverter(
        color_maps=color_maps[:4],
        flip_strategy="none"
        if runtime_capture
        else (args.flip_strategy if hasattr(args, "flip_strategy") else "cache"),
        max_tiles=256 if runtime_capture else 512,
    )

    if bank_map.get("chr_banks", 1) > 1:
        chr_banks = _extract_chr_banks(loader.chr_data, bank_map)
        result = tile_converter.convert_multi_bank(chr_banks)
        print(f"      Multi-bank mode: {len(chr_banks)} banks")
    else:
        result = tile_converter.convert(loader.chr_data, bank_id=0)

    total_size = sum(len(tile) for tile in result.sms_tiles)
    print(f"      Base tiles: {len(result.sms_tiles)} | {total_size // 1024}KB")
    return result


def _extract_oam_sprites(loader, runtime_capture, tile_result: TileConversionResult) -> List[Dict[str, int]]:
    if runtime_capture:
        oam_sprites = sprites_from_runtime_oam(runtime_capture.oam)
        print(f"[4b] Captured {len(oam_sprites)} sprites from runtime OAM")
        print()
        return oam_sprites

    if not (loader.prg_data and loader.chr_data):
        return []

    chr_tile_count = len(loader.chr_data) // 16
    oam_extractor = OamExtractor(loader.prg_data, chr_tile_count)
    extracted_oam = oam_extractor.extract_oam_table()
    if not extracted_oam:
        return []

    tile_activity = OamExtractor.build_tile_activity(tile_result.sms_tiles)
    ratio = OamExtractor.nonempty_tile_ratio(extracted_oam, tile_activity)
    if not OamExtractor.is_confident_table(extracted_oam, tile_activity=tile_activity):
        print(f"[4b] Ignoring low-confidence OAM table ({ratio:.0%} referenced tiles are non-empty)")
        print("      Falling back to neutral SAT initialization")
        print()
        return []

    print(f"[4b] Extracted {len(extracted_oam)} sprites from OAM data")
    print(f"      OAM confidence: {ratio:.0%} referenced tiles are non-empty")
    print()
    return extracted_oam


def _extract_chr_banks(chr_data: bytes, banks_config: dict):
    chr_banks = []
    chr_bank_size = banks_config.get("chr_bank_size", 8192)
    num_chr_banks = banks_config.get("chr_banks", 1)

    for i in range(num_chr_banks):
        offset = i * chr_bank_size
        bank_data = chr_data[offset : offset + chr_bank_size]
        if bank_data:
            chr_banks.append((i, bank_data))

    return chr_banks


def _build_default_sprite_variant_map() -> bytes:
    """Build a default tile/attr map where each combo resolves to the base tile."""
    table = bytearray(256 * 16)
    for tile in range(256):
        base = tile * 16
        for combo in range(16):
            table[base + combo] = tile
    return bytes(table)


def _find_tile_index_within(tiles: List[bytes], candidate: bytes, max_index: int) -> Optional[int]:
    limit = min(max_index + 1, len(tiles))
    for idx in range(limit):
        if tiles[idx] == candidate:
            return idx
    return None


def _allocate_variant_slot(free_slots: List[int], tiles: List[bytes], max_index: int) -> Optional[int]:
    if free_slots:
        return free_slots.pop(0)
    if len(tiles) <= max_index:
        tiles.append(bytes(32))
        return len(tiles) - 1
    return None


def _apply_profiled_sprite_variants(
    chr_data: bytes,
    tile_result,
    oam_sprites: List[Dict],
    color_maps: List[List[int]],
    split_y: int = 48,
) -> Dict[str, object]:
    """
    Materialize profiled sprite variants and build runtime tile/attr lookup map.

    Variant generation is bounded to sprite-addressable tile indices (0-255).
    Unresolved combinations safely fall back to the base tile index.
    """
    warnings: List[str] = []
    tiles = tile_result.sms_tiles
    metadata = tile_result.tile_metadata
    flip_index = tile_result.flip_index
    max_sprite_tile = min(255, len(tiles) - 1)

    if max_sprite_tile < 0:
        return {
            "lookup": {},
            "variant_map": _build_default_sprite_variant_map(),
            "profile": {
                "split_y": split_y,
                "entries": [],
                "resolved_variants": [],
                "priority": {"top": 0, "bottom": 0},
                "warnings": ["No base tiles available for sprite variant mapping."],
            },
            "warnings": ["No base tiles available for sprite variant mapping."],
        }

    if len(color_maps) >= 8:
        sprite_maps = color_maps[4:8]
    elif len(color_maps) >= 4:
        sprite_maps = color_maps[:4]
    elif color_maps:
        sprite_maps = [color_maps[0], color_maps[0], color_maps[0], color_maps[0]]
    else:
        sprite_maps = [[0, 1, 2, 3]] * 4

    sprite_converter = TileConverter(color_maps=[sprite_maps[0]], flip_strategy="none")
    variant_lookup: Dict[Tuple[int, int], int] = {}
    observed_tiles = {
        int(spr.get("tile", 0)) & 0xFF
        for spr in oam_sprites
        if isinstance(spr.get("tile"), int) and 0 <= int(spr.get("tile", 0)) <= max_sprite_tile
    }
    free_slots = [
        idx for idx in range(max_sprite_tile + 1) if idx not in observed_tiles and not any(tiles[idx])
    ]

    profile_entries = OamExtractor.build_variant_profile(oam_sprites)
    resolved_variants = []

    for entry in profile_entries:
        tile = int(entry["tile"]) & 0xFF
        attr = int(entry["attr"]) & 0xFF
        combo = int(entry["combo"]) & 0x0F
        count = int(entry["count"])

        if tile > max_sprite_tile:
            warnings.append(
                f"Variant profile tile {tile} exceeds sprite index range 0-{max_sprite_tile}; fallback to base tile."
            )
            variant_lookup[(tile, combo)] = tile & 0xFF
            continue

        src_off = tile * 16
        if src_off + 16 > len(chr_data):
            warnings.append(f"Variant source tile {tile} is out of CHR bounds; fallback to base tile.")
            variant_lookup[(tile, combo)] = tile
            continue

        palette_idx = combo & 0x03
        tile_16 = chr_data[src_off : src_off + 16]
        variant_tile = sprite_converter.convert_tile_with_map(tile_16, sprite_maps[palette_idx])
        if combo & 0x04:
            variant_tile = TileConverter._flip_tile_h(variant_tile)
        if combo & 0x08:
            variant_tile = TileConverter._flip_tile_v(variant_tile)

        existing_idx = _find_tile_index_within(tiles, variant_tile, max_sprite_tile)
        if existing_idx is not None:
            mapped_idx = existing_idx
        else:
            slot = _allocate_variant_slot(free_slots, tiles, max_sprite_tile)
            if slot is None:
                warnings.append(
                    f"No sprite tile slots left for tile={tile} attr=${attr:02X} combo={combo}; fallback to base tile."
                )
                mapped_idx = tile
            else:
                tiles[slot] = variant_tile
                if slot < len(metadata):
                    metadata[slot] = {
                        "bank": metadata[slot].get("bank", 0),
                        "tile_index": tile,
                        "variant_combo": combo,
                        "variant_attr": attr,
                    }
                else:
                    metadata.append(
                        {
                            "bank": 0,
                            "tile_index": tile,
                            "variant_combo": combo,
                            "variant_attr": attr,
                        }
                    )
                mapped_idx = slot

        variant_lookup[(tile, combo)] = mapped_idx
        flip_index[f"{tile}_A{attr:02X}"] = mapped_idx
        resolved_variants.append(
            {
                "tile": tile,
                "attr": attr,
                "combo": combo,
                "count": count,
                "mapped_tile": mapped_idx,
            }
        )

    variant_map = bytearray(_build_default_sprite_variant_map())
    for (tile, combo), mapped in variant_lookup.items():
        if 0 <= tile < 256 and 0 <= combo < 16:
            variant_map[tile * 16 + combo] = mapped & 0xFF

    priority_top = sum(
        1
        for spr in oam_sprites
        if (int(spr.get("attr", 0)) & 0x20) and int(spr.get("y", 0)) < split_y
    )
    priority_bottom = sum(
        1
        for spr in oam_sprites
        if (int(spr.get("attr", 0)) & 0x20) and int(spr.get("y", 0)) >= split_y
    )

    profile = {
        "split_y": split_y,
        "entries": profile_entries,
        "resolved_variants": resolved_variants,
        "priority": {"top": priority_top, "bottom": priority_bottom},
        "warnings": warnings,
    }
    return {
        "lookup": variant_lookup,
        "variant_map": bytes(variant_map),
        "profile": profile,
        "warnings": warnings,
    }
