#!/usr/bin/python
# -*- coding: utf-8 -*-
"""

================================

Module for  application to

This script requires the following modules be installed in the python environment
    * logging - to perform logging operations

This script contains the following function
    * main - main function to call appropriate functions to find the contours in the video
"""

# Standard library imports
import logging
import re
from datetime import datetime, timezone

# Related third party imports
from pony.orm import commit, db_session

# Local application/library specific imports
from machine_monitoring_app.database.mongodb_client import get_mongo_collection
from machine_monitoring_app.database.pony_models import Machine, MachinePartCount

__author__ = "smt18m005@iiitdm.ac.in"

LOGGER = logging.getLogger(__name__)


def get_count_group_template(start_time_datetime: datetime, end_time_datetime: datetime, machine_name: str):
    """
    Function used to return the aggregation template for getting the alarm counts summary

    :param start_time_datetime: The start time of the query
    :param end_time_datetime: The end time of the query
    :param machine_name: The name of the machine

    :return:
    :rtype:
    """

    count_group = [
        {
            '$match': {
                'L1Name': machine_name,
                'updatedate': {
                    '$gte': start_time_datetime
                },
                'enddate': {
                    '$lte': end_time_datetime
                }
            }
        }, {
            '$group': {
                '_id': '$message',
                'total_count': {
                    '$sum': 1
                }
            }
        }, {
            '$project': {
                'message': '$_id',
                'total_count': 1,
                '_id': 0
            }
        }, {
            '$sort': {
                'total_count': -1
            }
        }
    ]

    return count_group


def get_real_time_data_mtlinki(start_time_datetime: datetime, end_time_datetime: datetime, machine_name: str,
                               parameter_name: str):
    """
    Function used to return the aggregation template for getting the realtime data from mtlinki mongodb

    :param start_time_datetime: The start time of the query
    :param end_time_datetime: The end time of the query
    :param machine_name: The name of the machine
    :param parameter_name: The parameter to be queried

    :return:
    :rtype:
    """

    real_time_data = [
        {
            '$match': {
                'signalname': parameter_name,
                'L1Name': machine_name,
                'updatedate': {
                    '$gte': start_time_datetime
                },
                'enddate': {
                    '$lte': end_time_datetime
                }
            }
        }, {
            '$sort': {
                'updatedate': 1
            }
        }, {
            '$project': {
                '_id': 0,
                'updatedate': 1,
                'value': 1
            }
        }
    ]

    return real_time_data


def get_machine_states_mtlinki(regex_pattern: str):
    """
    Return the mtlinki aggregation template to get the current state of all factory machines within a specified
    parameter group using the MT-Linki interface.

    :param regex_pattern: The regex for the parameter group to be queried

    :return:
    :rtype:
    """

    real_time_data = [
        {
            '$match': {
                'signalname': re.compile(rf"{regex_pattern}")
            }
        }, {
            '$project': {
                '_id': 0,
                'updatedate': 1,
                'signalname': 1,
                'value': 1
            }
        }
    ]

    return real_time_data


def get_value_before_requested_data_mtlinki(start_time_datetime: datetime,
                                            machine_name: str, parameter_name: str):
    """
    Function used to return the aggregation template for getting the one recent value before the request timestamp

    :param start_time_datetime: The start time of the query
    :param machine_name: The name of the machine
    :param parameter_name: The parameter to be queried

    :return:
    :rtype:
    """

    recent_value = [
        {
            '$match': {
                'signalname': parameter_name,
                'L1Name': machine_name,
                'enddate': {
                    '$lte': start_time_datetime
                }
            }
        }, {
            '$sort': {
                'enddate': -1
            }
        }, {
            '$limit': 30
        }, {
            '$project': {
                '_id': 0,
                'value': 1
            }
        }
    ]

    return recent_value


