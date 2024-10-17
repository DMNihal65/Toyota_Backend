# -*- coding: utf-8 -*-
"""
CORE DATA ROUTES MODULE TEST
=====================================

This Module consists of api routes for get access to core data

This script requires that the following packages be installed within the Python
environment you are running this script in.

    Standard Library
    =================

    * logging - To perform logging operations.

    Related 3rd Party Library
    =============================

    * fastapi - To perform web application (backend) related functions.

This script contains the following function

    * read_all_current_values - This is an api endpoint used to query the latest data from the database.
"""

# Standard Imports
import logging
import time
from itertools import zip_longest
from typing import Union, Optional, List, Dict
from datetime import datetime, timezone, timedelta
import copy

# Related third party imports
import pytz
from fastapi import APIRouter, Depends, HTTPException, status, Query
import pandas as pd
import psycopg2

# Local application/library specific imports
from numpy import select
from pony.orm import db_session, commit, flush

from machine_monitoring_app.database.mongodb_client import get_mongo_collection
from machine_monitoring_app.database.pony_models import Machine, ParameterGroup, MachineParameter, ParameterCondition, \
    ParameterComparison
from machine_monitoring_app.models.response_models import CurrentData, FullTimelineData, StatusSummaryResponseData, \
    SparePart, AlarmSummaryResponseModel, SpareDeleteResponseModel, GetSparePartResponse, \
    UpdateParameterLimitResponseModel, MachineParameterResponseModel, UsersResponseModel, UserDeleteResponseModel, \
    MachineParameterResponseModelState, SpmStateData, SpareStateData, SpmPositionData, SpecificGroupSchema, \
    FullTimelineDataUsingParameterName, GroupSchema, MachineAnalyticsSummary, ParameterAnalyticsSummary, MachineList, \
    MaintenanceAnalyticsSummary, SpecificGroupSchema_test, UpdateLogResponse, ParameterComparisonOutput, \
    DisconnectionHistoryResponse, ParameterComparisonOutput_mongodb

from machine_monitoring_app.database.crud_operations import get_current_machine_data, get_machine_timeline, \
    create_spare_part, update_spare_part, get_alarm_summary_data, delete_spare_part, update_parameter_limits, \
    get_machine_parameter_timeline_spm, get_users, delete_user, update_parameter_limits_spm, \
    get_machine_parameters_state, \
    get_all_machine_spm_status_active, get_similar_part, get_spare_part_states, get_real_time_data_parts, \
    get_latest_snapshot_for_parameter_group, get_machine_timeline_parameter_name, \
    update_parameter_limits_with_parameter_name, get_all_machine_spare_details, get_maintenance_activities, \
    update_maintenance_activities, get_maintenance_operators, get_abnormalities_machine_cumulative_counts, \
    get_abnormalities_parameter_cumulative_counts, get_machines_starting_with_t, get_parameter_group, \
    get_maintenance_operators_total_count, delete_spare_parts, get_maintenance_activities_parameter, get_schema_name, \
    get_machine_timeline_parameter_name_mtlinki, get_machine_names, get_latest_snapshot_for_parameter_group_test, \
    get_machine_names_2, get_maintenance_activities_parameter_new, fetch_update_logs, fetch_update_logs_by_name, \
    fetch_update_logs_by_user, fetch_update_logs_by_time_range, get_disconnected_machines_data, \
    get_disconnection_history_data

from machine_monitoring_app.database import TIMESCALEDB_URL
from machine_monitoring_app.exception_handling.custom_exceptions import NoParameterGroupError, GetParamGroupDBError, \
    GetAllParameterDBError, GetMachineTimelineError

from machine_monitoring_app.routers.router_dependencies import get_current_active_user, is_admin
from machine_monitoring_app.database.crud_operations import get_full_day_summary, get_full_month_week_summary, \
    get_spare_parts, get_machine_parameters

from machine_monitoring_app.models.base_data_models import User

from machine_monitoring_app.models.request_models import PendingActivityListModel, \
    SparePartsToDeleteModel, SparePartUpdateList, SparePartPost, ParameterComparisonInput, \
    UpdateParameterComparisonInput

LOGGER = logging.getLogger(__name__)

# Depends(get_current_active_user)
# ROUTER = APIRouter(
#     prefix="/api/v1",
#     tags=["Core Data Routes"],
#     dependencies=[Depends(get_current_active_user)],
#     responses={404: {"description": "Not found"}})

ROUTER = APIRouter(
    prefix="/api/v1",
    tags=["Core Data Routes"],
    responses={404: {"description": "Not found"}})


@ROUTER.get("/machine-spare-states-new", response_model=GroupSchema)
async def read_machine_spare_states_new():
    """
    GET CURRENT PARAMETERS DATA
    ===============================

    This api is used to query the status of the machines for given parameter group
    """

    start_time = time.time()
    try:
        response_data = get_all_machine_spare_details()
        end_time = time.time() - start_time
        LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
    except GetParamGroupDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    except GetAllParameterDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return response_data


@ROUTER.get("/machines", response_model=MachineList)
async def read_all_machines():
    """
    GET LIST OF ALL MACHINES
    ===============================

    This api is used to query the list of all available machine names
    """

    start_time = time.time()
    try:
        response_data = get_machines_starting_with_t()
        end_time = time.time() - start_time
        LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
    except GetParamGroupDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    except GetAllParameterDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return response_data


@ROUTER.get("/parameter_groups", response_model=MachineList)
async def read_all_parameter_groups():
    """
    GET CURRENT PARAMETERS GROUPS DATA
    ===================================

    This api is used to query the list of all parameter group names
    """

    start_time = time.time()
    try:
        response_data = get_parameter_group()
        end_time = time.time() - start_time
        LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
    except GetParamGroupDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    except GetAllParameterDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return response_data


@ROUTER.get("/maintenance-activities")
async def read_maintenance_activities(startTime: float, endTime: float):
    """
    GET CURRENT MAINTENANCE ACTIVITY DATA
    =====================================

    This api is used to query the maintenance activity information
    """

    start_time = time.time()
    try:
        response_data = get_maintenance_activities(start_time=startTime, end_time=endTime)
        end_time = time.time() - start_time
        LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
    except GetParamGroupDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    except GetAllParameterDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return response_data


