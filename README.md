# zookeeper-k8s

[![Charmhub](https://img.shields.io/badge/Charmhub-orange)](https://charmhub.io/zookeeper-k8s)
[![GitHub](https://img.shields.io/badge/GitHub-orange)](https://github.com/openstack-charmers/charm-zookeeper-k8s)

## Description

This [Juju Charmed Operator](https://juju.is/docs) deploys
[Apache ZooKeeper](https://zookeeper.apache.org/) on top of Kubernetes.

Apache ZooKeeper is a service for storing the configuration (key-value store) of
a distributed system and helping with synchronization between components of that
system. This is for example used by [Zuul](https://zuul-ci.org/docs/zuul/),
OpenStack's CI system.

→ [Advanced documentation](https://charmhub.io/zookeeper-k8s/docs)

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

→ [Advanced usage](https://charmhub.io/zookeeper-k8s/docs/usage)

→ [Contributing](https://charmhub.io/zookeeper-k8s/docs/contributing)
