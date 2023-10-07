import time
from datetime import datetime

DIFFICULTY = 1
BOUNDARY = (0, 99999999)

def convert_time(timestamp=None):
    if timestamp is None:
        return time.time()
    
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime('%Y-%m-%d %H:%M:%S')

CONNECTED_NODE_ADDRESS = {'http://127.0.0.1:5000'}