@ROUTER.get("/maintenance-activities-parameter")
async def read_maintenance_activities(paramter_name: str):
    """
    GET CURRENT MAINTENANCE ACTIVITY DATA
    =====================================

    This api is used to query the maintenance activity information
    """

    start_time = time.time()
    try:
        response_data = get_maintenance_activities_parameter(paramter_name)
        end_time = time.time() - start_time
        LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
    except GetParamGroupDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    except GetAllParameterDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    except HTTPException as error:
        raise HTTPException(404, error.detail)

    return response_data


@ROUTER.get("/maintenance-activities-parameter-new")
async def read_maintenance_activities_new(paramter_name: str):
    """
    GET CURRENT MAINTENANCE ACTIVITY DATA
    =====================================

    This api is used to query the maintenance activity information
    """

    start_time = time.time()
    try:
        response_data = get_maintenance_activities_parameter_new(paramter_name)
        end_time = time.time() - start_time
        LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
    except GetParamGroupDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    except GetAllParameterDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    except HTTPException as error:
        raise HTTPException(404, error.detail)

    return response_data


@ROUTER.put("/maintenance-activities")
async def put_maintenance_activities(activities_data: PendingActivityListModel):
    """
    GET CURRENT MAINTENANCE ACTIVITY DATA
    =====================================

    This api is used to query the maintenance activity information
    """

    start_time = time.time()
    try:
        LOGGER.info("*" * 10)
        LOGGER.info(activities_data.data)
        update_maintenance_activities(activities_data.data)
        end_time = time.time() - start_time
        LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
    except GetParamGroupDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    except GetAllParameterDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return {"status": "ok"}


@ROUTER.get("/maintenance-operators", response_model=list[User])
async def read_maintenance_operators():
    """
    GET ALL MAINTENANCE OPERATORS DATA
    =====================================

    This api is used to query the list of all available maintenance operators
    """

    start_time = time.time()
    try:
        response_data = get_maintenance_operators()
        end_time = time.time() - start_time
        LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
    except GetParamGroupDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    except GetAllParameterDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return response_data


@ROUTER.get("/factory-state/{parameterGroupName}", response_model=SpecificGroupSchema)
async def read_recent_group(parameterGroupName: str):
    """
    GET CURRENT PARAMETERS DATA
    ===============================

    This api is used to query the status of the machines for given parameter group
    """

    start_time = time.time()
    try:
        response_data = get_latest_snapshot_for_parameter_group(parameterGroupName)
        end_time = time.time() - start_time
        LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
    except NoParameterGroupError as error:
        raise HTTPException(status_code=404, detail=f"Parameter group id '{parameterGroupName}' is not found")
    except GetParamGroupDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    except GetAllParameterDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return response_data


@ROUTER.get("/factory-state-mtlinki/{parameterGroupName}", response_model=SpecificGroupSchema)
async def read_recent_group_mtlinki(parameterGroupName: str):
    """
    GET CURRENT PARAMETERS DATA
    ===============================

    This api is used to query the status of the machines for given parameter group with agumentation from mtlinki
    """

    start_time = time.time()
    try:
        response_data = get_latest_snapshot_for_parameter_group(parameterGroupName)
        end_time = time.time() - start_time
        LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
    except NoParameterGroupError as error:
        raise HTTPException(status_code=404, detail=f"Parameter group id '{parameterGroupName}' is not found")
    except GetParamGroupDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    except GetAllParameterDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return response_data

#TODO : CHANGING THE ROUTES TO THIS FROM factory-state-mtlinki


@ROUTER.get("/factory-state-mtlinki-test/{parameterGroupName}", response_model=SpecificGroupSchema_test)
async def read_recent_group_mtlinki_test(parameterGroupName: str):
    """
    GET CURRENT PARAMETERS DATA
    ===============================

    This api is used to query the status of the machines for given parameter group with agumentation from mtlinki
    """

    start_time = time.time()
    try:
        response_data = get_latest_snapshot_for_parameter_group_test(parameterGroupName)
        end_time = time.time() - start_time
        LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
    except NoParameterGroupError as error:
        raise HTTPException(status_code=404, detail=f"Parameter group id '{parameterGroupName}' is not found")
    except GetParamGroupDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    except GetAllParameterDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return response_data


@ROUTER.get("/machine-state/{parameterGroupId}", response_model=CurrentData)
async def read_all_current_values(parameterGroupId: int):
    """
    GET CURRENT PARAMETERS DATA
    ===============================

    This api is used to query the status of the machines for given parameter group
    """

    start_time = time.time()
    try:
        response_data = get_current_machine_data(parameterGroupId)
        end_time = time.time() - start_time
        LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
    except NoParameterGroupError as error:
        raise HTTPException(status_code=404, detail=f"Parameter group id '{parameterGroupId}' is not found")
    except GetParamGroupDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    except GetAllParameterDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return response_data


@ROUTER.get("/dynamic-parameter-real-time/{machineName}/{parameterGroupId}/{axisId}")
async def read_timeline_machine_param_dynamic(machineName: str, parameterGroupId: int, axisId: int, startTime: float,
                                              endTime: float):
    """

    GET MACHINE TIMELINE DATA DYNAMIC
    =====================================

    This api is used to query the given machine's parameter for full timeline of data

    """
    response_data = {
        "param": 0,
        "axis": 0,
        "machine": "string",
        "start_time": 0,
        "stop_time": 0,
        "data": [
            {"cycle_value": [4, 2, 3],
             "timestamps": [1, 2, 3],
             "reference_cycle": [4, 4, 3],
             "condition": "critical",
             "alpha_value": 0.6,
             "stat_value": 1.0,
             "variant_name": "name",
             "cycle_time": 60},
            {"cycle_value": [5, 6, 7, 8],
             "timestamps": [4, 5, 6, 7],
             "reference_cycle": [5, 7, 7, 8],
             "condition": "critical",
             "alpha_value": 0.6,
             "stat_value": 1.0,
             "variant_name": "name",
             "cycle_time": 60}
        ]
    }
    return response_data


