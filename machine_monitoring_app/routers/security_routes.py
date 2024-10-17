# -*- coding: utf-8 -*-
"""
SECURITY ROUTES MODULE
==================================

This Module consists of api routes for basic login, security and other requirements

This script requires that the following packages be installed within the Python
environment you are running this script in.

    Standard Library
    =================

    * logging - to perform logging operations


    Related 3rd Party Library
    =============================
"""

# Standard Imports
import logging
from datetime import timedelta, datetime

# External Imports
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm

# User Imports
from pony.orm import commit

from machine_monitoring_app.database.pony_models import UserAccessLog
from machine_monitoring_app.routers import ACCESS_TOKEN_EXPIRE_MINUTES
from machine_monitoring_app.routers.router_dependencies import authenticate_user, \
    create_access_token, get_password_hash, get_current_active_user
from machine_monitoring_app.models.request_models import RequestUserModel
from machine_monitoring_app.models.base_data_models import Token
from machine_monitoring_app.database.crud_operations import create_user, log_user_access
from machine_monitoring_app.models.base_data_models import User

LOGGER = logging.getLogger(__name__)

ROUTER = APIRouter(
    prefix="/api/v1",
    tags=["Security Routes"],
    responses={404: {"description": "Not found"}},)


@ROUTER.post("/auth", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    LOGIN API ROUTE
    =====================
    This api route is used to authenticate the user trying to login, create an access token to be used for later
    communications
    :param form_data: This is the html form data from which user information such as name, password are sent
    as part of the html body.
    :return: A dictionary consisting of access token and token type
    :rtype: dict
    """
    user = authenticate_user(form_data.username, form_data.password)
    LOGGER.debug(f"User Name: {form_data.username}")
    LOGGER.debug(f"User password: {form_data.password}")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    log_user_access(user)

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    user_role = user.role
    LOGGER.info("USER ROLE _____________________")
    LOGGER.info(user_role)
    LOGGER.info("_____________________")
    response_data = {"access_token": access_token, "token_type": "bearer", "role": user_role}
    LOGGER.debug(response_data)
    return Token(**response_data)

@ROUTER.post("/register/", response_model=User)
async def register_user(user: RequestUserModel, current_user: User = Depends(get_current_active_user)):
    print("Registering user...")
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized to register, Only admin can register users",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_details = user.dict()
    user_details["hashed_password"] = get_password_hash(user.password)

    del user_details['password']

    user = create_user(**user_details)

    if user:
        return user

    raise HTTPException(status_code=409, detail="User already registered")
