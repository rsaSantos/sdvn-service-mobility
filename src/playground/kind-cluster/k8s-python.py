from kubernetes import client, config

def create_deployment_object():
    # Configureate Pod template container
    container = client.V1Container(
        name="kubeserver",
        image="kubeserver:latest",
        image_pull_policy="IfNotPresent",
        ports=[client.V1ContainerPort(container_port=8080)],
        env=[client.V1EnvVar(name="POD_IP", value_from=client.V1EnvVarSource(field_ref=client.V1ObjectFieldSelector(field_path="status.podIP")))]
    )
    
    # Create and configurate a spec section
    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": "test-python-server"}),
        spec=client.V1PodSpec(containers=[container], node_name="kind-worker"))
    
    # Create the specification of deployment
    spec = client.V1DeploymentSpec(
        replicas=1,
        template=template,
        selector={"matchLabels": {"app": "test-python-server"}})
    
    # Instantiate the deployment object
    deployment = client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(name="test-python-server-deployment"),
        spec=spec)

    return deployment

def create_deployment(api_instance, deployment):
    # Create deployment
    api_response = api_instance.create_namespaced_deployment(
        body=deployment,
        namespace="default")
    print("Deployment created. status='%s'" % str(api_response.status))

def delete_deployment(api_instance):
    # Delete deployment
    api_response = api_instance.delete_namespaced_deployment(
        name="test-python-server-deployment",
        namespace="default",
        body=client.V1DeleteOptions(
            propagation_policy='Foreground',
            grace_period_seconds=5))
    print("Deployment deleted. status='%s'" % str(api_response.status))


def main():
    # Configs can be set in Configuration class directly or using helper
    # utility. If no argument provided, the config will be loaded from
    # default location.
    config.load_kube_config()
    apps_v1 = client.AppsV1Api()

    # Uncomment the following lines to enable debug logging
    # c = client.Configuration()
    # c.debug = True
    # apps_v1 = client.AppsV1Api(api_client=client.ApiClient(configuration=c))

    # Create a deployment object with client-python API. The deployment we
    # created is same as the `nginx-deployment.yaml` in the /examples folder.
    deployment = create_deployment_object()

    create_deployment(apps_v1, deployment)
    # delete_deployment(apps_v1)


if __name__ == '__main__':
    main()