def get_recent_active_pool_value(machine_name: str, parameter_name: str):
    """
    Function used to return the aggregation template for getting the one recent value before the request timestamp
    from L1Signal Pool Active

    :param machine_name: The name of the machine
    :param parameter_name: The parameter to be queried

    :return:
    :rtype:
    """

    recent_value = [
        {
            '$match': {
                'signalname': parameter_name,
                'L1Name': machine_name
            }
        }, {
            '$project': {
                'updatedate': 1,
                'value': 1,
                '_id': 0
            }
        }
    ]

    return recent_value


def get_timespan_group_template(start_time_datetime: datetime, end_time_datetime: datetime, machine_name: str):
    """
    Function used to return the aggregation template for getting the alarm timespan value summary

    :param start_time_datetime: The start time of the query
    :param end_time_datetime: The end time of the query
    :param machine_name: The name of the machine

    :return:
    :rtype:
    """

    timespan_group = [
        {
            '$match': {
                'L1Name': machine_name,
                'updatedate': {
                    '$gte': start_time_datetime
                },
                'enddate': {
                    '$lte': end_time_datetime
                }
            }
        }, {
            '$group': {
                '_id': '$message',
                'total_time': {
                    '$sum': '$timespan'
                }
            }
        }, {
            '$project': {
                'message': '$_id',
                'total_time': 1,
                '_id': 0
            }
        }, {
            '$sort': {
                'total_time': -1
            }
        }
    ]

    return timespan_group


def get_timeline_group_template(start_time_datetime: datetime, end_time_datetime: datetime, machine_name: str):
    """
    Function used to return the aggregation template for getting the full alarm timeline data

    :param start_time_datetime: The start time of the query
    :param end_time_datetime: The end time of the query
    :param machine_name: The name of the machine

    :return:
    :rtype:
    """

    timeline_group = [
        {
            '$match': {
                'L1Name': machine_name,
                'updatedate': {
                    '$gte': start_time_datetime
                },
                'enddate': {
                    '$lte': end_time_datetime
                }
            }
        }, {
            '$project': {
                'message': 1,
                'timespan': 1,
                'enddate_epoch_time': {'$divide': [{'$subtract': [
                    '$enddate', datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
                ]}, 1000]
                },
                'update_epoch_time': {'$divide': [{'$subtract': [
                    '$updatedate', datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
                ]}, 1000]
                },
                '_id': 0
            }
        }, {
            '$sort': {
                'update_epoch_time': -1
            }
        }
    ]

    return timeline_group


def get_recent_most_alarm_time_template(machine_name: str):
    """
    Function used to return the aggregation template for getting the recent most available time for
     the alarm for a given machine

    :param machine_name: The name of the machine

    :return:
    :rtype:
    """

    recent_data = [
        {
            '$match': {
                'L1Name': machine_name
            }
        }, {
            '$sort': {
                'enddate': -1
            }
        }, {
            '$project': {
                'enddate': 1,
                'updatedate': 1,
                '_id': 0
            }
        }, {
            '$limit': 1
        }
    ]

    return recent_data


def get_exceed_group_template(start_time_datetime: datetime, end_time_datetime: datetime,
                              signalname: str = "DISCONNECT", production_line: str = r".*"):
    exceed_group_1 = [
        {
            '$match': {
                'signalname': signalname,
                'L1Name': {
                    '$regex': re.compile(production_line)
                },
                'value': True
            }
        }, {
            '$match': {
                'updatedate': {
                    '$lte': start_time_datetime
                },
                'enddate': {
                    '$gte': end_time_datetime
                }
            }
        }, {
            '$group': {
                '_id': '$signalname',
                'TOTAL_TIME_HOUR': {
                    '$count': {}
                }
            }
        }, {
            '$project': {
                'TOTAL_TIME_SECONDS': {
                    '$multiply': [
                        3600, '$TOTAL_TIME_HOUR'
                    ]
                }
            }
        }
    ]

    return exceed_group_1


