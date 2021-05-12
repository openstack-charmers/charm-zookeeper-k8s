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

    def test_action(self):
        # the harness doesn't (yet!) help much with actions themselves
        action_event = Mock(params={"fail": ""})
        self.harness.charm._on_fortune_action(action_event)

        self.assertTrue(action_event.set_results.called)

    def test_action_fail(self):
        action_event = Mock(params={"fail": "fail this"})
        self.harness.charm._on_fortune_action(action_event)

        self.assertEqual(action_event.fail.call_args, [("fail this",)])

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
