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

EMAIL_REPORT_ROOT_DIRECTORY = "./output/email_reports/"

EMAIL_REPORT_ROOT_DIRECTORY_TEMP = "./output/email_reports_temporary/"

EMAIL_MESSAGE = "Please Find the Attached Reports of Recent Anomalies"

# EMAIL_RECIPIENTS = ['shreyas.bk@tiei.toyota-industries.com',
#                     'mohith@tiei.toyota-industries.com',
#                     'vinay.d@tiei.toyota-industries.com',
#                     'vinay.n@tiei.toyota-industries.com',
#                     'Eng_tool@tiei.toyota-industries.com',
#                     'yousuf@tiei.toyota-industries.com',
#                     'murali.c@tiei.toyota-industries.com']

EMAIL_RECIPIENTS = ['praveen06061995@gmail.com',
                    'smt18m005@iiitdm.ac.in']
