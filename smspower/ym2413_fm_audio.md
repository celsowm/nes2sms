# YM2413 FM Audio (OPLL) Application Manual
Summary of primary functions and interfacing.

## Primary Functions
The YM2413 (OPLL) is an FM Sound Generator with a built-in 9-bit DAC.
- **Modes**: 9 melody sounds OR 6 melody sounds + 5 rhythm sounds.
- **Instruments ROM**: Built-in 15 melody tones and 5 rhythm tones.
- **Customization**: One user-definable tone register.

## Bus Control
- **CS, WE, A0**: Control signals for addressing and data transfer.
- **Addressing**: Wait 12 cycles of master clock after writing address.
- **Data Write**: Wait 84 cycles between successive writes.

## Interfacing
- **Clock**: Operates between 2 to 4 MHz (typically 3.579545 MHz).
- **Audio Output**: Requires external pulses and low-pass filter (20kHz).

---
Source: https://www.smspower.org/maxim/Documents/YM2413ApplicationManual