@ROUTER.get("/spm-machine-state", response_model=SpmStateData)
async def read_spm_machine_states():
    """
    GET CURRENT PARAMETERS DATA SPM
    ===================================

    This api is used to query the status of the machines for given parameter group
    """

    start_time = time.time()
    try:
        response_data = get_all_machine_spm_status_active()
        end_time = time.time() - start_time
        LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
    except NoParameterGroupError as error:
        raise HTTPException(status_code=404, detail=f"Parameter group id is not found")
    except GetParamGroupDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    except GetAllParameterDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return response_data


@ROUTER.get("/machine-spare-states", response_model=SpareStateData)
async def read_machine_spare_states():
    """
    GET CURRENT PARAMETERS DATA CNC
    ===================================

    This api is used to query the status of all the spare parts of all machines
    """

    start_time = time.time()
    try:
        warning_machines, critical_machines = get_spare_part_states()

        response_data = {"spare_machine_status": {"warning_machines": warning_machines,
                                                  "critical_machines": critical_machines}}

        end_time = time.time() - start_time
        LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
    except NoParameterGroupError as error:
        raise HTTPException(status_code=404, detail=f"Parameter group id is not found")
    except GetParamGroupDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    except GetAllParameterDBError as error:
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return response_data


@ROUTER.get("/factory/machines/{machineName}/parameters/{parameterName}",
            response_model=FullTimelineDataUsingParameterName)
async def read_timeline_machine_parameter_name(machineName: str, parameterName: str, startTime: float,
                                               endTime: float):
    """

    GET MACHINE TIMELINE DATA PARAMETER NAME
    =========================================

    This api is used to query the given machine's parameter for full timeline of data using only  parameter name
    """
    LOGGER.info("===================================>>>>")
    process_start_time = time.time()
    if startTime > endTime:
        raise HTTPException(status_code=400, detail="Start Time cannot be greater than End Time")
    try:
        response_data = get_machine_timeline_parameter_name(parameterName, startTime, endTime)

        if response_data:
            end_time = time.time() - process_start_time
            LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
            return response_data

        end_time = time.time() - process_start_time
        LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")

        # If there is no response, raise an exception
        raise HTTPException(status_code=404, detail="No data available for given machine, parameter group, "
                                                    "axis and timestamp")
    except GetMachineTimelineError as error:
        raise HTTPException(status_code=404, detail=f"Issue with database: {error.args[0]}")


@ROUTER.get("/factory/machines/{machineName}/parameters-mtlinki/{parameterName}",
            response_model=FullTimelineDataUsingParameterName)
async def read_timeline_machine_parameter_name_mtlinki(machineName: str, parameterName: str, startTime: float,
                                                       endTime: float):
    """

    GET MACHINE TIMELINE DATA PARAMETER NAME USING MTLINKI
    =======================================================

    This api is used to query the given machine's parameter for full timeline of data using only  parameter name
    from MtLinki
    """
    process_start_time = time.time()
    if startTime > endTime:
        raise HTTPException(status_code=400, detail="Start Time cannot be greater than End Time")
    try:
        response_data = get_machine_timeline_parameter_name_mtlinki(machine_name=machineName,
                                                                    parameter_name=parameterName,
                                                                    start_time=startTime,
                                                                    end_time=endTime)

        if response_data:
            end_time = time.time() - process_start_time
            LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
            return response_data

        end_time = time.time() - process_start_time
        LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")

        # If there is no response, raise an exception
        raise HTTPException(status_code=404, detail="No data available for given machine, parameter group, "
                                                    "axis and timestamp")
    except GetMachineTimelineError as error:
        raise HTTPException(status_code=404, detail=f"Issue with database: {error.args[0]}")


@ROUTER.get("/factory/analytics/machines/{machineName}",
            response_model=MachineAnalyticsSummary)
async def read_machine_analytics(machineName: str, startTime: float,
                                 endTime: float):
    """

    GET MACHINE ANALYTICS DATA
    =========================================

    This api is used to query the summary of abnormal data for the given machine
    """

    process_start_time = time.time()
    if startTime > endTime:
        raise HTTPException(status_code=400, detail="Start Time cannot be greater than End Time")
    try:
        response_data = get_abnormalities_machine_cumulative_counts(startTime, endTime, machineName)
        LOGGER.info(response_data)
        if response_data:
            end_time = time.time() - process_start_time
            LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
            return response_data

        end_time = time.time() - process_start_time
        LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")

        # If there is no response, raise an exception
        raise HTTPException(status_code=404, detail="No data available for given machine")
    except GetMachineTimelineError as error:
        raise HTTPException(status_code=404, detail=f"Issue with database: {error.args[0]}")


@ROUTER.get("/factory/analytics/parameters/{parameterName}",
            response_model=ParameterAnalyticsSummary)
async def read_parameter_analytics(parameterName: str, startTime: float,
                                   endTime: float):
    """

    GET PARAMETER ANALYTICS DATA
    =========================================

    This api is used to query the summary of abnormal data for the given machine
    """

    process_start_time = time.time()
    if startTime > endTime:
        raise HTTPException(status_code=400, detail="Start Time cannot be greater than End Time")
    try:
        response_data = get_abnormalities_parameter_cumulative_counts(startTime, endTime, parameterName)
        LOGGER.info(response_data)
        if response_data:
            end_time = time.time() - process_start_time
            LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
            return response_data

        end_time = time.time() - process_start_time
        LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")

        # If there is no response, raise an exception
        raise HTTPException(status_code=404, detail="No data available for given parameter")
    except GetMachineTimelineError as error:
        raise HTTPException(status_code=404, detail=f"Issue with database: {error.args[0]}")


@ROUTER.get("/factory/analytics/operators",
            response_model=MaintenanceAnalyticsSummary)
async def read_maintenance_analytics(startTime: float,
                                     endTime: float):
    """

    GET MAINTENANCE ANALYTICS DATA
    =========================================

    This api is used to query the summary of maintenance analytics data
    """
    LOGGER.info("In maintenance analytics")
    LOGGER.info("=" * 100)
    process_start_time = time.time()
    if startTime > endTime:
        raise HTTPException(status_code=400, detail="Start Time cannot be greater than End Time")
    try:
        LOGGER.info("8" * 100)
        response_data = get_maintenance_operators_total_count(startTime, endTime)
        LOGGER.info(response_data)
        if response_data:
            end_time = time.time() - process_start_time
            LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
            return response_data

        end_time = time.time() - process_start_time
        LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")

        # If there is no response, raise an exception
        raise HTTPException(status_code=404, detail="No data available for given parameter")
    except GetMachineTimelineError as error:
        raise HTTPException(status_code=404, detail=f"Issue with database: {error.args[0]}")


