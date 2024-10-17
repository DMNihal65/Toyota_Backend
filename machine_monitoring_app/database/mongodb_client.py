#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
MONGODB DATABASE CONNECTIONS
================================

Module that contains functions to return mongodb database client for connections

This script requires the following modules be installed in the python environment
    * logging - To perform logging operations.

This script contains the following function
    * get_database - Function that return the mongodb database client for connections
"""

# Standard library imports
import logging
from functools import lru_cache

# Related third party imports
from pymongo import MongoClient
from machine_monitoring_app.utils.global_variables import get_settings

# Local application/library specific imports
# None

__author__ = "smt18m005@iiitdm.ac.in"

LOGGER = logging.getLogger(__name__)


@lru_cache()
def get_mongo_client():
    """
    Return the mongo database client object

    :return: The MongoClient instance
    :rtype: MongoClient
    """
    LOGGER.debug("New Request for mongodb client")

    setting = get_settings()

    if setting.mongodb_user:
        MONGODB_URL = f"mongodb://{setting.mongodb_user}:{setting.mongodb_password}@" \
                      f"{setting.mongodb_host}:27017/?authSource=MTLINKi&read" \
                      "Preference=primary&directConnection=true&ssl=false"
    else:
        # MONGODB_URL = "mongodb://localhost:27017/"  #UNCOMMENT THIS IN PRODUCTION
        MONGODB_URL = "mongodb://172.18.7.27:27017/"

    # MongoClient('mongodb://localhost:27017/')
    return MongoClient(MONGODB_URL)


def get_mongo_collection(collection="L1Signal_Pool"):
    """
    Get a collection from a mongo database

    :param collection: Name of the collection
    :type collection: str

    :return: The collection
    """
    client = get_mongo_client()
    return client['MTLINKi'][collection]


def get_mongo_collection_active(collection="L1Signal_Pool_Active"):
    """
    Get a collection from a mongo database

    :param collection: Name of the collection
    :type collection: str

    :return: The collection
    """
    client = get_mongo_client()
    return client['MTLINKi'][collection]
