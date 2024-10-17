# -*- coding: utf-8 -*-
"""
front_end_utility_route.py

This module defines FastAPI endpoints for handling additional data related to the front end such as factory layout.
These endpoints provide information to dynamically create the factory layout on the front end.

Endpoints:
- /api/factory-layout-info: Retrieve information about the factory layout.
- /api/other-endpoint: [Add description]

Author: Praveen Kumar G
"""

# Standard Imports
import logging
import time
from typing import Union, Optional
from datetime import datetime

# Related third party imports
import pytz
from fastapi import APIRouter, Depends, HTTPException, status
import pandas as pd
import psycopg2

# Local application/library specific imports
from machine_monitoring_app.models.response_models import FactoryLayout, FactorySchema, FactorySchema_new, \
     new_ResponseModel

from machine_monitoring_app.database.crud_operations import get_real_time_parameters_data, \
    get_real_time_parameters_data_mtlinki, get_real_time_layout_data, get_real_time_parameters_data_mtlinki_new_layout

from machine_monitoring_app.routers.router_dependencies import get_current_active_user

LOGGER = logging.getLogger(__name__)

# Depends(get_current_active_user)
ROUTER = APIRouter(
    prefix="/api/v1",
    tags=["Front End Utility Data Routes"],
    # dependencies=[Depends(get_current_active_user)],
    responses={404: {"description": "Not found"}})


@ROUTER.get("/factory/layout", response_model=FactorySchema)
async def read_factory_layout():
    """
    GET PARAMETER LAYOUT DATA
    ===============================

    This API is used to query the status of the factory.
    """

    start_time = time.time()
    try:
        response_data = get_real_time_parameters_data()
        end_time = time.time() - start_time
        LOGGER.info(f"Total Time Taken For this endpoint: {(round((end_time * 1000), 2))} ms")
        return response_data

    except ValueError as ve:
        # Log the error for debugging purposes
        LOGGER.error(f"ValueError in get_real_time_parameters_data: {ve}")

        # Extract the error message for the client response
        error_message = str(ve)
        raise HTTPException(status_code=422, detail={"error": error_message})

    except Exception as error:
        # Log the error for debugging purposes
        LOGGER.error(f"An unexpected error occurred: {error}")

        # Extract the error message for the client response
        error_message = str(error)
        raise HTTPException(status_code=500, detail={"error": error_message})



#TODO : UUPDATING THE ROUTES USING THE MTLINKI

@ROUTER.get("/factory/layout_mtlinki", response_model=FactorySchema)
async def read_factory_layout_mtlinki():
    """
    GET PARAMETER LAYOUT DATA
    ===============================

    This API is used to query the status of the factory.
    """

    start_time = time.time()
    try:
        response_data = get_real_time_parameters_data_mtlinki()
        end_time = time.time() - start_time
        LOGGER.info(f"Total Time Taken For this endpoint: {(round((end_time * 1000), 2))} ms")
        return response_data

    except ValueError as ve:
        # Log the error for debugging purposes
        LOGGER.error(f"ValueError in get_real_time_parameters_data: {ve}")

        # Extract the error message for the client response
        error_message = str(ve)
        raise HTTPException(status_code=422, detail={"error": error_message})

    except Exception as error:
        # Log the error for debugging purposes
        LOGGER.error(f"An unexpected error occurred: {error}")

        # Extract the error message for the client response
        error_message = str(error)
        raise HTTPException(status_code=500, detail={"error": error_message})


# --------------------------------------NEW LAYOUT---------------------------------------------
@ROUTER.get("/factory/new_layout", response_model=FactorySchema_new)
async def read_factory_layout():
    """
    GET PARAMETER LAYOUT DATA
    ===============================

    This API is used to query the status of the factory.
    """

    start_time = time.time()
    try:
        response_data = get_real_time_layout_data()
        end_time = time.time() - start_time
        LOGGER.info(f"Total Time Taken For this endpoint: {(round((end_time * 1000), 2))} ms")
        return response_data

    except ValueError as ve:
        # Log the error for debugging purposes
        LOGGER.error(f"ValueError in get_real_time_parameters_data: {ve}")

        # Extract the error message for the client response
        error_message = str(ve)
        raise HTTPException(status_code=422, detail={"error": error_message})

    except Exception as error:
        # Log the error for debugging purposes
        LOGGER.error(f"An unexpected error occurred: {error}")

        # Extract the error message for the client response
        error_message = str(error)
        raise HTTPException(status_code=500, detail={"error": error_message})


@ROUTER.get("/factory/new_layout_mtlinki", response_model=new_ResponseModel)
async def read_factory_layout_mtlinki():
    """
    GET PARAMETER LAYOUT DATA
    ===============================

    This API is used to query the status of the factory.
    """

    start_time = time.time()
    try:
        response_data = get_real_time_parameters_data_mtlinki_new_layout()
        end_time = time.time() - start_time
        LOGGER.info(f"Total Time Taken For this endpoint: {(round((end_time * 1000), 2))} ms")
        return response_data

    except ValueError as ve:
        # Log the error for debugging purposes
        LOGGER.error(f"ValueError in get_real_time_parameters_data: {ve}")

        # Extract the error message for the client response
        error_message = str(ve)
        raise HTTPException(status_code=422, detail={"error": error_message})

    except Exception as error:
        # Log the error for debugging purposes
        LOGGER.error(f"An unexpected error occurred: {error}")

        # Extract the error message for the client response
        error_message = str(error)
        raise HTTPException(status_code=500, detail={"error": error_message})