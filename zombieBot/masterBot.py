import logging
import socket
# import random
import select
import time
import sys
# import errno
import Queue
import csv


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


def read_bot_stats():
    count = 0
    retList = []
    with open('botStats.csv') as f:
        csvReader = csv.DictReader(f)
        for row in csvReader:
            count += 1
            output = '{}-{},{},{},{},{}'.format('robot',
                                                count,
                                                row['speed'],
                                                row['size'],
                                                row['count'],
                                                row['isDos']
                                                )
            retList.append(output)
    return count, retList


def main():
    logging.basicConfig(level=logging.NOTSET)
    log = logging.getLogger(__name__)

    log.info('Starting up master bot server.')

    log.info('Getting bot stats.')
    expected_bot_number, bot_stats = read_bot_stats()
    log.debug('Expected count: {}'.format(expected_bot_number))

    master = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    master.setblocking(0)

    master_addr = ('localhost', 12000)
    master.bind(master_addr)
    log.debug('Server address set to: {}'.format(master_addr))

    master.listen(5)
    log.info('Server is listening for bots to connect.')

    time_to_wait = 10.0
    current_bot_number = 0
    waiting_on = expected_bot_number
    inputs = [master]
    outputs = []
    conn_to_queue = {}
    conn_to_time = {}
    conn_to_lCmd = {}
    conn_to_started = {}
    cmds = bot_commands()
    currentTime = time.time
    newQueue = Queue.Queue

    try:
        while True:
            read, write, err = select.select(inputs, outputs, inputs, 0.05)

            # Reading from Sockets
            for s in read:
                if s is master:
                    bot, bot_addr = s.accept()
                    log.info('Received new connection from {}.'.format(
                        bot_addr)
                    )
                    # Adding bot to read and write.
                    inputs.append(bot)
                    outputs.append(bot)
                    conn_to_queue[bot] = newQueue()
                    conn_to_time[bot] = currentTime()
                    conn_to_lCmd[bot] = cmds.SETVALUES
                    conn_to_started[bot] = False
                    waiting_on -= 1
                    log.debug('I am waiting on {} friends now.'.format(
                        waiting_on
                    ))

                    # Give bot a message.
                    message = '{},{}'.format(cmds.ctos[cmds.SETVALUES],
                                             bot_stats[current_bot_number])
                    current_bot_number += 1
                    log.debug('Prepared message for bot: {}'.format(message))
                    conn_to_queue[bot].put(message)

                    if waiting_on == 0:
                        log.debug('No more bots will join the party.')
                        inputs.remove(s)
                        s.close()
                else:
                    buffer = s.recv(1024)
                    buffer = buffer.strip()
                    log.debug('Received data from {}'.format(s.getpeername()))
                    if buffer:
                        try:
                            if cmds.stoc[buffer] == cmds.DEAD:
                                log.debug('Bot went offline, closing socket')
                                inputs.remove(s)
                                del conn_to_lCmd[s]
                                s.close()
                            elif (conn_to_lCmd[s] == cmds.SETVALUES or
                                  conn_to_lCmd[s] == cmds.START) \
                                    and cmds.stoc[buffer] != cmds.OK\
                                    or conn_to_lCmd[s] == cmds.HEART \
                                    and cmds.stoc[buffer] != cmds.BEAT:
                                log.error('Bot sent incorrect response, got:'
                                          ' {}, Closing socket.'.format(
                                              buffer))
                                inputs.remove(s)
                                del conn_to_lCmd[s]
                                s.close()
                            elif cmds.stoc[buffer] == cmds.BEAT:
                                conn_to_time[s] = currentTime()
                            else:
                                log.debug('Received correct response.')
                            conn_to_lCmd[s] = cmds.NOCMD
                        except KeyError:
                            log.debug('Bad Response, Closing.')
                            inputs.remove(s)
                            del conn_to_lCmd[s]
                            s.close()

                    else:
                        log.error('Connection is broken. Cleaning up.')
                        inputs.remove(s)
                        del conn_to_lCmd[s]
                        s.close()

            # Writing to sockets
            for s in write:
                try:
                    msg = conn_to_queue[s].get_nowait()
                    log.debug(
                        'Sending message to {}: it says {}'
                        ''.format(s.getpeername(), msg))
                except Queue.Empty:
                    log.debug('Queue is empty.')
                else:
                    total_sent = 0
                    msglen = len(msg)
                    while total_sent < msglen:
                        sent = s.send(msg[total_sent:])
                        if sent == 0:
                            log.error('Connection to bot broke. Removing bot.')
                            inputs.remove(s)
                            outputs.remove(s)
                            del conn_to_queue[s]
                            s.close()
                            continue
                        else:
                            total_sent += sent
                            log.debug(
                                'Sent {} of {}.'.format(total_sent, msglen)
                            )
                finally:
                    outputs.remove(s)
                    del conn_to_queue[s]

            # Handling exceptions from sockets
            for s in err:
                log.error("Exceptional error occurred for {}".format(
                    s.getpeername()
                ))
                inputs.remove(s)
                outputs.remove(s)
                del conn_to_queue[s]
                del conn_to_time[s]
                s.close()

            # Send out heartbeat signals
            for s in inputs:
                if s != master and \
                        currentTime() - conn_to_time[s] > time_to_wait and \
                        conn_to_lCmd[s] == cmds.NOCMD:
                    log.debug('Preparing heart message for bot {}'.format(
                        s.getpeername()
                    ))
                    outputs.append(s)
                    conn_to_queue[s] = newQueue()
                    conn_to_queue[s].put(cmds.ctos[cmds.HEART])
                    conn_to_lCmd[s] = cmds.HEART
                    conn_to_time[s] = currentTime()

            # Send out start signals
            for s in inputs:
                if s != master and not conn_to_started[s] \
                        and conn_to_lCmd[s] == cmds.NOCMD \
                        and current_bot_number == expected_bot_number:
                    log.debug('Preparing start signal for bot {}'.format(
                        s.getpeername()
                    ))
                    outputs.append(s)
                    conn_to_queue[s] = newQueue()
                    conn_to_queue[s].put(cmds.ctos[cmds.START])
                    conn_to_lCmd[s] = cmds.START
                    conn_to_started[s] = True

            if len(inputs) == 0 and waiting_on == 0:
                log.info('All my friends are dead. Shutting down.')
                sys.exit()

    except KeyboardInterrupt:
        log.error('System was terminated via keyboard.')
    except SystemExit:
        log.debug('Work completed.')
    finally:
        log.debug('Server was terminated, Cleaning up.')
        for i in inputs:
            i.close()
        for o in outputs:
            o.close()
        master.close()
        # for key, _ in conn_to_queue.iteritems():
        #     del conn_to_queue[key]


if __name__ == '__main__':
    main()
