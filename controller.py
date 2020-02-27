'''
Created on Feb 21, 2020

@author: daniel
'''

import logging
import loraserver
import oy1110
import lr210

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

class RHTThermostat(object):
    '''
    Implements a thermostat based on both RH and temp data
    '''

    def __init__(self, min_temp=-5.0, max_rh=80.0):
        '''
        Constructor
        '''
        self._min_temp = min_temp
        self._temp_hyst = 3.0
        self._max_rh = max_rh
        self._rh_hyst = 5.0
        self._actuals_valid = False
        self._output_state = False

    def set_rh_hysteresis(self, rh_hyst):
        '''
        Override default RH hysteresis, value in percent
        '''
        self._rh_hyst = rh_hyst

    def set_temp_hysteresis(self, temp_hyst):
        '''
        Override default temperature hysteresis, value in percent
        '''
        self._temp_hyst = temp_hyst

    def update_actual_values(self, humidity, temperature):
        '''
        Update actual values and performs output calculation
        '''
        self._actuals_valid = all([humidity, temperature])

        temp_ok = True
        hum_ok = True

        if self._actuals_valid and self._output_state:
            # We are heating, check criteria
            temp_ok = temperature > self._min_temp + (self._temp_hyst / 2)
            hum_ok = humidity < self._max_rh - (self._rh_hyst / 2)

        elif self._actuals_valid and not self._output_state:
            # We are not heating
            temp_ok = temperature > self._min_temp - (self._temp_hyst / 2)
            hum_ok = humidity < self._max_rh + (self._rh_hyst / 2)

        new_output_state = (not temp_ok) or (not hum_ok)

        if new_output_state != self._output_state:
            print("Heather change from " + str(self._output_state) +
                  " to " + str(new_output_state) +
                  " temperature OK: " + str(temp_ok) +
                  " humidity OK: " + str(hum_ok))
            self._output_state = new_output_state

    def output_active(self):
        '''
        Returns True is the thermostat output shall be send to the relay
        controller, ie when we have enough data to control the relay
        '''
        return self._actuals_valid

    def output(self):
        ''' Retrieve output, reflects desired output state (True/False) '''
        return self._output_state


class ClimateController(object):
    '''
    Main climatecontroller class, runs main loop and interfaces with sensors
    and loraserver
    '''

    def __init__(self):
        '''
        Constructor
        '''
        self._mqtt_host = "localhost"
        self._mqtt_port = 1883
        self._mqtt_user = ""
        self._mqtt_pass = ""
        self._rht_lora_app_loc = None
        self._lr210_app_app_loc = None
        self._lr210_relay_ch = None
        self._mqtt_tls = False
        self._lr210_ctrl = None

    def mqtt_server_params(self, mqtt_host="", mqtt_port=None,
                           mqtt_username="", mqtt_password="",
                           mqtt_tls_mode=False):
        '''
        Setup parameters for connecting to MQTT broker
        '''
        if mqtt_host:
            self._mqtt_host = mqtt_host
        if mqtt_port is not None:
            self._mqtt_port = mqtt_port
        if mqtt_username:
            self._mqtt_user = mqtt_username
        if mqtt_password:
            self._mqtt_pass = mqtt_password
        if mqtt_tls_mode:
            self._mqtt_tls = True

    def rht_sensor_data(self, application, dev_eui):
        '''
        Setup loraserver parameters where to find RHT sensor data
        '''
        self._rht_lora_app_loc = (application, dev_eui)

    def lr210_relay_ctrl(self, application, dev_eui, relay_channel):
        '''
        Setup loraserver parameters where to steer LR210 Relay
        '''
        self._lr210_app_app_loc = (application, dev_eui)
        self._lr210_relay_ch = relay_channel

    def mqtt_connect_handler(self):
        '''
        Installed as callback when we have connected to LoRa Server MQTT OK
        '''
        # Perform a one-time query of the current relay states
        if self._lr210_ctrl:
            self._lr210_ctrl.request_relay_states()

    def run(self):
        '''
        Run the main controller, will not return until severe errors occurs
        '''

        if any([not self._rht_lora_app_loc, not self._rht_lora_app_loc,
                not self._lr210_relay_ch]):
            raise RuntimeError("Missing loraserver parameters")

        lora_if = loraserver.LoraServerHandler(self._mqtt_host, self._mqtt_port,
                                               self._mqtt_tls,
                                               self._mqtt_user, self._mqtt_pass,
                                               self._rht_lora_app_loc,
                                               self._lr210_app_app_loc)

        # Set our connect handler
        lora_if.set_connect_handler(self.mqtt_connect_handler)

        # Create our RH and tempsensor object
        rht_sensor = oy1110.RHTSensor()
        # Connect the UL data handler (DL to OY1110 not used)
        lora_if.set_rht_sensor_ul_cb(rht_sensor.uplink_data_handler)

        # Create the LR210 relay controller object
        self._lr210_ctrl = lr210.LR210()

        # Connect the UL and DL data handlers
        lora_if.set_lr210_ul_cb(self._lr210_ctrl.uplink_data_handler)
        self._lr210_ctrl.set_dl_handler(lora_if.lr210_dl_handler)

        # Create out thermostat
        thermo = RHTThermostat(-15.0, 75.0)

        lora_if_result = True
        while lora_if_result:
            lora_if_result = lora_if.run_loop()

            # Feed the thermostat new values
            thermo.update_actual_values(rht_sensor.humidity(),
                                        rht_sensor.temperature())

            # Send the termostat output to the relay controller
            if thermo.output_active():
                self._lr210_ctrl.set_channel_state([(self._lr210_relay_ch,
                                                     thermo.output())])

            # Poll the relay controller if retries are needed
            self._lr210_ctrl.periodic_poll()

            # Check LR210 internal temperature
            if self._lr210_ctrl.temperature() and self._lr210_ctrl.temperature() > 55.0:
                LOGGER.warning("LR210 internal temp high!")
