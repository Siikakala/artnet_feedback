from __future__ import print_function
import array, sys, dns.resolver, requests, math, time
from ola.ClientWrapper import ClientWrapper

wrapper = None
mDNS = dns.resolver.Resolver()
mDNS.nameservers = ['224.0.0.251']  # mdns multicast address
mDNS.port = 5353  # mdns port

if "debug" in sys.argv:
    debug = True
else:
    debug = False

if debug:
    print("Debug present")

MaxLedsInUniverse = 128
Universe = 2  # Art-Net 1:0:2 NOTE: olad internal id
artnet_source = "10.0.0.7"
Nodes = ["wled-unit1", "wled-unit2", "wled-unit3", "wled-unit4", "wled-unit5", "wled-unit6", "wled-unit7", "wled-unit8", "wled-unit9", "wled-unit10"]
#Nodes = ["wled-test", "wled-Verho"]

def DmxSent(status):
    if not status.Succeeded():
        print('Error: %s' % status.message, file=sys.stderr)

    global wrapper
    if wrapper:
        wrapper.Stop()


def updateArtnet():
    dmxarray = array.array('B')
    for node in Nodes:
        if debug:
            print("- Node "+node)
        try:
            # who, what, class, tcp?, source ip, raise if no answer?, source port, lifetime s
            a = mDNS.resolve(node+".local", 'A', 'IN', False, None, False, 0, 1)
        except:
            a = None

        if a is not None:
            if debug:
                print("    Node mDNS resolved, querying json api")
            dmxarray.append(255) # chan 1
            try:
                response = requests.get("http://"+node+".local/json/info")
            except:
                response = None

            if response is not None:
                dmxarray.append(255) # chan 2
                data = response.json()
                if debug:
                    print("    API accessible")
            else:
                dmxarray.append(0) # chan 2
                data = None
                if debug:
                    print("    API not answering")

            if data["live"] == True:
                dmxarray.append(255) # chan 3
                if debug:
                    print("    Node is receiving live data")
            else:
                dmxarray.append(0) # chan 3
                if debug:
                    print("    Node is NOT receiving live data")

            if data["lip"] == artnet_source:
                dmxarray.append(255) # chan 4
                if debug:
                    print("    Node is receiving data from correct source "+artnet_source)
            else:
                dmxarray.append(0) # chan 4
                if debug:
                    print("    Node source is NOT correct: "+artnet_source)

            if data["leds"]["count"] > 250:
                dmxarray.append(255) # chan 5
            else:
                dmxarray.append(data["leds"]["count"]) # chan 5
            if debug:
                print("    LED count: "+str(data["leds"]["count"]))

            universe_amount = math.ceil(
                data["leds"]["count"] / MaxLedsInUniverse)
            dmxarray.append(universe_amount) # chan 6
            if debug:
                print("    Universe count: "+str(universe_amount))

            feedback = data["u"]["ArtNetFeedback"]
            dmxarray.append(feedback["NetInfo"]["Network"])  # chan 7
            dmxarray.append(feedback["NetInfo"]["Subnet"])  # chan 8
            dmxarray.append(feedback["NetInfo"]["Universe"])  # chan 9
            if feedback["Battery"]["currentVoltage"] > 0:
                dmxarray.append(feedback["Battery"]["percentageLeft"])  # chan 10
            else:
                dmxarray.append(250) # chan 10
            if debug:
                print("    First Art-Net universe: "+str(feedback["NetInfo"]["Network"])+":"+str(feedback["NetInfo"]["Subnet"])+":"+str(feedback["NetInfo"]["Universe"]))
                print("    Battery level "+str(feedback["Battery"]["percentageLeft"])+"% - voltage "+str(feedback["Battery"]["currentVoltage"])+"V / "+str(feedback["Battery"]["maxVoltage"])+"V")
        else:
            if debug:
                print("    Node NOT reachable - mDNS didn't resovle. Padding DMX array")
            dmxarray.append(10) # chan 1
            # Padding rest of the node data with zeros
            for i in range(1, 10):
                dmxarray.append(0)

        # Per-node channel info if it's hard to parse above:
        # * Channel 1: Does node name resolve? (mDNS - effectively testing network connectivity)
        # * Channel 2: Is the JSON API answering?
        # * Channel 3: Is the node receiving Art-Net?
        # * Channel 4: ..from correct source?
        # * Channel 5: amount of leds (255 if unknown or more than 250)
        # * Channel 6: amount of universes
        # * Channels 7-9 - Art-Net network info. Universe is starting universe.
        # * Channel 10 - battery status, 250 if battery not present (voltage -1)

    if debug:
        print("Sending DMX data")
    global wrapper
    wrapper = ClientWrapper()
    client = wrapper.Client()
    client.SendDmx(Universe, dmxarray, DmxSent)
    wrapper.Run()


def main():
    while True:
        if debug:
            print("Discovering nodes - nodelist: "+str(Nodes))
        updateArtnet()
        if debug:
            print("Iteration done, 15s sleep")
        time.sleep(15)


if __name__ == '__main__':
    main()
