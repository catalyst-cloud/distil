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

from keystonemiddleware import auth_token
from keystonemiddleware import opts
from oslo_config import cfg
from oslo_log import log as logging
import re

CONF = cfg.CONF
AUTH_GROUP_NAME = 'keystone_authtoken'


def _register_opts():
    options = []
    keystone_opts = opts.list_auth_token_opts()
    for n in keystone_opts:
        if (n[0] == AUTH_GROUP_NAME):
            options = n[1]
            break

        CONF.register_opts(options, group=AUTH_GROUP_NAME)
        auth_token.CONF = CONF


_register_opts()


LOG = logging.getLogger(__name__)


class AuthTokenMiddleware(auth_token.AuthProtocol):
    """A wrapper on Keystone auth_token middleware.
    Does not perform verification of authentication tokens
    for public routes in the API.
    """
    def __init__(self, app, conf, public_api_routes=None):
        if public_api_routes is None:
            public_api_routes = []
        route_pattern_tpl = '%s(\.json)?$'

        try:
            self.public_api_routes = [re.compile(route_pattern_tpl % route_tpl)
                                      for route_tpl in public_api_routes]
        except re.error as e:
            msg = _('Cannot compile public API routes: %s') % e

            LOG.error(msg)
            raise exception.ConfigInvalid(error_msg=msg)

        super(AuthTokenMiddleware, self).__init__(app, conf)

    def __call__(self, env, start_response):
        path = env.get('PATH_INFO', "/")

        # The information whether the API call is being performed against the
        # public API is required for some other components. Saving it to the
        # WSGI environment is reasonable thereby.
        env['is_public_api'] = any(map(lambda pattern: re.match(pattern, path),
                                       self.public_api_routes))

        if env['is_public_api']:
            return self._app(env, start_response)

        return super(AuthTokenMiddleware, self).__call__(env, start_response)

    @classmethod
    def factory(cls, global_config, **local_conf):
        public_routes = local_conf.get('acl_public_routes', '')
        public_api_routes = [path.strip() for path in public_routes.split(',')]

        def _factory(app):
            return cls(app, global_config, public_api_routes=public_api_routes)
        return _factory


def wrap(app, conf):
    """Wrap wsgi application with auth validator check."""

    auth_cfg = dict(conf.get(AUTH_GROUP_NAME))
    public_api_routes = CONF.public_api_routes
    auth_protocol = AuthTokenMiddleware(app, conf=auth_cfg,
                                        public_api_routes=public_api_routes)
    return auth_protocol
