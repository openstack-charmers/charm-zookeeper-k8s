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
import textwrap

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus

logger = logging.getLogger(__name__)


class ZookeeperK8SCharm(CharmBase):
    """Charm the service."""

    __PEBBLE_SERVICE_NAME = 'zookeeper'
    _stored = StoredState()  # FIXME remove?

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.zookeeper_pebble_ready,
                               self._on_zookeeper_pebble_ready)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.fortune_action, self._on_fortune_action)
        self._stored.set_default(things=[])

    def _on_zookeeper_pebble_ready(self, event):
        """Define and start a workload using the Pebble API.

        Learn more about Pebble layers at https://github.com/canonical/pebble
        """
        container = event.workload

        self.__push_zookeeper_config(container)

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

    def _on_config_changed(self, _):
        """Adapt ZooKeeper on Juju config changes.

        Learn more about config at https://juju.is/docs/sdk/config
        """
        container = self.unit.get_container('zookeeper')
        self.__push_zookeeper_config(container)
        self.__restart_zookeeper(container)

    def _on_fortune_action(self, event):
        """Just an example to show how to receive actions.

        FIXME: change this example to suit your needs.
        If you don't need to handle actions, you can remove this method,
        the hook created in __init__.py for it, the corresponding test,
        and the actions.py file.

        Learn more about actions at https://juju.is/docs/sdk/actions
        """
        fail = event.params["fail"]
        if fail:
            event.fail(fail)
        else:
            event.set_results({"fortune": "A bug in the code is worth two in the documentation."})

    def __push_zookeeper_config(self, workload_container):
        """Write ZooKeeper's config file on disk.

        :param workload_container: the container in which ZooKeeper is running
        :type workload_container: ops.model.Container
        """
        CONFIG_FILE_PATH = '/conf/zoo.cfg'

        client_port = self.config['client-port']
        server_port = self.config['server-port']
        leader_election_port = self.config['leader-election-port']

        config_file_content = textwrap.dedent(f'''\
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
        standaloneEnabled=true
        admin.enableServer=true
        server.1=localhost:{server_port}:{leader_election_port}
        ''')
        logging.debug('Writing config to {}:\n{}'.format(CONFIG_FILE_PATH,
                                                         config_file_content))
        workload_container.push(path=CONFIG_FILE_PATH,
                                source=config_file_content)

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


if __name__ == "__main__":
    main(ZookeeperK8SCharm)
