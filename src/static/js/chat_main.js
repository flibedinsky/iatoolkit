
// variables for controlling the cancellation of the request
let currentAbortController = null;
let isRequestInProgress = false;

let specificDataConfig;


$(document).ready(function () {

    // get the company specific configuration
    specificDataConfig = window.company_ui_config;

    // this is the Send/stop message on the chat window
    $('#send-button').on('click', handleChatMessage);
    $('#stop-button').on('click', abortCurrentRequest);

    $('#question').on('keypress', function (event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            handleChatMessage();
        }
    });

    // Evento para el selector de prompts
    $('.input-container').on('click', '.dropdown-menu .dropdown-item', function(event) {
        // Prevenir la acción por defecto del enlace (que es navegar a '#')
        event.preventDefault();

        // get the  text and y description, save in hidden field
        const selectedPrompt = $(this).data('value');
        const selectedDescription = $(this).text().trim();

        // display the selected option
        $('#agent-select-button').text(selectedDescription);

        // save values for handling in the call
        $('#agent-select-value').val(selectedPrompt);
        $('#agent-select-description').val(selectedDescription);

        // Aplica el estilo de "seleccionado" al botón.
        $('#agent-select-button').addClass('item-selected');

        // muestra el boton para limpiar la selección
        $('#clear-selection-button').show();
    });


    // Solo se activa si el componente está configurado y habilitado
    if (specificDataConfig && specificDataConfig.enabled) {
        // Usa el ID dinámico de la configuración
        $('#' + specificDataConfig.id).on('input', function () {
            if ($(this).val().trim() !== '') {
                $(this).addClass('has-content');
                // Usa el ID dinámico para el botón de limpiar
                $('#clear-' + specificDataConfig.id + '-button').show();
            } else {
                $(this).removeClass('has-content');
                $('#clear-' + specificDataConfig.id + '-button').hide();
            }
        });

        // Evento para el botón de limpiar dinámico
        $('#clear-' + specificDataConfig.id + '-button').on('click', function () {
            resetSpecificDataInput();
        });
    }


});  // fin del document.ready

const handleChatMessage = async function () {
    // Si hay una solicitud en progreso, abortar
    if (isRequestInProgress) {
        abortCurrentRequest();
        return;
    }

    const question = $('#question').val().trim();
    const selectedPrompt = $('#agent-select-value').val()
    const selectedDescription = $('#agent-select-description').val();

    // dynamic lecture of the value of the specific data input
    let specificDataValue = '';
    if (specificDataConfig && specificDataConfig.enabled) {
        specificDataValue = $('#' + specificDataConfig.id).val().trim();
    }

    if (!question && !selectedPrompt) {
        Swal.fire({
            icon: 'warning',
            title: 'Ingresa una pregunta o selecciona un prompt',
            text: 'Por favor, escribe una pregunta o selecciona una predefinida'
        });
        return;
    }

    // Mostrar el prompt al usuario en el chat
    displayUserMessage(question, selectedDescription, specificDataValue, selectedPrompt);
    showSpinner();

    // Cambiar botón a modo "Detener"
    setButtonToStop();

    // limpiar widgets
    $('#question').val('');
    resetAgentSelect();

    if (specificDataConfig && specificDataConfig.enabled) {
        resetSpecificDataInput();
    }

    const files = window.filePond.getFiles();
    const filesBase64 = await Promise.all(files.map(fileItem => toBase64(fileItem.file))); // fileItem.file es el objeto File nativo

    const client_data = {
        prompt_name: selectedPrompt,
        question: question,
    };

    // add the data only if the specific data input is enabled and has a value
    if (specificDataConfig && specificDataConfig.enabled && specificDataValue) {
        // use the `data_key` dynamic from the config
        client_data[specificDataConfig.data_key] = specificDataValue;
    }

    const data = {
        question: question,
        prompt_name: selectedPrompt,
        client_data: client_data,
        files: filesBase64.map(fileData => ({
            filename: fileData.name,
            content: fileData.base64
        })),
        external_user_id: window.externalUserId
    };

    try {
        const responseData = await callLLMAPI("/llm_query", data, "POST");
        if (responseData) {
            const {answer, aditional_data} = responseData;
            if (answer) {
                const answerSection = $('<div>').addClass('answer-section llm-output');
                answerSection.append(answer);
                displayBotMessage(answerSection);
            }

            /* this code is for the document classification use case
            if (aditional_data && 'classify_documents' in aditional_data && aditional_data.classify_documents.length > 0) {
                display_document_validation(aditional_data.classify_documents);
            }
            */
        }
    } catch (error) {
        console.error("Error en handleFormSubmission:", error);

        if (error.name === 'AbortError') {
            // Verificar si fue aborto manual o timeout automático
            if (window.isManualAbort) {
                const abortMessage = $('<div>')
                    .addClass('error-section alert alert-warning')
                    .append('Solicitud cancelada por el usuario');
                displayBotMessage(abortMessage);
                window.isManualAbort = false; // Resetear la bandera
            } else {
                const timeoutError = $('<div>')
                    .addClass('error-section alert alert-danger')
                    .append('La solicitud ha excedido el tiempo límite de respuesta, intente nuevamente');
                displayBotMessage(timeoutError);
            }
        } else {
            const commError = $('<div>')
                .addClass('error-section alert alert-danger')
                .append(`Error de conexión: ${error.message}`);
            displayBotMessage(commError);
        }
        hideSpinner();
        setButtonToSend();
    } finally {
        hideSpinner();
        setButtonToSend();
        window.filePond.removeFiles(); // Esto disparará 'removefile' y actualizará los iconos
    }
};


