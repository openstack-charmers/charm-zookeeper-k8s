#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following post for a quick-start guide that will help you
develop a new k8s charm using the Operator Framework:

    https://discourse.charmhub.io/t/4208
"""

import logging
import os
import textwrap

from charms.zookeeper_k8s.v0.zookeeper import (
    INGRESS_ADDR_CLIENT_REL_DATA_KEY, INGRESS_ADDR_CLIENT_REL_DATA_SEPARATOR,
    PORT_CLIENT_REL_DATA_KEY)

from contextlib import contextmanager

from kazoo.client import KazooClient
from ops.charm import CharmBase
from ops.main import main
from ops.model import ActiveStatus

logger = logging.getLogger(__name__)


class ZookeeperK8SCharm(CharmBase):
    """Charm the service."""

    __PEBBLE_SERVICE_NAME = 'zookeeper'
    __INGRESS_ADDR_PEER_REL_DATA_KEY = 'ingress-address'
    __CLIENT_PORT_CONFIG_KEY = 'client-port'

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.zookeeper_pebble_ready,
                               self._on_zookeeper_pebble_ready)

        self.framework.observe(self.on.config_changed,
                               self._on_config_or_peer_changed)
        self.framework.observe(self.on.replicas_relation_joined,
                               self._on_config_or_peer_changed)
        self.framework.observe(self.on.replicas_relation_departed,
                               self._on_config_or_peer_changed)
        self.framework.observe(self.on.replicas_relation_changed,
                               self._on_config_or_peer_changed)

        self.framework.observe(self.on.client_relation_joined,
                               self._on_client_joined)

        self.framework.observe(self.on.dump_data_action,
                               self._on_dump_data_action)
        self.framework.observe(self.on.seed_data_action,
                               self._on_seed_data_action)

    def _on_zookeeper_pebble_ready(self, event):
        """Define and start a workload using the Pebble API.

        Learn more about Pebble layers at https://github.com/canonical/pebble
        """
        container = event.workload

        relation = self.model.get_relation('replicas')
        my_ingress_address = self._get_my_ingress_address(relation)
        all_unit_ingress_addresses = self._get_all_unit_ingress_addresses(
            relation)
        self.__push_zookeeper_config(container, my_ingress_address,
                                     all_unit_ingress_addresses)

        pebble_layer = {
            "summary": "zookeeper layer",
            "description": "pebble config layer for zookeeper",
            "services": {
                self.__PEBBLE_SERVICE_NAME: {
                    "override": "replace",
                    "summary": "zookeeper",
                    "command": "/docker-entrypoint.sh zkServer.sh start-foreground",
                    "startup": "enabled",
                }
            },
        }
        container.add_layer("zookeeper", pebble_layer, combine=True)

        # Autostart any services that were defined with startup: enabled
        container.autostart()

        # Learn more about statuses in the SDK docs:
        # https://juju.is/docs/sdk/constructs#heading--statuses
        self.unit.status = ActiveStatus()

    def _on_config_or_peer_changed(self, _):
        """Adapt ZooKeeper's config to Juju changes and inform client charm."""
        logging.debug('Handling Juju config or peer change...')

        peer_relation = self.model.get_relation('replicas')
        my_ingress_address = self._get_my_ingress_address(peer_relation)
        self._share_address_with_peers(my_ingress_address, peer_relation)
        all_unit_ingress_addresses = self._get_all_unit_ingress_addresses(
            peer_relation)

        container = self.unit.get_container('zookeeper')
        self.__push_zookeeper_config(container, my_ingress_address,
                                     all_unit_ingress_addresses)
        self.__restart_zookeeper(container)

        self._share_addresses_and_port_with_client(all_unit_ingress_addresses)

    def _on_client_joined(self, _):
        """Inform client charm on how to connect to ZooKeeper."""
        peer_relation = self.model.get_relation('replicas')
        all_unit_ingress_addresses = self._get_all_unit_ingress_addresses(
            peer_relation)
        self._share_addresses_and_port_with_client(all_unit_ingress_addresses)

    def _on_dump_data_action(self, event):
        """Action that prints ZooKeeper's content on a given unit.

        Learn more about actions at https://juju.is/docs/sdk/actions
        """
        def _get_tree(path, zk):
            """Recursive function returning the tree as a dict.
            """
            children = zk.get_children(path)
            if not len(children):
                value = zk.get(path)[0]
                return value
            return {child: _get_tree(os.path.join(path, child), zk)
                    for child in children}

        with self.__zookeeper_client() as zk:
            content = _get_tree('/', zk)
        event.set_results({'content': content})

    def _on_seed_data_action(self, event):
        """Action that seeds ZooKeeper with some test data.

        Learn more about actions at https://juju.is/docs/sdk/actions
        """
        with self.__zookeeper_client() as zk:
            zk.ensure_path('/test-seed')
            zk.create('/test-seed/my-first-key', b'my first value')
            zk.create('/test-seed/my-second-key', b'my second value')
        event.set_results({})

    def _share_address_with_peers(self, my_ingress_address, relation):
        """Share this unit's ingress address with peer units."""
        relation.data[self.unit][self.__INGRESS_ADDR_PEER_REL_DATA_KEY] = (
            my_ingress_address)

    def _share_addresses_and_port_with_client(self, all_unit_ingress_addresses):
        """Share ingress addresses and port with the related client charm if
        possible.

        :param all_unit_ingress_addresses: Each unit's (first) ingress address.
        :type all_unit_ingress_addresses: List[str]
        """
        # Do nothing if we're not the leader
        if not self.model.unit.is_leader():
            return

        relation = self.model.get_relation('client')
        port = self.config[self.__CLIENT_PORT_CONFIG_KEY]
        if relation is None or port is None or len(
                all_unit_ingress_addresses) < 1:
            # Too early. Nothing can be done now. Will be
            # done later.
            return

        relation.data[self.model.app][INGRESS_ADDR_CLIENT_REL_DATA_KEY] = (
            INGRESS_ADDR_CLIENT_REL_DATA_SEPARATOR.join(
                all_unit_ingress_addresses))
        relation.data[self.model.app][PORT_CLIENT_REL_DATA_KEY] = str(port)

    def _get_all_unit_ingress_addresses(self, relation):
        """Get all ingress addresses shared by all peers over the relation.

        Including the current unit.

        :returns: Each unit's (first) ingress address.
        :rtype: List[str]
        """
        result = set()

        my_ingress_address = self._get_my_ingress_address(relation)
        if my_ingress_address is not None:
            result.add(my_ingress_address)

        for unit in relation.units:
            try:
                unit_ingress_address = relation.data[unit][
                    self.__INGRESS_ADDR_PEER_REL_DATA_KEY]
            except KeyError:
                # This unit hasn't shared its address yet. It's OK as there will
                # be other hook executions later calling this again:
                continue
            if unit_ingress_address is not None:
                result.add(unit_ingress_address)

        logging.debug('All unit ingress addresses: {}'.format(
            ', '.join(result)))

        return list(result)

    def _get_my_ingress_address(self, relation):
        """Returns this unit's address on which it wishes to be contacted.

        :returns: This unit's (first) ingress address.
        :rtype: str
        """
        network = self.model.get_binding(relation).network
        # There seems to be a bug and `ingress_address` is always None. See
        # FIXME link to GitHub/Launchpad bug
        return str(network.ingress_address or network.bind_address)

    def __push_zookeeper_config(self, workload_container, my_ingress_address,
                                all_unit_ingress_addresses):
        """Write ZooKeeper's config files to disk.

        See https://zookeeper.apache.org/doc/current/zookeeperStarted.html

        :param workload_container: the container in which ZooKeeper is running
        :type workload_container: ops.model.Container
        :param all_unit_ingress_addresses: Each unit's (first) ingress address.
        :type all_unit_ingress_addresses: List[str]
        """
        MAIN_CONFIG_FILE_PATH = '/conf/zoo.cfg'
        ID_CONFIG_FILE_PATH = '/data/myid'

        client_port = self.config[self.__CLIENT_PORT_CONFIG_KEY]
        server_port = self.config['server-port']
        leader_election_port = self.config['leader-election-port']

        # NOTE(lourot): All server IDs have to match in the config file of all
        # units. Thus we sort the list in the same way on all units.
        server_addresses = sorted(all_unit_ingress_addresses)
        server_config_part = ''
        for i in range(len(server_addresses)):
            server_id = i + 1
            server_address = server_addresses[i]
            if server_address == my_ingress_address:
                my_id = server_id

            server_config_part += (
                f'server.{server_id}={server_address}:'
                f'{server_port}:{leader_election_port}\n'
            )

        main_config_file_content = textwrap.dedent(f'''\
        # Generated by the Charmed Operator
        dataDir=/data
        clientPort={client_port}
        dataLogDir=/datalog
        tickTime=2000
        initLimit=5
        syncLimit=2
        autopurge.snapRetainCount=3
        autopurge.purgeInterval=0
        maxClientCnxns=60
        admin.enableServer=true
        ''') + server_config_part

        id_config_file_content = f'{my_id}\n'

        for path, content in (
                (MAIN_CONFIG_FILE_PATH, main_config_file_content),
                (ID_CONFIG_FILE_PATH, id_config_file_content)
        ):
            logging.debug('Writing config to {}:\n{}'.format(path, content))
            workload_container.push(path=path, source=content)

    def __restart_zookeeper(self, workload_container):
        """Restart ZooKeeper by restarting the Pebble services.

        :param workload_container: the container in which ZooKeeper is running
        :type workload_container: ops.model.Container
        """
        services = workload_container.get_plan().to_dict().get('services', {})
        if not len(services):
            # No Pebble service defined yet, too early:
            return

        logging.info('Restarting ZooKeeper...')
        workload_container.stop(self.__PEBBLE_SERVICE_NAME)
        # Autostart any services that were defined with startup: enabled :
        workload_container.autostart()

    @contextmanager
    def __zookeeper_client(self):
        client_port = self.config[self.__CLIENT_PORT_CONFIG_KEY]
        zk = KazooClient(hosts='127.0.0.1:{}'.format(client_port))
        zk.start()
        try:
            yield zk
        finally:
            zk.stop()


if __name__ == "__main__":
    main(ZookeeperK8SCharm)
