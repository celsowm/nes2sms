"""Translation context for maintaining state during 6502 to Z80 translation."""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class TranslationContext:
    """
    Maintains state during translation of a function.

    SRP: Only maintains translation state.
    """

    current_function: str = ""
    local_labels: Dict[str, str] = field(default_factory=dict)  # 6502 -> Z80
    register_map: Dict[str, str] = field(
        default_factory=lambda: {
            "A": "a",
            "X": "b",
            "Y": "c",
        }
    )
    loop_labels: Dict[int, str] = field(default_factory=dict)  # addr -> label
    subroutine_stack: List[str] = field(default_factory=list)
    translated_code: List[str] = field(default_factory=list)
    temp_counter: int = 0
    in_loop: bool = False
    loop_depth: int = 0

    def generate_local_label(self, prefix: str = "L") -> str:
        """Generate unique local label."""
        label = f"{prefix}{self.temp_counter}"
        self.temp_counter += 1
        return label

    def get_z80_register(self, reg_6502: str) -> str:
        """Map 6502 register to Z80 register."""
        return self.register_map.get(reg_6502.upper(), "hl")

    def enter_loop(self, addr: int) -> str:
        """Mark loop entry."""
        if addr not in self.loop_labels:
            self.loop_labels[addr] = self.generate_local_label("loop")

        self.in_loop = True
        self.loop_depth += 1
        return self.loop_labels[addr]

    def exit_loop(self, addr: int):
        """Mark loop exit."""
        self.loop_depth -= 1
        if self.loop_depth == 0:
            self.in_loop = False

    def enter_subroutine(self, name: str):
        """Enter subroutine context."""
        self.subroutine_stack.append(name)
        self.current_function = name

    def exit_subroutine(self):
        """Exit subroutine context."""
        if self.subroutine_stack:
            self.subroutine_stack.pop()
        self.current_function = self.subroutine_stack[-1] if self.subroutine_stack else ""

    def add_code(self, line: str):
        """Add translated code line."""
        self.translated_code.append(line)

    def add_comment(self, comment: str):
        """Add comment line."""
        self.translated_code.append(f"; {comment}")

    def add_label(self, label: str):
        """Add label."""
        self.translated_code.append(f"{label}:")

    def get_code(self) -> str:
        """Get all translated code as string."""
        return "\n".join(self.translated_code)

    def reset(self):
        """Reset context for new translation."""
        self.current_function = ""
        self.local_labels.clear()
        self.loop_labels.clear()
        self.subroutine_stack.clear()
        self.translated_code.clear()
        self.temp_counter = 0
        self.in_loop = False
        self.loop_depth = 0
