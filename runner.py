import configparser
import progressbar
from kubernetes import client, config
from kubernetes.client.rest import ApiException


def main():
    # Read in our config.ini file
    cp = configparser.ConfigParser()
    cp.read('config.ini')

    # Read in our Kubernetes configuration file
    configuration = config.load_kube_config()
    api_instance = client.BatchV1Api(client.ApiClient(configuration))
    namespace = cp['options']['namespace']

    # Time to assemble our job
    number_of_containers = int(cp['options']['number_of_containers'])
    containers = []

    while number_of_containers > 0:
        container = client.V1Container(
            name='%s-c-%s' % (cp['options']['image_name'], number_of_containers),
            image=cp['options']['image_name'],
            image_pull_policy=cp['options']['image_pull_policy'])
        containers.append(container)
        number_of_containers = number_of_containers - 1

    pod_spec = client.V1PodSpec(containers=containers, restart_policy="Never")
    template = client.V1PodTemplateSpec(spec=pod_spec)
    job_spec = client.V1JobSpec(template=template)
    job_metadata = client.V1ObjectMeta(name='loadtest')
    body = client.V1Job(spec=job_spec, metadata=job_metadata)

    print("Starting load test")

    try:
        api_instance.create_namespaced_job(namespace=namespace, body=body, pretty=True)
    except ApiException as e:
        print("Exception while creating load test job: %s\n" % e)

    msg = "Running load test using {} instance(s) of {} image".format(
        cp['options']['number_of_containers'],
        cp['options']['image_name']
    )
    print(msg)

    # Now watch until the pod has terminated
    test_completed = False
    v1 = client.CoreV1Api()
    bar = progressbar.ProgressBar(max_value=progressbar.UnknownLength)

    while test_completed is False:
        ret = v1.list_namespaced_pod(namespace=namespace)
        for pod in ret.items:
            if pod.status.phase == 'Succeeded':
                test_completed = True
        bar.update()
    
    bar.finish()
    print("Load test completed")

    # Now go and delete the job and we're done!
    try:
        api_instance.delete_namespaced_job(namespace=namespace, name='loadtest', body=body, pretty=True)
        print("Load test job deleted")
    except ApiException as e:
        print("Exception while trying to delete load test job: %s\n" % e)

    # Clean up the pods we created
    try:
        ret = v1.list_namespaced_pod(namespace=namespace)
        for pod in ret.items:
            v1.delete_namespaced_pod(namespace=namespace, body=body, name=pod.metadata.name)
        print("Load test pod deleted")
    except ApiException as e:
        print("Exception while trying to delete load test pod: %s\n" % e)


if __name__ == '__main__':
    main()

