# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

import pytest
from unittest.mock import MagicMock
from sqlalchemy import text # Para verificar el argumento de text()
import json
from datetime import datetime
from services.sql_service import SqlService
from repositories.database_manager import DatabaseManager
from common.util import Utility
from common.exceptions import AppException

class TestSqlService:
    def setup_method(self):

        self.db_manager_mock = MagicMock(spec=DatabaseManager)
        self.util_mock = MagicMock(spec=Utility)

        # Mock para la sesión de base de datos y el objeto de resultado de la consulta
        self.session_mock = MagicMock()
        self.mock_result_proxy = MagicMock() # Simula el objeto ResultProxy de SQLAlchemy

        # Configurar los mocks para que devuelvan otros mocks cuando sea necesario
        self.db_manager_mock.get_session.return_value = self.session_mock
        self.session_mock.execute.return_value = self.mock_result_proxy

        # Instanciar el servicio con las dependencias mockeadas
        self.service = SqlService(util=self.util_mock)

    def test_exec_sql_success_with_simple_data(self):
        """
        Prueba la ejecución exitosa de una consulta SQL que devuelve datos simples (int, str).
        En este caso, la función de serialización personalizada no debería ser invocada para estos tipos.
        """
        sql_statement = "SELECT id, name FROM users WHERE status = 'active'"
        expected_keys = ['id', 'name']
        # Datos que json.dumps puede manejar directamente
        expected_rows_from_db = [(1, 'Alice'), (2, 'Bob')]
        # Cómo se verán los datos después del procesamiento interno en exec_sql antes de json.dumps
        expected_rows_as_dicts = [{'id': 1, 'name': 'Alice'}, {'id': 2, 'name': 'Bob'}]

        self.mock_result_proxy.keys.return_value = expected_keys
        self.mock_result_proxy.fetchall.return_value = expected_rows_from_db

        # Ejecutar el método a probar
        result_json = self.service.exec_sql(self.db_manager_mock, sql_statement)

        # Verificar que la sesión y la ejecución fueron llamadas correctamente
        self.db_manager_mock.get_session.assert_called_once()
        self.session_mock.execute.assert_called_once()
        # Verificar que el argumento de execute fue el objeto text(sql_statement)
        args, _ = self.session_mock.execute.call_args
        assert isinstance(args[0], type(text(""))) # Comprueba el tipo del argumento
        assert str(args[0]) == sql_statement # Comprueba el contenido del SQL

        self.mock_result_proxy.keys.assert_called_once()
        self.mock_result_proxy.fetchall.assert_called_once()

        # Verificar que la función de serialización personalizada no fue llamada
        # para tipos que json.dumps maneja nativamente.
        self.util_mock.serialize.assert_not_called()

        # Verificar el resultado JSON
        expected_json_output = json.dumps(expected_rows_as_dicts)
        assert result_json == expected_json_output

    def test_exec_sql_success_with_custom_data_type_serialization(self):
        """
        Prueba la ejecución exitosa de una consulta SQL que devuelve datos que requieren
        serialización personalizada (ej. un objeto datetime).
        """
        sql_statement = "SELECT event_name, event_time FROM important_events"
        original_datetime_obj = datetime(2024, 1, 15, 10, 30, 0)
        # Suponemos que util.serialize convierte datetime a una string ISO
        serialized_datetime_str = original_datetime_obj.isoformat()

        expected_keys = ['event_name', 'event_time']
        # La base de datos devuelve una tupla con un objeto datetime
        expected_rows_from_db = [('Team Meeting', original_datetime_obj)]
        # El diccionario que se pasará a json.dumps, después de que serialize haga su trabajo
        expected_rows_as_dicts_after_serialization = [{'event_name': 'Team Meeting', 'event_time': serialized_datetime_str}]


        self.mock_result_proxy.keys.return_value = expected_keys
        self.mock_result_proxy.fetchall.return_value = expected_rows_from_db

        # Configurar el mock de util.serialize para que maneje datetime
        def mock_serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            # Para cualquier otro tipo, podría devolverlo tal cual si json.dumps lo maneja,
            # o lanzar un TypeError como lo haría json.dumps si default no estuviera.
            return obj
        self.util_mock.serialize.side_effect = mock_serializer

        # Ejecutar el método a probar
        result_json = self.service.exec_sql(self.db_manager_mock, sql_statement)

        # Verificar llamadas
        self.session_mock.execute.assert_called_once()
        self.mock_result_proxy.keys.assert_called_once()
        self.mock_result_proxy.fetchall.assert_called_once()

        # Verificar que util.serialize fue llamado para el objeto datetime
        self.util_mock.serialize.assert_called_once_with(original_datetime_obj)

        # Verificar el resultado JSON
        expected_json_output = json.dumps(expected_rows_as_dicts_after_serialization)
        assert result_json == expected_json_output

    def test_exec_sql_success_no_results(self):
        """
        Prueba la ejecución de una consulta SQL que no devuelve resultados.
        """
        sql_statement = "SELECT id FROM users WHERE name = 'NonExistentUser'"
        expected_keys = ['id'] # Las claves se devuelven incluso sin filas
        expected_rows_from_db = []
        expected_rows_as_dicts = []

        self.mock_result_proxy.keys.return_value = expected_keys
        self.mock_result_proxy.fetchall.return_value = expected_rows_from_db

        result_json = self.service.exec_sql(self.db_manager_mock, sql_statement)

        self.session_mock.execute.assert_called_once()
        self.mock_result_proxy.keys.assert_called_once()
        self.mock_result_proxy.fetchall.assert_called_once()
        self.util_mock.serialize.assert_not_called() # No hay datos que necesiten serialización

        expected_json_output = json.dumps(expected_rows_as_dicts, indent=2)
        assert result_json == expected_json_output

    def test_exec_sql_raises_app_exception_on_database_error(self):
        """
        Prueba que se lanza una AppException cuando ocurre un error en la base de datos.
        """
        sql_statement = "SELECT * FROM table_that_does_not_exist"
        original_db_error_message = "Error: Table not found"
        # Configurar el mock para que lance una excepción cuando se llame a execute
        self.session_mock.execute.side_effect = Exception(original_db_error_message)

        with pytest.raises(AppException) as exc_info:
            self.service.exec_sql(self.db_manager_mock, sql_statement)

        # Verificar el tipo de excepción y el mensaje
        assert exc_info.value.error_type == AppException.ErrorType.DATABASE_ERROR
        assert original_db_error_message in str(exc_info.value)
        # Verificar que la excepción original está encadenada (from e)
        assert isinstance(exc_info.value.__cause__, Exception)
        assert str(exc_info.value.__cause__) == original_db_error_message

        # Verificar que se intentó ejecutar la consulta
        self.session_mock.execute.assert_called_once()
        # Otros mocks no deberían haber sido llamados si execute falló
        self.mock_result_proxy.keys.assert_not_called()
        self.mock_result_proxy.fetchall.assert_not_called()
        self.util_mock.serialize.assert_not_called()
