#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Base Model Classes
================================

Module that contains base pydantic classes used to store data models

This script requires the following modules be installed in the python environment
    * logging - To perform logging operations.

    Related 3rd Party Library
    =============================
    * pydantic - To perform data validation and settings management using python type annotations.
"""

# Standard library imports
from typing import Optional

# Related third party imports
from pydantic import BaseModel
from pydantic import BaseSettings

# Local application/library specific imports
# None

__author__ = "smt18m005@iiitdm.ac.in"


class Settings(BaseSettings):
    """Data model for configuration settings."""

    # Database provider (postgres, sqlite, etc.)
    timescaledb_provider: str

    # Database user
    timescaledb_user: str

    # Database password for user
    timescaledb_password: str

    # Database host identifier
    timescaledb_host: str

    # Database name (within postgresql)
    timescaledb_database: str

    # Mongodb Database port identifier
    timescaledb_port: str

    # Default Logging configuration file path
    logger_configuration_file: str

    # Secret key used for signing jwt credentials
    secret_key: str

    # Mongodb Database user
    mongodb_user: str

    # Mongodb Database password for user
    mongodb_password: str

    # Mongodb Database host identifier
    mongodb_host: str




    class Config:
        env_file = "./configs/.env"
        # env_file = "D:\\PS-CMTI\\Codes\\PycharmProjects\\TIEI\\tiei_main\\configs\\.env"


class EmailSettings(BaseSettings):
    """Data model for configuration settings for email settings."""

    # Mail server  host ip address
    mail_server_host: str

    # Mail server port address
    mail_server_port: int

    # Sender's email address
    sender_email: str

    # Sender email password
    sender_password: str

    # class Config:
    #     env_file = "configs/.env_email_amazon"


class Token(BaseModel):
    """
    RESPONSE CLASS FOR TOKEN REQUEST
    ======================================

    This is a class (pydantic class) to represent the response body when a client request
    a token for an authentication token. so this works with the api route "/token"
    """


    access_token: str
    token_type: str
    role: str


class TokenData(BaseModel):
    """
    TOKEN DATA FOR CURRENT USER
    ======================================

    This is a class (pydantic class) to represent the token data for a current user
    """

    username: Optional[str] = None


class User(BaseModel):
    """
    PYDANTIC MODEL FOR USER
    ======================================

    This is a class (pydantic class) to represent a user, for authentication purposes.
    """

    id: Optional[int] = None
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = False
    role: Optional[str] = None
    company_id: Optional[int] = None


class UserInDB(User):
    """
    PYDANTIC MODEL FOR ACTIVE USER
    ======================================

    This is a class (pydantic class) to represent a user currently active which extends USER class, for authentication
    purposes.
    """

    hashed_password: str
