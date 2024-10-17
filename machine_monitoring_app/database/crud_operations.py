#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
DATABASE CRUD OPERATIONS
================================

Module consisting of functions to carry out database crud operations

This script requires the following modules be installed in the python environment

    Standard Library
    =================
    * logging - To perform logging operations.
    * pprint - To pretty print the output from database operations.

    Related 3rd Party Library
    =============================

This script contains the following function
    * get_current_machine_data - Function that connects to database to get the current machine details
"""

# Standard library imports
import logging
import pprint
import re
import time
from datetime import datetime, timedelta, timezone, date
import pytz
from typing import Optional, List,Dict
import calendar
import math
import json

# Related third party imports
from pony.orm import db_session, desc, commit, count as pony_count, select
from pony.orm.core import ObjectNotFound
import pandas as pd
from fastapi import HTTPException
import numpy as np

# Local application/library specific imports
from machine_monitoring_app.database.orm import update_operation
from machine_monitoring_app.database.pony_models import Machine, ParameterGroup, MachineParameter, \
    RealTimeParameter, User as UserPony, SparePart, EmailUser, MachinePartCount, User, RealTimeParameterActive, \
    MachineProductionTimeline, MachinePartCount, CorrectiveActivity, ActivityHistory, ParameterCondition, UpdateLog,UserAccessLog

from machine_monitoring_app.exception_handling.custom_exceptions import NoParameterGroupError, \
    GetParamGroupDBError, GetAllParameterDBError, GetMachineTimelineError

from machine_monitoring_app.models.base_data_models import UserInDB, User as UserPydantic
from machine_monitoring_app.database.mongodb_client import get_mongo_collection, get_mongo_collection_active

from machine_monitoring_app.database.mongo_db_utils import (get_exceed_group_template, get_within_group_template, \
                                                            get_between_head_group_template,
                                                            get_between_tail_group_template,
                                                            get_exceed_group_day_template, \
                                                            get_within_group_day_template,
                                                            get_between_head_group_day_template,
                                                            get_between_tail_group_day_template, \
                                                            get_timeline_group_template, get_timespan_group_template,
                                                            get_count_group_template, \
                                                            get_recent_most_alarm_time_template,
                                                            get_real_time_data_mtlinki,
                                                            get_value_before_requested_data_mtlinki,
                                                            get_recent_active_pool_value,
                                                            get_machine_states_mtlinki)

from machine_monitoring_app.models.request_models import SparePartUpdateList

from machine_monitoring_app.models.response_models import SparePart as PydanticSparePart, UpdateLogResponse,DisconnectionHistoryItem
from machine_monitoring_app.database.db_utils import get_all_status_templates, get_all_recent_time_template, \
    initialize_pony
from machine_monitoring_app.database.db_utils import PONY_DATABASE

__author__ = "smt18m005@iiitdm.ac.in"

LOGGER = logging.getLogger(__name__)


@db_session
def get_schema_name():
    try:
        schema_name = PONY_DATABASE.schema
        return {"schema_name": schema_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def custom_sort_key(machine_name):
    parts = re.split(r'(\d+)', machine_name)
    return [part if i % 2 == 0 else int(part) for i, part in enumerate(parts)]
def alphanumeric_key(s):
    return [int(text) if text.isdigit() else text for text in re.split('([0-9]+)', s)]

@db_session(optimistic=False)
def get_real_time_parameters_data():
    """
    Retrieves real-time parameter data for a specific set of conditions.

    Returns a nested JSON structure containing information about parameter groups,
    locations, machines, and their respective parameters.

    :return: List of JSON objects representing parameter group data
    :rtype: dict
    """

    # Query the database for relevant data
    result = select(
        (pg.group_name,
         m.location,
         m.name,
         mp.name,
         mp.display_name,
         mp.internal_parameter_name,
         rtpa.time,
         rtpa.value,
         mp.warning_limit,
         mp.critical_limit,
         rtpa.parameter_condition.name)

        for rtpa in RealTimeParameterActive
        for mp in MachineParameter
        for pg in ParameterGroup
        for m in Machine
        if (
                rtpa.machine_parameter == mp and
                mp.parameter_group == pg and
                mp.machine == m

        )
    ).order_by(lambda _group_name, machine_location, _machine_name,
                      parameter_name, display_name, internal_parameter_name, timestamp, value, warn_limit,
                      _critical_limit, condition_name: (_group_name, machine_location, _machine_name, parameter_name))

    # Convert the result to a pandas DataFrame
    columns = ['group_name', 'location', 'machine_name', 'parameter_name',
               'display_name', 'internal_parameter_name', 'time', 'value', 'warn_limit',
               'critical_limit', 'condition_name']
    result_df = pd.DataFrame(result, columns=columns)
    result_df = result_df.sort_values(by='machine_name', key=lambda col: col.map(alphanumeric_key))

    # result_df = result_df.sort_values(
    #     by=['group_name', 'location', 'machine_name'],
    #     key=lambda x: x.map(lambda y: custom_sort_key(y) if x.name == 'machine_name' else y)
    # )
    groups_overview = []

    # Create a nested JSON structure
    json_list = []

    # Iterate over unique parameter groups
    for group_name, group_data in result_df.groupby('group_name'):
        group_json = {'group_name': group_name, 'group_details': [], 'group_state': 'OK',
                      'count': {'OK': 0, 'WARNING': 0, 'CRITICAL': 0}}

        # Iterate over unique locations within the parameter group
        for location, location_data in group_data.groupby('location'):
            location_json = {'line_name': location, 'machines': [], 'line_state': 'OK',
                             'count': {'OK': 0, 'WARNING': 0, 'CRITICAL': 0}}
            # Iterate over unique machines within the location
            for machine_name, machine_data in location_data.groupby('machine_name', sort=False):
                machine_json = {'machine_name': machine_name, 'parameters': [], 'machine_state': 'OK'}

                # Initialize counts for the machine
                machine_count = {'OK': 0, 'WARNING': 0, 'CRITICAL': 0}

                # Iterate over parameter data for the machine
                for _, row in machine_data.iterrows():
                    # Replace NaN values with None
                    warning_limit = row['warn_limit'] if not pd.isna(row['warn_limit']) else None
                    critical_limit = row['critical_limit'] if not pd.isna(row['critical_limit']) else None
                    parameter_value = None if math.isnan(row['value']) else row['value']

                    parameter_json = {
                        'actual_parameter_name': row['parameter_name'],
                        'display_name': row['display_name'],
                        'internal_parameter_name': row['internal_parameter_name'],
                        'latest_update_time': int(row['time'].timestamp() * 1000),
                        'parameter_value': parameter_value,
                        'parameter_state': row['condition_name'],
                        'warning_limit': warning_limit,
                        'critical_limit': critical_limit
                    }

                    machine_json['parameters'].append(parameter_json)

                    # Update counts based on parameter state
                    if row['condition_name'] == 'OK':
                        machine_count['OK'] += 1
                    elif row['condition_name'] == 'WARNING':
                        machine_count['WARNING'] += 1
                    elif row['condition_name'] == 'CRITICAL':
                        machine_count['CRITICAL'] += 1

                # Determine machine state and line count based on machine's counts
                if machine_count['CRITICAL'] > 0:
                    machine_json['machine_state'] = 'CRITICAL'

                    # Increment the location's critical count also
                    location_json['count']['CRITICAL'] += 1
                elif machine_count['WARNING'] > 0:
                    machine_json['machine_state'] = 'WARNING'

                    # Increment the location's warning count also
                    location_json['count']['WARNING'] += 1
                else:
                    # Increment the location's ok count also
                    location_json['count']['OK'] += 1

                location_json['machines'].append(machine_json)

            # Determine line state based on counts
            if location_json['count']['CRITICAL'] > 0:
                location_json['line_state'] = 'CRITICAL'
            elif location_json['count']['WARNING'] > 0:
                location_json['line_state'] = 'WARNING'

            # Update counts for the line state
            group_json['count']['OK'] += location_json['count']['OK']
            group_json['count']['WARNING'] += location_json['count']['WARNING']
            group_json['count']['CRITICAL'] += location_json['count']['CRITICAL']

            group_json['group_details'].append(location_json)

        # Determine group state based on counts
        if group_json['count']['CRITICAL'] > 0:
            group_json['group_state'] = 'CRITICAL'
        elif group_json['count']['WARNING'] > 0:
            group_json['group_state'] = 'WARNING'

        group_info = {"item_name": group_name,
                      "item_state": group_json['group_state']}

        groups_overview.append(group_info)

        json_list.append(group_json)

    response = {"group_names": groups_overview,
                "all_group_details": json_list}
    return response


# TODO : CHANGES TO THE LAYOUT UISNG THE MTLINKI


@db_session(optimistic=False)
def get_real_time_parameters_data_mtlinki():
    """
    Retrieves real-time parameter data for a specific set of conditions.

    Returns a nested JSON structure containing information about parameter groups,
    locations, machines, and their respective parameters.

    :return: List of JSON objects representing parameter group data
    :rtype: dict
    """

    # Get the PostgreSQL data
    machines = select(m.name for m in Machine)
    parameters = select(mp.name for mp in MachineParameter)
    mongodb_q = select(mpg.mongodb_query for mpg in ParameterGroup)

    # Get the MongoDB collection
    collection = get_mongo_collection("L1Signal_Pool_Active")

    # Initialize an empty list to store processed data
    processed_data = []

    # Loop through each machine name from PostgreSQL
    for machine_name in machines:
        # Loop through each parameter using regex pattern from PostgreSQL
        for mongodb_query in mongodb_q:
            # Define the MongoDB query regex pattern
            regex_pattern = re.compile(f".*{mongodb_query}.*")

            # MongoDB aggregation pipeline
            pipeline = [
                {
                    '$match': {
                        'L1Name': machine_name,
                        'signalname': {'$regex': regex_pattern}
                    }
                },
                {
                    '$project': {
                        'L1Name': 1,
                        'signalname': 1,
                        'value': 1
                    }
                }
            ]

            # Execute the aggregation pipeline
            result = collection.aggregate(pipeline)

            # Convert the cursor to a list of dictionaries
            result_list = list(result)

            # Append the processed data to the list
            processed_data.extend(result_list)

    # Convert the processed data to a Pandas DataFrame
    df = pd.DataFrame(processed_data)
    LOGGER.info(df)

    # Query the database for relevant data
    result = select(
        (pg.group_name,
         m.location,
         m.name,
         mp.name,
         mp.display_name,
         mp.internal_parameter_name,
         rtpa.time,
         rtpa.value,
         mp.warning_limit,
         mp.critical_limit,
         rtpa.parameter_condition.name)

        for rtpa in RealTimeParameterActive
        for mp in MachineParameter
        for pg in ParameterGroup
        for m in Machine
        if (
                rtpa.machine_parameter == mp and
                mp.parameter_group == pg and
                mp.machine == m

        )
    ).order_by(lambda _group_name, machine_location, _machine_name,
                      parameter_name, display_name, internal_parameter_name, timestamp, value, warn_limit,
                      _critical_limit, condition_name: (_group_name, machine_location, _machine_name, parameter_name))

    # Convert the result to a pandas DataFrame
    columns = ['group_name', 'location', 'machine_name', 'parameter_name',
               'display_name', 'internal_parameter_name', 'time', 'value', 'warn_limit',
               'critical_limit', 'condition_name']
    result_df = pd.DataFrame(result, columns=columns)
    result_df = result_df.sort_values(by='machine_name', key=lambda col: col.map(alphanumeric_key))

    groups_overview = []

    # Create a nested JSON structure
    json_list = []

    # Iterate over unique parameter groups
    for group_name, group_data in result_df.groupby('group_name'):
        group_json = {'group_name': group_name, 'group_details': [], 'group_state': 'OK',
                      'count': {'OK': 0, 'WARNING': 0, 'CRITICAL': 0}}

        # Iterate over unique locations within the parameter group
        for location, location_data in group_data.groupby('location'):
            location_json = {'line_name': location, 'machines': [], 'line_state': 'OK',
                             'count': {'OK': 0, 'WARNING': 0, 'CRITICAL': 0}}
            # Iterate over unique machines within the location
            for machine_name, machine_data in location_data.groupby('machine_name', sort=False):
                machine_json = {'machine_name': machine_name, 'parameters': [], 'machine_state': 'OK'}

                # Initialize counts for the machine
                machine_count = {'OK': 0, 'WARNING': 0, 'CRITICAL': 0}

                # Iterate over parameter data for the machine
                for _, row in machine_data.iterrows():
                    # Replace NaN values with None
                    warning_limit = row['warn_limit'] if not pd.isna(row['warn_limit']) else None
                    critical_limit = row['critical_limit'] if not pd.isna(row['critical_limit']) else None
                    parameter_value = None if math.isnan(row['value']) else row['value']

                    parameter_json = {
                        'actual_parameter_name': row['parameter_name'],
                        'display_name': row['display_name'],
                        'internal_parameter_name': row['internal_parameter_name'],
                        'latest_update_time': int(row['time'].timestamp() * 1000),
                        'parameter_value': parameter_value,
                        'parameter_state': row['condition_name'],
                        'warning_limit': warning_limit,
                        'critical_limit': critical_limit
                    }

                    machine_json['parameters'].append(parameter_json)

                    # Update counts based on parameter state
                    if row['condition_name'] == 'OK':
                        machine_count['OK'] += 1
                    elif row['condition_name'] == 'WARNING':
                        machine_count['WARNING'] += 1
                    elif row['condition_name'] == 'CRITICAL':
                        machine_count['CRITICAL'] += 1

                # Determine machine state and line count based on machine's counts
                if machine_count['CRITICAL'] > 0:
                    machine_json['machine_state'] = 'CRITICAL'

                    # Increment the location's critical count also
                    location_json['count']['CRITICAL'] += 1
                elif machine_count['WARNING'] > 0:
                    machine_json['machine_state'] = 'WARNING'

                    # Increment the location's warning count also
                    location_json['count']['WARNING'] += 1
                else:
                    # Increment the location's ok count also
                    location_json['count']['OK'] += 1

                location_json['machines'].append(machine_json)

            # Determine line state based on counts
            if location_json['count']['CRITICAL'] > 0:
                location_json['line_state'] = 'CRITICAL'
            elif location_json['count']['WARNING'] > 0:
                location_json['line_state'] = 'WARNING'

            # Update counts for the line state
            group_json['count']['OK'] += location_json['count']['OK']
            group_json['count']['WARNING'] += location_json['count']['WARNING']
            group_json['count']['CRITICAL'] += location_json['count']['CRITICAL']

            group_json['group_details'].append(location_json)

        # Determine group state based on counts
        if group_json['count']['CRITICAL'] > 0:
            group_json['group_state'] = 'CRITICAL'
        elif group_json['count']['WARNING'] > 0:
            group_json['group_state'] = 'WARNING'

        group_info = {"item_name": group_name,
                      "item_state": group_json['group_state']}

        groups_overview.append(group_info)

        json_list.append(group_json)

    response = {"group_names": groups_overview,
                "all_group_details": json_list}
    return response


@db_session(optimistic=False)
def get_latest_snapshot_for_parameter_group(parameter_group_name: str = "APC_BATTERY"):
    """
    Fetches the latest snapshot of the status of all machines in all production lines
    for the given parameter group.

    :param parameter_group_name: The name of the parameter group.
    :type parameter_group_name: str

    :return: Dictionary containing the latest snapshot of machine statuses.
    :rtype: dict
    """

    try:

        LOGGER.info("Retrieving current machine details")

        response = {"group_names": get_parameter_group_statuses(),
                    "requested_group_details": get_real_time_parameters_data_by_group(parameter_group_name)}

        return response
    except ObjectNotFound as error:
        LOGGER.error(f"The given parameter group id is not available: {error.args[0]}")
        raise NoParameterGroupError


#TODO CHANGING THE FUCNTION TO GET THE DATA FOR THE SPECIFIC PARAMETER GROUP

@db_session(optimistic=False)
def get_latest_snapshot_for_parameter_group_test(parameter_group_name: str = "APC_BATTERY"):
    """
    Fetches the latest snapshot of the status of all machines in all production lines
    for the given parameter group.

    :param parameter_group_name: The name of the parameter group.
    :type parameter_group_name: str

    :return: Dictionary containing the latest snapshot of machine statuses.
    :rtype: dict
    """

    try:

        LOGGER.info("Retrieving current machine details")

        response = {"group_names": get_parameter_group_statuses(),
                    "requested_group_details": get_machine_states_2(parameter_group_name)}

        return response
    except ObjectNotFound as error:
        LOGGER.error(f"The given parameter group id is not available: {error.args[0]}")
        raise NoParameterGroupError


@db_session
def get_abnormalities_summary(start_time: datetime, end_time: datetime):
    """
    Get the count of abnormalities summary for given time range

    Parameters:
    - start_time (datetime): The start time of the query period.
    - end_time (datetime): The end time of the query period.

    Returns:
    - List[Tuple[str, int]]: A list of tuples containing parameter group names and corresponding total abnormalities
    count.
    """
    response_data = [{"line": "Overall", "WARNING": 0, "CRITICAL": 0, "COMPLETED": 0},
                     {"line": "Head", "WARNING": 0, "CRITICAL": 0, "COMPLETED": 0},
                     {"line": "Block", "WARNING": 0, "CRITICAL": 0, "COMPLETED": 0},
                     {"line": "Crank", "WARNING": 0, "CRITICAL": 0, "COMPLETED": 0}]

    # OVERALL LEVEL DATA START
    abnormality_query_pending_overall = select((ca.parameter_condition.name, pony_count(ca.id))
                                               for ca in CorrectiveActivity
                                               if ca.date_of_identification > start_time and
                                               ca.date_of_identification < end_time)

    # machines_query = machines_query.group_by(lambda: Machine.name)
    abnormality_query_pending_overall = abnormality_query_pending_overall.order_by(
        lambda condition, agg_count: desc(agg_count))[:]

    for data in abnormality_query_pending_overall:
        response_data[0][data[0]] = data[1]

    abnormality_query_completed_overall = select(pony_count((history.date_of_identification,
                                                             history.machine_parameter))
                                                 for history in ActivityHistory
                                                 if history.date_of_identification > start_time and
                                                 history.date_of_identification < end_time)

    # machines_query = abnormality_query_completed.group_by(lambda: Machine.name)
    abnormality_query_completed_overall = abnormality_query_completed_overall.order_by(lambda agg_count:
                                                                                       desc(agg_count))[:]
    if abnormality_query_completed_overall:
        response_data[0]["COMPLETED"] = abnormality_query_completed_overall[0]

    # OVERALL LEVEL DATA END

    # HEAD LEVEL DATA START

    abnormality_query_pending_head = select((ca.parameter_condition.name, pony_count(ca.id))
                                            for ca in CorrectiveActivity
                                            if ca.date_of_identification > start_time and
                                            ca.date_of_identification < end_time and
                                            ca.machine_parameter.machine.location == "HEAD")

    # machines_query = machines_query.group_by(lambda: Machine.name)
    abnormality_query_pending_head = abnormality_query_pending_head.order_by(
        lambda condition, agg_count: desc(agg_count))[:]

    for data in abnormality_query_pending_head:
        response_data[1][data[0]] = data[1]

    abnormality_query_completed_head = select(pony_count((history.date_of_identification,
                                                          history.machine_parameter))
                                              for history in ActivityHistory
                                              if history.date_of_identification > start_time and
                                              history.date_of_identification < end_time and
                                              history.machine_parameter.machine.location == "HEAD")

    abnormality_query_completed_head = abnormality_query_completed_head.order_by(lambda agg_count:
                                                                                 desc(agg_count))[:]
    if abnormality_query_completed_head:
        response_data[1]["COMPLETED"] = abnormality_query_completed_head[0]

    # HEAD LEVEL DATA END

    # BLOCK LEVEL DATA START
    abnormality_query_pending_block = select((ca.parameter_condition.name, pony_count(ca.id))
                                             for ca in CorrectiveActivity
                                             if ca.date_of_identification > start_time and
                                             ca.date_of_identification < end_time and
                                             ca.machine_parameter.machine.location == "BLOCK")

    abnormality_query_pending_block = abnormality_query_pending_block.order_by(
        lambda condition, agg_count: desc(agg_count))[:]

    for data in abnormality_query_pending_block:
        response_data[2][data[0]] = data[1]

    abnormality_query_completed_block = select(pony_count((history.date_of_identification,
                                                           history.machine_parameter))
                                               for history in ActivityHistory
                                               if history.date_of_identification > start_time and
                                               history.date_of_identification < end_time and
                                               history.machine_parameter.machine.location == "BLOCK")

    abnormality_query_completed_block = abnormality_query_completed_block.order_by(lambda agg_count:
                                                                                   desc(agg_count))[:]
    if abnormality_query_completed_block:
        response_data[2]["COMPLETED"] = abnormality_query_completed_block[0]

    # BLOCK LEVEL DATA END

    # CRANK LEVEL DATA START
    abnormality_query_pending_crank = select((ca.parameter_condition.name, pony_count(ca.id))
                                             for ca in CorrectiveActivity
                                             if ca.date_of_identification > start_time and
                                             ca.date_of_identification < end_time and
                                             ca.machine_parameter.machine.location == "CRANK")

    abnormality_query_pending_crank = abnormality_query_pending_crank.order_by(
        lambda condition, agg_count: desc(agg_count))[:]

    for data in abnormality_query_pending_crank:
        response_data[3][data[0]] = data[1]

    abnormality_query_completed_crank = select(pony_count((history.date_of_identification,
                                                           history.machine_parameter))
                                               for history in ActivityHistory
                                               if history.date_of_identification > start_time and
                                               history.date_of_identification < end_time and
                                               history.machine_parameter.machine.location == "CRANK")

    abnormality_query_completed_crank = abnormality_query_completed_crank.order_by(lambda agg_count:
                                                                                   desc(agg_count))[:]
    if abnormality_query_completed_crank:
        response_data[3]["COMPLETED"] = abnormality_query_completed_crank[0]

    # CRANK LEVEL DATA END

    return response_data


## abnormalities_summary for parameter_name

@db_session
def get_abnormalities_summary_parameter(pending_activities, history_dict, parameter_name):
    """
    Get the count of abnormalities summary for given time range

    Parameters:
    - pending_activities (list): List of pending activities.
    - history_dict (list): List of completed activities.
    - parameter_name (str): The parameter name to check completion status.

    Returns:
    - List[dict]: A list of dictionaries containing abnormalities summary for each line.
    """
    response_data = [{"line": "Overall", "WARNING": 0, "CRITICAL": 0, "COMPLETED": 0}]

    # Initialize line-wise counts
    line_counts = {"HEAD": {"WARNING": 0, "CRITICAL": 0, "COMPLETED": 0},
                   "BLOCK": {"WARNING": 0, "CRITICAL": 0, "COMPLETED": 0},
                   "CRANK": {"WARNING": 0, "CRITICAL": 0, "COMPLETED": 0}}

    # Loop through pending activities and update counts
    for activity in pending_activities:
        location = activity["location"]
        condition = activity["condition"]
        if condition == "WARNING":
            line_counts[location]["WARNING"] += 1
        elif condition == "CRITICAL":
            line_counts[location]["CRITICAL"] += 1

    # Loop through completed activities and update counts
    for activity in history_dict:
        location = activity["location"]  # Only consider location from completed activities
        response_data[0]["COMPLETED"] += 1  # Increment overall completed count
        if location in line_counts:
            line_counts[location]["COMPLETED"] += 1  # Increment completed count for the specific line

    # Update Overall counts
    for line_data in line_counts.values():
        response_data[0]["WARNING"] += line_data["WARNING"]
        response_data[0]["CRITICAL"] += line_data["CRITICAL"]

    # Add line-wise counts to response_data
    for line, counts in line_counts.items():
        response_data.append({"line": line, "WARNING": counts["WARNING"], "CRITICAL": counts["CRITICAL"],
                              "COMPLETED": counts["COMPLETED"]})

    return response_data


# Machine Analytics Start

@db_session
def get_abnormalities_machine_total_count(start_time: datetime, end_time: datetime, machine_name: str):
    """
    Get the count of abnormalities for given machine within a specified time range

    Parameters:
    - start_time (datetime): The start time of the query period.
    - end_time (datetime): The end time of the query period.
    - machine_name (str): The name of the machine.

    Returns:
    - List[Tuple[str, int]]: A list of tuples containing parameter group names and corresponding total abnormalities
    count.
    """
    print(machine_name)
    machines_query = select((pg.group_name, pony_count((rtmp.time, rtmp.machine_parameter)))
                            for m in Machine
                            for mp in MachineParameter
                            for rtmp in RealTimeParameter
                            for condition in ParameterCondition
                            for pg in ParameterGroup
                            if mp.machine == m and
                            mp.parameter_group == pg and
                            rtmp.machine_parameter == mp and
                            rtmp.parameter_condition == condition and
                            rtmp.time > start_time and
                            rtmp.time < end_time and
                            m.name == machine_name and
                            condition.name != 'OK').without_distinct()

    # machines_query = machines_query.group_by(lambda: Machine.name)
    machines_query = machines_query.order_by(lambda pg_name, agg_count: desc(agg_count))

    # Execute the query and retrieve the result
    result = machines_query[:]
    return result


@db_session
def get_abnormalities_machine_warning_count(start_time: datetime, end_time: datetime, machine_name: str):
    """
    Get the count of abnormalities for each machine within a specified time range and parameter group.

    Parameters:
    - start_time (datetime): The start time of the query period.
    - end_time (datetime): The end time of the query period.
    - machine_name (str): The name of the machine.

    Returns:
    - List[Tuple[str, int]]: A list of tuples containing parameter group names and corresponding total warning
    count.
    """
    # Build the query to retrieve abnormalities count for each machine
    # machines_query = select((m, pony_count(m.machine_parameters.real_time_parameters)) for m in Machine if
    #                         m.machine_parameters.real_time_parameters.parameter_condition.name != 'OK')[:5]
    print(machine_name)
    machines_query = select((pg.group_name, pony_count((rtmp.time, rtmp.machine_parameter)))
                            for m in Machine
                            for mp in MachineParameter
                            for rtmp in RealTimeParameter
                            for condition in ParameterCondition
                            for pg in ParameterGroup
                            if mp.machine == m and
                            mp.parameter_group == pg and
                            rtmp.machine_parameter == mp and
                            rtmp.parameter_condition == condition and
                            rtmp.time > start_time and
                            rtmp.time < end_time and
                            m.name == machine_name and
                            condition.name == 'WARNING').without_distinct()

    # machines_query = machines_query.group_by(lambda: Machine.name)

    # machines_query = machines_query.group_by(lambda: Machine.name)
    machines_query = machines_query.order_by(lambda pg_name, agg_count: desc(agg_count))

    # Execute the query and retrieve the result
    result = machines_query[:]
    return result


@db_session
def get_abnormalities_machine_critical_count(start_time: datetime, end_time: datetime, machine_name: str):
    """
    Get the count of abnormalities for each machine within a specified time range and parameter group.

    Parameters:
    - start_time (datetime): The start time of the query period.
    - end_time (datetime): The end time of the query period.
    - machine_name (str): The name of the machine.

    Returns:
    - List[Tuple[str, int]]: A list of tuples containing parameter group names and corresponding total abnormalities
    count.
    """
    # Build the query to retrieve abnormalities count for each machine
    # machines_query = select((m, pony_count(m.machine_parameters.real_time_parameters)) for m in Machine if
    #                         m.machine_parameters.real_time_parameters.parameter_condition.name != 'OK')[:5]

    print(machine_name)
    machines_query = select((pg.group_name, pony_count((rtmp.time, rtmp.machine_parameter)))
                            for m in Machine
                            for mp in MachineParameter
                            for rtmp in RealTimeParameter
                            for condition in ParameterCondition
                            for pg in ParameterGroup
                            if mp.machine == m and
                            mp.parameter_group == pg and
                            rtmp.machine_parameter == mp and
                            rtmp.parameter_condition == condition and
                            rtmp.time > start_time and
                            rtmp.time < end_time and
                            m.name == machine_name and
                            condition.name == 'CRITICAL').without_distinct()

    # machines_query = machines_query.group_by(lambda: Machine.name)

    machines_query = machines_query.order_by(lambda pg_name, agg_count: desc(agg_count))

    # Execute the query and retrieve the result
    result = machines_query[:]
    return result


@db_session
def get_abnormalities_machine_cumulative_counts(start_time: float, end_time: float, machine_name: str):
    """
    Get the count of abnormalities for given parameter group within a specified time range, including total,
    warning, and critical counts.

    Parameters:
    - start_time (float): The start time of the query period.
    - end_time (float): The end time of the query period.
    - machine_name (str): The name of the machine to be queried.

    Returns:
    - List[List[Tuple[str, int]]]: A list of lists containing machine names and corresponding total, warning,
    and critical abnormalities counts.
    """

    start_time_seconds = start_time / 1000
    end_time_seconds = end_time / 1000

    # Converting the epoch format to datetime format (UTC-just like how it is stored in db)
    start_time_datetime = datetime.fromtimestamp(start_time_seconds, timezone.utc)
    end_time_datetime = datetime.fromtimestamp(end_time_seconds, timezone.utc)

    total_query = get_abnormalities_machine_total_count(start_time_datetime, end_time_datetime, machine_name)
    warning_query = get_abnormalities_machine_warning_count(start_time_datetime, end_time_datetime, machine_name)
    critical_query = get_abnormalities_machine_critical_count(start_time_datetime, end_time_datetime, machine_name)

    abnormality_summary = {parameter_group_name[0]: {"total_abnormality": parameter_group_name[1], "warning": 0,
                                                     "critical": 0} for parameter_group_name in total_query}

    for warning in warning_query:
        abnormality_summary[warning[0]]["warning"] = warning[1]

    for critical in critical_query:
        abnormality_summary[critical[0]]["critical"] = critical[1]

    result = []
    for key, value in abnormality_summary.items():
        current_dic = {"parameter_group_name": key}
        current_dic.update(value)
        result.append(current_dic)

    response_data = {"data": result}
    return response_data


# Machine Analytics End


# Parameter Analytics Start


@db_session
def get_abnormalities_parameter_total_count(start_time: datetime, end_time: datetime, parameter_group_name: str):
    """
    Get the count of abnormalities for given parameter group within a specified time range

    Parameters:
    - start_time (datetime): The start time of the query period.
    - end_time (datetime): The end time of the query period.
    - parameter_group_name (str): The name of the parameter group.

    Returns:
    - List[Tuple[str, int]]: A list of tuples containing machine names and corresponding total abnormalities
    count.
    """

    machines_query = select((m.name, pony_count((rtmp.time, rtmp.machine_parameter)))
                            for m in Machine
                            for mp in MachineParameter
                            for rtmp in RealTimeParameter
                            for condition in ParameterCondition
                            for pg in ParameterGroup
                            if mp.machine == m and
                            mp.parameter_group == pg and
                            rtmp.machine_parameter == mp and
                            rtmp.parameter_condition == condition and
                            rtmp.time > start_time and
                            rtmp.time < end_time and
                            pg.group_name == parameter_group_name and
                            condition.name != 'OK').without_distinct()

    # machines_query = machines_query.group_by(lambda: Machine.name)
    machines_query = machines_query.order_by(lambda mc_name, agg_count: desc(agg_count))

    # Execute the query and retrieve the result
    result = machines_query[:]
    return result


@db_session
def get_abnormalities_parameter_warning_count(start_time: datetime, end_time: datetime, parameter_group_name: str):
    """
    Get the count of abnormalities for given parameter group within a specified time range

    Parameters:
    - start_time (datetime): The start time of the query period.
    - end_time (datetime): The end time of the query period.
    - parameter_group_name (str): The name of the parameter group.

    Returns:
    - List[Tuple[str, int]]: A list of tuples containing machine names and corresponding total abnormalities
    count.
    """

    machines_query = select((m.name, pony_count((rtmp.time, rtmp.machine_parameter)))
                            for m in Machine
                            for mp in MachineParameter
                            for rtmp in RealTimeParameter
                            for condition in ParameterCondition
                            for pg in ParameterGroup
                            if mp.machine == m and
                            mp.parameter_group == pg and
                            rtmp.machine_parameter == mp and
                            rtmp.parameter_condition == condition and
                            rtmp.time > start_time and
                            rtmp.time < end_time and
                            pg.group_name == parameter_group_name and
                            condition.name == 'WARNING').without_distinct()

    # machines_query = machines_query.group_by(lambda: Machine.name)
    machines_query = machines_query.order_by(lambda pg_name, agg_count: desc(agg_count))

    # Execute the query and retrieve the result
    result = machines_query[:]
    return result


@db_session
def get_abnormalities_parameter_critical_count(start_time: datetime, end_time: datetime, parameter_group_name: str):
    """
    Get the count of abnormalities for given parameter group within a specified time range

    Parameters:
    - start_time (datetime): The start time of the query period.
    - end_time (datetime): The end time of the query period.
    - parameter_group_name (str): The name of the parameter group.

    Returns:
    - List[Tuple[str, int]]: A list of tuples containing machine names and corresponding total abnormalities
    count.
    """

    machines_query = select((m.name, pony_count((rtmp.time, rtmp.machine_parameter)))
                            for m in Machine
                            for mp in MachineParameter
                            for rtmp in RealTimeParameter
                            for condition in ParameterCondition
                            for pg in ParameterGroup
                            if mp.machine == m and
                            mp.parameter_group == pg and
                            rtmp.machine_parameter == mp and
                            rtmp.parameter_condition == condition and
                            rtmp.time > start_time and
                            rtmp.time < end_time and
                            pg.group_name == parameter_group_name and
                            condition.name == 'CRITICAL').without_distinct()

    # machines_query = machines_query.group_by(lambda: Machine.name)
    machines_query = machines_query.order_by(lambda pg_name, agg_count: desc(agg_count))

    # Execute the query and retrieve the result
    result = machines_query[:]
    return result


@db_session
def get_abnormalities_parameter_cumulative_counts(start_time: float, end_time: float, parameter_group_name: str):
    """
    Get the count of abnormalities for given parameter group within a specified time range, including total,
    warning, and critical counts.

    Parameters:
    - start_time (datetime): The start time of the query period.
    - end_time (datetime): The end time of the query period.
    - parameter_group_name (str): The name of the parameter group.

    Returns:
    - List[List[Tuple[str, int]]]: A list of lists containing machine names and corresponding total, warning,
    and critical abnormalities counts.
    """

    start_time_seconds = start_time / 1000
    end_time_seconds = end_time / 1000

    # Converting the epoch format to datetime format (UTC-just like how it is stored in db)
    start_time_datetime = datetime.fromtimestamp(start_time_seconds, timezone.utc)
    end_time_datetime = datetime.fromtimestamp(end_time_seconds, timezone.utc)

    total_query = get_abnormalities_parameter_total_count(start_time_datetime, end_time_datetime,
                                                          parameter_group_name)
    warning_query = get_abnormalities_parameter_warning_count(start_time_datetime, end_time_datetime,
                                                              parameter_group_name)
    critical_query = get_abnormalities_parameter_critical_count(start_time_datetime, end_time_datetime,
                                                                parameter_group_name)

    abnormality_summary = {machine_query[0]: {"total_abnormality": machine_query[1], "warning": 0,
                                              "critical": 0} for machine_query in total_query}

    for warning in warning_query:
        abnormality_summary[warning[0]]["warning"] = warning[1]

    for critical in critical_query:
        abnormality_summary[critical[0]]["critical"] = critical[1]

    result = []
    for key, value in abnormality_summary.items():
        current_dic = {"machine_name": key}
        current_dic.update(value)
        result.append(current_dic)

    response_data = {"data": result}
    return response_data


# Parameter Group Analytics End


# Maintenance Group Analytics Start

@db_session
def get_maintenance_operators_total_count(start_time: float, end_time: float):
    """
    Get the count of abnormalities handled for each maintenance operators within a specified time range.

    Parameters:
    - start_time (datetime): The start time of the query period.
    - end_time (datetime): The end time of the query period.

    Returns:
    - Dict: A dictionary having data as key and another list as its value. This list has dictionary of operator name
    operator company id and total abnormalities.
    """

    start_time_seconds = start_time / 1000
    end_time_seconds = end_time / 1000

    # Converting the epoch format to datetime format (UTC-just like how it is stored in db)
    start_time_datetime = datetime.fromtimestamp(start_time_seconds, timezone.utc)
    end_time_datetime = datetime.fromtimestamp(end_time_seconds, timezone.utc)

    responsible_person_query = select((ca.responsible_person.username,
                                       ca.responsible_person.company_id,
                                       pony_count(ca.id))
                                      for ca in CorrectiveActivity
                                      if ca.date_of_identification > start_time_datetime and
                                      ca.date_of_identification < end_time_datetime)

    # machines_query = machines_query.group_by(lambda: Machine.name)
    machines_query = responsible_person_query.order_by(lambda person_name, person_company_id,
                                                              agg_count: desc(agg_count))

    # Execute the query and retrieve the result
    result = machines_query[:]
    response = []
    for data in result:
        current_dict = {"operator_name": data[0],
                        "operator_company_id": data[1],
                        "total_abnormality": data[2]}
        response.append(current_dict)

    response = {"data": response}
    return response


@db_session
def get_machines_starting_with_t():
    """
    Get a list of machines whose names start with "T_".

    Returns:
    - dict: A dictionary of data, with list as value.
    """
    machines_query = select(m.name for m in Machine if m.name.startswith('T_')).order_by(lambda name: name)[:]
    if not machines_query:
        machines_query = select(m.name for m in Machine).order_by(lambda name: name)[:]
    response = {"data": list(machines_query)}
    print(response)
    return response


@db_session
def get_parameter_group():
    """
    Get a list of available parameter groups.

    Returns:
    - dict: A dictionary of data, with list as value.
    """

    parameters_query = select(pg.group_name for pg in ParameterGroup).order_by(lambda name: name)[:]
    response = {"data": list(parameters_query)}

    return response


@db_session(optimistic=False)
def get_real_time_parameters_data_by_group(group_name):
    """
    Retrieves real-time parameter data for a specific parameter group.

    Returns a nested JSON structure containing information about the specified
    parameter group, locations, machines, and their respective parameters.

    :param group_name: Name of the parameter group to retrieve information for.
    :type group_name: str

    :return: JSON object representing parameter group data
    :rtype: dict
    """
    # Query the database for relevant data for the specified group
    result = select(
        (m.location,
         m.name,
         mp.name,
         mp.display_name,
         mp.internal_parameter_name,
         rtpa.time,
         rtpa.value,
         mp.warning_limit,
         mp.critical_limit,
         rtpa.parameter_condition.name)

        for rtpa in RealTimeParameterActive
        for mp in MachineParameter
        for pg in ParameterGroup
        for m in Machine
        if (
                rtpa.machine_parameter == mp and
                mp.parameter_group == pg and
                mp.machine == m and
                pg.group_name == group_name
        )
    ).order_by(lambda machine_location, _machine_name,
                      parameter_name, display_name, internal_parameter_name, timestamp, value, warn_limit,
                      _critical_limit, condition_name: (machine_location, _machine_name, parameter_name))

    # Convert the result to a pandas DataFrame
    columns = ['location', 'machine_name', 'parameter_name',
               'display_name', 'internal_parameter_name', 'time', 'value', 'warn_limit',
               'critical_limit', 'condition_name']
    result_df = pd.DataFrame(result, columns=columns)

    group_json = {'group_name': group_name, 'group_details': [], 'group_state': 'OK',
                  'count': {'OK': 0, 'WARNING': 0, 'CRITICAL': 0}}

    # Iterate over unique locations within the parameter group
    for location, location_data in result_df.groupby('location'):
        location_json = {'line_name': location, 'machines': [], 'line_state': 'OK',
                         'count': {'OK': 0, 'WARNING': 0, 'CRITICAL': 0}}
        # Iterate over unique machines within the location
        for machine_name, machine_data in location_data.groupby('machine_name'):
            machine_json = {'machine_name': machine_name, 'parameters': [], 'machine_state': 'OK'}

            # Initialize counts for the machine
            machine_count = {'OK': 0, 'WARNING': 0, 'CRITICAL': 0}

            # Iterate over parameter data for the machine
            for _, row in machine_data.iterrows():
                # Replace NaN values with None
                warning_limit = row['warn_limit'] if not pd.isna(row['warn_limit']) else None
                critical_limit = row['critical_limit'] if not pd.isna(row['critical_limit']) else None
                parameter_value = None if math.isnan(row['value']) else row['value']

                parameter_json = {
                    'actual_parameter_name': row['parameter_name'],
                    'display_name': row['display_name'],
                    'internal_parameter_name': row['internal_parameter_name'],
                    'latest_update_time': int(row['time'].timestamp() * 1000),
                    'parameter_value': parameter_value,
                    'parameter_state': row['condition_name'],
                    'warning_limit': warning_limit,
                    'critical_limit': critical_limit
                }

                machine_json['parameters'].append(parameter_json)

                # Update counts based on parameter state
                if row['condition_name'] == 'OK':
                    machine_count['OK'] += 1
                elif row['condition_name'] == 'WARNING':
                    machine_count['WARNING'] += 1
                elif row['condition_name'] == 'CRITICAL':
                    machine_count['CRITICAL'] += 1

            # Determine machine state and line count based on machine's counts
            if machine_count['CRITICAL'] > 0:
                machine_json['machine_state'] = 'CRITICAL'

                # Increment the location's critical count also
                location_json['count']['CRITICAL'] += 1
            elif machine_count['WARNING'] > 0:
                machine_json['machine_state'] = 'WARNING'

                # Increment the location's warning count also
                location_json['count']['WARNING'] += 1
            else:
                # Increment the location's ok count also
                location_json['count']['OK'] += 1

            location_json['machines'].append(machine_json)

        # Determine line state based on counts
        if location_json['count']['CRITICAL'] > 0:
            location_json['line_state'] = 'CRITICAL'
        elif location_json['count']['WARNING'] > 0:
            location_json['line_state'] = 'WARNING'

        # Update counts for the line state
        group_json['count']['OK'] += location_json['count']['OK']
        group_json['count']['WARNING'] += location_json['count']['WARNING']
        group_json['count']['CRITICAL'] += location_json['count']['CRITICAL']

        group_json['group_details'].append(location_json)

    # Determine group state based on counts
    if group_json['count']['CRITICAL'] > 0:
        group_json['group_state'] = 'CRITICAL'
    elif group_json['count']['WARNING'] > 0:
        group_json['group_state'] = 'WARNING'

    return group_json


@db_session(optimistic=False)
def get_machine_states(group_name):
    """
    Retrieves the current state of all factory machines within a specified parameter
    group using the MT-Linki interface.

    Returns a nested JSON structure containing information about the specified
    parameter group, locations, machines, and their respective parameters.

    :param group_name: Name of the parameter group to retrieve information for.
    :type group_name: str

    :return: JSON object representing parameter group data
    :rtype: dict
    """

    parameter_group = ParameterGroup.get(group_name=group_name)

    # Query the database for relevant data for the specified group
    result = select(
        (m.location,
         m.name,
         mp.name,
         mp.display_name,
         mp.internal_parameter_name,
         rtpa.time,
         rtpa.value,
         mp.warning_limit,
         mp.critical_limit,
         rtpa.parameter_condition.name)

        for rtpa in RealTimeParameterActive
        for mp in MachineParameter
        for pg in ParameterGroup
        for m in Machine
        if (
                rtpa.machine_parameter == mp and
                mp.parameter_group == pg and
                mp.machine == m and
                pg.group_name == group_name
        )
    ).order_by(lambda machine_location, _machine_name,
                      parameter_name, display_name, internal_parameter_name, timestamp, value, warn_limit,
                      _critical_limit, condition_name: (machine_location, _machine_name, parameter_name))

    # Convert the result to a pandas DataFrame
    columns = ['location', 'machine_name', 'parameter_name',
               'display_name', 'internal_parameter_name', 'time', 'value', 'warn_limit',
               'critical_limit', 'condition_name']
    result_df = pd.DataFrame(list(result), columns=columns)

    result_df["time_from_mtlinki"] = result_df["parameter_name"]
    result_df["value_from_mtlinki"] = result_df["parameter_name"]
    result_df["condition_from_mtlinki"] = "OK"

    collection = get_mongo_collection(collection="L1Signal_Pool_Active")

    machine_state_mtlinki = collection.aggregate(
        get_machine_states_mtlinki(regex_pattern=parameter_group.mongodb_query))

    machine_state_mtlinki = list(machine_state_mtlinki)

    time_from_mtlinki_map = {data["signalname"]: data["updatedate"] for data in machine_state_mtlinki}
    value_from_mtlinki_map = {data["signalname"]: data["value"] for data in machine_state_mtlinki}

    result_df["time_from_mtlinki"] = result_df["time_from_mtlinki"].map(time_from_mtlinki_map)
    result_df["value_from_mtlinki"] = result_df["value_from_mtlinki"].map(value_from_mtlinki_map)

    if parameter_group.parameter_type == "decreasing":

        # If the parameter type is decreasing, we do the following

        # Map all the values in column "condition" to 1, if the corresponding value in column "value"
        # Is greater than the warning limit, if it is less than warning but greater than critical
        # We set it to 2, if less than critical limit, we set it to 3
        # self.recent_data["condition"].
        # mask(self.recent_data["value"] > self.warning_limit, 1, inplace=True)
        # self.recent_data["condition"].
        # mask(self.recent_data["value"] < self.warning_limit - 1, 2, inplace=True)
        # self.recent_data["condition"].
        # mask(self.recent_data["value"] < self.critical_limit - 1, 3, inplace=True)
        result_df["condition_from_mtlinki"] = np.where(
            (result_df["value_from_mtlinki"] <= result_df["critical_limit"]),
            "CRITICAL", result_df["condition_from_mtlinki"])

        result_df["condition_from_mtlinki"] = np.where(
            (result_df["value_from_mtlinki"] <= result_df["warn_limit"]) &
            (result_df["value_from_mtlinki"] > result_df["critical_limit"]),
            "WARNING", result_df["condition_from_mtlinki"])

    elif parameter_group.parameter_type == "increasing":

        # If parameter is of type increasing do the following

        # Map all the values in column "condition" to 1, if the corresponding value in column "value"
        # Is less than the warning limit, if it is greater than warning but less than critical
        # # We set it to 2, if greater than critical limit, we set it to 3
        # self.recent_data["condition"].
        # mask(self.recent_data["value"] < self.warning_limit, 1, inplace=True)
        # self.recent_data["condition"].
        # mask(self.recent_data["value"] > self.warning_limit - 1, 2, inplace=True)
        # self.recent_data["condition"].
        # mask(self.recent_data["value"] > self.critical_limit - 1, 3, inplace=True)

        result_df["condition_from_mtlinki"] = np.where(
            (result_df["value_from_mtlinki"] >= result_df["critical_limit"]),
            "CRITICAL", result_df["condition_from_mtlinki"])

        result_df["condition_from_mtlinki"] = np.where(
            (result_df["value_from_mtlinki"] >= result_df["warn_limit"]) &
            (result_df["value_from_mtlinki"] < result_df["critical_limit"]),
            "WARNING", result_df["condition_from_mtlinki"])

    elif parameter_group.parameter_type == "bool":

        # If parameter is of type boolean, do the following

        # We map all the true values to 1, and false to 0 in the "value" column
        # Since in Timescaledb we cannot have mixed value type in a column, hence we're converting it from
        # Boolean to float
        result_df["value_from_mtlinki"] = result_df["value_from_mtlinki"].map({True: 1, False: 0})

        # Mapping all 1 to 3 (True to 3, critical condition, such in "ApcBatLow_0_path1_T_B_OP160"
        # Where true denotes battery is low), and 0 to 1 (False to 1 - OK condition)
        result_df["condition_from_mtlinki"].mask(result_df["value_from_mtlinki"] == 1, 3, inplace=True)
        result_df["condition_from_mtlinki"].mask(result_df["value_from_mtlinki"] == 0, 1, inplace=True)

    result_df['condition_from_mtlinki'] = np.where(result_df['value_from_mtlinki'].isnull() |
                                                   np.isnan(result_df['value_from_mtlinki']),
                                                   'DISCONNECTED', result_df['condition_from_mtlinki'])

    # TODO : The code till above line, collected two data from mtlinki for the current parameter group
    # TODO: The updatetime and value, and based on those values it calculates the condition
    # TODO: The new and latest_condition is in the column condition_from_mtlinki and the value is
    # TODO: in the column value_from_mtlinki and the condition_from_mtlinki has new value called as DISCONNECTED
    # TODO: Based on the above changes, modify the remaining code, such that it gets the count for "DISCONNETED" state
    # TODO: Also, and the calculations are based on  row['value_from_mtlinki'] instead of row['value']
    # TODO: row['condition_name'] do with row['condition_from_mtlinki']]
    # TODO: row['time'] should be replaced with row['time_from_mtlinki']
    # TODO: Maybe i missed few, run this file, from main_test in debug mode, and see how data is
    # TODO: filled based on that modify others

    group_json = {'group_name': group_name, 'group_details': [], 'group_state': 'OK',
                  'count': {'OK': 0, 'WARNING': 0, 'CRITICAL': 0}}

    # Iterate over unique locations within the parameter group
    for location, location_data in result_df.groupby('location'):
        location_json = {'line_name': location, 'machines': [], 'line_state': 'OK',
                         'count': {'OK': 0, 'WARNING': 0, 'CRITICAL': 0}}
        # Iterate over unique machines within the location
        for machine_name, machine_data in location_data.groupby('machine_name'):
            machine_json = {'machine_name': machine_name, 'parameters': [], 'machine_state': 'OK'}

            # Initialize counts for the machine
            machine_count = {'OK': 0, 'WARNING': 0, 'CRITICAL': 0}

            # Iterate over parameter data for the machine
            for _, row in machine_data.iterrows():
                # Replace NaN values with None
                warning_limit = row['warn_limit'] if not pd.isna(row['warn_limit']) else None
                critical_limit = row['critical_limit'] if not pd.isna(row['critical_limit']) else None
                parameter_value = None if math.isnan(row['value']) else row['value']

                parameter_json = {
                    'actual_parameter_name': row['parameter_name'],
                    'display_name': row['display_name'],
                    'internal_parameter_name': row['internal_parameter_name'],
                    'latest_update_time': int(row['time'].timestamp() * 1000),
                    'parameter_value': parameter_value,
                    'parameter_state': row['condition_name'],
                    'warning_limit': warning_limit,
                    'critical_limit': critical_limit
                }

                machine_json['parameters'].append(parameter_json)

                # Update counts based on parameter state
                if row['condition_name'] == 'OK':
                    machine_count['OK'] += 1
                elif row['condition_name'] == 'WARNING':
                    machine_count['WARNING'] += 1
                elif row['condition_name'] == 'CRITICAL':
                    machine_count['CRITICAL'] += 1

            # Determine machine state and line count based on machine's counts
            if machine_count['CRITICAL'] > 0:
                machine_json['machine_state'] = 'CRITICAL'

                # Increment the location's critical count also
                location_json['count']['CRITICAL'] += 1
            elif machine_count['WARNING'] > 0:
                machine_json['machine_state'] = 'WARNING'

                # Increment the location's warning count also
                location_json['count']['WARNING'] += 1
            else:
                # Increment the location's ok count also
                location_json['count']['OK'] += 1

            location_json['machines'].append(machine_json)

        # Determine line state based on counts
        if location_json['count']['CRITICAL'] > 0:
            location_json['line_state'] = 'CRITICAL'
        elif location_json['count']['WARNING'] > 0:
            location_json['line_state'] = 'WARNING'

        # Update counts for the line state
        group_json['count']['OK'] += location_json['count']['OK']
        group_json['count']['WARNING'] += location_json['count']['WARNING']
        group_json['count']['CRITICAL'] += location_json['count']['CRITICAL']

        group_json['group_details'].append(location_json)

    # Determine group state based on counts
    if group_json['count']['CRITICAL'] > 0:
        group_json['group_state'] = 'CRITICAL'
    elif group_json['count']['WARNING'] > 0:
        group_json['group_state'] = 'WARNING'

    return group_json


#Changes made to get the data from the mtlinki for the parameter group
@db_session(optimistic=False)
def get_machine_states_2(group_name):
    """
    Retrieves the current state of all factory machines within a specified parameter
    group using the MT-Linki interface.

    Returns a nested JSON structure containing information about the specified
    parameter group, locations, machines, and their respective parameters.

    :param group_name: Name of the parameter group to retrieve information for.
    :type group_name: str

    :return: JSON object representing parameter group data
    :rtype: dict
    """

    parameter_group = ParameterGroup.get(group_name=group_name)

    # Query the database for relevant data for the specified group
    result = select(
        (m.location,
         m.name,
         mp.name,
         mp.display_name,
         mp.internal_parameter_name,
         rtpa.time,
         rtpa.value,
         mp.warning_limit,
         mp.critical_limit,
         rtpa.parameter_condition.name)

        for rtpa in RealTimeParameterActive
        for mp in MachineParameter
        for pg in ParameterGroup
        for m in Machine
        if (
                rtpa.machine_parameter == mp and
                mp.parameter_group == pg and
                mp.machine == m and
                pg.group_name == group_name
        )
    ).order_by(lambda machine_location, _machine_name,
                      parameter_name, display_name, internal_parameter_name, timestamp, value, warn_limit,
                      _critical_limit, condition_name: (machine_location, _machine_name, parameter_name))

    # Convert the result to a pandas DataFrame
    columns = ['location', 'machine_name', 'parameter_name',
               'display_name', 'internal_parameter_name', 'time', 'value', 'warn_limit',
               'critical_limit', 'condition_name']
    result_df = pd.DataFrame(list(result), columns=columns)
    result_df = result_df.sort_values(by='machine_name', key=lambda col: col.map(alphanumeric_key))

    result_df["time_from_mtlinki"] = result_df["parameter_name"]
    result_df["value_from_mtlinki"] = result_df["parameter_name"]
    result_df["condition_from_mtlinki"] = "OK"

    collection = get_mongo_collection(collection="L1Signal_Pool_Active")

    machine_state_mtlinki = collection.aggregate(
        get_machine_states_mtlinki(regex_pattern=parameter_group.mongodb_query))

    machine_state_mtlinki = list(machine_state_mtlinki)

    time_from_mtlinki_map = {data["signalname"]: data["updatedate"] for data in machine_state_mtlinki}
    value_from_mtlinki_map = {data["signalname"]: data["value"] for data in machine_state_mtlinki}

    result_df["time_from_mtlinki"] = result_df["time_from_mtlinki"].map(time_from_mtlinki_map)
    result_df["value_from_mtlinki"] = result_df["value_from_mtlinki"].map(value_from_mtlinki_map)

    if parameter_group.parameter_type == "decreasing":
        result_df["condition_from_mtlinki"] = np.where(
            (result_df["value_from_mtlinki"] <= result_df["critical_limit"]),
            "CRITICAL", result_df["condition_from_mtlinki"])

        result_df["condition_from_mtlinki"] = np.where(
            (result_df["value_from_mtlinki"] <= result_df["warn_limit"]) &
            (result_df["value_from_mtlinki"] > result_df["critical_limit"]),
            "WARNING", result_df["condition_from_mtlinki"])

    elif parameter_group.parameter_type == "increasing":
        result_df["condition_from_mtlinki"] = np.where(
            (result_df["value_from_mtlinki"] >= result_df["critical_limit"]),
            "CRITICAL", result_df["condition_from_mtlinki"])

        result_df["condition_from_mtlinki"] = np.where(
            (result_df["value_from_mtlinki"] >= result_df["warn_limit"]) &
            (result_df["value_from_mtlinki"] < result_df["critical_limit"]),
            "WARNING", result_df["condition_from_mtlinki"])

    elif parameter_group.parameter_type == "bool":
        result_df["value_from_mtlinki"] = result_df["value_from_mtlinki"].map({True: 1, False: 0})
        #TODO CHANGED THE VALUE FOR THE BOOLIEAN TO SHOW "OK,CRITICAL"
        # result_df["condition_from_mtlinki"].mask(result_df["value_from_mtlinki"] == 1, 3, inplace=True)
        # result_df["condition_from_mtlinki"].mask(result_df["value_from_mtlinki"] == 0, 1, inplace=True)

    result_df['condition_from_mtlinki'] = np.where(result_df['value_from_mtlinki'].isnull() |
                                                   np.isnan(result_df['value_from_mtlinki']),
                                                   'DISCONNECTED', result_df['condition_from_mtlinki'])

    group_json = {'group_name': group_name, 'group_details': [], 'group_state': 'OK',
                  'count': {'OK': 0, 'WARNING': 0, 'CRITICAL': 0, 'DISCONNECTED': 0}}  # Added 'DISCONNECTED' count

    # Iterate over unique locations within the parameter group
    for location, location_data in result_df.groupby('location'):
        location_json = {'line_name': location, 'machines': [], 'line_state': 'OK',
                         'count': {'OK': 0, 'WARNING': 0, 'CRITICAL': 0,
                                   'DISCONNECTED': 0}}  # Added 'DISCONNECTED' count

        # Iterate over unique machines within the location
        for machine_name, machine_data in location_data.groupby('machine_name', sort=False):
            machine_json = {'machine_name': machine_name, 'parameters': [], 'machine_state': 'OK'}

            # Initialize counts for the machine
            machine_count = {'OK': 0, 'WARNING': 0, 'CRITICAL': 0, 'DISCONNECTED': 0}  # Added 'DISCONNECTED' count

            # Iterate over parameter data for the machine
            for _, row in machine_data.iterrows():
                # Replace NaN values with None
                warning_limit = row['warn_limit'] if not pd.isna(row['warn_limit']) else None
                critical_limit = row['critical_limit'] if not pd.isna(row['critical_limit']) else None
                parameter_value = None if pd.isna(row['value_from_mtlinki']) else row[
                    'value_from_mtlinki']  # Changed to value_from_mtlinki
                # Changed 'value' to 'value_from_mtlinki' in the above line

                # Handle NaT values in time_from_mtlinki column
                if pd.isna(row['time_from_mtlinki']):
                    latest_update_time = 0  # or assign a default timestamp value
                else:
                    latest_update_time = int(
                        row['time_from_mtlinki'].timestamp() * 1000)  # Changed to time_from_mtlinki

                parameter_json = {
                    'actual_parameter_name': row['parameter_name'],
                    'display_name': row['display_name'],
                    'internal_parameter_name': row['internal_parameter_name'],
                    'latest_update_time': latest_update_time,
                    'parameter_value': parameter_value,
                    'parameter_state': row['condition_from_mtlinki'],  # Changed to condition_from_mtlinki
                    'warning_limit': warning_limit,
                    'critical_limit': critical_limit
                }

                machine_json['parameters'].append(parameter_json)

                # Update counts based on parameter state
                if row['condition_from_mtlinki'] == 'OK':  # Changed to condition_from_mtlinki
                    machine_count['OK'] += 1
                elif row['condition_from_mtlinki'] == 'WARNING':  # Changed to condition_from_mtlinki
                    machine_count['WARNING'] += 1
                elif row['condition_from_mtlinki'] == 'CRITICAL':  # Changed to condition_from_mtlinki
                    machine_count['CRITICAL'] += 1
                elif row['condition_from_mtlinki'] == 'DISCONNECTED':  # Added count for 'DISCONNECTED'
                    machine_count['DISCONNECTED'] += 1

            # Determine machine state and line count based on machine's counts
            if machine_count['DISCONNECTED'] == len(machine_json['parameters']):
                machine_json[
                    'machine_state'] = 'DISCONNECTED'  # Set machine_state to 'DISCONNECTED' if all parameters are disconnected
                location_json['count'][
                    'DISCONNECTED'] += 1  # Increment count of machines with all parameters disconnected
            elif machine_count['CRITICAL'] > 0:
                machine_json['machine_state'] = 'CRITICAL'
                location_json['count']['CRITICAL'] += 1
            elif machine_count['WARNING'] > 0:
                machine_json['machine_state'] = 'WARNING'
                location_json['count']['WARNING'] += 1
            else:
                location_json['count']['OK'] += 1

            location_json['machines'].append(machine_json)

        # Determine line state based on counts
        if location_json['count']['CRITICAL'] > 0:
            location_json['line_state'] = 'CRITICAL'
        elif location_json['count']['WARNING'] > 0:
            location_json['line_state'] = 'WARNING'

        group_json['count']['OK'] += location_json['count']['OK']
        group_json['count']['WARNING'] += location_json['count']['WARNING']
        group_json['count']['CRITICAL'] += location_json['count']['CRITICAL']
        group_json['count']['DISCONNECTED'] += location_json['count']['DISCONNECTED']  # Added count for 'DISCONNECTED'

        # Log count for 'DISCONNECTED' state
        LOGGER.info(
            f"+++++++++++++++++++++++++Count for DISCONNECTED at location {location}: {location_json['count']['DISCONNECTED']}")

        group_json['group_details'].append(location_json)

    # Determine group state based on counts
    if group_json['count']['CRITICAL'] > 0:
        group_json['group_state'] = 'CRITICAL'
    elif group_json['count']['WARNING'] > 0:
        group_json['group_state'] = 'WARNING'

    return group_json




@db_session(optimistic=False)
def get_current_machine_data(parameter_group_id=5):
    """

    Retrieves the current machine details from the database

    :param parameter_group_id: The parameter group identifier
    :type parameter_group_id: int

    :return: The current machine details
    :rtype: dict

    """

    try:
        # Selecting the given parameter_group_id
        parameter_group = ParameterGroup[parameter_group_id]

        response_data = {"param_actual_name": parameter_group.group_name, "param": parameter_group.id, "machines": [],
                         "params_group_status": []}

        LOGGER.info("Retrieving current machine details")

        # response_data["machines"] = get_parameter_group_status(parameter_group)
        response_data["machines"] = get_parameter_group_status_active(parameter_group.id)

        # Commenting out to test the new function to get the all the parameter group status
        # response_data["params_group_status"] = get_all_parameter_group_status()

        response_data["params_group_status"] = get_all_parameter_group_status_active()

        return response_data
    except ObjectNotFound as error:
        LOGGER.error(f"The given parameter group id is not available: {error.args[0]}")
        raise NoParameterGroupError


@db_session(optimistic=False)
def get_parameter_group_status(parameter_group):
    """

    Function to get the parameter group status for given parameter group id

    :param parameter_group: The parameter group object
    :type parameter_group: ParameterGroup

    :return: List of machines and their parameter status
    :rtype: list

    """

    try:
        start_time = time.time()

        parameter_status = []

        # Selecting all the machines available in the database
        # machines = Machine.select(lambda current_machine: current_machine.id > 1)
        machines = Machine.select(lambda current_machine: current_machine.id not in (1, 60))

        # For all the machines, we do the following
        for machine in machines:
            # The current machine's data are
            current_machine_data = {"name": machine.name, "axes": []}

            # Query to get all the axes for the current machine
            axes = MachineParameter.select(lambda parameter: parameter.machine.id == machine.id)
            axes = axes.filter(lambda parameter: parameter.parameter_group.id == parameter_group.id). \
                order_by(MachineParameter.name)

            axes = list(axes)

            # For each axis
            for count, axis in enumerate(axes):

                if (parameter_group.id != 15) and (parameter_group.id != 16):
                    axis_count = count
                else:
                    if count == 0:
                        continue
                    else:
                        axis_count = count - 1

                # Set the base current axis data, as per the response model
                current_axis_data = {"name": axis_count, "actual_name": axis.name}

                # Get the real time parameter, equal to the current axis
                current_value_base_query = RealTimeParameter. \
                    select(lambda parameter: parameter.machine_parameter.id == axis.id)

                current_value = list(current_value_base_query.
                                     order_by(desc(RealTimeParameter.time)).for_update()[:1])

                if not current_value:

                    # If in case this is the "RADIATOR_FAN1_SERVO_SPINDLE_AMPLIFIER" group, then
                    # We need to check the first parameter (spindle parameter)
                    if (parameter_group.id == 15) or (parameter_group.id == 16):

                        # Set the base current axis data, as per the response model
                        current_axis_data = {"name": axis_count, "actual_name": axes[0].name}

                        # Get the real time parameter, equal to the current axis
                        current_value_base_query = RealTimeParameter. \
                            select(lambda parameter: parameter.machine_parameter.id == axes[0].id)

                        current_value = list(current_value_base_query.
                                             order_by(desc(RealTimeParameter.time)).for_update()[:1])

                        if not current_value:
                            # If there is no data for the spindle parameter for current machine, we break
                            # This will be the case only for testing, in actual you will have data
                            break

                        current_value = current_value[0]

                        if current_value.parameter_condition.id == 1:
                            # If the condition is OK, we skip the remaining code
                            break

                        # Set the current data axis data keys
                        current_axis_data["value"] = current_value.value
                        current_axis_data["status"] = current_value.parameter_condition.id
                        current_axis_data["last_update_time"] = current_value.time.timestamp()

                        # Append to the current machine details
                        current_machine_data["axes"].append(current_axis_data)

                    # If the data is not available it means we we were accessing an axis data for which data is
                    # Is not available, then we will skip remaining of the code since they are not configured
                    break

                current_value = current_value[0]

                if current_value.parameter_condition.id == 1:
                    # If the condition is OK, we skip the remaining code
                    continue

                # # Filter only non_ok data current_value = current_value_base_query.filter(lambda parameter:
                # parameter.parameter_condition.id > 1)
                #
                # # Sort by time (descending order) and limit to 1 (which gives the recent most data)
                # # Making it for update query, so that we don't get the Unrepeatable Read Problem
                # current_value = current_value.order_by(desc(RealTimeParameter.time)).for_update()[:1]

                # Set the current data axis data keys
                current_axis_data["value"] = current_value.value
                current_axis_data["status"] = current_value.parameter_condition.id
                current_axis_data["last_update_time"] = current_value.time.timestamp()

                # Append to the current machine details
                current_machine_data["axes"].append(current_axis_data)

            if current_machine_data["axes"]:

                # Since this machine had a non_ok data, we initially set the status to 2 (warning)
                current_machine_data["status"] = 2

                # loop through all the machine's axis data
                for axis in current_machine_data["axes"]:
                    # If the status of the axis is 3
                    if axis["status"] == 3:
                        # Set the machine status to 3 and break from the loop
                        current_machine_data["status"] = 3
                        break
                # If any parameter(axes) was there with non_ok data, append it to all parameter_status list
                parameter_status.append(current_machine_data)

        end_time = time.time() - start_time
        LOGGER.info(f"Time for individual parameter group: {end_time * 1000} ms")

        return parameter_status
    except Exception as error:
        LOGGER.exception(f"Exception while processing status of machine for given parameter group: {error.args[0]}")
        raise GetParamGroupDBError


@db_session(optimistic=False)
def get_parameter_group_status_active(parameter_group):
    """

    Function to get the parameter group status for given parameter group id from real time active table

    :param parameter_group: The parameter group object
    :type parameter_group: int

    :return: Dictionary of machines and their parameter status
    :rtype: dict

    """

    try:
        start_time = time.time()

        real_time_active_abnormal = RealTimeParameterActive.select(lambda parameter: parameter.parameter_condition.id
                                                                                     > 1)

        real_time_active_abnormal = real_time_active_abnormal.filter(lambda parameter:
                                                                     parameter.machine_parameter.parameter_group.id
                                                                     == parameter_group)
        real_time_active_abnormal = list(real_time_active_abnormal)

        all_machine_data = {}

        for real_parameter in real_time_active_abnormal:

            machine_name = real_parameter.machine_parameter.machine.name
            current_data = {"name": 0,
                            "actual_name": real_parameter.machine_parameter.name,
                            "value": real_parameter.value,
                            "status": real_parameter.parameter_condition.id,
                            "last_update_time": real_parameter.time.timestamp()}

            list_of_machine_parameters = MachineParameter.select(lambda parameter: parameter.machine.name
                                                                                   == machine_name)

            list_of_machine_parameters = list_of_machine_parameters.filter(lambda parameter:
                                                                           parameter.parameter_group.id
                                                                           == parameter_group). \
                order_by(MachineParameter.name)

            list_of_machine_parameters = [mc_para.id for mc_para in list_of_machine_parameters]

            if (parameter_group != 15) and (parameter_group != 16):
                axis_id = list_of_machine_parameters.index(real_parameter.machine_parameter.id)
            else:
                axis_id = list_of_machine_parameters.index(real_parameter.machine_parameter.id)
                if axis_id == 0:
                    axis_id = len(list_of_machine_parameters) - 1
                else:
                    axis_id = axis_id - 1

            current_data["name"] = axis_id

            if not machine_name in all_machine_data:
                all_machine_data[machine_name] = {"axes": []}

            all_machine_data[machine_name]["axes"].append(current_data)

        if all_machine_data:

            for current_machine_data in all_machine_data:

                if all_machine_data[current_machine_data]["axes"]:

                    # Since this machine had a non_ok data, we initially set the status to 2 (warning)
                    all_machine_data[current_machine_data]["status"] = 2

                    # loop through all the machine's axis data
                    for axis in all_machine_data[current_machine_data]["axes"]:
                        # If the status of the axis is 3
                        if axis["status"] == 3:
                            # Set the machine status to 3 and break from the loop
                            all_machine_data[current_machine_data]["status"] = 3
                            break

        response_data = []

        if all_machine_data:

            for key, value in all_machine_data.items():
                current_data = {"name": key,
                                "status": value["status"],
                                "axes": value["axes"]}

                response_data.append(current_data)

        end_time = time.time() - start_time

        LOGGER.info(f"Time for individual parameter group: {(round((end_time * 1000), 2))} ms")

        print(response_data)

        return response_data
    except Exception as error:
        LOGGER.exception(f"Exception while processing status of machine for given parameter group: {error.args[0]}")
        raise GetParamGroupDBError


@db_session(optimistic=False)
def get_all_parameter_group_status():
    """

    Function used to return status of all parameter group

    :return: Status of all parameter groups
    :rtype: list

    """

    try:
        start_time = time.time()

        status = [1 for _ in range(17)]
        query_template = get_all_status_templates()

        # Using a really complicated group by function along with timescale db inbuilt function
        # To get the total number of warning and critical parameters
        warning_data = list(PONY_DATABASE.select(query_template.format(condition_holder=2)))
        critical_data = list(PONY_DATABASE.select(query_template.format(condition_holder=3)))
        # If we have any parameter in warning state, we do the following
        if warning_data:
            # For all the warning parameter
            for data in warning_data:
                # The first value of the list given the parameter group id from the actual table
                # Hence APC Battery would be 1, but in the status list the index would be 0
                # Hence we need to subtract 1 from it
                status[data[0] - 1] = 2

        if critical_data:
            for data in critical_data:
                # The first value of the list given the parameter group id from the actual table
                # Hence APC Battery would be 1, but in the status list the index would be 0
                # Hence we need to subtract 1 from it
                status[data[0] - 1] = 3

        LOGGER.info("time for all status")
        print("time for all status")
        LOGGER.info(time.time() - start_time)
        print(time.time() - start_time)
        print(status)

        return status
    except Exception as error:
        LOGGER.exception(f"Exception while processing status of machine for given parameter group: {error.args[0]}")
        raise GetAllParameterDBError


@db_session(optimistic=False)
def get_parameter_group_statuses():
    """
    Retrieves the statuses of all parameter groups based on real-time parameters.

    :return: List of dictionaries containing parameter group statuses.
    :rtype: list[dict]
    """

    try:
        start_time = time.time()

        status_list = []

        # Using a complicated group by function along with timescale db inbuilt function
        # To get the total number of warning and critical parameters
        warning_data = list(select((rpa.machine_parameter.parameter_group.group_name, pony_count())
                                   for rpa in RealTimeParameterActive
                                   if rpa.parameter_condition.name == "WARNING" and
                                   rpa.machine_parameter.parameter_group is not None))

        critical_data = list(select((rpa.machine_parameter.parameter_group.group_name, pony_count())
                                    for rpa in RealTimeParameterActive
                                    if rpa.parameter_condition.name == "CRITICAL" and
                                    rpa.machine_parameter.parameter_group is not None))

        # If we have any parameter in critical state, we do the following
        if critical_data:
            for data in critical_data:
                status_list.append({'item_name': data[0], 'item_state': 'CRITICAL'})

        # If we have any parameter in warning state, we do the following only if it was not added in the critical state
        if warning_data:
            for data in warning_data:
                if not any(item['item_name'] == data[0] for item in status_list):
                    status_list.append({'item_name': data[0], 'item_state': 'WARNING'})

        # If no warnings or critical issues, mark as OK
        for group_name in select(pg.group_name for pg in ParameterGroup):
            if not any(item['item_name'] == group_name for item in status_list):
                status_list.append({'item_name': group_name, 'item_state': 'OK'})

        end_time = time.time() - start_time
        LOGGER.info(f"Time for all status: {(round((end_time * 1000), 2))} ms")

        # Sorting the list based on the value of 'key1'
        status_list = sorted(status_list, key=lambda group: group['item_name'])

        return status_list

    except Exception as error:
        LOGGER.exception(f"Exception while processing status of machine for given parameter group: {error.args[0]}")
        raise GetAllParameterDBError


@db_session(optimistic=False)
def get_all_parameter_group_status_active():
    """

    Function used to return status of all parameter group using the real time parameters active table

    :return: Status of all parameter groups
    :rtype: list

    """

    try:
        start_time = time.time()

        status = [1 for _ in range(17)]

        print("ONE")
        # Using a really complicated group by function along with timescale db inbuilt function
        # To get the total number of warning and critical parameters
        warning_data = list(select((rpa.machine_parameter.parameter_group.id, pony_count())
                                   for rpa in RealTimeParameterActive if rpa.parameter_condition.id == 2 and
                                   rpa.machine_parameter.parameter_group is not None))

        critical_data = list(select((rpa.machine_parameter.parameter_group.id, pony_count())
                                    for rpa in RealTimeParameterActive if rpa.parameter_condition.id == 3 and
                                    rpa.machine_parameter.parameter_group is not None))

        # If we have any parameter in warning state, we do the following
        if warning_data:
            # For all the warning parameter
            for data in warning_data:
                # The first value of the list given the parameter group id from the actual table
                # Hence APC Battery would be 1, but in the status list the index would be 0
                # Hence we need to subtract 1 from it
                status[data[0] - 1] = 2

        if critical_data:
            for data in critical_data:
                # The first value of the list given the parameter group id from the actual table
                # Hence APC Battery would be 1, but in the status list the index would be 0
                # Hence we need to subtract 1 from it
                status[data[0] - 1] = 3

        end_time = time.time() - start_time
        LOGGER.info(f"Time for all status: {(round((end_time * 1000), 2))} ms")
        print(f"Time for all status: {(round((end_time * 1000), 2))} ms")

        print(status)

        return status

    except Exception as error:
        LOGGER.exception(f"Exception while processing status of machine for given parameter group: {error.args[0]}")
        raise GetAllParameterDBError


@db_session(optimistic=False)
def get_all_machine_spm_status_active():
    """

    Function used to return status of all parameter group using the real time parameters active table

    :return: Status of all parameter groups
    :rtype: list

    """

    try:
        start_time = time.time()

        status = [1 for _ in range(5)]

        # spm_machine_ids = [1, 61, 63, 64]
        spm_machine_ids = [1, 61, 62, 63]
        # spm_machine_ids_keys = {1: 0, 61: 1, 63: 2, 64: 3}
        spm_machine_ids_keys = {1: 0, 61: 2, 3: 2, 63: 4, 64: 1}

        print("ONE")
        # Using a really complicated group by function along with timescale db inbuilt function
        # To get the total number of warning and critical parameters
        warning_data = list(select((rpa.machine_parameter.machine.id, pony_count())
                                   for rpa in RealTimeParameterActive if rpa.parameter_condition.id == 2 and
                                   rpa.machine_parameter.machine.id in spm_machine_ids))

        critical_data = list(select((rpa.machine_parameter.machine.id, pony_count())
                                    for rpa in RealTimeParameterActive if rpa.parameter_condition.id == 3 and
                                    rpa.machine_parameter.machine.id in spm_machine_ids))

        # If we have any parameter in warning state, we do the following
        if warning_data:
            # For all the warning parameter
            for data in warning_data:
                # The first value of the list given the parameter group id from the actual table
                # Hence APC Battery would be 1, but in the status list the index would be 0
                # Hence we need to subtract 1 from it
                spm_status_list_id = spm_machine_ids_keys[data[0]]
                status[spm_status_list_id] = 2

        if critical_data:
            for data in critical_data:
                # The first value of the list given the parameter group id from the actual table
                # Hence APC Battery would be 1, but in the status list the index would be 0
                # Hence we need to subtract 1 from it
                spm_status_list_id = spm_machine_ids_keys[data[0]]
                status[spm_status_list_id] = 3

        end_time = time.time() - start_time
        LOGGER.info(f"Time for all status: {end_time * 1000} ms")
        print(f"Time for all status: {end_time * 1000} ms")

        print(status)
        LOGGER.info(status)

        return {"spm_machine_status": status}

    except Exception as error:
        LOGGER.exception(f"Exception while processing status of machine for given parameter group: {error.args[0]}")
        raise GetAllParameterDBError


@db_session(optimistic=False)
def get_machine_timeline_parameter_name(parameter_name, start_time=1655859600, end_time=1655874000):
    """

    Retrieves the current machine's given parameter group and axis's full timeline information for given
    start and end time

    :param parameter_name: The machine name whose data is required
    :type parameter_name: str

    :param start_time: Start time for which the data needs to be queried in epoch format
    :type start_time: float

    :param end_time: End time for which the data needs to be queried in epoch format
    :type end_time: float

    :return: The current machine's full timeline information
    :rtype: dict

    """

    try:

        # Get the actual parameter name
        requested_parameter = MachineParameter.select(lambda mp: mp.name == parameter_name)[:][0]

        real_time_data_active = RealTimeParameterActive.select(lambda parameter: parameter.machine_parameter.id
                                                                                 == requested_parameter.id)
        if not list(real_time_data_active):
            LOGGER.info(f"Data not available for {requested_parameter.name}")

        # Getting real time data
        real_time_data = get_realtime_machine_parameter_data(requested_parameter.id, start_time, end_time)

        # We get the timestamp of the recent most recorded value of the requested parameter id
        recent_value_before_start = get_realtime_machine_parameter_data_before_requested_time(
            requested_parameter.id, start_time)

        if math.isnan(recent_value_before_start):
            recent_value_before_start = None

        LOGGER.info(real_time_data)
        # The following is simulated data
        real_time_data.insert(0, [start_time, recent_value_before_start])
        LOGGER.info("test")
        LOGGER.info(real_time_data)
        real_time_data.append([end_time, real_time_data[-1][1]])
        LOGGER.info(real_time_data)

        # Do the following only if real time data is available (either for the requested timestamp or
        # The timestamp of recent most value and one hour before it)
        if real_time_data:
            # Creating response dictionary
            # If warning limit is none, it means it is a dynamic parameter ,
            # And we set the limits to zero for them
            if (requested_parameter.warning_limit is not None) and \
                    not math.isnan(requested_parameter.warning_limit):

                response_data = {"parameter_name": parameter_name,
                                 "chart_data": real_time_data,
                                 "warning_limit": requested_parameter.warning_limit,
                                 "critical_limit": requested_parameter.critical_limit}
            else:

                response_data = {"parameter_name": parameter_name,
                                 "chart_data": real_time_data,
                                 "warning_limit": 0,
                                 "critical_limit": 0}

            unit = requested_parameter.unit.short_name
            response_data["legend_data"] = {"x_axis_label": "Timestamp",
                                            "y_axis_label": parameter_name,
                                            "x_axis_units": "DateTime",
                                            "y_axis_units": unit}
            return response_data

    except ObjectNotFound as error:
        LOGGER.error(f"The object not found in database: {error.args[0]}")
        raise GetMachineTimelineError
    except Exception as error:
        LOGGER.error(f"The issues with database: {error.args[0]}")
        raise GetMachineTimelineError(error.args[0])


@db_session(optimistic=False)
def get_machine_timeline_parameter_name_mtlinki(machine_name, parameter_name, start_time=1655859600,
                                                end_time=1655874000):
    """

    Retrieves the realtime data for the given parameter name for the given start and end time from MtLinki

    :param machine_name: The machine name whose data is required
    :type machine_name: str

    :param parameter_name: The parameter name whose data is required
    :type parameter_name: str

    :param start_time: Start time for which the data needs to be queried in epoch format
    :type start_time: float

    :param end_time: End time for which the data needs to be queried in epoch format
    :type end_time: float

    :return: The current machine's full timeline information
    :rtype: dict

    """

    try:
        start_time_seconds = start_time / 1000
        end_time_seconds = end_time / 1000

        message = "Data Available for the requested Time Range"

        # Converting the epoch format to datetime format (UTC-just like how it is stored in db)
        start_time_datetime = datetime.fromtimestamp(start_time_seconds, timezone.utc)
        end_time_datetime = datetime.fromtimestamp(end_time_seconds, timezone.utc)

        # Get the actual parameter name
        requested_parameter = MachineParameter.select(lambda mp: mp.name == parameter_name)[:][0]

        collection = get_mongo_collection(collection="L1Signal_Pool")

        real_time_data_mtlinki = collection.aggregate(
            get_real_time_data_mtlinki(start_time_datetime=start_time_datetime,
                                       end_time_datetime=end_time_datetime,
                                       machine_name=machine_name,
                                       parameter_name=parameter_name))

        real_time_data_mtlinki = list(real_time_data_mtlinki)

        LOGGER.info("++++---------real time data after list--------+++++++++++++++")
        LOGGER.info(real_time_data_mtlinki)

        if not real_time_data_mtlinki:
            message = "Data not available requested time range, giving recent data before the requested start time"
            LOGGER.info(f"Data not available for {requested_parameter.name}")

        # Getting real time data
        real_time_data = [
            [record["updatedate"].timestamp() * 1000, record["value"]]
            for record in real_time_data_mtlinki]
        # Iterate through the real_time_data and replace None values with 0

        LOGGER.info("++++---------real time data after processing--------+++++++++++++++")
        LOGGER.info(real_time_data)

        # We get the timestamp of the recent most recorded value of the requested parameter id before query start time
        recent_value_before_start = get_realtime_machine_parameter_data_before_requested_time_mtlinki(
            start_time=start_time, machine_name=machine_name, parameter_name=parameter_name)

        LOGGER.info("++++---------recent value before start--------+++++++++++++++")
        LOGGER.info(recent_value_before_start)
        LOGGER.info(not recent_value_before_start)

        # SHOULD BE UNCOMMENTED USED FOR DEBUGGING
        # None will be replaced by zero, for recent_value_before_start
        if not recent_value_before_start:
            recent_value_before_start = 0

        LOGGER.info("++++-----------------+++++++++++++++")
        LOGGER.info("++++---------recent value before start , after checking for nan--------+++++++++++++++")
        LOGGER.info(recent_value_before_start)

        # The following is simulated data
        real_time_data.insert(0, [start_time, recent_value_before_start])
        real_time_data.append([end_time, real_time_data[-1][1]])

        LOGGER.info("++++---------real time data after inserting simulated data point--------+++++++++++++++")
        LOGGER.info(real_time_data)

        real_time_data = [[timestamp, 0] if value is None else [timestamp, value] for timestamp, value in
                          real_time_data]
        LOGGER.info("++++---------real time data after inserting and changing for none values --------++++++++++")
        LOGGER.info(real_time_data)

        # Do the following only if real time data is available (either for the requested timestamp or
        # The timestamp of recent most value and one hour before it)
        if real_time_data:
            # Creating response dictionary
            # If warning limit is none, it means it is a dynamic parameter ,
            # And we set the limits to zero for them
            if (requested_parameter.warning_limit is not None) and \
                    not math.isnan(requested_parameter.warning_limit):

                response_data = {"parameter_name": parameter_name,
                                 "chart_data": real_time_data,
                                 "warning_limit": requested_parameter.warning_limit,
                                 "critical_limit": requested_parameter.critical_limit}
            else:

                response_data = {"parameter_name": parameter_name,
                                 "chart_data": real_time_data,
                                 "warning_limit": 0,
                                 "critical_limit": 0}

            unit = requested_parameter.unit.short_name
            response_data["legend_data"] = {"x_axis_label": "Timestamp",
                                            "y_axis_label": parameter_name,
                                            "x_axis_units": "DateTime",
                                            "y_axis_units": unit}
            response_data["message"] = message

            return response_data

    except ObjectNotFound as error:
        LOGGER.error(f"The object not found in database: {error.args[0]}")
        raise GetMachineTimelineError
    except Exception as error:
        LOGGER.error(f"The issues with database: {error.args[0]}")
        raise GetMachineTimelineError(error.args[0])


@db_session(optimistic=False)
def get_machine_timeline(machine_name, parameter_group_id=5, axis_id=0,
                         start_time=1655859600, end_time=1655874000):
    """

    Retrieves the current machine's given parameter group and axis's full timeline information for given
    start and end time

    :param machine_name: The machine name whose data is required
    :type machine_name: str

    :param parameter_group_id: The parameter group identifier
    :type parameter_group_id: int

    :param axis_id: The parameter axis identifier
    :type axis_id: int

    :param start_time: Start time for which the data needs to be queried in epoch format
    :type start_time: float

    :param end_time: End time for which the data needs to be queried in epoch format
    :type end_time: float

    :return: The current machine's full timeline information
    :rtype: dict

    """

    try:

        search_axis_id = axis_id

        # Getting all the parameters for the given machine in the given parameter group
        machine_parameters = get_parameters(machine=machine_name, parameter_group_id=parameter_group_id)

        LOGGER.info(f"Requested parameters all:{machine_parameters}")

        if not machine_parameters:
            # If there was no data found, raise an error
            raise GetMachineTimelineError("Invalid machine/ parameter identifier")

        if search_axis_id >= len(machine_parameters):
            # If the given axis_id is greater than than the total number of axes for the machine, raise an error
            raise GetMachineTimelineError("Invalid axis identifier")

        if (parameter_group_id == 15) or (parameter_group_id == 16):
            search_axis_id = search_axis_id + 1

        # Get the actual parameter name
        requested_parameter_id = machine_parameters[search_axis_id]

        real_time_data_active = RealTimeParameterActive.select(lambda parameter: parameter.machine_parameter.id
                                                                                 == requested_parameter_id)
        if not list(real_time_data_active):
            LOGGER.info(f"Data not available for {requested_parameter_id}, checking if it's spindle parameter")
            if (parameter_group_id == 15) or (parameter_group_id == 16):
                search_axis_id = 0
            else:
                search_axis_id = len(machine_parameters) - 1

            requested_parameter_id = machine_parameters[search_axis_id]
            LOGGER.info(f"With new Parameter id: {requested_parameter_id}")

        requested_parameter_object = MachineParameter[requested_parameter_id]

        LOGGER.info(f"Requested parameter:{requested_parameter_id}")

        # Getting real time data
        real_time_data = get_realtime_data(requested_parameter_id, start_time, end_time)

        # If not data available for the given time, we set the real time data to be
        # Equal to data from recent most time to one hour before it.
        if not real_time_data:

            LOGGER.info("Data not available for the given time, returning the recent most data")

            # We get the timestamp of the recent most recorded value of the requested parameter id
            recent_end_time = get_recent_time_parameter(requested_parameter_id)

            if recent_end_time:
                # We add 5 hour and 30 minutes to adjust for gmt timezone
                # recent_end_time = recent_end_time + 19800
                recent_end_time = recent_end_time

                # We set the stating time stamp for the search to be one hour before the recent most time
                recent_start_time = recent_end_time - 3600

                # If there is any data available for the given parameter (recent most data)
                # We set the real time data to be the data between the recent most recorded value and one hour before it
                real_time_data = get_realtime_data(requested_parameter_id, recent_start_time, recent_end_time)

        # Do the following only if real time data is available (either for the requested timestamp or
        # The timestamp of recent most value and one hour before it)
        if real_time_data:

            # The data sometime have nan values, hence checking the first value, if it is nan, we return nothing
            if math.isnan(real_time_data[1][0]):
                LOGGER.info("Nan Value in database")
                return

            # Creating response dictionary
            # If warning limit is none, it means it is a dynamic parameter ,
            # And we set the limits to zero for them
            if (requested_parameter_object.warning_limit is not None) and \
                    not math.isnan(requested_parameter_object.warning_limit):

                print("value: ", type(requested_parameter_object.warning_limit))

                response_data = {"param": parameter_group_id, "machine": machine_name, "axis": axis_id,
                                 "start_time": real_time_data[0][0], "stop_time": real_time_data[0][-1],
                                 "data": real_time_data[1],
                                 "timestamps": real_time_data[0],
                                 "warning_limit": requested_parameter_object.warning_limit,
                                 "critical_limit": requested_parameter_object.critical_limit}
            else:

                response_data = {"param": parameter_group_id, "machine": machine_name, "axis": axis_id,
                                 "start_time": real_time_data[0][0], "stop_time": real_time_data[0][-1],
                                 "data": real_time_data[1],
                                 "timestamps": real_time_data[0],
                                 "warning_limit": 0,
                                 "critical_limit": 0}

            return response_data

    except ObjectNotFound as error:
        LOGGER.error(f"The object not found in database: {error.args[0]}")
        raise GetMachineTimelineError
    except Exception as error:
        LOGGER.error(f"The issues with database: {error.args[0]}")
        raise GetMachineTimelineError(error.args[0])


@db_session(optimistic=False)
def get_machine_parameter_timeline_spm(machine_name, parameter_name="MeasurementData(SIDE_AUTO_SIZER)"
                                                                    "_JOURNAL FINISH-GRINDING",
                                       start_time=1655859600,
                                       end_time=1655874000):
    """

    Retrieves the full timeline data for a given parameter for a given machine (used for spm)

    :param machine_name: The machine name whose data is required
    :type machine_name: str

    :param parameter_name: The parameter name
    :type parameter_name: str

    :param start_time: Start time for which the data needs to be queried in epoch format
    :type start_time: float

    :param end_time: End time for which the data needs to be queried in epoch format
    :type end_time: float

    :return: The current machine's full timeline information
    :rtype: dict

    """

    try:
        # Getting all the parameters for the given machine in the given parameter group
        machine = Machine.get(name=machine_name)
        requested_parameter_object = MachineParameter.get(name=parameter_name, machine=machine)


        #TODO CHANGED THE TIMESTAP FROM MILISECONDS TO SECONDS(DONE)
        # Convert start_time and end_time from milliseconds to seconds
        start_time_seconds = start_time / 1000.0
        end_time_seconds = end_time / 1000.0

        LOGGER.info(f"Requested parameters Id:{requested_parameter_object.id}")

        if not requested_parameter_object:
            # If there was not data found, raise error
            raise GetMachineTimelineError("Invalid machine/ parameter identifier")


        # Getting real time data
        real_time_data = get_realtime_data(requested_parameter_object.id, start_time, end_time)

        # If not data available for the given time, we set the real time data to be
        # Equal to data from recent most time to one hour before it.
        if not real_time_data:

            LOGGER.info("Data Not available for the given time, returning the recent most available data")

            # We get the timestamp of the recent most recorded value of the requested parameter id
            recent_end_time = get_recent_time_parameter(requested_parameter_object.id)

            # This should be un commented for development purposes, as the development
            # Table has time column without timezone, but in production timezone is there
            # hence need to be commented out
            # We add 5 hour and 30 minutes to adjust for gmt timezone
            # if machine_name != "Laser Cladding":
            #     recent_end_time = recent_end_time + 19800
            # recent_end_time = recent_end_time

            LOGGER.info(f"Recently recorded End time: {recent_end_time}")
            # We set the stating time stamp for the search to be one hour before the recent most time
            recent_start_time = recent_end_time - 3600

            LOGGER.info(f"Recently recorded Start time: {recent_start_time}")

            # If there is any data available for the given parameter (recent most data)
            # We set the real time data to be the data between the recent most recorded value and one hour before it
            if recent_end_time:
                real_time_data = get_realtime_data(requested_parameter_object.id, recent_start_time, recent_end_time)

        # Do the following only if real time data is available (either for the requested timestamp or
        # The timestamp of recent most value and one hour before it)
        if real_time_data:
            # Creating response dictionary
            # If warning limit is none, it means it is a dynamic parameter ,
            # And we set the limits to zero for them
            if (requested_parameter_object.warning_limit is not None) and \
                    not math.isnan(requested_parameter_object.warning_limit):

                print("value: ", type(requested_parameter_object.warning_limit))

                response_data = {"param": requested_parameter_object.id, "machine": machine_name,
                                 "axis": requested_parameter_object.name,
                                 "start_time": real_time_data[0][0], "stop_time": real_time_data[0][-1],
                                 "data": real_time_data[1],
                                 "timestamps": real_time_data[0],
                                 "warning_limit": requested_parameter_object.warning_limit,
                                 "critical_limit": requested_parameter_object.critical_limit}
            else:

                response_data = {"param": requested_parameter_object.id, "machine": machine_name,
                                 "axis": requested_parameter_object.name,
                                 "start_time": real_time_data[0][0], "stop_time": real_time_data[0][-1],
                                 "data": real_time_data[1],
                                 "timestamps": real_time_data[0],
                                 "warning_limit": 0,
                                 "critical_limit": 0}

            return response_data

    except ObjectNotFound as error:
        LOGGER.error(f"The object not found in database: {error.args[0]}")
        raise GetMachineTimelineError
    except Exception as error:
        LOGGER.error(f"The issues with database: {error.args[0]}")
        raise GetMachineTimelineError(error.args[0])


@db_session
def get_parameters(machine="T_B_OP160", parameter_group_id=1):
    """

    Function to get all parameters for a given machine in a given parameter group (identifier)

    :param machine: The machine for which the parameters are required
    :type machine: str

    :param parameter_group_id: The parameter group identifier
    :type parameter_group_id: int

    :return: List of sorted (by name) parameter (identifier) for the given machine and parameter group
    :rtype: list

    """

    try:
        LOGGER.info(f"Getting all parameters for machine: {machine} and group id: {parameter_group_id}")

        # Selecting machine parameters based on given machine name and parameter group identifier
        parameters = MachineParameter.select(lambda parameter: parameter.machine.name == machine)
        parameters = parameters.filter(lambda parameter: parameter.parameter_group.id == parameter_group_id)

        # Sorting by machine parameter name (hence ApcBatLow_0, ApcBatLow_1, ...so on will be the order of results
        # returned)
        parameters = parameters.sort_by(MachineParameter.name)

        # If the query results in any data, do the following
        if parameters:
            LOGGER.info("parameter available")
            # Return only the parameter ids
            return [param.id for param in parameters]
    except Exception as error:
        LOGGER.exception(f"Exception while processing status of machine for given parameter group: {error.args[0]}")
        raise GetAllParameterDBError


@db_session(optimistic=False)
def get_realtime_machine_parameter_data(parameter_id=5361, start_time=1662505509000, end_time=1662534309000):
    """

    Function used to return the real time data from the database for given parameter and time

    :param parameter_id: The parameter identifier
    :type parameter_id: int

    :param start_time: Start time for which the data needs to be queried in epoch format (in milliseconds)
    :type start_time: float

    :param end_time: End time for which the data needs to be queried in epoch format (in milliseconds)
    :type end_time: float

    :return: A List of machine parameter data with timestamp
    :rtype: list

    """

    try:
        start_time_seconds = start_time / 1000
        end_time_seconds = end_time / 1000

        # Converting the epoch format to datetime format (UTC-just like how it is stored in db)
        start_time_datetime = datetime.fromtimestamp(start_time_seconds, timezone.utc)
        end_time_datetime = datetime.fromtimestamp(end_time_seconds, timezone.utc)

        LOGGER.info(f"The start time of the query is {str(start_time_datetime)}")
        LOGGER.info(f"The end time of the query is {str(end_time_datetime)}")
        LOGGER.info(f"The parameter id of the query is {parameter_id}")

        # Querying the real time data from the database for given parameter and time and sorting them using timestamp
        data = RealTimeParameter.select(lambda parameter: parameter.machine_parameter.id == parameter_id)
        data = data.filter(lambda parameter: parameter.time >= start_time_datetime)

        data = data.filter(lambda parameter: parameter.time <= end_time_datetime)
        data = data.sort_by(RealTimeParameter.time).for_update()[:]

        if data:
            return_data = [[record.time.timestamp() * 1000, None if math.isnan(record.value) else record.value]
                           for record in data]

            return return_data
        return []
    except Exception as error:
        LOGGER.exception(f"Exception while processing status of machine for given parameter: {error.args[0]}")


@db_session(optimistic=False)
def get_realtime_machine_parameter_data_before_requested_time(parameter_id=5361, start_time=1662505509000):
    """

    Function used to return the one real time data from the database for given parameter and time earlier (but the
    latest) than the start_time

    :param parameter_id: The parameter identifier
    :type parameter_id: int

    :param start_time: Start time for which the data needs to be queried in epoch format (in milliseconds)
    :type start_time: float

    :return: A floating point value of the recent most value before the requested timestamp
    :rtype: float

    """

    try:
        start_time_seconds = start_time / 1000

        # Converting the epoch format to datetime format (UTC- just like how it is stored in db)
        start_time_datetime = datetime.fromtimestamp(start_time_seconds, timezone.utc)

        LOGGER.info(f"The start time of the query is {str(start_time_datetime)}")
        LOGGER.info(f"The parameter id of the query is {parameter_id}")

        # Querying the real time data from the database for given parameter and time and sorting them using timestamp
        data = RealTimeParameter.select(lambda parameter: parameter.machine_parameter.id == parameter_id)
        data = data.filter(lambda parameter: parameter.time <= start_time_datetime)
        # If any issue check the for_update option here, commenting it for some purpose
        # data = data.sort_by(desc(RealTimeParameter.time)).limit(1).for_update()
        data = data.sort_by(desc(RealTimeParameter.time)).limit(1)

        if data:
            LOGGER.info("=" * 10)
            LOGGER.info(data[0].value)
            LOGGER.info(data[0].time)
            return_data = data[0].value

            return return_data
    except Exception as error:
        LOGGER.exception(f"Exception while processing status of machine for given parameter: {error.args[0]}")


def get_realtime_machine_parameter_data_before_requested_time_mtlinki(machine_name, parameter_name=5361,
                                                                      start_time=1662505509000):
    """

    Function used to return the one real time data from the database for given parameter and time earlier (but the
    latest) than the start_time from MtLinki

    :param machine_name: The machine name
    :type machine_name: str

    :param parameter_name: The parameter identifier
    :type parameter_name: str

    :param start_time: Start time for which the data needs to be queried in epoch format (in milliseconds)
    :type start_time: float

    :return: A floating point value of the recent most value before the requested timestamp
    :rtype: float

    """

    try:
        start_time_seconds = start_time / 1000

        # Converting the epoch format to datetime format (UTC- just like how it is stored in db)
        start_time_datetime = datetime.fromtimestamp(start_time_seconds, timezone.utc)

        LOGGER.info(f"The start time of the query is {str(start_time_datetime)}")
        LOGGER.info(f"The parameter name of the query is {parameter_name}")

        # Getting the recent most value from Mtlink Signal Pool Active

        collection_active = get_mongo_collection_active(collection="L1Signal_Pool_Active")

        recent_data_active = collection_active.aggregate(
            get_recent_active_pool_value(machine_name=machine_name, parameter_name=parameter_name))

        recent_data_active = list(recent_data_active)[0]

        active_update_time = recent_data_active["updatedate"].timestamp()

        if active_update_time < start_time_seconds:
            LOGGER.info("The recent most data from MtLinki Active is earlier than the requested start time")
            return recent_data_active["value"]

        # Getting recent most value from MtLinki Signal Pool

        # Querying the real time data from the database for given parameter and time and sorting them using timestamp
        collection = get_mongo_collection_active(collection="L1Signal_Pool")

        recent_data_pool = collection.aggregate(
            get_value_before_requested_data_mtlinki(start_time_datetime=start_time_datetime,
                                                    machine_name=machine_name,
                                                    parameter_name=parameter_name))

        LOGGER.info("Getting the data for the  recent before list")
        LOGGER.info(recent_data_pool)

        recent_data_pool = list(recent_data_pool)
        LOGGER.info("Getting the data for the previous recent")
        LOGGER.info(recent_data_pool)

        if recent_data_pool:
            LOGGER.info("=" * 10)
            # LOGGER.info(recent_data_pool[0]["value"])
            # return_data = recent_data_pool[0]["value"]

            for i in recent_data_pool:
                if i["value"] != None:
                    return_data = i["value"]
                    break
            else:
                return_data = 0

            LOGGER.info("The recent most data from MtLinki Active is later than the requested start time")
            return return_data

        LOGGER.info("No recent data for the requested detail")

    except Exception as error:
        LOGGER.exception(f"Exception while getting recent most data: {error.args[0]}")


@db_session(optimistic=False)
def get_realtime_data(parameter_id=5361, start_time=1662505509, end_time=1662534309):
    """

    Function used to return the real time data from the database for given parameter and time

    :param parameter_id: The parameter identifier
    :type parameter_id: int

    :param start_time: Start time for which the data needs to be queried in epoch format
    :type start_time: float

    :param end_time: End time for which the data needs to be queried in epoch format
    :type end_time: float

    :return: A List of list of machine parameter data and list of timestamp
    :rtype: list

    """

    try:

        # Converting the epoch format to datetime format (UTC- just like how it is stored in db)
        start_time_datetime = datetime.fromtimestamp(start_time, tz=pytz.timezone("UTC"))
        LOGGER.info("Starttime")
        LOGGER.info(start_time_datetime)
        end_time_datetime = datetime.fromtimestamp(end_time, tz=pytz.timezone("UTC"))
        LOGGER.info("Starttime")
        LOGGER.info(end_time_datetime)

        # #TESTING FOR GMT
        # # Converting the epoch format to datetime format (UTC- just like how it is stored in db)
        # # Convert start_time from epoch to datetime in GMT+5:30 (Indian Standard Time)
        # start_time_datetime = datetime.fromtimestamp(start_time, timezone.utc)
        # LOGGER.info("Starttime")
        # LOGGER.info(start_time_datetime)
        #
        # # Convert end_time from epoch to datetime in GMT+5:30 (Indian Standard Time)
        # end_time_datetime = datetime.fromtimestamp(end_time, timezone.utc)
        # LOGGER.info("Endtime")
        # LOGGER.info(end_time_datetime)

        # start_time_datetime = datetime.fromtimestamp(start_time)
        # end_time_datetime = datetime.fromtimestamp(end_time)

        LOGGER.info(f"The start time of the query is {str(start_time_datetime)}")
        LOGGER.info(f"The end time of the query is {str(end_time_datetime)}")
        LOGGER.info(f"The parameter id of the query is {parameter_id}")

        # Querying the real time data from the database for given parameter and time and sorting them using timestamp
        data = RealTimeParameter.select(lambda parameter: parameter.machine_parameter.id == parameter_id)
        data = data.filter(lambda parameter: parameter.time >= start_time_datetime)

        # LOGGER.info(f"Requested data:{data}")

        # Remember that they are sorted by timestamp in ascending order
        # In that case, the condition_id of 1 or 2 or 3 will be be coming in the end of each cycle
        data = data.filter(lambda parameter: parameter.time <= end_time_datetime). \
                   sort_by(RealTimeParameter.time).for_update()[:]
        # print(data)
        #TODO THE CHANGES

        # Inside the data processing section where the error occurs
        # for record in data:
        #     parameter_condition = record.parameter_condition
        #     if parameter_condition is not None:
        #         parameter_condition_id = parameter_condition.id
        #         # Process parameter_condition_id as needed
        #     else:
        #         LOGGER.warning("Parameter condition is None for record: {}".format(record))
        #         # Set a default value of "1" for the condition_id
        #         parameter_condition_id = "1"  # Change this default value as needed
        #
        # # Add more logging statements for debugging
        # LOGGER.info("Value of parameter_condition: {}".format(parameter_condition))
        #
        # LOGGER.info(f"Requested data after sorting:{data}")

        if data:
            return_data = [[record.time.timestamp() * 1000 for record in data], [record.value for record in data]]
            # LOGGER.info(return_data)

            # Getting all the parameter condition_id values as list
            # return_data_2 = [record.parameter_condition.id for record in data]
            # LOGGER.info(return_data_2)
            # LOGGER.info(f'{return_data[0][0]} || {return_data[0][8752]}')
            return_data_2 = []
            # TODO MONITOR THE CHANGE
            for record in data:
                try:
                    return_data_2.append(record.parameter_condition)
                except:
                    return_data_2.append(None)

            # Getting all the ids of rows where the condition_id is not none
            # These represents the end of cycle row
            LOGGER.info("++++++++++++++++++++++++++++++")
            indices = [i for i, x in enumerate(return_data_2) if x is not None]
            LOGGER.info(f'return_data[0]={len(return_data[0])}, return_data[1]={len(return_data[1])}')
            LOGGER.info(indices)

            response_data = []

            # For each index we do the following
            # To understand better, use the following example
            # Assume this is a sample condition_id data
            # condition_id = [None, None, None, None, 1, None, None, None, 1, None, None, None, 1]
            #
            # Then the indices will have the following values
            # indices = [4, 8, 12]
            #
            # When we loop over the range(len(indices), the index will take the following values
            # index = [0, 1, 2]
            for index in range(len(indices)):
                current_cycle_data = {}

                # If the index is zero, it means we're starting the loop and hence we should take the
                # start_index value to be zero
                if index == 0:
                    start_index = 0
                else:
                    # If not, (we'll take the example above, the second cycle starts at index 5
                    # Hence we need to start from 5 (which is 4 + 1, where 4 is the index of last
                    # time condition id was not none), we get this 4 by getting previous values
                    start_index = indices[index - 1] + 1

                end_index = indices[index] + 1
                current_cycle_data["cycle_value"] = return_data[1][start_index: end_index]
                current_cycle_data["timestamps"] = return_data[0][start_index: end_index]
                # LOGGER.info(f"current_cycle_data  is : {current_cycle_data} ")

                # LOGGER.info('*'*30)
                # Add more logging statements for debugging
                # LOGGER.info("Value of parameter_condition: {}".format(parameter_condition))
                # TODO : ADDED THE END INDEX -1
                try:
                    current_cycle_data["cycle_time"] = (return_data[0][end_index - 1] - return_data[0][
                        start_index]) / 1000
                    # LOGGER.info(f"Current cycle data in the try +++++++++++++++++++++")
                    # LOGGER.info({current_cycle_data})
                except Exception:
                    current_cycle_data["cycle_time"] = return_data[0][indices[start_index]]

                response_data.append(current_cycle_data)
            # LOGGER.info(f"Returend Data is : {return_data} ")
            return return_data
    except Exception as error:
        LOGGER.exception(f"Exception while processing status of machine for given parameter group: {error.args[0]}")


@db_session(optimistic=False)
def get_recent_time_parameter(parameter_id=2711):
    """

    Function used to return the last recorded time of a parameter value

    :param parameter_id: The parameter identifier
    :type parameter_id: int

    :return: recent most timestamp of the given parameter
    :rtype: float

    """

    try:
        # Querying the real time data from the database for given parameter and time and sorting them using timestamp
        data = RealTimeParameterActive.select(lambda parameter: parameter.machine_parameter.id == parameter_id)
        data = list(data)

        if data:
            return_data = data[0].time.timestamp()
            return return_data
    except Exception as error:
        LOGGER.exception(f"Exception while getting last recorded time of parameter: {parameter_id}")


@db_session(optimistic=False)
def set_dynamic_parameter_reference_signals():
    """
    Function used to set the reference signal for dynamic parameters
    (that uses kruskal's method for anomaly detection)

    :return: A String containing the sql query
    :rtype: str
    """

    # query_template = get_all_recent_time_template()
    #
    # # Using a really complicated group by function along with timescale db inbuilt function
    # # To get the total number of warning and critical parameters
    # oldest_time_parameters = list(PONY_DATABASE.select(query_template))
    #
    # reference_signal_time = [(parameter[0], parameter[1], parameter[1] + timedelta(hours=1))
    #                          for parameter in oldest_time_parameters]
    #
    # for parameter in reference_signal_time:
    #     current_reference_signal = get_realtime_data(parameter[0], parameter[1].timestamp() + 19800,
    #                                                  parameter[2].timestamp() + 19800)
    #
    #     if current_reference_signal:
    #         current_reference_signal = current_reference_signal[1]
    #     else:
    #         continue
    #
    #     machine_parameter = MachineParameter[parameter[0]]
    #     machine_parameter.reference_signal = current_reference_signal
    #     commit()

    # Getting all the dynamic parameters
    dynamic_parameters = MachineParameter.select(lambda p: p.parameter_group.id == 17)

    for parameter in dynamic_parameters:
        real_time_data = RealTimeParameter.select(lambda p: p.machine_parameter == parameter)
        real_time_data = real_time_data.filter(lambda p: p.parameter_condition.id > 0)
        real_time_data = real_time_data.order_by(desc(RealTimeParameter.time))[:2]

        if len(real_time_data) == 2:

            reference_signal = RealTimeParameter.select(lambda p: p.time > real_time_data[1].time)
            reference_signal = reference_signal.filter(lambda p: p.time <= real_time_data[0].time)
            reference_signal = reference_signal.filter(lambda p: p.machine_parameter == parameter)
            reference_signal = reference_signal.order_by(RealTimeParameter.time)
        else:
            continue
        if reference_signal:
            set_reference_signal = []
            for signal in reference_signal:
                print(signal)
                set_reference_signal.append(signal.value)

            parameter.reference_signal = set_reference_signal
            commit()
    return


@db_session
def get_user(username: str):
    """
    GET USER
    ===========

    This function is used to return a Pydantic model of (active - disable = False) user if the user is in the database

    :param username: The user name who wants to log in

    :return: Return a pydantic class of user
    :rtype: UserInDB
    """

    user = UserPony.select(lambda current_user: current_user.username == username).first()

    if user:
        return UserInDB(**user.to_dict())


@db_session
def get_user_emails():
    """
    GET USER
    ===========

    This function is used to return all the email ids of available users

    :return: Return a list of email ids of users
    :rtype: list
    """

    email_ids = select(email.email_id for email in EmailUser)[:]

    print(list(email_ids))

    return email_ids


@db_session
def get_users():
    """
    GET USERS
    ===========

    This function is used to return all available users

    :return: Return a list of email ids of users
    :rtype: list
    """

    # Getting all the users from the database
    users = select(user for user in UserPony)[:]

    # Converting the users in database to pydantic users model
    users = [UserPydantic(**user.to_dict()) for user in users]

    return users


@db_session
def get_maintenance_operators():
    """
    GET MAINTENANCE OPERATORS
    =========================

    This function is used to return all available maintenance operators

    :return: Return a list of users and their unique id in database
    :rtype: list
    """

    # Getting all the users from the database
    users = select(user for user in UserPony if user.role
                   == 'maintenance_operator')[:]

    # Converting the users in database to pydantic users model
    users = [UserPydantic(**user.to_dict()) for user in users]

    return users


@db_session
def create_user(username: str, hashed_password: str,
                email: Optional[str] = None,
                role: Optional[str] = 'guest',
                company_id: Optional[int] = None):
    """
    CREATE USER
    ==============

    This function is used to create a new user

    :param username: The new user name
    :param email: The email of the new user
    :param role: The role of new user
    :param hashed_password: The hashed_password of new user
    :param company_id: The unique id that identifies the user in the company database

    :return: Return a pydantic class of user
    :rtype: User
    """

    # We need to check if the user is already in the database
    # Hence we're searching for user of same name
    user = UserPony.select(lambda current_user: current_user.username == username).first()

    # If user of same name is not existing, we do the following
    if not user:
        user_orm = UserPony(username=username, email=email,
                            hashed_password=hashed_password, disabled=False,
                            role=role, company_id=company_id)

        # Not required to commit, but lets use if for testing purposes
        commit()
        return UserPydantic(**user_orm.to_dict())


@db_session
def get_spare_parts(machine_name: str):
    """
    GET SPARE PARTs
    =====================

    This function is used to get all the spare parts of machine

    :param machine_name: The machine name

    :return: Returns list of spare parts details
    :rtype: dict
    """

    machine = Machine.get(name=machine_name)

    if machine:
        spare_parts = list(machine.spare_parts.order_by(SparePart.part_name))

        # Not required to commit, but committing for testing purpose.
        commit()

        # response_data = spare_parts.to_dict()
        response_data = []

        # Getting the machine part count object (Table)
        machine_part_count = MachinePartCount.get(machine=machine)

        # Getting the total part count of this machine
        total_part_count_of_machine = machine_part_count.current_part_count
        current_part_count_of_machine = total_part_count_of_machine - machine_part_count.last_reset_count

        id_counter = 1

        # For every spare part available in the machine, we do the following
        for part in spare_parts:
            # Converting the part pony object to dictionary
            part_details = part.to_dict()

            part_details["machine_id"] = part_details["machine"]

            # Getting the current part count for the spare part, by subtracting the reference
            # Part count/number from the total part count of machine.
            # The reference part count is equal to the total part count of machine when the
            # Spare part was created from the front end or equal to the total part count of machine when the
            # Spare part count was reset from the front end.
            current_spare_part_count = total_part_count_of_machine - part.reference_part_number

            part_details["count"] = current_spare_part_count
            part_details["id"] = id_counter
            id_counter += 1
            response_data.append(part_details)

        response_data = {"total_count": total_part_count_of_machine,
                         "current_count": current_part_count_of_machine,
                         "spare_parts": response_data}

        return response_data


@db_session
def create_spare_part(machine_name: str, part_name: str, reference_part_number: int, warning_limit: int,
                      critical_limit: int):
    """
    CREATE SPARE PART
    =====================

    This function is used to create a new user

    :param machine_name: The machine name
    :param part_name: The part name
    :param reference_part_number: The reference part number
    :param warning_limit: The change limit for the part number
    :param critical_limit: The change limit for the part number

    :return: Return a pydantic class of user
    :rtype: PydanticSparePart
    """

    machine = Machine.select(lambda current_machine: current_machine.name == machine_name).first()

    if machine:
        spare_part_orm = SparePart(part_name=part_name, reference_part_number=reference_part_number,
                                   warning_limit=warning_limit, critical_limit=critical_limit, machine=machine)

        # Not required to commit, but lets use if for testing purposes
        commit()

        response_data = spare_part_orm.to_dict()
        response_data["machine_id"] = response_data["machine"]

        return PydanticSparePart(**response_data)


# @db_session
# def update_spare_part(machine_name: str, part_name: str, parameter_name: str, parameter_value: int):
#     """
#     CREATE SPARE PART
#     =====================
#
#     This function is used to create a new user
#
#     :param machine_name: The machine name
#     :param part_name: The part name
#     :param parameter_name: The parameter name
#     :param parameter_value: The reference part number
#
#     :return: Return a pydantic class of spare part
#     :rtype: PydanticSparePart
#     """
#
#     machine = Machine.select(lambda current_machine: current_machine.name == machine_name).first()
#
#     spare_part = SparePart.select(lambda current_part: current_part.part_name == part_name)
#     spare_part = spare_part.filter(lambda current_part: current_part.machine == machine).first()
#
#     if spare_part:
#         if parameter_name == "reference_part_number":
#             spare_part.reference_part_number = parameter_value
#         elif parameter_name == "warning_limit":
#             spare_part.warning_limit = parameter_value
#         else:
#             spare_part.critical_limit = parameter_value
#
#         # Not required to commit, but lets use if for testing purposes
#         commit()
#
#         response_data = spare_part.to_dict()
#         response_data["machine_id"] = response_data["machine"]
#
#         return PydanticSparePart(**response_data)


# Separate update function
@db_session
def update_spare_part(machine_name: str, updates: SparePartUpdateList):
    """Updates spare parts associated with a specified machine.

    Args:
        machine_name (str): The name of the machine whose spare parts need updating.
        updates (SparePartUpdateList): A list of spare part updates.

    Raises:
        HTTPException (404):  If the specified machine is not found.
        HTTPException (404):  If a specific spare part to be updated is not found.
    """

    machine = Machine.get(name=machine_name)
    if not machine:  # Check if the machine exists
        raise HTTPException(status_code=404, detail="Machine part not found")

    LOGGER.info(machine_name)  # Log the machine name

    for update in updates.data:
        spare_part = SparePart.get(machine=machine, part_name=update.part_name)

        if not spare_part:  # Check if the spare part exists
            raise HTTPException(status_code=404, detail="Spare part not found")

        spare_part_dic = update.dict()  # Convert update data to a dictionary
        spare_part.set(**spare_part_dic)  # Update the spare part attributes
        commit()  # Commit changes to the database


@db_session
def delete_spare_part(machine_name: str, part_name: str):
    """
    DELETE SPARE PART
    =====================

    This function is used to delete a spare part from the database

    :param machine_name: The machine name
    :param part_name: The part name

    :return: Return a deleted message
    :rtype: dict
    """

    machine = Machine.select(lambda current_machine: current_machine.name == machine_name).first()

    spare_part = SparePart.select(lambda current_part: current_part.part_name == part_name)
    spare_part = spare_part.filter(lambda current_part: current_part.machine == machine).first()

    if spare_part:
        spare_part_name = spare_part.part_name

        spare_part.delete()

        # Not required to commit, but lets use if for testing purposes
        commit()

        return {"detail": "Successfully Deleted", "spare_part": spare_part_name}


@db_session
def delete_spare_parts(machine_name: str, part_names: list):
    """
    DELETE SPARE PART
    =====================

    This function is used to delete a spare part from the database

    :param machine_name: The machine name
    :param part_names: The list of part names

    :return: Return a deleted message
    :rtype: dict
    """

    machine = Machine.select(lambda current_machine: current_machine.name == machine_name).first()

    for spare in part_names:

        spare_part = SparePart.select(lambda current_part: current_part.part_name == spare)
        spare_part = spare_part.filter(lambda current_part: current_part.machine == machine).first()

        if spare_part:
            spare_part.delete()

            # Not required to commit, but lets use if for testing purposes
            commit()

    return {"detail": "Successfully Deleted"}


@db_session
def delete_user(user_id: int):
    """
    DELETE USER
    =====================

    This function is used to delete a user from the database

    :param user_id: The user id as stored in the database

    :return: Return a deleted message
    :rtype: dict
    """

    user = User[user_id]

    if user.username == "cmti":
        return {"detail": "admin"}

    if user:
        user_name = user.username

        user.delete()

        # Not required to commit, but lets use if for testing purposes
        commit()

        return {"detail": "Successfully Deleted", "user_name": user_name}


@db_session
def get_alert_summary(condition_id: int = 3):
    """
    CREATE ALERT SUMMARY
    =======================

    This function is used to create a new user

    :param condition_id: The condition if for which the summary is to be created

    :return: List of alert summary
    :rtype: List
    """

    # If you dont use '*' in pony count,  (instead use something like p.time), it will result in
    # Using the keyword 'DISTINCT' within the count, that will result in less number
    # So if you simply want to get how many times a machine went to anomaly within given time, you can use
    # p.time in count (since every second more than 1 parameter might be in warning state, hence
    # You may have to use the keyword 'DISTINCT'.
    # parameters = select((p.machine_parameter.machine.name, p.machine_parameter.machine.location, pony_count("*"))
    #                     for p in RealTimeParameter if p.parameter_condition.id == 3)[:]

    # parameters = select((p.machine_parameter.machine.name, p.machine_parameter.machine.location, pony_count(p.time))
    #                     for p in RealTimeParameter if p.parameter_condition.id == 3)

    # This gives anomaly for each location, how many machines (not how many times all machine, so even if machine
    # had been in anomaly twice, it will be counted as one), and how many times (all) parameters were in anomaly
    # Order by -3 means order by the 3rd element of the resulting tuple in descending order
    parameters = select((p.machine_parameter.machine.location, pony_count(p.machine_parameter.machine.name),
                         pony_count("*")) for p in RealTimeParameter if p.parameter_condition.id == condition_id). \
        order_by(-3)

    return parameters[:]


@db_session(optimistic=False)
def update_parameter_limits_with_parameter_name(parameter_name: str, set_type: str = "warning_limit",
                                                limit: Optional[float] = None, reference_signal: Optional[List[float]] = None,
                                                append: bool = False, current_user: User = None):
    """
    Updates the specified machine parameter limits.
    """

    try:
        machine_parameter = MachineParameter.select(lambda mp: mp.name == parameter_name).first()

        if not machine_parameter:
            raise HTTPException(status_code=404, detail="Machine parameter not found")

        # Fetch current limit values before updating
        old_warning_limit = machine_parameter.warning_limit
        old_critical_limit = machine_parameter.critical_limit
        old_reference_signal = machine_parameter.reference_signal

        # Log old limit values
        LOGGER.info(f"Fetched Old Values - Warning Limit: {old_warning_limit}, Critical Limit: {old_critical_limit}")

        if set_type == "warning_limit":
            if machine_parameter.parameter_type == "decreasing":
                if machine_parameter.critical_limit < limit:
                    machine_parameter.warning_limit = limit
                    response_data = {"set_type": "warning_limit", "value": limit}
                else:
                    raise Exception("Warning limit must be greater than the critical limit")
            else:
                if machine_parameter.critical_limit > limit:
                    machine_parameter.warning_limit = limit
                    response_data = {"set_type": "warning_limit", "value": limit}
                else:
                    raise Exception("Warning limit must be less than the critical limit")

        elif set_type == "critical_limit":
            if machine_parameter.parameter_type == "decreasing":
                if machine_parameter.warning_limit > limit:
                    machine_parameter.critical_limit = limit
                    response_data = {"set_type": "critical_limit", "value": limit}
                else:
                    raise Exception("Critical limit must be less than the warning limit")
            else:
                if machine_parameter.warning_limit < limit:
                    machine_parameter.critical_limit = limit
                    response_data = {"set_type": "critical_limit", "value": limit}
                else:
                    raise Exception("Critical limit must be greater than the warning limit")

        else:
            if append:
                if machine_parameter.reference_signal is not None:
                    machine_parameter.reference_signal.extend(reference_signal)
                else:
                    machine_parameter.reference_signal = reference_signal
            else:
                machine_parameter.reference_signal = reference_signal

            response_data = {"set_type": "dynamic_limit", "value": reference_signal}

        # Log the update
        LOGGER.info(f"Logging Update - Previous Limit: {old_warning_limit if set_type == 'warning_limit' else old_critical_limit}")

        # Log the update
        UpdateLog(
            user=current_user.username,
            parameter_name=parameter_name,
            previous_limit=old_warning_limit if set_type == "warning_limit" else old_critical_limit,
            limit_value=limit,
            reference_signal=reference_signal,
            set_type=set_type,
            date_changed=datetime.now()
        )

        commit()
        return {"response_data": response_data,"previous_limit": old_warning_limit if set_type == "warning_limit" else old_critical_limit}

    except ObjectNotFound as error:
        error_message = error.args[0] if error.args else str(error)
        LOGGER.error(f"The object not found in database: {error_message}")
        raise HTTPException(status_code=404, detail="Object not found in database")
    except Exception as error:
        error_message = error.args[0] if error.args else str(error)
        LOGGER.error(f"Database error: {error_message}")
        raise HTTPException(status_code=500, detail=f"Internal Error: {error_message}")

@db_session(optimistic=False)
def update_parameter_limits(machine_name, parameter_group_id=5, axis_id=0,
                            set_type="warning_limit", limit=None, reference_signal=None,
                            append=False):
    """
    Retrieves the current machine's given parameter group and axis's full timeline information for given
    start and end time

    :param machine_name: The machine name whose data is required
    :type machine_name: str

    :param parameter_group_id: The parameter group identifier
    :type parameter_group_id: int

    :param axis_id: The parameter axis identifier
    :type axis_id: int

    :param set_type: The parameter axis identifier
    :type set_type: str

    :param limit: Start time for which the data needs to be queried in epoch format
    :type limit: float

    :param reference_signal: End time for which the data needs to be queried in epoch format
    :type reference_signal: Optional[list[float]]

    :param append: If the parameter type is dynamic, we're updating the reference signal, then we either append to
    the existing value or add a new value (list of values)
    :type append: bool

    :return: The current machine's full timeline information
    :rtype: dict

    """

    try:
        # Getting all the parameters for the given machine in the given parameter group
        machine_parameters = get_parameters(machine=machine_name, parameter_group_id=parameter_group_id)

        LOGGER.info(f"Requested parameters all:{machine_parameters}")

        if not machine_parameters:
            # If there was not data found, raise error
            raise GetMachineTimelineError("Invalid machine/ parameter identifier")

        if axis_id >= len(machine_parameters):
            # If the given axis_id is greater than than the total number of axes for the machine, raise error
            raise GetMachineTimelineError("Invalid axis identifier")

        # Get the actual parameter name
        requested_parameter_id = machine_parameters[axis_id]
        LOGGER.info(f"Requested parameter:{requested_parameter_id}")

        machine_parameter = MachineParameter[requested_parameter_id]

        if set_type == "warning_limit":
            if machine_parameter.parameter_type == "decreasing":
                if machine_parameter.critical_limit < limit:
                    machine_parameter.warning_limit = limit
                    response_data = {"set_type": "warning_limit",
                                     "value": limit}
                else:
                    raise Exception("Invalid limit, warning limit must be greater than the critical limit")
            else:
                if machine_parameter.critical_limit > limit:
                    machine_parameter.warning_limit = limit
                    response_data = {"set_type": "warning_limit",
                                     "value": limit}
                else:
                    raise Exception("Invalid limit, warning limit must be less than the critical limit")

        elif set_type == "critical_limit":
            if machine_parameter.parameter_type == "decreasing":
                if machine_parameter.warning_limit > limit:
                    machine_parameter.critical_limit = limit
                    response_data = {"set_type": "critical_limit",
                                     "value": limit}
                else:
                    raise Exception("Invalid limit, warning limit must be greater than the critical limit")
            else:
                if machine_parameter.warning_limit < limit:
                    machine_parameter.critical_limit = limit
                    response_data = {"set_type": "critical_limit",
                                     "value": limit}
                else:
                    raise Exception("Invalid limit, warning limit must be less than the critical limit")

        else:
            if append:
                if machine_parameter.reference_signal is not None:
                    machine_parameter.reference_signal.extend(reference_signal)
                else:
                    machine_parameter.reference_signal = reference_signal
            else:
                machine_parameter.reference_signal = reference_signal

            response_data = {"set_type": "dynamic_limit",
                             "value": reference_signal}

        commit()
        # response_data = {"detail": f"Successfully updated machine parameters limit for machine: {machine_name},"
        #                            f" parameter group id: {parameter_group_id}, axis id : {axis_id}"}

        return response_data

    except ObjectNotFound as error:
        LOGGER.error(f"The object not found in database: {error.args[0]}")
        raise GetMachineTimelineError
    except Exception as error:
        LOGGER.error(f"The issues with database: {error.args[0]}")
        raise GetMachineTimelineError(error.args[0])


@db_session(optimistic=False)
def update_parameter_limits_spm(parameter_name,
                                set_type="warning_limit", limit=None, reference_signal=None,
                                append=False):
    """
    Retrieves the current machine's given parameter group and axis's full timeline information for given
    start and end time

    :param parameter_name: The machine name whose data is required
    :type parameter_name: str

    :param set_type: The parameter axis identifier
    :type set_type: str

    :param limit: Start time for which the data needs to be queried in epoch format
    :type limit: float

    :param reference_signal: End time for which the data needs to be queried in epoch format
    :type reference_signal: Optional[list[float]]

    :param append: If the parameter type is dynamic, we're updating the reference signal, then we either append to
    the existing value or add a new value (list of values)
    :type append: bool

    :return: The current machine's full timeline information
    :rtype: dict

    """

    try:

        machine_parameter = MachineParameter.get(name=parameter_name)

        if set_type == "warning_limit":
            machine_parameter.warning_limit = limit
            response_data = {"set_type": "warning_limit",
                             "value": limit}

        elif set_type == "critical_limit":
            machine_parameter.critical_limit = limit
            response_data = {"set_type": "critical_limit",
                             "value": limit}

        else:
            if append:
                if machine_parameter.reference_signal is not None:
                    machine_parameter.reference_signal.extend(reference_signal)
                else:
                    machine_parameter.reference_signal = reference_signal
            else:
                machine_parameter.reference_signal = reference_signal

            response_data = {"set_type": "dynamic_limit",
                             "value": reference_signal}

        commit()
        # response_data = {"detail": f"Successfully updated machine parameters limit for machine: {machine_name},"
        #                            f" parameter group id: {parameter_group_id}, axis id : {axis_id}"}

        return response_data

    except ObjectNotFound as error:
        LOGGER.error(f"The object not found in database: {error.args[0]}")
        raise GetMachineTimelineError
    except Exception as error:
        LOGGER.error(f"The issues with database: {error.args[0]}")
        raise GetMachineTimelineError(error.args[0])


def get_alarm_summary(start_time_datetime, end_time_datetime, production_line: str = r".*",
                      state="DISCONNECT"):
    """
    Function to get the total number of seconds between start and end time for given production_line/ machine and
    signal name

    :param start_time_datetime: The start time of the state.
    :type start_time_datetime: datetime

    :param end_time_datetime: The end time of the state
    :type end_time_datetime: datetime

    :param production_line: Name of production line or machine
    :type production_line: str

    :param state: The state of machine/production line
    :type state: str

    :return: Total time the machine/ production_line was in the given state in seconds
    :rtype: float
    """

    collection = get_mongo_collection()

    result_1 = collection.aggregate(get_exceed_group_template(signalname=state, production_line=production_line,
                                                              start_time_datetime=start_time_datetime,
                                                              end_time_datetime=end_time_datetime))

    result_2 = collection.aggregate(get_within_group_template(signalname=state, production_line=production_line,
                                                              start_time_datetime=start_time_datetime,
                                                              end_time_datetime=end_time_datetime))

    result_3 = collection.aggregate(get_between_head_group_template(signalname=state, production_line=production_line,
                                                                    start_time_datetime=start_time_datetime,
                                                                    end_time_datetime=end_time_datetime))

    result_4 = collection.aggregate(get_between_tail_group_template(signalname=state, production_line=production_line,
                                                                    start_time_datetime=start_time_datetime,
                                                                    end_time_datetime=end_time_datetime))

    results = [list(result_1), list(result_2), list(result_3), list(result_4)]

    total_seconds = 0

    for result in results:

        if result:
            total_seconds += float(result[0]['TOTAL_TIME_SECONDS'])

    # print("Total Time in seconds: ", total_seconds)

    return total_seconds


def get_total_time_state(start_time_datetime, end_time_datetime, production_line: str = r".*",
                         state="DISCONNECT"):
    """
    Function to get the total number of seconds between start and end time for given production_line/ machine and
    signal name

    :param start_time_datetime: The start time of the state.
    :type start_time_datetime: datetime

    :param end_time_datetime: The end time of the state
    :type end_time_datetime: datetime

    :param production_line: Name of production line or machine
    :type production_line: str

    :param state: The state of machine/production line
    :type state: str

    :return: Total time the machine/ production_line was in the given state in seconds
    :rtype: float
    """

    collection = get_mongo_collection()

    result_1 = collection.aggregate(get_exceed_group_template(signalname=state, production_line=production_line,
                                                              start_time_datetime=start_time_datetime,
                                                              end_time_datetime=end_time_datetime))

    result_2 = collection.aggregate(get_within_group_template(signalname=state, production_line=production_line,
                                                              start_time_datetime=start_time_datetime,
                                                              end_time_datetime=end_time_datetime))

    result_3 = collection.aggregate(get_between_head_group_template(signalname=state, production_line=production_line,
                                                                    start_time_datetime=start_time_datetime,
                                                                    end_time_datetime=end_time_datetime))

    result_4 = collection.aggregate(get_between_tail_group_template(signalname=state, production_line=production_line,
                                                                    start_time_datetime=start_time_datetime,
                                                                    end_time_datetime=end_time_datetime))

    results = [list(result_1), list(result_2), list(result_3), list(result_4)]

    total_seconds = 0

    for result in results:

        if result:
            total_seconds += float(result[0]['TOTAL_TIME_SECONDS'])

    # print("Total Time in seconds: ", total_seconds)

    return total_seconds


def get_total_time_day_state(start_time_datetime, end_time_datetime, production_line: str = r".*",
                             state="DISCONNECT"):
    """
    Function to get the total number of seconds in day  for given production_line/ machine and
    signal name

    :param start_time_datetime: The start time of the state.
    :type start_time_datetime: datetime

    :param end_time_datetime: The end time of the state
    :type end_time_datetime: datetime

    :param production_line: Name of production line or machine
    :type production_line: str

    :param state: The state of machine/production line
    :type state: str

    :return: Total time the machine/ production_line was in the given state in seconds
    :rtype: float
    """

    collection = get_mongo_collection()

    result_1 = collection.aggregate(get_exceed_group_day_template(signalname=state, production_line=production_line,
                                                                  start_time_datetime=start_time_datetime,
                                                                  end_time_datetime=end_time_datetime))

    result_2 = collection.aggregate(get_within_group_day_template(signalname=state, production_line=production_line,
                                                                  start_time_datetime=start_time_datetime,
                                                                  end_time_datetime=end_time_datetime))

    result_3 = collection.aggregate(get_between_head_group_day_template(signalname=state,
                                                                        production_line=production_line,
                                                                        start_time_datetime=start_time_datetime,
                                                                        end_time_datetime=end_time_datetime))

    result_4 = collection.aggregate(get_between_tail_group_day_template(signalname=state,
                                                                        production_line=production_line,
                                                                        start_time_datetime=start_time_datetime,
                                                                        end_time_datetime=end_time_datetime))

    results = [list(result_1), list(result_2), list(result_3), list(result_4)]

    total_seconds = 0

    for result in results:

        if result:
            total_seconds += float(result[0]['TOTAL_TIME_SECONDS'])

    # print("Total Time in seconds: ", total_seconds)

    return total_seconds


def get_alarm_summary_data(start_time, end_time, machine_name):
    """
    Function to get all the data required for full alarm summary of a machine between given start and end time

    :param start_time: The start time of the state.
    :type start_time: float

    :param end_time: The end time of the state
    :type end_time: float

    :param machine_name: Name of machine
    :type machine_name: str

    :return: Alarm summary data for machine
    :rtype: dict
    """
    start_time_seconds = start_time / 1000
    end_time_seconds = end_time / 1000

    # Converting the epoch format to datetime format (UTC-just like how it is stored in db)
    start_time_datetime = datetime.fromtimestamp(start_time_seconds, timezone.utc)
    end_time_datetime = datetime.fromtimestamp(end_time_seconds, timezone.utc)

    LOGGER.info(f"Current Start Time: {start_time_datetime}")

    collection = get_mongo_collection(collection="Alarm_History")
    # collection = get_mongo_collection(collection="Alarm History")

    result_1 = collection.aggregate(get_count_group_template(start_time_datetime=start_time_datetime,
                                                             end_time_datetime=end_time_datetime,
                                                             machine_name=machine_name))
    result_1 = list(result_1)

    if not result_1:
        LOGGER.info("Data not available for machine in given time, returning the recent most data")

        end_time_datetime, start_time_datetime = get_recent_most_alarm_time(machine_name=machine_name)

        LOGGER.info(f"Current Start Time: {start_time_datetime}")
        LOGGER.info(f"Current End Time: {end_time_datetime}")

        result_1 = collection.aggregate(get_count_group_template(start_time_datetime=start_time_datetime,
                                                                 end_time_datetime=end_time_datetime,
                                                                 machine_name=machine_name))
        result_1 = list(result_1)

    result_2 = collection.aggregate(get_timespan_group_template(start_time_datetime=start_time_datetime,
                                                                end_time_datetime=end_time_datetime,
                                                                machine_name=machine_name))

    result_2 = list(result_2)

    result_3 = collection.aggregate(get_timeline_group_template(start_time_datetime=start_time_datetime,
                                                                end_time_datetime=end_time_datetime,
                                                                machine_name=machine_name))

    result_3 = list(result_3)

    results = {"data": {"count_data": result_1, "timespan_data": result_2,
                        "timeline_data": result_3}}

    return results


def get_all_states_summary(production_line, start_time_datetime, end_time_datetime):
    """
    Function to get all the states summary of states for a given production line or machine

    :param production_line: The machine name of production_line
    :type production_line: str

    :param start_time_datetime: The start time for the query
    :type start_time_datetime: datetime

    :param end_time_datetime: The end time for the query
    :type end_time_datetime: datetime

    :return: Dictionary of total time for each state of machines/production_line
    :rtype: dict
    """
    states = {"OPERATE": 0, "MANUAL": 0, "STOP": 0, "ALARM": 0,
              "EMERGENCY": 0, "SUSPEND": 0, "DISCONNECT": 0}

    for state in states.keys():
        states[state] = get_total_time_state(state=state, production_line=production_line,
                                             start_time_datetime=start_time_datetime,
                                             end_time_datetime=end_time_datetime)
    # pprint.pprint(states)

    return states


def get_all_states_day_summary(production_line, start_time_datetime, end_time_datetime):
    """
    Function to get all the states summary of states for a given production line or machine

    :param production_line: The machine name of production_line
    :type production_line: str

    :param start_time_datetime: The start time for the query
    :type start_time_datetime: datetime

    :param end_time_datetime: The end time for the query
    :type end_time_datetime: datetime

    :return: Dictionary of total time for each state of machines/production_line
    :rtype: dict
    """
    states = {"OPERATE": 0, "MANUAL": 0, "STOP": 0, "ALARM": 0,
              "EMERGENCY": 0, "SUSPEND": 0, "DISCONNECT": 0}

    for state in states.keys():
        states[state] = get_total_time_day_state(state=state, production_line=production_line,
                                                 start_time_datetime=start_time_datetime,
                                                 end_time_datetime=end_time_datetime)
    # pprint.pprint(states)

    return states


def get_full_day_summary(production_line=r'.*', day: int = 1655596800):
    """
    Function to get the full day summary of a production line/ machine for all states

    :param production_line: The machine name or production line to get the full day summary
    :type production_line: str

    :param day: The epoch timestamp of the date at exactly 12:00 AM
    :type day: int

    :return: Full day's statics for all state of machine
    :rtype: dict
    """

    day_start = int(day)
    day_end = 86400 + day

    time_slots = [(slot, slot + 3600) for slot in range(day_start, day_end - 3600 + 1, 3600)]

    full_day_stats = []

    current_hour = 0

    for current_time in time_slots:
        current_time_stats = get_all_states_summary(production_line=production_line,
                                                    start_time_datetime=datetime.fromtimestamp(current_time[0],
                                                                                               tz=pytz.timezone("UTC")),
                                                    end_time_datetime=datetime.fromtimestamp(current_time[1],
                                                                                             tz=pytz.timezone("UTC")))
        full_day_stats.append({"current_hour_day": current_hour, "data": current_time_stats})
        current_hour += 1
    full_day = {"OPERATE": 0, "MANUAL": 0, "STOP": 0, "ALARM": 0,
                "EMERGENCY": 0, "SUSPEND": 0, "DISCONNECT": 0}

    for hour in full_day_stats:
        for state in full_day.keys():
            full_day[state] += hour["data"][state]

    full_day_stats.append({"current_hour_day": current_hour, "data": full_day})

    pprint.pprint(full_day_stats)

    return full_day_stats


def get_full_month_week_summary(production_line=r'.*', day: int = 1654043400, week=False):
    """
    Function to get the full month summary of a production line/ machine for all states

    :param production_line: The machine name or production line to get the full day summary
    :type production_line: str

    :param day: The epoch timestamp of the first day of the month at exactly 12:00 AM
    :type day: int

    :param week:
    :type week:

    :return: Full day's statics for all state of machine
    :rtype: dict
    """

    # program_start_time = time.time()

    day_start = int(day)

    day_object = datetime.fromtimestamp(day_start, tz=pytz.timezone("UTC"))

    number_of_days = calendar.monthrange(day_object.year, day_object.month)[1]

    if week:
        day_end = 604800 + day
    else:
        day_end = (number_of_days * 86400) + day

    day_slots = [(slot, slot + 86400) for slot in range(day_start, day_end - 86400 + 1, 86400)]

    full_month_week_stats = []

    current_day = 0

    for current_time in day_slots:
        current_time_stats = get_all_states_day_summary(production_line=production_line,
                                                        start_time_datetime=datetime.fromtimestamp(current_time[0],
                                                                                                   tz=pytz.timezone(
                                                                                                       "UTC")),
                                                        end_time_datetime=datetime.fromtimestamp(current_time[1],
                                                                                                 tz=pytz.timezone(
                                                                                                     "UTC")))
        full_month_week_stats.append({"current_hour_day": current_day, "data": current_time_stats})
        current_day += 1

    full_month_week = {"OPERATE": 0, "MANUAL": 0, "STOP": 0, "ALARM": 0,
                       "EMERGENCY": 0, "SUSPEND": 0, "DISCONNECT": 0}

    for day in full_month_week_stats:
        for state in full_month_week.keys():
            full_month_week[state] += day["data"][state]

    full_month_week_stats.append({"current_hour_day": current_day, "data": full_month_week})

    pprint.pprint(full_month_week_stats)

    # print("Total Time For Program: " + str(time.time() - program_start_time))

    return full_month_week_stats


@db_session
def test_function(machine="T_B_OP160", parameter_group_id=1):
    """

    Function to get all parameters for a given machine in a given parameter group (identifier)

    :param machine: The machine for which the parameters are required
    :type machine: str

    :param parameter_group_id: The parameter group identifier
    :type parameter_group_id: int

    :return: List of sorted (by name) parameter (identifier) for the given machine and parameter group
    :rtype: list

    """

    try:

        current_value_base_query = RealTimeParameter. \
            select(lambda parameter: parameter.machine_parameter.id == 3211)

        current_value = list(current_value_base_query.order_by(desc(RealTimeParameter.time)).for_update()[:1])
        print(current_value[0])
        non_ok_data = select(c for c in current_value if c.parameter_condition.id > 1)
        print(list(non_ok_data))
    except Exception as error:
        LOGGER.exception(f"Exception while processing status of machine for given parameter group: {error.args[0]}")
        raise GetAllParameterDBError


@db_session
def set_real_time_active():
    """

    Function to populate the real_time_active table

    :return: List of sorted (by name) parameter (identifier) for the given machine and parameter group
    :rtype: list

    """

    try:
        parameters = select(mp for mp in MachineParameter)

        for parameter in parameters:
            real_time_parameter = RealTimeParameter.select(lambda rp: rp.machine_parameter.id == parameter.id)
            real_time_parameter = list(real_time_parameter.order_by(desc(RealTimeParameter.time)).for_update()[:1])
            if real_time_parameter:
                data_dic = real_time_parameter[0].to_dict()
                real_time_parameter_active = RealTimeParameterActive(**data_dic)
                # commit()
    except Exception as error:
        LOGGER.exception(f"Exception while processing status of machine for given parameter group: {error.args[0]}")
        raise GetAllParameterDBError


@db_session
def test_function_2(required_part_number: str = "2543"):
    """

    Function to get all parameters for a given machine in a given parameter group (identifier)

    :return: List of sorted (by name) parameter (identifier) for the given machine and parameter group
    :rtype: tuple of ()

    """

    try:
        # collection = get_mongo_collection(collection="Alarm History")
        collection = get_mongo_collection(collection="Alarm_History")
        result_1 = collection.aggregate(get_recent_most_alarm_time(machine_name="T_C_OP912"))

        result = list(result_1)[0]["enddate"]
        result_2 = result - timedelta(hours=1)

        print(result)
        print(result_2)

    except Exception as error:
        LOGGER.exception(f"Exception while getting part similar to {required_part_number}")
        raise GetAllParameterDBError


def get_recent_most_alarm_time(machine_name: str = "T_C_OP912"):
    """

    Function to get all parameters for a given machine in a given parameter group (identifier)

    :return: List of sorted (by name) parameter (identifier) for the given machine and parameter group
    :rtype:

    """

    try:

        collection = get_mongo_collection(collection="Alarm_History")
        # collection = get_mongo_collection(collection="Alarm History")

        result_1 = collection.aggregate(get_recent_most_alarm_time_template(machine_name=machine_name))

        result = list(result_1)

        if result:
            end_date = result[0]["enddate"]
            update_date = result[0]["updatedate"]
            update_date = update_date - timedelta(hours=1)

            print(end_date)
            print(update_date)

            return end_date, update_date

    except Exception as error:
        LOGGER.exception(f"Exception while getting part similar to")
        raise GetAllParameterDBError


@db_session
def get_all_machine_spare_details():
    """

    Function to get the states of all machines based on their spare part details

    :return: List of sorted (by name) parameter (identifier) for the given machine and parameter group
    :rtype: tuple of ()

    """

    try:
        query = select((machine.location, machine.name, spare_part.part_name,
                        machine_part_count.part_signal_name, machine_part_count.latest_update_time,
                        machine_part_count.current_part_count,
                        (machine_part_count.current_part_count -
                         spare_part.reference_part_number) > spare_part.warning_limit,
                        (machine_part_count.current_part_count -
                         spare_part.reference_part_number) > spare_part.critical_limit)
                       for machine in Machine
                       for spare_part in SparePart
                       for machine_part_count in MachinePartCount
                       if spare_part.machine == machine and
                       machine_part_count.machine == machine)

        results = list(query)
        all_machines = select((machine.location, machine.name) for machine in Machine
                              if machine.name.startswith('T_'))

        all_machines = list(all_machines)

        # Create DataFrame from query results
        all_machines_df = pd.DataFrame(all_machines, columns=["location", "machine_name"])

        for result in results:
            print(result)

        print("=" * 30)

        columns = ["location", "machine_name", "internal_parameter_name",
                   "actual_parameter_name", "latest_update_time", "cumulative_part_count",
                   "is_warning", "is_critical"]

        # Create DataFrame from query results
        df = pd.DataFrame(results, columns=columns)

        # Initialize group-level dictionary
        group_json = {
            "group_name": "spare_part_status",
            "group_details": [],
            "group_state": "OK",
            "count": {"OK": 0, "WARNING": 0, "CRITICAL": 0}
        }

        # Iterate over unique locations using groupby
        for location, location_data in all_machines_df.groupby('location'):
            location_json = {
                "line_name": location,
                "machines": [],
                "line_state": "OK",
                "count": {"OK": 0, "WARNING": 0, "CRITICAL": 0}
            }

            # Iterate over unique machines within the location using groupby
            for machine_name, machine_data in location_data.groupby('machine_name'):
                machine_json = {
                    "machine_name": machine_name,
                    "parameters": [],
                    "machine_state": "OK"
                }

                # Initialize counts for the machine
                machine_count = {'OK': 0, 'WARNING': 0, 'CRITICAL': 0}

                machine_data_actual = df[(df['location'] == location) & (df['machine_name'] == machine_name)]

                if machine_data_actual.shape[0] != 0:
                    for _, row in machine_data_actual.iterrows():
                        parameter_json = {
                            "internal_parameter_name": row["internal_parameter_name"],
                            "display_name": row["cumulative_part_count"],
                            "actual_parameter_name": row["actual_parameter_name"],
                            "latest_update_time": int(row['latest_update_time'].timestamp() * 1000),
                            "parameter_value": row["cumulative_part_count"],  # Assuming no specific value available
                            "parameter_state": "CRITICAL" if row["is_critical"] else
                            ("WARNING" if row["is_warning"] else "OK"),
                            "warning_limit": 0,  # Set to 0 by default
                            "critical_limit": 0  # Set to 0 by default
                        }

                        machine_json["parameters"].append(parameter_json)

                        if row["is_critical"]:
                            machine_count['CRITICAL'] += 1
                        elif row["is_warning"]:
                            machine_count['WARNING'] += 1

                    # Determine machine state based on machine's counts and increment location stats
                    if machine_count['CRITICAL'] > 0:
                        machine_json['machine_state'] = 'CRITICAL'
                        location_json['count']['CRITICAL'] += 1
                    elif machine_count['WARNING'] > 0:
                        machine_json['machine_state'] = 'WARNING'
                        location_json['count']['WARNING'] += 1
                    else:
                        location_json['count']['OK'] += 1

                else:
                    location_json['count']['OK'] += 1

                location_json['machines'].append(machine_json)

            # Determine location state based on location's counts
            if location_json['count']['CRITICAL'] > 0:
                location_json['line_state'] = 'CRITICAL'
            elif location_json['count']['WARNING'] > 0:
                location_json['line_state'] = 'WARNING'

            # Update counts for the group state
            group_json['count']['OK'] += location_json['count']['OK']
            group_json['count']['WARNING'] += location_json['count']['WARNING']
            group_json['count']['CRITICAL'] += location_json['count']['CRITICAL']

            group_json['group_details'].append(location_json)

            # Determine location state based on location's counts
        if group_json['count']['CRITICAL'] > 0:
            group_json['group_state'] = 'CRITICAL'
        elif group_json['count']['WARNING'] > 0:
            group_json['group_state'] = 'WARNING'

        return group_json
    except Exception as error:
        LOGGER.exception(f"Exception")
        raise GetAllParameterDBError


@db_session
def get_spare_part_states():
    """

    Function to get all parameters for a given machine in a given parameter group (identifier)

    :return: List of sorted (by name) parameter (identifier) for the given machine and parameter group
    :rtype: tuple of ()

    """

    try:
        # Selecting only the parameters that are in warning state, and grouping them by
        # Parameter Group and getting the count of parameters in the group
        warning_machine_part = select((part.machine.name, pony_count(part.machine))
                                      for part in SparePart
                                      for mpc in MachinePartCount
                                      if mpc.machine == part.machine and
                                      (mpc.current_part_count - part.reference_part_number) > part.warning_limit and
                                      (mpc.current_part_count - part.reference_part_number) < part.critical_limit)

        warning_machine_part = [cmp[0] for cmp in warning_machine_part]

        critical_machine_part = select((part.machine.name, pony_count(part.machine))
                                       for part in SparePart
                                       for mpc in MachinePartCount
                                       if mpc.machine == part.machine and
                                       (mpc.current_part_count - part.reference_part_number) > part.critical_limit)

        critical_machine_part = [cmp[0] for cmp in critical_machine_part]

        LOGGER.info(f"Critical Spare Machine: {critical_machine_part}")
        LOGGER.info(f"Warning Spare Machine: {warning_machine_part}")

        print(f"Critical Spare Machine: {critical_machine_part}")
        print(f"Warning Spare Machine: {warning_machine_part}")

        return warning_machine_part, critical_machine_part
    except Exception as error:
        LOGGER.exception(f"Exception")
        raise GetAllParameterDBError


@db_session
def get_maintenance_activities(start_time=1608008392000, end_time=1808058452000):
    """

    Function to get all maintenance activities

    :return: List of sorted (by name) parameter (identifier) for the given machine and parameter group
    :rtype: tuple of ()

    """

    try:
        start_time_seconds = start_time / 1000
        end_time_seconds = end_time / 1000

        # Converting the epoch format to datetime format (UTC-just like how it is stored in db)
        start_time_datetime = datetime.fromtimestamp(start_time_seconds, timezone.utc)
        end_time_datetime = datetime.fromtimestamp(end_time_seconds, timezone.utc)

        LOGGER.info(f"The start time of the query in epoch mill is {start_time}")
        LOGGER.info(f"The start time of the query is {str(start_time_datetime)}")
        LOGGER.info(f"The end time of the query in epoch mill is {end_time}")
        LOGGER.info(f"The end time of the query is {str(end_time_datetime)}")

        # Query the database for relevant data
        pending_activities_result = select(
            (mc.location,
             mc.name,
             pg.group_name,
             mp.name,
             mp.display_name,
             coract.date_of_identification,
             coract.latest_occurrence,
             coract.target_date_of_completion,
             coract.number_of_occurrences,
             coract.corrective_measurement,
             coract.spare_required,
             coract.support_needed,
             coract.responsible_person,
             coract.priority,
             coract.recent_value,
             mp.warning_limit,
             mp.critical_limit,
             coract.parameter_condition.name)
            for coract in CorrectiveActivity
            for mp in MachineParameter
            for pg in ParameterGroup
            for mc in Machine
            if (
                    coract.machine_parameter == mp and
                    mp.parameter_group == pg and
                    mp.machine == mc and
                    coract.date_of_identification >= start_time_datetime and
                    coract.date_of_identification <= end_time_datetime
            )
        ).order_by(lambda machine_location, _machine_name, pg_group_name,
                          parameter_name, display_name, date_of_identification, latest_occurrence,
                          target_date_of_completion, number_of_occurrences, corrective_measurement, spare_required,
                          support_needed, responsible_person, priority, recent_value,
                          warning_limit, critical_limit, condition: date_of_identification)

        pending_activities_result = list(pending_activities_result)

        if not pending_activities_result:
            LOGGER.info("Data not there for given time, getting recent most available Pending")
            # Query the database for relevant data
            pending_activities_result = select(
                (mc.location,
                 mc.name,
                 pg.group_name,
                 mp.name,
                 mp.display_name,
                 coract.date_of_identification,
                 coract.latest_occurrence,
                 coract.target_date_of_completion,
                 coract.number_of_occurrences,
                 coract.corrective_measurement,
                 coract.spare_required,
                 coract.support_needed,
                 coract.responsible_person,
                 coract.priority,
                 coract.recent_value,
                 mp.warning_limit,
                 mp.critical_limit,
                 coract.parameter_condition.name)
                for coract in CorrectiveActivity
                for mp in MachineParameter
                for pg in ParameterGroup
                for mc in Machine
                if (
                        coract.machine_parameter == mp and
                        mp.parameter_group == pg and
                        mp.machine == mc
                )
            ).order_by(lambda machine_location, _machine_name, pg_group_name,
                              parameter_name, display_name, date_of_identification, latest_occurrence,
                              target_date_of_completion, number_of_occurrences, corrective_measurement,
                              spare_required, support_needed, responsible_person,
                              abnorm_priority, recent_value, warning_limit,
                              critical_limit, para_condition: desc(date_of_identification))[:10]

            pending_activities_result = list(pending_activities_result)

        # Convert the result to a list of dictionaries
        pending_activities = []
        for activity_index in range(len(pending_activities_result)):
            target_doc = pending_activities_result[activity_index][7].strftime('%Y-%m-%d') \
                if pending_activities_result[activity_index][7] else ""

            priority = pending_activities_result[activity_index][13] \
                if pending_activities_result[activity_index][13] else ""

            if pending_activities_result[activity_index][12]:
                resp_id = pending_activities_result[activity_index][12].company_id
                resp_username = pending_activities_result[activity_index][12].username
            else:
                resp_id = None
                resp_username = None

            if not math.isnan(pending_activities_result[activity_index][15]):
                warning_limit_pending = pending_activities_result[activity_index][15]
            else:
                warning_limit_pending = None

            if not math.isnan(pending_activities_result[activity_index][16]):
                critical_limit_pending = pending_activities_result[activity_index][16]
            else:
                critical_limit_pending = None

            activity_dict = dict(
                id=activity_index + 1,
                location=pending_activities_result[activity_index][0],
                name=pending_activities_result[activity_index][1],
                group_name=pending_activities_result[activity_index][2],
                parameter_name=pending_activities_result[activity_index][3],
                axis_name=pending_activities_result[activity_index][4],
                date_of_identification=pending_activities_result[activity_index][5].timestamp() * 1000,
                latest_occurrence=pending_activities_result[activity_index][6].timestamp() * 1000,
                target_date_of_completion=target_doc,
                number_of_occurrences=pending_activities_result[activity_index][8],
                corrective_measurement=pending_activities_result[activity_index][9],
                spare_required=pending_activities_result[activity_index][10],
                support_needed=pending_activities_result[activity_index][11],
                responsible_person_company_id=resp_id,
                responsible_person_username=resp_username,
                priority=priority,
                recent_value=pending_activities_result[activity_index][14],
                warning_limit=warning_limit_pending,
                critical_limit=critical_limit_pending,
                condition=pending_activities_result[activity_index][17],
                status="Pending"
            )
            pending_activities.append(activity_dict)

        # Querying the real time data from the database for given parameter and
        # Time and sorting them using timestamp
        history = select(
            (mc.location,
             mc.name,
             pg.group_name,
             mp.name,
             mp.display_name,
             history.date_of_identification,
             history.latest_occurrence,
             history.target_date_of_completion,
             history.actual_date_of_completion,
             history.number_of_occurrences,
             history.corrective_measurement,
             history.spare_required,
             history.support_needed,
             history.responsible_person,
             history.priority,
             history.recent_value,
             mp.warning_limit,
             mp.critical_limit,
             history.parameter_condition.name)

            for history in ActivityHistory
            for mp in MachineParameter
            for pg in ParameterGroup
            for mc in Machine
            if (
                    history.machine_parameter == mp and
                    mp.parameter_group == pg and
                    mp.machine == mc and
                    history.date_of_identification >= start_time_datetime and
                    history.date_of_identification <= end_time_datetime
            )
        ).order_by(lambda machine_location, _machine_name, pg_group_name,
                          parameter_name, display_name, date_of_identification, latest_occurrence,
                          target_date_of_completion, actual_date_of_completion,
                          number_of_occurrences, corrective_measurement, spare_required,
                          support_needed, responsible_person, abnorm_priority, recent_value, warning_limit,
                          critical_limit, para_condition: date_of_identification)

        history = list(history)

        if not history:
            LOGGER.info("Data not there for given time, getting recent most available, History")
            # Querying the real time data from the database for given parameter and
            # Time and sorting them using timestamp
            history = select(
                (mc.location,
                 mc.name,
                 pg.group_name,
                 mp.name,
                 mp.display_name,
                 history.date_of_identification,
                 history.latest_occurrence,
                 history.target_date_of_completion,
                 history.actual_date_of_completion,
                 history.number_of_occurrences,
                 history.corrective_measurement,
                 history.spare_required,
                 history.support_needed,
                 history.responsible_person,
                 history.priority,
                 history.recent_value,
                 mp.warning_limit,
                 mp.critical_limit,
                 history.parameter_condition.name)

                for history in ActivityHistory
                for mp in MachineParameter
                for pg in ParameterGroup
                for mc in Machine
                if (
                        history.machine_parameter == mp and
                        mp.parameter_group == pg and
                        mp.machine == mc
                )
            ).order_by(lambda machine_location, _machine_name, pg_group_name,
                              parameter_name, display_name, date_of_identification, latest_occurrence,
                              target_date_of_completion, actual_date_of_completion,
                              number_of_occurrences, corrective_measurement, spare_required,
                              support_needed, responsible_person, abnorm_priority, recent_value, warning_limit,
                              critical_limit, para_condition: desc(date_of_identification))[:10]

            history = list(history)

        # Convert the result to a list of dictionaries
        history_dict = []

        for activity_index in range(len(history)):

            target_doc = history[activity_index][7].strftime('%Y-%m-%d') \
                if history[activity_index][7] else ""

            history_priority = history[activity_index][14] \
                if history[activity_index][14] else ""

            if history[activity_index][13]:
                resp_id = history[activity_index][13].company_id
                resp_username = history[activity_index][13].username
            else:
                resp_id = None
                resp_username = None

            if not math.isnan(history[activity_index][16]):
                warning_limit_history = history[activity_index][16]
            else:
                warning_limit_history = None

            if not math.isnan(history[activity_index][17]):
                critical_limit_history = history[activity_index][17]
            else:
                critical_limit_history = None

            activity_dict = dict(
                id=activity_index + 1,
                location=history[activity_index][0],
                name=history[activity_index][1],
                group_name=history[activity_index][2],
                parameter_name=history[activity_index][3],
                axis_name=history[activity_index][4],
                date_of_identification=history[activity_index][5].timestamp() * 1000,
                latest_occurrence=history[activity_index][6].timestamp() * 1000,
                target_date_of_completion=target_doc,
                actual_date_of_completion=history[activity_index][8].strftime('%Y-%m-%d'),
                number_of_occurrences=history[activity_index][9],
                corrective_measurement=history[activity_index][10],
                spare_required=history[activity_index][11],
                support_needed=history[activity_index][12],
                responsible_person_company_id=resp_id,
                responsible_person_username=resp_username,
                priority=history_priority,
                recent_value=history[activity_index][15],
                warning_limit=warning_limit_history,
                critical_limit=critical_limit_history,
                condition=history[activity_index][18]
            )
            history_dict.append(activity_dict)

        abnormality_summary = get_abnormalities_summary(start_time_datetime, end_time_datetime)

        response = {"pending": pending_activities, "completed": history_dict,
                    "abnormality_summary": abnormality_summary}
        LOGGER.info("*" * 100)
        LOGGER.info(response)

        return response

    except Exception as error:
        LOGGER.exception(f"Exception while processing status of machine for given parameter: {error.args[0]}")


# pending activity filtring using the paramter name

@db_session
def get_maintenance_activities_parameter(parameter_name: str):
    """
    Function to get all maintenance activities

    :return: List of sorted (by name) parameter (identifier) for the given machine and parameter group
    :rtype: tuple of ()
    """

    try:
        machine_parameter = MachineParameter.get(name=parameter_name)

        if not machine_parameter:
            return {"error": f"Parameter '{parameter_name}' not found."}

        # Query the database for relevant data
        pending_activities_result = select(
            (mc.location,
             mc.name,
             pg.group_name,
             mp.name,
             mp.display_name,
             coract.date_of_identification,
             coract.latest_occurrence,
             coract.target_date_of_completion,
             coract.number_of_occurrences,
             coract.corrective_measurement,
             coract.spare_required,
             coract.support_needed,
             coract.responsible_person,
             coract.priority,
             coract.recent_value,
             mp.warning_limit,
             mp.critical_limit,
             coract.parameter_condition.name)
            for coract in CorrectiveActivity
            for mp in MachineParameter
            for pg in ParameterGroup
            for mc in Machine
            if (
                    coract.machine_parameter == mp and
                    mp.parameter_group == pg and
                    mp.machine == mc and
                    coract.machine_parameter == machine_parameter
            )
        ).order_by(lambda machine_location, _machine_name, pg_group_name,
                          parameter_name, display_name, date_of_identification, latest_occurrence,
                          target_date_of_completion, number_of_occurrences, corrective_measurement, spare_required,
                          support_needed, responsible_person, priority, recent_value,
                          warning_limit, critical_limit, condition: date_of_identification)

        pending_activities_result = list(pending_activities_result)
        # Check if no data found for pending activities
        # if not pending_activities_result:
        #     # If no pending activities found, return default response
        #     return {"pending": [{
        #         "id": 1,
        #         "location": None,
        #         "name": machine_parameter.name,
        #         "group_name": None,
        #         "parameter_name": parameter_name,
        #         "axis_name": None,
        #         "date_of_identification": None,
        #         "latest_occurrence": None,
        #         "target_date_of_completion": None,
        #         "number_of_occurrences": None,
        #         "corrective_measurement": None,
        #         "spare_required": None,
        #         "support_needed": None,
        #         "responsible_person_company_id": None,
        #         "responsible_person_username": None,
        #         "priority": None,
        #         "recent_value": None,
        #         "warning_limit": None,
        #         "critical_limit": None,
        #         "condition": None,
        #         "status": None
        #     }], "completed": [{
        #         "id": 1,
        #         "location": None,
        #         "name": machine_parameter.name,
        #         "group_name": None,
        #         "parameter_name": parameter_name,
        #         "axis_name": None,
        #         "date_of_identification": None,
        #         "latest_occurrence": None,
        #         "target_date_of_completion": None,
        #         "actual_date_of_completion": None,
        #         "number_of_occurrences": None,
        #         "corrective_measurement": None,
        #         "spare_required": None,
        #         "support_needed": None,
        #         "responsible_person_company_id": None,
        #         "responsible_person_username": None,
        #         "priority": None,
        #         "recent_value": None,
        #         "warning_limit": None,
        #         "critical_limit": None,
        #         "condition": None
        #     }],
        #         "abnormality_summary": [{"line": "Overall", "WARNING": 0, "CRITICAL": 0, "COMPLETED": 0}]}

        # Convert the result to a list of dictionaries
        pending_activities = []
        for activity_index in range(len(pending_activities_result)):
            target_doc = pending_activities_result[activity_index][7].strftime('%Y-%m-%d') \
                if pending_activities_result[activity_index][7] else ""

            priority = pending_activities_result[activity_index][13] \
                if pending_activities_result[activity_index][13] else ""

            if pending_activities_result[activity_index][12]:
                resp_id = pending_activities_result[activity_index][12].company_id
                resp_username = pending_activities_result[activity_index][12].username
            else:
                resp_id = None
                resp_username = None

            if not math.isnan(pending_activities_result[activity_index][15]):
                warning_limit_pending = pending_activities_result[activity_index][15]
            else:
                warning_limit_pending = None

            if not math.isnan(pending_activities_result[activity_index][16]):
                critical_limit_pending = pending_activities_result[activity_index][16]
            else:
                critical_limit_pending = None

            activity_dict = dict(
                id=activity_index + 1,
                location=pending_activities_result[activity_index][0],
                name=pending_activities_result[activity_index][1],
                group_name=pending_activities_result[activity_index][2],
                parameter_name=pending_activities_result[activity_index][3],
                axis_name=pending_activities_result[activity_index][4],
                date_of_identification=pending_activities_result[activity_index][5].timestamp() * 1000,
                latest_occurrence=pending_activities_result[activity_index][6].timestamp() * 1000,
                target_date_of_completion=target_doc,
                number_of_occurrences=pending_activities_result[activity_index][8],
                corrective_measurement=pending_activities_result[activity_index][9],
                spare_required=pending_activities_result[activity_index][10],
                support_needed=pending_activities_result[activity_index][11],
                responsible_person_company_id=resp_id,
                responsible_person_username=resp_username,
                priority=priority,
                recent_value=pending_activities_result[activity_index][14],
                warning_limit=warning_limit_pending,
                critical_limit=critical_limit_pending,
                condition=pending_activities_result[activity_index][17],
                status="Pending"
            )
            pending_activities.append(activity_dict)

        # Querying the real-time data from the database for given parameter and
        # Time and sorting them using timestamp
        history = select(
            (mc.location,
             mc.name,
             pg.group_name,
             mp.name,
             mp.display_name,
             history.date_of_identification,
             history.latest_occurrence,
             history.target_date_of_completion,
             history.actual_date_of_completion,
             history.number_of_occurrences,
             history.corrective_measurement,
             history.spare_required,
             history.support_needed,
             history.responsible_person,
             history.priority,
             history.recent_value,
             mp.warning_limit,
             mp.critical_limit,
             history.parameter_condition.name)

            for history in ActivityHistory
            for mp in MachineParameter
            for pg in ParameterGroup
            for mc in Machine
            if (
                    history.machine_parameter == machine_parameter and
                    history.machine_parameter == mp and
                    mp.parameter_group == pg and
                    mp.machine == mc and
                    history.machine_parameter == machine_parameter

            )
        ).order_by(lambda machine_location, _machine_name, pg_group_name,
                          parameter_name, display_name, date_of_identification, latest_occurrence,
                          target_date_of_completion, actual_date_of_completion,
                          number_of_occurrences, corrective_measurement, spare_required,
                          support_needed, responsible_person, abnorm_priority, recent_value, warning_limit,
                          critical_limit, para_condition: date_of_identification)

        history = list(history)

        # Convert the result to a list of dictionaries
        history_dict = []

        for activity_index in range(len(history)):

            target_doc = history[activity_index][7].strftime('%Y-%m-%d') \
                if history[activity_index][7] else ""

            history_priority = history[activity_index][14] \
                if history[activity_index][14] else ""

            if history[activity_index][13]:
                resp_id = history[activity_index][13].company_id
                resp_username = history[activity_index][13].username
            else:
                resp_id = None
                resp_username = None

            if not math.isnan(history[activity_index][16]):
                warning_limit_history = history[activity_index][16]
            else:
                warning_limit_history = None

            if not math.isnan(history[activity_index][17]):
                critical_limit_history = history[activity_index][17]
            else:
                critical_limit_history = None

            activity_dict = dict(
                id=activity_index + 1,
                location=history[activity_index][0],
                name=history[activity_index][1],
                group_name=history[activity_index][2],
                parameter_name=history[activity_index][3],
                axis_name=history[activity_index][4],
                date_of_identification=history[activity_index][5].timestamp() * 1000,
                latest_occurrence=history[activity_index][6].timestamp() * 1000,
                target_date_of_completion=target_doc,
                actual_date_of_completion=history[activity_index][8].strftime('%Y-%m-%d'),
                number_of_occurrences=history[activity_index][9],
                corrective_measurement=history[activity_index][10],
                spare_required=history[activity_index][11],
                support_needed=history[activity_index][12],
                responsible_person_company_id=resp_id,
                responsible_person_username=resp_username,
                priority=history_priority,
                recent_value=history[activity_index][15],
                warning_limit=warning_limit_history,
                critical_limit=critical_limit_history,
                condition=history[activity_index][18]
            )
            history_dict.append(activity_dict)

        abnormality_summary = get_abnormalities_summary_parameter(pending_activities, history_dict, parameter_name)

        response = {"pending": pending_activities, "completed": history_dict,
                    "abnormality_summary": abnormality_summary}
        LOGGER.info("*" * 100)
        LOGGER.info(response)

        return response

    except Exception as error:
        LOGGER.exception(f"Exception while processing status of machine for given parameter: {error.args[0]}")
        # Handling the case where no data is found for the given parameter


# @db_session
# def update_maintenance_activities(activities):
#     for activity_model in activities:
#
#         try:
#             corrective_activity = CorrectiveActivity.get(
#                 lambda ca: ca.machine_parameter.name == activity_model.parameter_name)
#
#             if corrective_activity:
#                 if activity_model.status == 'Completed':
#                     if activity_model.responsible_person_company_id:
#                         responsible_person_company_id = activity_model.responsible_person_company_id
#                         responsible_person = select(user for user in UserPony if
#                                                     user.company_id == responsible_person_company_id)[:][0]
#
#                         # The priority is by default set to "C"
#                         history_priority = "C"
#
#                         if corrective_activity.priority:
#                             history_priority = corrective_activity.priority
#
#                         target_date_of_completion = date.fromisoformat(
#                             activity_model.target_date_of_completion)
#
#                         # Create a new entry in ActivityHistory
#                         activity_history = ActivityHistory(
#                             date_of_identification=corrective_activity.date_of_identification,
#                             machine_parameter=corrective_activity.machine_parameter,
#                             latest_occurrence=corrective_activity.latest_occurrence,
#                             target_date_of_completion=target_date_of_completion,
#                             number_of_occurrences=corrective_activity.number_of_occurrences,
#                             corrective_measurement=activity_model.corrective_measurement,
#                             spare_required=activity_model.spare_required,
#                             support_needed=activity_model.support_needed,
#                             responsible_person=responsible_person,
#                             actual_date_of_completion=datetime.now().date(),
#                             parameter_condition=corrective_activity.parameter_condition,
#                             recent_value=corrective_activity.recent_value,
#                             priority=history_priority
#                         )
#
#                         commit()
#
#                     # Delete entry from CorrectiveActivity
#                     corrective_activity.delete()
#
#                     commit()
#                 else:
#                     updating_dict = activity_model.dict()
#                     if activity_model.responsible_person_company_id:
#                         responsible_person_company_id = activity_model.responsible_person_company_id
#                         responsible_person = select(user for user in UserPony if
#                                                     user.company_id == responsible_person_company_id)[:]
#
#                         updating_dict.pop("responsible_person_company_id")
#                         updating_dict["responsible_person"] = responsible_person[0]
#
#                     if not updating_dict["priority"]:
#                         updating_dict.pop("priority")
#
#                     updating_dict.pop("parameter_name")
#                     updating_dict.pop("status")
#
#                     # Check if the date is present before converting
#                     if updating_dict["target_date_of_completion"]:
#                         updating_dict["target_date_of_completion"] = date.fromisoformat(
#                             updating_dict["target_date_of_completion"])
#                     else:
#                         # Remove the key if the date is empty
#                         updating_dict.pop("target_date_of_completion")
#
#                     updating_dict = {key: value for key, value in updating_dict.items() if value is not None}
#
#                     # Update values in CorrectiveActivity
#                     corrective_activity.set(**updating_dict)
#                     commit()
#         except Exception as e:
#             LOGGER.error(f"Error processing activity for parameter_name {activity_model.parameter_name}: {str(e)}")
#


@db_session
def update_maintenance_activities(activities):
    for activity_model in activities:
        try:
            # LOGGER.info(f"Processing activity: {activity_model}")

            # Use select instead of get to handle multiple matches
            corrective_activities = select(ca for ca in CorrectiveActivity
                                           if ca.machine_parameter.name == activity_model.parameter_name)[:]

            # LOGGER.info(f"Found {len(corrective_activities)} corrective activities")

            for corrective_activity in corrective_activities:
                # LOGGER.info(f"Processing corrective activity: {corrective_activity}")

                if activity_model.status == 'Completed':
                    # LOGGER.info("Activity status is Completed")
                    if activity_model.responsible_person_company_id:
                        responsible_person_company_id = activity_model.responsible_person_company_id
                        responsible_person = select(user for user in UserPony if
                                                    user.company_id == responsible_person_company_id)[:][0]

                        history_priority = "C" if not corrective_activity.priority else corrective_activity.priority

                        target_date_of_completion = date.fromisoformat(
                            activity_model.target_date_of_completion)

                        # LOGGER.info("Creating ActivityHistory entry")
                        activity_history = ActivityHistory(
                            date_of_identification=corrective_activity.date_of_identification,
                            machine_parameter=corrective_activity.machine_parameter,
                            latest_occurrence=corrective_activity.latest_occurrence,
                            target_date_of_completion=target_date_of_completion,
                            number_of_occurrences=corrective_activity.number_of_occurrences,
                            corrective_measurement=activity_model.corrective_measurement,
                            spare_required=activity_model.spare_required,
                            support_needed=activity_model.support_needed,
                            responsible_person=responsible_person,
                            actual_date_of_completion=datetime.now().date(),
                            parameter_condition=corrective_activity.parameter_condition,
                            recent_value=corrective_activity.recent_value,
                            priority=history_priority
                        )

                        # LOGGER.info("Committing ActivityHistory")
                        commit()

                        # LOGGER.info("Deleting CorrectiveActivity")
                        corrective_activity.delete()

                        # LOGGER.info("Committing deletion")
                        commit()
                else:
                    # LOGGER.info("Updating CorrectiveActivity")
                    updating_dict = activity_model.dict()
                    if activity_model.responsible_person_company_id:
                        responsible_person_company_id = activity_model.responsible_person_company_id
                        responsible_person = select(user for user in UserPony if
                                                    user.company_id == responsible_person_company_id)[:]

                        updating_dict.pop("responsible_person_company_id")
                        updating_dict["responsible_person"] = responsible_person[0]

                    if not updating_dict["priority"]:
                        updating_dict.pop("priority")

                    updating_dict.pop("parameter_name")
                    updating_dict.pop("status")

                    if updating_dict["target_date_of_completion"]:
                        updating_dict["target_date_of_completion"] = date.fromisoformat(
                            updating_dict["target_date_of_completion"])
                    else:
                        updating_dict.pop("target_date_of_completion")

                    updating_dict = {key: value for key, value in updating_dict.items() if value is not None}

                    corrective_activity.set(**updating_dict)
                    LOGGER.info("Committing update")
                    commit()

            if not corrective_activities:
                LOGGER.warning(f"No CorrectiveActivity found for parameter_name: {activity_model.parameter_name}")
        except Exception as e:
            LOGGER.error(f"Error processing activity for parameter_name {activity_model.parameter_name}: {str(e)}")
            LOGGER.exception("Detailed traceback:")


@db_session
def get_maintenance_activities_parameter_new(parameter_name: str):
    """
    Function to get all maintenance activities

    :return: List of sorted (by name) parameter (identifier) for the given machine and parameter group
    :rtype: tuple of ()
    """

    try:
        machine_parameter = MachineParameter.get(name=parameter_name)

        if not machine_parameter:
            return {"error": f"Parameter '{parameter_name}' not found."}

        # LOGGER.info(f'{CorrectiveActivity.select()}')
        # Query the database for relevant data
        pending_activities_result = select(
            (mc.location,
             mc.name,
             pg.group_name,
             mp.name,
             mp.display_name,
             coract.date_of_identification,
             coract.latest_occurrence,
             coract.target_date_of_completion,
             coract.number_of_occurrences,
             coract.corrective_measurement,
             coract.spare_required,
             coract.support_needed,
             coract.responsible_person,
             coract.priority,
             coract.recent_value,
             mp.warning_limit,
             mp.critical_limit,
             coract.parameter_condition.name)
            for coract in CorrectiveActivity
            for mp in MachineParameter
            for pg in ParameterGroup
            for mc in Machine
            if (
                    coract.machine_parameter == mp and
                    mp.parameter_group == pg and
                    mp.machine == mc and
                    coract.machine_parameter == machine_parameter
            )
        ).order_by(lambda machine_location, _machine_name, pg_group_name,
                          parameter_name, display_name, date_of_identification, latest_occurrence,
                          target_date_of_completion, number_of_occurrences, corrective_measurement, spare_required,
                          support_needed, responsible_person, priority, recent_value,
                          warning_limit, critical_limit, condition: date_of_identification)

        pending_activities_result = list(pending_activities_result)

        # TODO: Implement Corrective Activity updation via per parameter coming from parameter graph view.
        temp_parameter = select((mp.machine.name, mp.name, mp.parameter_type, mp.warning_limit, mp.critical_limit)
                                for mp in MachineParameter
                                for pg in ParameterGroup
                                for mc in Machine
                                if (
                                        mp.parameter_group == pg and
                                        mp.machine == mc and
                                        mp.name == machine_parameter.name
                                )
                                )[:][0]

        LOGGER.info(temp_parameter)
        collection = get_mongo_collection(collection="L1Signal_Pool_Active")

        real_time_data_mtlinki = collection.aggregate(
            get_recent_active_pool_value(machine_name=temp_parameter[0], parameter_name=temp_parameter[1]))

        real_time_data_mtlinki = list(real_time_data_mtlinki)

        recent_condition = 1
        recent_value = real_time_data_mtlinki[0]['value']
        recent_updatedate = real_time_data_mtlinki[0]['updatedate']

        LOGGER.info(real_time_data_mtlinki)

        if temp_parameter[2] == "decreasing":
            if (recent_value != None and recent_value <= temp_parameter[4]):
                recent_condition = 3

            if (recent_value != None and (recent_value <= temp_parameter[3] and recent_value > temp_parameter[4])):
                recent_condition = 2

        elif temp_parameter[2] == "increasing":
            if (recent_value != None and recent_value >= temp_parameter[4]):
                recent_condition = 3

            if (recent_value != None and (recent_value >= temp_parameter[3] and recent_value < temp_parameter[4])):
                recent_condition = 2

        elif temp_parameter[2] == "bool":
            if (recent_value != None and recent_value == True):
                recent_condition = 3

            if (recent_value != None and recent_value == False):
                recent_condition = 1

        recent_condition_name = list(map(lambda x: {1: 'OK', 2: 'WARNING', 3: 'CRITICAL'}[x], [recent_condition]))[0]

        # Convert the result to a list of dictionaries
        pending_activities = []
        for activity_index in range(len(pending_activities_result)):
            target_doc = pending_activities_result[activity_index][7].strftime('%Y-%m-%d') \
                if pending_activities_result[activity_index][7] else ""

            priority = pending_activities_result[activity_index][13] \
                if pending_activities_result[activity_index][13] else ""

            if pending_activities_result[activity_index][12]:
                resp_id = pending_activities_result[activity_index][12].company_id
                resp_username = pending_activities_result[activity_index][12].username
            else:
                resp_id = None
                resp_username = None

            if not math.isnan(pending_activities_result[activity_index][15]):
                warning_limit_pending = pending_activities_result[activity_index][15]
            else:
                warning_limit_pending = None

            if not math.isnan(pending_activities_result[activity_index][16]):
                critical_limit_pending = pending_activities_result[activity_index][16]
            else:
                critical_limit_pending = None

            activity_dict = dict(
                id=activity_index + 1,
                location=pending_activities_result[activity_index][0],
                name=pending_activities_result[activity_index][1],
                group_name=pending_activities_result[activity_index][2],
                parameter_name=pending_activities_result[activity_index][3],
                axis_name=pending_activities_result[activity_index][4],
                date_of_identification=pending_activities_result[activity_index][5].timestamp() * 1000,
                latest_occurrence=pending_activities_result[activity_index][6].timestamp() * 1000,
                target_date_of_completion=target_doc,
                number_of_occurrences=pending_activities_result[activity_index][8],
                corrective_measurement=pending_activities_result[activity_index][9],
                spare_required=pending_activities_result[activity_index][10],
                support_needed=pending_activities_result[activity_index][11],
                responsible_person_company_id=resp_id,
                responsible_person_username=resp_username,
                priority=priority,
                recent_value=pending_activities_result[activity_index][14],
                warning_limit=warning_limit_pending,
                critical_limit=critical_limit_pending,
                condition=pending_activities_result[activity_index][17],
                status="Pending"
            )
            pending_activities.append(activity_dict)

        pending_activity_new = []
        if (recent_condition > 1):
            for i in pending_activities:
                if (temp_parameter[1] == i['parameter_name'] and recent_condition_name == i['condition']):
                    i['latest_occurence'] = recent_updatedate
                    i['recent_value'] = recent_value
                    i['number_of_occurrences'] += 1

                    update_dict = {'signalname': machine_parameter.id, 'condition': recent_condition, 'updatedate': recent_updatedate, 'value': recent_value}
                    update_dict_df = pd.DataFrame(update_dict, index=[0])
                    update_operation.update_corrective_activities_from_dataframe(update_dict_df)
                pending_activity_new.append(i)

            if not pending_activity_new:
                insert_dict = {'signalname': machine_parameter.id, 'condition': recent_condition,
                               'updatedate': recent_updatedate, 'value': recent_value}
                insert_dict_df = pd.DataFrame(insert_dict, index=[0])

                table_name = "corrective_activity"
                table_column_names = ("machine_parameters_id", "date_of_identification", "parameter_condition_id",
                                      "recent_value", "latest_occurrence",
                                      "number_of_occurrences")

                db_schema = "tiei_sample_4"

                update_operation.insert_corrective_activities_from_dataframe(insert_dict_df)
                LOGGER.debug("INSERTED DATA INTO TIMESCALEDB corrective_activity")

                new_record = select(
                    (mc.location,
                     mc.name,
                     pg.group_name,
                     mp.name,
                     mp.display_name,
                     mp.warning_limit,
                     mp.critical_limit,)
                    for mp in MachineParameter
                    for pg in ParameterGroup
                    for mc in Machine
                    if (
                            mp.parameter_group == pg and
                            mp.machine == mc and
                            mp.name == machine_parameter.name
                    )
                )[:][0]

                activity_dict_new = dict(
                    location=new_record[0],
                    name=new_record[1],
                    group_name=new_record[2],
                    parameter_name=new_record[3],
                    axis_name=new_record[4],
                    date_of_identification=recent_updatedate,
                    latest_occurrence=recent_updatedate,
                    number_of_occurrences=1,
                    recent_value=recent_value,
                    warning_limit=new_record[5],
                    critical_limit=new_record[6],
                    condition=recent_condition_name,
                    status="Pending"
                )
                pending_activity_new.append(activity_dict_new)
                print(pending_activity_new)
        else:
            pending_activity_new = pending_activities

        # Querying the real-time data from the database for given parameter and
        # Time and sorting them using timestamp
        history = select(
            (mc.location,
             mc.name,
             pg.group_name,
             mp.name,
             mp.display_name,
             history.date_of_identification,
             history.latest_occurrence,
             history.target_date_of_completion,
             history.actual_date_of_completion,
             history.number_of_occurrences,
             history.corrective_measurement,
             history.spare_required,
             history.support_needed,
             history.responsible_person,
             history.priority,
             history.recent_value,
             mp.warning_limit,
             mp.critical_limit,
             history.parameter_condition.name)

            for history in ActivityHistory
            for mp in MachineParameter
            for pg in ParameterGroup
            for mc in Machine
            if (
                    history.machine_parameter == machine_parameter and
                    history.machine_parameter == mp and
                    mp.parameter_group == pg and
                    mp.machine == mc and
                    history.machine_parameter == machine_parameter

            )
        ).order_by(lambda machine_location, _machine_name, pg_group_name,
                          parameter_name, display_name, date_of_identification, latest_occurrence,
                          target_date_of_completion, actual_date_of_completion,
                          number_of_occurrences, corrective_measurement, spare_required,
                          support_needed, responsible_person, abnorm_priority, recent_value, warning_limit,
                          critical_limit, para_condition: date_of_identification)

        history = list(history)

        # Convert the result to a list of dictionaries
        history_dict = []

        for activity_index in range(len(history)):

            target_doc = history[activity_index][7].strftime('%Y-%m-%d') \
                if history[activity_index][7] else ""

            history_priority = history[activity_index][14] \
                if history[activity_index][14] else ""

            if history[activity_index][13]:
                resp_id = history[activity_index][13].company_id
                resp_username = history[activity_index][13].username
            else:
                resp_id = None
                resp_username = None

            if not math.isnan(history[activity_index][16]):
                warning_limit_history = history[activity_index][16]
            else:
                warning_limit_history = None

            if not math.isnan(history[activity_index][17]):
                critical_limit_history = history[activity_index][17]
            else:
                critical_limit_history = None

            activity_dict = dict(
                id=activity_index + 1,
                location=history[activity_index][0],
                name=history[activity_index][1],
                group_name=history[activity_index][2],
                parameter_name=history[activity_index][3],
                axis_name=history[activity_index][4],
                date_of_identification=history[activity_index][5].timestamp() * 1000,
                latest_occurrence=history[activity_index][6].timestamp() * 1000,
                target_date_of_completion=target_doc,
                actual_date_of_completion=history[activity_index][8].strftime('%Y-%m-%d'),
                number_of_occurrences=history[activity_index][9],
                corrective_measurement=history[activity_index][10],
                spare_required=history[activity_index][11],
                support_needed=history[activity_index][12],
                responsible_person_company_id=resp_id,
                responsible_person_username=resp_username,
                priority=history_priority,
                recent_value=history[activity_index][15],
                warning_limit=warning_limit_history,
                critical_limit=critical_limit_history,
                condition=history[activity_index][18]
            )
            history_dict.append(activity_dict)

        abnormality_summary = get_abnormalities_summary_parameter(pending_activity_new, history_dict, parameter_name)

        response = {"pending": pending_activity_new, "completed": history_dict,

                    "abnormality_summary": abnormality_summary}
        LOGGER.info("*" * 100)
        LOGGER.info(response)

        return response

    except Exception as error:
        LOGGER.exception(f"Exception while processing status of machine for given parameter: {error.args[0]}")
        # Handling the case where no data is found for the given parameter



@db_session
def get_similar_part(required_part_number: str = "2543", machine_name: str = "Laser Cladding A"):
    """

    Function to get the part similar to {required_part_number}

    :param required_part_number: The few letters from the required part number

    :param machine_name: The machine name

    :return: the part similar to {required_part_number}
    :rtype: string

    """

    try:
        machine = Machine.get(name=machine_name)

        if machine:
            # Selecting only the parts that are similar to {required_part_number}
            parts = list(select(part for part in MachineProductionTimeline if required_part_number in part.part_number
                                and part.machine == machine))

            if parts:
                parts = [part.part_number for part in parts]
                return parts

    except Exception as error:
        LOGGER.exception(f"Exception while getting part similar to {required_part_number}")
        raise GetAllParameterDBError


@db_session
def get_real_time_data_parts(required_part_number: str = "_3611242204282543",
                             parameter_name: str = "laser_output_monitor_value",
                             machine_name: str = "Laser Cladding A"):
    """

    Function to get the real time data for given part

    :param required_part_number: The few letters from the required part number

    :param parameter_name: The parameter name

    :param machine_name: The machine name

    :return: dictionary of data for the given part
    :rtype: dict

    """

    try:

        machine = Machine.get(name=machine_name)
        if machine:

            # Selecting only the parts that are similar to {required_part_number}
            machine_production = MachineProductionTimeline.get(part_number=required_part_number,
                                                               machine=machine)
            machine_parameters_object = MachineParameter.get(name=parameter_name,
                                                             machine=machine)
            machine_parameters_position_object = MachineParameter.get(name="c_axis_machine_position",
                                                                      machine=machine)
            if machine_production.id:
                real_time_parameter = RealTimeParameter.select(lambda rp: rp.machine_parameter ==
                                                                          machine_parameters_object)
                real_time_parameter = real_time_parameter.filter(lambda rp: rp.time >= machine_production.start_time)
                real_time_parameter = real_time_parameter.filter(lambda rp: rp.time <= machine_production.end_time)
                real_time_parameter = real_time_parameter.order_by(RealTimeParameter.time).for_update()[:]
                real_time_parameter_values = [rp.value for rp in real_time_parameter]

                real_time_parameter_position = RealTimeParameter.select(lambda rp: rp.machine_parameter ==
                                                                                   machine_parameters_position_object)
                real_time_parameter_position = real_time_parameter_position. \
                    filter(lambda rp: rp.time >= machine_production.start_time)

                real_time_parameter_position = real_time_parameter_position. \
                    filter(lambda rp: rp.time <= machine_production.end_time)

                real_time_parameter_position = real_time_parameter_position. \
                                                   order_by(RealTimeParameter.time).for_update()[:]

                real_time_parameter_position = [rp.value for rp in real_time_parameter_position]

                response_data = {"param": parameter_name,
                                 "machine": machine_parameters_object.machine.name,
                                 "data": real_time_parameter_values,
                                 "position": real_time_parameter_position}

                return response_data

    except Exception as error:
        LOGGER.exception(f"Exception while getting real time data for part: {required_part_number}")
        raise GetAllParameterDBError


@db_session
def get_machine_parameters(machine_name="Laser Cladding"):
    """
    Function to get all parameters for a given machine

    :param machine_name: The machine for which the parameters are required
    :type machine_name: str

    :return: List of parameters for the given machine
    :rtype: list

    """

    try:

        # Getting the machine object (table) from the database
        machine = Machine.get(name=machine_name)
        # machine = Machine[61]

        if machine:
            parameters = MachineParameter.select(lambda parameter: parameter.machine.id == machine.id)
            parameters = parameters.order_by(MachineParameter.id)[:]

            # Getting all the parameters of the machine
            parameters = [parameter.name for parameter in parameters]
            LOGGER.info(parameters)
            print(parameters)
            return parameters
    except Exception as error:
        LOGGER.exception(f"Exception while processing status of machine for given parameter group: {error.args[0]}")
        raise GetAllParameterDBError


@db_session
def get_machine_parameters_state(machine_name="Laser Cladding"):
    """
    Function to get all parameters for a given machine with their states (used for spm)

    :param machine_name: The machine for which the parameters are required
    :type machine_name: str

    :return: Dictionary of List of parameters for the given machine
    :rtype: dict
    """

    try:

        # Getting the machine object (table) from the database
        machine = Machine.get(name=machine_name)
        # machine = Machine[61]

        if machine:
            # parameters = MachineParameter.select(lambda parameter: parameter.machine.id == machine.id)
            # parameters = parameters.order_by(MachineParameter.id)[:]

            parameter_states = RealTimeParameterActive.select(lambda parameter:
                                                              parameter.machine_parameter.machine.id == machine.id)
            parameter_states = parameter_states.order_by(RealTimeParameterActive.machine_parameter)[:]

            # Getting all the parameters of the machine
            # parameters = [(parameter.name, state.parameter_condition.id) for parameter, state in zip(
            #     parameters, parameter_states)]

            # Getting all the parameters of the machine
            parameters = [{"name": state.machine_parameter.name, "item_state": state.parameter_condition.name}
                          for state in parameter_states]

            response = {"data": parameters}
            LOGGER.info(response)
            return response

    except Exception as error:
        LOGGER.exception(f"Exception while processing status of machine for given parameter group: {error.args[0]}")
        raise GetAllParameterDBError


@db_session
def get_machine_names(machine_ids):
    machine_status = {}

    for machine_id in machine_ids:
        machine = Machine[machine_id]
        machine_params = MachineParameter.select(lambda mp: mp.machine == machine)[:]

        # Check condition for each machine parameter
        status = "OK"
        for machine_param in machine_params:
            active_param = RealTimeParameterActive.get(machine_parameter=machine_param)
            if active_param and active_param.parameter_condition.id == 3:
                status = "CRITICAL"
                break

        machine_status[machine.name] = status

    return machine_status


@db_session
def get_machine_names_2(machine_ids):
    machine_status = {}

    for machine_id in machine_ids:
        machine = Machine[machine_id]
        machine_params = MachineParameter.select(lambda mp: mp.machine == machine)[:]

        # Check condition for each machine parameter
        status = "OK"
        for machine_param in machine_params:
            active_param = RealTimeParameterActive.get(machine_parameter=machine_param)
            if active_param and active_param.parameter_condition.id == 3:
                status = "CRITICAL"
                break

        machine_status[machine.name] = status

    return machine_status

@db_session
def fetch_update_logs() -> List[UpdateLogResponse]:
    """
    Fetch all update logs from the database and return them as a list of UpdateLogResponse.

    :return: List of update logs as UpdateLogResponse objects
    :rtype: List[UpdateLogResponse]
    """
    logs = select(log for log in UpdateLog)[:]
    response_data = [
        UpdateLogResponse(
            user=log.user,
            parameter_name=log.parameter_name,
            limit_value=log.limit_value,
            reference_signal=log.reference_signal,
            set_type=log.set_type,
            date_changed=log.date_changed,
            previous_limit=log.previous_limit,
        ) for log in logs
    ]
    return response_data

@db_session
def fetch_update_logs_by_user(user: str) -> List[UpdateLogResponse]:
    """
    Fetch update logs from the database filtered by parameter name.

    :param user: The user to filter update logs.
    :return: List of update logs as UpdateLogResponse objects filtered by parameter name.
    :rtype: List[UpdateLogResponse]
    """
    logs = select(log for log in UpdateLog if log.user == user)[:]
    response_data = [
        UpdateLogResponse(
            user=log.user,
            parameter_name=log.parameter_name,
            limit_value=log.limit_value,
            reference_signal=log.reference_signal,
            set_type=log.set_type,
            date_changed=log.date_changed,
            previous_limit=log.previous_limit,
        ) for log in logs
    ]
    return response_data

@db_session
def fetch_update_logs_by_name(parameter_name: str) -> List[UpdateLogResponse]:
    """
    Fetch update logs from the database filtered by parameter name.

    :param parameter_name: The parameter name to filter the update logs.
    :return: List of update logs as UpdateLogResponse objects filtered by parameter name.
    :rtype: List[UpdateLogResponse]
    """
    logs = select(log for log in UpdateLog if log.parameter_name == parameter_name)[:]
    response_data = [
        UpdateLogResponse(
            user=log.user,
            parameter_name=log.parameter_name,
            limit_value=log.limit_value,
            reference_signal=log.reference_signal,
            set_type=log.set_type,
            date_changed=log.date_changed,
            previous_limit=log.previous_limit,
        ) for log in logs
    ]
    return response_data





IST_OFFSET = timedelta(hours=5, minutes=30)

@db_session
def fetch_update_logs_by_time_range(start_time_epoch: float, end_time_epoch: float) -> List[UpdateLogResponse]:
    """
    Fetch update logs from the database filtered by a time range, using epoch timestamps with precision.

    :param start_time_epoch: The start time in epoch milliseconds to filter the update logs.
    :param end_time_epoch: The end time in epoch milliseconds to filter the update logs.
    :return: List of update logs as UpdateLogResponse objects filtered by the time range.
    :rtype: List[UpdateLogResponse]
    """

    if start_time_epoch >= end_time_epoch:
        raise ValueError("Start time must be before end time")

    try:
        # Convert epoch milliseconds to seconds with precision
        start_time_seconds = start_time_epoch / 1000
        end_time_seconds = end_time_epoch / 1000

        # Convert seconds since epoch to datetime in UTC with precision
        start_time_datetime = datetime.fromtimestamp(start_time_seconds, tz=timezone.utc)
        end_time_datetime = datetime.fromtimestamp(end_time_seconds, tz=timezone.utc)

        # Use a simpler query to avoid decompile errors
        logs = select(
            log for log in UpdateLog
            if log.date_changed >= start_time_datetime and log.date_changed <= end_time_datetime
        )[:]

        # Prepare response data
        response_data = [
            UpdateLogResponse(
                user=log.user,
                parameter_name=log.parameter_name,
                limit_value=log.limit_value,
                reference_signal=log.reference_signal,
                set_type=log.set_type,
                # Convert date_changed to IST before sending response
                date_changed=log.date_changed.astimezone(timezone(IST_OFFSET)),
                previous_limit=log.previous_limit,
            ) for log in logs
        ]

        LOGGER.info(f"Fetched {len(response_data)} logs between {start_time_datetime} and {end_time_datetime}")

        return response_data

    except Exception as e:
        LOGGER.error(f"Error fetching update logs: {e}")
        raise

@db_session(optimistic=False)
def get_real_time_layout_data():
    """
    Retrieves real-time parameter data for a specific set of conditions.

    Returns a nested JSON structure containing information about lines,
    machines, and their respective parameters.

    :return: List of JSON objects representing line data
    :rtype: dict
    """

    # Query the database for relevant data
    result = select(
        (m.location,
         m.name,
         mp.name,
         mp.display_name,
         mp.internal_parameter_name,
         rtpa.time,
         rtpa.value,
         mp.warning_limit,
         mp.critical_limit,
         rtpa.parameter_condition.name)
        for rtpa in RealTimeParameterActive
        for mp in MachineParameter
        for pg in ParameterGroup
        for m in Machine
        if (
                rtpa.machine_parameter == mp and
                mp.parameter_group == pg and
                mp.machine == m
        )
    ).order_by(lambda location, machine_name, parameter_name, display_name, internal_parameter_name, timestamp, value, warn_limit, critical_limit, condition_name: (location, machine_name, parameter_name))

    # Convert the result to a pandas DataFrame
    columns = ['location', 'machine_name', 'parameter_name',
               'display_name', 'internal_parameter_name', 'time', 'value', 'warn_limit',
               'critical_limit', 'condition_name']
    result_df = pd.DataFrame(result, columns=columns)
    result_df = result_df.sort_values(by='machine_name', key=lambda col: col.map(alphanumeric_key))

    lines_overview = []

    # Create a nested JSON structure
    json_list = []

    # Iterate over unique locations (lines)
    for location, location_data in result_df.groupby('location'):
        location_json = {'line_name': location, 'machines': [], 'line_state': 'OK',
                         'count': {'OK': 0, 'WARNING': 0, 'CRITICAL': 0}}

        # Create a temporary dictionary to track machine counts
        machine_counts = {'OK': 0, 'WARNING': 0, 'CRITICAL': 0}

        # Iterate over unique machines within the location
        for machine_name, machine_data in location_data.groupby('machine_name', sort=False):
            machine_json = {'machine_name': machine_name, 'parameters': [], 'machine_state': 'OK',
                            'count': {'OK': 0, 'WARNING': 0, 'CRITICAL': 0}}

            # Iterate over parameter data for the machine
            for _, row in machine_data.iterrows():
                # Replace NaN values with None
                warning_limit = row['warn_limit'] if not pd.isna(row['warn_limit']) else None
                critical_limit = row['critical_limit'] if not pd.isna(row['critical_limit']) else None
                parameter_value = None if math.isnan(row['value']) else row['value']

                parameter_json = {
                    'actual_parameter_name': row['parameter_name'],
                    'display_name': row['display_name'],
                    'internal_parameter_name': row['internal_parameter_name'],
                    'latest_update_time': int(row['time'].timestamp() * 1000),
                    'parameter_value': parameter_value,
                    'parameter_state': row['condition_name'],
                    'warning_limit': warning_limit,
                    'critical_limit': critical_limit
                }

                machine_json['parameters'].append(parameter_json)

                # Update counts based on parameter state
                if row['condition_name'] == 'OK':
                    machine_json['count']['OK'] += 1
                elif row['condition_name'] == 'WARNING':
                    machine_json['count']['WARNING'] += 1
                elif row['condition_name'] == 'CRITICAL':
                    machine_json['count']['CRITICAL'] += 1

            # Determine machine state based on counts
            if machine_json['count']['CRITICAL'] > 0:
                machine_json['machine_state'] = 'CRITICAL'
            elif machine_json['count']['WARNING'] > 0:
                machine_json['machine_state'] = 'WARNING'
            else:
                machine_json['machine_state'] = 'OK'

            # Update machine counts for the location
            machine_counts[machine_json['machine_state']] += 1

            location_json['machines'].append(machine_json)

        # Update the line count based on machine counts
        location_json['count']['OK'] = machine_counts['OK']
        location_json['count']['WARNING'] = machine_counts['WARNING']
        location_json['count']['CRITICAL'] = machine_counts['CRITICAL']

        # Determine line state based on counts
        if location_json['count']['CRITICAL'] > 0:
            location_json['line_state'] = 'CRITICAL'
        elif location_json['count']['WARNING'] > 0:
            location_json['line_state'] = 'WARNING'
        else:
            location_json['line_state'] = 'OK'

        json_list.append(location_json)

    response = {"lines": json_list}
    return response


@db_session(optimistic=False)
def get_real_time_parameters_data_mtlinki_new_layout():
    # Get the PostgreSQL data
    machines = select(m.name for m in Machine)
    parameters = select(mp.name for mp in MachineParameter)
    mongodb_q = select(mpg.mongodb_query for mpg in ParameterGroup)

    # Get the MongoDB collection
    collection = get_mongo_collection("L1Signal_Pool_Active")

    # Initialize an empty list to store processed data
    processed_data = []

    # Loop through each machine name from PostgreSQL
    for machine_name in machines:
        # Loop through each parameter using regex pattern from PostgreSQL
        for mongodb_query in mongodb_q:
            # Define the MongoDB query regex pattern
            regex_pattern = re.compile(f".*{mongodb_query}.*")

            # MongoDB aggregation pipeline
            pipeline = [
                {
                    '$match': {
                        'L1Name': machine_name,
                        'signalname': {'$regex': regex_pattern}
                    }
                },
                {
                    '$project': {
                        'L1Name': 1,
                        'signalname': 1,
                        'value': 1
                    }
                }
            ]

            # Execute the aggregation pipeline
            result = collection.aggregate(pipeline)

            # Convert the cursor to a list of dictionaries
            result_list = list(result)

            # Append the processed data to the list
            processed_data.extend(result_list)

    # Convert the processed data to a Pandas DataFrame
    df = pd.DataFrame(processed_data)
    LOGGER.info(df)

    # Query the database for relevant data
    result = select(
        (pg.group_name,
         m.location,
         m.name,
         mp.name,
         mp.display_name,
         mp.internal_parameter_name,
         rtpa.time,
         rtpa.value,
         mp.warning_limit,
         mp.critical_limit,
         rtpa.parameter_condition.name)

        for rtpa in RealTimeParameterActive
        for mp in MachineParameter
        for pg in ParameterGroup
        for m in Machine
        if (
                rtpa.machine_parameter == mp and
                mp.parameter_group == pg and
                mp.machine == m

        )
    ).order_by(lambda _group_name, machine_location, _machine_name,
                      parameter_name, display_name, internal_parameter_name, timestamp, value, warn_limit,
                      _critical_limit, condition_name: (_group_name, machine_location, _machine_name, parameter_name))

    # Convert the result to a pandas DataFrame
    columns = ['group_name', 'location', 'machine_name', 'parameter_name',
               'display_name', 'internal_parameter_name', 'time', 'value', 'warn_limit',
               'critical_limit', 'condition_name']
    result_df = pd.DataFrame(result, columns=columns)
    result_df = result_df.sort_values(by='machine_name', key=lambda col: col.map(alphanumeric_key))

    # Create a nested JSON structure
    json_list = []

    # Iterate over unique locations
    for location, location_data in result_df.groupby('location'):
        location_json = {'line_name': location, 'machines': [], 'line_state': 'OK',
                         'count': {'OK': 0, 'WARNING': 0, 'CRITICAL': 0}}
        # Iterate over unique machines within the location
        for machine_name, machine_data in location_data.groupby('machine_name', sort=False):
            machine_json = {'machine_name': machine_name, 'parameters': [], 'machine_state': 'OK',
                            'count': {'OK': 0, 'WARNING': 0, 'CRITICAL': 0}}

            # Initialize counts for the machine
            machine_count = {'OK': 0, 'WARNING': 0, 'CRITICAL': 0}

            # Iterate over parameter data for the machine
            for _, row in machine_data.iterrows():
                # Replace NaN values with None
                warning_limit = row['warn_limit'] if not pd.isna(row['warn_limit']) else None
                critical_limit = row['critical_limit'] if not pd.isna(row['critical_limit']) else None
                parameter_value = None if math.isnan(row['value']) else row['value']

                parameter_json = {
                    'actual_parameter_name': row['parameter_name'],
                    'display_name': row['display_name'],
                    'internal_parameter_name': row['internal_parameter_name'],
                    'latest_update_time': int(row['time'].timestamp() * 1000),
                    'parameter_value': parameter_value,
                    'parameter_state': row['condition_name'],
                    'warning_limit': warning_limit,
                    'critical_limit': critical_limit
                }

                machine_json['parameters'].append(parameter_json)

                # Update counts based on parameter state
                if row['condition_name'] == 'OK':
                    machine_count['OK'] += 1
                elif row['condition_name'] == 'WARNING':
                    machine_count['WARNING'] += 1
                elif row['condition_name'] == 'CRITICAL':
                    machine_count['CRITICAL'] += 1

            # Determine machine state and line count based on machine's counts
            if machine_count['CRITICAL'] > 0:
                machine_json['machine_state'] = 'CRITICAL'
                # Increment the location's critical count also
                location_json['count']['CRITICAL'] += 1
            elif machine_count['WARNING'] > 0:
                machine_json['machine_state'] = 'WARNING'
                # Increment the location's warning count also
                location_json['count']['WARNING'] += 1
            else:
                # Increment the location's ok count also
                location_json['count']['OK'] += 1

            machine_json['count'] = machine_count
            location_json['machines'].append(machine_json)

        # Determine line state based on counts
        if location_json['count']['CRITICAL'] > 0:
            location_json['line_state'] = 'CRITICAL'
        elif location_json['count']['WARNING'] > 0:
            location_json['line_state'] = 'WARNING'

        json_list.append(location_json)

    response = {"lines": json_list}
    return response


@db_session
def log_user_access(user: User):
    """
    Log user access to the database
    """
    UserAccessLog(username=user.id, timestamp=datetime.utcnow())
    commit()



#FUNCTION TO GET THE DATA FOR THE DISCONNETED MACHINES FROM MONGODB FOR THE LOGS

def get_disconnected_machines_data() -> Dict:
    """
    Retrieves the data for disconnected machines in the factory.

    Returns:
        A dictionary containing the disconnected machines, sorted by line.
    """
    # Get the MongoDB collection
    collection = get_mongo_collection("L1Signal_Pool_Active")

    # MongoDB aggregation pipeline
    pipeline = [
        {
            '$match': {
                'signalname': 'DISCONNECT'
            }
        },
        {
            '$project': {
                '_id': 0,
                'L1Name': 1,
                'value': 1,
                'updatedate': 1
            }
        }
    ]

    # Execute the aggregation pipeline
    result = collection.aggregate(pipeline)

    # Convert the cursor to a list of dictionaries
    disconnected_machines = list(result)

    # Sort the disconnected machines by line
    sorted_machines = sort_machines_by_line(disconnected_machines)

    return sorted_machines

def sort_machines_by_line(machines: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Sorts the machines by line based on the L1Name.

    Args:
        machines (List[Dict]): The list of machine data.

    Returns:
        Dict[str, List[Dict]]: A dictionary containing the sorted machines by line.
    """
    sorted_machines = {
        "Head": [],
        "Block": [],
        "Crank": []
    }

    for machine in machines:
        if machine["L1Name"].startswith("T_H_"):
            sorted_machines["Head"].append(machine)
        elif machine["L1Name"].startswith("T_B_"):
            sorted_machines["Block"].append(machine)
        elif machine["L1Name"].startswith("T_C_"):
            sorted_machines["Crank"].append(machine)
        else:
            line = machine["L1Name"].split("_")[0] ###
            if line == "H":
                sorted_machines["Head"].append(machine)
            elif line == "B":
                sorted_machines["Block"].append(machine)
            elif line == "C":
                sorted_machines["Crank"].append(machine)

    return sorted_machines

# MACHINE HISTORY LOGS FUNCTION TO GET THE HISTORY DATA FOR A PARTICULAR MACHINE
def get_disconnection_history_data(l1name: str, from_timestamp: int, to_timestamp: int) -> List[DisconnectionHistoryItem]:
    try:
        from_datetime_utc = convert_ist_epoch_to_utc(from_timestamp)
        to_datetime_utc = convert_ist_epoch_to_utc(to_timestamp)

        if from_datetime_utc > to_datetime_utc:
            raise ValueError("The 'from_timestamp' must be earlier than the 'to_timestamp'.")

        collection = get_mongo_collection("L1Signal_Pool")

        pipeline = [
            {
                '$match': {
                    'L1Name': l1name,
                    'signalname': 'DISCONNECT',
                    'updatedate': {'$gte': from_datetime_utc, '$lte': to_datetime_utc}
                }
            },
            {
                '$project': {
                    '_id': 0,
                    'L1Name': 1,
                    'updatedate': 1,
                    'enddate': 1,
                    'timespan': 1
                }
            }
        ]

        result = collection.aggregate(pipeline)

        # Convert UTC datetime to IST and prepare the response
        disconnection_history = [
            DisconnectionHistoryItem(
                L1Name=item['L1Name'],
                updatedate=item['updatedate'].astimezone(timezone(IST_OFFSET)),  # Convert updatedate to IST
                enddate=item['enddate'].astimezone(timezone(IST_OFFSET)) if item.get('enddate') else None,  # Convert enddate to IST
                timespan=item['timespan']
            )
            for item in result
        ]

        return disconnection_history

    except ValueError as ve:
        LOGGER.error(f"Validation error occurred: {ve}")
        raise ve
    except Exception as error:
        LOGGER.error(f"Failed to fetch disconnection history: {error}")
        raise HTTPException(status_code=500, detail="Error while fetching disconnection history.")

# CONVERTING THE TIMESTAMP
def convert_ist_epoch_to_utc(epoch_time_ist: int) -> datetime:
    """
    Converts an IST epoch timestamp (in seconds) to UTC datetime.

    Args:
        epoch_time_ist (int): The epoch timestamp in seconds (IST).

    Returns:
        datetime: The corresponding UTC datetime.
    """
    # Convert epoch time to datetime in IST
    ist_datetime = datetime.fromtimestamp(epoch_time_ist, tz=timezone(timedelta(hours=5, minutes=30)))

    # Convert IST datetime to UTC datetime
    utc_datetime = ist_datetime.astimezone(timezone.utc)

    return utc_datetime

def main():
    # get_maintenance_activities(start_time=1707022740000, end_time=1710045600000)
    # Example usage
    # start_time = datetime(2022, 9, 7, 7, 4, 4)
    # end_time = datetime(2025, 2, 7, 13, 15)
    #
    # print(get_abnormalities_summary(start_time, end_time))


    # print(get_machine_timeline_parameter_name_mtlinki(machine_name='T_B_OP160',
    #                                                   parameter_name='ServoLoad_0_path1_T_B_OP160',
    #                                                   start_time=1655704434000, end_time=1711552240000))
    # #
    # print(get_machine_parameter_timeline_spm("JOURNAL FINISH-GRINDING_JOP_140",
    #                                          parameter_name="EffectivePosition(WF:FTSTK_SPINDL)_JOURNAL_GRINDING_JOP140",
    #                                          start_time=1666122178000,
    #                                          end_time= 1666122198000))

    # get_realtime_data(parameter_id=6217, start_time=1666059150, end_time=1666059180)

    # group_name = 'ENCODER_TEMPERATURE'
    # machine_name = 'T_H_OP100B'
    #
    # # abnormalities_count = get_abnormalities_machine_cumulative_counts(start_time, end_time, machine_name)
    # abnormalities_count = get_abnormalities_parameter_cumulative_counts(start_time, end_time, group_name)
    # # abnormalities_count = get_abnormalities_machine_total_count(start_time, end_time, machine_name)
    # print("TOTAL")
    # print(abnormalities_count)

    # abnormalities_warning_count = get_abnormalities_warning_count(start_time, end_time, machine_name)
    # print("WARNING")
    # print(abnormalities_warning_count)
    #
    # abnormalities_critical_count = get_abnormalities_critical_count(start_time, end_time, machine_name)
    # print("CRITICAL")
    # print(abnormalities_critical_count)

    # Example usage
    # machines_starting_with_t = get_machines_starting_with_t()
    # print(machines_starting_with_t)
    # data = get_maintenance_activities()

    # data = get_maintenance_operators_total_count(start_time=1707022740000, end_time=1710045600000)
    # print(get_real_time_parameters_data_mtlinki())
    print(get_real_time_parameters_data())
    # get_machine_states(group_name="ENCODER_TEMPERATURE")

    # get_machine_states_2(group_name="ENCODER_TEMPERATURE")
    # print(get_maintenance_activities_parameter_new("ApcBatLow_1_path1_T_C_OP190"))
    # print(get_maintenance_activities(start_time=1713418428772, end_time=1713422028772))


if __name__ == '__main__':
    initialize_pony()
    main()
