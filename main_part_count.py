#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Main Module for the Monitoring Application
===============================================

Module for starting point of the FastApi application

This script requires the following modules be installed in the python environment
    * logging - To perform logging operations.
    * fastapi - To perform web application (backend) related functions.
"""

# Standard library imports
import logging


# Local application/library specific imports
from machine_monitoring_app.utils.configuration_helper import initialize_server
from machine_monitoring_app.monitoring_services.part_monitor import monitor_part_count

__author__ = "smt18m005@iiitdm.ac.in"

LOGGER = logging.getLogger(__name__)


def main():
    """
    Main Function
    ====================

    Main function to call appropriate functions to start the part count monitoring application

    :return: Nothing
    :rtype: None

    """

    initialize_server()
    monitor_part_count(10)


if __name__ == '__main__':

    main()
