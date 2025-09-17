# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

from infra.connectors.file_connector import FileConnector
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.service_account import Credentials
import io
from typing import List


class GoogleDriveConnector(FileConnector):
    def __init__(self, folder_id: str, service_account_path: str = "service_account.json"):
        """
        Inicializa el conector de Google Drive utilizando la API oficial de Google.
        :param folder_id: ID de la carpeta en Google Drive.
        :param service_account_path: Ruta al archivo JSON de la cuenta de servicio.
        """
        self.folder_id = folder_id
        self.service_account_path = service_account_path
        self.drive_service = self._authenticate()

    def _authenticate(self):
        """
        Autentica en Google Drive utilizando una cuenta de servicio.
        """
        # Cargar credenciales desde el archivo de servicio
        credentials = Credentials.from_service_account_file(
            self.service_account_path,
            scopes=["https://www.googleapis.com/auth/drive"]
        )

        # Crear el cliente de Google Drive API
        service = build('drive', 'v3', credentials=credentials)
        return service

    def list_files(self) -> List[dict]:
        """
        Estándar: Lista todos los archivos como diccionarios con claves 'path', 'name' y 'metadata'.
        """
        query = f"'{self.folder_id}' in parents and trashed=false"
        results = self.drive_service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])

        return [
            {
                "path": file['id'],  # ID único del archivo en Google Drive
                "name": file['name'],  # Nombre del archivo en Google Drive
                "metadata": {}  # No hay metadatos adicionales en este caso
            }
            for file in files
        ]

    def get_file_content(self, file_path: str) -> bytes:
        """
        Obtiene el contenido de un archivo en Google Drive utilizando su ID (file_path).
        """
        request = self.drive_service.files().get_media(fileId=file_path)
        file_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(file_buffer, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()

        return file_buffer.getvalue()
