from __future__ import print_function

import array
import sys
import dns.resolver
import requests
import math
import time
from ola.ClientWrapper import ClientWrapper

wrapper = None
mDNS = dns.resolver.Resolver()
mDNS.nameservers = ['224.0.0.251']  # mdns multicast address
mDNS.port = 5353  # mdns port

MaxLedsInUniverse = 128
Universe = 2  # Art-Net 1:0:2 NOTE: olad internal id
artnet_source = "10.0.0.7"
# Nodes = ["wled-unit1", "wled-unit2", "wled-unit3", "wled-unit4", "wled-unit5", "wled-unit6", "wled-unit7", "wled-unit8", "wled-unit9", "wled-unit10"]
Nodes = ["wled-test", "wled-Verho"]


def set_bit(value, bit_index):
    return value | (1 << bit_index)


def DmxSent(status):
    if not status.Succeeded():
        print('Error: %s' % status.message, file=sys.stderr)

    global wrapper
    if wrapper:
        wrapper.Stop()


def updateArtnet():
    dmxarray = array.array('B')
    for node in Nodes:
        statusmask = 0
        try:
            # who, what, class, tcp?, source ip, raise if no answer?, source port, lifetime
            a = mDNS.resolve(node+".local", 'A', 'IN', False, None, False, 0, 1)
        except:
            a = None

        if a is not None:
            statusmask = set_bit(statusmask, 0)
            try:
                response = requests.get("http://"+node+".local/json/info")
            except:
                response = None

            if response is not None:
                statusmask = set_bit(statusmask, 1)
                data = response.json()
            if data["live"] == True:
                statusmask = set_bit(statusmask, 2)
            if data["lip"] == artnet_source:
                statusmask = set_bit(statusmask, 3)
            ledlayout = 0
            if data["leds"]["count"] < 11:
                ledlayout = data["leds"]["count"]
            elif data["leds"]["count"] == 30:
                ledlayout = 11
            elif data["leds"]["count"] == 60:
                ledlayout = 12
            elif data["leds"]["count"] == 90:
                ledlayout = 13
            elif data["leds"]["count"] == 120:
                ledlayout = 14
            else:
                ledlayout = 15
            statusmask = statusmask | (ledlayout << 4)
            dmxarray.append(statusmask)  # chan 1

            universe_amount = math.ceil(
                data["leds"]["count"] / MaxLedsInUniverse)
            if universe_amount > 3:
                universe_amount = 0
            temperature = 0  # placeholder
            chan2 = (universe_amount << 6) | temperature
            dmxarray.append(chan2)  # chan 2

            feedback = data["u"]["ArtNetFeedback"]
            dmxarray.append(feedback["NetInfo"]["Network"])  # chan 3
            dmxarray.append(feedback["NetInfo"]["Subnet"])  # chan 4
            dmxarray.append(feedback["NetInfo"]["Universe"])  # chan 5
            dmxarray.append(feedback["Battery"]["percentageLeft"])  # chan 6
        else:
            dmxarray.append(statusmask)  # chan 1
            # Padding rest of the node data with zeros
            for i in range(2, 6):
                dmxarray.append(0)

        # Padding for future
        for i in range(7, 15):
            dmxarray.append(0)

        # Per-node channel info if it's hard to parse above:
        # * Channel 1 - statuses as bitmask
        # ** bit 1: Does node name resolve? (mDNS - effectively testing network connectivity)
        # ** bit 2: Is the JSON API answering?
        # ** bit 3: Is the node receiving Art-Net?
        # ** bit 4: ..from correct source?
        # ** bits 5-8: amount of leds -
        # * Channel 2 - temperature and amount of universes bitmask
        # ** bits 1-6: temperature with -16℃ offset to get range of 16-80
        # ** bits 7-8: amount of universes used (unit is using too many if it's using more than 3 universes - in which case returning 0)
        # * Channels 3-5 - Art-Net network info. Universe is starting universe.
        # * Channel 6 - battery status
        # * Channels 7-15 - reserved (battery cell monitoring planned among other things)

    global wrapper
    wrapper = ClientWrapper()
    client = wrapper.Client()
    client.SendDmx(Universe, dmxarray, DmxSent)
    wrapper.Run()


def main():
    while True:
        updateArtnet()
        time.sleep(15)


if __name__ == '__main__':
    main()
