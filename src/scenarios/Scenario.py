from kind.kubernetesController import KubernetesController
from mininetwf.mininetController import MininetController

import subprocess
import json
import math
import requests

class Scenario:

    SDN_PAYLOAD = {
            "dpid": 0,
            "cookie": 0,
            "cookie_mask": 0,
            "table_id": 0,
            "idle_timeout": 0,
            "hard_timeout": 0,
            "priority": 0,
            "flags": 0,
            "match": {},
            "actions": []
        }

    def __init__(self, kindCfg, mininetCfg, sdnController, force_restart=False):
        self.kindCfg = kindCfg
        self.mininetCfg = mininetCfg
        self.sdnController = sdnController
        self.force_restart = force_restart

        with open(mininetCfg, 'r') as file:
            print(f"Using config file: {mininetCfg}")
            mnCfg = json.load(file)
            self.accessPoints = mnCfg['aps']
            self.numCars = mnCfg['cars']['count']

        self.kindController = None
        self.dockerImages = [] # List of docker images loaded
        self.workers = {} # {worker_name: worker_ip}
        self.services = {} # {service_name: service_object}
        self.deployments = {} # {worker_name: [deployment_objects]}
    
    def getNumberOfNodes(self):
        return len(self.workers)

    def getNumberOfAps(self):
        return len(self.accessPoints)

    def getDeployment(self):
        return self.deployments
    
    def getNumberOfDeployments(self):
        return len(self.deployments)

    def deleteDeployment(self, worker_name, deployment_name):
        self.kindController.deleteDeployment(deployment_name)
        del self.deployments[worker_name]

    def getBootstrap_worker_ip(self):
        return self.workers[self.kindController.clusterName + '-worker']
    
    def convertWorkerIdToName(self, cluster_name, worker_id):
        return cluster_name + '-worker' + (worker_id if worker_id != '1' else '')

    def convertWorkerNameToId(self, worker_name):
        # Get the last character of the worker name
        last_char = worker_name[-1]
        # If the last character is a digit, return it
        if last_char.isdigit():
            return int(last_char)
        else:
            return 1

    def startKindController(self) -> KubernetesController:
        # Start the kind controller and get the workers
        self.kindController = KubernetesController(self.kindCfg)
        self.kindController.startCluster(self.force_restart)

        self.workers = self.kindController.getNodeInfo()

        return self.kindController.clusterName
    
    def createService(self, appName, serviceName, serviceType, port, targetPort, nodePort, tag='latest'):
        #
        imageName = f'{appName}:{tag}'
        self.kindController.loadDockerImages(imageName)
        #
        serviceObject = self.kindController.createServiceObject(serviceName, 
                                                       serviceType, 
                                                       appName, 
                                                       port, 
                                                       targetPort, 
                                                       nodePort)
        
        serviceCreationResult = self.kindController.createService(serviceObject)
        if serviceCreationResult == 0:
            self.dockerImages.append(imageName)
            self.services[serviceName] = serviceObject
        
        elif serviceCreationResult == 1:
            # Service already exists but it might be from previous runs
            # Check if the service is from previous runs
            for service in self.services.values():
                if service.metadata.name == serviceName:
                    # Service exists
                    return serviceCreationResult
            
            # Service does not exist, it is from previous runs
            self.services[serviceName] = serviceObject
            self.dockerImages.append(imageName)

        return serviceCreationResult
    
    def createDeployment(self, appName, deploymentName, containerPort, numReplicas, nodeName, tag='latest'):
        deploymentObject = self.kindController.createDeploymentObject(appName, 
                                                             f'{appName}:{tag}', 
                                                             containerPort, 
                                                             numReplicas, 
                                                             deploymentName, 
                                                             nodeName, 
                                                             appName)

        deploymentResult = self.kindController.createDeployment(deploymentObject)
        if deploymentResult == 0:
            # Fresh deployment
            workerDeployments = self.deployments.get(nodeName, [])
            workerDeployments.append(deploymentObject)
            self.deployments[nodeName] = workerDeployments

        elif deploymentResult == 1:
            # Deployment already exists but it might be from previous runs
            # Check if the deployment is from previous runs
            workerDeployments = self.deployments.get(nodeName, [])
            for deployment in workerDeployments:
                if deployment.metadata.name == deploymentName:
                    # Deployment exists
                    return deploymentResult
            
            # Deployment does not exist, it is from previous runs
            workerDeployments.append(deploymentObject)
            self.deployments[nodeName] = workerDeployments

        return deploymentResult

    def launchSDNController(self):
        # Launch a new terminal and run the controller with 'ryu-manager'
        command = f'ryu-manager {self.sdnController}'
        print(f"Launching SDN controller with command: {command}")
        subprocess.Popen(f"konsole -e {command} && exit", shell=True)

    def startMininetController(self):
        # To support the applications launched in the mininet network...
        # ...create the config file that contains the bootstrap worker IP
        bootstrap_worker_ip = self.getBootstrap_worker_ip()
        configPath = 'services/client/client.ini'
        with open(configPath, 'w') as file:
            file.write(f'[DEFAULT]\n')
            file.write(f'bootstrap_worker_ip = {bootstrap_worker_ip}\n')

        mininetController = MininetController(self.mininetCfg)
        mininetController.startNetwork()

        return mininetController
    
    def getAssociatedAP(self, car_id):
        #
        car_mac = '02:00:00:00:%02x:00' % (car_id)

        # Run the iw command for each AP until we get the car's MAC address
        for ap in self.accessPoints:
            # iw dev ap3-wlan1 station dump
            result = subprocess.run(["iw", "dev", f"ap{ap['id']}-wlan1", "station", "dump"], capture_output=True, text=True)
            if result.returncode != 0:
                continue
    
            if car_mac in result.stdout:
                return ap['id']
        
        return None
    
    def closestAP(self, x, y):
        carPos = [x, y]
        closestAp = None
        minDistance = None
        for ap in self.accessPoints:
            apPos = ap['position'].split(',')[0:2]
            apPos = [float(i) for i in apPos]
            distance = math.dist(carPos, apPos)
            if minDistance is None:
                minDistance = distance

            if distance <= minDistance:
                minDistance = distance
                closestAp = ap['id']

        return closestAp

    def getNodeByAP(self, apID):
        if apID is None:
            return None
        for ap in self.accessPoints:
            if ap['id'] == apID:
                return ap['kindNode']
        return None

    def isAPInRange(self, x, y, ap_id, range=300):
        carPos = [x, y]
        for ap in self.accessPoints:
            if ap['id'] == ap_id:
                apPos = ap['position'].split(',')[0:2]
                apPos = [float(i) for i in apPos]
                distance = math.dist(carPos, apPos)
                return distance <= range
        return False

    def apAndNodeInRange(self, x, y, direction, range=300):
        carPos = [x, y]
        for ap in self.accessPoints:
            apPos = ap['position'].split(',')[0:2]
            apPos = [float(i) for i in apPos]
            distance = math.dist(carPos, apPos)
            if distance <= range:
                migrate = self.isCarPastAP(carPos, apPos, direction)
                return (ap['id'], ap['kindNode'], migrate)
        return (None, None, False)
    
    def isDeployedAt(self, workerName, appName):
        for deployment in self.deployments.get(workerName, []):
            if deployment.spec.selector['matchLabels']['app'] == appName:
                return True
        return False

    # Check if the car has passed the AP if it is moving to certain direction
    def isCarPastAP(self, carPos, apPos, direction):
        return not self.checkDirection(carPos, apPos, direction)

    # Check if the source is in the direction of the destination, assuming the source moves in the direction
    def checkDirection(self, source, destination, direction):
        if direction == 'north':
            return source[1] < destination[1]
        elif direction == 'south':
            return source[1] > destination[1]
        elif direction == 'west':
            return source[0] > destination[0]
        elif direction == 'east':
            return source[0] < destination[0]
        else:
            return False

    def nextApAndNode(self, x, y, direction, range=300):
        carPos = [x, y]
        nextAp = None
        nextNode = None
        minDistance = None
        for ap in self.accessPoints:
            apPos = ap['position'].split(',')[0:2]
            apPos = [float(i) for i in apPos]
            distance = math.dist(carPos, apPos)
            if distance > range or self.checkDirection(carPos, apPos, direction):
                if minDistance is None:
                    minDistance = distance

                if distance <= minDistance:
                    minDistance = distance
                    nextAp = ap['id']
                    nextNode = ap['kindNode']

        return (nextAp, nextNode)
    
    def distanceInRange(self, x, y, dx, dy, ap_id, range=300):
        if ap_id is None:
            return 0

        carPos = [x, y]
        
        apPos = None
        for ap in self.accessPoints:
            if int(ap['id']) == int(ap_id):
                apPos = ap['position'].split(',')[0:2]
                apPos = [float(i) for i in apPos]
                break

        if apPos is None:
            print("apPos is null")
            return 0

        distance_iter = math.sqrt(dx**2 + dy**2)
        if distance_iter == 0:
            return range - math.dist(carPos, apPos)

        distance = 0
        theoreticalPos = carPos[:]
        while math.dist(theoreticalPos, apPos) <= range:
            theoreticalPos[0] += dx
            theoreticalPos[1] += dy
            distance += distance_iter
        
        return distance
    
    def isLeavingAP(self, x, y, dx, dy, ap_id, range=300, threshold=0.20):
        # Check if the car at position x,y and moving in direction dx,dy is leaving the AP
        distance = self.distanceInRange(x, y, dx, dy, ap_id, range)
        if distance == 0:
            print(f"Error calculating distance in isLeavingAP function for AP {ap_id}")
            return False

        return distance <= threshold * range

    def nextApInDirection(self, x, y, dx, dy, current_ap_id, range=300):
        # Get the theoretical position of the car after
        # moving in the direction dx,dy and reaching the range
        carPos = [x, y]
        theoreticalPos = carPos[:]
        while math.dist(theoreticalPos, carPos) <= range:
            theoreticalPos[0] += dx
            theoreticalPos[1] += dy
        
        # Find the closest AP to the theoretical position
        # Exclude the current AP
        closestAp = None
        minDistance = None
        for ap in self.accessPoints:
            if ap['id'] == current_ap_id:
                continue

            apPos = ap['position'].split(',')[0:2]
            apPos = [float(i) for i in apPos]
            distance = math.dist(theoreticalPos, apPos)
            if minDistance is None:
                minDistance = distance

            if distance <= minDistance:
                minDistance = distance
                closestAp = ap['id']
        
        return closestAp
    
    def getAPsAssociatedWithWorker(self, workerID):
        aps = []
        for ap in self.accessPoints:
            if int(ap['kindNode']) == int(workerID):
                aps.append(int(ap['id']))
        return aps
    
    def getDistanceFactorBetweenNodes(self, ap1, node2):
        # The car is using node1 via ap1, but it should be using node2
        # Get the ap_id of the closest AP that uses node2
        # Return the different between the ap's
        aps_list = self.getAPsAssociatedWithWorker(node2)
        if len(aps_list) == 0:
            print(f"No APs associated with worker {node2}")
            return 0
        
        ap2_id = aps_list[0]
        min_distance = None
        for ap_id in aps_list:
            for ap in self.accessPoints:
                if ap['id'] == ap_id:
                    apPos = ap['position'].split(',')[0:2]
                    apPos = [float(i) for i in apPos]
                    distance = math.dist(apPos, [0, 0])
                    if min_distance is None:
                        min_distance = distance

                    if distance <= min_distance:
                        min_distance = distance
                        ap2_id = ap_id
        
        return abs(int(ap1) - ap2_id)

    def createDefaultLoadBalancingSDNFlows(self):
        for ap in self.accessPoints:
            node = ap["kindNode"]
            if node == '1':
                continue
            nodeName = self.clusterName + '-worker' + (node if node != '1' else '')

            self.redirectTrafficSDN(nodeName, ap["id"])
    
    def createDefaultMobilitySDNFlows(self):
        for ap in self.accessPoints:
            nodeName = self.clusterName + '-worker'
            self.redirectTrafficSDN(nodeName, ap["id"])

    def getCarIPFromID(self, car_id):
        return f'10.0.0.{car_id}'

    def installFlowForVehicle(self, car_id, ap_id, worker_name):
        car_ip = self.getCarIPFromID(car_id)
        worker_ip = self.workers[worker_name]
        dpid = 1152921504606846977 + int(ap_id) - 1
        bootstrap_worker_ip = self.getBootstrap_worker_ip()

        payload_snat = self.SDN_PAYLOAD.copy()
        payload_snat['dpid'] = dpid
        payload_snat['priority'] = 100

        snat_match = {
            "in_port": 1,
            "ipv4_src": car_ip,
            "eth_type": 2048
        }
        payload_snat['match'] = snat_match

        snat_actions = [
            {
                "type": "SET_FIELD",
                "field": "ipv4_dst",
                "value": worker_ip
            },
            {
                "type": "OUTPUT",
                "port": 2
            }
        ]
        payload_snat['actions'] = snat_actions

        response = requests.post('http://localhost:8080/stats/flowentry/add', json=payload_snat)
        if response.status_code != 200:
            print(f"Error sending the request to the SDN controller: {response.status_code} : {response.text}")
            return
        
        payload_dnat = self.SDN_PAYLOAD.copy()
        payload_dnat['dpid'] = dpid
        payload_dnat['priority'] = 100

        dnat_match = {
            "in_port": 2,
            "ipv4_src": worker_ip,
            "ipv4_dst": car_ip,
            "eth_type": 2048
        }
        payload_dnat['match'] = dnat_match

        dnat_actions = [
            {
                "type": "SET_FIELD",
                "field": "ipv4_src",
                "value": bootstrap_worker_ip
            },
            {
                "type": "OUTPUT",
                "port": 0xfffffffb # FLOOD to ports 1 and 3!
            }
        ]
        payload_dnat['actions'] = dnat_actions

        response = requests.post('http://localhost:8080/stats/flowentry/add', json=payload_dnat)
        if response.status_code != 200:
            print(f"Error sending the request to the SDN controller: {response.status_code} : {response.text}")
            return
        
        print(f"Flow installed for car {car_id} at AP{ap_id} on Worker{worker_name}...")

    def redirectTrafficSDN(self, workerName, nextAp):
        workerIP = self.workers[workerName]
        dpid = 1152921504606846977 + int(nextAp) - 1
        bootstrap_worker_ip = self.getBootstrap_worker_ip()

        payload_snat = self.SDN_PAYLOAD.copy()
        payload_snat['dpid'] = dpid
        payload_snat['priority'] = 10

        snat_match = { 
            "in_port": 1,
            "ipv4_dst": bootstrap_worker_ip,
            "eth_type": 2048
        }
        payload_snat['match'] = snat_match

        snat_actions = [
            {
                "type": "SET_FIELD",
                "field": "ipv4_dst",
                "value": workerIP
            },
            {
                "type": "OUTPUT",
                "port": 2
            }
        ]
        payload_snat['actions'] = snat_actions

        response = requests.post('http://localhost:8080/stats/flowentry/add', json=payload_snat)
        if response.status_code != 200:
            print(f"Error sending the request to the SDN controller: {response.status_code} : {response.text}")
            return


        payload_dnat = self.SDN_PAYLOAD.copy()
        payload_dnat['dpid'] = dpid
        payload_dnat['priority'] = 10

        dnat_match = {
            "in_port": 2,
            "ipv4_src": workerIP,
            "eth_type": 2048
        }
        payload_dnat['match'] = dnat_match

        dnat_actions = [
            {
                "type": "SET_FIELD",
                "field": "ipv4_src",
                "value": bootstrap_worker_ip
            },
            {
                "type": "OUTPUT",
                "port": 0xfffffffb # FLOOD to ports 1 and 3!
            }
        ]
        payload_dnat['actions'] = dnat_actions

        response = requests.post('http://localhost:8080/stats/flowentry/add', json=payload_dnat)
        if response.status_code != 200:
            print(f"Error sending the request to the SDN controller: {response.status_code} : {response.text}")
            return

        print(f"Redirecting traffic from base service IP to worker IP ({workerIP})...")

    def deleteSDNFlow(self, ap_id):
        dpid = 1152921504606846977 + int(ap_id) - 1
        
        delete_payload = self.SDN_PAYLOAD.copy()
        delete_payload['dpid'] = dpid
        delete_payload['priority'] = 10

        dnat_match = {
            "in_port": 2,
            "eth_type": 2048
        }
        delete_payload['match'] = dnat_match

        response = requests.post('http://localhost:8080/stats/flowentry/delete', json=delete_payload)
        if response.status_code != 200:
            print(f"Error sending the request to the SDN controller: {response.status_code} : {response.text}")
            return
        
        print(f"Deleted flow for in_port=2 on ap{ap_id}...")

        delete_payload = self.SDN_PAYLOAD.copy()
        delete_payload['dpid'] = dpid
        delete_payload['priority'] = 10

        dnat_match = {
            "in_port": 1,
            "eth_type": 2048
        }
        delete_payload['match'] = dnat_match

        response = requests.post('http://localhost:8080/stats/flowentry/delete', json=delete_payload)
        if response.status_code != 200:
            print(f"Error sending the request to the SDN controller: {response.status_code} : {response.text}")
            return
        
        print(f"Deleted flow for in_port=1 on ap{ap_id}...")
