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
import time
import schedule

# Local application/library specific imports
from machine_monitoring_app.database.db_utils import initialize_pony
from machine_monitoring_app.report_manager.email_sender import send_mail


__author__ = "smt18m005@iiitdm.ac.in"

LOGGER = logging.getLogger(__name__)


def main():
    """
    Main Function
    ====================

    Main function to call appropriate functions to send email notifications

    :return: Nothing
    :rtype: None

    """
    send_mail()
    LOGGER.info("Mail Sent")


if __name__ == '__main__':

    schedule.every(1).minutes.do(main)
    initialize_pony()

    while True:
        schedule.run_pending()
        LOGGER.debug("Sleeping for 1 second")
        time.sleep(1)
