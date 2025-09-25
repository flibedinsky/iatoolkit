## Copyright (c) 2024 Fernando Libedinsky

from dotenv import load_dotenv
from iatoolkit import IAToolkit, register_company
from companies.sample_fintech.sample_fintech import SampleFintech
from urllib.parse import urlparse
import os
import logging

# load environment variables
load_dotenv()

# companies must be registered before creating the IAToolkit
register_company('sample_fintech', SampleFintech)

if __name__ == "__main__":
    # create the IAToolkit and Flask instance
    toolkit = IAToolkit()
    app = toolkit.create_iatoolkit()
    if app:
        # get the port from the environment variable
        base_url = os.getenv('IATOOLKIT_BASE_URL')
        run_port = 5001  # default port

        if base_url:
            try:
                # Extraer el puerto de la URL
                parsed_url = urlparse(base_url)
                if parsed_url.port:
                    run_port = parsed_url.port
                else:
                    logging.warning(
                        f"La variable IATOOLKIT_BASE_URL ('{base_url}') no contiene un puerto. Usando el puerto por defecto {run_port}.")
            except Exception as e:
                logging.error(
                    f"No se pudo parsear la IATOOLKIT_BASE_URL: '{base_url}'. Error: {e}. Usando el puerto por defecto {run_port}.")
        else:
            logging.info(f"Variable IATOOLKIT_BASE_URL no definida. Usando el puerto por defecto {run_port}.")

        app.run(port=run_port)