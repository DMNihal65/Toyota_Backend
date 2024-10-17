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
import schedule
import time

# Local application/library specific imports
from machine_monitoring_app.report_manager.report_summary_generator import main as report_main
from machine_monitoring_app.database.db_utils import initialize_pony
from machine_monitoring_app.report_manager.email_sender import send_mail

__author__ = "smt18m005@iiitdm.ac.in"

LOGGER = logging.getLogger(__name__)


def main():
    """
    Main Function to generate 4 hour summary report

    :return: Nothing
    :rtype: None
    """

    # Initializing Database Connections
    # initialize_pony()

    # Creating Reports
    report_main()
    LOGGER.info("Reports Generated")

    # Sending Email
    # send_mail()


if __name__ == '__main__':

    schedule.every().day.at("09:30").do(main)
    schedule.every().day.at("13:30").do(main)
    schedule.every().day.at("17:30").do(main)
    schedule.every().day.at("21:30").do(main)
    schedule.every().day.at("24:00").do(main)

    #schedule.every(1).minutes.do(main)

    initialize_pony()

    while True:
        schedule.run_pending()
        LOGGER.debug("Sleeping for 1 second")
        time.sleep(10)
