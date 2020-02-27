# lr210-heaterctrl
Python application implementing a humidity controller using LoRaWAN technology.
Humidity is controlled using two LoRa devices;

1. [DNIL Electronics LR210 LoRa relay controller](http://www.dnil.se/products/lr210-relay-controller)
2. [Talkpool OY1110](https://talkpool.io/temperature-and-humidity-sensor/)

The LR210 relay controller is controlling power to a standard electric heather,
heater is switched on or off based on the humidity reported by the OY1110 sensor.

LoRaWAN network is implemented using [LoRa Server](https://www.chirpstack.io/) (now known as ChirpStack)

Developed on Ubuntu 18.04 using default python3 interpreter, also tested on
python2 in the same environment. Needs Paho MQTT library:

`sudo apt install python3-paho-mqtt`