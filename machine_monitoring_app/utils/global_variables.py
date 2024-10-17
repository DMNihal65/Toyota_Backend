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
import logging
from functools import lru_cache

# Related third party imports
import pandas as pd

# Local application/library specific imports
from machine_monitoring_app.models.base_data_models import Settings, EmailSettings

__author__ = "smt18m005@iiitdm.ac.in"

LOGGER = logging.getLogger(__name__)


@lru_cache()
def get_settings():
    """
    Return the configuration settings read from the os environment, using pydantic's base settings class

    :return: The configuration settings read from the os
    :rtype: Settings
    """
    LOGGER.debug("New Request for environment variable")
    return Settings()


@lru_cache()
def get_settings_email_service():
    """
    Return the configuration settings read from the os environment, using pydantic's base settings class
    for email service

    :return: The configuration settings read from the os
    :rtype: EmailSettings
    """
    LOGGER.debug("New Request for environment variable")
    return EmailSettings()


@lru_cache()
def get_axis_translation():
    """
    Return the configuration settings read from the os environment, using pydantic's base settings class

    :return: The translation settings read from the file
    :rtype: pd.DataFrame
    """
    LOGGER.debug("New Request for environment variable")

    axis_data = pd.read_excel("./input/axis_translation.xlsx")

    return axis_data


def main():
    """
    Main Function
    ====================

    Main function to call appropriate functions to

    """

    get_axis_translation()


if __name__ == "__main__":
    main()
