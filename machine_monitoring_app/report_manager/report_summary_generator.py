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
from datetime import datetime, timedelta
import math
import pytz
import math
# Related third party imports
from pony.orm import db_session, select, avg as pony_avg
import xlsxwriter

# Local application/library specific imports
from machine_monitoring_app.database.crud_operations import get_parameters
from machine_monitoring_app.database.pony_models import RealTimeParameter
from machine_monitoring_app.utils.global_variables import get_axis_translation

__author__ = "smt18m005@iiitdm.ac.in"

LOGGER = logging.getLogger(__name__)


@db_session
def generate_summary(start_time: datetime = datetime(2022, 9, 7, 6, 20, 0),
                     end_time: datetime = datetime(2022, 9, 7, 6, 30, 0),
                     given_line: str = "T_B"):
    """
    Function used to generate summary information of anomalies in the machines for the last 4 hours

    :return:
    :rtype:
    """
    production_line_translations = {"block": "T_B", "crank": "T_C", "head": "T_H"}
    line = production_line_translations[given_line]

    axis_data = get_axis_translation()
    static_data_cumulative = []
    dynamic_data_cumulative = []

    # Get the real time parameter, equal to the current axis
    current_value_base_query_count = RealTimeParameter.select(lambda parameter: parameter.machine_parameter.
                                                              machine.name.startswith(line))

    # current_value_base_query_original = select((p.machine_parameter, pony_avg(p.value),
    #                                             pony_avg(p.value)) for p in
    #                                            RealTimeParameter)[:]
    #
    current_value_base_query_aggregate_warning = select((p.machine_parameter, pony_avg(p.value * p.value))
                                                        for p in RealTimeParameter
                                                        if p.time <= end_time and p.time >= start_time and
                                                        p.parameter_condition.id == 2 and
                                                        p.machine_parameter.machine.name.startswith(line))

    current_value_base_query_aggregate_critical = select((p.machine_parameter, pony_avg(p.value * p.value))
                                                         for p in RealTimeParameter
                                                         if p.time <= end_time and p.time >= start_time and
                                                         p.parameter_condition.id == 3 and
                                                         p.machine_parameter.machine.name.startswith(line))

    # for value in current_value_base_query_aggregate_warning:
    #     print(value[0], round(math.sqrt(value[1]), 4))

    current_value = current_value_base_query_count. \
        filter(lambda parameter: parameter.time > start_time)

    current_value_base = current_value. \
        filter(lambda parameter: parameter.time <= end_time)

    current_value_ng_data = current_value_base.filter(lambda parameter: parameter.parameter_condition.id > 1)

    current_value_warning_count = current_value_base. \
        filter(lambda parameter: parameter.parameter_condition.id == 2).count()

    current_value_critical_count = current_value_base. \
        filter(lambda parameter: parameter.parameter_condition.id == 3).count()

    current_value_dynamic = current_value_ng_data. \
        filter(lambda parameter: parameter.machine_parameter.parameter_group.id == 17)
    #
    # current_value_static = current_value_base_query_aggregate. \
    #     filter(lambda parameter: parameter.machine_parameter.parameter_group.id != 17)
    #
    # current_value_static = current_value_static.order_by(RealTimeParameter.time)

    current_value_dynamic = current_value_dynamic.order_by(RealTimeParameter.time)

    LOGGER.debug("\n==========================\n")
    LOGGER.debug("Warning Count: ", current_value_warning_count)
    LOGGER.debug("Critical Count: ", current_value_critical_count)
    LOGGER.debug("\n==========================\n")

    current_value_base_query_aggregate_warning = current_value_base_query_aggregate_warning[:]

    for index, value in enumerate(current_value_base_query_aggregate_warning):

        LOGGER.debug("\n=====================================\n")

        machine_parameter_name = value[0].name
        LOGGER.debug(f"Parameter Name: {machine_parameter_name}")

        machine_name = value[0].machine.name

        LOGGER.debug(f"Machine Name: {machine_name}")

        parameter_group_index = value[0].parameter_group.id
        parameter_group_name = value[0].parameter_group.group_name

        LOGGER.debug(f"Parameter Group Index: {parameter_group_index}")

        # LOGGER.debug("Time in Ist: ", value.time + timedelta(hours=5, minutes=30))
        #
        # time_ist = value.time + timedelta(hours=5, minutes=30)

        current_parameter_value = round(math.sqrt(value[1]), 2)
        LOGGER.debug(f"Parameter Current Value: {current_parameter_value}")

        condition_name = "Warning"
        LOGGER.debug(condition_name)

        warning_limit = value[0].warning_limit
        critical_limit = value[0].critical_limit
        LOGGER.debug(warning_limit)
        LOGGER.debug(critical_limit)

        machine_parameters = get_parameters(machine=machine_name,
                                            parameter_group_id=parameter_group_index)

        axis_index = machine_parameters.index(value[0].id)
        axis_name = axis_data.loc[axis_data['machine name'] == value[0].machine.name]
        axis_name = axis_name["a" + str(axis_index)].values[0]

        if isinstance(axis_name, float) and math.isnan(axis_name):
            axis_name = "SP"

        LOGGER.debug(f"Axis Name: {axis_name}")

        current_data = [index + 1, machine_name,
                        parameter_group_name,
                        axis_name, condition_name,
                        current_parameter_value, warning_limit,
                        critical_limit]

        static_data_cumulative.append(current_data)

    for index, value in enumerate(current_value_base_query_aggregate_critical):

        LOGGER.debug("\n=====================================\n")

        machine_parameter_name = value[0].name
        LOGGER.debug(f"Parameter Name: {machine_parameter_name}")

        machine_name = value[0].machine.name

        LOGGER.debug(f"Machine Name: {machine_name}")

        parameter_group_index = value[0].parameter_group.id
        parameter_group_name = value[0].parameter_group.group_name

        LOGGER.debug(f"Parameter Group Index: {parameter_group_index}")

        # LOGGER.debug("Time in Ist: ", value.time + timedelta(hours=5, minutes=30))
        #
        # time_ist = value.time + timedelta(hours=5, minutes=30)

        current_parameter_value = round(math.sqrt(value[1]), 2)

        LOGGER.debug(f"Parameter Current Value: {current_parameter_value}")

        condition_name = "Critical"
        LOGGER.debug(condition_name)

        warning_limit = value[0].warning_limit
        critical_limit = value[0].critical_limit
        LOGGER.debug(warning_limit)
        LOGGER.debug(critical_limit)

        machine_parameters = get_parameters(machine=machine_name,
                                            parameter_group_id=parameter_group_index)

        axis_index = machine_parameters.index(value[0].id)
        axis_name = axis_data.loc[axis_data['machine name'] == value[0].machine.name]
        axis_name = axis_name["a" + str(axis_index)].values[0]

        if isinstance(axis_name, float) and math.isnan(axis_name):
            axis_name = "SP"

        LOGGER.debug(f"Axis Name: {axis_name}")

        current_data = [index + 1 + len(current_value_base_query_aggregate_warning), machine_name,
                        parameter_group_name,
                        axis_name, condition_name,
                        current_parameter_value, warning_limit,
                        critical_limit]
        static_data_cumulative.append(current_data)

    LOGGER.debug("Dynamic Parameter")

    for index, value in enumerate(current_value_dynamic):
        LOGGER.debug("\n=====================================\n")

        machine_parameter_name = value.machine_parameter.name
        LOGGER.debug(f"Parameter Name: {machine_parameter_name}")

        machine_name = value.machine_parameter.machine.name

        LOGGER.debug(f"Machine Name: {machine_name}")

        parameter_group_index = value.machine_parameter.parameter_group.id
        parameter_group_name = value.machine_parameter.parameter_group.group_name

        LOGGER.debug(f"Parameter Group Index: {parameter_group_index}")

        LOGGER.debug("Time in Ist: ", value.time + timedelta(hours=5, minutes=30))

        time_ist = value.time + timedelta(hours=5, minutes=30)

        current_parameter_value = value.value
        LOGGER.debug(f"Parameter Current Value: {current_parameter_value}")

        condition_name = value.parameter_condition.name
        LOGGER.debug(condition_name)

        machine_parameters = get_parameters(machine=machine_name,
                                            parameter_group_id=parameter_group_index)

        axis_index = machine_parameters.index(value.machine_parameter.id)
        axis_name = axis_data.loc[axis_data['machine name'] == value.machine_parameter.machine.name]
        axis_name = axis_name["a" + str(axis_index)]
        LOGGER.debug(axis_name)

        current_data = [index + 1, str(time_ist), machine_name,
                        parameter_group_name,
                        axis_name, condition_name]

        dynamic_data_cumulative.append(current_data)

    return dynamic_data_cumulative, static_data_cumulative, \
           current_value_warning_count, current_value_critical_count


