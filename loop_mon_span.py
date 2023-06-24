import configparser
from datetime import datetime, timedelta
import os 


# Read the config file
config = configparser.ConfigParser()
config.read('conf/config.BCMM.ini')

# Get the start and end timestamps from the config file
start_ts_str = config['OUTPUT']['etl_strt_ts']
end_ts_str = config['OUTPUT']['etl_end_ts']

# Convert the timestamps to datetime objects
start_ts = datetime.strptime(start_ts_str, '%Y%m%d%H%M')
end_ts = datetime.strptime(end_ts_str, '%Y%m%d%H%M')

# Loop over the months from January to December
for month in range(1,13):
    # Calculate the start and end timestamps for the current month
    month_start = datetime(start_ts.year, month, 1)
    if month<12:
        month_end = datetime(start_ts.year, month+1, 1) - timedelta(hours=6)
    else:
        month_end = datetime(start_ts.year+1, 1, 1) - timedelta(hours=6)
    # Reassign the start and end timestamps for the current month
    config['OUTPUT']['etl_strt_ts'] = month_start.strftime('%Y%m%d%H%M')
    config['OUTPUT']['etl_end_ts'] = month_end.strftime('%Y%m%d%H%M')
    with open(f'conf/config.BCMM.ini', 'w') as config_file:
        config.write(config_file)

    # Call another Python script using subprocess
    os.system('python3 run_c2w.py -m BCMM')
