'''
Created on Feb 23, 2020

@author: daniel
'''

import sys
from datetime import datetime, timedelta

class DownlinkSetCommand(object):
    ''' Object representing a LoRa Downlink Relay Set Command '''

    def __init__(self, relay_set_data):
        '''
        Constructor intended to be called when the command is first sent
        '''
        self._is_pending = False
        self._rly_set_data = relay_set_data
        self._retry_count = 0
        self._last_send_timestamp = datetime.now()
        self._retry_period = timedelta(minutes=5)
        self._retry_max = 5

    def increase_retry(self):
        '''
        Call method each send attempt to increase retry count and set
        new send timestamp
        '''
        self._retry_count += 1
        self._last_send_timestamp = datetime.now()
        print("DL relay set command retry count: " + str(self._retry_count))

    def retry_ok(self):
        '''
        Returns True if this command has retries left
        '''
        can_retry = self._retry_max > self._retry_count
        if not can_retry:
            sys.stderr.write("LR210 out of retries on set command!\n")
        return can_retry

    def cmd(self):
        '''
        Returns the relay set command data (integer) of this command
        '''
        return self._rly_set_data

    def cmd_is_equal(self, relay_set_data):
        '''
        Returns True if relay_set_data (integer) is equal to the already sent
        command in this object
        '''
        return self._rly_set_data == relay_set_data

    def resend_due(self):
        '''
        Returns True is a resend is due
        '''
        return self._last_send_timestamp + self._retry_period < datetime.now()

class RelayChannel(object):
    '''
    Object representing one relay channel
    '''

    def __init__(self, channel):
        '''
        Constructor
        '''
        self._ch = channel
        self._ch_str = "Channel " + str(channel)
        self._act_state = None
        self._req_state = None
        self._act = "active"
        self._deact = "deactive"

    def reset_state(self):
        '''
        Reset the state of this channel to unknown
        '''
        self._act_state = None
        self._req_state = None

    def actual_state_str(self):
        '''
        Return string representing actual state of relay channel
        '''
        state = "Channel " + str(self._ch) + " state is "
        if self._act_state:
            state += self._act_state
        else:
            state += "unknown"
        return state

    def set_actual(self, actual):
        '''
        Set the actual relay state to either True (active) or False (deactive)
        '''
        if actual:
            self._act_state = self._act
        else:
            self._act_state = self._deact

    def set_requested(self, requested):
        '''
        Set the requested relay state to either True (active) or False (deactive)
        '''
        if requested:
            self._req_state = self._act
        else:
            self._req_state = self._deact

    def dl_command(self):
        '''
        Returns a tuple containing True/False if change is needed followed
        by 0 or 1 for the new channel state. Used to create the DL set command
        '''
        need_change = False
        new_state = 0

        # We only send new DL requests if we know the current states and
        # change of states is requested
        if all([self._act_state, self._req_state]) and \
        self._req_state != self._act_state:
            need_change = True
            if self._act == self._req_state:
                new_state = 1
            else:
                new_state = 0

        return (need_change, new_state)