def get_exceed_group_day_template(start_time_datetime: datetime, end_time_datetime: datetime,
                                  signalname: str = "DISCONNECT", production_line: str = r".*"):
    """
    Get the template for given day for exceeding group.

    :param start_time_datetime:
    :type start_time_datetime:

    :param end_time_datetime:
    :type end_time_datetime:

    :param signalname:
    :type signalname:

    :param production_line:
    :type production_line:

    :return:
    :rtype:
    """

    exceed_group_1 = [
        {
            '$match': {
                'signalname': signalname,
                'L1Name': {
                    '$regex': re.compile(production_line)
                },
                'value': True
            }
        }, {
            '$match': {
                'updatedate': {
                    '$lte': start_time_datetime
                },
                'enddate': {
                    '$gte': end_time_datetime
                }
            }
        }, {
            '$group': {
                '_id': '$signalname',
                'TOTAL_TIME_DAY': {
                    '$count': {}
                }
            }
        }, {
            '$project': {
                'TOTAL_TIME_SECONDS': {
                    '$multiply': [
                        86400, '$TOTAL_TIME_DAY'
                    ]
                }
            }
        }
    ]

    return exceed_group_1


def get_within_group_template(start_time_datetime: datetime, end_time_datetime: datetime,
                              signalname: str = "DISCONNECT", production_line: str = r".*"):
    within_group_2 = [
        {
            '$match': {
                'signalname': signalname
            }
        }, {
            '$match': {
                'L1Name': {
                    '$regex': re.compile(production_line)
                }
            }
        }, {
            '$match': {
                'updatedate': {
                    '$gte': start_time_datetime
                },
                'enddate': {
                    '$lte': end_time_datetime
                }
            }
        }, {
            '$match': {
                'value': True
            }
        }, {
            '$group': {
                '_id': '$signalname',
                'TOTAL_TIME_SECONDS': {
                    '$sum': '$timespan'
                }
            }
        }
    ]

    return within_group_2


def get_within_group_day_template(start_time_datetime: datetime, end_time_datetime: datetime,
                                  signalname: str = "DISCONNECT", production_line: str = r".*"):
    """
    Template used for mongodb aggregate pipeline that returns the within groups summary for a day.

    :param start_time_datetime:
    :type start_time_datetime:

    :param end_time_datetime:
    :type end_time_datetime:

    :param signalname:
    :type signalname:

    :param production_line:
    :type production_line:

    :return:
    :rtype:
    """

    within_group_2 = [
        {
            '$match': {
                'signalname': signalname
            }
        }, {
            '$match': {
                'L1Name': {
                    '$regex': re.compile(production_line)
                }
            }
        }, {
            '$match': {
                'updatedate': {
                    '$gte': start_time_datetime
                },
                'enddate': {
                    '$lte': end_time_datetime
                }
            }
        }, {
            '$match': {
                'value': True
            }
        }, {
            '$group': {
                '_id': '$signalname',
                'TOTAL_TIME_SECONDS': {
                    '$sum': '$timespan'
                }
            }
        }
    ]

    return within_group_2


def get_between_head_group_template(start_time_datetime: datetime, end_time_datetime: datetime,
                                    signalname: str = "DISCONNECT", production_line: str = r".*"):
    between_head_group_3 = [
        {
            '$match': {
                'signalname': signalname,
                'L1Name': {
                    '$regex': re.compile(production_line)
                },
                'value': True
            }
        }, {
            '$match': {
                'updatedate': {
                    '$lte': start_time_datetime
                },
                'enddate': {
                    '$lte': end_time_datetime,
                    '$gt': start_time_datetime
                }
            }
        }, {
            '$project': {
                'minutes': {
                    '$minute': '$enddate'
                },
                'seconds': {
                    '$second': '$enddate'
                },
                'signalname': 1
            }
        }, {
            '$group': {
                '_id': '$signalname',
                'TOTAL_MINUTES': {
                    '$sum': '$minutes'
                },
                'TOTAL_SECONDS': {
                    '$sum': '$seconds'
                }
            }
        }, {
            '$project': {
                'TOTAL_TIME_SECONDS': {
                    '$sum': [
                        '$TOTAL_SECONDS', {
                            '$multiply': [
                                '$TOTAL_MINUTES', 60
                            ]
                        }
                    ]
                }
            }
        }
    ]

    return between_head_group_3


