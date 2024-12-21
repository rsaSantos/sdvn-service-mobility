FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    net-tools \
    iputils-ping \
    iproute2 \
    curl

RUN curl -fsSL https://get.docker.com | sh

RUN [ $(uname -m) = x86_64 ] && curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.22.0/kind-linux-amd64
RUN chmod +x ./kind
RUN mv ./kind /usr/local/bin/kind

# For minikube:
# RUN curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
# RUN install minikube-linux-amd64 /usr/local/bin/minikube


CMD dockerd