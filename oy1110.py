'''
Created on Feb 23, 2020

@author: daniel
'''

from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

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
                LOGGER.info("Temperature: %f Humidity: %f", self._temp, self._humi)
            else:
                LOGGER.error("Only ungrouped data of length 3 supported")
        elif port == 1:
            # Protocol data deconding not implemented yet
            pass
        else:
            LOGGER.error("Unknown port in UL data: %d", port)

    def _check_max_data_age(self):
        time_now = datetime.now()
        if self._temp_humi_ts and (self._temp_humi_ts + self._temp_humi_max_age) < time_now:
            self._temp = None
            self._humi = None
            LOGGER.warning("Invalidating temp/humi data due to age")

    def temperature(self):
        ''' Return current temperature (if known) else None '''
        self._check_max_data_age()
        return self._temp

    def humidity(self):
        ''' Return current humidity (if known) else None '''
        self._check_max_data_age()
        return self._humi
