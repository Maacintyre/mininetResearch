#! /usr/bin/env python
import threading
import socket
import select
import logging
from Queue import Queue

logging.basicConfig(level=logging.NOTSET)
log = logging.getLogger(__name__)


class net_node:

    def __init__(self, id, src):
        self.id = id
        self.srcs = []
        self.srcs.append(src)


"""
    Class to create a map of an arbitrary tree like network with a root
    The purpose of this script is to enable the user to quickly map and
        ascertain the gateway switches on a server oriented network

    This program must perform the following tasks

    init: server_mac_addess, server_switch_ID

        1. Use this to store the server addr and the switch addr to orient the
            map.

    append: switch_id, packet_src, packet_dst

        1. Accept an instance of switch information along with the source
            hardware address appended to a list on a new node.

            A. This should be fed in as packets are read from the switches.

            B. This node will not have any connections initially, as a result
                many connectionless nodes may exist.

        2. If the packet src is the server then the network is mapped
            starting with the server switch.

            A. This packet will not be broadcast and will be directed, thus
                the only switches to be registered will be the ones along the
                path.

            B. When creating a new path from the server switch the packet
                destination should be compared with the old src along the same
                nodes for directional accuracy. This will help ensure that
                redundant paths are not built while the server is talking to
                two hosts.

            C. When arriving at a node where the packet src is the server and
                the packet dst was stored in the node list remove the old src.
                (Maybe make this point optional)

            D. While the final border switch can never be truly known, this
                method will search for the furthest switch that can be safely
                assumed to be the border switch.

            E. I.E this script can find the border switches under the domain
                of the controller that runs this script.

        3. If a new host passes through an already registered switch then the
            new packet source is appended to the register list.

            A. This will allow multiple paths to be built simultaneously.

    isBorder: switch_connection

        1. Take the current switch information and traverse the tree if one
            exists and determine if the switch is lowest on the tree.

"""


class network_mapper:
    """
        Network mapping class for mapping arbitrary network trees
    """

    def __init__(self, srv_addr, swt_addr):
        self.srv_addr = srv_addr
        self.swt_addr = swt_addr

        self.nodes = {}
        self.last_nodes = []
        self.src_to_block = {}
        # self.tup_to_block = {}

    def append(self, id, src, dst):
        log.debug('Running mapper class for {} {} {}'.format(id, src, dst))
        if id in self.nodes:
            log.debug('Id found.')
            if dst == 'ff:ff:ff:ff:ff:ff':
                log.debug('DST is broadcast.')
                if src not in self.nodes[id].srcs:
                    self.nodes[id].srcs.append(src)
            elif dst != self.srv_addr:
                log.debug('DST is the host.')
                tup = (id, dst)
                if id == self.swt_addr and not self.src_to_block[tup]:
                    log.debug('Backtracing from the server switch')
                    self.last_nodes.append(self.nodes[id])
                    self.src_to_block[tup] = True
                elif not self.src_to_block[tup]:
                    log.debug('Moving the border up.')
                    for node in self.last_nodes:
                        if dst in node.srcs:
                            index = self.last_nodes.index(node)
                            break
                    # self.last_nodes[index].append(self.nodes[id])
                    self.last_nodes[index] = self.nodes[id]
                    self.src_to_block[tup] = True
        else:
            log.debug('Id not found adding new node for ID: {} SRC: {}'.format(
                id,
                src
            ))
            self.nodes[id] = net_node(id, src)
            if src not in self.src_to_block:
                self.src_to_block[(id, src)] = False

    def is_border(self, id):
        log.debug('Running is_border.')
        if len(self.last_nodes) > 0:
            log.debug('Parsing node list.')
            for node in self.last_nodes:
                log.debug('\tNode.id: {} id: {} Result: {}'.format(
                    node.id,
                    id,
                    node.id == id
                ))
                if node.id == id:
                    return True
                else:
                    return False
        return True


"""
    Class thread to monitor various queues and process commands to submit to
        the network_mapper class.

    run:
        1. Monitor the read queue for any new data submission from
            conn_threads.

            1.1 If a command is submitted the command is parsed for the
                thread name, the command, and additional args.

            1.2 If the command is to add data then the args are parsed into
                arguments to be submitted to the network_mapper.

            1.3 If the command is to get border then the is_border is called
                for the switch name and returned to the queue mapped to the
                thread name.

        2. GOTO Step 1

    append_worker: thread_name, switch_info, write_queue
        1. Form a tuple of switch_info and write queue.

        2. Map tuple to thread_name.
"""


class network_thread (threading.Thread):

    def __init__(self, read_queue):
        threading.Thread.__init__(self)
        self.nm = network_mapper('00:00:00:00:00:01', '1')
        self.read_queue = read_queue
        self.thread_name_to_tup = {}

    def append_worker(self, thread_name, switch_id, write_queue):
        tup = (switch_id, write_queue)  # 1
        self.thread_name_to_tup[thread_name] = tup  # 2

    def run(self):
        while True:
            bucket = self.read_queue.get(True)  # 1
            args = bucket.split('\n')  # 1.1
            if args[1] == 'data':  # 1.2
                id = self.thread_name_to_tup[args[0]][0]
                src, dst = args[2:]
                self.nm.append(id, src, dst)
            else:  # 1.3
                id = self.thread_name_to_tup[args[0]][0]
                self.thread_name_to_tup[args[0]][1].put(
                    str(self.nm.is_border(id))
                )


"""
    Class thread to monitor the network connection given to it then traffic
        data through its various queues

    run:
        1. Read from the TCP connection stored in the class.

        2. When data is received parse the data for a command and args.

            2.1 When command is data send thread_name, cmd arg1, and arg2 to
                the write buffer.

            2.2 When the command is border send thread_name, and cmd to the
                write buffer.

                2.2.1 Listen on read buffer.

                2.2.2 When response is ready send back along TCP connection

        3. GOTO Step 1
"""


