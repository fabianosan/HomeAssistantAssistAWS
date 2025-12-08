# -*- coding: utf-8 -*-
import warnings
import sys

if not sys.warnoptions:
    warnings.filterwarnings("ignore", category=SyntaxWarning)

import os
import re
import logging
import json
import random
import asyncio
import uuid
import requests
import requests.exceptions
import ask_sdk_core.utils as ask_utils

from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler, AbstractExceptionHandler
from ask_sdk_model.interfaces.alexa.presentation.apl import RenderDocumentDirective, ExecuteCommandsDirective, OpenUrlCommand
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

# Load configurations and localization
def load_config(file_name):
    if str(file_name).endswith(".lang") and not os.path.exists(file_name):
        file_name = "locale/en-US.lang"
    try:
        with open(file_name, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or '=' not in line:
                    continue
                name, value = line.split('=', 1)
                # Store in global vars
                globals()[name] = value
    except Exception as e:
        logger.error(f"Error loading file: {str(e)}")

# Initial config load
load_config("locale/en-US.lang")

# Log configuration
debug = bool(os.environ.get('debug', False))
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG if debug else logging.INFO)

# Thread pool max workers
executor = ThreadPoolExecutor(max_workers=5)
# Note: config.cfg stores values as strings; we'll normalize expected boolean
# flags to lowercase strings ("true"/"false") and compare explicitly.
# Globals for conversation
conversation_id = None
last_interaction_date = None
is_apl_supported = False
account_linking_token = None
user_locale = "US"  # Default locale
home_assistant_url = os.environ.get('home_assistant_url', "").strip("/")
apl_document_token = str(uuid.uuid4())
assist_input_entity = os.environ.get('assist_input_entity', "input_text.assistant_input")
home_assistant_room_recognition = str(os.environ.get('home_assistant_room_recognition', 'False')).lower()
home_assistant_kioskmode = str(os.environ.get('home_assistant_kioskmode', 'False')).lower()
ask_for_further_commands = str(os.environ.get('ask_for_further_commands', 'False')).lower()
suppress_greeting = str(os.environ.get('suppress_greeting', 'False')).lower()

