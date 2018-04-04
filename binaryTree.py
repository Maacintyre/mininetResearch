from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import CPULimitedHost, RemoteController
from mininet.link import TCLink
import logging

logging.basicConfig(level=logging.NOTSET)
log = logging.getLogger(__name__)


class binaryTree(Topo):

    def build(self, d=1, bw=10, delay='1ms', htb=True, lossy=True):
        log.info('Building network with depth of {}'.format(d))
        self.bw = bw
        self.delay = delay
        self.htb = htb
        self.lossy = lossy

        for i in range(d):
            log.debug('Iteration {} of {}'.format(i, d))
            if i == 0:
                log.debug('Initializing host_count.')
                self.host_count = 1
                if d == 1:
                    log.debug('Depth 1 exiting loop.')
                    break
            else:
                log.debug('Doubling host count.')
                self.host_count *= 2
        self.host_number = 2

        log.info('Creating Server.')
        server = self.addHost('h1', cpu=.5 / self.host_count,
                              mac='00:00:00:00:00:01')
        log.info('Creating Server Switch')
        switch = self.addSwitch('s1')
        log.info('Linking Server to Switch.')
        self.addLink(server, switch, bw=self.bw, delay=self.delay,
                     loss=self.lossy, use_htb=self.htb)
        log.info('Adding Tree to hub.')
        self.add_links(d, switch)

    def add_links(self, depth, last_switch, new_number=2):
        if depth == 1:
            host = self.addHost('h%s' % self.host_number,
                                cpu=.5 / self.host_count)
            self.host_number += 1
            self.addLink(host, last_switch, bw=self.bw, delay=self.delay,
                         loss=self.lossy, use_htb=self.htb)
        else:
            for i in range(2):
                new_switch = self.addSwitch('s%s' % new_number)
                self.addLink(last_switch, new_switch, bw=self.bw,
                             delay=self.delay, loss=self.lossy,
                             use_htb=self.htb)
                self.add_links(depth - 1, new_switch, new_number * 2)
                new_number += 1


def setup():
    log.info('Creating Network Template.')
    topo = binaryTree(d=3)
    log.info('Adding Controller.')
    controller = RemoteController('c0', ip='10.0.2.15', port=6633)
    log.info('Generating Network')
    net = Mininet(topo=topo,
                  host=CPULimitedHost, link=TCLink,
                  autoStaticArp=True, controller=controller)
    log.info('Running Network in Interactive Mode')
    net.interact()


if __name__ == '__main__':
    setup()
