# Copyright 2017 Catalyst IT Ltd
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


class BaseDriver(object):
    """Base class for ERP drivers.
    """
    conf = None

    def __init__(self, conf):
        self.conf = conf

    def get_salesOrders(self, project, start_at, end_at):
        """List sales orders based on the given project and time range

        :param project: project id
        :param start_at: start time
        :param end_at: end time
        :returns List of sales order, if the time range only cover one month,
                 then, the list will only contain 1 sale orders. Otherwise,
                 the length of the list depends on the months number of the
                 time range.
        """
        raise NotImplementedError()

    def get_products(self, regions=None):
        """List products based o given regions

        :param regions: List of regions to get projects
        :returns Dict of products based on the given regions
        """
        raise NotImplementedError()

    def create_product(self, product):
        """Create product in Odoo.

        :param product: info used to create product
        """
        raise NotImplementedError()

    def get_credits(self, project):
        """Get project credits

        :param instance: nova.objects.instance.Instance
        :returns list of credits current project can get
        """
        raise NotImplementedError()

    def create_credit(self, project, credit):
        """Create credit for a given project

        :param project: project
        """
        raise NotImplementedError()

    def get_costs(self, bill_dates, project_id):
        """Get cost from invoice created in a date range.

        :param bill_dates: The dates when the invoice was created.
        :param project_id: project ID.
        :return: The total price for each month.
        """
        raise NotImplementedError()

    def build_service_name_mapping(self, products):
        """Gets mapping from service name to service type.

        :param products: Product dict returned from erp.
        """
        raise NotImplementedError()
