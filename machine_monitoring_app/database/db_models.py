#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
DATABASE MODELS
================================

Module consisting of SQLMODEL representing the tables in the sql

This script requires the following modules be installed in the python environment
    * logging - To perform logging operations.
    * pprint - To pretty print the output from database operations.

This script contains the following function
    * get_current_machine_data - Function that connects to database to get the current machine details
"""

# Standard Python Imports
from datetime import datetime, timedelta

from typing import List, Optional

# Related External Imports
from sqlmodel import Field, Relationship, SQLModel, MetaData, create_engine, Session, select


# Local Imports
from machine_monitoring_app.database import TIMESCALEDB_URL


class Units(SQLModel, table=True):

    metadata = MetaData(schema="tiei_sample_4")

    __tablename__ = "units"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    short_name: str = Field(index=True)
    description: Optional[str] = None
    type: str

    parameters: List["MachineParameters"] = Relationship(back_populates="units")


class Events(SQLModel, table=True):
    """

    Represents that table that stores that category of events that could happen to a machine

    """

    metadata = MetaData(schema="tiei_sample_4")

    __tablename__ = "events"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: str

    machine_event_timeline: List["MachineEventTimeline"] = Relationship(back_populates="events")


class ParameterConditions(SQLModel, table=True):
    """

    Represents the table that stores information about the possible condition that a parameter could take

    """

    metadata = MetaData(schema="tiei_sample_4")

    __tablename__ = "parameter_conditions"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str

    real_time_machine_parameters: List["RealTimeMachineParameters"] = \
        Relationship(back_populates="parameter_conditions")


class Machines(SQLModel, table=True):
    """

    Represents that table that stores information about all machines

    """

    metadata = MetaData(schema="tiei_sample_4")

    __tablename__ = "machines"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    location: Optional[str] = None
    machine_number: Optional[str] = None
    short_name: Optional[str] = None
    description: Optional[str] = None
    enabled: bool = True
    parameters: int

    machine_parameters: List["MachineParameters"] = Relationship(back_populates="machines")
    machine_production_timeline: List["MachineProductionTimeline"] = Relationship(back_populates="machines")
    machine_event_timeline: List["MachineEventTimeline"] = Relationship(back_populates="machines")


class MachineParameters(SQLModel, table=True):
    """

    Represents the table that has information about the paramters of all machines

    """

    metadata = MetaData(schema="tiei_sample_4")

    __tablename__ = "machine_parameters"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    machine_id: int = Field(index=True, foreign_key="machines.id")
    unit_id: int = Field(foreign_key="units.id")
    ok_condition_range: Optional[int] = None
    warning_condition_range: Optional[int] = None
    critical_condition_range: Optional[int] = None

    units: Units = Relationship(back_populates="machine_parameters")
    machines: Machines = Relationship(back_populates="machine_parameters")
    real_time_machine_parameters: List["RealTimeMachineParameters"] = \
        Relationship(back_populates="machine_parameters")
    event_static_machine_parameters: List["EventStaticMachineParameters"] =  \
        Relationship(back_populates="machine_parameters")


class RealTimeMachineParameters(SQLModel, table=True):
    """

    Represents the table that stores the real time parameters

    """

    metadata = MetaData(schema="tiei_sample_4")

    __tablename__ = "real_time_machine_parameters"

    time: datetime = Field(primary_key=True)
    machine_parameters_id: int = Field(primary_key=True, foreign_key="machine_parameters.id")
    value: float
    condition_id: Optional[int] = Field(index=True, foreign_key="parameter_conditions.id")

    machine_parameters: MachineParameters = Relationship(back_populates="real_time_machine_parameters")
    parameter_conditions: Optional[ParameterConditions] = \
        Relationship(back_populates="real_time_machine_parameters")


class MachineProductionTimeline(SQLModel, table=True):
    """

    Represents the  machine production timeline with history of part that was manufactured

    """

    metadata = MetaData(schema="tiei_sample_4")

    __tablename__ = "machine_production_timeline"
    id: Optional[int] = Field(default=None, primary_key=True)
    start_time: datetime
    end_time: datetime
    machine_id: int = Field(index=True, foreign_key="machines.id")
    part_number: str = Field(index=True)
    duration: Optional[timedelta] = None
    machine_event_timeline_id: Optional[int] = Field(default=None, foreign_key="machine_event_timeline.id")

    machines: Machines = Relationship(back_populates="machine_production_timeline")
    machine_event_timeline: Optional["MachineEventTimeline"] = \
        Relationship(back_populates="machine_production_timeline")


class MachineEventTimeline(SQLModel, table=True):
    """

    Represents the event history of machine, such as cycle complete, machine breakdown

    """

    metadata = MetaData(schema="tiei_sample_4")

    __tablename__ = "machine_event_timeline"

    id: Optional[int] = Field(default=None, primary_key=True)
    machine_id: int = Field(index=True, foreign_key="machines.id")
    start_time: datetime
    end_time: Optional[datetime] = None

    # This is actually an interval type in the database, hence we have to use timedelta in python
    duration: Optional[timedelta] = None
    events_id: int = Field(foreign_key="events.id")

    machines: Machines = Relationship(back_populates="machine_event_timeline")
    events: Events = Relationship(back_populates="machine_event_timeline")

    # This would actually be a list of size one
    machine_production_timeline: List[MachineProductionTimeline] = \
        Relationship(back_populates="machine_event_timeline")

    event_static_machine_parameters: List["EventStaticMachineParameters"] = \
        Relationship(back_populates="machine_event_timeline")


class EventStaticMachineParameters(SQLModel, table=True):
    """

    Represents the table that stores the static parameters for all machines, that doesn't change during machning

    """

    metadata = MetaData(schema="tiei_sample_4")

    __tablename__ = "event_static_machine_parameters"
    id: Optional[int] = Field(default=None, primary_key=True)
    machine_event_timeline_id: int = Field(index=True, foreign_key="machine_event_timeline.id")
    machine_parameters_id: int = Field(index=True, foreign_key="machine_parameters.id")
    value: float

    machine_event_timeline: MachineEventTimeline = Relationship(back_populates="event_static_machine_parameters")
    machine_parameters: MachineParameters = Relationship(back_populates="event_static_machine_parameters")


def main():

    engine = create_engine(TIMESCALEDB_URL)

    #SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        statement = select(MachineParameters)
        item = session.exec(statement).first()
        print(item)
        #print(item.machine_parameters.machine_id)


if __name__ == "__main__":
    main()
