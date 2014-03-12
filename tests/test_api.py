from webtest import TestApp
from . import test_interface, helpers, constants
from artifice.api.web import get_app
from artifice import models
from artifice import interface
from datetime import datetime
import json
import mock


class TestApi(test_interface.TestInterface):

    def setUp(self):
        super(TestApi, self).setUp()
        self.app = TestApp(get_app(constants.config))

    def tearDown(self):
        super(TestApi, self).tearDown()
        self.app = None

    def test_usage_run_for_all(self):
        """Asserts a usage run generates data for all tenants"""

        usage = helpers.get_usage()

        with mock.patch('artifice.interface.Artifice') as Artifice:

            tenants = []

            for tenant in constants.TENANTS:
                t = mock.Mock(spec=interface.Tenant)
                t.usage.return_value = usage
                t.conn = tenant
                tenants.append(t)

            artifice = mock.Mock(spec=interface.Artifice)

            artifice.tenants = tenants

            Artifice.return_value = artifice

            # patch to mock out the novaclient call
            with mock.patch('artifice.helpers.flavor_name') as flavor_name:
                flavor_name.side_effect = lambda x: x

                resp = self.app.post("/collect_usage")
                self.assertEquals(resp.status_int, 200)

                tenants = self.session.query(models.Tenant)
                self.assertTrue(tenants.count() > 0)

                usages = self.session.query(models.UsageEntry)
                self.assertTrue(usages.count() > 0)
                resources = self.session.query(models.Resource)

                self.assertEquals(resources.count(), len(usage.values()))

    def test_sales_run_for_all(self):
        """Assertion that a sales run generates all tenant orders"""

        now = datetime.now().\
            replace(hour=0, minute=0, second=0, microsecond=0)
        helpers.fill_db(self.session, 7, 5, now)
        resp = self.app.post("/sales_order",
                             params=json.dumps({}),
                             content_type='application/json')
        resp_json = json.loads(resp.body)

        self.assertEquals(resp.status_int, 200)

        query = self.session.query(models.SalesOrder)
        self.assertEquals(query.count(), 7)

        self.assertEquals(len(resp_json['tenants']), 7)

        for i, tenant in enumerate(resp_json['tenants']):
            self.assertTrue(tenant['generated'])
            self.assertEquals(tenant['id'], 'tenant_id_' + str(i))

    def test_sales_run_single(self):
        """Assertion that a sales run generates one tenant only"""

        now = datetime.now().\
            replace(hour=0, minute=0, second=0, microsecond=0)
        helpers.fill_db(self.session, 5, 5, now)
        resp = self.app.post("/sales_order",
                             params=json.dumps({"tenants": ["tenant_id_0"]}),
                             content_type="application/json")
        resp_json = json.loads(resp.body)

        self.assertEquals(resp.status_int, 200)

        query = self.session.query(models.SalesOrder)
        self.assertEquals(query.count(), 1)
        # todo: assert things in the response
        self.assertEquals(len(resp_json['tenants']), 1)
        self.assertTrue(resp_json['tenants'][0]['generated'])
        self.assertEquals(resp_json['tenants'][0]['id'], 'tenant_id_0')

    def test_sales_raises_400(self):
        """Assertion that 400 is being thrown if content is not json."""
        resp = self.app.post("/sales_order", expect_errors=True)
        self.assertEquals(resp.status_int, 400)

    def test_sales_order_no_tenants_overlap(self):
        """Test that if a tenant list is provided and none match,
        then we throw an error."""
        resp = self.app.post('/sales_order',
                             expect_errors=True,
                             params=json.dumps({'tenants': ['bogus tenant']}),
                             content_type='application/json')
        self.assertEquals(resp.status_int, 400)
