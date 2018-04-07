import logging
import socket
# import random
import select
import time
# import os
# import errno
import Queue


class bot_commands:
    OK = 0
    SETVALUES = 1
    HEART = 2
    BEAT = 3
    START = 4
    DEAD = 5

    cmds = {OK: 'ok',
            SETVALUES: 'setValues',
            HEART: 'heart',
            BEAT: 'beat',
            START: 'start',
            DEAD: 'dead'}


def main():
    logging.basicConfig(level=logging.NOTSET)
    log = logging.getLogger(__name__)

    log.info('Starting up master bot server.')

    master = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    master.setblocking(0)

    master_addr = ('localhost', 13000)
    master.bind(master_addr)
    log.debug('Server address set to: {}'.format(master_addr))

    master.listen(5)
    log.info('Server is listening for bots to connect.')

    timeout = 5
    last_time = time.time()
    inputs = [master]
    outputs = []

    try:
        while True:
            read, write, err = select.select(inputs, outputs, inputs, 1.0)

            # Reading from Sockets
            for s in read:
                if s is master:
                    log.debug('Running master block')
                    bot, bot_addr = s.accept()
                    log.debug('Rec from {}'.format(bot_addr))
                    bot.close()

            # Writing to sockets
            for s in write:
                log.debug('Running write block')

            # Handling exceptions from sockets
            for s in err:
                log.error("Exceptional error occurred for {}".format(
                    s.getpeername()
                ))
                if s in inputs:
                    inputs.remove(s)
                if s in outputs:
                    outputs.remove(s)
                s.close()

            if time.time() - last_time > timeout:
                log.debug('This could be a heartbeat.')
                last_time = time.time()

    except (KeyboardInterrupt, SystemExit):
        log.error('Server was terminated, Cleaning up.')
    finally:
        pass


if __name__ == '__main__':
    main()
