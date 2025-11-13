# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from typing import Dict, List, Any
from abc import ABC, abstractmethod
from iatoolkit.common.util import Utility
from iatoolkit.infra.llm_response import LLMResponse
from iatoolkit.services.configuration_service import ConfigurationService
from iatoolkit.infra.openai_adapter import OpenAIAdapter
from iatoolkit.infra.gemini_adapter import GeminiAdapter
from iatoolkit.common.exceptions import IAToolkitException
from iatoolkit.repositories.models import Company
from openai import OpenAI
import google.generativeai as genai
import os
import threading
from enum import Enum
from injector import inject


class LLMProvider(Enum):
    OPENAI = "openai"
    GEMINI = "gemini"


class LLMAdapter(ABC):
    """common interface for LLM adapters"""

    @abstractmethod
    def create_response(self, *args, **kwargs) -> LLMResponse:
        pass


class LLMProxy:
    """
    Proxy que enruta las llamadas al adaptador correcto y gestiona la creación
    de los clientes de los proveedores de LLM.
    """
    _clients_cache = {}
    _clients_cache_lock = threading.Lock()

    @inject
    def __init__(self, util: Utility,
                 configuration_service: ConfigurationService,
                 openai_client = None,
                 gemini_client = None):
        """
        Inicializa una instancia del proxy. Puede ser una instancia "base" (fábrica)
        o una instancia de "trabajo" con clientes configurados.
        """
        self.util = util
        self.configuration_service = configuration_service
        self.openai_adapter = OpenAIAdapter(openai_client) if openai_client else None
        self.gemini_adapter = GeminiAdapter(gemini_client) if gemini_client else None

    def create_for_company(self, company: Company) -> 'LLMProxy':
        """
        Crea y configura una nueva instancia de LLMProxy para una empresa específica.
        """
        try:
            openai_client = self._get_llm_connection(company, LLMProvider.OPENAI)
        except IAToolkitException:
            openai_client = None

        try:
            gemini_client = self._get_llm_connection(company, LLMProvider.GEMINI)
        except IAToolkitException:
            gemini_client = None

        if not openai_client and not gemini_client:
            raise IAToolkitException(
                IAToolkitException.ErrorType.API_KEY,
                f"La empresa '{company.name}' no tiene configuradas API keys para ningún proveedor LLM."
            )

        # Devuelve una NUEVA instancia con los clientes configurados
        return LLMProxy(
                    util=self.util,
                    configuration_service=self.configuration_service,
                    openai_client=openai_client,
                    gemini_client=gemini_client)

    def create_response(self, model: str, input: List[Dict], **kwargs) -> LLMResponse:
        """Enruta la llamada al adaptador correcto basado en el modelo."""
        # Se asume que esta instancia ya tiene los clientes configurados por `create_for_company`
        if self.util.is_openai_model(model):
            if not self.openai_adapter:
                raise IAToolkitException(IAToolkitException.ErrorType.API_KEY,
                                   f"No se configuró cliente OpenAI, pero se solicitó modelo OpenAI: {model}")
            return self.openai_adapter.create_response(model=model, input=input, **kwargs)
        elif self.util.is_gemini_model(model):
            if not self.gemini_adapter:
                raise IAToolkitException(IAToolkitException.ErrorType.API_KEY,
                                   f"No se configuró cliente Gemini, pero se solicitó modelo Gemini: {model}")
            return self.gemini_adapter.create_response(model=model, input=input, **kwargs)
        else:
            raise IAToolkitException(IAToolkitException.ErrorType.LLM_ERROR, f"Modelo no soportado: {model}")

    def _get_llm_connection(self, company: Company, provider: LLMProvider) -> Any:
        """Obtiene una conexión de cliente para un proveedor, usando un caché para reutilizarla."""
        cache_key = f"{company.short_name}_{provider.value}"
        client = LLMProxy._clients_cache.get(cache_key)

        if not client:
            with LLMProxy._clients_cache_lock:
                client = LLMProxy._clients_cache.get(cache_key)
                if not client:
                    if provider == LLMProvider.OPENAI:
                        client = self._create_openai_client(company)
                    elif provider == LLMProvider.GEMINI:
                        client = self._create_gemini_client(company)
                    else:
                        raise IAToolkitException(f"provider not supported: {provider.value}")

                    if client:
                        LLMProxy._clients_cache[cache_key] = client

        if not client:
            raise IAToolkitException(IAToolkitException.ErrorType.API_KEY, f"No se pudo crear el cliente para {provider.value}")

        return client

    def _create_openai_client(self, company: Company) -> OpenAI:
        """Crea un cliente de OpenAI con la API key."""
        decrypted_api_key = ''
        llm_config = self.configuration_service.get_configuration(company.short_name, 'llm')

        # Try to get API key name from config first
        if llm_config and llm_config.get('api-key'):
            api_key_env_var = llm_config['api-key']
            decrypted_api_key = os.getenv(api_key_env_var, '')
        else:
            # Fallback to old logic
            if company.openai_api_key:
                decrypted_api_key = self.util.decrypt_key(company.openai_api_key)
            else:
                decrypted_api_key = os.getenv("OPENAI_API_KEY", '')

        if not decrypted_api_key:
            raise IAToolkitException(IAToolkitException.ErrorType.API_KEY,
                                     f"La empresa '{company.name}' no tiene API key de OpenAI.")
        return OpenAI(api_key=decrypted_api_key)

    def _create_gemini_client(self, company: Company) -> Any:
        """Configura y devuelve el cliente de Gemini."""

        decrypted_api_key = ''
        llm_config = self.configuration_service.get_configuration(company.short_name, 'llm')

        # Try to get API key name from config first
        if llm_config and llm_config.get('api-key'):
            api_key_env_var = llm_config['api-key']
            decrypted_api_key = os.getenv(api_key_env_var, '')
        else:
            # Fallback to old logic
            if company.gemini_api_key:
                decrypted_api_key = self.util.decrypt_key(company.gemini_api_key)
            else:
                decrypted_api_key = os.getenv("GEMINI_API_KEY", '')

        if not decrypted_api_key:
            return None
        genai.configure(api_key=decrypted_api_key)
        return genai

