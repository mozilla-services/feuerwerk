import os
import progressbar


from kubernetes import client, config
from kubernetes.client.rest import ApiException


def create_deployment_object(number_of_containers, image_name):
    containers = []

    while number_of_containers > 0:
        container = client.V1Container(
            name="feuerwerk%s" % number_of_containers,
            image=image_name,
            image_pull_policy='IfNotPresent',
        )
        containers.append(container)
        number_of_containers = number_of_containers - 1

    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": "loadtest"}),
        spec=client.V1PodSpec(containers=containers),
    )

    # Create the specification of deployment
    spec = client.ExtensionsV1beta1DeploymentSpec(replicas=1, template=template)

    # Instantiate the deployment object
    deployment = client.ExtensionsV1beta1Deployment(
        api_version="extensions/v1beta1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(name=os.environ["FEUERWERK_DEPLOYMENT_NAME"]),
        spec=spec,
    )

    return deployment


def create_deployment(api_instance, deployment):
    api_instance.create_namespaced_deployment(body=deployment, namespace="default")


def delete_deployment(api_instance):
    api_instance.delete_namespaced_deployment(
        name=os.environ["FEUERWERK_DEPLOYMENT_NAME"],
        namespace="default",
        body=client.V1DeleteOptions(
            propagation_policy="Foreground", grace_period_seconds=5
        ),
    )


def terminated_iter(v1):
    for item in v1.list_pod_for_all_namespaces(watch=False).items:
        for container in item.status.container_statuses:
            terminated = container.state.terminated
            if isinstance(terminated, client.V1ContainerStateTerminated):
                yield terminated


def main():
    bar = progressbar.ProgressBar(max_value=progressbar.UnknownLength)

    # Get our k8s configuration info
    print("Loading our k8s config")
    config.load_kube_config()

    # Grab an API instance for GCP
    print("Creating API instance object for GCP")
    api_instance = client.ExtensionsV1beta1Api()

    # Create our loadtest deployment
    print("Creating our deployment")
    deployment = create_deployment_object(
        number_of_containers=int(os.environ["FEUERWERK_NUM_CONTAINERS"]),
        image_name=os.environ["FEUERWERK_IMAGE_NAME"],
    )
    create_deployment(api_instance, deployment)

    msg = "Running load test using {} instance(s) of {} image".format(
        os.environ["FEUERWERK_NUM_CONTAINERS"], os.environ["FEUERWERK_IMAGE_NAME"]
    )
    print(msg)

    # Now watch until our test is done
    v1 = client.CoreV1Api()
    containers_terminated = False
    terminated_msg = "Loadtest containers exited without errors"

    while not containers_terminated:
        bar.update()
        for terminated in terminated_iter(v1):
            if terminated.reason == "Completed":
                containers_terminated = True
                if terminated.exit_code != 0:
                    terminated_msg = (
                        "Loadtest containers exited with errors, please check the logs"
                    )

    bar.finish()
    print("Load test completed")
    print(terminated_msg)

    # Now go and delete the job and we're done!
    try:
        delete_deployment(api_instance)
        print("Deployment deleted")
    except ApiException as e:
        print("Exception while trying to delete load test job: %s\n" % e)


if __name__ == "__main__":
    main()
