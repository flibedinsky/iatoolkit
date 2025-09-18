# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

from flask import session


class SessionManager:
    @staticmethod
    def set(key, value):
        session[key] = value

    @staticmethod
    def get(key, default=None):
        return session.get(key, default)

    @staticmethod
    def remove(key):
        if key in session:
            session.pop(key)

    @staticmethod
    def clear():
        session.clear()
