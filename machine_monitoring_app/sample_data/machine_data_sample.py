#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
SAMPLE MACHINE DATA
===========================

Module that stores sample machine data to be used for testing.
"""

# Standard library imports
# None

# Related third party imports
# None

# Local application/library specific imports
from machine_monitoring_app.models.response_models import StateEnum

__author__ = "smt18m005@iiitdm.ac.in"


SAMPLE_MACHINE_DATA_CURRENT = [{"machine_name": "MCV-450",

                                "machine_state": StateEnum.OK,
                                "machine_parameters": [{'parameter_name': 'ApcBatLow_0_path1_MCV-450',
                                                        'parameter_state': StateEnum.OK,
                                                        'parameter_value': False},
                                                       {'parameter_name': 'ApcBatLow_1_path1_MCV-450',
                                                        'parameter_state': StateEnum.OK,
                                                        'parameter_value': False},
                                                       {'parameter_name': 'ApcBatLow_2_path1_MCV-450',
                                                        'parameter_state': StateEnum.OK,
                                                        'parameter_value': False},
                                                       {'parameter_name': 'ApcBatZero_0_path1_MCV-450',
                                                        'parameter_state': StateEnum.OK,
                                                        'parameter_value': False},
                                                       {'parameter_name': 'ApcBatZero_1_path1_MCV-450',
                                                        'parameter_state': StateEnum.OK,
                                                        'parameter_value': False},
                                                       {'parameter_name': 'ApcBatZero_2_path1_MCV-450',
                                                        'parameter_state': StateEnum.OK,
                                                        'parameter_value': 2.6}
                                                       ]
                                }]
