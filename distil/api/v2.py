# Copyright (c) 2016 Catalyst IT Ltd
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

from dateutil import parser

from oslo_log import log

from distil import exceptions
from distil.api import acl
from distil.common import api
from distil.common import constants
from distil.common import openstack
from distil.service.api.v2 import costs
from distil.service.api.v2 import health
from distil.service.api.v2 import invoices
from distil.service.api.v2 import products
from distil.service.api.v2 import quotations

LOG = log.getLogger(__name__)

rest = api.Rest('v2', __name__)


@rest.get('/health')
def health_get():
    return api.render(health=health.get_health())


@rest.get('/products')
def products_get():
    os_regions = api.get_request_args().get('regions', None)
    regions = os_regions.split(',') if os_regions else []

    if regions:
        actual_regions = [r.id for r in openstack.get_regions()]

        if not set(regions).issubset(set(actual_regions)):
            raise exceptions.NotFoundException(
                'Region name(s) %s not found, available regions: %s' %
                (list(set(regions) - set(actual_regions)),
                 actual_regions)
            )

    return api.render(products=products.get_products(regions))


def _get_usage_args():
    # NOTE(flwang): Get 'tenant' first for backward compatibility.
    tenant_id = api.get_request_args().get('tenant', None)
    project_id = api.get_request_args().get('project_id', tenant_id)
    start = api.get_request_args().get('start', None)
    end = api.get_request_args().get('end', None)
    return project_id, start, end


@rest.get('/costs')
@acl.enforce("rating:costs:get")
def costs_get():
    project_id, start, end = _get_usage_args()

    # NOTE(flwang): Here using 'usage' instead of 'costs' for backward
    # compatibility.
    return api.render(usage=costs.get_costs(project_id, start, end))


@rest.get('/measurements')
@acl.enforce("rating:measurements:get")
def measurements_get():
    project_id, start, end = _get_usage_args()

    return api.render(measurements=costs.get_usage(project_id, start, end))


@rest.get('/invoices')
@acl.enforce("rating:invoices:get")
def invoices_get():
    project_id, start, end = _get_usage_args()
    detailed = bool(api.get_request_args().get('detailed', False))

    return api.render(
        invoices.get_invoices(project_id, start, end, detailed=detailed)
    )


@rest.get('/quotations')
@acl.enforce("rating:quotations:get")
def quotations_get():
    tenant_id = api.get_request_args().get('tenant', None)
    project_id = api.get_request_args().get('project_id', tenant_id)
    detailed = bool(api.get_request_args().get('detailed', False))

    return api.render(
        quotations.get_quotations(project_id, detailed=detailed)
    )
