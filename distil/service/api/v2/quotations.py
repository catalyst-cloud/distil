# Copyright (c) 2017 Catalyst IT Ltd.
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

from datetime import date
from datetime import datetime

from oslo_config import cfg
from oslo_log import log as logging

from distil.db import api as db_api
from distil.erp import utils as erp_utils
from distil.service.api.v2 import products

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


def get_quotations(project_id, detailed=False):
    """Get real time cost of current month."""

    today = date.today()
    start = datetime(today.year, today.month, 1)
    end = datetime(today.year, today.month, today.day)
    region_name = CONF.keystone_authtoken.region_name
    project = db_api.project_get(project_id)

    LOG.info(
        'Get quotations for %s(%s) from %s to %s, region: %s',
        project.id, project.name, start, end, region_name
    )

    # Same format with get_invoices output.
    output = {
        'start': str(start),
        'end': str(end),
        'project_id': project.id,
        'project_name': project.name,
    }

    usage = db_api.usage_get(project_id, start, end)

    erp_driver = erp_utils.load_erp_driver(CONF)
    cost = erp_driver.get_current_month_cost(
        region_name,
        project,
        usage,
        detailed=detailed
    )

    output['quotations'] = {str(end.date()): cost}

    return output
