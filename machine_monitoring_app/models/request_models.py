#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Response Model Classes
================================

Module that contains pydantic classes for the api endpoint response models in the application

This script requires the following modules be installed in the python environment

    Standard Library
    =================

    * logging - To perform logging operations.

    Related 3rd Party Library
    =============================

    * pydantic - To perform data validation and settings management using python type annotations.
"""

# Standard library imports
from typing import Optional
from datetime import date, datetime

# Related third party imports
from pydantic import BaseModel, validator

# Local application/library specific imports
# None

__author__ = "smt18m005@iiitdm.ac.in"


def convert_to_date(v: str) -> date:
    try:
        print("$" * 10)
        print(v)
        print(date.fromisoformat(v))
        return date.fromisoformat(v)  # Use fromisoformat for flexible parsing
    except ValueError:
        raise ValueError("Invalid date format")


class RequestUserModel(BaseModel):
    """
    PYDANTIC MODEL FOR USER IN DATABASE
    ==========================================

    This is a class (pydantic class) to represent a user, for authentication purposes.
    """

    username: str
    email: Optional[str] = None
    password: str
    role: Optional[str] = "guest"
    company_id: Optional[int] = None


class PendingActivityModel(BaseModel):
    """
    PYDANTIC MODEL FOR USER IN DATABASE
    =====================================

    This is a class (pydantic class) to represent a user, for authentication purposes.
    """

    parameter_name: str
    target_date_of_completion: Optional[str] = ""
    corrective_measurement: Optional[str] = None
    spare_required: Optional[str] = None
    support_needed: Optional[str] = None
    responsible_person_company_id: Optional[int] = None
    priority: Optional[str] = None
    status: str


class PendingActivityListModel(BaseModel):
    """
    PYDANTIC MODEL FOR USER IN DATABASE
    ==========================================

    This is a class (pydantic class) to represent a user, for authentication purposes.
    """

    data: list[PendingActivityModel]


class SparePartsToDeleteModel(BaseModel):
    """
    PYDANTIC MODEL FOR LIST OF SPARE PARTS
    ==========================================

    This is a class (pydantic class) to represent a list of spare parts to be deleted
    """
    part_names: list[str]


# Pydantic model for spare part updates
class SparePartUpdate(BaseModel):
    part_name: str  # Optional updates
    reference_part_number: int = 0
    warning_limit: int = 0
    critical_limit: int = 0


# Pydantic model for spare part updates
class SparePartUpdateList(BaseModel):
    data: list[SparePartUpdate]


class SparePartPost(BaseModel):
    data: SparePartUpdate


class ParameterComparisonInput(BaseModel):
    line_name: str
    machine_name: str
    parameter_group_name: Optional[str] = None
    machine_parameter1_name: str
    machine_parameter2_name: str
    warning_limit: Optional[float] = None
    critical_limit: Optional[float] = None

class UpdateParameterComparisonInput(BaseModel):
    warning_limit: float
    critical_limit: float

