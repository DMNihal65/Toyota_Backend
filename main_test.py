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
from machine_monitoring_app.report_manager.report_summary_generator import main as report_main
from machine_monitoring_app.database.db_utils import initialize_pony, main as db_utils_main
from machine_monitoring_app.report_manager.email_sender import send_mail
from machine_monitoring_app.database.crud_operations import main as crud_main
from machine_monitoring_app.database.mongo_db_utils import main as mongo_db_utils_main

__author__ = "smt18m005@iiitdm.ac.in"

LOGGER = logging.getLogger(__name__)


def main():
    """

    :return:
    :rtype:
    """

    # Initializing Database Connections
    initialize_pony()

    #mongo_db_utils_main()

    crud_main()

    #db_utils_main()

    # Getting email ids
    #get_user_emails()

    # Creating Reports
    #report_main()

    # Sending Email
    #send_mail()


if __name__ == "__main__":
    main()
