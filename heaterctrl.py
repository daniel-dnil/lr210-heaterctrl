#!/usr/bin/env python
# encoding: utf-8
'''
heaterCtrl -- Control heater based on RH input data

heaterCtrl is a a control application using LoRaWAN LR210 controller and OY110 RHT sensor

@author:     Daniel Nilsson

@copyright:  2020 DNIL Electronics AB. All rights reserved.

@license:    Apache License 2.0

@contact:    daniel@dnil.se
@deffield    updated: Updated
'''

import sys
import os
import traceback
import controller

def main():
    '''Main controller application'''

    program_name = os.path.basename(sys.argv[0])
    try:
        # Setup the main controller class
        climate_ctrl = controller.ClimateController()
        climate_ctrl.mqtt_server_params("lorans.home.dnil.se", 1883)
        climate_ctrl.lr210_relay_ctrl("application/20", "70b3d5d72ffc8000", 1)
        climate_ctrl.rht_sensor_data("application/6", "70b3d5d7201c0029")

        # Run program
        climate_ctrl.run()

    except Exception as exception:
        sys.stderr.write(program_name + ": " + repr(exception) + "\n")
        traceback.print_exc()
        return -1

    return 0

if __name__ == "__main__":
    sys.exit(main())
