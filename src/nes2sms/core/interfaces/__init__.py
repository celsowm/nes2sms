"""Core interfaces for SOLID architecture."""

from .i_disassembler import IDisassembler, DisassemblyResult
from .i_translator import ITranslator
from .i_control_flow_analyzer import IControlFlowAnalyzer, ControlFlowGraph, BasicBlock

__all__ = [
    "IDisassembler",
    "DisassemblyResult",
    "ITranslator",
    "IControlFlowAnalyzer",
    "ControlFlowGraph",
    "BasicBlock",
]
