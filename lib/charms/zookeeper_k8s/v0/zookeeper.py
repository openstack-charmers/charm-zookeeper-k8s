"""

# ZooKeeper Library

This [library](https://juju.is/docs/sdk/libraries) implements both sides of the
`zookeeper` [interface](https://juju.is/docs/sdk/relations).

The *provider* side of this interface is implemented by the
[zookeeper-k8s Charmed Operator](https://charmhub.io/zookeeper-k8s).

Any Charmed Operator that *requires* a ZooKeeper database for providing its
service should implement the *requirer* side of this interface.
[zookeeper-dummy-client-k8s](https://github.com/AurelienLourot/charm-zookeeper-dummy-client-k8s)
is an example.

These two Charmed Operators would then be related to each other with

```
$ juju add-relation zookeeper-k8s:client zookeeper-dummy-client-k8s:zookeeper
```

In a nutshell using this library to implement a Charmed Operator *requiring* a
ZooKeeper database (and talking to it as a ZooKeeper client) would look like

```
$ charmcraft fetch-lib charms.zookeeper_k8s.v0.zookeeper
```

`metadata.yaml`:

```
requires:
  zookeeper:
    interface: zookeeper
```

`src/charm.py`:

```
from charms.zookeeper_k8s.v0.zookeeper import ZookeeperRequires

class ZookeeperDummyClientK8SCharm(CharmBase):
    on = ZookeeperRelationCharmEvents()
    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.zookeeper = ZookeeperRequires(self, self._stored)
        self.framework.observe(self.on.zookeeper_relation_updated,
                               self._on_zookeeper_config_changed)
```

You can file bugs
[here](https://github.com/openstack-charmers/charm-zookeeper-k8s/issues)!
"""

from ops.charm import CharmEvents, RelationChangedEvent
from ops.framework import EventBase, EventSource, Object

# The unique Charmhub library identifier, never change it
LIBID = "0d1db716e5cf45aa9177f4df6ad969ff"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 10

INGRESS_ADDR_CLIENT_REL_DATA_KEY = 'ingress-addresses'
INGRESS_ADDR_CLIENT_REL_DATA_SEPARATOR = ','
PORT_CLIENT_REL_DATA_KEY = 'client-port'


class ZookeeperRequires(Object):
    def __init__(self, charm, stored):
        super().__init__(charm, None)
        self.framework.observe(charm.on.zookeeper_relation_changed,
                               self.__on_relation_changed)
        self.charm = charm
        self.stored = stored

    def __on_relation_changed(self, event: RelationChangedEvent):
        # Do nothing if we're not the leader
        if not self.model.unit.is_leader():
            return

        zookeeper_addresses = event.relation.data[event.app].get(
            INGRESS_ADDR_CLIENT_REL_DATA_KEY).split(
                INGRESS_ADDR_CLIENT_REL_DATA_SEPARATOR)
        zookeeper_port = event.relation.data[event.app].get(
            PORT_CLIENT_REL_DATA_KEY)

        self.stored.apps.update({event.relation.id: {
            'zookeeper-addresses': zookeeper_addresses,
            'zookeeper-port': zookeeper_port,
        }})

        self.charm.on.zookeeper_relation_updated.emit()


class ZookeeperRelationCharmEvents(CharmEvents):
    class ZookeeperRelationUpdatedEvent(EventBase):
        pass

    zookeeper_relation_updated = EventSource(ZookeeperRelationUpdatedEvent)
