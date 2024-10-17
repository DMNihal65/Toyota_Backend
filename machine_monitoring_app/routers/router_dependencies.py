# -*- coding: utf-8 -*-
"""
ROUTER DEPENDENCIES MODULE
==================================

This Module consists of variables and functions that are required for the functioning of various routers
defined in this subpackage "router"

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
from typing import Optional
from datetime import datetime, timedelta

# External Imports
from fastapi import Depends, HTTPException, status
from jose import JWTError, jwt

# User Imports
from machine_monitoring_app.routers import PASSWORD_CONTEXT, OAUTH2_SCHEME, ALGORITHM
from machine_monitoring_app.database.crud_operations import get_user

from machine_monitoring_app.models.base_data_models import UserInDB, TokenData, User

from machine_monitoring_app.utils.global_variables import get_settings

LOGGER = logging.getLogger(__name__)


def verify_password(unhashed_password: str, hashed_password: str):
    """
    VERIFY PASSWORDS
    ======================

    This function is used to verify is the password from the client (un-hashed) is same as the hashed password
    stored in the database.

    :param unhashed_password: This is the un-hashed password from the client as a plain text
    :param hashed_password: The hashed password of the user stored in the database

    :return: Boolean stating whether the password matched or not
    :rtype: bool
    """

    return PASSWORD_CONTEXT.verify(unhashed_password, hashed_password)


def get_password_hash(password: str):
    """
    HASH A PASSWORD
    ==================

    This function is used to hash a given plain (un-hashed) password

    :param password: The plain un hashed password from the user

    :return: The hashed password
    :rtype: str
    """

    return PASSWORD_CONTEXT.hash(password)


def authenticate_user(username: str, password: str):
    """
    AUTHENTICATE USER
    ==================

    This function is used to authenticate a user by verifying if the password (un-hashed) sent by the client
    is same as the hashed password stored in the database.

    :param username: The username of the user who wants to log in
    :param password: The plain un-hashed password of the user

    :return: Either "False" to indicate the user is not authenticated, or a pydantic user class model representing
    the authenticated user.
    :rtype: Union[UserInDB, bool]
    """

    user = get_user(username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    CREATE ACCESS TOKEN
    ==========================

    This function is used to create an new access token for the user who wants to log in

    :param data: This data will be part of the access jwt token (specifically a field called "sub" which stores the
    username - yes the token will have username details, expiry time etc, for more info see fastapi security page)
    :param expires_delta: The time of expiry for the token

    :return: The JSON Web Token for the current user who wants to log in
    :rtype: str
    """

    setting = get_settings()

    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, setting.secret_key, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(OAUTH2_SCHEME)):
    """
    GET CURRENT USER
    ==================

    This function is used to decode the jwt token received from the client, check for authentication and return
    a pydantic model of the active user.

    :param token: The jwt token sent by the client

    :return: The pydantic model of the current user
    :rtype: UserInDB
    """

    setting = get_settings()

    # Creating an Http exception class to be sent if cannot authorize the user
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Decoding the jwt token using the secret key and algorithm
        payload = jwt.decode(token, setting.secret_key, algorithms=[ALGORITHM])

        # This decoded payload will be a dictionary with various key value pair, one of which is key "sub"
        # Which has the username in it
        username: str = payload.get("sub")

        if username is None:
            raise credentials_exception

        # Creating a pydantic class for representing the token data (which is just a username in this case)
        token_data = TokenData(username=username)

    except JWTError:
        raise credentials_exception

    # Creating pydantic user model
    user = get_user(username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    """
    GET CURRENT ACTIVE USER
    =============================

    This function is used to get the current active user by checking if the user is disabled or not.

    :param current_user: The current user (who needs to be checked if active or not)

    :return: The current user if he is active else raises an http exception
    :rtype: User
    """
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def is_admin(current_user: User = Depends(get_current_user)):
    """
    CHECK IF USER IS ADMIN
    =============================

    This function checks if the current user has admin privileges.

    :param current_user: The current user to check
    :type current_user: User

    :return: True if the user is an admin, False otherwise
    :rtype: bool
    """
    return current_user.role == "admin"