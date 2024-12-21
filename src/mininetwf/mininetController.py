from mininet.node import RemoteController
from mininet.log import setLogLevel, info
from mn_wifi.cli import CLI
from mn_wifi.net import Mininet_wifi
from mn_wifi.sumo.runner import sumo
from mn_wifi.link import wmediumd
from mn_wifi.wmediumdConnector import interference
from mn_wifi.node import OVSAP

import json

class MininetController:
    
    def __init__(self, configPath):
        print("MininetController object created!")
        setLogLevel('info')
        self.configPath = configPath

        with open(configPath, 'r') as file:
            print(f"Using config file: {configPath}")
            self.config = json.load(file)
        
    def startNetwork(self) -> bool:
        info( '*** Creating network\n' )
        net = Mininet_wifi(link=wmediumd, wmediumd_mode=interference)

        info( '*** Adding controller\n' )
        c1 = RemoteController('c1', ip='127.0.0.1', port=6653, protocols='OpenFlow13')
        net.addController(c1)

        info("*** Creating vehicles\n")
        if 'cars' in self.config and 'count' in self.config['cars']:
            for id in range(0, self.config['cars']['count']):
                mac = '02:00:00:00:%02x:00' % (id+1)
                net.addCar('car%s' % (id+1), ip=f'10.0.0.{id+1}/8', mac=mac)
        else:
            print("Error: Missing 'cars' or 'count' in config file!")
            return False

        info( '*** Add APs\n')
        linkTo = {}
        if 'aps' in self.config:
            for apCfg in self.config['aps']:
                apID = int(apCfg['id'])
                ap = net.addAccessPoint(f"ap{apID}", mac=f'00:00:00:00:00:0{apID}', channel=apCfg['channel'],
                                    position=apCfg['position'], cls=OVSAP)
                
                if 'linkTo' in apCfg:
                    linkTo[apID] = apCfg['linkTo']
        else:
            print("Error: Missing 'aps' in config file!")
            return False
        
        info("*** Configuring Propagation Model\n")
        if 'propagationModel' in self.config:
            model = self.config["propagationModel"]["model"]
            if model == 'logDistance' and "exp" in self.config["propagationModel"]:
                exp = self.config["propagationModel"]["exp"]
                net.setPropagationModel(model=model, exp=exp)
            else:
                print("Error: Unknown propagation model!")
                return False
        else:
            print("Error: Missing 'propagationModel' in config file!")
            return False

        info("*** Configuring nodes\n")
        net.configureWifiNodes()

        info( '*** Add links\n')
        for ap1, ap2 in linkTo.items():
            # Get ap with name 'ap{ap1}' and link it to ap with name 'ap{ap2}'
            net.addLink(net.getNodeByName(f"ap{ap1}"), net.getNodeByName(f"ap{ap2}"))

        if 'sumoConfig' in self.config:
            info( '*** Starting SUMO\n' )
            net.useExternalProgram(program=sumo, port=8813,
                                config_file=self.config['sumoConfig'],
                                extra_params=["--delay 1000"],
                                clients=1, exec_order=0)
        else:
            info( '*** No SUMO config available\n' )

        info( '*** Building network\n' )
        net.build()

        net.addNAT().configDefault()

        info("*** Starting network\n")
        c1.start()
        
        for ap in net.aps:
            ap.start([c1])
        
        if 'telemetry' in self.config and 'enabled' in self.config['telemetry'] and self.config['telemetry']['enabled']:
            info("*** Running Telemetry\n")
            nodes = net.cars + net.aps
            net.telemetry(nodes=nodes, data_type='position',
                min_x=self.config['telemetry']['min_x'], min_y=self.config['telemetry']['min_y'],
                max_x=self.config['telemetry']['max_x'], max_y=self.config['telemetry']['max_y'])
        else:
            info("*** Telemetry is disabled\n")

        info("*** Running CLI\n")
        CLI(net)

        info("*** Stopping network\n")
        net.stop()

        return True
