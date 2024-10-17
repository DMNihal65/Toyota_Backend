"""
ORM Update Operation Module
============================

The `update_operation` module within the `orm` subpackage provides functions to update records in the database
using Object-Relational Mapping (ORM) tools. It includes functionalities to modify existing records in the
database tables represented by ORM entities.

Functions
---------
- `update_user_record`: Function to update a user record in the database.
- `update_product_record`: Function to update a product record in the database.
- `update_order_record`: Function to update an order record in the database.
- ... (add more functions as needed)

"""

# Standard library imports
import logging

# Related third-party imports
from pony.orm import db_session, commit, select

from machine_monitoring_app.database.pony_models import CorrectiveActivity, ParameterCondition

LOGGER = logging.getLogger(__name__)


@db_session(optimistic=False)
def update_corrective_activities_from_dataframe(df):
    """Updates CorrectiveActivity instances based on a pandas DataFrame.

    Args:
        df: A pandas DataFrame with columns "updatedate", "value", "machine_parameters_id", and "condition_id".

    Returns:
        None
    """

    for index, row in df.iterrows():
        machine_parameters_id = row["signalname"]
        condition_id = row["condition"]
        updatedate = row["updatedate"]
        value = row["value"]

        corrective_activity = select(
            ca for ca in CorrectiveActivity
            if ca.machine_parameter.id == machine_parameters_id and ca.parameter_condition.id == condition_id
        ).first()

        if corrective_activity:
            corrective_activity.latest_occurrence = updatedate
            corrective_activity.recent_value = value
            corrective_activity.number_of_occurrences = corrective_activity.number_of_occurrences + 1

    commit()

@db_session()
def insert_corrective_activities_from_dataframe(df):
    """Updates CorrectiveActivity instances based on a pandas DataFrame.

    Args:
        df: A pandas DataFrame with columns "updatedate", "value", "machine_parameters_id", and "condition_id".

    Returns:
        None
    """

    for index, row in df.iterrows():
        signal_name = row['signalname']
        date_of_identification = row['updatedate']
        latest_occurrence = row['updatedate']
        recent_value = row['value']
        condition = ParameterCondition.get(id=row['condition'])

        CorrectiveActivity(
            machine_parameter=signal_name,
            date_of_identification=date_of_identification,
            latest_occurrence=latest_occurrence,
            number_of_occurrences=1,
            recent_value=recent_value,
            parameter_condition=condition
        )

    commit()
