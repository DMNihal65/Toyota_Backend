#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Response Model Classes
================================

Module that contains pydantic classes for the api endpoint response models in the application

This script requires the following modules be installed in the python environment
    * logging - To perform logging operations.
    * pydantic - To perform data validation and settings management using python type annotations.
"""

# Standard library imports
from datetime import datetime
from enum import IntEnum
from typing import Union, Optional, List, Dict
# Related third party imports
from pydantic import BaseModel, Field

# Local application/library specific imports
from machine_monitoring_app.models.base_data_models import User

__author__ = "smt18m005@iiitdm.ac.in"


class StateEnum(IntEnum):
    """

    This class represents the enum type that will be used to represent the three machine/ parameter states

    """
    OK = 1
    WARNING = 2
    CRITICAL = 3


class ParameterData(BaseModel):
    """

    This is used as part of the response model, that denotes the individual parameters (will be used by MachineData)

    """

    # Represents the parameter name (as integer)
    name: int

    # Represents the parameter name (as string)
    actual_name: str

    # Represents the recent update timestamp for the parameter
    last_update_time: float

    # Represents the value of the parameter
    value: float

    # Represents the status of the parameter
    status: StateEnum


class MachineData(BaseModel):
    """

    This is used as response model for current status of the machine

    """

    # Represents the machine name
    name: str

    # Represents the machine state, either ok, warning or critical
    status: StateEnum

    # Represents the requested parameters
    axes: list[ParameterData]


class CurrentData(BaseModel):
    """

    This is used as response model for current status of the machine

    """

    # Represents the parameter name (as integer)
    param: int

    # Represents the actual parameter name in the database
    param_actual_name: str

    # All machines data
    machines: list[MachineData]

    # State of parameter group
    params_group_status: list[StateEnum]


class SpmStateData(BaseModel):
    """

    This is used as response model for current status of SPM machines

    """

    spm_machine_status: list[StateEnum]


class SpareSubStateData(BaseModel):
    """

    This is used as response model for current status of spare parts of machines (sub)

    """

    warning_machines: list[str]

    critical_machines: list[str]


class SpareStateData(BaseModel):
    """

    This is used as response model for current status of spare parts of machines

    """

    spare_machine_status: SpareSubStateData


class FullTimelineData(BaseModel):
    """

    This is used as response model for sending full timeline data of a given machine, parameter group
    and axis

    """

    # Represents the parameter name (as integer)
    param: int

    # Represents the axis identifier (as integer)
    axis: int | str

    # Represents the actual machine name in the database
    machine: str

    # Start time of query
    start_time: float

    # End time of query
    stop_time: float

    # Real time data of the parameter
    data: list[float]

    # Corresponding parameters
    timestamps: list[float]

    # critical limit values
    critical_limit: Optional[float]

    # warning limit values
    warning_limit: Optional[float]


class LegendData(BaseModel):
    x_axis_label: str = "Timestamp",
    y_axis_label: str = "Temperature",
    x_axis_units: str = "DateTime",
    y_axis_units: str = "'c"


class MachineAnalytics(BaseModel):
    """

    This represents individual machine level abnormality report

    """

    # Represents the parameter group name
    parameter_group_name: str

    # Total Number of abnormalities
    total_abnormality: int

    # Total Number of warning counts
    warning: int

    # Total Number of critical counts
    critical: int


class MachineAnalyticsSummary(BaseModel):
    """

    This represents a list of abnormality of a machine

    """

    data: list[MachineAnalytics]


class ParameterAnalytics(BaseModel):
    """

    This represents individual machine level abnormality report

    """

    # Represents the parameter group name
    machine_name: str

    # Total Number of abnormalities
    total_abnormality: int

    # Total Number of warning counts
    warning: int

    # Total Number of critical counts
    critical: int


class MaintenanceAnalytics(BaseModel):
    """

    This represents individual machine level abnormality report

    """

    # Represents the operator name
    operator_name: str

    # Maintenance Operator Id
    operator_company_id: int

    # Total Number of abnormalities
    total_abnormality: int


class ParameterAnalyticsSummary(BaseModel):
    """

    This represents a list of abnormality of a machine

    """

    data: list[ParameterAnalytics]


class MaintenanceAnalyticsSummary(BaseModel):
    """

    This represents a list of abnormality of a machine

    """

    data: list[MaintenanceAnalytics]


class FullTimelineDataUsingParameterName(BaseModel):
    """

    This is used as response model for sending full timeline data of a given machine, parameter group
    and axis

    """

    # Represents the parameter name (as integer)
    parameter_name: str

    # Real time data of the parameter
    chart_data: list[list[float | None]]

    # critical limit values
    critical_limit: Optional[float]

    # warning limit values
    warning_limit: Optional[float]

    legend_data: LegendData

    message: Optional[str]


class SpmPositionData(BaseModel):
    """

    This is used as response model for sending full position based data of a given spm machine and parameter

    """

    # Represents the parameter name
    param: str

    # Represents the actual machine name in the database
    machine: str

    # Real time data of the parameter
    data: list[float]

    # Corresponding parameters
    position: list[float]


class StatusSummaryData(BaseModel):
    """

    This is used as response model for sending full timeline data of a given machine, parameter group
    and axis

    """

    # Represents the total time in seconds the machine/ all machines in production line was
    # ALARM state
    ALARM: int

    # Represents the total time in seconds the machine/ all machines in production line was
    # DISCONNECT state
    DISCONNECT: int

    # Represents the total time in seconds the machine/ all machines in production line was
    # EMERGENCY state
    EMERGENCY: int

    # Represents the total time in seconds the machine/ all machines in production line was
    # MANUAL state
    MANUAL: int

    # Represents the total time in seconds the machine/ all machines in production line was
    # OPERATE state
    OPERATE: int

    # Represents the total time in seconds the machine/ all machines in production line was
    # STOP state
    STOP: int

    # Represents the total time in seconds the machine/ all machines in production line was
    # SUSPEND state
    SUSPEND: int


class StatusSummary(BaseModel):
    """

    This is used as response model for sending full timeline data of a given machine, parameter group
    and axis

    """

    # Represents the hour/day (time slot) for the summary data
    current_hour_day: int

    # Represents the actual data
    data: StatusSummaryData


class StatusSummaryResponseData(BaseModel):
    """

    This is used as response model for sending full timeline data of a given machine, parameter group
    and axis

    """

    # Represents the hour (time slot) for the summary data
    requested_time: int

    requested_factory_object: str

    requested_day_range: str

    # Represents the actual data
    requested_data: list[StatusSummary]


class SparePart(BaseModel):
    """
    Represents the spare part model used as response model for sending back the created data to client
    """

    # Represents the spare part name
    id: int

    # Represents the spare part name
    part_name: str

    # Represents the warning set limit
    warning_limit: int

    # Represents the critical set limit
    critical_limit: int

    # Represents the default count of the spare part
    count: int = 0


class GetSparePartResponse(BaseModel):
    """
    Represents the spare part model used as response model for sending back the created data to client
    """

    # Represent the total part count from the machine
    total_count: int

    # Represent the current part count from the machine (since the reset button was clicked on the machine)
    current_count: int

    # Represents the individual spare part details
    spare_parts: list[SparePart]


class AlarmCountData(BaseModel):
    """
    Represents the alarm summary response model used as response model for sending back the alarm
    summary data to client
    """

    # Represent the message / alarm name
    message: str

    # Represents the alarm count
    total_count: int


class AlarmTimeData(BaseModel):
    """
    Represents the alarm timespan summary response model used as response model for sending back the alarm
    summary data to client
    """

    # Represent the message / alarm name
    message: str

    # Represents the alarm timespan in seconds
    total_time: float


class AlarmTimelineData(BaseModel):
    """
    Represents the alarm timespan summary response model used as response model for sending back the alarm
    summary data to client
    """

    # Represent the start time of the alarm in epoch seconds
    enddate_epoch_time: float

    # Represent the end  time of the alarm in epoch seconds
    update_epoch_time: float

    message: str

    timespan: float


class AlarmModel(BaseModel):
    """
    Represents the alarm summary response model used as response model for sending back the alarm
    summary data to client
    """

    # Represent the row id
    count_data: list[AlarmCountData]

    timespan_data: list[AlarmTimeData]

    timeline_data: list[AlarmTimelineData]


class AlarmSummaryResponseModel(BaseModel):
    """
    Represents the alarm summary response model used as response model for sending back the alarm
    summary data to client
    """

    # Represent the alarm response data
    data: AlarmModel


class SpareDeleteResponseModel(BaseModel):
    """
    Represents the Spare part delete response model used as response model for sending back the message when
    a spare is deleted
    """

    # Represent the message detail
    detail: str

    # Name of the spare part that was deleted
    spare_part: str


class UserDeleteResponseModel(BaseModel):
    """
    Represents the User delete response model used as response model for sending back the message when
    a user is deleted
    """

    # Represent the message detail
    detail: str

    # Name of the user that was deleted
    user_name: str


class UpdateParameterLimitResponseModel(BaseModel):
    """
    Represents the alarm summary response model used as response model for sending back the alarm
    summary data to client
    """

    # Represents the parameter set type
    set_type: str

    # Represents the parameter set value
    value: Union[float, list[float]]

class UpdateLogResponse(BaseModel):
    user: str
    parameter_name: str
    limit_value: Optional[float] = None
    reference_signal: Optional[List[float]] = None
    set_type: str
    date_changed: datetime
    previous_limit: Optional[float] = None

class MachineParameterResponseModel(BaseModel):
    """
    Represents the machine parameter response model used as response model for sending back the
    parameter data to client
    """

    # Represents the machine parameter data
    parameter_data: list[str]


class ParameterStateData(BaseModel):
    """
    Represents the individual machine parameter response model
    """
    name: str
    item_state: str


class MachineParameterResponseModelState(BaseModel):
    """
    Represents the machine parameter response model used as response model for sending back the
    parameter data to client
    """

    # Represents the machine parameter data
    data: list[ParameterStateData]


class UsersResponseModel(BaseModel):
    """
    Represents the users response model used as response model for sending back the list of all available users
    """

    # Represents the machine parameter data
    user_data: list[User]


#############################################
# Front End Utility Route Response Models
#############################################

class Parameter(BaseModel):
    internal_parameter_name: str
    display_name: str
    actual_parameter_name: str


class Machine(BaseModel):
    machine_name: str
    parameters: list[Parameter]


class Line(BaseModel):
    line_name: str
    machines: list[Machine]


class Group(BaseModel):
    group_name: str
    group_details: list[Line]


class FactoryLayout(BaseModel):
    layout_details: list[Group]


####################################
# Second Test
####################################

class StateCounter(BaseModel):
    OK: int = 0
    WARNING: int = 0
    CRITICAL: int = 0


class ParameterSchema(BaseModel):
    internal_parameter_name: str = "A0-P1"
    display_name: str = "X"
    actual_parameter_name: str
    latest_update_time: int
    parameter_value: Optional[Union[float, None]]
    parameter_state: str
    warning_limit: Optional[Union[float, None]]
    critical_limit: Optional[Union[float, None]]


class MachineSchema(BaseModel):
    machine_name: str
    parameters: list[ParameterSchema]
    machine_state: str = "OK"


class LocationSchema(BaseModel):
    line_name: str
    count: StateCounter
    machines: list[MachineSchema]
    line_state: str = "OK"


class GroupSchema(BaseModel):
    group_name: str
    count: StateCounter
    group_details: list[LocationSchema]
    group_state: str = "OK"


class MachineList(BaseModel):
    data: list[str]


class GroupOverview(BaseModel):
    item_name: str
    item_state: str


class FactorySchema(BaseModel):
    group_names: list[GroupOverview]
    all_group_details: list[GroupSchema]


class SpecificGroupSchema(BaseModel):
    group_names: list[GroupOverview]
    requested_group_details: GroupSchema


class StateCounter2(BaseModel):
    OK: int = 0
    WARNING: int = 0
    CRITICAL: int = 0
    DISCONNECTED: int = 0


class LocationSchema2(BaseModel):
    line_name: str
    count: StateCounter2
    machines: list[MachineSchema]
    line_state: str = "OK"


class GroupSchema_test(BaseModel):
    group_name: str
    count: StateCounter2
    group_details: list[LocationSchema2]
    group_state: str = "OK"


class SpecificGroupSchema_test(BaseModel):
    group_names: list[GroupOverview]
    requested_group_details: GroupSchema_test


"----------------added new schema for new layout(frontend utility)--------------------"
class Parameter_new(BaseModel):
    actual_parameter_name: str
    display_name: str
    internal_parameter_name: str
    latest_update_time: int
    parameter_value: Union[float, None]
    parameter_state: str
    warning_limit: Union[float, None]
    critical_limit: Union[float, None]

class Machine_new(BaseModel):
    machine_name: str
    machine_state: str
    count: Dict[str, int]
    parameters: List[Parameter_new]

class Line_new(BaseModel):
    line_name: str
    line_state: str
    count: Dict[str, int]
    machines: List[Machine_new]

class FactorySchema_new(BaseModel):
    lines: List[Line_new]

class new_Parameter(BaseModel):
    actual_parameter_name: str
    display_name: str
    internal_parameter_name: str
    latest_update_time: int
    parameter_value: Optional[float]
    parameter_state: str
    warning_limit: Optional[float]
    critical_limit: Optional[float]

class new_MachineCount(BaseModel):
    OK: int
    WARNING: int
    CRITICAL: int


class new_Machine(BaseModel):
    machine_name: str
    machine_state: str
    count: new_MachineCount
    parameters: List[new_Parameter]


class new_LineCount(BaseModel):
    OK: int
    WARNING: int
    CRITICAL: int


class new_Line(BaseModel):
    line_name: str
    line_state: str
    count: new_LineCount
    machines: List[new_Machine]


class new_ResponseModel(BaseModel):
    lines: List[new_Line]

class ParameterComparisonOutput(BaseModel):
    id: int
    time: datetime
    line: str
    machine_name: str
    parameter_group_name: str | None
    machine_parameter1_name: str
    machine_parameter2_name: str
    machine_parameter1_name_actual: str
    machine_parameter2_name_actual: str
    warning_limit: float
    critical_limit: float
    time_1: datetime | None
    time_2: datetime | None
    value_1: float
    value_2: float
    difference: float
    parameter_condition_name: str


class DisconnectedMachineSchema(BaseModel):
    L1Name: str
    value: str
    updatedate: str

class DisconnectedMachinesResponse(BaseModel):
    Head: List[DisconnectedMachineSchema]
    Block: List[DisconnectedMachineSchema]
    Crank: List[DisconnectedMachineSchema]


# Define the response model for the disconnection history
class DisconnectionHistoryItem(BaseModel):
    L1Name: str
    updatedate: datetime
    enddate: Optional[datetime]
    timespan: int

class DisconnectionHistoryResponse(BaseModel):
    history: List[DisconnectionHistoryItem]



class ParameterComparisonOutput_mongodb(BaseModel):
    id: int
    time: datetime
    machine_name: str
    parameter_name: str
    value: float