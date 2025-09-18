# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

from repositories.database_manager import DatabaseManager
from common.util import Utility
from sqlalchemy import text
from injector import inject
import json
from common.exceptions import AppException


class SqlService:
    @inject
    def __init__(self,util: Utility):
        self.util = util

    def exec_sql(self, db_manager: DatabaseManager, sql_statement: str) -> str:
        try:
            # here the SQL is executed
            result = db_manager.get_session().execute(text(sql_statement))

            # get the column names
            cols = result.keys()

            # convert rows to dict
            rows_context = [dict(zip(cols, row)) for row in result.fetchall()]

            # Serialize to JSON with type convertion
            sql_result_json = json.dumps(rows_context, default=self.util.serialize)

            return sql_result_json
        except Exception as e:
            db_manager.get_session().rollback()

            error_message = str(e)
            if 'timed out' in str(e):
                error_message = 'Intentalo de nuevo, se agoto el tiempo de espera'

            raise AppException(AppException.ErrorType.DATABASE_ERROR,
                               error_message) from e