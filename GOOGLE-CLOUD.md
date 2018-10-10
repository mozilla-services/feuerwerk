# Running Feuerwerk On Google Cloud

This document outlines how to use Feuerwerk with Google Compute Platform.

It assumes you have followed the directions in the README.


## Prerequisites

* Kubernetes CLI tools installed
* Google Cloud's `gcloud` CLI tool installed
* Docker image that contains and runs your load tests
* An account configured to work with Google Compute Platform


## Configure your project

Create your project and assign it to whatever computing zone you
require:

`gcloud config set project {PROJECT NAME}`
`gcloid config set computer/zone {ZONE}`

{PROJECT NAME} cannot contain any spaces or punctuation other than
a dash.

{ZONE} is one of the available computing zones like `us-west1-a`.
Check GCP's documentation for available zones.

Use the GCP console at https://console.google.com to configure your
project for use with Kubernetes Engine API.

## Deploy Container to Google Kubernetes Engine

You will need to create a JSON file that contains credentials that
GCP is expecting and then set an environment variable in your shell
that points to it's location. Details are at: 

https://cloud.google.com/docs/authentication/production

Then create a Kubernetes cluster to run your load tests in:

`gcloud container clusters create {CLUSTER NAME}`
`gcloud container clusters get-credentials {CLUSTER NAME}`

{CLUSTER NAME} follows the same rules as {PROJECT NAME}  

## Start Your Load Tests

To run your load tests, use the following command:

`python runner.py`
