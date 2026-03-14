# SMS Paging Scheme (SMSARCH Overview)
Overview of the paging mechanism and frame control registers.

## Memory Mapping
The Z80 can address 64KB, mapped as:
- **$0000-$3FFF**: Frame 0 (ROM Page 0).
- **$4000-$7FFF**: Frame 1 (ROM Page 1).
- **$8000-$BFFF**: Frame 2 (ROM Page 2 / Cartridge RAM).
- **$C000-$FFFF**: Program RAM.

## Frame Control Registers (FCR)
Physically located on the cartridge:
- **$FFFD**: Frame 0 (last 15KB).
- **$FFFE**: Frame 1.
- **$FFFF**: Frame 2.

*Note: The first 1KB ($0000-$03FF) is ALWAYS from ROM page 0 even when Frame 0 is paged.*

---
Source: https://www.smspower.org/uploads/Development/smsarch.html
