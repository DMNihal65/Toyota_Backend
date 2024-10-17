#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
DATABASE UTILITY FUNCTIONS
================================

Module that has utility functions for database operations

This script requires the following modules be installed in the python environment
    * logging - To perform logging operations.
    * motor - To perform database connection operation in asynchronous way.

This script contains the following function
    * connect_to_mongo - Function that connects to mongodb by creating a client at the start of the application.
    * close_mongo_connection - Function that destroys the connection to mongodb by closing the mongodb client.
"""

# Standard library imports
import logging
from typing import List, Optional
from datetime import timedelta

# Related third party imports
from pony.orm import Database, set_sql_debug, db_session

# from motor.motor_asyncio import AsyncIOMotorClient
# from sqlmodel import Session

# Local application/library specific imports
# from ..database import MONGODB_URL, MAX_CONNECTIONS_COUNT, MIN_CONNECTIONS_COUNT
# from .mongodb_client import DATABASE
# from machine_monitoring_app.database import TIMESCALE_ENGINE
from machine_monitoring_app.utils.global_variables import get_settings

__author__ = "smt18m005@iiitdm.ac.in"

LOGGER = logging.getLogger(__name__)

PONY_DATABASE = Database()


def initialize_pony(debug=True):
    """

    Function used to initialize the database connection object using pony orm

    :return: Nothing
    :rtype: None

    """

    setting = get_settings()

    LOGGER.info(setting.timescaledb_provider)
    LOGGER.info(setting.timescaledb_user)
    LOGGER.info(setting.timescaledb_password)
    LOGGER.info(setting.timescaledb_host)
    LOGGER.info(setting.timescaledb_database)
    PONY_DATABASE.bind(provider=setting.timescaledb_provider, user=setting.timescaledb_user,
                       password=setting.timescaledb_password, host=setting.timescaledb_host,
                       database=setting.timescaledb_database, port=setting.timescaledb_port )

    PONY_DATABASE.generate_mapping(create_tables=False)
    print("Generated mapping")
    if debug:
        set_sql_debug(True)


def get_all_status_templates():
    """
    Function used to return the query template used to get the count of critical/warning states

    :return: A String containing the sql query
    :rtype: str
    """

    template = """SELECT test.recent_group, count(*)
        FROM (SELECT tiei_sample_4.real_time_machine_parameters.machine_parameters_id,
              last(condition_id,time) AS recent_condition, last(time,time) AS recent_time,
              last(parameter_group_id, time) AS recent_group
                    FROM tiei_sample_4.real_time_machine_parameters
                JOIN tiei_sample_4.machine_parameters
                 ON tiei_sample_4.machine_parameters.id = 
                 tiei_sample_4.real_time_machine_parameters.machine_parameters_id
                 WHERE time > now() - INTERVAL '1 days'
                GROUP BY tiei_sample_4.real_time_machine_parameters.machine_parameters_id
                HAVING last(condition_id,time) = {condition_holder}) as test
    GROUP BY test.recent_group
    ORDER BY recent_group;
    """

    # template = """SELECT test.recent_group, count(*)
    #     FROM (SELECT tiei_sample_4.real_time_machine_parameters.machine_parameters_id,
    #           last(condition_id,time) AS recent_condition, last(time,time) AS recent_time,
    #           last(parameter_group_id, time) AS recent_group
    #                 FROM tiei_sample_4.real_time_machine_parameters
    #             JOIN tiei_sample_4.machine_parameters
    #              ON tiei_sample_4.machine_parameters.id =
    #               tiei_sample_4.real_time_machine_parameters.machine_parameters_id
    #             GROUP BY tiei_sample_4.real_time_machine_parameters.machine_parameters_id
    #             HAVING last(condition_id,time) = {condition_holder}) as test
    # GROUP BY test.recent_group
    # ORDER BY recent_group;
    # """

    return template


def get_all_recent_time_template():
    """
    Function used to return the query template used to get the count of critical/warning states

    :return: A String containing the sql query
    :rtype: str
    """

    template = """SELECT machine_parameters_id, first(time, time) as old_time
        FROM tiei_sample_4.real_time_machine_parameters
        JOIN tiei_sample_4.machine_parameters
            ON tiei_sample_4.machine_parameters.id = tiei_sample_4.real_time_machine_parameters.machine_parameters_id
            WHERE parameter_group_id = 17
        GROUP BY machine_parameters_id
        ORDER BY machine_parameters_id
        """

    return template


# async def connect_to_mongo():
#     """
#     Function that connects to mongodb by creating a client at the start of the application.
#
#     :return: Nothing
#     :rtype: None
#     """
#
#     LOGGER.info("Creating Mongodb client")
#     DATABASE.client = AsyncIOMotorClient(str(MONGODB_URL),
#                                          maxPoolSize=MAX_CONNECTIONS_COUNT,
#                                          minPoolSize=MIN_CONNECTIONS_COUNT)
#     LOGGER.info("Connection Created")
#
#
# async def close_mongo_connection():
#     """
#     Function that destroys the connection to mongodb by closing the mongodb client.
#
#     :return: Nothing
#     :rtype: None
#     """
#
#     LOGGER.info("Closing Mongodb Connection")
#     DATABASE.client.close()
#     LOGGER.info("Closed Mongodb Connection")
#
#
# def get_session():
#     """
#     GET SESSION
#     =============
#     """
#     with Session(TIMESCALE_ENGINE) as session:
#         yield session

# initialize_pony()


@db_session
def main():
    """
    Main Function
    ====================

    Main function to call appropriate functions to

    """

    # query = """SELECT * FROM tiei_sample_4.machine_parameters
    # ORDER BY id ASC LIMIT 10;
    # """
    # data = PONY_DATABASE.select(query)
    #
    # for d in data:
    #     print(d)

    # for mac in select(m for m in MachineProductionTimeline).order_by(MachineProductionTimeline.id)[:10]:
    #     print(mac.id, mac.start_time)


if __name__ == "__main__":
    main()
