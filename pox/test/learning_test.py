from pox.core import core
import pox.openflow.libopenflow_01 as of

log = core.getLogger()


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

    def _handle_PacketIn(self, event):
        """
        Handles packet in messages from the switch.
        """

        packet = event.parsed  # This is the parsed packet data.

        self.mac_to_port[packet.src] = event.port

        if packet.dst in self.mac_to_port:  # Create a rule for future packets
            msg = of.ofp_flow_mod()
            msg.match = of.ofp_match.from_packet(packet, event.port)
            msg.idle_timeout = 10
            msg.hard_timeout = 30
            port = self.mac_to_port[packet.dst]
            msg.actions.append(of.ofp_action_output(port=port))
            msg.data = event.ofp
        else:
            msg = of.ofp_packet_out()
            msg.data = event.ofp  # The actual ofp_packet_in message.
            action = of.ofp_action_output(port=of.OFPP_FLOOD)
            msg.actions.append(action)

        self.connection.send(msg)


def launch():
    """
    Starts the component
    """
    def start_switch(event):
        log.debug("Controlling %s" % (event.connection,))
        controller(event.connection)
    core.openflow.addListenerByName("ConnectionUp", start_switch)
