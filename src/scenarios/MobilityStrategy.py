from scenarios.Scenario import Scenario

import threading
import time
import os
import json

class MobilityStrategy(Scenario):

    clusterName = 'mobility-strategy'
    appName = 'mysimpleserver'
    tag = 'latest'
    serviceType = 'NodePort'
    containerPort = 8080
    targetPort = 8080
    nodePort = 30001

    MAX_DEPLOYMENTS = 3 # Limit by cost!

    STOP_SIMULATION = False

    # Visualization structure: for each time t, store the global latency
    visualization = {}
    # {
    #   t_0: {
    #       global_latency: _,
    #   },
    # }

    # Flows
    flows = []
    # [
    #   {
    #       ap_id: _,
    #       node_id: _
    #   },
    #   ...
    # ]

    # Deployments
    deployments = []
    # [
    #   {
    #       node_id: _,
    #       apps: [
    #           app_name,
    #           ...
    #       ]
    #   },
    #   ...
    # ]

    # Vehicle position dictionary and its lock
    vehicleDataLock = threading.Lock()
    vehicleData = {}
    #
    # {
    #   1: {
    #       "position": (x, y),
    #       "direction": (dx, dy),
    #       "associated_ap": 1
    #   },
    #   ...
    # }


    def __init__(self, kindCfg, mininetCfg, sdnController):
        super().__init__(kindCfg, mininetCfg, sdnController, force_restart=False)


    def positionTracker(self, num_cars):
        #
        for i in range(1, num_cars + 1):
            with MobilityStrategy.vehicleDataLock:
                MobilityStrategy.vehicleData[i] = {}
        #
        while not MobilityStrategy.STOP_SIMULATION:
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
                    
                    with MobilityStrategy.vehicleDataLock:
                        previous_position = MobilityStrategy.vehicleData[car_id].get('position', None)
                        if previous_position is None or previous_position != (x, y):
                            if previous_position is not None:
                                dx = x - previous_position[0]
                                dy = y - previous_position[1]
                                MobilityStrategy.vehicleData[car_id]['direction'] = (dx, dy)
                            MobilityStrategy.vehicleData[car_id]['position'] = (x, y)
                            
                            associated_ap = Scenario.getAssociatedAP(self, car_id)
                            if associated_ap is None:
                                associated_ap = Scenario.closestAP(self, x, y)
                            MobilityStrategy.vehicleData[car_id]['associated_ap'] = associated_ap
    
    def getCurrentGlobalLatency(self):
        # For each vehicle, get its associated AP
        # Get the node that serves the AP from the flows
        # Get the node that should serve the AP from the deployments
        # If they are different, increment global latency by factor
        # The factor is the distance between the two nodes...
        global_latency = 0
        with MobilityStrategy.vehicleDataLock:
            for car_id, data in MobilityStrategy.vehicleData.items():
                if 'associated_ap' not in data:
                    continue
                ap_id = data['associated_ap']
                if ap_id is None:
                    continue

                using_node = None
                for flow_data in MobilityStrategy.flows:
                    if flow_data['ap_id'] == ap_id:
                        using_node = flow_data['node_id']
                        break
                
                if using_node is None:
                    using_node = 1
                
                best_node = Scenario.getNodeByAP(self, ap_id)
                if best_node is None:
                    continue

                if best_node != using_node:
                    global_latency += Scenario.getDistanceFactorBetweenNodes(self, ap_id, using_node)
        
        return global_latency

    def updateVisualization(self, i_time):
        visualization_item = {}
        visualization_item['global_latency'] = MobilityStrategy.getCurrentGlobalLatency(self)
        MobilityStrategy.visualization[i_time] = visualization_item

        # Overwrite visualization file as json format pretty
        with open('visualization.json', 'w') as f:
            json.dump(MobilityStrategy.visualization, f, sort_keys=True, indent=4)

    def updateDeploymentsStructure(self):
        updated_deployments = []
        # Populate deployments structure: get from Scenario.deployments
        scenario_deployments = Scenario.getDeployment(self)
        for (worker_name, deployment_list) in scenario_deployments.items():
            node_id = Scenario.convertWorkerNameToId(self, worker_name)
            app_list = []
            for deployment_obj in deployment_list:
                try:
                    deployment_obj = deployment_obj.to_dict()
                    app_name = deployment_obj['spec']['selector']['matchLabels']['app']
                    app_list.append(app_name)
                except Exception as e:
                    print("Error getting app name from deployment object: ", e)

            updated_deployments.append({
                'node_id': node_id,
                'apps': app_list
            })
        
        MobilityStrategy.deployments = updated_deployments

    def existsFlow(self, ap_id, node_id):
        for flow_data in MobilityStrategy.flows:
            if flow_data['ap_id'] == ap_id and flow_data['node_id'] == node_id:
                return True
        return False
    
    def existsDeployment(self, node_id, app_name):
        for deployment in MobilityStrategy.deployments:
            if int(deployment['node_id']) == int(node_id) and app_name in deployment['apps']:
                return True
        return False

    def updateDeploymentsAndFlows(self, nodes_load, new_deployment_and_flow):
        if len(new_deployment_and_flow) == 0:
            return
        
        for n in range(1, Scenario.getNumberOfNodes(self) + 1):
            if n not in nodes_load:
                nodes_load[str(n)] = 0
        
        heaviest_N_nodes = sorted(nodes_load.items(), key=lambda x: x[1], reverse=True)[:self.MAX_DEPLOYMENTS]

        sorted_deployments = sorted(MobilityStrategy.deployments, key=lambda d: nodes_load[str(d['node_id'])])
        sorted_node_ids = [str(deployment['node_id']) for deployment in sorted_deployments]

        to_remove = [] # [node_id]
        to_create = [] # [node_id]

        for node_id in sorted_node_ids:
            if node_id not in heaviest_N_nodes:
                to_remove.append(node_id)

                if len(heaviest_N_nodes) > 0:
                    node_id_load_pair = heaviest_N_nodes.pop(0)
                    to_create.append(node_id_load_pair[0])

        #print(to_create)
        #print(to_remove)

        to_remove = sorted(to_remove, key=lambda d: nodes_load[str(d)])
        to_create = sorted(to_create, key=lambda d: nodes_load[str(d)], reverse=True)

        # Update deployments and flows
        for (node_id, app_name, ap_id) in new_deployment_and_flow:
            if node_id not in to_create and len(to_create) > 0:
                continue

            node_name = Scenario.convertWorkerIdToName(self, self.clusterName, node_id)

            # Create deployment if app is not deployed
            if app_name is not None:
                deployment_name = app_name + '-deployment-' + str(node_id)
                if Scenario.createDeployment(self, app_name, deployment_name, self.containerPort, 1, node_name, self.tag) == 0:
                    print(f"App {app_name} deployed on {node_name}...")
                
                if Scenario.getNumberOfDeployments(self) > MobilityStrategy.MAX_DEPLOYMENTS and len(to_remove) > 0:
                    to_remove_node_id = to_remove.pop(0)
                    if to_remove_node_id != node_id:
                        remove_deployment_name = app_name + '-deployment-' + str(to_remove_node_id)
                        Scenario.deleteDeployment(self, Scenario.convertWorkerIdToName(self, MobilityStrategy.clusterName, to_remove_node_id), remove_deployment_name)

                        aps_of_node = Scenario.getAPsAssociatedWithWorker(self, to_remove_node_id)
                        for ap_id_to_remove in aps_of_node:
                            Scenario.deleteSDNFlow(self, ap_id_to_remove)
            
            # Redirect traffic
            if not MobilityStrategy.existsFlow(self, ap_id, node_id):
                Scenario.redirectTrafficSDN(self, node_name, ap_id)
                flow_data = {
                    'ap_id': ap_id,
                    'node_id': node_id
                }
                MobilityStrategy.flows.append(flow_data)

        MobilityStrategy.updateDeploymentsStructure(self)

    def controller_reactive(self):
        base_flows_installed = False
        MobilityStrategy.updateDeploymentsStructure(self)
        #
        i_time = -1
        while not MobilityStrategy.STOP_SIMULATION:
            time.sleep(1)
            new_deployment_and_flow = [] # [(node_id, app_name, ap_id), ...]
            nodes_load = {} # node_id : load
            with MobilityStrategy.vehicleDataLock:
                with open('vehicle-data.json', 'w') as f:
                    json.dump(MobilityStrategy.vehicleData, f, sort_keys=True, indent=4)
                for car_id, data in MobilityStrategy.vehicleData.items():
                    if 'associated_ap' not in data:
                        continue
                    ap_id = data['associated_ap']
                    if ap_id is None:
                        continue
                    
                    best_node = Scenario.getNodeByAP(self, ap_id)
                    if best_node is None:
                        continue

                    if best_node in nodes_load:
                        nodes_load[best_node] += 1
                    else:
                        nodes_load[best_node] = 1

                    using_node = None
                    for flow_data in MobilityStrategy.flows:
                        if flow_data['ap_id'] == ap_id:
                            using_node = flow_data['node_id']
                            break
                    
                    if using_node is None:
                        using_node = 1 # Bootstrap worker
                    
                    if best_node == using_node:
                        continue
                    
                    x, y = data['position']

                    if 'direction' not in data:
                        continue
                    dx, dy = data['direction']
                    
                    if not Scenario.isLeavingAP(self, x, y, dx, dy, ap_id):
                        deployment_app_name = self.appName
                        if MobilityStrategy.existsDeployment(self, best_node, self.appName):
                            deployment_app_name = None
                        
                        new_deployment_and_flow.append((best_node, deployment_app_name, ap_id))

            if i_time != -1 or len(new_deployment_and_flow) > 0:
                if not base_flows_installed:
                    Scenario.createDefaultMobilitySDNFlows(self)
                    base_flows_installed = True
                i_time += 1
                MobilityStrategy.updateVisualization(self, i_time)
            #
            MobilityStrategy.updateDeploymentsAndFlows(self, nodes_load, new_deployment_and_flow)

    def controller_predictive(self):
        base_flows_installed = False
        MobilityStrategy.updateDeploymentsStructure(self)
        #
        i_time = -1
        while not MobilityStrategy.STOP_SIMULATION:
            #
            # Iterate cars
            #  - check if car is leaving AP
            #    - check next AP in direction
            #    - check if next AP uses different node
            #      - replicate deployment

            time.sleep(1)
            new_deployment_and_flow = [] # [(node_id, app_name, ap_id), ...]
            nodes_load = {} # node_id : load
            with MobilityStrategy.vehicleDataLock:
                with open('vehicle-data.json', 'w') as f:
                    json.dump(MobilityStrategy.vehicleData, f, sort_keys=True, indent=4)
                for car_id, data in MobilityStrategy.vehicleData.items():
                    if 'associated_ap' not in data:
                        continue
                    ap_id = data['associated_ap']

                    best_node = Scenario.getNodeByAP(self, ap_id)
                    if best_node is not None:
                        if best_node in nodes_load:
                            nodes_load[best_node] += 1
                        else:
                            nodes_load[best_node] = 1

                    x, y = data['position']

                    if 'direction' not in data:
                        continue

                    dx, dy = data['direction']
                    if not Scenario.isLeavingAP(self, x, y, dx, dy, ap_id):
                        continue
                    
                    next_ap = Scenario.nextApInDirection(self, x, y, dx, dy, ap_id)
                    if next_ap is None:
                        continue

                    next_node = Scenario.getNodeByAP(self, next_ap)

                    using_node = None
                    for flow_data in MobilityStrategy.flows:
                        if flow_data['ap_id'] == ap_id:
                            using_node = flow_data['node_id']
                            break
                    
                    if using_node is None:
                        using_node = 1 # Bootstrap worker
                    
                    if next_node == using_node:
                        continue

                    deployment_app_name = self.appName
                    if MobilityStrategy.existsDeployment(self, next_node, self.appName):
                        deployment_app_name = None
                    
                    new_deployment_and_flow.append((next_node, deployment_app_name, next_ap))

            if i_time != -1 or len(new_deployment_and_flow) > 0:
                if not base_flows_installed:
                    Scenario.createDefaultMobilitySDNFlows(self)
                    base_flows_installed = True
                i_time += 1
                MobilityStrategy.updateVisualization(self, i_time)
            #
            MobilityStrategy.updateDeploymentsAndFlows(self, nodes_load, new_deployment_and_flow)

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

        # Start position tracker threads
        positionTrackerThread = threading.Thread(target=self.positionTracker, args=(self.numCars,), daemon=True)
        print(f"Starting position tracker thread on thread {positionTrackerThread.name}")
        positionTrackerThread.start()
        
        #controller = threading.Thread(target=self.controller_reactive, daemon=True)
        controller = threading.Thread(target=self.controller_predictive, daemon=True)
        print("Starting controller thread on thread ", controller.name)
        controller.start()

        time.sleep(3)

        Scenario.startMininetController(self)

        print("Joining threads...")
        MobilityStrategy.STOP_SIMULATION = True
        positionTrackerThread.join()
        controller.join()
    
        print("Exiting...")
