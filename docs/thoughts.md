# Thoughts

This is the first time I implement a [sidecar charn](https://juju.is/docs/sdk).
Writing down some thoughts along the way.

## Charmcraft

### Auto-completion

In bash:

```bash
$ ls *.charm
zookeeper-k8s.charm
$ charmcraft upload zoo[TAB][TAB][TAB]  # no auto-completion
```


## Juju

### juju deploy

I decided to use [microk8s](https://microk8s.io/) for developing, which ships
Juju as one of its deps:

```bash
$ sudo snap install --classic microk8s
$ sudo snap alias microk8s.kubectl kubectl
$ sudo snap alias microk8s.juju juju
```

Unfortunately this is Juju 2.8.6 at the moment, which doesn't see to support
sidecar charms yet:

```bash
$ juju deploy ./zookeeper-k8s.charm --resource zookeeper-image=zookeeper
WARNING zookeeper-k8s does not declare supported series in metadata.yml
ERROR series "bionic" in a kubernetes model not valid
```

I had to install Juju 2.9.0 instead for it to work:

```bash
$ sudo snap unalias juju
$ sudo snap install --classic juju
```


### juju ssh

As a newbie it's not clear to me if `juju ssh zookeeper-k8s/0` will bring me to
the ZooKeeper container or to the sidecar container

```bash
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

```yaml
resources:
  zookeeper-image:
    type: oci-image
```

so that my user doesn't need to pass that value at deploy-time on the
command-line.


## Pebble

This forces me to duplicate the docker `CMD`:

```python
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
                }
            },
        }
```


## Operator Framework

### Implementing relations

[The documentation about relations](https://juju.is/docs/sdk/relations) should
at least mention the
[documentation about libraries](https://juju.is/docs/sdk/libraries) otherwise I
have no chance to know that I should implement relations/interfaces as
libraries. Reported
[here](https://discourse.charmhub.io/t/libraries/4467/2?u=aurelien-lourot).


#### Library version

What's the difference between the folder's name `v0/` and `LIBAPI = 0`? (See
[documentation](https://juju.is/docs/sdk/libraries).) Or do they have to match?


### Changing the workload's exposed port

My workload docker image does `EXPOSE 2181` and I wanted to be able to change
that port with a Juju config option named `client-port`. I searched a long time
in the Operator Framework's, Juju's and Kubernetes's documentation to find out
how to do a port change or mapping (I have extended experience with pure Docker
and this made sense to me). Possibly something like a
[k8s service](https://kubernetes.io/docs/concepts/services-networking/service/#defining-a-service).

It took me a long time to understand that I didn't need to do anything of that
at all: all I had to do was to tell my workload software to listen to a
different port, and the Juju+k8s stack just exposes all ports anyway.


### Browsing the workload's filesystem

It took me a while to figure this out:

```bash
# Get pod name:
kubectl get all --namespace=<juju-model-name>

# Get workload container name:
kubectl describe pods --namespace=<juju-model-name>

# Browse the workload's filesystem:
kubectl exec --namespace=<juju-model-name> <pod-name> -c <workload-container-name> -- ls /
kubectl exec --namespace=myzookeeper zookeeper-k8s-0 -c zookeeper -- ls /
kubectl exec --namespace=myzookeeper zookeeper-k8s-0 -c zookeeper --stdin --tty -- bash
```


### Harness

`push()` (Pebble) needs to be mocked away:

```python
    @patch('ops.model.Container.push')
    def test_config_changed(self, mock_push):
        self.harness.update_config({"thing": "foo"})
```

otherwise:

```
======================================================================
ERROR: test_config_changed (tests.test_charm.TestCharm)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/lourot/Documents/git/canonical/charm-zookeeper-k8s/tests/test_charm.py", line 33, in test_config_changed
    self.harness.update_config({"thing": "foo"})
  File "/home/lourot/Documents/git/canonical/charm-zookeeper-k8s/venv/lib/python3.6/site-packages/ops/testing.py", line 636, in update_config
    self._charm.on.config_changed.emit()
  File "/home/lourot/Documents/git/canonical/charm-zookeeper-k8s/venv/lib/python3.6/site-packages/ops/framework.py", line 278, in emit
    framework._emit(event)
  File "/home/lourot/Documents/git/canonical/charm-zookeeper-k8s/venv/lib/python3.6/site-packages/ops/framework.py", line 722, in _emit
    self._reemit(event_path)
  File "/home/lourot/Documents/git/canonical/charm-zookeeper-k8s/venv/lib/python3.6/site-packages/ops/framework.py", line 767, in _reemit
    custom_handler(event)
  File "/home/lourot/Documents/git/canonical/charm-zookeeper-k8s/src/charm.py", line 93, in _on_config_changed
    self.__push_zookeeper_config(container)
  File "/home/lourot/Documents/git/canonical/charm-zookeeper-k8s/src/charm.py", line 147, in __push_zookeeper_config
    source=config_file_content)
  File "/home/lourot/Documents/git/canonical/charm-zookeeper-k8s/venv/lib/python3.6/site-packages/ops/model.py", line 1133, in push
    group_id=group_id, group=group)
  File "/home/lourot/Documents/git/canonical/charm-zookeeper-k8s/venv/lib/python3.6/site-packages/ops/testing.py", line 1099, in push
    raise NotImplementedError(self.push)
NotImplementedError: <bound method _TestingPebbleClient.push of <ops.testing._TestingPebbleClient object at 0x7ff3e8df0710>>
```


### Getting all peer's ingress address

This seems to be a wheel that many charms will need to re-invent: for now we
need to let each unit actively share its ingress address to its peers.


#### ingress_address returs None

```python
# ops/model.py

class Network:
    """Network space details.
    [...]
        ingress_addresses: A list of :class:`ipaddress.ip_address` objects representing the IP
            addresses that other units should use to get in touch with you.
    [...]
    """

    @property
    def ingress_address(self):
        """The address other applications should use to connect to your unit.
        [...]
        """
```

But it always returns `None` and one needs to use `bind_address` instead


### Revision vs. version

The [documentation](https://juju.is/docs/sdk/resources) isn't clear about the
difference and uses the words interchangeably. Reported
[here](https://discourse.charmhub.io/t/resources/4468/2).


### Charmhub

#### metadata.yaml changes not always reflected

I was releasing to `channel=beta` only at first and it turned out that changes
to the metadata.yaml are only reflected on the Web UI if releasing to
`channel=stable`, even if I have never released to that channel yet. I.e. each
time I would release to `channel=beta` my README changes would be reflected but
not my metadata changes.


#### Can't link to the GitHub repo

On the Charmstore this was possible with the `charm` snap. On the Charmhub the
possibility to provide a link to GitHub isn't implemented yet. Confirmed with
the Web team.


#### Reactive vs. Operator warning

Even if the charm is made with the Operator framework, the Web UI still shows

> While many Reactive Framework charms work on machines today, it’s recommended
> to create new charms with the Operator Framework.

Apparently the Web team has to
[fix it manually](https://github.com/canonical-web-and-design/charmhub.io/pull/1033)
for each and every sidecar charm.


## Discourse

Not having my documentation together with the source code makes it really hard
for my users to find the documentation that applies to a specific version of
the charm. Which channel (stable, edge) should the Discourse page be showing?
If stable, where do I develop the edge documentation?
