from mininet.net import Mininet
from mininet.topo import Topo
from mininet.topo import LinearTopo
from mininet.node import CPULimitedHost, RemoteController
from mininet.link import TCLink
import time


class singleSwitch(Topo):
    '''
    Define the topology shape with this subclass where n hosts are connected
    to 1 switch. Where each host is only allowed at most 0.5/n total cpu time
    a max bandwidth of 10mbs and a delay of 1ms
    '''

    def build(self, n=2, lossy=True):
        switch = self.addSwitch('s1')
        for h in range(n):
            host = self.addHost('h%s' % (h + 1), cpu=.5 / n)

            bw = 10
            delay = '1ms'
            htb = True
            if lossy:
                loss = 1

            self.addLink(host, switch, bw=bw, delay=delay,
                         loss=loss, use_htb=htb)


def dos_test(net):
    '''
    Use the passed in network handler to run a DDOS test on host 1 from
    hosts 3 through n size of the network. Host 2 will act as a legitimate user
    and run a performance test between itself and host 1. Hosts 3 - n will
    flood the network with ping packets to host 1
    '''
    for h in range(len(net.hosts)):
        if h > 1:
            print 'Starting basic DDOS with host {}'.format(net.hosts[h].name)
            net.hosts[h].sendCmd('hping3 -q -i u1 {}'.format(net.hosts[0].IP()))

    time.sleep(5)
    print 'Starting bandwidth test'
    net.iperf(hosts=[net.hosts[0], net.hosts[1]], l4Type='UDP')

    for h in range(len(net.hosts)):
        if h >= 2:
            net.hosts[h].sendInt()
            net.hosts[h].waitOutput(verbose=True)


# def one_test(net, start):
#     if start != 1:
#         h1, h2, h3 = [net.hosts[s] for s in range(len(net.hosts))]
#         for i in range(start, 0, int(-0.1 * start)):
#             print 'Generating packet noise with delay of {}us'.format(i)
#             h3.sendCmd('hping3 -q -i u{} {}'.format(i, h2.IP()))
#             time.sleep(10)
#             print 'Beginning test'
#             net.iperf(hosts=[h1, h2], l4Type='UDP')
#
#             h3.sendInt()
#             h3.waitOutput(verbose=True)
#         one_test(net, int(0.1 * start))
#
#
# def brute_force_test(net):
#     h1, h2, h3 = [net.hosts[s] for s in range(len(net.hosts))]
#     print 'Generating packet noise'
#     h3.sendCmd('hping3 -i u1 {}'.format(h2.IP()))
#     time.sleep(5)
#     print 'Beginning test'
#     net.iperf(hosts=[h1, h2], l4Type='UDP')
#
#     h3.sendInt()
#     h3.waitOutput(verbose=True)


def setupTest(lossy=True):
    '''
    Create a network using a single switch topology a specific external
    remote controller and run a performance test to setup and benchmark
    the workspace.
    '''
    # topo = singleSwitch(n=3, lossy=lossy)
    topo = LinearTopo(n=1, k=3)
    controller = RemoteController('c0', ip='10.0.2.15', port=6633)
    net = Mininet(topo=topo,
                  host=CPULimitedHost, link=TCLink,
                  autoStaticArp=True, controller=controller)
    net.start()
    # h1, h2, h3 = [net.hosts[s] for s in range(len(net.hosts))]
    # print 'Testing bandwidth between h1 and h2'
    # net.iperf(hosts=[net.hosts[0], net.hosts[1]])
    # dos_test(net)


if __name__ == '__main__':
    setupTest()
