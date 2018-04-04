
import time
import socket
import errno
from pox.core import core
from pox.lib.addresses import EthAddr
import pox.openflow.libopenflow_01 as of

log = core.getLogger()

'''
Dumb DOS mitigation technique
    When a packet comes in update the state of the controller and determine
        if the mac_to_blocked dict for the packet should be set to true.
    Then test if the packet destination is known or not.

    If the destination is known then test if the source is the server.
        If so add a flow rule for future traffic
        Else test if the packet is not blocked
            If so then test if the packet should be added as a flow rule or not
            If 5 messages with reasonable space between them is sent from a
                host then add a flow rule
            Else send the message as a one time instance
'''

ADD_FLOW_COUNT = 5
DROP_FLOW_COUNT = 100
PACKET_DELAY = 0.003
REFRESH_DELAY = 10.0
SERVER_ADDR = '00:00:00:00:00:01'


class controller (object):
    """
    A controller object is created for each switch that connects.
    A Connection object for that switch is passed to the __init__ function.
    """

    def __init__(self, connection):
        # Keep track of the connection to the switch so that we can
        # send it messages!
        self.connection = connection

        self.is_border = True

        # log.info('Creating socket')
        # self.sock = socket.socket(
        #     socket.AF_INET, socket.SOCK_STREAM
        # )
        # self.conn_good = True
        # try:
        #     log.debug('Trying to connect to {} at {}'.format('localhost',
        #                                                      10000))
        #     self.sock.connect(('localhost', 10000))
        #     output = 'id\n{}'.format(str(self.connection.dpid))
        #     self.sock.send(output)
        # except socket.error as e:
        #     if e.errno == errno.ECONNREFUSED:
        #         log.error('Could not connect to mapper.')
        #         self.conn_good = False
        #     elif e.errno == errno.ETIMEDOUT:
        #         log.error('Conn timed out resuming without mapper.')
        #         self.conn_good = False

        # This binds our PacketIn event listener
        connection.addListeners(self)

        # Use this table to keep track of which ethernet address is on
        # which switch port (keys are MACs, values are ports).
        self.mac_to_port = {}

        self.refresh_time = time.time()
        self.mac_to_timestamp = {}
        self.mac_to_blocked = {}
        self.mac_to_add_count = {}
        self.mac_to_drop_count = {}

        self.map = None

        # This holds a list of switches that are on the border of the network.
        # self.border_list = []
        #
        # This holds the last switch that received a packet as well as where it
        # had come from.
        # self.last_switch_state = ()

    def refresh_times(self):
        """
        Function to reset the flow counts to 0 if enough time has passed.
        """
        if time.time() - self.refresh_time >= REFRESH_DELAY:
            for key in self.mac_to_add_count:
                self.mac_to_add_count[key] = 0
                self.mac_to_drop_count[key] = 0
            self.refresh_time = time.time()

    def _handle_PacketIn(self, event):
        """
        Handles packet in messages from the switch.
        """

        def send_sock_data():
            log.info('Sending Mapper data')
            sock = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM
            )
            try:
                log.debug('Trying to connect to {} at {}'.format(
                    'localhost',
                    10000)
                )

                sock.connect(('localhost', 10000))
                output = '{}\n{}\n{}\n{}'.format(
                    self.connection.dpid,
                    'data',
                    packet.src,
                    packet.dst
                )

                count = sock.send(output)
                log.debug('{} of {} sent'.format(count, len(output)))
            except socket.error as e:
                if e.errno == errno.ECONNREFUSED:
                    log.error('Could not connect to mapper.')
            # sock.shutdown(socket.SHUT_RDWR)
            sock.close()

        def get_sock_border():
            is_border = True
            log.info('Sending Border Data')
            sock = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM
            )

            try:
                log.debug('Trying to connect to {} at {}'.format(
                    'localhost',
                    10000)
                )

                sock.connect(('localhost', 10000))
                output = '{}\n{}'.format(
                    self.connection.dpid,
                    'border'
                )

                sock.send(output)
                is_border = bool(sock.recv(1024))
            except socket.error as e:
                if e.errno == errno.ECONNREFUSED:
                    log.error('Could not connect to mapper.')
            # sock.shutdown(socket.SHUT_RDWR)
            sock.close()
            return is_border

        # def sock_send(data):
        #     total_sent = 0
        #     msg_len = len(data)
        #
        #     log.debug('Running send_sock_()')
        #     while total_sent < msg_len and self.conn_good:
        #         log.debug('Xmiting data.')
        #         sent = self.sock.send(data[msg_len:])
        #         log.debug('Sent: {}'.format(sent))
        #         if sent == 0:
        #             log.debug('Conn_good set to False')
        #             self.conn_good = False
        #         total_sent = total_sent + sent
        #         log.debug('Total sent: {}'.format(total_sent))
        #
        # def send_sock_data():
        #     """
        #     This function will send the src and dst to the mapper if the socket
        #         is still alive, else the conn_good flag is set to False
        #     """
        #     log.debug('Running send_sock_data()')
        #     if self.conn_good:
        #         data = 'data\n{}\n{}'.format(packet.src, packet.dst)
        #         log.debug('Data sent: {}'.format(data))
        #         sock_send(data)
        #
        # def get_sock_border():
        #     log.debug('Running get_sock_border()')
        #     if self.conn_good:
        #         data = 'border'
        #         log.debug('Data sent: {}'.format(data))
        #         sock_send(data)
        #         return bool(self.sock.recv(1024))
        #     log.debug('Conn_good is False')
        #     return True

        def send(out_port):
            """
            This function will send a one time command to send the current
            packet to the port specified.
            """
            msg = of.ofp_packet_out()
            msg.data = event.ofp
            action = of.ofp_action_output(port=out_port)
            msg.actions.append(action)
            event.connection.send(msg)

        def drop():
            """
            This function will send a flow rule to drop all packets based on
                the current packet.
            """
            if event.ofp.buffer_id is not None:
                msg = of.ofp_flow_mod()
                msg.match.in_port = self.mac_to_port[packet_src]
                msg.match.dl_type = 0x0800  # Filter for most TCP packets
                port = self.mac_to_port[packet_src]
                msg.actions.append(of.ofp_action_output(port=port))
                event.connection.send(msg)

        def add():
            """
            This function adds a new flow to allow similar packets in the
                future to be expedited through the switch.
            """
            msg = of.ofp_flow_mod()
            msg.match.in_port = self.mac_to_port[packet_src]
            msg.match.dl_type = 0x0800  # Filter for most TCP packets
            msg.idle_timeout = 10
            msg.hard_timeout = 30
            port = self.mac_to_port[packet_dst]
            msg.actions.append(of.ofp_action_output(port=port))
            msg.data = event.ofp
            event.connection.send(msg)

        def update_dicts():
            """
            This function updates the internal state of the controller based on
                the currently received packet. If the source has not been
                registered before then create new state variables for it.
                Else update the current state variables for it based on elapsed
                time since last packet.
            """
            if packet_src in self.mac_to_timestamp \
                    and packet_src[1] != EthAddr(SERVER_ADDR):
                if self.mac_to_blocked[packet_src]:
                    return

                elapsed_time = time.time() - self.mac_to_timestamp[packet_src]
                self.mac_to_timestamp[packet_src] = time.time()

                # print 'Time elapsed {}'.format(elapsed_time)

                if elapsed_time < PACKET_DELAY:
                    self.mac_to_drop_count[packet_src] += 1
                    if self.mac_to_drop_count[packet_src] >= \
                            DROP_FLOW_COUNT:
                        self.mac_to_blocked[packet_src] = True
                else:
                    self.mac_to_add_count[packet_src] += 1
            elif packet_src[1] != EthAddr(SERVER_ADDR):
                self.mac_to_timestamp[packet_src] = time.time()
                self.mac_to_blocked[packet_src] = False
                self.mac_to_add_count[packet_src] = 0
                self.mac_to_drop_count[packet_src] = 0

        # print '\nConnection: {}'.format(self.connection)
        # print 'DPID?: {}'.format(self.connection.dpid)  # This is the one
        # print 'ID?: {}'.format(self.connection.ID)
        # print 'Connection type: {}'.format(type(self.connection))

        """
        Start making decisions on current packet
        """
        # print 'PID: {}'.format(os.getpid())
        # if self.map is None:
        #     print 'Creating new mapper.'
        #     self.map = nm(self.connection, SERVER_ADDR, 1)
        #     print "Created new mapper."
        #     print 'Printing vars:'
        #     self.map.getVars()
        # else:
        #     print 'Mapper already created, printing vars.'
        #     self.map.getVars()

        packet = event.parsed  # This is the parsed packet data.
        self.mac_to_port[(self.connection, packet.src)] = event.port
        packet_src = (self.connection, packet.src)
        packet_dst = (self.connection, packet.dst)
        update_dicts()
        log.info('Sending socket data.')
        send_sock_data()
        log.info('Getting border data.')
        self.is_border = get_sock_border()

        # log.debug('Mac table.')
        # for key, value in self.mac_to_port.iteritems():
        #     log.debug(str(key), str(value))

        log.debug('For switch: {} with source: {} and dest: {}\n'.format(
            self.connection, packet.src, packet.dst
        ))
        log.debug('Switch is border: {}'.format(self.is_border))

        if packet_dst in self.mac_to_port:
            if packet.src == EthAddr(SERVER_ADDR):
                log.debug('Adding server flow rule at time: {} '.format(
                    time.time()
                ))
                add()
            elif self.mac_to_blocked[packet_src] and self.is_border:
                log.debug('Adding drop flow rule at time: {} '.format(
                    time.time()
                ))
                drop()
            else:
                if self.mac_to_add_count[packet_src] > ADD_FLOW_COUNT:
                    log.debug('Adding flow rule to server at time: {} '.format(
                        time.time()
                    ))
                    add()
                else:
                    log.debug('Sending packet out one time at time: {} '.format(
                        time.time()
                    ))
                    send(out_port=self.mac_to_port[packet_dst])

        else:
            log.debug('Flooding packet out at time: {} '.format(
                time.time()
            ))
            send(out_port=of.OFPP_FLOOD)

        self.refresh_times()

        # print 'Received packet from {}'.format(packet.src)
        # print 'With event.port of {}'.format(event.port)
        # print 'Sending packet to {}'.format(packet.dst)
        # if packet.dst in self.mac_to_port:
        #     print 'With event.port of {}'.format(self.mac_to_port[packet.dst])
        # else:
        #     print 'With and unknown event.port'
        # print ''


def launch():
    """
    Starts the component
    """
    def start_switch(event):
        log.debug("Controlling %s" % (event.connection,))
        controller(event.connection)
    core.openflow.addListenerByName("ConnectionUp", start_switch)
