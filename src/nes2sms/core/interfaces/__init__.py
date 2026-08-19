"""Core interfaces for SOLID architecture."""

from .i_control_flow_analyzer import BasicBlock, ControlFlowGraph, IControlFlowAnalyzer
from .i_disassembler import DisassemblyResult, IDisassembler
from .i_translator import ITranslator

__all__ = [
    "IDisassembler",
    "DisassemblyResult",
    "ITranslator",
    "IControlFlowAnalyzer",
    "ControlFlowGraph",
    "BasicBlock",
]
