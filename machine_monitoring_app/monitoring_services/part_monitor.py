#!/usr/bin/python
# -*- coding: utf-8 -*-
"""

================================

Module for  application to

This script requires the following modules be installed in the python environment
    * logging - to perform logging operations

This script contains the following function
    * main - main function to call appropriate functions to find the contours in the video
"""

# Standard library imports
import logging
import time
from datetime import datetime

# Related third party imports
from pony.orm import db_session, commit, max as pony_max, min as pony_min, select

# Local application/library specific imports
from machine_monitoring_app.database.mongodb_client import get_mongo_collection
from machine_monitoring_app.database.pony_models import Machine, MachinePartCount, SparePart
from machine_monitoring_app.database.mongo_db_utils import part_signal_query_with_time
from machine_monitoring_app.report_manager.email_sender import create_excel_report
from machine_monitoring_app.report_manager import EMAIL_REPORT_ROOT_DIRECTORY

__author__ = "smt18m005@iiitdm.ac.in"

LOGGER = logging.getLogger(__name__)


@db_session
def get_new_part_data(query_timestamp: datetime):
    """
    Function to monitor the mongodb for new part count data and insert it into timescaledb database

    :return: It returns the updatedate time of the machine whose part count got updated recently.
    :rtype: datetime | None
    """
    # Getting the mongodb collection
    collection = get_mongo_collection("L1Signal_Pool_Active_2")

    # Getting the aggregate value
    part_count_data = collection.aggregate(part_signal_query_with_time(query_timestamp))

    # Converting it to list
    part_count_data = list(part_count_data)

    # This variable is used to store the abnormal spare parts( when they are beyond the limits)
    abnormal_spare_part_count = []

    # If part count is none, we return None
    if not part_count_data:
        return

    # For every part count data, we do the following
    for part in part_count_data:

        # Get the MachinePartCount object(Table)
        machine_part_count = MachinePartCount.get(part_signal_name=part['signalname'])

        # If in case the part count value is zero, meaning either the machine is not configured
        # Or is turned of now, we skip the remaining code
        if part['value'] is None:
            continue

        # If the machine part count has been reset from the HMI, then the current part count will be zero
        # Hence it will be less than the current part count in the database.
        if part['value'] < machine_part_count.current_part_count:

            # If the part count is reset, we set the last_reset_count to the current_part_count
            # That is there in the database.
            machine_part_count.last_reset_count = machine_part_count.current_part_count
            commit()

        # We set the current_part_count equal to the last_reset_count + current part count value
        # From the "PMC_D9388" register.
        machine_part_count.current_part_count = machine_part_count.last_reset_count + part["value"]

        # Updating the latest_update_time in the database, for this machine part count
        machine_part_count.latest_update_time = part["updatedate"]
        commit()

        # The remaining part of the code checks for abnormal part count

        # Getting all the spare parts for the machine
        spare_parts = SparePart.select(lambda sp: sp.machine == machine_part_count.machine)[:]

        # For all the spare parts this machine has, we do the following
        for spare_part in spare_parts:

            # The current part count for this spare part is equal to the current part count of the
            # Machine minus the reference part count. This reference part count is equal to the
            # Part count of the machine (to which the spare part belongs) when it was created/reset
            # From the front end.
            current_spare_part_count = machine_part_count.current_part_count - spare_part.reference_part_number

            # If the current_spare_part_count is greater than the critical limit, we append it to the list
            # Of abnormal_spare_part_count
            if current_spare_part_count > spare_part.critical_limit:
                abnormal_spare_part_count.append((spare_part, current_spare_part_count,
                                                  str(part["updatedate"]),
                                                  "Critical"))

            # If the current_spare_part_count is greater than the warning limit, we append it to the list
            # Of abnormal_spare_part_count
            elif current_spare_part_count > spare_part.warning_limit:
                abnormal_spare_part_count.append((spare_part, current_spare_part_count,
                                                  str(part["updatedate"]), "Warning"))
            # By having separate check for warning and critical, the machine will be added only once to the
            # abnormal_spare_part_count list

    # The data coming from the mongodb database is already sorted in descending order with respect to the updatedate
    # So we can get the first value to get the recent most timestamp
    recent_update_time = part_count_data[0]["updatedate"]

    if abnormal_spare_part_count:
        # This variable is used to convert and store the abnormal data in a format that is required
        # For generating the excel report
        abnormal_spare_part_data = []

        for index, abnormal_part in enumerate(abnormal_spare_part_count):

            current_part_data = [str(index + 1), abnormal_part[0].machine.name,
                                 abnormal_part[2],
                                 abnormal_part[0].part_name,
                                 abnormal_part[3],
                                 abnormal_part[1],
                                 abnormal_part[0].warning_limit,
                                 abnormal_part[0].critical_limit]

            abnormal_spare_part_data.append(current_part_data)

        file_location = EMAIL_REPORT_ROOT_DIRECTORY + "critical_alert_report_part_count.xlsx"

        LOGGER.info("Creating Abnormal Report")
        create_excel_report(file_location=file_location,
                            data=abnormal_spare_part_data,  parameter_type="part_count")
    return recent_update_time


@db_session
def monitor_part_count(sleep_time: int):
    """
    Function to monitor the part count of all machines in the MtLINKi Mongodb database

    :param sleep_time: The sleep time in seconds for this service

    :return: Nothing
    :rtype: None
    """

    #latest_update_time = pony_max(mpc.latest_update_time for mpc in MachinePartCount)
    latest_update_time = pony_min(mpc.latest_update_time for mpc in MachinePartCount)

    while True:
        LOGGER.info("Getting New Data")

        # Getting new part count values from the mongodb database and setting the return value
        # From the database to _latest_update_time.
        _latest_update_time = get_new_part_data(latest_update_time)

        # If the function returns a datetime object, then we set it to latest_update_time
        if _latest_update_time:
            LOGGER.info("Got New Data")
            latest_update_time = _latest_update_time
        else:
            LOGGER.info("No New Data")

        LOGGER.info(f"Sleeping for {sleep_time} seconds")
        # Sleeping for given time.
        time.sleep(sleep_time)


def main():
    """
    Main Function
    ====================
    
    Main function to call appropriate functions to start the part monitor services

    """


if __name__ == '__main__':
    main()
