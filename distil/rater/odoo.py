# Copyright 2014 Catalyst IT Ltd
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

from distil import rater
from distil.rater import rate_file
from distil.service.api.v2 import products


class OdooRater(rater.BaseRater):

    def __init__(self):
        self.prices = products.get_products()

    def rate(self, name, region=None):
        if not self.prices:
            return rate_file.FileRater().rate(name, region)
        region_prices = (self.prices[region] if region else
                         self.prices.values[0])

        for category in region_prices:
            for product in region_prices[category]:
                if product['resource'] == name:
                    return {'rate': product['price'],
                            'unit': product['unit']
                            }

        return rate_file.FileRater().rate(name, region)
