# Feuerwerk

## Introduction

Feuerwerk is a tool designed to run load tests in [Docker](https://docker.com) containers using
[Kubernetes](https://kubernetes.io). It is a command-line tool, so be sure to read up on
how to run commands from your terminal.

Feuerwerk creates and launches a Kubernetes job, monitors the job
to see when it is completed, and then deletes the job afterwards.

## Installation

This project assumes the use of [pipenv](https://pipenv.readthedocs.io/en/latest/)
to create a virtual environment and install the required Python dependencies.

## Configuration

Copy the `config.ini.dist` to config.ini and change the following
values:

#### namespace

Can be left as "default" or changed to a different one based on
your Kubernetes set up

#### number_of_containers

This value should be set to the number of load test containers
you want running at one time.

#### container_name

The name you wish to give to the container when being executed
by Kubernetes.

#### image_name

Name of the Docker image you wish to use

#### image_pull_policy

Set this to `Always` for it to try and remotely pull the image down
from Docker. Set this to `Never` if you are using a container
you created locally.

## Use

Before running a load test, verify the following:

* You have the latest stable Kubernetes tools installed
* You have the latest version of Docker installed
* You have created a Docker image containing your load tests
