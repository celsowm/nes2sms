# Super Majik Spiral Crew's Guide to the SMS
by SMSC (v0.02)

## Overview
Based on Jon's guide and information from the SMS Preservation Society.

## Hardware
- **CPU**: Z80.
- **Cartridges**: 128k to 512k standard, potentially up to 4MB.

## Video Highlights
- Character-mapped screen.
- 32x28 internal size.
- 16-color palettes (2).
- Sprite characters can be 8x8 or 8x16.
- Hardware scrolling (positive direction mentioned, but bidirectional used in games).

## Controllers
- **Active Low Logic**: 0 = pressed.
- **Port $DC**: Up, Down, Left, Right, Button 1, Button 2 (Pad 1), Up, Down (Pad 2).
- **Port $DD**: Left, Right, Button 1, Button 2 (Pad 2), Reset button.

## Pause Button
- Generates NMI at $0066.
- Implementation must handle toggling game state manually in the NMI handler.

---
Source: https://www.smspower.org/uploads/Development/smsc.txt
