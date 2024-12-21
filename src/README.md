## Mobility of microservices in VANET

In this project I aim to setup a kubernetes cluster network, a mininet-wifi network and a mobility simulation using SUMO, in order to simulate the mobility of microservices with the goal of maintaining vehicle connectivity.

## Start Guide

### Kubernetes cluster with Kind

1. Create the cluster with the costum configuration file.
    
    > kind create cluster --config kind-config.yaml

2. Load the necessary docker images into the cluster nodes.
    
    > kind load docker-image kubeserver:latest

3. Run the cluster.py application to bootstrap the cluster services.

4. Request information from a service, e.g.,
    
    > wget 172.18.0.4:30001


### SDN Controller

Installing Ryu:
- git clone ... ; cd ryu
- pip install -r tools/pip-requires
- sudo python setup.py install

You can start the SDN controller by using the command:

    > ryu-manager --ofp-tcp-listen-port 6633 controller.py

### Running simulation

sudo env "PATH=/home/rubensas/anaconda3/envs/dissertation/bin:$PATH" python app.py scenarios/configs/1_POC_Replication.json


sudo /home/rubensas/anaconda3/envs/dissertation/bin/mn -c ; clear
