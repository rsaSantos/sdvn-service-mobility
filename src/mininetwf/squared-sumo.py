#!/usr/bin/env python

"""Sample file for VANET

***Requirements***:
Kernel version: 5.8+ (due to the 802.11p support)
sumo 1.5.0 or higher
sumo-gui

Please consider reading https://mininet-wifi.github.io/80211p/ for 802.11p support
"""

from mininet.node import OVSKernelSwitch, RemoteController
from mininet.log import setLogLevel, info
from mn_wifi.cli import CLI
from mn_wifi.net import Mininet_wifi
from mn_wifi.sumo.runner import sumo
from mn_wifi.link import wmediumd, ITSLink
from mn_wifi.wmediumdConnector import interference
from mn_wifi.node import OVSAP


def topology():

    "Create a network."
    net = Mininet_wifi(link=wmediumd, wmediumd_mode=interference)

    info( '*** Adding controller\n' )
    c0 = RemoteController('c0', ip='127.0.0.1', port=6653, protocols='OpenFlow13')
    net.addController(c0)

    info("*** Creating nodes\n")
    for id in range(0, 2):
        net.addCar('car%s' % (id+1), wlans=2, encrypt=['wpa2', ''])

    info( '*** Add APs\n')
    kwargs = {'ssid': 'vanet-ssid', 'mode': 'g', 'passwd': '123456789a',
              'encrypt': 'wpa2', 'failMode': 'standalone', 'datapath': 'user'}
    e1 = net.addAccessPoint('e1', mac='00:00:00:11:00:01', channel='1',
                            position='0,0,0', **kwargs, cls=OVSAP)
    e2 = net.addAccessPoint('e2', mac='00:00:00:11:00:02', channel='6',
                            position='1500,-500,0', **kwargs, cls=OVSAP)
    
    info( '*** Add switches\n')
    s1 = net.addSwitch('s1', cls=OVSKernelSwitch)
    s2 = net.addSwitch('s2', cls=OVSKernelSwitch)

    info( '*** Add hosts\n')
    h1 = net.addHost('h1', ip='10.0.10.1', mac='10:00:00:00:10:01')
    h2 = net.addHost('h2', ip='10.0.10.2', mac='10:00:00:00:10:02')

    info("*** Configuring Propagation Model\n")
    net.setPropagationModel(model="logDistance", exp=2.8)

    info("*** Configuring nodes\n")
    net.configureNodes()

    info( '*** Add links\n')
    net.addLink(s1, s2, 1, 1)
    net.addLink(s1, h1, 2, 1)
    net.addLink(s2, h2, 2, 1)
    net.addLink(s1, e1, 3)
    net.addLink(s2, e2, 3)

    for car in net.cars:
        net.addLink(car, intf=car.wintfs[1].name,
                    cls=ITSLink, band=20, channel=181)

    # exec_order: Tells TraCI to give the current
    # client the given position in the execution order.
    # We may have to change it from 0 to 1 if we want to
    # load/reload the current simulation from a 2nd client
    net.useExternalProgram(program=sumo, port=8813,
                           config_file='/home/rubensas/UM/Msc-Dissertation/src/sumo/square/square.sumocfg',
                           extra_params=["--delay 250"],
                           clients=1, exec_order=0)

    info("*** Starting network\n")
    net.build()

    # net.addNAT(ip='10.0.0.50', mac='10:00:00:00:00:50').configDefault()

    c0.start()
    s1.start([c0])
    s2.start([c0])
    e1.start([c0])
    e2.start([c0])

    for enb in net.aps:
        enb.start([])

    for id, car in enumerate(net.cars):
        car.setIP('10.0.10.{}/24'.format(id+31),
                  intf='{}'.format(car.wintfs[0].name))
        car.setIP('10.0.10.{}/24'.format(id+31),
                  intf='{}'.format(car.wintfs[1].name))

    # Track the position of the nodes
    nodes = net.cars + net.aps
    net.telemetry(nodes=nodes, data_type='position',
                  min_x=-2000, min_y=-2000,
                  max_x=2000, max_y=2000)

    info("*** Running CLI\n")
    CLI(net)

    info("*** Stopping network\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology()