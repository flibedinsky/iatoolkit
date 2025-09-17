# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

from dataclasses import dataclass
from typing import Dict, List, Any, Optional

@dataclass
class ToolCall:
    """Representa una llamada a herramienta en formato común"""
    call_id: str
    type: str  # 'function_call'
    name: str
    arguments: str


@dataclass
class Usage:
    """Información de uso de tokens en formato común"""
    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass
class LLMResponse:
    """Estructura común para respuestas de diferentes LLMs"""
    id: str
    model: str
    status: str  # 'completed', 'failed', etc.
    output_text: str
    output: List[ToolCall]  # lista de tool calls
    usage: Usage

    def __post_init__(self):
        """Asegura que output sea una lista"""
        if self.output is None:
            self.output = []