// Función genérica para llamadas al API
const callLLMAPI = async function(apiPath, data, method, timeoutMs = 500000) {
    const companyShortName = window.companyShortName;
    const serverBaseUrl = window.iatoolkit_base_url;

    // destination url
    const url = `${serverBaseUrl}/${companyShortName}${apiPath}`;

    // add the session JWT if it exists
    const headers = {"Content-Type": "application/json"};
    if (typeof sessionJWT !== 'undefined' && sessionJWT) {
        headers['X-Chat-Token'] = sessionJWT;
    }

    // Crear AbortController para manejar el timeout
        const controller = new AbortController();
        currentAbortController = controller; // Asignar al controlador global
        const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

        try {
            const response = await fetch(url, {
                method: method,
                headers: headers,
                body: JSON.stringify(data),
                signal: controller.signal,
                credentials: 'include'
            });

            clearTimeout(timeoutId); // Limpiar el timeout si la respuesta llega a tiempo

            if (!response.ok) {
                const errorData = await response.json();
                const endpointError = $('<div>').addClass('error-section');
                endpointError.append(`<p>${errorData.error_message || 'Error desconocido del servidor'}</p>`);
                displayBotMessage(endpointError);
                return null;
            }

            const responseData = await response.json();
            return responseData;
        } catch (error) {
            clearTimeout(timeoutId); // Limpiar el timeout en caso de error

            if (error.name === 'AbortError') {
                // Re-lanzar el error para que se maneje en handleChatMessage
                throw error;
            } else {
                const commError = $('<div>').addClass('error-section');
                commError.append(`<p>Error de conexión: ${error.message}</p>`);
                displayBotMessage(commError);
            }
            return null;
        }
    };

    // Función para mostrar mensaje del usuario
    const displayUserMessage = function(question, selectedDescription, specificDataValue, selectedPrompt) {
        const chatContainer = $('#chat-container');
        const userMessage = $('<div>').addClass('message shadow-sm');

        let pencil = true;
        let messageText;
        if (specificDataValue && question && !selectedPrompt) {
            messageText = $('<span>').text(`${specificDataValue}: ${question}`);
            }
        else if (specificDataValue && !question && selectedPrompt) {
            messageText = $('<span>').text(`${specificDataValue}: ${selectedDescription}`);
            }
        else if ( ! specificDataValue && selectedPrompt) {
            messageText = $('<span>').text(`${selectedDescription}`);
            pencil = false;
            }
        else {
            messageText = $('<span>').text(question);
            pencil = true;
        }

        userMessage.append(messageText);

        if ( pencil ){
            const editIcon = $('<i>')
            .addClass('bi bi-pencil-fill edit-icon')
            .attr('title', 'Editar consulta')
            .on('click', function () {
                $('#question').val(question);
            });
        userMessage.append(editIcon);
        }

        chatContainer.append(userMessage);
    };

// display the aswer from the LLM
function displayBotMessage(section) {
    const chatContainer = $('#chat-container');
    chatContainer.append(section);
    chatContainer.scrollTop(chatContainer[0].scrollHeight);
}

    // Función para cambiar el botón a modo "Detener"
    function setButtonToStop() {
        const sendButton = $('#send-button');
        sendButton
            .removeClass('btn-primary')
            .addClass('btn-danger stop-mode')
            .html('<div class="spinner" style="width: 1rem; height: 1rem; margin-right: 4px; border: 2px solid #f3f3f3; border-top: 2px solid #fff; border-radius: 50%; animation: spin 1s linear infinite; display: inline-block;"></div>Detener')
            .prop('disabled', false);
        isRequestInProgress = true;
    }

    // Función para cambiar el botón de vuelta a modo "Enviar"
    function setButtonToSend() {
        const sendButton = $('#send-button');
        sendButton
            .removeClass('btn-danger stop-mode')
            .addClass('btn-primary')
            .text('Enviar')
            .prop('disabled', false);
        isRequestInProgress = false;
        currentAbortController = null;
    }


