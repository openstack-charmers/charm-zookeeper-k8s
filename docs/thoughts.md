# Thoughts

This is the first time I implement a [sidecar charn](https://juju.is/docs/sdk).
Writing down some thoughts along the way.

## Charmcraft

### charmcraft init

At the beginning of my project my folder isn't empty. Instead it contains
already an initial `.git/` subfolder. `charmcraft init` should tolerate this
IMHO but instead fails with:

```
$ charmcraft init
/home/lourot/Documents/git/canonical/charm-zookeeper-k8s is not empty (consider using --force to work on nonempty directories) (full execution logs in /home/lourot/snap/charmcraft/common/charmcraft-
log-9qqbpl9b)
```


## Juju

### juju deploy

I decided to use [microk8s](https://microk8s.io/) for developing, which ships
Juju as one of its deps:

```
$ sudo snap install --classic microk8s
$ sudo snap alias microk8s.kubectl kubectl
$ sudo snap alias microk8s.juju juju
```

Unfortunately this is Juju 2.8.6 at the moment, which doesn't see to support
sidecar charms yet:

```
$ juju deploy ./zookeeper-k8s.charm --resource zookeeper-image=zookeeper
WARNING zookeeper-k8s does not declare supported series in metadata.yml
ERROR series "bionic" in a kubernetes model not valid
```

I had to install Juju 2.9.0 instead for it to work:

```
$ sudo snap unalias juju
$ sudo snap install --classic juju
```


### juju ssh

As a newbie it's not clear to me if `juju ssh zookeeper-k8s/0` will bring me to
ZooKeeper container or to the sidecar container

```
$ juju status
Model  Controller  Cloud/Region        Version  SLA          Timestamp
hello  micro       microk8s/localhost  2.9.0    unsupported  09:52:18Z

App            Version  Status  Scale  Charm          Store  Channel  Rev  OS          Address  Message
zookeeper-k8s           active      1  zookeeper-k8s  local             0  kubernetes           

Unit              Workload  Agent  Address    Ports  Message
zookeeper-k8s/0*  active    idle   10.1.0.11
```


### metadata.yaml


I wish I could specify a default OCI image in

```
resources:
  zookeeper-image:
    type: oci-image
```

so that my user doesn't need to pass that value at deploy-time on the
command-line.


## Pebble

this forces me to duplicate the docker `CMD`:

```
        pebble_layer = {
            "summary": "httpbin layer",
            "description": "pebble config layer for httpbin",
            "services": {
                "httpbin": {
                    "override": "replace",
                    "summary": "httpbin",
                    # duplicate of: CMD ["gunicorn" "-b" "0.0.0.0:80" "httpbin:app" "-k" "gevent"]
                    "command": "gunicorn -b 0.0.0.0:80 httpbin:app -k gevent",
                    "startup": "enabled",
                    "environment": {"thing": self.model.config["thing"]},
                }
            },
        }
```
