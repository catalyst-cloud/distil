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

from stevedore import driver

from distil.common import general


class BaseTransformer(object):

    def __init__(self, name, override_config=None):
        self.config = general.get_transformer_config(name)
        if override_config:
            self.config.update(override_config)

    def transform_usage(self, meter_name, raw_data, start_at, end_at):
        return self._transform_usage(meter_name, raw_data, start_at, end_at)

    def _transform_usage(self, meter_name, raw_data, start_at, end_at):
        raise NotImplementedError


def get_transformer(name, **kwargs):
    return driver.DriverManager(
        'distil.transformer',
        name,
        invoke_on_load=True,
        invoke_args=(name,),
        invoke_kwds=kwargs
    ).driver
