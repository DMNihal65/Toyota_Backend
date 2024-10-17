#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Logging Configuration
================================

Main Module for configuring logger

This script requires the following modules be installed in the python environment
    * logging - To perform logging operations
    * json - To load json files

This script contains the following function
    * configure_logging - To configure logging
    * load_database_credentials - To load database credentials file
"""

# Standard library imports
import logging.config
import json

# Local application/library specific imports
from machine_monitoring_app.utils import DEFAULT_LOGGER_PATH, DEFAULT_DB_CREDENTIALS_PATH
from machine_monitoring_app.database.db_utils import initialize_pony

__author__ = "smt18m005@iiitdm.ac.in"

LOGGER = logging.getLogger(__name__)


def configure_logging(filepath: str = DEFAULT_LOGGER_PATH):
    """
    Function to configure logging
    ==================================

    :param filepath: The file path for the logger configuration file
    :type filepath: str

    :return: Nothing
    :rtype: None
    """
    try:
        with open(filepath, 'r') as file_object:
            config_data = json.load(file_object)
    except FileNotFoundError as err:
        LOGGER.error(err)
        raise

    logging.config.dictConfig(config_data)

    LOGGER.info("Configured Logging")


def load_database_credentials(filepath: str = DEFAULT_DB_CREDENTIALS_PATH):
    """
    Function to load database credentials file
    ================================================

    :param filepath: The file path for the database credentials file
    :type filepath: str

    :return: Dictionary consisting of database connection credentials
    :rtype: dict
    """
    try:
        with open(filepath, 'r') as file_object:
            credential_data = json.load(file_object)
    except FileNotFoundError as err:
        LOGGER.error(err)
        raise

    LOGGER.info("Loaded DB credentials file")

    return credential_data


def initialize_server():
    """
    Initialize the server

    :return: None
    """

    # Configure logger settings
    configure_logging()

    # Initialize database connection settings
    initialize_pony()


def main():
    """
    Main Function
    ====================

    Main function to call appropriate functions to

    """

    pass


if __name__ == "__main__":
    main()
