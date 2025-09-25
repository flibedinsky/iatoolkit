## Copyright (c) 2024 Fernando Libedinsky

from dotenv import load_dotenv
from injector import Binder
from iatoolkit import IAToolkit, register_company
from companies.sample_fintech.sample_fintech import SampleFintech

VERSION = "2.0.0"


load_dotenv()

def configure(binder: Binder) -> None:
    binder.bind(SampleFintech, to=SampleFintech())


# Registra las compañías antes de crear la app
register_company('sample_fintech', SampleFintech)

# Crea el toolkit y la instancia de la app Flask
toolkit = IAToolkit()
app = toolkit.create_iatoolkit()

# Inicializa las compañías
dispatcher = toolkit.get_dispatcher()
dispatcher.start_execution()


if __name__ == "__main__":
    app.run()