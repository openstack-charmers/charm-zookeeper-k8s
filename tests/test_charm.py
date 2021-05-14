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
from unittest.mock import ANY, call, Mock, patch

from charm import ZookeeperK8SCharm
from ops.model import ActiveStatus
from ops.testing import Harness


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(ZookeeperK8SCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()

    @patch('ops.model.Container.push')
    @patch('charm.ZookeeperK8SCharm._get_all_unit_ingress_addresses')
    @patch('charm.ZookeeperK8SCharm._share_address_with_peers')
    @patch('charm.ZookeeperK8SCharm._get_my_ingress_address')
    def test_config_changed(self, mock_my_address, mock_share_address,
                            mock_get_all_addresses, mock_push):
        mock_my_address.return_value = '10.1.0.42'
        mock_get_all_addresses.return_value = ['10.1.0.42', '10.1.0.43',
                                               '10.1.0.44']

        self.harness.update_config({'client-port': 1234})
        mock_share_address.assert_called_once_with('10.1.0.42', ANY)
        mock_push.assert_has_calls([
            call(path='/conf/zoo.cfg', source=SuperstringOf(
                ['clientPort=1234', '10.1.0.42', '10.1.0.43', '10.1.0.44'])),
            call(path='/data/myid', source=SuperstringOf(['1']))
        ], any_order=True)

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
    @patch('charm.ZookeeperK8SCharm._get_all_unit_ingress_addresses')
    @patch('charm.ZookeeperK8SCharm._share_address_with_peers')
    @patch('charm.ZookeeperK8SCharm._get_my_ingress_address')
    def test_zookeeper_pebble_ready(self, mock_my_address, mock_share_address,
                                    mock_get_all_addresses, mock_push):
        mock_my_address.return_value = '10.1.0.42'
        mock_get_all_addresses.return_value = ['10.1.0.42', '10.1.0.43',
                                               '10.1.0.44']

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
        mock_push.assert_has_calls([
            call(path='/conf/zoo.cfg',
                 source=SuperstringOf(['clientPort=2181'])),
            call(path='/data/myid', source=SuperstringOf(['1']))
        ], any_order=True)


class SuperstringOf:
    """Mock argument matcher that will match any superstring of the given
    expected substrings.
    """
    def __init__(self, expected_substrings):
        self.__expected_substrings = expected_substrings

    def __repr__(self):
        return 'SuperstringOf(' + str(self.__expected_substrings) + ')'

    def __eq__(self, expected_superstring):
        for expected_substring in self.__expected_substrings:
            if expected_substring not in expected_superstring:
                return False
        return True
