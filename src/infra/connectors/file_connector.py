# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

from abc import ABC, abstractmethod
from typing import List


class FileConnector(ABC):
    @abstractmethod
    def list_files(self) -> List[str]:
        pass

    @abstractmethod
    def get_file_content(self, file_path: str) -> bytes:
        pass