@ROUTER.get("/factory-state-summary", response_model=StatusSummaryResponseData)
def read_factory_state_summary(startTime: int, factoryObject: str = "all", dayRange: str = "month"):
    """

    GET MACHINE TIMELINE DATA
    ===============================

    This api is used to query the given machine's parameter for full timeline of data

    """

    process_start_time = time.time()

    if dayRange == "day":
        try:
            if factoryObject == "all":
                response_data = get_full_day_summary(day=startTime)
            else:
                response_data = get_full_day_summary(production_line=factoryObject, day=startTime)

            if response_data:
                LOGGER.info(time.time() - process_start_time)
                response_data = {"requested_time": startTime, "requested_factory_object": factoryObject,
                                 "requested_data": response_data, "requested_day_range": dayRange}
                return response_data

            # If there is no response, raise an exception
            raise HTTPException(status_code=404, detail="No data available for given machine, production_line")
        except Exception as error:
            raise HTTPException(status_code=404, detail=f"Issue with database: {error.args[0]}")
    elif dayRange == "month":
        try:
            if factoryObject == "all":
                response_data = get_full_month_week_summary(day=startTime)
            else:
                response_data = get_full_month_week_summary(production_line=factoryObject, day=startTime)

            if response_data:
                LOGGER.info(time.time() - process_start_time)
                response_data = {"requested_time": startTime, "requested_factory_object": factoryObject,
                                 "requested_data": response_data, "requested_day_range": dayRange}
                return response_data

            # If there is no response, raise an exception
            raise HTTPException(status_code=404, detail="No data available for given machine, production_line")
        except Exception as error:
            raise HTTPException(status_code=404, detail=f"Issue with database: {error.args[0]}")
    else:
        try:
            if factoryObject == "all":
                response_data = get_full_month_week_summary(day=startTime, week=True)
            else:
                response_data = get_full_month_week_summary(production_line=factoryObject, day=startTime, week=True)

            if response_data:
                LOGGER.info(time.time() - process_start_time)
                response_data = {"requested_time": startTime, "requested_factory_object": factoryObject,
                                 "requested_data": response_data, "requested_day_range": dayRange}
                return response_data

            # If there is no response, raise an exception
            raise HTTPException(status_code=404, detail="No data available for given machine, production_line")
        except Exception as error:
            raise HTTPException(status_code=404, detail=f"Issue with database: {error.args[0]}")


@ROUTER.get("/{machineName}/alarms", response_model=AlarmSummaryResponseModel)
def read_alarm_summary(machineName: str, startTime: float, endTime: float):
    """
    GET MACHINE ALARM DATA
    ===============================

    This api is used to query the given machine's parameter for full timeline of data
    """
    LOGGER.info(f"Start Time: {startTime}")

    process_start_time = time.time()
    if startTime > endTime:
        raise HTTPException(status_code=400, detail="Start Time cannot be greater than End Time")
    try:

        response_data = get_alarm_summary_data(start_time=startTime, end_time=endTime,
                                               machine_name=machineName)

        if response_data:
            end_time = time.time() - process_start_time
            LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
            return response_data

        # If there is no response, raise an exception
        raise HTTPException(status_code=404, detail="No data available for given machine, parameter group, "
                                                    "axis and timestamp")
    except GetMachineTimelineError as error:
        raise HTTPException(status_code=404, detail=f"Issue with database: {error.args[0]}")


@ROUTER.get("/{machineName}/spare-parts", response_model=GetSparePartResponse)
def get_spare_parts_method(machineName):
    """
    GET MACHINE SPARE PARTs
    ===============================

    This api is used to get all the spare parts of a machine
    """

    process_start_time = time.time()

    spare_part = get_spare_parts(machine_name=machineName)

    if spare_part:
        end_time = time.time() - process_start_time
        LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
        return spare_part

    # If there is no response, raise an exception
    raise HTTPException(status_code=404, detail="Given Machine Not Available")


@ROUTER.post("/{machineName}/spare-parts", response_model=SparePart)
def create_spare_part_method(machineName: str, newSparePartData: SparePartPost):
    """
    POST MACHINE SPARE PART
    ===============================

    This api is used to add new spare part to the machine
    """

    process_start_time = time.time()

    newSparePart = newSparePartData.data
    spare_part = create_spare_part(part_name=newSparePart.part_name,
                                   reference_part_number=newSparePart.reference_part_number,
                                   warning_limit=newSparePart.warning_limit,
                                   critical_limit=newSparePart.critical_limit,
                                   machine_name=machineName)

    if spare_part:
        end_time = time.time() - process_start_time
        LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
        return spare_part

    # If there is no response, raise an exception
    raise HTTPException(status_code=404, detail="Given Machine Not Available")


# @ROUTER.put("/{machineName}/{sparePart}", response_model=SparePart)
# def update_spare_part_method(machineName: str, sparePart: str, parameterName: str, parameterValue: int,
#                              current_user: User = Depends(get_current_active_user)):
#     """
#     UPDATE MACHINE SPARE PART
#     ===============================
#
#     This api is used to add new spare part to the machine
#     """
#
#     if current_user.role != "admin":
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Not authorized to update, Only admin can update",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
#
#     process_start_time = time.time()
#
#     spare_part = update_spare_part(part_name=sparePart, parameter_value=parameterValue,
#                                    machine_name=machineName, parameter_name=parameterName)
#
#     if spare_part:
#         end_time = time.time() - process_start_time
#         LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
#         return spare_part
#
#     # If there is no response, raise an exception
#     raise HTTPException(status_code=404, detail="Given Spare Part Not Found")


# Endpoint
@ROUTER.put("/{machineName}/spare-parts")
def update_spare_parts(machineName: str, updates: SparePartUpdateList):
    """Updates spare part information for a specified machine.

    Args:
        machineName (str): The name of the machine to update.
        updates (SparePartUpdateList): A list of spare part updates.

    Returns:
        dict: A success message indicating the update was completed.

    Raises:
        HTTPException: If an unexpected error occurs during the update process.
    """

    LOGGER.info("==" * 20)  # Log the machine name for which updates are being made
    LOGGER.info(machineName)  # Log the machine name for which updates are being made

    try:
        update_spare_part(machine_name=machineName, updates=updates)  # Perform the update operation
        return {"message": "Spare parts updated"}

    except Exception as e:  # Catch other general exceptions
        LOGGER.error("Unexpected error during spare part update: %s", e)  # Log the error
        raise HTTPException(status_code=500, detail=e)  # Raise a generic server error