def get_between_head_group_day_template(start_time_datetime: datetime, end_time_datetime: datetime,
                                        signalname: str = "DISCONNECT", production_line: str = r".*"):
    """

    :param start_time_datetime:
    :type start_time_datetime:

    :param end_time_datetime:
    :type end_time_datetime:

    :param signalname:
    :type signalname:

    :param production_line:
    :type production_line:

    :return:
    :rtype:
    """

    between_head_group_3 = [
        {
            '$match': {
                'signalname': signalname,
                'L1Name': {
                    '$regex': re.compile(production_line)
                },
                'value': True
            }
        }, {
            '$match': {
                'updatedate': {
                    '$lt': start_time_datetime
                },
                'enddate': {
                    '$lte': end_time_datetime,
                    '$gt': start_time_datetime
                }
            }
        }, {
            '$project': {
                'enddate_epoch_time': {'$divide': [{'$subtract': [
                    '$enddate', datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
                ]}, 1000]
                },
                'signalname': 1,
                'start_limit_epoch': {'$divide': [{'$subtract': [
                    start_time_datetime, datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
                ]}, 1000]
                }

            }
        }, {
            '$project': {
                'signalname': 1,
                'seconds': {
                    '$subtract': [
                        '$enddate_epoch_time', '$start_limit_epoch'
                    ]
                }
            }
        }, {
            '$group': {
                '_id': '$signalname',
                'TOTAL_TIME_SECONDS': {
                    '$sum': '$seconds'
                }
            }
        }
    ]

    return between_head_group_3


def get_between_tail_group_template(start_time_datetime: datetime, end_time_datetime: datetime,
                                    signalname: str = "DISCONNECT", production_line: str = r".*"):
    between_tail_group_4 = [
        {
            '$match': {
                'signalname': signalname,
                'L1Name': {
                    '$regex': re.compile(production_line)
                },
                'value': True
            }
        }, {
            '$match': {
                'updatedate': {
                    '$gte': start_time_datetime,
                    '$lt': end_time_datetime
                },
                'enddate': {
                    '$gt': end_time_datetime
                }
            }
        }, {
            '$project': {
                'actual_minutes': {
                    '$subtract': [
                        60, {
                            '$minute': '$updatedate'
                        }
                    ]
                },
                'minutes': {
                    '$minute': '$updatedate'
                },
                'actual_seconds': {
                    '$subtract': [
                        60, {
                            '$second': '$updatedate'
                        }
                    ]
                },
                'seconds': {
                    '$second': '$updatedate'
                },
                'signalname': 1
            }
        }, {
            '$group': {
                '_id': '$signalname',
                'TOTAL_MINUTES': {
                    '$sum': '$actual_minutes'
                },
                'TOTAL_SECONDS': {
                    '$sum': '$actual_seconds'
                }
            }
        }, {
            '$project': {
                'TOTAL_TIME_SECONDS': {
                    '$sum': [
                        '$TOTAL_SECONDS', {
                            '$multiply': [
                                '$TOTAL_MINUTES', 60
                            ]
                        }
                    ]
                }
            }
        }
    ]

    return between_tail_group_4


