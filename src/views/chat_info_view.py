# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

from flask import render_template
from flask.views import MethodView
from injector import inject


class ChatInfoView(MethodView):
    @inject
    def __init__(self):
        pass

    def get(self):
            return render_template("chat-info.html",
                                   auth_method='jwt')
