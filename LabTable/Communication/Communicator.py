import logging
import threading
import uuid
from typing import Callable

import websocket
import ssl
import json

from LabTable.Configurator import ConfigError
from LabTable.ExtentTracker import ExtentTracker


# Configure logging
logger = logging.getLogger(__name__)

# remote communication protocol
URL = "ws{s}://{host}:{port}"  # this is a websocket (ssl) connection

ANSWER_STRING = "success"


# the base class for websocket communication
class Communicator(threading.Thread):

    _uri = None
    _ssl_context = None
    _connection_instance = None
    _connection_open = False
    _message_stack = {}
    ssl_pem_file = None
    ip = None
    port = None

    def __init__(self, config):

        # call super()
        threading.Thread.__init__(self)
        self.name = "[LabTable] {}".format(__name__)

        self.config = config
        self.extent_tracker = ExtentTracker.get_instance()
        self.brick_update_callback = lambda: None
        self._ssl_context = None

        # if ssl is configured load the pem file
        s = ""
        if self.ssl_pem_file:
            self._ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            try:
                self._ssl_context.load_verify_locations(self.ssl_pem_file)
                s = "s"
            except FileNotFoundError:
                logger.fatal("SSL file configured but not found: {}".format(self.ssl_pem_file))
                raise ConfigError("SSL file configured but not found: {}".format(self.ssl_pem_file))

        self._uri = URL.format(s=s, host=self.ip, port=self.port)
        logger.info("configured remote URL to {}".format(self._uri))

        # start the listener thread
        self.start()

    def on_message(self, ws, message):
        json_message = json.loads(message)
        logger.debug("received message: {:.250}".format(message))
        message_id = int(json_message["message_id"])
        if json_message[ANSWER_STRING]:
            if message_id in self._message_stack:
                callback = self._message_stack[message_id]
                del json_message["message_id"]
                del json_message[ANSWER_STRING]
                if callback:
                    del self._message_stack[message_id]
                    callback(json_message)
                else:
                    logger.warning("could not find associated callback to message: {}".format(message_id))
            else:
                logger.warning("received unknown answer in message: {}".format(message))
                logger.debug(self._message_stack)
        else:
            logger.warning("request {} was unsuccessful.".format(message_id))

    def on_error(self, ws, error):
        logger.exception(error)
        self._connection_open = False

    def on_close(self, ws):
        self._connection_open = False
        logger.debug("Connection to {} closed.".format(self._uri))

    def on_open(self, ws):
        self._connection_open = True
        logger.debug("Connection to {} established".format(self._uri))

    def close(self):
        self._connection_instance.close()
        logger.info("closing websocket connection")

    # starting the listener thread and perform the connection to the LandscapeLab!
    def run(self):

        # try to connect to server
        self._connection_instance = websocket.WebSocketApp(self._uri, on_close=self.on_close,
                                                           on_message=self.on_message, on_open=self.on_open,
                                                           on_error=self.on_error)
        self._connection_instance.run_forever()

    # this sends an message to the server and returns the json answer
    def send_message(self, message: dict, callback: Callable):

        if self._connection_open:
            # add a message_id and register the answer callback to it
            message_id = uuid.uuid4().int
            message["message_id"] = str(message_id)
            self._message_stack[message_id] = callback

            # send the actual message and return
            self._connection_instance.send(json.dumps(message))
            logger.debug("sent message: {}".format(message))

        else:
            logger.error("Could not send message {} to {} as the connection is closed!".format(message, self._uri))
