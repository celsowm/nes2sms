# SMS Paging Chips
Compiled from S8-Dev Forum and personal investigations.

## Introduction
Sega Master System cartridges use specialized paging chips to handle memory mapping for ROMs larger than 48KB. Common chips include 315-5208, 315-5235, and 315-5365.

## The 315-5208 Paging Chip
- **Capacity**: Handles up to 8 x 16KByte pages (1 Megabit / 128KB).
- **ROM Support**: Commonly used with 831000 ROM chips (28-pin).
- **EPROM Replacement**: 28-pin 831000 can be replaced with a 32-pin 27010 (1 Megabit) EPROM with specific mapping.

## The 315-5235 Paging Chip
- **Capacity**: Believed to handle up to 32 x 16KByte pages (4 Megabit / 512KB).
- **RAM Support**: Contains logic for handling battery-backup RAM (e.g., in Phantasy Star).
- **Dual ROMs**: Can support two 16-bit ROM chips using CE1 and CE2.

---
Source: https://www.smspower.org/Development/SMSPagingChips
