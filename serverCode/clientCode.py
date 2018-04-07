import logging
import socket
import random
import time
# from Queue import Queue


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
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger(__name__)

    log.info('Starting up Client.')

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    server_addr = ('localhost', 11000)

    client.connect(server_addr)

    start_time = time.time()

    for i in range(2048):
        lhs = random.randint(0, 1024)
        rhs = random.randint(0, 1024)
        operand_select = random.randint(1, 4)

        if operand_select == 1:
            answer = lhs + rhs
            operand = '+'
        elif operand_select == 2:
            answer = lhs - rhs
            operand = '-'
        elif operand_select == 3:
            answer = lhs * rhs
            operand = '*'
        else:
            if rhs == 0:
                lhs, rhs = rhs, lhs
            answer = lhs / rhs
            operand = '/'

        message = '{} {} {}'.format(lhs, operand, rhs)

        total_sent = 0
        msglen = len(message)
        while total_sent < msglen:
            sent = client.send(message[total_sent:])
            if sent == 0:
                break
            else:
                total_sent += sent
        if sent == 0:
            break
        buffer = client.recv(1024)
        server_answer = buffer.strip()

        if server_answer != str(answer):
            log.error('Received bad answer:')
            log.error('LHS: {}, RHS: {}, Operand: {}, '
                      'Expected: {}, Given: {}'.format(
                          lhs,
                          rhs,
                          operand,
                          answer,
                          server_answer
                      ))
            break
        else:
            log.debug('Expected answer given, continuing.')
    log.info('Program Completed, Wrapping up.')
    log.info('Program Completed, in {} seconds'.format(
        time.time() - start_time))
    client.close()


if __name__ == '__main__':
    pass
    # main()