@ROUTER.put("/factory/{parameterGroup}/{machineName}/{parameterName}/", response_model=dict)
async def update_set_limit_method_parameter(parameterGroup: str,
                                        machineName: str,
                                        parameterName: str,
                                        setType: str,
                                        limit: Optional[float] = None,
                                        append: Optional[bool] = None,
                                        referenceSignal: Optional[List[float]] = None,
                                        current_user: User = Depends(get_current_active_user)
                                        ):
    """
    Updates machine parameter limits or reference signal.
    """

    if current_user.role not in ["admin", "maintenance_operator"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized to update, only admin or operator can update",
            headers={"WWW-Authenticate": "Bearer"},
        )

    process_start_time = time.time()

    try:
        update_response = update_parameter_limits_with_parameter_name(
            parameter_name=parameterName,
            set_type=setType,
            limit=limit,
            reference_signal=referenceSignal,
            append=append,
            current_user=current_user
        )

        LOGGER.info(f"Total Time Taken: {time.time() - process_start_time}")

        if update_response:
            return {
                "message": "Parameter updated successfully",
                "updated_by": current_user.username,
                "parameter_name": parameterName,
                "set_type": setType,
                "limit_value": limit,
                "reference_signal": referenceSignal,
                "date_changed": datetime.now(),
                "previous_limit": update_response.get("previous_limit")
            }

        raise HTTPException(status_code=404, detail="Machine or parameter group or axis not found")
    except Exception as error:
        error_message = error.args[0] if error.args else str(error)
        LOGGER.error(f"Error Occurred: {error_message}")
        raise HTTPException(status_code=500, detail=f"Internal Error: {error_message}")



@ROUTER.put("/parameters_limit/{machineName}/{parameterGroupId}/{axisId}",
            response_model=UpdateParameterLimitResponseModel)
def update_set_limit_method(machineName: str, parameterGroupId: int, axisId: int, setType: str,
                            limit: Optional[float] = None, append: Optional[bool] = None,
                            referenceSignal: Optional[list[float]] = None,
                            current_user: User = Depends(get_current_active_user)):
    """
    UPDATE MACHINE PARAMETER  SET LIMITS
    =========================================

    This api is used to update machine parameters set limit or reference signal
    """

    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized to update, Only admin can update",
            headers={"WWW-Authenticate": "Bearer"},
        )

    process_start_time = time.time()

    try:

        update_response = update_parameter_limits(machine_name=machineName, parameter_group_id=parameterGroupId,
                                                  axis_id=axisId, set_type=setType, limit=limit,
                                                  reference_signal=referenceSignal, append=append)

        if update_response:
            return update_response

        LOGGER.info(f"Total Time Taken: {time.time() - process_start_time}")

        # If there is no response, raise an exception
        raise HTTPException(status_code=404, detail="Given machine or parameter group or axis not found")
    except Exception as error:
        LOGGER.error(f"Error Occurred : {error.args[0]}")
        raise HTTPException(status_code=500, detail=f"Internal Error {error.args[0]}")


@ROUTER.put("/spm/parameters_limit/{parameterName}",
            response_model=UpdateParameterLimitResponseModel)
def update_set_limit_method_spm(parameterName: str, setType: str,
                                limit: Optional[float] = None, append: Optional[bool] = None,
                                referenceSignal: Optional[list[float]] = None,
                                current_user: User = Depends(get_current_active_user)):
    """
    UPDATE MACHINE PARAMETER  SET LIMITS
    =========================================

    This api is used to update machine parameters set limit or reference signal
    """

    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized to update, Only admin can update",
            headers={"WWW-Authenticate": "Bearer"},
        )

    process_start_time = time.time()

    try:

        update_response = update_parameter_limits_spm(parameter_name=parameterName,
                                                      set_type=setType, limit=limit,
                                                      reference_signal=referenceSignal,
                                                      append=append)

        if update_response:
            return update_response

        LOGGER.info(f"Total Time Taken: {time.time() - process_start_time}")

        # If there is no response, raise an exception
        raise HTTPException(status_code=404, detail="Given machine or parameter group or axis not found")
    except Exception as error:
        LOGGER.error(f"Error Occurred : {error.args[0]}")
        raise HTTPException(status_code=500, detail=f"Internal Error {error.args[0]}")


@ROUTER.delete("/factory/machines/{machineName}/spare-parts/{sparePart}", response_model=SpareDeleteResponseModel)
def delete_spare_part_method(machineName: str, sparePart: str, current_user: User = Depends(get_current_active_user)):
    """
    DELETE MACHINE SPARE PART
    ===============================

    This api is used to delete an existing spare part to the machine
    """

    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized to delete, Only admin can delete spare parts",
            headers={"WWW-Authenticate": "Bearer"},
        )

    process_start_time = time.time()

    response = delete_spare_part(part_name=sparePart, machine_name=machineName)

    if response:
        return response

    LOGGER.info(f"Total Time Taken: {time.time() - process_start_time}")

    # If there is no response, raise an exception
    raise HTTPException(status_code=404, detail="Given Spare Part / Machine Not Found")


@ROUTER.delete("/factory/machines/{machineName}/spare-parts")
def delete_spare_part_method(machineName: str, spare_parts: SparePartsToDeleteModel,
                             current_user: User = Depends(get_current_active_user)):
    """
    DELETE MANY MACHINE SPARE PARTS
    ================================

    This api is used to delete multiple existing spare parts of the given machine
    """

    # if current_user.role != "admin":
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Not authorized to delete, Only admin can delete spare parts",
    #         headers={"WWW-Authenticate": "Bearer"},
    #     )

    process_start_time = time.time()

    response = delete_spare_parts(machine_name=machineName, part_names=spare_parts.part_names)

    # response = delete_spare_part(part_name=sparePart, machine_name=machineName)

    if response:
        return response

    LOGGER.info(f"Total Time Taken: {time.time() - process_start_time}")

    # If there is no response, raise an exception
    raise HTTPException(status_code=404, detail="Given Spare Part / Machine Not Found")


