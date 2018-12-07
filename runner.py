import os
import progressbar
import time
import uuid
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from threading import Thread,Event


class ProgressBarUpdater(Thread):
    def __init__(self):
        super().__init__()
        self.bar = progressbar.ProgressBar(max_value=progressbar.UnknownLength)
        self.should_finish = Event()

    def run(self):
        while not self.should_finish.is_set():
            self.bar.update()
            time.sleep(0.1)

        self.bar.finish()


class TooManyRetriesTerminated:
    reason = "toomanyretries"


class NoContainersTerminated:
    reason = "nocontainers"


def create_deployment_object(number_of_containers, image_name, deployment_name):
    containers = []

    while number_of_containers > 0:
        container = client.V1Container(
            name="feuerwerk%s" % number_of_containers,
            image=image_name,
            image_pull_policy="IfNotPresent",
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
        metadata=client.V1ObjectMeta(name=deployment_name),
        spec=spec,
    )

    return deployment


def create_deployment(api_instance, deployment):
    api_instance.create_namespaced_deployment(body=deployment, namespace="default")


def delete_deployment(api_instance, deployment_name):
    api_instance.delete_namespaced_deployment(
        name=deployment_name,
        namespace="default",
        body=client.V1DeleteOptions(
            propagation_policy="Foreground", grace_period_seconds=5
        ),
    )


class NotReadyError(Exception):
    pass


def terminated_iter(v1):
    retry_count = 1
    no_container_count = 1

    while retry_count <= 3 and no_container_count <= 5:
        try:
            for item in v1.list_pod_for_all_namespaces(watch=False).items:
                if item.status.container_statuses is None:
                    retry_count += 1
                    time.sleep(5)
                    break
                for container in item.status.container_statuses:
                    terminated = container.state.terminated
                    if isinstance(terminated, client.V1ContainerStateTerminated):
                        yield terminated
                    else:
                        no_container_count += 1
                        time.sleep(5)
        except Exception as e:
            raise e

    # @TODO Better messaging that we ran out of retries
    if retry_count > 3:
        yield TooManyRetriesTerminated

    yield NoContainersTerminated


def main():
    deployment_name = "fw-" + uuid.uuid4().hex

    # Get the number of containers we are supposed to be running
    if os.environ["NUMBER_OF_CONTAINERS"] == "":
        finished = False
        while not finished:
            number_of_containers = int(
                input("How many copies of the container do you want running? ")
            )
            if number_of_containers <= 0:
                print(
                    "The number of copies of containers to run must be a positive integer"
                )
            else:
                finished = True
    else:
        number_of_containers = int(os.environ["NUMBER_OF_CONTAINERS"])

    # Get the name of our Docker image
    if os.environ["IMAGE_NAME"] == "":
        image_name = input(
            "What image are you using? (include full URL without http(s)://) "
        )
    else:
        image_name = os.environ["IMAGE_NAME"]

    # Create our progress bar
    bar = ProgressBarUpdater()

    # Get our k8s configuration info
    print("Loading our k8s config")
    config.load_kube_config()

    # Grab an API instance for GCP
    print("Creating API instance object for GCP")
    api_instance = client.ExtensionsV1beta1Api()

    # Create our loadtest deployment
    print("Creating our deployment {}".format(deployment_name))
    deployment = create_deployment_object(
        number_of_containers=number_of_containers,
        image_name=image_name,
        deployment_name=deployment_name,
    )
    create_deployment(api_instance, deployment)

    msg = "Running load test using {} instance(s) of {} image".format(
        number_of_containers, image_name
    )
    print(msg)
    bar.start()

    # Now watch until our test is done
    v1 = client.CoreV1Api()
    containers_terminated = False
    terminated_msg = "Loadtest containers exited without errors"

    while not containers_terminated:
        for terminated in terminated_iter(v1):
            if terminated.reason == "Completed":
                bar.should_finish.set()
                time.sleep(1)
                containers_terminated = True
                if terminated.exit_code != 0:
                    terminated_msg = (
                        "Loadtest containers exited with errors, please check the logs"
                    )
            elif terminated.reason == "toomanyretries":
                bar.should_finish.set()
                containers_terminated = True
                terminated_msg = "Could not get container status from GCP"
            elif terminated.reason == "nocontainers":
                bar.should_finish.set()
                containers_terminated = True
                terminated_msg = "GCP reported no containers could be found"

    time.sleep(2)
    print("Load test completed")
    print(terminated_msg)

    # Now go and delete the job and we're done!
    try:
        delete_deployment(api_instance, deployment_name)
        print("Deployment deleted")
    except ApiException as e:
        print("Exception while trying to delete load test job: %s\n" % e)


if __name__ == "__main__":
    main()
