import unittest
from unittest.mock import patch
from services.user_session_context_service import UserSessionContextService


class TestUserSessionContextService(unittest.TestCase):

    def setUp(self):
        """Configura el servicio y los mocks antes de cada test."""
        self.service = UserSessionContextService()
        self.company_short_name = "test_company"
        self.user_identifier = "test_user"

        # Definir las claves esperadas para reutilizarlas en los tests
        self.history_key = f"llm_history:{self.company_short_name}/{self.user_identifier}"
        self.data_key = f"user_data:{self.company_short_name}/{self.user_identifier}"

        # Patchear la dependencia RedisSessionManager para aislar el servicio
        self.redis_patcher = patch("services.user_session_context_service.RedisSessionManager")
        self.mock_redis_manager = self.redis_patcher.start()

    def tearDown(self):
        """Limpia los patches después de cada test."""
        patch.stopall()

    def test_save_last_response_id(self):
        """Prueba que se guarda correctamente el ID de la última respuesta."""
        response_id = "resp_xyz"
        self.service.save_last_response_id(self.company_short_name, self.user_identifier, response_id)
        # Verificar que se llamó a Redis con la clave y valor correctos
        self.mock_redis_manager.set.assert_called_once_with(self.history_key, response_id)

    def test_get_last_response_id(self):
        """Prueba que se obtiene correctamente el ID de la última respuesta."""
        self.mock_redis_manager.get.return_value = "resp_abc"
        result = self.service.get_last_response_id(self.company_short_name, self.user_identifier)

        # Verificar que se llamó a Redis con la clave y el default correctos
        self.mock_redis_manager.get.assert_called_once_with(self.history_key, '')
        self.assertEqual(result, "resp_abc")

    def test_save_user_session_data(self):
        """Prueba que los datos de sesión del usuario se guardan como JSON."""
        data = {"role": "admin", "theme": "dark"}
        self.service.save_user_session_data(self.company_short_name, self.user_identifier, data)
        # Verificar que se llamó a set_json con la clave y los datos correctos
        self.mock_redis_manager.set_json.assert_called_once_with(self.data_key, data)

    def test_get_user_session_data(self):
        """Prueba que los datos de sesión del usuario se recuperan correctamente."""
        expected_data = {"role": "admin", "theme": "dark"}
        self.mock_redis_manager.get_json.return_value = expected_data

        result = self.service.get_user_session_data(self.company_short_name, self.user_identifier)

        # Verificar que se llamó a get_json con la clave y el default correctos
        self.mock_redis_manager.get_json.assert_called_once_with(self.data_key, {})
        self.assertEqual(result, expected_data)

    def test_clear_llm_history(self):
        """Prueba que el historial del LLM se limpia correctamente."""
        self.service.clear_llm_history(self.company_short_name, self.user_identifier)
        # Verificar que se llamó a remove con la clave del historial
        self.mock_redis_manager.remove.assert_called_once_with(self.history_key)

    def test_clear_user_session_data(self):
        """Prueba que los datos de sesión del usuario se limpian correctamente."""
        self.service.clear_user_session_data(self.company_short_name, self.user_identifier)
        # Verificar que se llamó a remove con la clave de datos de usuario
        self.mock_redis_manager.remove.assert_called_once_with(self.data_key)

    def test_clear_all_context(self):
        """Prueba que se limpian ambos contextos (historial y datos de usuario)."""
        self.service.clear_all_context(self.company_short_name, self.user_identifier)

        # Verificar que se llamó a remove para ambas claves
        self.mock_redis_manager.remove.assert_any_call(self.history_key)
        self.mock_redis_manager.remove.assert_any_call(self.data_key)
        # Asegurarse de que se hicieron exactamente dos llamadas a remove
        self.assertEqual(self.mock_redis_manager.remove.call_count, 2)

    def test_methods_do_nothing_with_none_user_identifier(self):
        """
        Prueba que ningún método interactúa con Redis si el user_identifier es None.
        """
        user_id = None

        # Probar métodos de escritura
        self.service.save_last_response_id(self.company_short_name, user_id, "id_1")
        self.service.save_user_session_data(self.company_short_name, user_id, {"data": "value"})
        self.service.clear_all_context(self.company_short_name, user_id)

        # Probar métodos de lectura
        get_id_result = self.service.get_last_response_id(self.company_short_name, user_id)
        get_data_result = self.service.get_user_session_data(self.company_short_name, user_id)

        # Verificar que NUNCA se llamó a Redis
        self.mock_redis_manager.set.assert_not_called()
        self.mock_redis_manager.get.assert_not_called()
        self.mock_redis_manager.set_json.assert_not_called()
        self.mock_redis_manager.get_json.assert_not_called()
        self.mock_redis_manager.remove.assert_not_called()

        # Verificar que los métodos de lectura devuelven valores seguros/por defecto
        self.assertIsNone(get_id_result)
        self.assertEqual(get_data_result, {})

    def test_methods_do_nothing_with_empty_user_identifier(self):
        """
        Prueba que ningún método interactúa con Redis si el user_identifier es una cadena vacía o espacios.
        """
        for user_id in ["", "   "]:
            # Probar métodos de escritura
            self.service.save_last_response_id(self.company_short_name, user_id, "id_1")
            self.service.save_user_session_data(self.company_short_name, user_id, {"data": "value"})
            self.service.clear_all_context(self.company_short_name, user_id)

            # Probar métodos de lectura
            get_id_result = self.service.get_last_response_id(self.company_short_name, user_id)
            get_data_result = self.service.get_user_session_data(self.company_short_name, user_id)

            # Verificar que los métodos de lectura devuelven valores seguros/por defecto
            self.assertIsNone(get_id_result)
            self.assertEqual(get_data_result, {})

        # Al final del bucle, verificar que NUNCA se llamó a Redis
        self.mock_redis_manager.set.assert_not_called()
        self.mock_redis_manager.get.assert_not_called()
        self.mock_redis_manager.set_json.assert_not_called()
        self.mock_redis_manager.get_json.assert_not_called()
        self.mock_redis_manager.remove.assert_not_called()

