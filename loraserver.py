'''
Created on Feb 22, 2020

@author: daniel
'''
import ssl
import json
import sys
import base64
import paho.mqtt.client as mqtt

def data_port_from_payload(payload):
    ''' Extract payload data as bytearray and port from payload '''
    data_arr = []
    port = 0
    try:
        payload_obj = json.loads(payload)
        data_arr = bytearray(base64.b64decode(payload_obj["data"]))
        port = payload_obj["fPort"]
    except TypeError as exception:
        sys.stderr.write("Failed to extract payload! " + repr(exception) + "\n")
        return (data_arr, port)
    ret_val = (data_arr, port)
    return ret_val

class LoraServerHandler(mqtt.Client):
    '''
    classdocs
    '''

    def __init__(self, mqtt_host, mqtt_port, mqtt_tls_mode,
                 mqtt_user, mqtt_pass,
                 rht_lora_app, lr210_lora_app):
        '''
        Constructor
        '''
        # Call the base class constructor
        mqtt.Client.__init__(self)

        # Do our own constructor stuff
        self._host = mqtt_host
        self._port = mqtt_port
        self._tls_support = mqtt_tls_mode
        self._user = mqtt_user
        self._pass = mqtt_pass
        self._rht_lora = rht_lora_app
        self._lr210_lora = lr210_lora_app
        self._mqtt_connected = False
        self._rht_uplink_handler = None
        self._lr210_uplink_handler = None

    def on_log(self, _client, _userdata, _level, buf):
        print("log: ", buf)

    def set_rht_sensor_ul_cb(self, callback):
        ''' Set callback to handle RHT sensor UL data '''
        self._rht_uplink_handler = callback

    def lr210_dl_handler(self, data):
        ''' Send downlink to LR210 from a tuple of bytearray and port '''
        if self._mqtt_connected:
            lr210pub = self._lr210_lora[0] + "/node/" + self._lr210_lora[1] + "/tx"
            b64_data = base64.b64encode(data[0])
            b64_str = b64_data.decode('utf-8')
            tx_object = {"confirmed": True, "fPort": data[1], "data":b64_str}
            self.publish(lr210pub, json.dumps(tx_object))
        else:
            sys.stderr.write("Not connected! Omitting send\n")

    def set_lr210_ul_cb(self, callback):
        ''' Set callback to handle RL210 UL data '''
        self._lr210_uplink_handler = callback

    def on_lr210_data(self, _mosq, _obj, msg):
        ''' Act on MQTT data matching LR210 RX topic '''

        # This callback will only be called for LR210 RX data
        print("LR210: " + msg.topic + " " + str(msg.qos) + " " + str(msg.payload))
        ul_data = data_port_from_payload(msg.payload)
        if self._lr210_uplink_handler:
            self._lr210_uplink_handler(ul_data)
        else:
            sys.stderr.write("No UL data handler for LR210 data?\n")

    def on_rht_sensor_data(self, _mosq, _obj, msg):
        ''' Act on MQTT data matching RHT RX topic '''

        # This callback will only be called for RHT sensor data
        print("RHT: " + msg.topic + " " + str(msg.qos) + " " + str(msg.payload))
        ul_data = data_port_from_payload(msg.payload)
        if self._rht_uplink_handler:
            self._rht_uplink_handler(ul_data)
        else:
            sys.stderr.write("No UL data handler for RHT data?\n")

    def on_message(self, _mosq, _obj, msg):
        # This callback will be called for messages that we receive that do not
        # match any patterns defined in topic specific callbacks
        print(msg.topic + " " + str(msg.qos) + " " + str(msg.payload))

    def connect_subscribe(self):
        ''' Perform the connect and subscribe procedure towards the broker '''
        if not self._mqtt_connected:
            if any([self._user, self._pass]):
                self.username_pw_set(self._user, self._pass)

            if self._tls_support:
                self.tls_set(tls_version=ssl.PROTOCOL_TLSv1_2)

            lr210sub = self._lr210_lora[0] + "/node/" + self._lr210_lora[1] + "/rx"
            rhtsub = self._rht_lora[0] + "/node/" + self._rht_lora[1] + "/rx"

            self.message_callback_add(lr210sub, self.on_lr210_data)
            self.message_callback_add(rhtsub, self.on_rht_sensor_data)

            self.connect(self._host, self._port, 60)
            self.subscribe([(lr210sub, 2), (rhtsub, 2)], 0)
            self._mqtt_connected = True

    def run_loop(self):
        self.connect_subscribe()
        return mqtt.MQTT_ERR_SUCCESS == self.loop()