# Helper: fetch text input via webhook
def fetch_prompt_from_ha():
    """
    Reads the state of your input_text helper directly via REST API.
    """
    try:
        url = f"{home_assistant_url}/api/states/{assist_input_entity}"
        headers = {
            "Authorization": "Bearer {}".format(account_linking_token),
            "Content-Type": "application/json",
        }
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            return resp.json().get("state", "").strip()
        else:
            logger.error(f"HA state fetch failed: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"Error fetching prompt from HA state: {e}")
    return ""

def localize(handler_input):
    # Load locale per user
    locale = handler_input.request_envelope.request.locale
    load_config(f"locale/{locale}.lang")

    # save user_locale var for regional differences in number handling like 2.4°C / 2,4°C
    global user_locale
    user_locale = locale.split("-")[1]  # "de-DE" -> "DE" split to respect lang differencies (not country specific)

class LaunchRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        global conversation_id, last_interaction_date, is_apl_supported, account_linking_token, suppress_greeting
        
        localize(handler_input)

        # Obtaining Account Linking token
        account_linking_token = handler_input.request_envelope.context.system.user.access_token
        if account_linking_token is None and debug:
            account_linking_token = os.environ.get('home_assistant_token') # DEBUG Purpose

        # Verifying if token was successfully obtained
        if not account_linking_token:
            logger.error("Unable to get token from Alexa Account Linking or AWS Functions environment variable.")
            speak_output = globals().get("alexa_speak_error")
            return handler_input.response_builder.speak(speak_output).response

        # Check for a pre-set prompt from HA
        prompt = fetch_prompt_from_ha()
        # Only treat valid prompts that are not the literal "none"
        if prompt and prompt.lower() != "none":
            # Process this prompt as user input and keep session open for follow-up
            response = process_conversation(prompt)
            return handler_input.response_builder.speak(response).ask(globals().get("alexa_speak_question")).response

        # No prompt and Checks if the device has a screen (APL support), if so, loads the interface
        device = handler_input.request_envelope.context.system.device
        is_apl_supported = device.supported_interfaces.alexa_presentation_apl is not None
        logger.debug("Device: " + repr(device))
        
        # Renders the APL document with the button to open HA (if the device has a screen)
        if is_apl_supported:
            handler_input.response_builder.add_directive(
                RenderDocumentDirective(token=apl_document_token, document=load_template("apl_openha.json"))
            )
            
        # Sets the last access and defines which welcome phrase to respond to
        now = datetime.now(timezone(timedelta(hours=-3)))
        current_date = now.strftime('%Y-%m-%d')
        speak_output = globals().get("alexa_speak_next_message")
        if last_interaction_date != current_date:
            # First run of the day
            speak_output = globals().get("alexa_speak_welcome_message")
            last_interaction_date = current_date

        if suppress_greeting == "true":
            return handler_input.response_builder.ask("").response
        else:
            return handler_input.response_builder.speak(speak_output).ask(speak_output).response

# Execute the asynchronous part with asyncio
def run_async_in_executor(func, *args):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(loop.run_in_executor(executor, func, *args))
    finally:
        loop.close()

class GptQueryIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("GptQueryIntent")(handler_input)

    def handle(self, handler_input):
        global account_linking_token

        # Ensure locale is set correctly
        localize(handler_input)

        request = handler_input.request_envelope.request
        context = handler_input.request_envelope.context
        response_builder = handler_input.response_builder

        # Get the account linking token
        account_linking_token = context.system.user.access_token

        # Extract user query
        query = request.intent.slots["query"].value
        logger.info(f"Query received from Alexa: {query}")

        # Handle keyword-based logic
        keyword_response = keywords_exec(query, handler_input)
        if keyword_response:
            return keyword_response

        # Include device ID if needed
        device_id = ""
        if home_assistant_room_recognition == "true":
            device_id = f". device_id: {context.system.device.device_id}"

        # Say processing message while async task runs
        processing_msg = globals().get("alexa_speak_processing")
        response_builder.speak(processing_msg).set_should_end_session(False)

        # Run async call
        full_query = query + device_id
        response = run_async_in_executor(process_conversation, full_query)

        logger.debug(f"Ask for further commands enabled: {ask_for_further_commands}")
        if ask_for_further_commands == "true":
            return response_builder.speak(response).ask(globals().get("alexa_speak_question")).response
        else:
            return response_builder.speak(response).set_should_end_session(True).response

# Handles keywords to execute specific commands
def keywords_exec(query, handler_input):
    # Commands to open the dashboard
    keywords_top_open_dash = globals().get("keywords_to_open_dashboard").split(";")
    if any(ko.strip().lower() in query.lower() for ko in keywords_top_open_dash):
        logger.info("Opening Home Assistant dashboard")
        open_page(handler_input)
        return handler_input.response_builder.speak(globals().get("alexa_speak_open_dashboard")).response

    # Commands to close the skill — only if query has 3 or fewer words and matches closing keywords exactly
    keywords_close_skill = [k.strip().lower() for k in globals().get("keywords_to_close_skill").split(";")]
    query_words = query.lower().split()
    if len(query_words) <= 3:
        for kc in keywords_close_skill:
            # Match whole word or phrase using word boundaries to avoid substrings
            if re.search(r'\b' + re.escape(kc) + r'\b', query.lower()):
                logger.info("Closing skill from keyword command")
                return CancelOrStopIntentHandler().handle(handler_input)

    # If it is not a keyword or the context does not allow closing
    return None


# Calls the Home Assistant API and handles the response
def process_conversation(query):
    global conversation_id
    
    # Gets user-configured environment variables
    if not home_assistant_url:
        logger.error("Please set 'home_assistant_url' AWS Lambda Functions environment variable.")
        return globals().get("alexa_speak_error")
    
    home_assistant_agent_id = os.environ.get("home_assistant_agent_id", None)
    home_assistant_language = os.environ.get("home_assistant_language", None)
        
    try:
        headers = {
            "Authorization": "Bearer {}".format(account_linking_token),
            "Content-Type": "application/json",
        }
        data = {
            "text": replace_words(query)
        }
        # Adding optional parameters to request
        if home_assistant_language:
            data["language"] = home_assistant_language
        if home_assistant_agent_id:
            data["agent_id"] = home_assistant_agent_id
        if conversation_id:
            data["conversation_id"] = conversation_id

        ha_api_url = "{}/api/conversation/process".format(home_assistant_url)
        logger.debug(f"HA request url: {ha_api_url}")        
        logger.debug(f"HA request data: {data}")
        
        response = requests.post(ha_api_url, headers=headers, json=data)
        
        logger.debug(f"HA response status: {response.status_code}")
        logger.debug(f"HA response data: {response.text}")
        
        contenttype = response.headers.get('Content-Type', '')
        logger.debug(f"Content-Type: {contenttype}")
        
        if (contenttype == "application/json"):
            response_data = response.json()
            speech = None

            if response.status_code == 200 and "response" in response_data:
                conversation_id = response_data.get("conversation_id", conversation_id)
                response_type = response_data["response"]["response_type"]
                
                if response_type == "action_done" or response_type == "query_answer":
                    # Extract speech, preferring SSML over plain text
                    speech, is_ssml = extract_speech(response_data["response"]["speech"])
                    
                    if speech and "device_id:" in speech:
                        speech = speech.split("device_id:")[0].strip()
                elif response_type == "error":
                    # Extract speech, preferring SSML over plain text
                    speech, is_ssml = extract_speech(response_data["response"]["speech"])
                    logger.error(f"Error code: {response_data['response']['data']['code']}")
                else:
                    speech = globals().get("alexa_speak_error")
                    is_ssml = False

            if not speech:
                if "message" in response_data:
                    message = response_data["message"]
                    logger.error(f"Empty speech: {message}")
                    return improve_response(f"{globals().get('alexa_speak_error')} {message}")
                else:
                    logger.error(f"Empty speech: {response_data}")
                    return globals().get("alexa_speak_error")

            # If speech is SSML, return as-is; otherwise apply text improvements
            if is_ssml:
                logger.debug("Returning SSML response")
                return speech
            else:
                logger.debug("Returning plain text response with improvements")
                return improve_response(speech)
        elif (contenttype == "text/html") and int(response.status_code, 0) >= 400:
            errorMatch = re.search(r'<title>(.*?)</title>', response.text, re.IGNORECASE)
            
            if errorMatch:
                title = errorMatch.group(1)
                logger.error(f"HTTP error {response.status_code} ({title}): Unable to connect to your Home Assistant server")
            else:
                logger.error(f"HTTP error {response.status_code}: Unable to connect to your Home Assistant server. \n {response.text}")
                
            return globals().get("alexa_speak_error")
        elif  (contenttype == "text/plain") and int(response.status_code, 0) >= 400:
            logger.error(f"Error processing request: {response.text}")
            return globals().get("alexa_speak_error")
        else:
            logger.error(f"Error processing request: {response.text}")
            return globals().get("alexa_speak_error")
            
    except requests.exceptions.Timeout as te:
        logger.error(f"Timeout when communicating with Home Assistant: {str(te)}", exc_info=True)
        return globals().get("alexa_speak_timeout")

    except Exception as e:
        logger.error(f"Error processing response: {str(e)}", exc_info=True)
        return globals().get("alexa_speak_error")

# Extract speech from Home Assistant response, preferring SSML over plain text
def extract_speech(speech_data):
    """
    Extract speech from HA response data, preferring SSML when available.
    
    Args:
        speech_data: Dictionary containing speech data from HA response
        
    Returns:
        Tuple of (speech_text, is_ssml)
    """
    # Check for SSML first
    if "ssml" in speech_data and speech_data["ssml"].get("speech"):
        speech = speech_data["ssml"]["speech"]
        logger.debug(f"Using SSML response: {speech}")
        return speech, True
    
    # Fall back to plain text
    if "plain" in speech_data and speech_data["plain"].get("speech"):
        speech = speech_data["plain"]["speech"]
        logger.debug(f"Using plain text response: {speech}")
        return speech, False
    
    # No speech found
    return None, False

# Replaces incorrectly generated words by Alexa interpreter in the query
def replace_words(query):
    query = query.replace('4.º','quarto')
    return query

# Replaces words and special characters to improve API response speech
def improve_response(speech):
    global user_locale
    speech = speech.replace(':\n\n', '').replace('\n\n', '. ').replace('\n', ',').replace('-', '').replace('_', ' ')

    # Change decimal separator if user_locale = "de-DE"
    if user_locale == "DE":
        # Only replace decimal separators and not 1.000 separators
        speech = re.sub(r'(\d+)\.(\d{1,3})(?!\d)', r'\1,\2', speech)  # Decimal point (e.g. 2.4 -> 2,4)
    
    speech = re.sub(r'[^A-Za-z0-9çÇáàâãäéèêíïóôõöúüñÁÀÂÃÄÉÈÊÍÏÓÔÕÖÚÜÑ\sß.,!?°]', '', speech)
    return speech

# Loads the initial APL screen template
def load_template(filepath):
    with open(filepath, encoding='utf-8') as f:
        template = json.load(f)

    if filepath == 'apl_openha.json':
        # Locate dynamic texts in the APL
        template['mainTemplate']['items'][0]['items'][2]['text'] = globals().get("echo_screen_welcome_text")
        template['mainTemplate']['items'][0]['items'][3]['text'] = globals().get("echo_screen_click_text")
        template['mainTemplate']['items'][0]['items'][4]['onPress']['source'] = get_hadash_url()
        template['mainTemplate']['items'][0]['items'][4]['item']['text'] = globals().get("echo_screen_button_text")

    return template

# Opens Home Assistant dashboard in Silk browser
def open_page(handler_input):
    if is_apl_supported:
        # Renders an empty template, required for the OpenURL command
        # https://amazon.developer.forums.answerhub.com/questions/220506/alexa-open-a-browser.html
        
        handler_input.response_builder.add_directive(
            RenderDocumentDirective(
                token=apl_document_token,
                document=load_template("apl_empty.json")
            )
        )
        
        # Open default page of dashboard
        handler_input.response_builder.add_directive(
            ExecuteCommandsDirective(
                token=apl_document_token,
                commands=[OpenUrlCommand(source=get_hadash_url())]
            )
        )

# Builds the Home Assistant dashboard URL
def get_hadash_url():
    ha_dashboard_url = home_assistant_url
    ha_dashboard_url += "/{}".format(os.environ.get("home_assistant_dashboard", "lovelace"))
    
    
    if home_assistant_kioskmode == "true":
        ha_dashboard_url += '?kiosk'
    
    logger.debug(f"ha_dashboard_url: {ha_dashboard_url}")
    return ha_dashboard_url

class HelpIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        speak_output = globals().get("alexa_speak_help")
        return handler_input.response_builder.speak(speak_output).ask(speak_output).response

class CancelOrStopIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input)

    def handle(self, handler_input):
        speak_output = random.choice(globals().get("alexa_speak_exit").split(";"))
        return handler_input.response_builder.speak(speak_output).set_should_end_session(True).response

class SessionEndedRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        return handler_input.response_builder.response

class CanFulfillIntentRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_request_type("CanFulfillIntentRequest")(handler_input)

    def handle(self, handler_input):
        localize(handler_input)
        
        intent_name = handler_input.request_envelope.request.intent.name if handler_input.request_envelope.request.intent else None
        if intent_name == "GptQueryIntent":
            return handler_input.response_builder.can_fulfill("YES").add_can_fulfill_intent("YES").response
        else:
            return handler_input.response_builder.can_fulfill("NO").add_can_fulfill_intent("NO").response

class CatchAllExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input, exception):
        return True

    def handle(self, handler_input, exception):
        logger.error(exception, exc_info=True)
        speak_output = globals().get("alexa_speak_error")
        return handler_input.response_builder.speak(speak_output).ask(speak_output).response

sb = SkillBuilder()
sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(GptQueryIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_request_handler(CanFulfillIntentRequestHandler())
sb.add_exception_handler(CatchAllExceptionHandler())
lambda_handler = sb.lambda_handler()
