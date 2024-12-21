from scenarios.Scenario import Scenario

import threading
import time
import os
import json
from datetime import datetime

class LoadBalancing(Scenario):

    LOG_FILE = 'load-balance.log'

    clusterName = 'load-balancing'
    appName = 'mysimpleserver'
    tag = 'latest'
    serviceType = 'NodePort'
    containerPort = 8080
    targetPort = 8080
    nodePort = 30001

    STOP_SIMULATION = False

    # Visualization structure: for each time t, store the load of each node
    visualization = {}
    # {
    #   t_0: {
    #       node_id: load,
    #   },
    # }

    # Vehicle position dictionary and its lock
    vehicleDataLock = threading.Lock()
    vehicleData = {}
    #
    # {
    #   1: {
    #       "position": (x, y),
    #       "direction": (dx, dy),
    #       "associated_ap": 1,
    #       "using_node": 1,
    #       "flows" : [
    #           {
    #               'ap': 1,
    #               'node': 1,
    #           },
    #           ...
    #       ]
    #   },
    # }

    def __init__(self, kindCfg, mininetCfg, sdnController):
        super().__init__(kindCfg, mininetCfg, sdnController, force_restart=False)

    def needToUpdateNode(self, car_id):
        if "using_node" not in LoadBalancing.vehicleData[car_id]:
            return True
        
        # If the ap's in the flows are not in range, update the node
        if 'flows' in LoadBalancing.vehicleData[car_id]:
            x,y = LoadBalancing.vehicleData[car_id]['position']
            for flow in LoadBalancing.vehicleData[car_id]['flows']:
                if Scenario.isAPInRange(self, x, y, flow['ap']):
                    return False

        return True

    def positionTracker(self, num_cars):
        #
        for i in range(1, num_cars + 1):
            with LoadBalancing.vehicleDataLock:
                LoadBalancing.vehicleData[i] = {}
        #
        while not LoadBalancing.STOP_SIMULATION:
            time.sleep(1)
            for car_id in range(1, num_cars + 1):
                car_position_path = f'position-car{i}-mn-telemetry.txt'

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
                    
                    with LoadBalancing.vehicleDataLock:
                        previous_position = LoadBalancing.vehicleData[car_id].get('position', None)
                        if previous_position is None or previous_position != (x, y):
                            if previous_position is not None:
                                dx = x - previous_position[0]
                                dy = y - previous_position[1]
                                LoadBalancing.vehicleData[car_id]['direction'] = (dx, dy)
                            LoadBalancing.vehicleData[car_id]['position'] = (x, y)
                            LoadBalancing.vehicleData[car_id]['associated_ap'] = Scenario.getAssociatedAP(self, car_id)
                            if self.needToUpdateNode(car_id):
                                LoadBalancing.vehicleData[car_id]['using_node'] = Scenario.getNodeByAP(self, LoadBalancing.vehicleData[car_id]['associated_ap'])

    def calculateDistanceInRange(self, car_id):
        # If the car already has a flow for the current ap, return 0
        if 'flows' in LoadBalancing.vehicleData[car_id]:
            for flow in LoadBalancing.vehicleData[car_id]['flows']:
                if flow['ap'] == LoadBalancing.vehicleData[car_id]['associated_ap']:
                    return 0

        # Calculate expected time the car will stay in range of the node
        if 'position' not in LoadBalancing.vehicleData[car_id]:
            return 0
        position = LoadBalancing.vehicleData[car_id]['position']
        x, y = position
        
        if 'direction' not in LoadBalancing.vehicleData[car_id]:
            return 0
        direction = LoadBalancing.vehicleData[car_id]['direction']
        dx, dy = direction
        ap = LoadBalancing.vehicleData[car_id]['associated_ap']

        return Scenario.distanceInRange(self, x, y, dx, dy, ap)

    def controller(self):
        base_flows_installed = False
        i_time = -1
        while not LoadBalancing.STOP_SIMULATION:
            time.sleep(1)
            nodes_load = {} # {node: [vehicle_id,...]}
            with LoadBalancing.vehicleDataLock:
                with open(LoadBalancing.LOG_FILE, "a") as f:
                    f.write(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} : Vehicle data: {LoadBalancing.vehicleData}\n")
                for car_id, data in LoadBalancing.vehicleData.items():
                    if 'using_node' not in data:
                        continue
                    node_id = data['using_node']
                    if node_id is None:
                        continue
                    if node_id not in nodes_load:
                        nodes_load[node_id] = [car_id]
                    else:
                        nodes_load[node_id].append(car_id)
            
            with open(LoadBalancing.LOG_FILE, "a") as f:
                f.write(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} : Nodes load: {nodes_load}\n")
            
            if len(nodes_load) == 0:
                continue

            if not base_flows_installed:
                print("Creating default LB SDN flows...")
                Scenario.createDefaultLoadBalancingSDNFlows(self)
                base_flows_installed = True

            i_time += 1
            visualization_item = {} # {node_id: load}
            for node_id, cars in nodes_load.items():
                visualization_item[node_id] = len(cars)
            LoadBalancing.visualization[i_time] = visualization_item

            # Overwrite the visualization file as json format pretty
            with open('visualization.json', 'w') as f:
                json.dump(LoadBalancing.visualization, f, sort_keys=True, indent=4)

            lighest_node_load = None
            lighest_node_id = None
            heaviest_node = None
            cars_to_move = None
            for node_id, cars in nodes_load.items():
                if lighest_node_load is None:
                    lighest_node_load = len(cars)
                    lighest_node_id = node_id
                
                if heaviest_node is None:
                    heaviest_node = node_id
                    cars_to_move = cars

                if len(cars) < lighest_node_load:
                    lighest_node_load = len(cars)
                    lighest_node_id = node_id

                elif len(cars) > len(cars_to_move):
                    heaviest_node = node_id
                    cars_to_move = cars
            
            with open(LoadBalancing.LOG_FILE, "a") as f:
                f.write(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} : Node {lighest_node_id} is the lighest node with {lighest_node_load} cars\n")
                f.write(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} : Node {heaviest_node} is the heaviest node with {len(cars_to_move)} cars\n")

            if lighest_node_id == heaviest_node:
                continue
            
            # Calculate retention rate of each car (distance they will stay in range of ap)
            retention_dist = {} # {car_id: distance_left}
            for car_id in cars_to_move:
                with LoadBalancing.vehicleDataLock:
                    dist_left = LoadBalancing.calculateDistanceInRange(self, car_id)
                    if dist_left > 0:
                        retention_dist[car_id] = dist_left

            num_cars_to_move = int((len(cars_to_move) + lighest_node_load) / 2) - 1
            if num_cars_to_move <= 0:
                continue
            sorted_cars = sorted(retention_dist.items(), key=lambda x: x[1], reverse=True)
            cars_ready_to_move = [car_id for car_id, _ in sorted_cars[:num_cars_to_move]]

            with open(LoadBalancing.LOG_FILE, "a") as f:
                f.write(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} : Moving {num_cars_to_move} cars from node {heaviest_node} to node {lighest_node_id}\n")

            # Move cars to the lighest node!
            # Install flows
            for car_id in cars_ready_to_move:
                with LoadBalancing.vehicleDataLock:
                    ap = LoadBalancing.vehicleData[car_id]['associated_ap']
                    if ap is None:
                        with open(LoadBalancing.LOG_FILE, "a") as f:
                            f.write(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} : Car {car_id} has no associated ap. Skipping...\n")
                        continue
                    if 'flows' not in LoadBalancing.vehicleData[car_id]:
                        LoadBalancing.vehicleData[car_id]['flows'] = []
                    Scenario.installFlowForVehicle(self, car_id, ap, Scenario.convertWorkerIdToName(self, self.clusterName, lighest_node_id))
                    LoadBalancing.vehicleData[car_id]['flows'].append({'ap': ap, 'node': lighest_node_id})

    def run(self):
        # Add delimiter to log, if it exists
        if os.path.exists(LoadBalancing.LOG_FILE):
            os.remove(LoadBalancing.LOG_FILE)

        # Setup kind cluster
        self.clusterName = Scenario.startKindController(self)
        print(f"Cluster name: {self.clusterName}")
        #
        Scenario.createService(self, self.appName, self.appName + '-service', self.serviceType, self.containerPort, self.targetPort, self.nodePort, self.tag)
        #
        firstDeploymentNodeName = self.clusterName + '-worker'
        deploymentName = self.appName + '-deployment-'
        Scenario.createDeployment(self, self.appName, deploymentName + '1', self.containerPort, 1, firstDeploymentNodeName, self.tag)
        #
        for i in range(2, Scenario.getNumberOfNodes(self) + 1):
            Scenario.createDeployment(self, self.appName, f"{deploymentName}{i}", self.containerPort, 1, firstDeploymentNodeName, self.tag)
        #
        Scenario.launchSDNController(self)

        # Start position tracker threads
        positionTrackerThread = threading.Thread(target=self.positionTracker, args=(self.numCars,), daemon=True)
        print(f"Starting position tracker thread on thread {positionTrackerThread.name}")
        positionTrackerThread.start()
        
        controller = threading.Thread(target=self.controller, daemon=True)
        print("Starting controller thread on thread ", controller.name)
        controller.start()

        time.sleep(3)

        Scenario.startMininetController(self)

        print("Joining threads...")
        LoadBalancing.STOP_SIMULATION = True
        positionTrackerThread.join()
        controller.join()
    
        print("Exiting...")
