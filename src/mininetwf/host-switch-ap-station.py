#!/usr/bin/python

from mininet.node import OVSKernelSwitch
from mininet.log import setLogLevel, info
from mn_wifi.net import Mininet_wifi
from mn_wifi.cli import CLI
from mininet.node import RemoteController


def myNetwork():

    net = Mininet_wifi()

    info( '*** Adding controller\n' )
    c0 = RemoteController('c0', ip='127.0.0.1', port=6653, protocols='OpenFlow13')
    net.addController(c0)
    info( '*** Add switches/APs\n')
    ap1 = net.addAccessPoint('ap1')
    s1 = net.addSwitch('s1', cls=OVSKernelSwitch)
    s2 = net.addSwitch('s2', cls=OVSKernelSwitch)

    info( '*** Add hosts/stations\n')
    h1 = net.addHost('h1', ip='10.0.10.1')
    h2 = net.addHost('h2', ip='10.0.10.2')

    sta1 = net.addStation('sta1', ip='10.0.10.3')

    info("*** Configuring Propagation Model\n")
    net.setPropagationModel(model="logDistance", exp=3)

    info("*** Configuring wifi nodes\n")
    net.configureWifiNodes()

    info( '*** Add links\n')
    net.addLink(s1, s2, 1, 1)
    net.addLink(s1, h1, 2, 1)
    net.addLink(s2, h2, 2, 1)
    net.addLink(s1, ap1, 3)
    net.addLink(sta1, ap1)

    info( '*** Building network\n' )
    net.build()

    net.addNAT().configDefault()

    info( '*** Starting network\n')
    c0.start()
    s1.start([c0])
    s2.start([c0])
    ap1.start([c0])

    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel( 'info' )
    myNetwork()

