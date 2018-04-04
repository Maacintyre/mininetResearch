
import time
from pox.core import core
import pox.openflow.libopenflow_01 as of

log = core.getLogger()

'''
Dumb DOS mitigation technique
    What do we do when a new packet comes in?
        1. Associate switch port to MAC address
        2. Test if the packet destination is known
            2A. Yes
                3. Test if this packet already has a registered pathway
                    3A. Yes
                        Create index for full pair
                        Register new timestamp
                    3B. No
                        Create index for full pair
                        Register half pair as a full pair
                        Register new timestamp
                    4. Decide if packet was sent before flood_delay expired
                        4A. Yes
                            Add drop rule to switch
                        4B. No
                            5 Decide if packet has exceeded n count
                                5A. Yes
                                    Add rule to expedite traffic
                                5B. No
                                    Send packet as a standalone
            2B. No
                Create a new src,dst tuple for the switch with only src
                Create a new timestamp list to monitor subsequent packets
                Send packet normally as it is the first
'''


class controller (object):
    """
    A controller object is created for each switch that connects.
    A Connection object for that switch is passed to the __init__ function.
    """

    def __init__(self, connection):
        # Keep track of the connection to the switch so that we can
        # send it messages!
        self.connection = connection

        # This binds our PacketIn event listener
        connection.addListeners(self)

        # Use this table to keep track of which ethernet address is on
        # which switch port (keys are MACs, values are ports).
        self.mac_to_port = {}

        # Use this to keep track of potential flow entries in the future
        # address_pairs are MACs
        self.hw_addresses = []
        self.timestamps = []
        self.blocked = []
        self.flow_count = 10
        self.flood_counts = []
        self.flood_delay = .001
        self.flood_time = time.time()
        self.flood_reset_time = 5.0

    def _handle_PacketIn(self, event):
        """
        Handles packet in messages from the switch.
        """

        packet = event.parsed  # This is the parsed packet data.

        def drop():
            # Kill buffer on switch
            if event.ofp.buffer_id is not None:
                msg = of.ofp_flow_mod()
                msg.match = of.ofp_match.from_packet(packet, event.port)
                port = self.mac_to_port[packet.src]
                msg.actions.append(of.ofp_action_output(port=port))
                msg.data = event.ofp
                # msg.buffer_id = event.ofp.buffer_id
                # msg.in_port = event.port
                event.connection.send(msg)

        def add():
            msg = of.ofp_flow_mod()
            msg.match = of.ofp_match.from_packet(packet, event.port)
            msg.idle_timeout = 10
            msg.hard_timeout = 30
            port = self.mac_to_port[packet.dst]
            msg.actions.append(of.ofp_action_output(port=port))
            msg.data = event.ofp
            event.connection.send(msg)

        def send(out_port):
            msg = of.ofp_packet_out()
            msg.data = event.ofp
            action = of.ofp_action_output(port=out_port)
            msg.actions.append(action)
            event.connection.send(msg)

        def xmit_packet(i):
            try:
                elapsed = self.timestamps[i][-1] - self.timestamps[i][-2]
            except IndexError:
                elapsed = self.flood_delay
            print 'elasped time {}'.format(elapsed)
            # if not self.blocked[i]:
            if not self.blocked[i]:
                print 'xmit 1'
                if elapsed < self.flood_delay:
                    print 'xmit 2'
                    if self.flood_counts[i] < 100:
                        print 'xmit 3'
                        self.flood_counts[i] += 1
                        send(out_port=self.mac_to_port[packet.dst])
                    else:
                        print 'xmit 4'
                        self.blocked[i] = True
                        drop()
                elif len(self.timestamps[i]) <= self.flow_count:
                    print 'xmit 5'
                    send(out_port=self.mac_to_port[packet.dst])
                else:
                    print 'xmit 6'
                    add()
            else:
                print 'xmit 7'
                drop()

        self.mac_to_port[packet.src] = event.port

        if time.time() - self.flood_time > self.flood_reset_time:
            self.flood_time = time.time()

            for i in range(len(self.flood_counts)):
                self.flood_counts[i] = 0

        if packet.src not in self.hw_addresses:
            i = len(self.hw_addresses)
            self.hw_addresses.append(packet.src)
            self.timestamps.append([time.time()])
            self.blocked.append(False)
            self.flood_counts.append(0)
        else:
            i = self.hw_addresses.index(packet.src)
            self.timestamps[i].append(time.time())

        if packet.dst in self.mac_to_port:
            xmit_packet(i)
        else:
            send(of.OFPP_FLOOD)


def launch():
    """
    Starts the component
    """
    def start_switch(event):
        log.debug("Controlling %s" % (event.connection,))
        controller(event.connection)
    core.openflow.addListenerByName("ConnectionUp", start_switch)
