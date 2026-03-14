# SMS Paging Register Notes
from Mail Extract (paging.txt)

## Paging Registers $FFFC-$FFFF
- **$FFFC**: Control register.
- **$FFFD**: Page 0 ROM bank select.
- **$FFFE**: Page 1 ROM bank select.
- **$FFFF**: Page 2 ROM bank select.

### Read Behavior
- **$DFFE**: Returns the last byte written to $DFFE.
- **$DFFF**: Returns the last byte written to $DFFF.
- **$FFFE**: Returns the last byte written to $DFFE.
- **$FFFF**: Returns the last byte written to $DFFF.

### Write Behavior
- **$DFFE**: Writes directly to the register.
- **$DFFF**: Writes directly to the register.
- **$FFFE**: Writes `(byte & cart_size)` to $DFFE and pages in the corresponding ROM block at $4000-$7FFF.
- **$FFFF**: Writes `(byte & cart_size)` to $DFFF and pages in the corresponding ROM block at $8000-$BFFF.

### Cartridge Sizes and Paging
- For 256K cartridges, page numbers are $00-$0F.
- Some games (like Fantasy Zone) may write $F0-$FF; these should be ANDed with the cartridge size.
- 384K (3 Megabit) cartridges (e.g., Battleship on Game Gear) use an AND mask of $1F (treating as 512K).

---
Source: https://www.smspower.org/uploads/Development/paging.txt
