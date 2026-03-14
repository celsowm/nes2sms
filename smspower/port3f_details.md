# SMS Port $3F and Controller Port Details
by asynchronous (2001)

## Port $3F Summary
Port $3F is an I/O control register for controller ports.

### Bit Definitions
- **Bit 0**: Port 1, Button 2 direction (1=Input, 0=Output).
- **Bit 1**: Port 1, TH direction/enable (1=Input, 0=Output).
- **Bit 2**: Port 2, Button 2 direction (1=Input, 0=Output).
- **Bit 3**: Port 2, TH direction/enable (1=Input, 0=Output).
- **Bit 4**: Port 1, Button 2 output level (1=High, 0=Low).
- **Bit 5**: Port 1, TH output level (1=High, 0=Low*).
- **Bit 6**: Port 2, Button 2 output level (1=High, 0=Low).
- **Bit 7**: Port 2, TH output level (1=High, 0=Low*).

\* *Presumed inverted for Japanese machines.*

## Features
- **Genesis Controllers**: Can be used on SMS by toggling TH as an output (setting it high/low).
- **Lightgun Latching**: TH pins can be configured to latch the VDP pixel counter (port $7F).
- **Dual Lightguns**: Possible by enabling/disabling TH inputs via port $3F.
- **Nationalization**: Bits 5 and 7 relate to identifying the console's region.

---
Source: https://www.smspower.org/uploads/Development/port3f.txt
