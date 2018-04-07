import socket
import select
import logging
import argparse
import Queue


def problem_solver(raw_problems):
    problems = raw_problems.strip('\n').split(',')
    answers = ''

    for problem in problems:
        try:
            fields = problem.split(' ')
            lhs = int(fields[0].strip())
            rhs = int(fields[2].strip())
            operand = fields[1].strip()
            if operand == '+' or operand == '-' or operand == '*' \
                    or operand == '/':
                pass
            else:
                raise ValueError
        except (ValueError, IndexError):
            return '1'
        else:
            if operand == '+':
                output = str(lhs + rhs)
            elif operand == '-':
                output = str(lhs - rhs)
            elif operand == '*':
                output = str(lhs * rhs)
            else:
                output = str(lhs / rhs)

            if answers == '':
                answers = output
            else:
                answers += ',{}'.format(output)
    return answers


def main():
    parser = argparse.ArgumentParser(description='Simple adding server to test'
                                     ' DoS mitigation.')
    parser.add_argument('-d',
                        '--debug',
                        help='Set the debug levels at which to record.',
                        required=True,
                        type=str
                        )

    args = parser.parse_args()
    if args.debug == 'info':
        level = logging.INFO
    elif args.debug == 'debug':
        level = logging.DEBUG
    else:
        logging.basicConfig(level=logging.ERROR)
        log = logging.getLogger(__name__)
        log.error('Logger not set correctly. Value: {}'.format(args.debug))
        return

    logging.basicConfig(level=level)
    log = logging.getLogger(__name__)

    log.info("Starting up Server.")

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setblocking(0)
    log.debug("Created Socket.")

    serv_addr = ('localhost', 11000)
    server.bind(serv_addr)
    log.debug("Bound Server Address to {}".format(serv_addr))

    server.listen(5)
    log.info("Server is listening for clients.")

    inputs = [server]
    outputs = []
    socket_to_queue = {}

    try:
        while True:
            read, write, err = select.select(inputs, outputs, inputs)

            for c in read:
                if c is server:
                    client, client_addr = c.accept()
                    log.info('New Connection accepted from: {}'. format(
                        client_addr))
                    client.setblocking(0)
                    inputs.append(client)
                else:
                    buffer = c.recv(1024)
                    if buffer:
                        log.info('Received data:')
                        log.debug('{} from: {}'.format(
                            buffer.strip(),
                            c.getpeername()
                        ))
                        # Do some work
                        message = problem_solver(buffer)
                        socket_to_queue[c] = Queue.Queue()
                        socket_to_queue[c].put(message)
                        outputs.append(c)
                    else:
                        log.error('Connection broke unexpectedly.'
                                  ' Cleaning up.')
                        inputs.remove(c)
                        c.close()

            for c in write:
                try:
                    message = socket_to_queue[c].get_nowait()
                except Queue.Empty:
                    log.error('Queue is mysteriously empty.')
                else:
                    log.info('Sending information.')
                    log.debug('Message is: {}'.format(message.strip()))
                    total_sent = 0
                    msglen = len(message)

                    log.info('Xmitting Data.')
                    while total_sent < msglen:
                        sent = c.send(message[total_sent:])
                        if sent == 0:
                            log.error('Connnection broke unexpectedly. '
                                      'Cleaning up')
                            break
                        else:
                            total_sent += sent
                        log.debug('{} sent of {}'.format(total_sent, msglen))
                log.info('Finished Xmitting.')
                del socket_to_queue[c]
                # inputs.remove(c)
                outputs.remove(c)
                # c.close()

            for c in err:
                log.error('Error in handling {}'.format(c.getpeername()))
                if c in inputs:
                    inputs.remove(c)

                if c in outputs:
                    outputs.remove(c)

                if c in socket_to_queue:
                    del socket_to_queue[c]
                c.close()
                log.error('Cleaned up broken socket.')

    except KeyboardInterrupt:
        log.warning('Server interrupted. Cleaning up.')
        for c in inputs:
            c.close()

        for key, value in socket_to_queue.iteritems():
            del socket_to_queue[key]


if __name__ == '__main__':
    main()
