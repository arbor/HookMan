#!/usr/bin/python3

import signal
import asyncio
import argparse
import json
import sys
import logging
from logging.handlers import RotatingFileHandler

import hookman.http as http

"""
HookMan main() module.

HookMan module that contains main() along with argument parsing, instantiation of the HTTP Objects,
also creates the loop and kicks everything off
"""

__version__ = "0.1.0"

class HMMain():

    """
    Class to encapsulate all main() functionality.
    """

    def __init__(self):

        """
        Constructor.
        """

        self.logger = None
        self.http_object = None
        self.stopping = False

    def init_signals(self):
        """
        Setup signal handling.
        """
        signal.signal(signal.SIGINT, self.handle_sig)
        signal.signal(signal.SIGTERM, self.handle_sig)

    def handle_sig(self, signum, frame):

        """
        Function to handle signals.

        SIGINT and SIGTERM both result in AD shutting down

        :param signum: signal number being processed
        :param frame: frame - unused
        """

        if signum == signal.SIGINT:
            self.logger.info("Keyboard interrupt")
            self.stop()
        if signum == signal.SIGTERM:
            self.logger.info("SIGTERM Recieved")
            self.stop()

    def stop(self):

        """
        Called by the signal handler to shut HookMan down.

        :return: None
        """

        self.logger.info("Hookman is shutting down")
        self.http_object.stop()
        self.stopping = True

    # noinspection PyBroadException,PyBroadException
    def run(self, config):

        """
        Start HookMan up after initial argument parsing.

        Create loop, createHTTP Object.

        :param http: config dictionary
        """

        try:
            loop = asyncio.get_event_loop()

            self.logger.info("Initializing HTTP")
            self.http_object = http.HTTP(__version__, loop, self.logger, config["http"], config["mappings"], self.test, self.config_file, self.reload)

            self.logger.info("Start Main Loop")

            pending = asyncio.Task.all_tasks()

            loop.run_until_complete(asyncio.gather(*pending))


            #
            # Now we are shutting down - perform any necessary cleanup
            #

            self.logger.info("HookMan is stopped.")

        except:
            self.logger.warning('-' * 60)
            self.logger.warning("Unexpected error during run()")
            self.logger.warning('-' * 60, exc_info=True)
            self.logger.warning('-' * 60)

            self.logger.debug("End Loop")

            self.logger.info("AppDeamon Exited")

    # noinspection PyBroadException
    def main(self):

        """
        Initial HookMan entry point.

        Parse command line arguments, load configuration, set up logging.
        """

        self.init_signals()

        # Get command line args

        parser = argparse.ArgumentParser()

        parser.add_argument("config", help="full or relative path to config file", type=str)
        parser.add_argument("-t", "--test", help="Test mode - print forwarding request and don't call", action='store_true')
        parser.add_argument("-r", "--reload", help="Reload config for every request - for testing purposes", action='store_true')

        args = parser.parse_args()

        self.config_file = args.config
        self.test = args.test
        self.reload = args.reload

        try:
            #
            # Read config file
            #
            with open(self.config_file) as json_file:
                config = json.load(json_file)

        except Exception as e:
            print("ERROR", "Error loading configuration file: {}".format(e))
            sys.exit(1)

        # Setup logging

        self.logger = logging.getLogger("log1")

        if "log" in config:
            log_config = config["log"]
        else:
            log_config = None

        if log_config is not None and "level" in log_config:
            level = log_config["level"]
        else:
            level = "INFO"

        self.logger.setLevel(level)
        self.logger.propagate = False
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

        fh = None
        if log_config is not None and "logfile" in log_config:
            if log_config["logfile"] != "STDOUT":
                if "log_size" in log_config:
                    log_size = int(log_config["log_size"])
                else:
                    log_size = 10000000

                if "log_generations" in log_config:
                    log_generations = int(log_config["log_generations"])
                else:
                    log_generations = 3

                fh = RotatingFileHandler(log_config["logfile"], maxBytes=log_size, backupCount=log_generations)
        else:
            # Default for StreamHandler() is sys.stderr
            fh = logging.StreamHandler(stream=sys.stdout)

        fh.setLevel(level)
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

        # Startup message

        self.logger.info("HookMan Version %s starting", __version__)
        self.logger.info("Configuration read from: %s", self.config_file)

        if "http" not in config:
            self.logger.error("Missing 'http' section in %s - exiting", self.config_file)
            sys.exit(1)

        if "mappings" not in config:
            self.logger.error("Missing 'mappings' section in %s - exiting", self.config_file)
            sys.exit(1)

        self.run(config)

def main():
    """
    Called when run from the command line.
    """
    hookman = HMMain()
    hookman.main()

if __name__ == "__main__":
    main()