@ROUTER.delete("/user/{userId}", response_model=UserDeleteResponseModel)
def delete_user_method(userId: int, current_user: User = Depends(get_current_active_user)):
    """
    DELETE USER
    ================

    This api is used to add new spare part to the machine
    """

    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized to delete, Only admin can delete users",
            headers={"WWW-Authenticate": "Bearer"},
        )

    process_start_time = time.time()

    response = delete_user(user_id=userId)

    if response:
        if response["detail"] == "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authorized to delete Super User cmti",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return response

    LOGGER.info(f"Total Time Taken: {time.time() - process_start_time}")

    # If there is no response, raise an exception
    raise HTTPException(status_code=404, detail="Given User Not Found")


@ROUTER.get("/spm/laser/{machineName}/real-time", response_model=SpmPositionData)
def read_laser_clad_time(machineName: str, part_number: str, parameter_name: str):
    """
    End point used to get the real time data for the given part number and parameter

    :param machineName: The machine name

    :param part_number: The part name as stored in timescaledb

    :param parameter_name: The parameter name as stored in timescaledb

    :return: Dictionary consisting of data for the given part
    :rtype: SpmPositionData
    """

    process_start_time = time.time()

    data = get_real_time_data_parts(required_part_number=part_number,
                                    parameter_name=parameter_name,
                                    machine_name=machineName)

    if not data:
        raise HTTPException(status_code=404, detail="Part Number Not Found")

    end_time = time.time() - process_start_time
    LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
    return data


@ROUTER.get("/spm/laser/{machineName}/similar-part")
def read_laser_clad_similar_part(machineName: str, part_number: str):
    """
    End point used to get all the parts that are similar to the given part number

    :param machineName: The machine name

    :param part_number: The part name as stored in timescaledb

    :return: Dictionary consisting of a single list with parameters of the machine
    :rtype: MachineParameterResponseModel
    """
    time_1 = time.time()

    parts = get_similar_part(required_part_number=part_number, machine_name=machineName)

    if not parts:
        raise HTTPException(status_code=404, detail="Part Number Not Found")

    data = {"part_ending": part_number,
            "data": parts}

    time_2 = time.time()

    LOGGER.info(f"TOTAL TIME: {(time_2 - time_1) * 1000} ms")

    return data


@ROUTER.get("/machine-parameters", response_model=MachineParameterResponseModel)
def read_machine_parameters_spm(machineName: str):
    """
    End point used to get all the parameters of a given machine

    :param machineName: Machine name as stored in timescaledb

    :return: Dictionary consisting of a single list with parameters of the machine
    :rtype: MachineParameterResponseModel
    """

    start_time = time.time()
    response_data = get_machine_parameters(machine_name=machineName)

    if not response_data:
        raise HTTPException(status_code=404, detail="Machine Not Available")

    LOGGER.info(response_data)

    data = {"parameter_data": response_data}
    end_time = time.time()
    LOGGER.info(f"TOTAL TIME for machine-parameters end point: {(end_time - start_time) * 1000} ms")
    return data


@ROUTER.get("/machine-parameters-with-states", response_model=MachineParameterResponseModelState)
def read_machine_parameters_spm_states(machineName: str):
    """
    End point used to get all the parameters of a given machine

    :param machineName: Machine name as stored in timescaledb

    :return: Dictionary consisting of a single list with parameters of the machine
    :rtype: MachineParameterResponseModel
    """

    start_time = time.time()
    response_data = get_machine_parameters_state(machine_name=machineName)

    if not response_data:
        raise HTTPException(status_code=404, detail="Machine Not Available")

    end_time = time.time() - start_time
    LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
    return response_data


@ROUTER.get("/spm/real-time/{machineName}/{parameterName}", response_model=FullTimelineData)
async def read_timeline_machine_param_spm(machineName: str, parameterName: str, startTime: float,
                                          endTime: float):
    """

    GET MACHINE TIMELINE DATA SPM
    ===============================

    This api is used to query the given machine's (SPM) parameter for full timeline of data

    """
    process_start_time = time.time()

    if startTime > endTime:
        raise HTTPException(status_code=400, detail="Start Time cannot be greater than End Time")
    try:
        response_data = get_machine_parameter_timeline_spm(machineName, parameterName, startTime, endTime)

        if response_data:
            end_time = time.time() - process_start_time
            LOGGER.info(f"Total Time Taken For this end point: {(round((end_time * 1000), 2))} ms")
            return response_data

        # If there is no response, raise an exception
        raise HTTPException(status_code=404, detail="No data available for given machine, parameter group, "
                                                    "axis and timestamp")
    except GetMachineTimelineError as error:
        raise HTTPException(status_code=404, detail=f"Issue with database: {error.args[0]}")


@ROUTER.get("/users", response_model=UsersResponseModel)
def read_all_users():
    """
    End point used to get all the available users

    :return: Dictionary consisting of a single list with all the available users
    :rtype: UsersResponseModel
    """

    start_time = time.time()
    response_data = {"user_data": get_users()}
    end_time = time.time()
    LOGGER.info(f"TOTAL TIME for users end point: {round((end_time - start_time) * 1000, 2)} ms")
    return response_data


@ROUTER.get("/SPMmachines")
async def read_machine_names():
    machine_ids = [1, 61, 63, 64]
    machine_status = get_machine_names(machine_ids)
    return {"machine_status": machine_status}

#TODO ADDED THE SPM140 machine_id =62 (DONE)
@ROUTER.get("/SPMmachines_2")
async def read_machine_names():
    machine_ids = [1, 61, 63, 62, 64]
    machine_status = get_machine_names_2(machine_ids)

    formatted_status = []
    for machine_name, status in machine_status.items():
        formatted_status.append({"machineName": machine_name, "status": status})

    return formatted_status

@ROUTER.get("/update-logs", response_model=List[UpdateLogResponse])
def read_update_logs():
    """
    Endpoint used to get all update logs

    :return: List of update logs
    :rtype: List[UpdateLogResponse]
    """
    # Fetch the data from the database
    response_data = fetch_update_logs()

    if not response_data:
        raise HTTPException(status_code=404, detail="No Update Logs Found")

    return response_data

