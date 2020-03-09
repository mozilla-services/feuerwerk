# Feuerwerk

## Introduction

Feuerwerk is a tool designed to run load tests in [Docker](https://docker.com) containers using
[Google Kubernetes Engine](https://cloud.google.com/kubernetes-engine/). It is a command-line tool, so be sure to read up on
how to run commands from your terminal.

Feuerwerk creates a Kubernetes deployment, launches it and then monitors your containerized tests, tearing down the deployment once the tests have finished running.

Feuerwerk was created and tested using [macos](https://www.apple.com/macos/), [iterm2](https://iterm2.com/) and [zsh](http://www.zsh.org/).
Please consult the documentation for your operating system, terminal emulator and shell if any
of the command-line instructions provided here do not work for you.

## Installation

To use this project you will need the following tools installed:

* [pipenv](https://pipenv.readthedocs.io/en/latest/) to create a virtual environment and install the required Python dependencies
* [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/) to manage your Kubernetes deployments
* Google's [Cloud SDK](https://cloud.google.com/sdk/) to configure Google Kubernetes Engine for use

You also will need to have a [Docker](https://docker.com) image containing a load test that can be run. You can find an example
of creating a Dockerized load test [here](https://github.com/Kinto/kinto-loadtests/blob/master/Dockerfile).

Once you checked out this repo, create the virtual environment and activate it using
the following commands:

* `pipenv install`
* `pipenv shell`

## How To Run A Loadtest

### Project Creation and Configuration

If you haven't already created one, use the [Google Cloud Platform Console](https://console.cloud.google.com/) to create one and
note the value Google returns to you for the name of the project.

For the sake of examples, the project ID is 'yetanothertest-219614'

Next we need to configure our environment to use this project using this CLI command:

`gcloud config set project yetanothertest-219614`

followed by setting which [region and zone](https://cloud.google.com/compute/docs/regions-zones/)
you wish to run your tests in. In this example we are using the US West zone. Choose a
zone that provides you with the computing resources you will need to run your tests.

`gcloud config set compute/zone us-west1a`

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

You will also need to set up a cluster for your load test containers to run in.
Please follow the instructions on [configuring cluster access for kubectl](https://cloud.google.com/kubernetes-engine/docs/how-to/cluster-access-for-kubectl).

### Creating Your Load Test

You will then need to create a load test that you can later put inside a
[Docker](https://docker.com) container. Here is a sample that uses [Molotov](https://github.com/loads/molotov)
as it's framework:

```python
import os
from molotov import scenario


@scenario(weight=7)
async def recipe_endpoint_test(session):
    recipe_endpoint = os.environ["NORMANDY_DOMAIN"] + "/api/v1/recipe/?enabled=true/"
    async with session.get(recipe_endpoint) as resp:
        res = await resp.json()
        assert resp.status == 200
        assert len(res) > 0


@scenario(weight=7)
async def signed_recipe_endpoint_test(session):
    signed_recipe_endpoint = (
        os.environ["NORMANDY_DOMAIN"] + "/api/v1/recipe/signed/?enabled=true/"
    )
    async with session.get(signed_recipe_endpoint) as resp:
        res = await resp.json()
        assert resp.status == 200
        assert len(res) > 0


@scenario(weight=7)
async def heartbeat_test(session):
    heartbeat_endpoint = os.eviron["NORMANDY_DOMAIN"] + "/__heartbeat__"
    async with session.get(heartbeat_endpoint) as resp:
        res = await resp.json()
        assert resp.status == 200
        assert "status" in res


@scenario(weight=50)
async def classify_client_test(session):
    classify_client_endpoint = (
        os.environ["NORMANDY_DOMAIN"] + "/api/v1/classify_client/"
    )
    async with session.get(classify_client_endpoint) as resp:
        res = await resp.json()
        assert resp.status == 200
        assert "country" in res
        assert "request_time" in res


@scenario(weight=7)
async def implementation_url_tests(session):
    signed_action_endpoint = os.environ["NORMANDY_DOMAIN"] + "/api/v1/action/signed/"
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
CMD URL_SERVER=$URL_SERVER molotov -c -v -d 60 api_tests.py
```

This can be customized based on whatever load testing framework you are using but
is should be able to run your load test.


### Run Your Load Test

To run your load test, run the following command:

`python runner.py`

You will be prompted to enter:

* a name for the deployment
* how many copies of your container to run at once
* the name of the image (ie gcr.io/yetanothertest-219614/kintowe-loadtests)

You should see output similar to the following:

```
Loading our k8s config
Creating API instance object for GCP
How many copies of the container do you want running? 3
What Docker image are you using? (ie chartjes/kinto-loadtests) chartjes/kinto-loadtest
Checking to see if image exists locally...
Could not find the image locally
Checking if image exists at Docker Hub...
Could not find the requested Docker image
What Docker image are you using? (ie chartjes/kinto-loadtests) chartjes/kinto-loadtests
Checking to see if image exists locally...
Could not find the image locally
Checking if image exists at Docker Hub...
Found the image on Docker hub
Creating our deployment fw-d1f678bb4a8b4580b674739c589b31f8
Running load test using 3 instance(s) of chartjes/kinto-loadtests image                            #                                                                  | 0 Elapsed Time: 0:04:25 
Load test completed
GCP reported no containers could be found
Deployment deleted
```

