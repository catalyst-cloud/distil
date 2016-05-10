# Copyright (C) 2014 Catalyst IT Ltd
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_config import cfg
from oslo_log import log

from distil import version

CONF = cfg.CONF

DEFAULT_OPTIONS = (
    cfg.IntOpt('port',
               default=9999,
               help='The port for the Distil API server',
               ),
    cfg.StrOpt('host',
               default='0.0.0.0',
               help='The listen IP for the Distil API server',
               ),
    cfg.ListOpt('public_api_routes',
                default=['/', '/v2/prices', '/v2/health'],
                help='The list of public API routes',
                ),
    cfg.ListOpt('ignore_tenants',
                default=[],
                help=('The tenant name list which will be ignored when '
                      'collecting metrics from Ceilometer.')),
)

COLLECTOR_OPTS = [
    cfg.IntOpt('periodic_interval', default=3600,
               help=('Interval of usage collection.')),
    cfg.StrOpt('collector_backend', default='ceilometer',
               help=('Data collector.')),
]

ODOO_OPTS = [
    cfg.StrOpt('version', default='8.0',
               help='Version of Odoo server.'),
    cfg.StrOpt('hostname',
               help='Host name of Odoo server.'),
    cfg.IntOpt('port', default=443,
               help='Port of Odoo server'),
    cfg.StrOpt('protocol', default='jsonrpc+ssl',
               help='Protocol to connect to Odoo server.'),
    cfg.StrOpt('database',
               help='Name of the Odoo database.'),
    cfg.StrOpt('user',
               help='Name of Odoo account to login.'),
    cfg.StrOpt('password', secret=True,
               help='Password of Odoo account to login.'),
    cfg.StrOpt('last_update',
               help='Last time when the products/prices are updated.')
]

RATER_OPTS = [
    cfg.StrOpt('rater_type', default='odoo',
               help='Rater type, by default it is odoo.'),
    cfg.StrOpt('rate_file_path', default='/etc/distil/rates.csv',
               help='Rate file path, it will be used when the rater_type '
               'is "file".'),
]

RATER_GROUP = 'rater'
ODOO_GROUP = 'odoo'
COLLECTOR_GROUP = 'collector'


CONF.register_opts(DEFAULT_OPTIONS)
CONF.register_opts(ODOO_OPTS, group=ODOO_GROUP)
CONF.register_opts(COLLECTOR_OPTS, group=COLLECTOR_GROUP)
CONF.register_opts(RATER_OPTS, group=RATER_GROUP)


# This is simply a namespace for global config storage
main = None
rates_config = None
memcache = None
auth = None
collection = None
transformers = None


def setup_config(conf):
    global main
    main = conf['main']
    global rates_config
    rates_config = conf['rates_config']

    # special case to avoid issues with older configs
    try:
        global memcache
        memcache = conf['memcache']
    except KeyError:
        memcache = {'enabled': False}

    global auth
    auth = conf['auth']
    global collection
    collection = conf['collection']
    global transformers
    transformers = conf['transformers']


def parse_args(args=None, prog=None):
    log.set_defaults()
    log.register_options(CONF)
    CONF(
        args=args,
        project='distil',
        prog=prog,
        version=version.version_info.version_string(),
    )
    log.setup(CONF, prog)
