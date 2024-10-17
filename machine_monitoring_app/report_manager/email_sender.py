#!/usr/bin/python
# -*- coding: utf-8 -*-
"""

EMAIL SENDER
==================

Module for sending email alerts

This script requires the following modules be installed in the python environment
    Standard Library
    =================

    * logging - to perform logging operations
    * os - to os related operations
    * smtplib - to send email alerts

This script contains the following function
    * main - main function to call appropriate functions to send email alerts

"""

# Standard library imports
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import time

# Related third party imports
import pandas as pd
import xlsxwriter

# Local application/library specific imports
from machine_monitoring_app.report_manager import EMAIL_REPORT_ROOT_DIRECTORY_TEMP, EMAIL_MESSAGE, \
    EMAIL_REPORT_ROOT_DIRECTORY
from machine_monitoring_app.database.crud_operations import get_alert_summary
from machine_monitoring_app.utils.global_variables import get_settings_email_service
from machine_monitoring_app.database.crud_operations import get_user_emails

__author__ = "smt18m005@iiitdm.ac.in"

LOGGER = logging.getLogger(__name__)


def send_mail():
    """

    Function to send emails for new alerts generated

    :return: Nothing
    :rtype: None
    """
    settings = get_settings_email_service()

    try:

        LOGGER.debug("Getting all email ids")
        email_recipients = get_user_emails()

        message = MIMEMultipart()

        message['To'] = ", ".join(email_recipients)

        message['From'] = settings.sender_email

        message['subject'] = "ANOMALY REPORTS"

        message.attach(MIMEText(EMAIL_MESSAGE, 'plain'))

        reports = os.listdir(EMAIL_REPORT_ROOT_DIRECTORY)
        attachments = [(report, EMAIL_REPORT_ROOT_DIRECTORY + report) for report in reports]

        if not attachments:
            LOGGER.info("No New Anomalies")
            return

        for attachment in attachments:
            with open(attachment[1], 'rb') as report_file:
                file = MIMEBase('application', 'octet-stream')
                file.set_payload(report_file.read())
                encoders.encode_base64(file)
                file.add_header('Content-Disposition', "attachment; filename= %s" % attachment[0])

                message.attach(file)

        email_server = smtplib.SMTP(settings.mail_server_host, settings.mail_server_port)
        email_server.ehlo()
        email_server.starttls()
        email_server.ehlo()
        email_server.login(settings.sender_email, settings.sender_password)
        email_server.sendmail(settings.sender_email, email_recipients, message.as_string())
        email_server.quit()
    except Exception as error:
        LOGGER.exception("Error", error.args[0])
        return

    # The reports will be deleted only if they were successfully sent as email
    try:
        for attachment in attachments:
            os.remove(attachment[1])
    except Exception as error:
        LOGGER.exception("Error", error.args[0])


def save_report():
    """
    Function used to save 4 hour summary reports

    :return: Nothing
    :rtype: None
    """

    data_critical = get_alert_summary(condition_id=3)
    data_critical = pd.DataFrame(data=data_critical, columns=['PRODUCTION_LINE',
                                                              'NUMBER_OF_MACHINES',
                                                              'NUMBER_OF_PARAMETERS'])

    data_warning = get_alert_summary(condition_id=2)
    data_warning = pd.DataFrame(data=data_warning, columns=['PRODUCTION_LINE',
                                                            'NUMBER_OF_MACHINES',
                                                            'NUMBER_OF_PARAMETERS'])

    report_file_name_critical = EMAIL_REPORT_ROOT_DIRECTORY + \
                                f"critical_anomaly_summary_report_{int(time.time())}.xlsx"
    report_file_name_warning = EMAIL_REPORT_ROOT_DIRECTORY + \
                               f"warning_anomaly_summary_report_{int(time.time())}.xlsx"

    report_file_name_temp_critical = EMAIL_REPORT_ROOT_DIRECTORY_TEMP + \
                                     f"critical_anomaly_summary_report_{int(time.time())}.xlsx"
    report_file_name_temp_warning = EMAIL_REPORT_ROOT_DIRECTORY_TEMP + \
                                    f"warning_anomaly_summary_report_{int(time.time())}.xlsx"

    # Permanent report files
    data_critical.to_excel(report_file_name_critical)
    data_warning.to_excel(report_file_name_warning)

    # Temporary report files
    data_critical.to_excel(report_file_name_temp_critical)
    data_warning.to_excel(report_file_name_temp_warning)


def create_excel_report(file_location: str, data: list,  parameter_type: str = "static"):
    """
    Function to create a full report

    :return:
    :rtype:
    """
    workbook = xlsxwriter.Workbook(file_location)

    cell_format = workbook.add_format()

    cell_format.set_align('center')
    cell_format.set_align('vcenter')

    # Create a format to use in the merged range.
    merge_format = workbook.add_format({
        'bold': 5,
        'border': 3,
        'align': 'center',
        'valign': 'vcenter',
        'fg_color': 'yellow'})

    worksheet = workbook.add_worksheet("Critical Alerts")

    worksheet.set_column(0, 0, 15, cell_format)
    worksheet.set_column(1, 2, 25, cell_format)
    worksheet.set_column(3, 3, 45, cell_format)
    worksheet.set_column(4, 4, 45, cell_format)
    worksheet.set_column(5, 5, 20, cell_format)
    worksheet.set_column(6, 8, 15, cell_format)

    # Merge cells
    worksheet.merge_range('A1:J1', 'Merged Range', merge_format)
    #
    # # Merge 3 cells over two rows.
    # worksheet.merge_range('B7:D8', 'Merged Range', merge_format)

    worksheet.write('A1', 'TNGA Machining Abnormality report')

    start_cell_static = "B8"
    end_cell_static = "I" + str(8 + len(data))
    end_cell_dynamic = "F" + str(8 + len(data))
    end_cell_part = "I" + str(8 + len(data))

    worksheet.merge_range('A6:D6', 'Merged Range', merge_format)
    worksheet.write('A6', 'Critical Alerts')

    if parameter_type == "static":
        worksheet.add_table(f'{start_cell_static}:{end_cell_static}',
                            {'data': data,
                             'columns': [{'header': 'S.No'},
                                         {'header': 'Machine Name'},
                                         {'header': 'Date Time'},
                                         {'header': 'Parameter'},
                                         {'header': 'Axis'},
                                         {'header': 'Value'},
                                         {'header': 'Warning Limit'},
                                         {'header': 'Critical Limit'}]})
    elif parameter_type == "part_count":
        worksheet.add_table(f'{start_cell_static}:{end_cell_part}',
                            {'data': data,
                             'columns': [{'header': 'S.No'},
                                         {'header': 'Machine Name'},
                                         {'header': 'Date Time'},
                                         {'header': 'Spare Part Name'},
                                         {'header': 'Machine State'},
                                         {'header': 'Current Count'},
                                         {'header': 'Warning Limit'},
                                         {'header': 'Critical Limit'}]})
    else:
        data = [d[:5] for d in data]
        worksheet.add_table(f'{start_cell_static}:{end_cell_dynamic}',
                            {'data': data,
                             'columns': [{'header': 'S.No'},
                                         {'header': 'Machine Name'},
                                         {'header': 'Date Time'},
                                         {'header': 'Parameter'},
                                         {'header': 'Axis'}]})

    workbook.close()


def main():
    """
    Main Function
    ====================

    Main function to call appropriate functions to

    """

    send_mail()


if __name__ == '__main__':
    main()
