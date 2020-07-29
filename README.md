# Feuerwerk

## Introduction

Feuerwerk is a tool designed to run load tests in [Docker](https://docker.com) containers using
[Google Kubernetes Engine](https://cloud.google.com/kubernetes-engine/). It is a command-line tool, so be sure to read up on
how to use whatever shell or command prompt is available for your operating system. 

Feuerwerk creates a Kubernetes job, launches it and then deletes the job when it has succesfully completed.

Please consult the documentation for your operating system, terminal emulator and shell if any
of the command-line instructions provided here do not work for you. 

## Requirements

To use this project you will need the following tools installed:

* [Python]() 3.6 or greater
* [pipenv](https://pipenv.readthedocs.io/en/latest/) to create a virtual environment and install the required Python dependencies
* [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/) to 
* Google's [Cloud SDK](https://cloud.google.com/sdk/) to configure Google Kubernetes Engine for use
* Docker to obtain images containing a load test or to turn your own load tests into a Docker image

Feuerwerk was developed
and tested using the following configurations:

* [macOS](), [iTerm 2]() and [zsh]()
* [Windows 10]() with [Ubuntu]() running inside [Windows Subsystem for Linux](), [Windows Terminal]() and [bash]()

You can find an example of creating a Dockerized load test [here](https://github.com/Kinto/kinto-loadtests/blob/master/Dockerfile). 


## Installation

Once you checked out this repo, create the virtual environment and activate it using
the following commands:

* `pipenv install`
* `pipenv shell`


## Project Creation and Configuration

If you haven't already created one, use the [Google Cloud Platform Console](https://console.cloud.google.com/) to create a project and
note the value Google returns to you for the name of the project.

For the sake of examples, the project ID is 'yetanothertest-219614'

Next we need to configure our environment to use this project using this CLI command:

`gcloud config set project yetanothertest-219614`

followed by setting which [region and zone](https://cloud.google.com/compute/docs/regions-zones/)
you wish to run your tests in. In this example we are using the US West zone. Choose a
zone that provides you with the computing resources you will need to run your tests.

`gcloud config set compute/zone us-west1-a`


### Service User and Credentials

Create a user who has permissions to access the resources you will be deploying up
to GKE. In this example we're using the same project as above and creating a user named
'feuerwerk'

`gcloud iam service-accounts create feuerwerk`

Then we need to give that user permission to access your project

`gcloud projects add-iam-policy-binding yetanothertest-219614 --member "serviceAccount:feuerwerk@yetanothertest-219614.iam.gserviceaccount.com" --role "roles/owner"`

With the user configured, we need to obtain the access keys and other credentials associated with the
user we created. These will be written to a file on your local filesystem.

`gcloud iam service-accounts keys create loadtest.json --iam-account feuerwerk@yetanothertest-219614.iam.gserviceaccount.com`

Next, we need to assign a value representing the fully qualified of path of the file to an
environment variable so the Kubernetes python client libraries can find. For [bash](https://www.gnu.org/software/bash/)
or zsh, you can use the following command:

`export GOOGLE_APPLICATION_CREDENTIALS=/Users/chartjes/mozilla-services/feuerwerk/loadtest.json`

You can optionally add the following line to your `.env` file so it is accessible
the next time you exit the virtual environment and re-enter it.

`GOOGLE_APPLICATION_CREDENTIALS=/Users/chartjes/mozilla-services/feuerwerk/loadtest.json`

### Cluster Creation

You will also need to set up a cluster for your load test containers to run in. You can create one by doing
the following:

* _Google Cloud Platform_ -> _Kubernetes Engine_ -> _Configuration_
* In the section that says "Filter secrets and config maps" click on the name (ie default-token-k7m4b)
* Then click on _KUBECTL_ and select _Get YAML_

This should open up a Cloud Shell. From inside the shell you can run the following command to get a kubectl config:

`cat .kube/config`

It should look something like this:

```
apiVersion: v1
clusters:
- cluster:
    certificate-authority-data: <redacted because I can't share>
    server: https://34.83.235.67
  name: gke_autopush-test-01_us-west1-a_autopush-cluster
contexts:
- context:
    cluster: gke_autopush-test-01_us-west1-a_autopush-cluster
    user: gke_autopush-test-01_us-west1-a_autopush-cluster
  name: gke_autopush-test-01_us-west1-a_autopush-cluster
current-context: gke_autopush-test-01_us-west1-a_autopush-cluster
kind: Config
preferences: {}
users:
- name: gke_autopush-test-01_us-west1-a_autopush-cluster
  user:
    auth-provider:
      config:
        access-token: <redacted because I can't share>
        cmd-args: config config-helper --format=json
        cmd-path: /usr/lib/google-cloud-sdk/bin/gcloud
        expiry: "2020-07-23T15:33:06Z"
        expiry-key: '{.credential.token_expiry}'
        token-key: '{.credential.access_token}'
      name: gcp
```

and then cut-and-paste that into your own kubectl configuration file.


### Creating Your Load Test

If you don't already have a load test in a Docker container, you will need to create one.  Here is a sample that uses [Molotov](https://github.com/loads/molotov):

```python
from molotov import scenario


@scenario(weight=7)
async def recipe_endpoint_test(session):
    recipe_endpoint = "https://localhost/api/v1/recipe/?enabled=true/"
    async with session.get(recipe_endpoint) as resp:
        res = await resp.json()
        assert resp.status == 200
        assert len(res) > 0


@scenario(weight=7)
async def signed_recipe_endpoint_test(session):
    signed_recipe_endpoint = (
        "https://localhost/api/v1/recipe/signed/?enabled=true/"
    )
    async with session.get(signed_recipe_endpoint) as resp:
        res = await resp.json()
        assert resp.status == 200
        assert len(res) > 0


@scenario(weight=7)
async def heartbeat_test(session):
    heartbeat_endpoint = "https://localhost/__heartbeat__"
    async with session.get(heartbeat_endpoint) as resp:
        res = await resp.json()
        assert resp.status == 200
        assert "status" in res


@scenario(weight=50)
async def classify_client_test(session):
    classify_client_endpoint = (
        "https://localhost/api/v1/classify_client/"
    )
    async with session.get(classify_client_endpoint) as resp:
        res = await resp.json()
        assert resp.status == 200
        assert "country" in res
        assert "request_time" in res


@scenario(weight=7)
async def implementation_url_tests(session):
    signed_action_endpoint = "https://localhost/api/v1/action/signed/"
    async with session.get(signed_action_endpoint) as resp:
        res = await resp.json()
        assert resp.status == 200
        count = 0

        while count <= 4 and res[count]["action"]["implementation_url"] is not None:
            implementation_url = res[count]["action"]["implementation_url"]
            async with session.get(implementation_url) as iu_resp:
                iu_res = await iu_resp.text()
                assert iu_resp.status == 200
                assert len(iu_res) > 0
                count = count + 1
```

### Dockerize Your Load Test

Once you have verified your test is working, you then need to createa Docker image
that will run your test. Here is a sample Dockerfile for a load test that was built
using Molotov

```
# Mozilla Load-Tester
FROM alpine:3.7

# deps
RUN apk add --update python3; \
    apk add --update python3-dev; \
    apk add --update openssl-dev; \
    apk add --update libffi-dev; \
    apk add --update build-base; \
    apk add --update git; \
    pip3 install --upgrade pip; \
    pip3 install molotov; \
    pip3 install git+https://github.com/loads/mozlotov.git; \
    pip3 install PyFxa;

WORKDIR /molotov
ADD . /molotov

# run the test
CMD molotov -c -v -d 60 api_tests.py
```

This can be customized based on whatever load testing framework you are using but
is should be able to run your load test.


### Run Your Load Test

To run your load test, run the following command:

`python runner.py`

You will be prompted to enter:

* a name for the deployment
* how many copies of your container to run at once
* the name of the image (ie someproject/sample-loadtest)

You should see output similar to the following:

```
Initializing our k8s configuration
How many copies of the image do you want running? 1
What Docker image are you using? (ie chartjes/kinto-loadtests) someproject/sample-loadtest:v1
Checking to see if image exists locally...
Found the image locally...
Creating our load testing job...
Starting the load testing job...
| |                                                            #                                   | 0 Elapsed Time: 0:05:20
Deleting load test job...
Load test finished
```