/**
 * Función para abortar la solicitud en curso.
 */
const abortCurrentRequest = function () {
    if (currentAbortController && isRequestInProgress) {
        window.isManualAbort = true;            // Flag para saber que fue el usuario quien canceló
        currentAbortController.abort();
        toggleSendStopButtons(false);   // Volver a mostrar 'Enviar'
        hideSpinner();
    }
};


// Función para mostrar spinner
const showSpinner = function () {
    // Primero, nos aseguramos de que no haya otros spinners
    if ($('#spinner').length) $('#spinner').remove();

    // Determinar la clase de accesibilidad correcta según la versión de Bootstrap.
    // Bootstrap 5 introduce el objeto global 'bootstrap', que no existe en la v4.
    const accessibilityClass = (typeof bootstrap !== 'undefined') ? 'visually-hidden' : 'sr-only';

    const chatContainer = $('#chat-container');
    const spinner = $(`
            <div id="spinner" style="display: flex; align-items: center; justify-content: start; margin: 10px 0; padding: 10px;">
                <div class="spinner-border text-primary" role="status" style="width: 1.5rem; height: 1.5rem; margin-right: 15px;">
                    <span class="${accessibilityClass}">Cargando...</span>
                </div>
                <span style="font-weight: bold; font-size: 15px;">Cargando...</span>
            </div>
        `);

    chatContainer.append(spinner);
    chatContainer.scrollTop(chatContainer[0].scrollHeight);
};

function hideSpinner() {
    $('#spinner').fadeOut(function () {
        $(this).remove();
    });
}


/**
 * Cambia la visibilidad entre el botón de Enviar y el de Detener.
 * @param {boolean} showStop - Si es true, muestra Detener y oculta Enviar. Si es false, hace lo contrario.
 */
const toggleSendStopButtons = function (showStop) {
    $('#send-button-container').toggle(!showStop);
    $('#stop-button-container').toggle(showStop);
};


function resetAgentSelect() {
    // 1. Restaura el texto original del botón visible
    $('#agent-select-button').text('Available prompts  ....');

    // 2. Limpia los valores de los inputs ocultos
    $('#agent-select-value').val('');
    $('#agent-select-description').val('');

    // oculta el boton de limpiar
    $('#agent-select-button').removeClass('item-selected');
    $('#clear-selection-button').hide();
}

function resetSpecificDataInput() {
    if (specificDataConfig && specificDataConfig.enabled) {
        const input = $('#' + specificDataConfig.id);
        input.val(''); // Limpia el texto
        input.removeClass('has-content'); // Quita el estilo
        $('#clear-' + specificDataConfig.id + '-button').hide(); // Oculta el botón 'X'
    }
}

function toBase64(file) { // file aquí es el objeto File nativo
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve({name: file.name, base64: reader.result.split(",")[1]});
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}


function display_document_validation(document_list) {
    const requiredFields = ['document_name', 'document_type', 'causes', 'is_valid'];
    for (const doc of document_list) {
        if (!requiredFields.every(field => field in doc)) {
            console.warn("Documento con estructura incorrecta:", doc);
            continue;
        }
        const docValidationSection = $('<div>').addClass('document-section card mt-2 mb-2');
        const cardBody = $('<div>').addClass('card-body');
        const headerDiv = $('<div>').addClass('d-flex justify-content-between align-items-center mb-2');
        const filenameSpan = $(`
                <div>
                    <span class="text-primary fw-bold">Archivo: </span>
                    <span class="text-secondary">${doc.document_name}</span>
                </div>`);
        const badge_style = doc.is_valid ? 'bg-success' : 'bg-danger';
        const documentBadge = $('<span>')
            .addClass(`badge ${badge_style} p-2`)
            .text(doc.document_type);
        headerDiv.append(filenameSpan).append(documentBadge);
        cardBody.append(headerDiv);

        if (!doc.is_valid && doc.causes && doc.causes.length > 0) {
            const rejectionSection = $('<div>').addClass('rejection-reasons mt-2');
            rejectionSection.append('<h6 class="text-danger">Causales de Rechazo:</h6>');
            const causesList = doc.causes.map(cause => `<li class="text-secondary">${cause}</li>`).join('');
            rejectionSection.append(`<ul class="list-unstyled">${causesList}</ul>`);
            cardBody.append(rejectionSection);
        } else if (doc.is_valid) {
            const validSection = $('<div>').addClass('mt-2');
            validSection.append('<p class="text-success fw-bold">Documento válido.</p>');
            cardBody.append(validSection);
        }
        docValidationSection.append(cardBody);
        displayBotMessage(docValidationSection);
    }
}


