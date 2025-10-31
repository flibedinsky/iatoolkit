# iatoolkit/views/index_view.py

from flask import render_template, session
from flask.views import MethodView


class IndexView(MethodView):
    """
    Handles the rendering of the generic landing page, which no longer depends
    on a specific company.
    """

    def get(self):
        return render_template('index.html')