class conn_thread (threading.Thread):

    def __init__(self, thread_name, conn, write_buffer, read_buffer):
        threading.Thread.__init__(self)
        self.thread_name = thread_name
        self.conn = conn
        self.write_buffer = write_buffer
        self.read_buffer = read_buffer

    def run(self):
        log.debug('{} started.'.format(self.thread_name))
        while True:
            bucket = self.conn.recv(1024)  # 1
            log.debug('{} received {}'.format(self.thread_name, bucket))
            args = bucket.split('\n')  # 2
            output = self.thread_name + '\n'
            if args[0] == 'data':  # 2.1
                log.debug(
                    '{} processing data request.'.format(self.thread_name)
                )
                output = output + 'data\n'
                output = output + args[1] + '\n'
                output = output + args[2]
                log.debug(
                    '{} writing to queue: {}'.format(self.thread_name, output)
                )
                self.write_buffer.put(output, True)
            else:  # 2.2
                output = output + 'border\n'
                self.write_buffer.put(output, True)
                dat_back = self.read_buffer.get(True)  # 2.2.1
                self.conn.send(dat_back)  # 2.2.2


"""
    Main program to create TCP connections with openflow controllers and
        retrieve feedback their feed back. This program makes use of the
        network_mapper class to manage network information and retrieve border
        information.

    This program must perform the following tasks:

    Server:

        1. Create a read queue to be passed to the network mapper class.

        2. Create the network mapper thread and pass it the read queue.
            See Mapper Class.

        3. Start up the server listener and accept incoming connections

        4. When new connections are created:

            4.1 Read the switch information from the socket stream

            4.2 Create a new write queue

            4.3 Create a new thread name.

            4.4 Pass the switch info, the write queue and thread name to the
                network_thread.

            4.5 Spawn new connection_thread with the connection, thread_name
                and the read and write queues

        5. GOTO Step 4
"""

if __name__ == '__main__':
    def test1():
        log.info('Starting up Mapping Server.')
        mapper = network_mapper('00:00:00:00:00:01', '1')

        log.info('Creating Server Socket.')
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setblocking(0)

        server_address = ('localhost', 10000)
        log.debug('Binding socket to {}.'.format(server_address))
        server.bind(server_address)

        log.info('Server is ready to receive clients.')
        server.listen(5)

        inputs = [server]
        outputs = []
        conn_to_id = {}
        conn_to_queue = {}

        while True:
            read, write, err = select.select(inputs, outputs, inputs)

            for s in read:
                if s is server:
                    conn, client_addr = s.accept()
                    log.info('New Connection established from {}.'.format(
                        client_addr
                    ))
                    conn.setblocking(0)
                    inputs.append(conn)
                    conn_to_queue[conn] = Queue()
                else:
                    data = s.recv(1024)
                    if data:
                        log.debug('Received {} from {}'.format(
                            data,
                            s.getpeername()
                        ))
                        args = data.split('\n')
                        conn_to_id[s] = args[0]
                        if args[1] == 'data':
                            log.info('Adding new map information.')
                            mapper.append(conn_to_id[s],
                                          args[2],
                                          args[3]
                                          )
                            inputs.remove(s)
                            del conn_to_queue[s]
                            del conn_to_id[s]
                            s.close()
                        elif args[1] == 'border':
                            log.info('Getting border information.')
                            is_border = mapper.is_border(conn_to_id[s])
                            conn_to_queue[conn].put(is_border, True)
                            if s not in outputs:
                                outputs.append(s)
                        else:
                            log.info('Unknown command.')
                    else:
                        log.info('Connection broken: closing Sockets')
                        if s in outputs:
                            outputs.remove(s)
                        inputs.remove(s)
                        del conn_to_queue[s]
                        s.close()

            for s in write:
                try:
                    next_msg = conn_to_queue[s].get_nowait()
                except Queue.Empty:
                    outputs.remove(s)
                else:
                    log.info('Sending border information {} to {}'.format(
                        next_msg,
                        conn_to_id[s]
                    ))
                    s.send(str(next_msg))
                del conn_to_queue[s]
                del conn_to_id[s]
                inputs.remove(s)
                outputs.remove(s)
                s.close()

            for s in err:
                log.error('Exception in handling {}'.format(s.getpeername()))
                if s in outputs:
                    outputs.remove(s)
                inputs.remove(s)
                s.close()

    def test():
        log.info('Creating network queue.')
        net_queue = Queue()  # 1
        log.info('Starting up network mapper.')
        net_thread = network_thread(net_queue)  # 2
        net_thread.start()

        log.info('Creating Server Socket.')
        server_sock = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM
        )
        server_sock.bind(('localhost', 10000))
        server_sock.listen(5)  # 3

        counter = 0
        log.info('Starting up Server.')
        while True:
            client, addr = server_sock.accept()  # 4
            log.info('Received new client.')
            bucket = client.recv(1024)  # 4.1
            new_queue = Queue()  # 4.2
            thread_name = 'Thread-' + str(counter)  # 4.3

            log.debug('Appending new worker thread {}: {}'.format(thread_name,
                                                                  bucket
                                                                  )
                      )
            net_thread.append_worker(thread_name,
                                     bucket,
                                     new_queue
                                     )  # 4.4

            log.debug('Starting up new connection monitor named {}'.format(
                thread_name
            ))
            connection_thread = conn_thread(
                thread_name,
                client,
                net_queue,
                new_queue
            )  # 4.5

            connection_thread.start()

            counter += 1

    test1()
