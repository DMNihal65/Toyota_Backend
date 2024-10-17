# import pandas as pd
#
# # Load the CSV files
# machine_params_df = pd.read_csv('D:\\DM-CMTI\\Misc\\BackupDatabase31052024\\tiei\\machine_parameters1.csv')
# real_time_params_df = pd.read_csv('D:\\DM-CMTI\\Misc\\BackupDatabase31052024\\tiei\\real_time_machine_parameters_active'
#                                   '.csv')
#
# # Check if machine_parameters_id in real_time_machine_parameters_active.csv exists in id of machine_parameters1.csv
# valid_ids = set(machine_params_df['id'])
# filtered_real_time_params_df = real_time_params_df[real_time_params_df['machine_parameters_id'].isin(valid_ids)]
#
# # Save the updated CSV
# filtered_real_time_params_df.to_csv(
#     'D:\\DM-CMTI\\Misc\\BackupDatabase31052024\\tiei\\real_time_machine_parameters_active_filtered.csv', index=False)
#
# print("Filtered CSV file has been saved as 'real_time_machine_parameters_active_filtered.csv'.")

#
# import pandas as pd
#
# # Load the CSV file
# real_time_params_df = pd.read_csv('D:\\DM-CMTI\\Misc\\BackupDatabase31052024\\tiei\\real_time_machine_parameters_active_filtered.csv')
#
# # Define a function to convert values to integers
# def convert_to_int(value):
#     try:
#         return int(value)
#     except ValueError:
#         return 0  # Default value if conversion fails
#
# # Apply the conversion function to the 'condition_id' column
# real_time_params_df['condition_id'] = real_time_params_df['condition_id'].apply(convert_to_int)
#
# # Save the updated CSV
# output_path = 'D:\\DM-CMTI\\Misc\\BackupDatabase31052024\\tiei\\real_time_machine_parameters_active_condition_id_updated.csv'
# real_time_params_df.to_csv(output_path, index=False)
#
# print(f"Updated CSV file has been saved as '{output_path}'.")

#
# import pandas as pd
#
# # Load the CSV file
# real_time_params_df = pd.read_csv('D:\\DM-CMTI\\Misc\\BackupDatabase31052024\\tiei\\real_time_machine_parameters_active_filtered.csv')
#
# # Define a function to convert values to integers, remove decimals and negative numbers
# def clean_condition_id(value):
#     try:
#         # Convert to float first to handle any decimal numbers, then to int
#         int_value = int(float(value))
#         if int_value < 0:
#             return None  # Mark negative numbers for removal
#         return int_value
#     except ValueError:
#         return 0  # Default value if conversion fails
#
# # Apply the cleaning function to the 'condition_id' column
# real_time_params_df['condition_id'] = real_time_params_df['condition_id'].apply(clean_condition_id)
#
# # Remove rows with None values in 'condition_id' (which were negative numbers)
# real_time_params_df = real_time_params_df.dropna(subset=['condition_id'])
#
# # Convert the 'condition_id' column to integers
# real_time_params_df['condition_id'] = real_time_params_df['condition_id'].astype(int)
#
# # Save the updated CSV
# output_path_cleaned = 'D:\\DM-CMTI\\Misc\\BackupDatabase31052024\\tiei\\real_time_machine_parameters_active_condition_id_updated.csv'
# real_time_params_df.to_csv(output_path_cleaned, index=False)
#
# print(f"Cleaned CSV file has been saved as '{output_path_cleaned}'.")


import pandas as pd

# Load the CSV file
real_time_params_df = pd.read_csv('D:\\DM-CMTI\\Misc\\BackupDatabase31052024\\tiei\\real_time_machine_parameters_active_filtered.csv')

# Define a function to convert values to integers, remove decimals and negative numbers
def clean_condition_id(value):
    try:
        # Convert to float first to handle any decimal numbers, then to int
        int_value = int(float(value))
        if int_value < 0:
            return None  # Mark negative numbers for removal
        return int_value
    except ValueError:
        return 0  # Default value if conversion fails

# Apply the cleaning function to the 'condition_id' column
real_time_params_df['condition_id'] = real_time_params_df['condition_id'].apply(clean_condition_id)

# Remove rows with None values in 'condition_id' (which were negative numbers)
real_time_params_df = real_time_params_df.dropna(subset=['condition_id'])

# Convert the 'condition_id' column to integers
real_time_params_df['condition_id'] = real_time_params_df['condition_id'].astype(int)

# Save the updated CSV
output_path_cleaned = 'D:\\DM-CMTI\\Misc\\BackupDatabase31052024\\tiei\\real_time_machine_parameters_active_condition_id_updated.csv'
real_time_params_df.to_csv(output_path_cleaned, index=False)

print(f"Cleaned CSV file has been saved as '{output_path_cleaned}'.")
