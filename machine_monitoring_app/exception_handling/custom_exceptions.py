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

# Related third party imports


# Local application/library specific imports


__author__ = "smt18m005@iiitdm.ac.in"

LOGGER = logging.getLogger(__name__)


class NoParameterGroupError(Exception):
    pass


class GetParamGroupDBError(Exception):
    """

    This exception is used when the get_parameter_group_status is not able to query data and has encountered problems

    """
    pass


class GetAllParameterDBError(Exception):
    """

    This exception is used when the get_all_parameter_group_status is not able to query data and has encountered problems

    """
    pass


class GetMachineTimelineError(Exception):
    """

    This exception is used when the get_machine_timeline has returned an empty list, meaning that the machine or
    parameter group is not available.

    """
    pass


def main():
    """
    Main Function
    ====================
    
    Main function to call appropriate functions to 

    """


if __name__ == '__main__':
    main()