@ROUTER.get("/update-logs-by-user/{user}", response_model=List[UpdateLogResponse])
def read_update_logs_by_user(user: str):
    """
    Endpoint used to get update logs by user.

    :param user: The user to filter update logs.
    :return: List of update logs with the specified parameter name.
    :rtype: List[UpdateLogResponse]
    """
    # Fetch the data from the database based on the parameter name
    response_data = fetch_update_logs_by_user(user)

    if not response_data:
        raise HTTPException(status_code=404, detail="No Update Logs Found for the given parameter name")

    return response_data

@ROUTER.get("/update-logs-by-name/{parameter_name}", response_model=List[UpdateLogResponse])
def read_update_logs_by_name(parameter_name: str):
    """
    Endpoint used to get update logs by parameter name.

    :param parameter_name: The parameter name to filter update logs.
    :return: List of update logs with the specified parameter name.
    :rtype: List[UpdateLogResponse]
    """
    # Fetch the data from the database based on the parameter name
    response_data = fetch_update_logs_by_name(parameter_name)

    if not response_data:
        raise HTTPException(status_code=404, detail="No Update Logs Found for the given parameter name")

    return response_data

@ROUTER.get("/update-logs/by-time", response_model=List[UpdateLogResponse])
def read_update_logs_by_time(start_time: float, end_time: float):
    """
    Endpoint used to get update logs by a specified time range using epoch timestamps.

    :param start_time: The start time in epoch milliseconds to filter update logs.
    :param end_time: The end time in epoch milliseconds to filter update logs.
    :return: List of update logs within the specified time range.
    :rtype: List[UpdateLogResponse]
    """
    if start_time >= end_time:
        raise HTTPException(status_code=400, detail="Start time must be before end time")


    try:
        response_data = fetch_update_logs_by_time_range(start_time, end_time)

        if not response_data:
            raise HTTPException(status_code=404, detail="No Update Logs Found for the given time range")

        return response_data

    except HTTPException as e:
        LOGGER.error(f"HTTP Exception in read_update_logs_by_time endpoint: {e.detail}")
        raise
    except Exception as e:
        LOGGER.error(f"Error in read_update_logs_by_time endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")




