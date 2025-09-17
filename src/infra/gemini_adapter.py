# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

from infra.llm_response import LLMResponse, ToolCall, Usage
from typing import Dict, List, Optional
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from google.protobuf.json_format import MessageToDict
from exceptions import AppException
import logging
import json
import uuid

class GeminiAdapter:
    """Adaptador para la API de Gemini"""

    def __init__(self, gemini_client):
        """Inicializar con cliente Gemini ya configurado"""
        self.client = gemini_client

        # Configuración de seguridad - permitir contenido que podría ser bloqueado por defecto
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

    def create_response(self,
                        model: str,
                        input: List[Dict],
                        previous_response_id: Optional[str] = None,
                        context_history: Optional[List[Dict]] = None,
                        tools: Optional[List[Dict]] = None,
                        text: Optional[Dict] = None,
                        reasoning: Optional[Dict] = None,
                        tool_choice: str = "auto",
                        ) -> LLMResponse:
        """Llamada a la API de Gemini y mapeo a estructura común"""
        try:
            # Inicializar el modelo de Gemini usando el cliente configurado
            gemini_model = self.client.GenerativeModel(
                model_name=self._map_model_name(model),
                safety_settings=self.safety_settings
            )

            # Preparar el contenido para Gemini
            if context_history:
                # Concatenar el historial de conversación con el input actual
                contents = self._prepare_gemini_contents(context_history + input)
            else:
                # Usar solo el input actual si no hay historial
                contents = self._prepare_gemini_contents(input)

            # Preparar herramientas si están disponibles
            gemini_tools = self._prepare_gemini_tools(tools) if tools else None

            # Configurar generación
            generation_config = self._prepare_generation_config(text, tool_choice)

            # Llamar a Gemini
            if gemini_tools:
                # Con herramientas
                response = gemini_model.generate_content(
                    contents,
                    tools=gemini_tools,
                    generation_config=generation_config
                )
            else:
                # Sin herramientas
                response = gemini_model.generate_content(
                    contents,
                    generation_config=generation_config
                )

            # map the answer to a common structure
            llm_response = self._map_gemini_response(response, model)

            # add the model answer to the history
            if context_history and llm_response.output_text:
                context_history.append(
                    {
                        'role': 'assistant',
                        'context': llm_response.output_text
                    }
                )

            return llm_response

        except Exception as e:
            error_message = f"Error calling Gemini API: {str(e)}"
            logging.error(error_message)

            # handle gemini specific errors
            if "quota" in str(e).lower():
                error_message = "Se ha excedido la cuota de la API de Gemini"
            elif "blocked" in str(e).lower():
                error_message = "El contenido fue bloqueado por las políticas de seguridad de Gemini"
            elif "token" in str(e).lower():
                error_message = "Tu consulta supera el límite de contexto de Gemini"

            raise AppException(AppException.ErrorType.LLM_ERROR, error_message)

    # ... rest of the methods keep the same ...
    def _map_model_name(self, model: str) -> str:
        """Mapear nombre del modelo a formato de Gemini"""
        model_mapping = {
            "gemini-pro": "gemini-2.5-pro",
            "gemini": "gemini-2.5-pro",
            "gemini-1.5": "gemini-2.5-pro",
            "gemini-flash": "gemini-1.5-flash",
            "gemini-2.0": "gemini-2.0-flash-exp"
        }
        return model_mapping.get(model.lower(), model)

    def _prepare_gemini_contents(self, input: List[Dict]) -> List[Dict]:
        """Convertir mensajes de formato OpenAI a formato Gemini"""
        gemini_contents = []

        for message in input:
            if message.get("role") == "system":
                gemini_contents.append({
                    "role": "user",
                    "parts": [{"text": f"[INSTRUCCIONES DEL SISTEMA]\n{message.get('content', '')}"}]
                })
            elif message.get("role") == "user":
                gemini_contents.append({
                    "role": "user",
                    "parts": [{"text": message.get("content", "")}]
                })
            elif message.get("type") == "function_call_output":
                gemini_contents.append({
                    "role": "function",
                    "parts": [{
                        "function_response": {
                            "name": "tool_result",
                            "response": {"output": message.get("output", "")}
                        }
                    }]
                })

        return gemini_contents

    def _prepare_gemini_tools(self, tools: List[Dict]) -> List[Dict]:
        """Convertir herramientas de formato OpenAI a formato Gemini"""
        if not tools:
            return None

        function_declarations = []
        for i, tool in enumerate(tools):
            # Verificar estructura básica
            tool_type = tool.get("type")

            if tool_type != "function":
                logging.warning(f"Herramienta {i} no es de tipo 'function': {tool_type}")
                continue

            # Extraer datos de la herramienta (estructura plana)
            function_name = tool.get("name")
            function_description = tool.get("description", "")
            function_parameters = tool.get("parameters", {})

            # Verificar si el nombre existe y no está vacío
            if not function_name or not isinstance(function_name, str) or not function_name.strip():
                logging.error(f"PROBLEMA: Herramienta {i} sin nombre válido")
                continue

            # Preparar la declaración de función para Gemini
            gemini_function = {
                "name": function_name,
                "description": function_description,
            }

            # Agregar parámetros si existen y limpiar campos específicos de OpenAI
            if function_parameters:
                clean_parameters = self._clean_openai_specific_fields(function_parameters)
                gemini_function["parameters"] = clean_parameters

            function_declarations.append(gemini_function)

        if function_declarations:
            final_tools = [{
                "function_declarations": function_declarations
            }]

            # Log de la estructura final para debug
            # logging.info("Estructura final de herramientas para Gemini:")
            # logging.info(f"{json.dumps(final_tools, indent=2)}")

            return final_tools

        return None


    def _clean_openai_specific_fields(self, parameters: Dict) -> Dict:
        """Limpiar campos específicos de OpenAI que Gemini no entiende"""
        clean_params = {}

        # Campos permitidos por Gemini según su Schema protobuf
        # Estos son los únicos campos que Gemini acepta en sus esquemas
        allowed_fields = {
            "type",  # Tipo de datos: string, number, object, array, boolean
            "properties",  # Para objetos: define las propiedades
            "required",  # Array de propiedades requeridas
            "items",  # Para arrays: define el tipo de elementos
            "description",  # Descripción del campo
            "enum",  # Lista de valores permitidos
            # Gemini NO soporta estos campos comunes de JSON Schema:
            # "pattern", "format", "minimum", "maximum", "minItems", "maxItems",
            # "minLength", "maxLength", "additionalProperties", "strict"
        }

        for key, value in parameters.items():
            if key in allowed_fields:
                if key == "properties" and isinstance(value, dict):
                    # Limpiar recursivamente las propiedades
                    clean_props = {}
                    for prop_name, prop_def in value.items():
                        if isinstance(prop_def, dict):
                            clean_props[prop_name] = self._clean_openai_specific_fields(prop_def)
                        else:
                            clean_props[prop_name] = prop_def
                    clean_params[key] = clean_props
                elif key == "items" and isinstance(value, dict):
                    # Limpiar recursivamente los items de array
                    clean_params[key] = self._clean_openai_specific_fields(value)
                else:
                    clean_params[key] = value
            else:
                logging.debug(f"Campo '{key}' removido (no soportado por Gemini)")

        return clean_params

    def _prepare_generation_config(self, text: Optional[Dict], tool_choice: str) -> Dict:
        """Preparar configuración de generación para Gemini"""
        config = {"candidate_count": 1}

        if text:
            if "temperature" in text:
                config["temperature"] = float(text["temperature"])
            if "max_tokens" in text:
                config["max_output_tokens"] = int(text["max_tokens"])
            if "top_p" in text:
                config["top_p"] = float(text["top_p"])

        return config

    def _map_gemini_response(self, gemini_response, model: str) -> LLMResponse:
        """Mapear respuesta de Gemini a estructura común"""
        response_id = str(uuid.uuid4())
        output_text = ""
        tool_calls = []

        if gemini_response.candidates and len(gemini_response.candidates) > 0:
            candidate = gemini_response.candidates[0]

            for part in candidate.content.parts:
                if hasattr(part, 'text') and part.text:
                    output_text += part.text
                elif hasattr(part, 'function_call') and part.function_call:
                    func_call = part.function_call
                    tool_calls.append(ToolCall(
                        call_id=f"call_{uuid.uuid4().hex[:8]}",
                        type="function_call",
                        name=func_call.name,
                        arguments=json.dumps(MessageToDict(func_call._pb).get('args', {}))
                    ))

        # Determinar status
        status = "completed"
        if gemini_response.candidates:
            candidate = gemini_response.candidates[0]
            if hasattr(candidate, 'finish_reason'):
                # Manejar finish_reason tanto como objeto con .name como entero/enum directo
                finish_reason = candidate.finish_reason

                # Si finish_reason tiene un atributo .name, usarlo
                if hasattr(finish_reason, 'name'):
                    finish_reason_name = finish_reason.name
                else:
                    # Si es un entero o enum directo, convertirlo a string
                    finish_reason_name = str(finish_reason)

                if finish_reason_name in ["SAFETY", "RECITATION", "3", "4"]:  # Agregar valores numéricos también
                    status = "blocked"
                elif finish_reason_name in ["MAX_TOKENS", "LENGTH", "2"]:  # Agregar valores numéricos también
                    status = "length_exceeded"

        # Calcular usage de tokens
        usage = self._extract_usage_metadata(gemini_response)

        # Estimación básica si no hay datos de usage
        if usage.total_tokens == 0:
            estimated_output_tokens = len(output_text) // 4
            usage = Usage(
                input_tokens=0,
                output_tokens=estimated_output_tokens,
                total_tokens=estimated_output_tokens
            )

        return LLMResponse(
            id=response_id,
            model=model,
            status=status,
            output_text=output_text,
            output=tool_calls,
            usage=usage
        )

    def _extract_usage_metadata(self, gemini_response) -> Usage:
        """Extraer información de uso de tokens de manera segura"""
        input_tokens = 0
        output_tokens = 0
        total_tokens = 0

        try:
            # Verificar si existe usage_metadata
            if hasattr(gemini_response, 'usage_metadata') and gemini_response.usage_metadata:
                usage_metadata = gemini_response.usage_metadata

                # Acceder a los atributos directamente, no con .get()
                if hasattr(usage_metadata, 'prompt_token_count'):
                    input_tokens = usage_metadata.prompt_token_count
                if hasattr(usage_metadata, 'candidates_token_count'):
                    output_tokens = usage_metadata.candidates_token_count
                if hasattr(usage_metadata, 'total_token_count'):
                    total_tokens = usage_metadata.total_token_count

        except Exception as e:
            logging.warning(f"No se pudo extraer usage_metadata de Gemini: {e}")

        # Si no hay datos de usage o son cero, hacer estimación básica
        if total_tokens == 0 and output_tokens == 0:
            # Obtener texto de salida para estimación
            output_text = ""
            if (hasattr(gemini_response, 'candidates') and
                    gemini_response.candidates and
                    len(gemini_response.candidates) > 0):

                candidate = gemini_response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            output_text += part.text

            # Estimación básica (4 caracteres por token aproximadamente)
            estimated_output_tokens = len(output_text) // 4 if output_text else 0
            output_tokens = estimated_output_tokens
            total_tokens = estimated_output_tokens

        return Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens
        )
