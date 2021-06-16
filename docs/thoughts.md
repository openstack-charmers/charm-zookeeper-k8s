# Thoughts

This is the first time I implement a [sidecar charn](https://juju.is/docs/sdk).
Writing down some thoughts along the way.

## The good

* The code that this framework makes me write is easy to read and grasp, even
  for someone who isn't familiar with the concepts.
* The primitives and concepts make sense to me.


## Challenges / Issues / Wishlist

**TOC**:

+ Charmcraft
  - :heavy_check_mark: [Reporting issues](#heavy_check_mark-reporting-issues)
  - [Auto-completion](#auto-completion)
+ Juju
  - :heavy_check_mark: [juju deploy](#heavy_check_mark-juju-deploy) - microk8s ships old Juju
  - :star: [juju ssh](#star-juju-ssh) - where?
  - :star: [Charm without workload/container](#star-charm-without-workload-container)
+ :star: [Pebble](#star-pebble) - duplicates docker `CMD`
+ Operator Framework
  - :star: [Substrate abstraction](#star-substrate-abstraction)
  - [Implementing relations](#implementing-relations) - documentation should point to `libraries`
    * :star: [Library version](#star-library-version) - `v0` vs. `LIBAPI = 0`
    * :star: [`publish-lib` / `fetch-lib`](#star-publish-lib--fetch-lib) - what if more complex things to share?
  - [Changing the workload's exposed port](#changing-the-workloads-exposed-port)
  - :star: [Browsing the workload's filesystem](#star-browsing-the-workloads-filesystem)
  - [Harness](#harness) - mocking `push()`
  - :star: [Getting all peer's ingress address](#star-getting-all-peers-ingress-address)
    * :star: [ingress_address returs None](#star-ingress-address-returs-none)
  - :star: [Revision vs. version](#star-revision-vs-version)
  - Charmhub
    * [metadata.yaml changes not always reflected](#metadatayaml-changes-not-always-reflected)
    * [Can't link to the GitHub repo](#cant-link-to-the-github-repo)
    * [Reactive vs. Operator warning](#reactive-vs-operator-warning)
+ [Discourse](#discourse)


### Charmcraft

#### :heavy_check_mark: Reporting issues

https://snapcraft.io/charmcraft has no link to GitHub or Launchpad. People won't
know where to report issues. Fixed 
[meanwhile](https://github.com/canonical/charmcraft/issues/371).


#### Auto-completion

In bash:

```bash
$ ls *.charm
zookeeper-k8s.charm
$ charmcraft upload zoo[TAB][TAB][TAB]  # no auto-completion
```

Reported [here](https://github.com/canonical/charmcraft/issues/372).


### Juju

#### :heavy_check_mark: juju deploy

I decided to use [microk8s](https://microk8s.io/) for developing, which ships
Juju as one of its deps:

```bash
$ sudo snap install --classic microk8s
$ sudo snap alias microk8s.kubectl kubectl
$ sudo snap alias microk8s.juju juju
```

Unfortunately this is Juju 2.8.6 at the moment, which doesn't seem to support
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

This seems to be fixed
[meanwhile](https://github.com/ubuntu/microk8s/blob/master/snap/snapcraft.yaml#L547).


#### :star: juju ssh

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

Reported [here](https://discourse.charmhub.io/t/command-ssh/1834/2).


#### :star: Charm without workload/container

I implemented a [dummy client](https://charmhub.io/zookeeper-dummy-client-k8s)
for validating this charm. It has no workload, so it just deploys a dummy
`ubuntu` container. I wish it were possible to not have to define that dummy
container. Reported [here](https://bugs.launchpad.net/juju/+bug/1928991)


### :star: Pebble

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

Reported [here](https://bugs.launchpad.net/juju/+bug/1929861).


### Operator Framework

#### :star: Substrate abstraction

I wish I could more easily write one charm that would both work:

* as a legacy/machine charm, and
* as a container-orchestration/k8s charm.


#### Implementing relations

[The documentation about relations](https://juju.is/docs/sdk/relations) should
at least mention the
[documentation about libraries](https://juju.is/docs/sdk/libraries) otherwise I
have no chance to know that I should implement relations/interfaces as
libraries. Reported
[here](https://discourse.charmhub.io/t/libraries/4467/2?u=aurelien-lourot).


##### :star: Library version

What's the difference between the folder's name `v0/` and `LIBAPI = 0`? (See
[documentation](https://juju.is/docs/sdk/libraries).) Or do they have to match?


##### :star: `publish-lib` / `fetch-lib`

This works great if you have one snippet (one file) you want to share between
two charms. My intuition is that it's too simple and will bite back as soon as
you'll have trees of dependencies you want to share. There are reasons why other
frameworks make us of more advanced systems like git submodules and/or pip.


#### Changing the workload's exposed port

My workload docker image does `EXPOSE 2181` and I wanted to be able to change
that port with a Juju config option named `client-port`. I searched a long time
in the Operator Framework's, Juju's and Kubernetes's documentation to find out
how to do a port change or mapping (I have extended experience with pure Docker
and this made sense to me). Possibly something like a
[k8s service](https://kubernetes.io/docs/concepts/services-networking/service/#defining-a-service).

It took me a long time to understand that I didn't need to do anything of that
at all: all I had to do was to tell my workload software to listen to a
different port, and the Juju+k8s stack just exposes all ports anyway.

[Related issue.](https://bugs.launchpad.net/juju/+bug/1920960)


#### :star: Browsing the workload's filesystem

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

And apparently this can be done with just
[`juju ssh --container ...`](https://discourse.charmhub.io/t/command-ssh/1834/2)


#### Harness

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

Reported [here](https://github.com/canonical/operator/issues/518).


#### :star: Getting all peer's ingress address

This seems to be a wheel that many charms will need to re-invent: for now we
need to let each unit actively share its ingress address to its peers.

Even just getting the current unit's ingress address
[is tedious](https://github.com/canonical/operator/issues/534).

Reported [here](https://github.com/canonical/operator/issues/549).


##### :star: ingress_address returs None

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

But it always returns `None` and one needs to use `bind_address` instead.
Reported [here](https://bugs.launchpad.net/juju/+bug/1922133).


#### :star: Revision vs. version

The [documentation](https://juju.is/docs/sdk/resources) isn't clear about the
difference and uses the words interchangeably. Reported
[here](https://discourse.charmhub.io/t/resources/4468/2).


#### Charmhub

##### metadata.yaml changes not always reflected

I was releasing to `channel=beta` only at first and it turned out that changes
to the metadata.yaml are only reflected on the Web UI if releasing to
`channel=stable`, even if I have never released to that channel yet. I.e. each
time I would release to `channel=beta` my README changes would be reflected but
not my metadata changes.

Reported [here](https://discourse.charmhub.io/t/publishing/4462/6).


##### Can't link to the GitHub repo

On the Charmstore this was possible with the `charm` snap. On the Charmhub the
possibility to provide a link to GitHub isn't implemented yet. Confirmed with
the Web team.


##### Reactive vs. Operator warning

Even if the charm is made with the Operator framework, the Web UI still shows

> While many Reactive Framework charms work on machines today, it’s recommended
> to create new charms with the Operator Framework.

Apparently the Web team has to
[fix it manually](https://github.com/canonical-web-and-design/charmhub.io/pull/1033)
for each and every sidecar charm.


### Discourse

I'm not a big fan of Discourse when it comes to suggesting edits to improve
documentation. On paper, Discourse sounds easy: you just reply to a post in
order to suggest an edit. But if you have ever done it in real life, you know
it's not that easy to really make yourself clear in a reply. You can't actually
submit an edit for review yourself like you would do with a pull-request on
GitHub.
