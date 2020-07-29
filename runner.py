import base64
import docker
import os
import progressbar
import requests
import time
import urllib3
import uuid

from kubernetes import client, config, watch
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


def main():
    # Turn off any SSL warnings
    urllib3.disable_warnings()

    # Create a job name
    job_name = "fw-" + uuid.uuid4().hex

    # Create our progress bar
    bar = ProgressBarUpdater()

    # Get our k8s configuration info
    print("Initializing our k8s configuration")
    config.load_kube_config()

    # Grab an API instance object
    api_instance = client.ExtensionsV1beta1Api()

    # Get the number of containers we are supposed to be running
    if "NUMBER_OF_CONTAINERS" not in os.environ:
        finished = False
        while not finished:
            number_of_containers = int(
                input("How many copies of the image do you want running? ")
            )
            if number_of_containers <= 0:
                print(
                    "The number of copies of images to run must be a positive integer"
                )
            else:
                finished = True
    else:
        number_of_containers = int(os.environ["NUMBER_OF_CONTAINERS"])

    # Get the name of our Docker image
    finished = False
    local_image = False

    while not finished:
        if "IMAGE_NAME" not in os.environ:
            image_name = input(
                "What Docker image are you using? (ie chartjes/kinto-loadtests) "
            )
        else:
            image_name = os.environ["IMAGE_NAME"]

        # First let's see if the image exists locally
        print("Checking to see if image exists locally...")
        try:
            docker_client = docker.from_env()
            docker_client.images.get(image_name)
            local_image = True
            finished = True
        except urllib3.exceptions.ProtocolError:
            local_image = False
        except docker.errors.ImageNotFound:
            local_image = False
        except FileNotFoundError:
            local_image = False
        except requests.exceptions.ConnectionError:
            local_image = False

        if local_image:
            print("Found the image locally...")
            finished = True
            continue

    if not local_image:
        print("Could not find the local Docker image, exiting")
        exit(1)		

    # Create our job
    print("Creating our load testing job...")
    container = client.V1Container(
        name='loadtest',
        image=image_name)
    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": "loadtest"}),
        spec=client.V1PodSpec(restart_policy="Never", containers=[container]))
    spec = client.V1JobSpec(
        template=template,
        parallelism=number_of_containers)
    job = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(name=job_name),
        spec=spec)

    # Start the job
    print("Starting the load testing job...")
    api_instance = client.BatchV1Api()
    api_response = api_instance.create_namespaced_job(
        body=job,
        namespace='default')

    # Monitor the status of our job
    bar.start()
    job_done = False
    finished_pod_count = 0
    deleteoptions = client.V1DeleteOptions()
    api_pods = client.CoreV1Api()

    while not job_done:
        resp = api_instance.list_namespaced_job(namespace="default", watch=False)
        for i in resp.items:
            if i.status.succeeded == True:
                job_done = True
                bar.should_finish.set()
        time.sleep(1) 


    # Delete the job
    print("Deleting load test job...")
    api_instance.delete_namespaced_job(
        job.metadata.name,
        "default",
        body = client.V1DeleteOptions(
                    grace_period_seconds = 5,
                    propagation_policy='Foreground'))

    print('Load test finished')

if __name__ == "__main__":
    main()
