# Copyright (c) 2013 Mirantis Inc.
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

from eventlet.green import threading
from oslo_context import context

from distil import exceptions


class RequestContext(context.RequestContext):

    def __init__(self, project_id=None, overwrite=True,
                 auth_token=None, user=None, tenant=None, domain=None,
                 user_domain=None, project_domain=None, is_admin=False,
                 read_only=False, show_deleted=False, request_id=None,
                 instance_uuid=None, roles=[], **kwargs):
        super(RequestContext, self).__init__(auth_token=auth_token,
                                             user=user,
                                             tenant=tenant,
                                             domain=domain,
                                             user_domain=user_domain,
                                             project_domain=project_domain,
                                             is_admin=is_admin,
                                             read_only=read_only,
                                             show_deleted=False,
                                             request_id=request_id,
                                             roles=roles)
        self.is_admin = 'admin' in roles
        self.project_id = project_id or self.tenant
        if overwrite or not hasattr(context._request_store, 'context'):
            self.update_store()

    def update_store(self):
        context._request_store.context = self


_CTX_STORE = threading.local()
_CTX_KEY = 'current_ctx'


def has_ctx():
    return hasattr(_CTX_STORE, _CTX_KEY)


def ctx():
    if not has_ctx():
        raise exceptions.IncorrectStateError(_("Context isn't available here"))
    return getattr(_CTX_STORE, _CTX_KEY)


def current():
    return ctx()


def set_ctx(new_ctx):
    if not new_ctx and has_ctx():
        delattr(_CTX_STORE, _CTX_KEY)
        if hasattr(context._request_store, 'context'):
            delattr(context._request_store, 'context')

    if new_ctx:
        setattr(_CTX_STORE, _CTX_KEY, new_ctx)
        setattr(context._request_store, 'context', new_ctx)
