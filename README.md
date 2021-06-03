# zookeeper-k8s

[![Charmhub](https://img.shields.io/badge/Charmhub-orange)](https://charmhub.io/zookeeper-k8s)
[![GitHub](https://img.shields.io/badge/GitHub-orange)](https://github.com/openstack-charmers/charm-zookeeper-k8s)

## Description

This [Juju Charmed Operator](https://juju.is/docs) deploys
[Apache ZooKeeper](https://zookeeper.apache.org/) on top of Kubernetes. It is
implemented using the [Charmed Operator Framework](https://juju.is/docs/sdk),
designed to deploy a standard [OCI](https://opencontainers.org/) (e.g. Docker)
ZooKeeper image alongside a sidecar container containing the Juju operator
logic.

Apache ZooKeeper is a service for storing the configuration (key-value store) of
a distributed system and helping with synchronization between components of that
system. This is for example used by [Zuul](https://zuul-ci.org/docs/zuul/),
OpenStack's CI system.

A non-sidecar version of this charm is also
[available on the Charmhub](https://charmhub.io/charmed-osm-zookeeper-k8s).

## Usage

### Deploying

```
$ juju add-model myzookeeper
$ juju deploy zookeeper-k8s -n 3
```

Where:

* `zookeeper-k8s`: the name of this Charmed Operator on the
  [Charmhub](https://charmhub.io/zookeeper-k8s).
* `-n`: the number of Juju units to deploy, i.e. the number of wanted k8s pods.
  Any number `>= 1` is supported but for production you should pick
  [an odd number `>= 3`](https://zookeeper.apache.org/doc/current/zookeeperStarted.html#sc_RunningReplicatedZooKeeper).

### Inspecting/Operating

The deployment can be inspected with `juju` and `kubectl`:

```
$ juju status
Model        Controller  Cloud/Region        Version  SLA          Timestamp
myzookeeper  micro       microk8s/localhost  2.9.0    unsupported  12:27:29Z

App            Version  Status  Scale  Charm          Store  Channel  Rev  OS          Address  Message
zookeeper-k8s           active      3  zookeeper-k8s  local             0  kubernetes

Unit              Workload  Agent  Address    Ports  Message
zookeeper-k8s/0   active    idle   10.1.0.47
zookeeper-k8s/1*  active    idle   10.1.0.49
zookeeper-k8s/2   active    idle   10.1.0.48

$ juju config zookeeper-k8s client-port
2181

$ kubectl get pods --namespace=myzookeeper
NAME                             READY   STATUS    RESTARTS   AGE
modeloperator-75988dd959-vvh2t   1/1     Running   0          4m33s
zookeeper-k8s-2                  2/2     Running   0          92s
zookeeper-k8s-1                  2/2     Running   0          92s
zookeeper-k8s-0                  2/2     Running   0          92s
```

This teaches us the IP addresses (here `10.1.0.47-49`) and the TCP port (`2181`)
to be used in order to access the ZooKeeper data from any client.

Zookeeper can be seeded with some dummy data:

```
$ juju run-action zookeeper-k8s/0 seed-data --wait
```

This data should then be replicated accross the entire ZooKeeper cluster and all
units should present that same data:

```
$ juju run-action zookeeper-k8s/0 zookeeper-k8s/1 zookeeper-k8s/2 dump-data --wait
unit-zookeeper-k8s-0:
  UnitId: zookeeper-k8s/0
  id: "8"
  results:
    content: '{''test-seed'': {''my-first-key'': b''my first value'', ''my-second-key'':
      b''my second value''}, ''zookeeper'': {''config'': b''server.1=10.1.0.47:2888:3888:participant\nserver.2=10.1.0.48:2888:3888:participant\nserver.3=10.1.0.49:2888:3888:participant\nversion=0'',
      ''quota'': b''''}}'
  status: completed
  timing:
    completed: 2021-06-02 11:41:36 +0000 UTC
    enqueued: 2021-06-02 11:41:33 +0000 UTC
    started: 2021-06-02 11:41:35 +0000 UTC
unit-zookeeper-k8s-1:
  UnitId: zookeeper-k8s/1
  id: "9"
  results:
    content: '{''test-seed'': {''my-first-key'': b''my first value'', ''my-second-key'':
      b''my second value''}, ''zookeeper'': {''config'': b''server.1=10.1.0.47:2888:3888:participant\nserver.2=10.1.0.48:2888:3888:participant\nserver.3=10.1.0.49:2888:3888:participant\nversion=0'',
      ''quota'': b''''}}'
  status: completed
  timing:
    completed: 2021-06-02 11:41:36 +0000 UTC
    enqueued: 2021-06-02 11:41:33 +0000 UTC
    started: 2021-06-02 11:41:35 +0000 UTC
unit-zookeeper-k8s-2:
  UnitId: zookeeper-k8s/2
  id: "10"
  results:
    content: '{''test-seed'': {''my-first-key'': b''my first value'', ''my-second-key'':
      b''my second value''}, ''zookeeper'': {''config'': b''server.1=10.1.0.47:2888:3888:participant\nserver.2=10.1.0.48:2888:3888:participant\nserver.3=10.1.0.49:2888:3888:participant\nversion=0'',
      ''quota'': b''''}}'
  status: completed
  timing:
    completed: 2021-06-02 11:41:36 +0000 UTC
    enqueued: 2021-06-02 11:41:33 +0000 UTC
    started: 2021-06-02 11:41:35 +0000 UTC
```

Any ZooKeeper client can be used to read and write data to/from the deployed
ZooKeeper cluster, e.g. [ZooNavigator](https://zoonavigator.elkozmon.com):

```
$ sudo snap install zoonavigator  # ZooNavigator's Web-UI is then served at:
$ firefox http://localhost:9000
```

![ZooNavigator Login](https://github.com/openstack-charmers/charm-zookeeper-k8s/raw/master/docs/zoonavigator_login.png)

![ZooNavigator Data](https://github.com/openstack-charmers/charm-zookeeper-k8s/raw/master/docs/zoonavigator_data.png)

## Developing

Create and activate a virtualenv with the development requirements:

```
$ virtualenv -p python3 venv
$ source venv/bin/activate
$ pip install -r requirements-dev.txt
```

### Testing

The Python operator framework includes a very nice harness for testing
operator behaviour without full deployment. Just `run_tests`:

```
$ ./run_tests
```

### Deploying from source

```
$ charmcraft pack
$ juju deploy ./zookeeper-k8s.charm -n 3 --resource zookeeper-image=zookeeper
```

Where:

* `-n`: the number of Juju units to deploy, i.e. the number of wanted k8s pods.
  Any number `>= 1` is supported but for production you should pick
  [an odd number `>= 3`](https://zookeeper.apache.org/doc/current/zookeeperStarted.html#sc_RunningReplicatedZooKeeper).
* `zookeeper-image`: [OCI](https://opencontainers.org/) (e.g. Docker) ZooKeeper
  image. Use `zookeeper` for the
  [latest image from DockerHub](https://hub.docker.com/_/zookeeper).
