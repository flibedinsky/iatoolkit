# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import pytest
from unittest.mock import MagicMock, patch
from services.tasks_service import TaskService
from infra.call_service import CallServiceClient
from repositories.models import Task, TaskStatus, TaskType, Company
from common.exceptions import AppException
from datetime import datetime, timedelta


class TestTaskService:

    def setup_method(self):
        self.mock_task_repo = MagicMock()
        self.mock_query_service = MagicMock()
        self.mock_profile_repo = MagicMock()
        self.mock_call_service = MagicMock(spec=CallServiceClient)

        self.task_service = TaskService(
            task_repo=self.mock_task_repo,
            query_service=self.mock_query_service,
            profile_repo=self.mock_profile_repo,
            call_service=self.mock_call_service
        )

        self.mock_company = Company(id=1, name='test_company', short_name='test_company')
        self.mock_task_type = TaskType(id=10, prompt_template='prompt.tpl')

        self.task_mock = Task(
            company_id=self.mock_company.id,
            task_type_id=self.mock_task_type.id,
            company_task_id=0,
            client_data={"key": "value"},
            execute_at=datetime.now(),
            status=TaskStatus.pendiente,
            files=[]
            )
        self.task_mock.company = self.mock_company
        self.task_mock.task_type = self.mock_task_type

    def test_create_task_when_company_not_found(self):
        self.mock_profile_repo.get_company_by_short_name.return_value = None

        with pytest.raises(AppException) as excinfo:
            self.task_service.create_task(
                company_short_name="non_existent_company",
                task_type_name="test_task_type",
                client_data={}
            )

        assert excinfo.value.error_type == AppException.ErrorType.INVALID_NAME
        assert "No existe la empresa" in str(excinfo.value)

    def test_create_task_when_tasktype_not_found(self):
        self.mock_profile_repo.get_company_by_short_name.return_value = self.mock_company
        self.mock_task_repo.get_task_type.return_value = None

        with pytest.raises(AppException) as excinfo:
            self.task_service.create_task(
                company_short_name="test_company",
                task_type_name="non_existent_type",
                client_data={}
            )

        assert excinfo.value.error_type == AppException.ErrorType.INVALID_NAME
        assert "No existe el task_type" in str(excinfo.value)

    def test_create_task_when_future_execution(self):
        future_date = datetime.now() + timedelta(days=1)

        self.mock_profile_repo.get_company_by_short_name.return_value = self.mock_company
        self.mock_task_repo.get_task_type.return_value = self.mock_task_type
        self.mock_task_repo.create_task.return_value = self.task_mock
        self.task_mock.execute_at = future_date

        result_task = self.task_service.create_task(
            company_short_name="test_company",
            task_type_name="test_task_type",
            client_data={"key": "value"},
            execute_at=future_date
        )

        assert result_task.execute_at == future_date
        self.mock_query_service.llm_query.assert_not_called()
        self.mock_task_repo.update_task.assert_not_called()

    def test_create_task_when_ok(self):
        self.mock_profile_repo.get_company_by_short_name.return_value = self.mock_company
        self.mock_task_repo.get_task_type.return_value = self.mock_task_type
        self.mock_task_repo.create_task.return_value = self.task_mock

        result_task = self.task_service.create_task(
            company_short_name="test_company",
            task_type_name="test_task_type",
            client_data={"key": "value"},
        )

        assert result_task.status == TaskStatus.pendiente
        self.mock_query_service.llm_query.assert_not_called()

    def test_review_task_when_task_not_found(self):
        self.mock_task_repo.get_task_by_id.return_value = None

        with pytest.raises(AppException) as excinfo:
            self.task_service.review_task(task_id=99,
                                          review_user='pgonzalez',
                                          approved=True,
                                          comment='Validación aprobada')

        assert excinfo.value.error_type.name == "TASK_NOT_FOUND"

    def test_review_task_when_invalid_status(self):
        self.mock_task_repo.get_task_by_id.return_value = self.task_mock

        with pytest.raises(AppException) as excinfo:
            self.task_service.review_task(task_id=99,
                                          review_user='pgonzalez',
                                          approved=True,
                                          comment='Validación aprobada')

        assert excinfo.value.error_type.name == "INVALID_STATE"

    def test_review_task_when_ok(self):
        self.task_mock.status = TaskStatus.ejecutado
        self.mock_task_repo.get_task_by_id.return_value = self.task_mock

        result = self.task_service.review_task(task_id=99,
                                          review_user='pgonzalez',
                                          approved=True,
                                          comment='Validación aprobada')

        assert self.task_mock.status == TaskStatus.aprobada
        assert self.task_mock.approved == True
        self.mock_task_repo.update_task.assert_called_once_with(self.task_mock)


    def test_execute_task_when_llm_error(self):
        llm_response = {
            "query_id": 456,
            "valid_response": False,
            "error": "IA error"}
        self.mock_query_service.llm_query.return_value = llm_response

        with pytest.raises(AppException) as excinfo:
            self.task_service.execute_task(self.task_mock)

        assert excinfo.value.error_type == AppException.ErrorType.LLM_ERROR
        assert "IA error" in str(excinfo.value)


    def test_execute_task_when_llm_response_valid(self):
        llm_response = {"query_id": 123, "valid_response": True}
        self.mock_query_service.llm_query.return_value = llm_response
        result_task = self.task_service.execute_task(self.task_mock)

        assert result_task.llm_query_id == 123
        assert result_task.status == TaskStatus.ejecutado
        self.mock_task_repo.update_task.assert_called_once_with(result_task)

    def test_execute_task_when_exception_in_callback(self):
        llm_response = {
            "query_id": 123,
            "valid_response": True,
            "answer": 'an llm answer',
            "additional_data": {}
        }
        self.mock_query_service.llm_query.return_value = llm_response
        self.task_mock.callback_url = "http://test.com"
        self.mock_call_service.post.side_effect =Exception("timeout")
        with pytest.raises(AppException) as excinfo:
            result_task = self.task_service.execute_task(self.task_mock)

        assert excinfo.value.error_type == AppException.ErrorType.REQUEST_ERROR
        assert "timeout" in str(excinfo.value)

    def test_execute_task_when_llm_invalid_response(self):
        llm_response = {
            "query_id": 123,
            "valid_response": False,
            "answer": 'an llm answer',
            "additional_data": {}
        }
        self.mock_query_service.llm_query.return_value = llm_response
        self.task_mock.callback_url = "http://test.com"
        self.task_mock.client_data = {"key": "value"}
        self.mock_call_service.post.return_value = {'status': 'ok'}, 200
        result_task = self.task_service.execute_task(self.task_mock)

        assert result_task.status == TaskStatus.fallida
        self.mock_call_service.post.assert_called_once()

    def test_execute_task_when_callback_ok(self):
        llm_response = {
            "query_id": 123,
            "valid_response": True,
            "answer": 'an llm answer',
            "additional_data": {}
        }
        self.mock_query_service.llm_query.return_value = llm_response
        self.task_mock.callback_url = "http://test.com"
        self.task_mock.client_data = {"key": "value"}
        self.mock_call_service.post.return_value = {'status': 'ok'}, 200
        result_task = self.task_service.execute_task(self.task_mock)

        assert result_task.llm_query_id == 123
        assert result_task.status == TaskStatus.ejecutado
        self.mock_call_service.post.assert_called_once()

    def test_trigger_pending_tasks_when_exception(self):
        self.mock_task_repo.get_pending_tasks.side_effect = Exception("Error al obtener tareas pendientes")
        with pytest.raises(AppException) as excinfo:
            self.task_service.trigger_pending_tasks('open')

        assert excinfo.value.error_type == AppException.ErrorType.TASK_EXECUTION_ERROR

    def test_trigger_pending_tasks_when_ok(self):
        self.mock_task_repo.get_pending_tasks.return_value = [self.task_mock]
        response = self.task_service.trigger_pending_tasks('open')

        assert response['message'] == '1 tareas ejecutadas.'

    @patch("services.tasks_service.secure_filename", return_value="secure_file.txt")
    def test_get_task_files_when_save_exception(self, mock_secure_filename):
        uploaded_file_mock = MagicMock()
        uploaded_file_mock.read.side_effect = Exception("Error Guardando")

        with pytest.raises(AppException) as excinfo:
            self.task_service.get_task_files([uploaded_file_mock])

        assert excinfo.value.error_type == AppException.ErrorType.FILE_IO_ERROR
        assert "Error al extraer el contenido del archivo secure_file.txt: Error Guardando" in str(excinfo.value)


    @patch("services.tasks_service.secure_filename", return_value="secure_file.txt")
    def test_get_task_files_when_success(self, mock_secure_filename):
        uploaded_file_mock = MagicMock()
        uploaded_file_mock.filename = "file.txt"
        uploaded_file_mock.content_type = "text/plain"

        # mockear el método save del archivo
        uploaded_file_mock.save = MagicMock()

        files_info = self.task_service.get_task_files([uploaded_file_mock])

        assert len(files_info) == 1
        assert files_info[0]['filename'] == "secure_file.txt"
        assert files_info[0]['type'] == "text/plain"

