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

import csv
from decimal import Decimal

import logging as log

from distil import rater


class FileRater(rater.BaseRater):
    def __init__(self, conf):
        super(FileRater, self).__init__(conf)

        try:
            with open(self.config['file']) as fh:
                # Makes no opinions on the file structure
                reader = csv.reader(fh, delimiter="|")
                self.__rates = {
                    row[1].strip(): {
                        'rate': Decimal(row[3].strip()),
                        'region': row[0].strip(),
                        'unit': row[2].strip()
                    } for row in reader
                }
        except Exception as e:
            log.critical('Failed to load rates file: `%s`' % e)
            raise

    def rate(self, name, region=None):
        return {
            'rate': self.__rates[name]['rate'],
            'unit': self.__rates[name]['unit']
        }
