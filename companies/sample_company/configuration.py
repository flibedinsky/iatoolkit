# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

FUNCTION_LIST = [
        {'name': 'Acceso via SQL a la base de datos.',
         'description': "Debes usar este servicio para consulta sobre Sample Company y sus "
                        "clientes, productos, ordenes , regiones, empleados.",
         'function_name': "sql_query",
         'params': {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string",
                                  "description": "string con la consulta en sql"}
                    },
                    "required": ["query"]
                }
         },
        {'name': 'busquedas en documentos: manuales internos, contratos de trabajo, procedimientos, legales',
         'description': "busquedas sobre documentos: manuales, contratos de trabajo de empleados,"
            'manuales de procedimientos, documentos legales, manuales de proveedores (supply-chain)',
         'function_name': "document_search",
         'params': {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string",
                                  "description": "Texto o pregunta a buscar en los documentos."}
                    },
                    "required": ["query"]
                }
         }
    ]


PROMPT_LIST = [
            {
                'name': 'analisis_ventas',
                'description': 'Analisis de ventas',
                'order': 1,
                'custom_fields': [
                    {
                        "data_key": "init_date",
                        "label": "Fecha desde",
                        "type": "date",
                    },
                    {
                        "data_key": "end_date",
                        "label": "Fecha hasta",
                        "type": "date",
                    }
                ]
            },
            {
                'name': 'supplier_report',
                'description': 'Análisis de proveedores',
                'order': 2,
                'custom_fields': [
                    {
                        "data_key": "supplier_id",
                        "label": "Identificador del Proveedor",
                    }
                ]
            }
        ]

BRANDING = {
    "header_background_color": "#EFF6FF",  # Un azul pastel muy claro
    "header_text_color": "#1E3A8A",  # Un azul oscuro y profesional
    "primary_font_weight": "600",  # Semibold, para un look refinado
    "primary_font_size": "1.1rem",  # Ligeramente más grande para jerarquía

    # for modals and buttons
    "brand_primary_color": "#1E3A8A",  # Mismo azul oscuro del texto para consistencia
    "brand_text_on_primary": "#FFFFFF",  # Texto blanco para el botón primario
    "brand_secondary_color": "#6c757d",  # Un gris neutro y profesional para acciones secundarias
    "brand_text_on_secondary": "#FFFFFF",  # Texto blanco para el botón secundario
}

ONBOARDING_CARDS = [
    {
        'icon': 'fas fa-database',
        'title': 'Base de Datos Northwind',
        'text': 'Tengo acceso completo a la base de datos de Northwind. Puedo consultar información sobre clientes, órdenes, productos y empleados.<br><br><strong>Ejemplo:</strong> ¿Cuál es el producto más vendido en Brasil?'
    },
    {
        'icon': 'fas fa-file-alt',
        'title': 'Documentos Internos',
        'text': 'Puedo buscar en manuales internos, contratos de trabajo y documentos legales para encontrar la información que necesitas.<br><br><strong>Ejemplo:</strong> ¿Cuál es el procedimiento para solicitar vacaciones?'
    },
    {
        'icon': 'fas fa-cogs',
        'title': 'Análisis SQL',
        'text': 'Puedes pedirme que ejecute consultas SQL directamente sobre la base de datos y te entregaré los resultados.<br><br><strong>Ejemplo:</strong> "SQL: SELECT * FROM Orders WHERE ShipCountry = \'France\' LIMIT 5"'
    }
]
