# SDSC Standards (ROM Tag and Debug Console)

## ROM Tag Specification
Provides additional metadata about a program beyond the standard SMS/GG header.
- **Fields**: Identification string ("SDSC"), version numbers, names (program, author, genre), and comments.

## Debug Console Specification
Protocol for emulators to provide a text-based debug output.
- **Commands**: Clear console (2), Set attribute (3), Move cursor (4).
- **Encoding**: Supports standard ASCII and special formatting (`%[width]<fmt><type>`).

---
Source: https://www.smspower.org/Development/SDSC
