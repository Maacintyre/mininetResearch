import logging
import socket
import random
import select
import time
import sys
# import errno
import Queue


class bot_commands:
    NOCMD = -1
    OK = 0
    SETVALUES = 1
    HEART = 2
    BEAT = 3
    START = 4
    DEAD = 5

    stoc = {
        'noCmd': NOCMD,
        'ok': OK,
        'setValues': SETVALUES,
        'heart': HEART,
        'beat': BEAT,
        'start': START,
        'dead': DEAD
    }

    ctos = {
        NOCMD: 'noCmd',
        OK: 'ok',
        SETVALUES: 'setValues',
        HEART: 'heart',
        BEAT: 'beat',
        START: 'start',
        DEAD: 'dead'
    }


def generate_problem():
    lhs = random.randint(0, 1024)
    rhs = random.randint(0, 1024)
    operand_select = random.randint(1, 4)

    if operand_select == 1:
        # answer = lhs + rhs
        operand = '+'
    elif operand_select == 2:
        # answer = lhs - rhs
        operand = '-'
    elif operand_select == 3:
        # answer = lhs * rhs
        operand = '*'
    else:
        if rhs == 0:
            lhs, rhs = rhs, lhs
        # answer = lhs / rhs
        operand = '/'

    return '{} {} {}'.format(lhs, operand, rhs)


def main():

    logging.basicConfig(level=logging.NOTSET)
    log = logging.getLogger(__name__)

    log.info('Starting up Zombie.')

    master = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # master.setblocking(0)

    # server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # server.setblocking(0)

    master_addr = ('localhost', 12000)
    server_addr = ('localhost', 11000)
    log.debug('Master address: {}, Server address: {}'.format(
        master_addr,
        server_addr,
    ))

    master.connect(master_addr)
    log.info('Connected to master.')

    inputs = [master]
    outputs = []
    err = []
    conn_to_queue = {}
    cmds = bot_commands()
    currentTime = time.time
    newQueue = Queue.Queue
    hertz, problems_sent, problem_size, problem_count = 0, 0, 0, 0
    wait_time = 0.0
    isDos = ''
    start = 0
    last_time = currentTime()

    try:
        while True:
            read, write, err = select.select(inputs, outputs, err, 0.001)

            for s in read:
                def cmd(c_int):
                    log.debug('Preparing message to be sent: {}'.format(
                        cmds.ctos[c_int]
                    ))
                    outputs.append(s)
                    conn_to_queue[s] = newQueue()
                    conn_to_queue[s].put(cmds.ctos[c_int])

                if s is master:
                    buffer = s.recv(1024)
                    log.debug('Received data from master: {}'.format(buffer))
                    if buffer:
                        fields = buffer.split(',')
                        if fields[0] == cmds.ctos[cmds.SETVALUES]:
                            name = fields[1]
                            hertz = float(fields[2])
                            problem_size = int(fields[3])
                            problem_count = int(fields[4])
                            isDos = fields[5]
                            wait_time = 1.0 / hertz
                            # Send ok signal
                            cmd(cmds.OK)
                        elif fields[0] == cmds.ctos[cmds.HEART]:
                            # Send the beat signal
                            cmd(cmds.BEAT)
                        elif fields[0] == cmds.ctos[cmds.START]:
                            # Send the ok signal
                            cmd(cmds.OK)
                            start = 1
                    else:
                        log.error(
                            'Connection to master broke. Completing task.'
                        )
                        inputs.remove(s)
                        s.close()
                else:
                    # Read from server here
                    pass

            for s in write:
                if s is master:
                    try:
                        buffer = conn_to_queue[s].get_nowait()
                        log.debug('Readying data to be sent.')
                    except Queue.Empty:
                        log.error('Queue is empty.')
                    else:
                        total_sent = 0
                        msglen = len(buffer)
                        while total_sent < msglen:
                            sent = s.send(buffer[total_sent:])
                            if sent == 0:
                                log.error('Connection broke to master. '
                                          'Completing task.')
                                inputs.remove(s)
                                outputs.remove(s)
                                del conn_to_queue[s]
                            else:
                                total_sent += sent
                            if buffer == cmds.ctos[cmds.DEAD]:
                                sys.exit()
                    finally:
                        outputs.remove(s)
                        del conn_to_queue[s]
                else:
                    # Write to server here
                    pass

            for s in err:
                log.debug('Exceptional circumstance occurred for '
                          '{}'.format(s.getpeername()))
                sys.exit()

            # Connect to server here
            if start == 1:
                log.info('Connecting to server now.')
                start = 2

            if currentTime() - last_time > wait_time and \
                    start == 2:
                if problems_sent < problem_count:
                    log.debug('Preparing problem for server.')
                    for i in range(problem_size):
                        pass
                    problems_sent += 1
                    last_time = currentTime()
                else:
                    outputs.append(master)
                    conn_to_queue[master] = newQueue()
                    conn_to_queue[master].put(cmds.ctos[cmds.DEAD])

    except KeyboardInterrupt:
        log.error('Zombie terminated via the keyboard.')
    except SystemExit:
        log.info('Zombie completed all tasks.')
    finally:
        for i in inputs:
            i.close()
        for o in outputs:
            o.close()
        for key, value in conn_to_queue.iteritems():
            del conn_to_queue[key]


if __name__ == '__main__':
    main()
