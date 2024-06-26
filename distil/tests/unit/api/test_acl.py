# Copyright (c) 2014 Mirantis Inc.
# Copyright (C) 2013-2024 Catalyst Cloud Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import flask
import mock
from oslo_policy import policy as cpolicy

from distil.api import acl
from distil import exceptions as ex
from distil.tests.unit import base
from distil import context



class TestAcl(base.DistilTestCase):

    def _set_policy(self, json):
        acl.setup_policy()
        rules = cpolicy.Rules.load_json(json)
        acl.ENFORCER.set_rules(rules, use_conf=False)

    def test_policy_allow(self):
        @acl.enforce("rating:get_all")
        def test():
            pass

        json = '{"rating:get_all": ""}'
        self._set_policy(json)

        test()

    def test_policy_deny(self):
        @acl.enforce("rating:get_all")
        def test(context):
            pass

        json = '{"rating:get_all": "!"}'
        self._set_policy(json)

        self.assertRaises(ex.Forbidden, test, context.RequestContext())

    @mock.patch('flask.Request')
    def test_route_post(self, get_deta_mock):
        get_deta_mock.return_value = '{"foo": "bar"}'
        pass
