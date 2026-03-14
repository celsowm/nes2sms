# SMS and Game Gear Programming Guide
by Jon (1993)

## Introduction
Covers the Sega Master System and Game Gear hardware for developers.

## Hardware Summary
- **Master System**: Cartridge port, joypad ports, Pause button, Reset button.
- **Game Gear**: Color LCD, Start button, two-player port.

## Video System
- **Resolution**: Internal 32x28 characters (256x224 pixels internally).
- **Characters**: 8x8 pixels, 4 bit planes (16 colors).
- **Palettes**: Two 16-color palettes (one for bg, one for sprites).
- **Scrolling**: Hardware support for X and Y axis.
- **Sprites**: 64 hardware sprites. Flipped sprites are NOT supported in hardware.

## I/O and Joypads
- **Active Low Logic**: 0 = pressed, 1 = released.
- **Port $DC**: Joypad 1 buttons.
- **Port $DD**: Joypad 2 buttons and Reset.
- **Pause**: Generates an NMI ($0066).
- **Start (GG only)**: Read via bit 7 of port $00.

## Two-Player Port (GG)
- **Method 1**: 7-bit bi-directional (Ports $01, $02).
- **Method 2 (Official)**: Byte-based with handshaking and NMI on receive (Ports $03, $04, $05).

---
Source: https://www.smspower.org/uploads/Development/jon.txt
