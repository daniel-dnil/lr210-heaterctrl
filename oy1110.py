'''
Created on Feb 23, 2020

@author: daniel
'''

import sys
from datetime import datetime, timedelta

class RHTSensor(object):
    '''
    Payload decoder for Talkpool OY1110 Temp and Humidity LoRa sensor
    '''

    def __init__(self):
        '''
        Constructor
        '''
        self._temp = None
        self._humi = None
        self._temp_humi_ts = None
        self._temp_humi_max_age = timedelta(minutes=65)

    def uplink_data_handler(self, data):
        '''
        Handle uplink data in the form of a tuple containing a
        bytearray with raw payload data and a port number
        '''
        # Periodic data is sent on port 2,
        # Protocol response data is sent on port 1
        data_arr = data[0]
        port = data[1]
        if port == 2:
            # Peridic data
            if len(data_arr) == 3:
                self._temp = int(data_arr[0]) << 4 | (int(data_arr[2]) >> 4)
                self._temp = (self._temp - 800) / 10.0
                self._humi = int(data_arr[1]) << 4 | (int(data_arr[2]) & 0xF)
                self._humi = (self._humi - 250) / 10.0
                self._temp_humi_ts = datetime.now()
                print("Temp: " + str(self._temp) + " Humi: " + str(self._humi))
            else:
                sys.stderr.write("Only ungrouped data of length 3 supported\n")
        elif port == 1:
            # Protocol data deconding not implemented yet
            pass
        else:
            sys.stderr.write("Unknown port in UL data: " + str(port) + "\n")

    def _check_max_data_age(self):
        time_now = datetime.now()
        if self._temp_humi_ts and (self._temp_humi_ts + self._temp_humi_max_age) < time_now:
            self._temp = None
            self._humi = None
            sys.stderr.write("Invalidating temp/humi data due to age\n")

    def temperature(self):
        self._check_max_data_age()
        return self._temp

    def humidity(self):
        self._check_max_data_age()
        return self._humi