class LR210(object):
    '''
    Payload decoder for DNIL LR210 LoRa Relay Controller
    '''

    def __init__(self):
        '''
        Constructor
        '''
        # We have two relay channels, simply indexed 1 and 2
        self._channels = {1: RelayChannel(1),\
                          2: RelayChannel(2)}
        self._temp = None

        # Stale data time handling
        self._temp_state_max_age = timedelta(minutes=190)
        self._temp_state_ts = None

        self._downlink_handler = None

        # DL command pending object
        self._dl_pend_cmd = None

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
            # we expect a 32-bit big endian integer here
            if len(data_arr) == 4:
                # Update actual relay channel states
                relay_data = int(data_arr[0]) << 8 | int(data_arr[1])
                for ch_index, channel in self._channels.items():
                    channel.set_actual((relay_data & (1 << (ch_index-1))) != 0)

                # Update internal temperature data
                temp_data = int(data_arr[2]) << 8 | int(data_arr[3])
                self._temp = (temp_data / 10.0) - 80.0

                # Update the timestamp on current data
                self._temp_state_ts = datetime.now()

                # Clear any pending commands
                self._dl_pend_cmd = None
            else:
                sys.stderr.write("Unexpected data length!\n")
        elif port == 1:
            # Protocol data deconding not fully implemented
            if len(data_arr) >= 2:
                if data_arr[0] == 0x01:
                    # Data
                    if data_arr[1] == 0x22:
                        # Relay status
                        relay_data = int(data_arr[2]) << 8 | int(data_arr[3])
                        for ch_index, channel in self._channels.items():
                            channel.set_actual((relay_data & (1 << (ch_index-1))) != 0)
        else:
            sys.stderr.write("Unknown port in UL data: " + str(port) + "\n")

    def _check_max_data_age(self):
        if self._temp_state_ts and \
        (self._temp_state_ts + self._temp_state_max_age) < datetime.now():
            sys.stderr.write("Invalidating temp and ch state due to age\n")
            self._temp = None
            for channel in self._channels.values():
                channel.reset_state()

    def _send_lora_relay_set_cmd(self, cmd_data):
        # We should send our command, 6 bytes needed
        dl_command = bytearray(6)
        dl_command[0] = 0x01 # set command
        dl_command[1] = 0x22 # relay state index
        dl_command[2] = (cmd_data >> 24) & 0xFF # big endian data
        dl_command[3] = (cmd_data >> 16) & 0xFF
        dl_command[4] = (cmd_data >> 8) & 0xFF
        dl_command[5] = (cmd_data >> 0) & 0xFF

        port = 1 # All DL command on port 1
        if self._downlink_handler:
            # If this is the first time we send the command, create an object
            # representing the command
            if not self._dl_pend_cmd:
                self._dl_pend_cmd = DownlinkSetCommand(cmd_data)

            # Send it over LoRa
            self._downlink_handler((dl_command, port))
        else:
            sys.stderr.write("No DL handler registered!\n")

    def _send_dl_channel_set_command(self):
        # Iterate over all channels and create the new channel set command
        cmd_data = 0
        update_needed = False
        for ch_index, channel in self._channels.items():
            change = channel.dl_command()
            if change[0]:
                update_needed = True
                # Set the mask from bit 16 and up
                cmd_data |= 1 << (16 + ch_index - 1)
                # Set the data bit
                cmd_data |= (change[1] << (ch_index - 1))
        if not update_needed:
            return

        # Change is needed, do we have a pending command equal to what we
        # would like to send now ?
        if self._dl_pend_cmd and self._dl_pend_cmd.cmd_is_equal(cmd_data):
            # Change is pending, no need to send again (yet)
            return

        # Send our new command
        self._send_lora_relay_set_cmd(cmd_data)

    def set_dl_handler(self, handler):
        ''' Register a DL data handler '''
        self._downlink_handler = handler

    def temperature(self):
        ''' Returns temp current relay controller internal temperature '''
        self._check_max_data_age()
        return self._temp

    def relay_states(self):
        ''' Returns a string of all current relay states '''
        state_list = []
        self._check_max_data_age()
        for channel in self._channels.values():
            state_list.append(channel.actual_state_str())
        return " ".join(state_list)

    def request_relay_states(self):
        ''' Send a query over LoRa to read current relay states '''
                # We should send our command, 6 bytes needed
        dl_command = bytearray(2)
        dl_command[0] = 0x02 # query command
        dl_command[1] = 0x22 # relay state index

        port = 1 # All DL command on port 1
        if self._downlink_handler:
            # Send it over LoRa
            self._downlink_handler((dl_command, port))
        else:
            sys.stderr.write("No DL handler registered!\n")

    def set_channel_state(self, new_channel_states):
        '''
        Set the requested relay channels, expects a list of channels to
        update, containing a tuple of channel (1 or 2) and new state
        True (active) or False (deactive)
        '''
        # Update each channel to the requested state
        for new_state in new_channel_states:
            channel_to_set = new_state[0]
            state = new_state[1]
            ch_match = False
            for ch_index, rly_ch in self._channels.items():
                if channel_to_set == ch_index:
                    rly_ch.set_requested(state)
                    ch_match = True
            if not ch_match:
                raise RuntimeError("Invalid channel requested!")

        # We always call the send command
        # in case no update is needed nothing is sent
        self._send_dl_channel_set_command()

    def periodic_poll(self):
        ''' Call this periodically to check retry commands '''
        if self._dl_pend_cmd and self._dl_pend_cmd.resend_due():
            # Check if this was the final attempt
            if not self._dl_pend_cmd.retry_ok():
                self._dl_pend_cmd = None
            else:
                self._dl_pend_cmd.increase_retry()
                self._send_lora_relay_set_cmd(self._dl_pend_cmd.cmd())
