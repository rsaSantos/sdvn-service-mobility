from scenarios.Scenario import Scenario

import time
import os
import threading

class POCReplication(Scenario):
    clusterName = 'poc-replication'

    appName = 'mysimpleserver'
    tag = 'latest'
    serviceType = 'NodePort'
    containerPort = 8080
    targetPort = 8080
    nodePort = 30001

    def __init__(self, kindCfg, mininetCfg, sdnController):
        super().__init__(kindCfg, mininetCfg, sdnController, force_restart=False)

    def positionTracker(self, car):
        car_position_path = f'position-{car}-mn-telemetry.txt'
        while True:
            if os.path.exists(car_position_path):
                with open(car_position_path, 'rb') as f:
                    try:
                        f.seek(-2, os.SEEK_END)
                        while f.read(1) != b'\n':
                            f.seek(-2, os.SEEK_CUR)
                    except OSError:
                        f.seek(0)
                    coordinates = f.readline().decode()
                    x, y = coordinates.strip().split(',')
                    x = float(x)
                    y = float(y)
                
                (ap, node, migrate) = Scenario.apAndNodeInRange(self, x, y, 'west')
                if ap is not None and node is not None:
                    # print(f"Car {car} is in range of AP{ap} on Worker{node}")
                    worker_name = self.clusterName + '-worker' + (node if node != '1' else '')
                    if not Scenario.isDeployedAt(self, worker_name, self.appName):
                        # Reactive deployment
                        print("Reactive deployment detected! Fix this or implement the migration.")
                    elif migrate:
                        (nextAp, nextNode) = Scenario.nextApAndNode(self, x, y, 'west')
                        if nextAp is not None and nextNode is not None and nextNode != node:
                            # print(f"Car {car} is moving to AP{nextAp} on Worker{nextNode}")
                            deploymentName = self.appName + '-deployment-' + nextNode
                            nextNodeName = self.clusterName + '-worker' + (nextNode if nextNode != '1' else '')
                            if Scenario.createDeployment(self, self.appName, deploymentName, self.containerPort, 1, nextNodeName, self.tag) == 0:
                                print(f"App {self.appName} deployed on {nextNodeName}...")
                                for nextAssociateAp in Scenario.getAPsAssociatedWithWorker(self, nextNode):
                                    Scenario.redirectTrafficSDN(self, nextNodeName, nextAssociateAp)
                                    print(f"Traffic redirected to Worker{nextNode} at AP{nextAp}")
            time.sleep(1)

    def run(self):
        # Setup kind cluster
        self.clusterName = Scenario.startKindController(self)
        print(f"Cluster name: {self.clusterName}")
        #
        Scenario.createService(self, self.appName, self.appName + '-service', self.serviceType, self.containerPort, self.targetPort, self.nodePort, self.tag)
        #
        firstDeploymentNodeName = self.clusterName + '-worker'
        deploymentName = self.appName + '-deployment-1'
        Scenario.createDeployment(self, self.appName, deploymentName, self.containerPort, 1, firstDeploymentNodeName, self.tag)
        #
        Scenario.launchSDNController(self)

        positionTrackerThread = threading.Thread(target=self.positionTracker, args=('car1',), daemon=True)
        positionTrackerThread.start()

        time.sleep(3) 

        Scenario.startMininetController(self)
    
        print("Exiting...")
