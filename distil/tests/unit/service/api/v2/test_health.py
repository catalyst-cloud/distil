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

from datetime import datetime
from datetime import timedelta

import mock

from distil.erp import utils as erp_utils
from distil.db.sqlalchemy import api as db_api
from distil.service.api.v2 import health
from distil.tests.unit import base


class HealthTest(base.DistilWithDbTestCase):
    def setUp(self):
        super(HealthTest, self).setUp()
        erp_utils._ERP_DRIVER = None

    @mock.patch('distil.common.openstack.get_projects')
    def test_get_health_ok(self, mock_get_projects):
        mock_get_projects.return_value = [
            {'id': '111', 'name': 'project_1', 'description': ''},
            {'id': '222', 'name': 'project_2', 'description': ''},
        ]

        # Insert projects in the database.
        project_1_collect = datetime.utcnow() - timedelta(hours=1)
        db_api.project_add(
            {
                'id': '111',
                'name': 'project_1',
                'description': '',
            },
            project_1_collect
        )
        project_2_collect = datetime.utcnow() - timedelta(hours=2)
        db_api.project_add(
            {
                'id': '222',
                'name': 'project_2',
                'description': '',
            },
            project_2_collect
        )

        ret = health.get_health()

        self.assertEqual('OK', ret['usage_collection'].get('status'))

    @mock.patch('distil.common.openstack.get_projects')
    def test_get_health_fail(self, mock_get_projects):
        mock_get_projects.return_value = [
            {'id': '111', 'name': 'project_1', 'description': ''},
            {'id': '222', 'name': 'project_2', 'description': ''},
        ]

        # Insert projects in the database.
        project_1_collect = datetime.utcnow() - timedelta(days=2)
        db_api.project_add(
            {
                'id': '111',
                'name': 'project_1',
                'description': '',
            },
            project_1_collect
        )
        project_2_collect = datetime.utcnow() - timedelta(hours=25)
        db_api.project_add(
            {
                'id': '222',
                'name': 'project_2',
                'description': '',
            },
            project_2_collect
        )

        ret = health.get_health()
        projects = ret['usage_collection'].get('failed_projects')

        self.assertIsNotNone(projects)
        self.assertEqual(2, len(projects))
        self.assertEqual('FAIL', ret['usage_collection'].get('status'))
        self.assertIn('2', ret['usage_collection'].get('msg'))

        p_names = [p['name'] for p in projects]
        p_ids = [p['id'] for p in projects]

        self.assertEqual(["project_1", "project_2"], p_names)
        self.assertEqual(["111", "222"], p_ids)

    @mock.patch('distil.service.api.v2.health.erp_utils')
    @mock.patch('distil.common.openstack.get_projects')
    def test_get_health_with_erp_backend_fail(self, mock_get_projects,
                                              mock_erp_utils):
        mock_erp_driver = mock.MagicMock()
        mock_erp_utils.load_erp_driver.return_value = mock_erp_driver
        mock_erp_driver.is_healthy.side_effect = Exception('Boom!')
        # mock_odoo.side_effect = ValueError
        ret = health.get_health()

        self.assertEqual('FAIL', ret['erp_backend'].get('status'))

    @mock.patch("distil.erp.drivers.odoo.client.Client")
    @mock.patch('distil.common.openstack.get_projects')
    def test_get_health_with_erp_backend(
        self,
        mock_get_projects,
        mock_odoo_client,
    ):
        ret = health.get_health()

        self.assertEqual('OK', ret['erp_backend'].get('status'))

    @mock.patch('distil.common.openstack.get_projects')
    def test_get_health_with_ignore_tenants(self, mock_get_projects):
        self.override_config('collector', ignore_tenants=['project_2'])
        mock_get_projects.return_value = [
            {'id': '111', 'name': 'project_1', 'description': ''},
            {'id': '222', 'name': 'project_2', 'description': ''},
        ]

        # Insert projects in the database.
        project_1_collect = datetime.utcnow() - timedelta(days=2)
        db_api.project_add(
            {
                'id': '111',
                'name': 'project_1',
                'description': '',
            },
            project_1_collect
        )
        project_2_collect = datetime.utcnow() - timedelta(hours=25)
        db_api.project_add(
            {
                'id': '222',
                'name': 'project_2',
                'description': '',
            },
            project_2_collect
        )

        ret = health.get_health()

        self.assertEqual('FAIL', ret['usage_collection'].get('status'))
        self.assertIn('1', ret['usage_collection'].get('msg'))
