# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import pytest
from unittest.mock import MagicMock
from flask import Flask
from views.tasks_view import TaskView
from services.tasks_service import TaskService
from repositories.profile_repo import ProfileRepo
from repositories.models import Company, ApiKey
from datetime import datetime


class TestTaskView:

    def setup_method(self):
        self.app = Flask(__name__)
        self.client = self.app.test_client()

        # Mock del TaskService
        self.mock_task_service = MagicMock(spec=TaskService)
        self.mock_profile_repo = MagicMock(spec=ProfileRepo)


        # Instanciamos la vista con el mock del servicio
        self.task_view = TaskView.as_view("tasks",
                                          task_service=self.mock_task_service,
                                          profile_repo=self.mock_profile_repo)
        self.app.add_url_rule('/tasks', view_func=self.task_view, methods=["POST"])

        # API Key exitosa
        self.api_key = ApiKey(key="test_key", company_id=100)
        self.api_key.company = Company(id=100, name="Test Company", short_name="test_company")
        self.mock_profile_repo.get_active_api_key_entry.return_value = self.api_key
        self.valid_header = {"Authorization": f"Bearer {self.api_key.key}"}

    @pytest.mark.parametrize("missing_field", ["company", "task_type", "client_data"])
    def test_post_when_missing_required_fields(self, missing_field):
        payload = {
            "company": "test_company",
            "task_type": "test_type",
            "client_data": {"key": "value"},
        }
        payload.pop(missing_field)

        response = self.client.post('/tasks',
                                    headers=self.valid_header,
                                    json=payload)

        assert response.status_code == 400
        assert response.get_json() == {
            "error": f"El campo {missing_field} es requerido"
        }

        self.mock_task_service.create_task.assert_not_called()

    def test_post_when_invalid_execute_at_format(self):
        payload = {
            "company": "test_company",
            "task_type": "test_type",
            "client_data": {"key": "value"},
            "execute_at": "fecha-invalida"
        }

        response = self.client.post('/tasks',
                                    headers=self.valid_header,
                                    json=payload)

        assert response.status_code == 400
        assert response.get_json() == {
            "error": "El formato de execute_at debe ser YYYY-MM-DD HH:MM:SS"
        }

        self.mock_task_service.create_task.assert_not_called()

    def test_post_when_internal_exception_error(self):
        self.mock_task_service.create_task.side_effect = Exception("Internal Error")

        payload = {
            "company": "test_company",
            "task_type": "test_type",
            "client_data": {"key": "value"}
        }

        response = self.client.post('/tasks',
                                    headers=self.valid_header,
                                    json=payload)

        assert response.status_code == 500
        assert response.get_json() == {
            "error": "Internal Error"
        }

        self.mock_task_service.create_task.assert_called_once()

    def test_post_when_successful_creation(self):
        mocked_task = MagicMock()
        mocked_task.id = 123
        mocked_task.status.name = "CREATED"
        self.mock_task_service.create_task.return_value = mocked_task

        payload = {
            "company": "test_company",
            "company_task_id": 100,
            "task_type": "test_type",
            "client_data": {"key": "value"},
            "execute_at": "2024-04-17 10:00:00"
        }

        response = self.client.post('/tasks', headers=self.valid_header,
                                    json=payload)

        assert response.status_code == 201
        assert response.get_json() == {
            "task_id": 123,
            "status": "CREATED"
        }

        execute_datetime = datetime.fromisoformat(payload["execute_at"])

        self.mock_task_service.create_task.assert_called_once_with(
            company_short_name="test_company",
            task_type_name="test_type",
            client_data={"key": "value"},
            company_task_id=100,
            execute_at=execute_datetime,
            files=[]
        )
