# Author: Rúben Santos
# Date  : 30/03/2024
#
import yaml
import json
import subprocess
from kubernetes import client, config
from kubernetes.client.rest import ApiException

class KubernetesController:
    
    def __init__(self, configPath, debug=False):
        self.configPath = configPath
        
        # Load configuration from file (YAML)
        with open(self.configPath, 'r') as file:
            self.config = yaml.safe_load(file)
        
        # Get attributes
        self.clusterName = 'kind' if 'name' not in self.config else self.config['name']
        self.numNodes = len(self.config['nodes'])

        # Save deployment objects. Use dictionary of { nodeName -> {deploymentName -> deploymentObject} }
        self.deployments = {}

    def __runCommandReturnOutput(self, commands, debug=False):
        return subprocess.run(commands, stdout=subprocess.PIPE).stdout.decode('utf-8')

    def deleteDeployment(self, deploymentName):
        return self.__runCommandReturnOutput(['kubectl', 'delete', 'deployment', deploymentName])

    def getClusters(self):
        return self.__runCommandReturnOutput(['kind', 'get', 'clusters'])

    def getNodeInfo(self):
        kubectl_output = self.__runCommandReturnOutput(['kubectl', 'get', 'nodes', '-o', 'json'])
        nodes_info = json.loads(kubectl_output)['items']

        node_info_list = {}
        for node in nodes_info:
            name = node['metadata']['name']
            if 'control-plane' in name:
                continue
            ip = node['status']['addresses'][0]['address']
            node_info_list[name] = ip

        return node_info_list
    
    def clearPreviousDeployments(self):
        print("Clearing previous deployments...")
        deployments_command_output = self.__runCommandReturnOutput(['kubectl', 'get', 'deployments', '-o', 'json'])
        deployment_objects = json.loads(deployments_command_output)['items']
        for deployment in deployment_objects:
            deployment_name = deployment['metadata']['name']
            print(f"Deleting deployment {deployment_name}...")
            self.deleteDeployment(deployment_name)

    def startCluster(self, force_restart=False):
        # Check if cluster exists with same name...
        if self.clusterName + '\n' in self.getClusters():
            print(f"Cluster with name {self.clusterName} was already created!")
            if force_restart:
                print(f"Force restarting cluster {self.clusterName}...")
                self.deleteCluster()
            else:
                print(f"Use force_restart=True to restart the cluster.")
                self.clearPreviousDeployments()
                return 1

        return self.__runCommandReturnOutput(['kind', 'create', 'cluster', '--config', str(self.configPath)])
    
    def deleteCluster(self):
        return self.__runCommandReturnOutput(['kind', 'delete', 'cluster', '--name', self.clusterName])

    def loadDockerImages(self, imageName):
        return self.__runCommandReturnOutput(['kind', 'load', 'docker-image', imageName, '--name', self.clusterName])

    def createDeploymentObject(self,
                               containerName,
                               imageName, 
                               containerPort,
                               numReplicas,
                               deploymentName, 
                               nodeName,
                               appName):
        #
        # Create the container
        #
        container = client.V1Container(
            name=containerName,
            image=imageName,
            image_pull_policy="IfNotPresent",
            ports=[client.V1ContainerPort(container_port=containerPort)],
            env=[client.V1EnvVar(name="POD_IP", value_from=client.V1EnvVarSource(field_ref=client.V1ObjectFieldSelector(field_path="status.podIP")))]
        )

        #
        # Create the pod template
        #
        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={"app": appName}),
            spec=client.V1PodSpec(containers=[container], node_name=nodeName)
        )

        #
        # Create the deployment specification
        #
        spec = client.V1DeploymentSpec(
            replicas=numReplicas,
            template=template,
            selector={"matchLabels": {"app": appName}}
        )

        #
        # Create the deployment object
        #
        deployment = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(name=deploymentName),
            spec=spec
        )

        return deployment

    def __saveDeployment(self, deployment):
        nodeName = deployment.spec.template.spec.node_name
        deploymentName = deployment.metadata.name

        if nodeName not in self.deployments:
            self.deployments[nodeName] = {}

        if deploymentName not in self.deployments[nodeName]:
            self.deployments[nodeName][deploymentName] = deployment
        else:
            print(f"Deployment {deploymentName} already exists in node {nodeName}!")

    def createDeployment(self, deployment):
        try:
            config.load_kube_config()
            apps_v1 = client.AppsV1Api()

            # Check if the deployment exists
            try:
                existing_deployment = apps_v1.read_namespaced_deployment(
                    name=deployment.metadata.name,
                    namespace="default"
                )
                print(f"Deployment {deployment.metadata.name} already exists.")
                return 1
            except ApiException as e:
                if e.status == 404:
                    # Deployment does not exist, create it
                    apps_v1.create_namespaced_deployment(
                        body=deployment,
                        namespace="default"
                    )
                    self.__saveDeployment(deployment)
                    print(f"Deployment {deployment.metadata.name} created!")
                    return 0
                else:
                    # An error occurred while trying to read the deployment
                    print(f"Error checking if deployment exists: {e}")
                    return 2

        except Exception as e:
            print(f"Error creating deployment {deployment.metadata.name}: {e}")
            return 3
    
    def createServiceObject(self, serviceName, serviceType, appName, port, targetPort, nodePort):
        #
        # Create the service specification
        #
        service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(name=serviceName),
            spec=client.V1ServiceSpec(
                selector={"app": appName},
                ports=[client.V1ServicePort(app_protocol="TCP", port=port, target_port=targetPort, node_port=nodePort)],
                type=serviceType,
                external_traffic_policy="Local"
            )
        )

        return service
    
    def createService(self, service):
        try:
            config.load_kube_config()
            v1 = client.CoreV1Api()

            # Check if the service exists
            try:
                existing_service = v1.read_namespaced_service(
                    name=service.metadata.name,
                    namespace="default"
                )
                print(f"Service {service.metadata.name} already exists.")
                return 1
            except ApiException as e:
                if e.status == 404:
                    # Service does not exist, create it
                    v1.create_namespaced_service(
                        body=service,
                        namespace="default"
                    )
                    print(f"Service {service.metadata.name} created!")
                    return 0
                else:
                    # An error occurred while trying to read the service
                    print(f"Error checking if service exists: {e}")
                    return 2

        except Exception as e:
            print(f"Error creating service {service.metadata.name}: {e}")
            return 3
