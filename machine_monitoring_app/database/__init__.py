# -*- coding: UTF-8 -*-
"""
Initialization For Database Operations
===========================================

This Initialization module imports the necessary functions and modules, create mongodb url connection string.

This script requires that the following packages be installed within the Python
environment you are running this script in.

    * logging - To perform logging operations.
    * os - To interact with os.
    * databases - To create database url using mongodb connection string.
"""

# Standard library imports
import logging

# Local application/library specific imports


__author__ = "smt18m005@iiitdm.ac.in"

LOGGER = logging.getLogger(__name__)

# Max and Min connection count for the database connection pool
# MAX_CONNECTIONS_COUNT = 10
# MIN_CONNECTIONS_COUNT = 10
#
# MONGODB_URL = os.getenv("MONGODB_URL", "")  # deploying without docker-compose
#
# # If the mongodb url is not defined in os environment, then do the following
# if not MONGODB_URL:
#
#     # Load the database connection credentials from the file.
#     credentials_data = load_database_credentials()
#
#     # Create the mongodb database url string
#     MONGODB_URL = DatabaseURL(
#         f"mongodb://{credentials_data['user']}:{credentials_data['password']}@{credentials_data['host']}:"
#         f"{credentials_data['port']}/{credentials_data['database']}"
#     )
#
#
# SQLITE_FILE_NAME = "database.db"
# SQLITE_URL = f"sqlite:///{SQLITE_FILE_NAME}"

# CONNECT_ARGS = {"check_same_thread": False}
# TIMESCALE_ENGINE = create_engine(SQLITE_URL, echo=True, connect_args=CONNECT_ARGS)

# TIMESCALEDB_URL = f"postgres://{INPUT_ARGUMENTS.user}:{INPUT_ARGUMENTS.password}@{INPUT_ARGUMENTS.host}" \
#                   f":5432/{INPUT_ARGUMENTS.database}"

TIMESCALEDB_URL = "postgres://tnga_iot_3:Toyota_2022@10.82.126.73:5432/tiei_test"

USER_DB = {
    "cmti": {
        "username": "cmti",
        "full_name": "CMTI SMDDC",
        "email": "cmti@cmti.res.in",
        "hashed_password": "$2y$10$kmtK6CWajzgOg6VmxUgPzuKrlz2nO0RXvvUxJiXQrvk5gMWN7Aw.e",
        "disabled": False,
            }
        }

# $2y$10$kmtK6CWajzgOg6VmxUgPzuKrlz2nO0RXvvUxJiXQrvk5gMWN7Aw.e - password (unhashed_password)
# $2b$12$RCuPSrRoK15qgq14ShruqeRg0i2s4zuw2UHX80DBqewdqICHtdw2u