@ROUTER.post("/parameter-comparison/")
async def create_parameter_comparison(input_data: ParameterComparisonInput):
    try:
        with db_session:
            # Get the machine
            machine = Machine.get(name=input_data.machine_name)
            if not machine:
                raise HTTPException(status_code=404, detail="Machine not found")

            # Get the parameter group (if provided)
            parameter_group = None
            if input_data.parameter_group_name:
                parameter_group = ParameterGroup.get(group_name=input_data.parameter_group_name)
                if not parameter_group:
                    raise HTTPException(status_code=404, detail="Parameter group not found")

            # Get machine parameters
            machine_parameter1 = MachineParameter.get(name=input_data.machine_parameter1_name, machine=machine)
            machine_parameter2 = MachineParameter.get(name=input_data.machine_parameter2_name, machine=machine)
            if not machine_parameter1 or not machine_parameter2:
                raise HTTPException(status_code=404, detail="One or both machine parameters not found")

            # Get the 'OK' parameter condition
            ok_condition = ParameterCondition.get(name="OK")
            if not ok_condition:
                raise HTTPException(status_code=404, detail="'OK' parameter condition not found")

            # Create new ParameterComparison
            new_comparison = ParameterComparison(
                time=datetime.now(),
                line=input_data.line_name,
                machine=machine,
                parameter_group=parameter_group,
                machine_parameter1=machine_parameter1,
                machine_parameter2=machine_parameter2,
                warning_limit=input_data.warning_limit,
                critical_limit=input_data.critical_limit,
                value_1=0,
                value_2=0,
                difference=0,
                parameter_condition=ok_condition
            )

            return {"message": "Parameter comparison created successfully", "id": new_comparison.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ROUTER.get("/parameter-comparison/time-range/", response_model=List[ParameterComparisonOutput])
async def get_parameter_comparisons_by_time_range(
        start_time: int = Query(..., description="Start time in epoch seconds"),
        end_time: int = Query(..., description="End time in epoch seconds")
):
    try:
        with db_session:
            # Convert epoch timestamps to datetime objects
            start_datetime = datetime.fromtimestamp(start_time)
            end_datetime = datetime.fromtimestamp(end_time)

            # Fetch ParameterComparison entries within the specified time range
            comparisons = list(ParameterComparison.select(
                lambda c: c.time >= start_datetime and c.time <= end_datetime
            ))

            # Convert the Pony ORM objects to dictionaries
            result = []
            for comparison in comparisons:
                result.append({
                    "id": comparison.id,
                    "time": comparison.time,
                    "line": comparison.line,
                    "machine_name": comparison.machine.name,
                    "parameter_group_name": comparison.parameter_group.group_name if comparison.parameter_group else None,
                    "machine_parameter1_name": comparison.machine_parameter1.name,
                    "machine_parameter2_name": comparison.machine_parameter2.name,
                    "warning_limit": comparison.warning_limit,
                    "critical_limit": comparison.critical_limit,
                    "value_1": comparison.value_1,
                    "value_2": comparison.value_2,
                    "difference": comparison.difference,
                    "parameter_condition_name": comparison.parameter_condition.name
                })

            return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ROUTER.get("/getallparameter-comparison/", response_model=List[ParameterComparisonOutput])
async def get_parameter_comparisons():
    try:
        with db_session:
            # Fetch all ParameterComparison entries
            comparisons = ParameterComparison.select()

            # Convert the Pony ORM objects to dictionaries
            result = []
            for comparison in comparisons:
                result.append({
                    "id": comparison.id,
                    "time": comparison.time,
                    "line": comparison.line,
                    "machine_name": comparison.machine.name,
                    "parameter_group_name": comparison.parameter_group.group_name if comparison.parameter_group else None,
                    "machine_parameter1_name": comparison.machine_parameter1.display_name,
                    "machine_parameter2_name": comparison.machine_parameter2.display_name,
                    "machine_parameter1_name_actual": comparison.machine_parameter1.name,
                    "machine_parameter2_name_actual": comparison.machine_parameter2.name,
                    "warning_limit": comparison.warning_limit,
                    "critical_limit": comparison.critical_limit,
                    "time_1": comparison.time_1,
                    "time_2": comparison.time_2,
                    "value_1": comparison.value_1,
                    "value_2": comparison.value_2,
                    "difference": comparison.difference,
                    "parameter_condition_name": comparison.parameter_condition.name
                })

            return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@ROUTER.put("/parameter-comparison/{comparison_id}")
async def update_parameter_comparison(
        comparison_id: int,
        input_data: UpdateParameterComparisonInput,
        # current_user: User = Depends(get_current_active_user),  # Get the current active user
        # is_admin_user: bool = Depends(is_admin)  # Check if the user is an admin
):
    # if not is_admin_user:
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Not authorized to update, Only admin can update",
    #         headers={"WWW-Authenticate": "Bearer"},
    #     )

    try:
        with db_session:
            # Get the existing parameter comparison
            comparison = ParameterComparison.get(id=comparison_id)
            if not comparison:
                raise HTTPException(status_code=404, detail="Parameter comparison not found")

            # Update the warning, critical limits, and set the time to now
            comparison.warning_limit = input_data.warning_limit
            comparison.critical_limit = input_data.critical_limit
            comparison.time = datetime.now()  # Automatically update the time to now

            return {"message": "Parameter comparison updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ROUTER.delete("/parameter-comparison/{comparison_id}")
async def delete_parameter_comparison(
        comparison_id: int,
        # current_user: User = Depends(get_current_active_user),  # Get the current active user
        # is_admin_user: bool = Depends(is_admin)  # Check if the user is an admin
):
    # if not is_admin_user:
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Not authorized to delete, Only admin can delete",
    #         headers={"WWW-Authenticate": "Bearer"},
    #     )

    try:
        with db_session:
            # Get the existing parameter comparison
            comparison = ParameterComparison.get(id=comparison_id)
            if not comparison:
                raise HTTPException(status_code=404, detail="Parameter comparison not found")

            # Delete the parameter comparison
            comparison.delete()

            return {"message": "Parameter comparison deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# ENDPOINT FOR THE REAL TIME MACHINES DISCCONCTED LOGS FROM THE MONGODB

@ROUTER.get("/factory/disconnected_machines", response_model=dict)
async def get_disconnected_machines():
    """
    GET DISCONNECTED MACHINES DATA
    =============================
    This API retrieves the list of disconnected machines in the factory.
    """
    try:
        response_data = get_disconnected_machines_data()
        return response_data
    except Exception as error:
        # Log the error for debugging purposes
        LOGGER.error(f"An unexpected error occurred: {error}")
        # Extract the error message for the client response
        error_message = str(error)
        raise HTTPException(status_code=500, detail={"error": error_message})




# MACHINE DISCONNETED HISTORY LOGS

@ROUTER.get("/factory/disconnection_history", response_model=DisconnectionHistoryResponse)
async def get_disconnection_history(l1name: str, from_timestamp: int, to_timestamp: int):
    try:
        response_data = get_disconnection_history_data(l1name, from_timestamp, to_timestamp)
        return {"history": response_data}
    except ValueError as ve:
        LOGGER.error(f"Validation error: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as error:
        LOGGER.error(f"An unexpected error occurred: {error}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve disconnection history: {str(error)}")


# Add timezone for IST
IST = timezone(timedelta(hours=5, minutes=30))

@ROUTER.get("/get-parameter-comparison-history/", response_model=Dict[str, List[ParameterComparisonOutput_mongodb]])
async def get_parameter_comparison_history(
        machine_name: str,
        parameter1: str,
        parameter2: str,
        from_datetime: int,  # Unix timestamp (seconds)
        to_datetime: int  # Unix timestamp (seconds)
):
    try:
        collection = get_mongo_collection("L1Signal_Pool")
        logging.info(f"Connected to MongoDB collection: {collection.name}")
        from_datetime_obj = datetime.fromtimestamp(from_datetime, tz=timezone.utc)
        to_datetime_obj = datetime.fromtimestamp(to_datetime, tz=timezone.utc)
        logging.info(f"Searching for data between {from_datetime_obj} and {to_datetime_obj}")

        def search_parameter(param_name):
            pipeline = [
                {
                    '$match': {
                        'L1Name': machine_name,
                        'signalname': param_name,
                        'updatedate': {'$gte': from_datetime_obj},
                        'enddate': {'$lte': to_datetime_obj}
                    }
                },
                {
                    '$sort': {
                        'updatedate': 1
                    }
                },
                {
                    '$project': {
                        'updatedate': 1,
                        'enddate': 1,
                        'timespan': 1,
                        'value': 1,
                        'signalname': 1
                    }
                }
            ]
            results = list(collection.aggregate(pipeline))
            return results

        # Perform search for both parameters
        param1_data = search_parameter(parameter1)
        param2_data = search_parameter(parameter2)

        # Helper function to create output items
        def create_output_items(param_data, parameter_name):
            items = []
            for idx, entry in enumerate(param_data):
                updatedate = entry.get('updatedate')
                timespan = entry.get('timespan', 0)
                value = entry.get('value')

                if updatedate:
                    time_dt = updatedate + timedelta(seconds=timespan)
                else:
                    time_dt = updatedate

                # Convert time to IST
                if time_dt:
                    time_dt = time_dt.astimezone(IST)

                # Replace null values with 0
                if value is None:
                    value = 0

                item = ParameterComparisonOutput_mongodb(
                    id=idx,
                    time=time_dt,
                    machine_name=machine_name,
                    parameter_name=parameter_name,
                    value=value
                )
                items.append(item)
            return items

        # Collect output items for both parameters
        output_param1 = create_output_items(param1_data, parameter1)
        output_param2 = create_output_items(param2_data, parameter2)

        logging.info(f"Total results found: {len(output_param1)} for parameter1, {len(output_param2)} for parameter2")

        if not output_param1 and not output_param2:
            logging.warning(
                f"No data found for {machine_name} with parameters {parameter1} and {parameter2} in the specified time range.")

        return {
            "parameter1_data": output_param1,
            "parameter2_data": output_param2
        }

    except Exception as e:
        logging.error(f"Error fetching parameter comparison history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))