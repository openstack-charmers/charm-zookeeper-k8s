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

# Learn more about testing at: https://juju.is/docs/sdk/testing

import unittest
from unittest.mock import Mock, patch

from charm import ZookeeperK8SCharm
from ops.model import ActiveStatus
from ops.testing import Harness


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(ZookeeperK8SCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()

    @patch('ops.model.Container.push')
    def test_config_changed(self, mock_push):
        self.harness.update_config({'client-port': 1234})
        mock_push.assert_called_once_with(
            path='/conf/zoo.cfg', source=SuperstringOf('clientPort=1234'))

    @patch('charm.KazooClient')
    def test_dump_data_action(self, mock_zk):
        def get_children_mock(path):
            if path == '/':
                return ['first-child', 'second-child']
            return []

        mock_zk.return_value.get_children.side_effect = get_children_mock
        mock_zk.return_value.get.return_value = ('my value', 'some metadata')
        action_event = Mock()

        self.harness.charm._on_dump_data_action(action_event)

        mock_zk.assert_called_once_with(hosts='127.0.0.1:2181')
        action_event.set_results.assert_called_once_with({
            'content': {
                'first-child': 'my value',
                'second-child': 'my value',
            }
        })

    @patch('charm.KazooClient')
    def test_seed_data_action(self, mock_zk):
        action_event = Mock()

        self.harness.charm._on_seed_data_action(action_event)

        mock_zk.assert_called_once_with(hosts='127.0.0.1:2181')
        mock_zk.return_value.ensure_path.assert_called_once_with('/test-seed')
        self.assertTrue(action_event.set_results.called)

    @patch('ops.model.Container.push')
    def test_zookeeper_pebble_ready(self, mock_push):
        # Check the initial Pebble plan is empty
        initial_plan = self.harness.get_container_pebble_plan("zookeeper")
        self.assertEqual(initial_plan.to_yaml(), "{}\n")
        # Expected plan after Pebble ready with default config
        expected_plan = {
            "services": {
                "zookeeper": {
                    "override": "replace",
                    "summary": "zookeeper",
                    "command": "/docker-entrypoint.sh zkServer.sh start-foreground",
                    "startup": "enabled",
                }
            },
        }
        # Get the zookeeper container from the model
        container = self.harness.model.unit.get_container("zookeeper")
        # Emit the PebbleReadyEvent carrying the zookeeper container
        self.harness.charm.on.zookeeper_pebble_ready.emit(container)
        # Get the plan now we've run PebbleReady
        updated_plan = self.harness.get_container_pebble_plan(
            "zookeeper").to_dict()
        # Check we've got the plan we expected
        self.assertEqual(expected_plan, updated_plan)
        # Check the service was started
        service = self.harness.model.unit.get_container(
            "zookeeper").get_service("zookeeper")
        self.assertTrue(service.is_running())
        # Ensure we set an ActiveStatus with no message
        self.assertEqual(self.harness.model.unit.status, ActiveStatus())
        # Check the ZooKeeper config was written on disk
        mock_push.assert_called_once_with(
            path='/conf/zoo.cfg', source=SuperstringOf('clientPort=2181'))


class SuperstringOf(str):
    def __eq__(self, other):
        return self in other