def create_excel_report(file_location: str):
    """
    Function to create a full report

    :return:
    :rtype:
    """
    workbook = xlsxwriter.Workbook(file_location)
    # end_time = datetime.now(pytz.utc)
    end_time = datetime(2022, 9, 7, 6, 30, 0)
    # start_time = end_time - timedelta(hours=4)
    start_time = datetime(2022, 9, 7, 6, 20, 0)

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

    for line in ["block", "crank", "head"]:

        worksheet = workbook.add_worksheet(line)

        worksheet.set_column(0, 0, 15, cell_format)
        worksheet.set_column(1, 2, 25, cell_format)
        worksheet.set_column(3, 3, 45, cell_format)
        worksheet.set_column(4, 4, 15, cell_format)
        worksheet.set_column(5, 5, 20, cell_format)
        worksheet.set_column(6, 8, 15, cell_format)

        # worksheet.set_column('B:D', 30)
        # worksheet.set_row(3, 30)
        # worksheet.set_row(6, 30)
        # worksheet.set_row(7, 30)

        # Merge cells
        worksheet.merge_range('A1:J1', 'Merged Range', merge_format)
        #
        # # Merge 3 cells over two rows.
        # worksheet.merge_range('B7:D8', 'Merged Range', merge_format)

        worksheet.write('A1', 'TNGA Machining Abnormality report')
        worksheet.write('E3', 'Start Time')
        worksheet.write('F3', str(start_time))
        worksheet.write('E4', 'End Time')
        worksheet.write('F4', str(end_time))

        dynamic_data, static_data, warn_count, critical_count = generate_summary(given_line=line,
                                                                                 start_time=start_time,
                                                                                 end_time=end_time)

        start_cell_static = "B8"
        end_cell_static = "I" + str(8 + len(static_data))

        if not static_data and not dynamic_data:
            continue

        worksheet.add_table(f'B3:C4', {'data': [[warn_count, critical_count]],
                                       'columns': [{'header': 'Warning Count'},
                                                   {'header': 'Critical Count'}]})

        worksheet.merge_range('A6:D6', 'Merged Range', merge_format)
        worksheet.write('A6', 'Static Parameters')

        if static_data:
            worksheet.add_table(f'{start_cell_static}:{end_cell_static}',
                                {'data': static_data,
                                 'columns': [{'header': 'S.No'},
                                             {'header': 'Machine Name'},
                                             {'header': 'Parameter'},
                                             {'header': 'Axis'},
                                             {'header': 'Status'},
                                             {'header': 'RMS Value'},
                                             {'header': 'Warning Limit'},
                                             {'header': 'Critical Limit'}]})

        worksheet.merge_range(f'A{8 + len(static_data) + 4}:D{8 + len(static_data) + 4}',
                              'Merged Range', merge_format)

        worksheet.write(f'A{8 + len(static_data) + 4}', 'Dynamic Parameters')
        if dynamic_data:
            worksheet.add_table(f'B{8 + len(static_data) + 5}:G{8 + len(static_data) + 6 + len(dynamic_data)}',
                                {'data': dynamic_data,
                                 'columns': [{'header': 'S.No'},
                                             {'header': 'Machine Name'},
                                             {'header': 'Parameter'},
                                             {'header': 'Axis'},
                                             {'header': 'Status'}]})

    workbook.close()


def main():
    """
    Main Function
    ====================
    
    Main function to call appropriate functions to 

    """

    # dynamic_data, static_data = generate_summary()
    #
    # print(dynamic_data)
    # print(static_data)

    file_path = "./output/email_reports/full_4_hour_summary_report.xlsx"
    create_excel_report(file_path)


if __name__ == '__main__':
    main()