def get_between_tail_group_day_template(start_time_datetime: datetime, end_time_datetime: datetime,
                                        signalname: str = "DISCONNECT", production_line: str = r".*"):
    between_tail_group_4 = [
        {
            '$match': {
                'signalname': signalname,
                'L1Name': {
                    '$regex': re.compile(production_line)
                },
                'value': True
            }
        }, {
            '$match': {
                'enddate': {
                    '$gt': end_time_datetime
                },
                'updatedate': {
                    '$gte': start_time_datetime,
                    '$lt': end_time_datetime
                }
            }
        }, {
            '$project': {
                'updatedate_epoch_time': {'$divide': [{'$subtract': [
                    '$updatedate', datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
                ]}, 1000]
                },
                'signalname': 1,
                'end_limit_epoch': {'$divide': [{'$subtract': [
                    end_time_datetime, datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
                ]}, 1000]
                }

            }
        }, {
            '$project': {
                'signalname': 1,
                'seconds': {
                    '$subtract': [
                        '$end_limit_epoch', '$updatedate_epoch_time'
                    ]
                }
            }
        }, {
            '$group': {
                '_id': '$signalname',
                'TOTAL_TIME_SECONDS': {
                    '$sum': '$seconds'
                }
            }
        }
    ]

    return between_tail_group_4


def part_signal_aggregate_template():
    """
    Function used to return the aggregate query template to get the part count signal names and their counts

    :return: list of the aggregate configurations
    :rtype: list
    """

    all_part_count_registers = [
        {
            '$match': {
                'signalname': re.compile(r"d9388(?i)")
            }
        }, {
            '$sort': {
                'value': 1
            }
        }, {
            '$project': {
                'L1Name': 1,
                'updatedate': 1,
                'signalname': 1,
                'value': 1,
                '_id': 0
            }
        }
    ]

    return all_part_count_registers


def part_signal_query_with_time(input_timestamp: datetime):
    """
    Function used to return the aggregate query template to get the part count signal names and their counts

    :return: list of the aggregate configurations
    :rtype: list
    """

    all_part_count_data = [
        {
            '$match': {
                'signalname': re.compile(r"d9388(?i)"),
                'updatedate': {
                    '$gt': input_timestamp
                }
            }
        }, {
            '$project': {
                'L1Name': 1,
                'updatedate': 1,
                'signalname': 1,
                'value': 1,
                '_id': 0
            }
        }, {
            '$sort': {
                'updatedate': -1
            }
        }
    ]

    return all_part_count_data


@db_session
def set_part_count():
    """
    Function used to set the part count signalname for all machines

    :return: Nothing
    :rtype: None
    """

    collection = get_mongo_collection("L1Signal_Pool_Active_2")

    # result = collection.aggregate(get_between_head_group_day_template(signalname="EMERGENCY", production_line="T_C",
    #                                                                   start_time_datetime=st_dt,
    #                                                                   end_time_datetime=en_dt))

    part_count_data = collection.aggregate(part_signal_aggregate_template())

    part_count_data = list(part_count_data)

    for part in part_count_data:

        machine = Machine.get(name=part['L1Name'])

        if part['value'] is None:
            data = MachinePartCount(part_signal_name=part['signalname'],
                                    current_part_count=0,
                                    last_reset_count=0,
                                    latest_update_time=part['updatedate'],
                                    machine=machine)
        else:
            data = MachinePartCount(part_signal_name=part['signalname'],
                                    current_part_count=part['value'],
                                    last_reset_count=0,
                                    latest_update_time=part['updatedate'],
                                    machine=machine)
        commit()
    return


def main():
    """
    Main Function
    ====================
    
    Main function to call appropriate functions to 

    """

    # collection = get_mongo_collection()
    #
    # st_dt = datetime(2022, 6, 20, 6, 0, 0, tzinfo=timezone.utc)
    # en_dt = datetime(2022, 6, 21, 6, 0, 0, tzinfo=timezone.utc)

    # result = collection.aggregate(get_between_head_group_day_template(signalname="EMERGENCY", production_line="T_C",
    #                                                                   start_time_datetime=st_dt,
    #                                                                   end_time_datetime=en_dt))

    # result = collection.aggregate(get_between_tail_group_day_template(start_time_datetime=st_dt,
    #                                                                   end_time_datetime=en_dt))

    # result = list(result)
    # print(result)

    set_part_count()


if __name__ == '__main__':
    main()
