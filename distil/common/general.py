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

from datetime import datetime
from datetime import timedelta
from decimal import Decimal
import functools
import math
import socket
import warnings
import yaml

from oslo_config import cfg
from oslo_log import log as logging

from distil.common import constants
from distil.db import api as db_api
from distil import exceptions

CONF = cfg.CONF
LOG = logging.getLogger(__name__)
_TRANS_CONFIG = None


def get_transformer_config(name):
    global _TRANS_CONFIG

    if not _TRANS_CONFIG:
        try:
            with open(CONF.collector.transformer_file) as f:
                _TRANS_CONFIG = yaml.safe_load(f)
        except IOError as e:
            raise e

    return _TRANS_CONFIG.get(name, {})


def get_windows(start, end):
    """Get configured hour windows in a given range."""
    windows = []
    window_size = timedelta(hours=CONF.collector.collect_window)

    while start + window_size <= end:
        window_end = start + window_size
        windows.append((start, window_end))

        if len(windows) >= CONF.collector.max_windows_per_cycle:
            break

        start = window_end

    return windows


def log_and_time_it(f):
    def decorator(*args, **kwargs):
        start = datetime.utcnow()
        LOG.info('Entering %s at %s' % (f.__name__, start))
        f(*args, **kwargs)
        LOG.info('Exiting %s at %s, elapsed %s' % (f.__name__,
                                                   datetime.utcnow(),
                                                   datetime.utcnow() - start))
    return decorator


def disable_ssl_warnings(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="A true SSLContext object is not available"
            )
            warnings.filterwarnings(
                "ignore",
                message="Unverified HTTPS request is being made"
            )
            return func(*args, **kwargs)

    return wrapper


def to_gigabytes_from_bytes(value):
    """From Bytes, unrounded."""
    return ((value / Decimal(1024)) / Decimal(1024)) / Decimal(1024)


def to_hours_from_seconds(value):
    """From seconds to rounded hours."""
    return Decimal(math.ceil((value / Decimal(60)) / Decimal(60)))


conversions = {'byte': {'gigabyte': to_gigabytes_from_bytes},
               'second': {'hour': to_hours_from_seconds}}


def convert_to(value, from_unit, to_unit):
    """Converts a given value to the given unit.
       Assumes that the value is in the lowest unit form,
       of the given unit (seconds or bytes).
       e.g. if the unit is gigabyte we assume the value is in bytes
       """
    if from_unit == to_unit:
        return value
    if from_unit not in conversions:
        raise ValueError(
            (
                "Unsupported unit '{}' "
                "(when trying to convert to unit '{}')"
            ).format(from_unit, to_unit),
        )
    elif to_unit not in conversions[from_unit]:
        raise ValueError(
            "Unable to convert from unit '{}' to unit '{}'".format(
                from_unit,
                to_unit,
            ),
        )
    return conversions[from_unit][to_unit](value)


def get_process_identifier():
    """Gets current running process identifier."""
    return "%s_%s" % (socket.gethostname(), CONF.collector.partitioning_suffix)


def convert_project_and_range(project_id, start, end):
    now = datetime.utcnow()

    try:
        if start is not None:
            try:
                start = datetime.strptime(start, constants.iso_date)
            except ValueError:
                start = datetime.strptime(start, constants.iso_time)
        else:
            raise exceptions.DateTimeException(
                message=(
                    "Missing parameter:" +
                    "'start' in format: y-m-d or y-m-dTH:M:S"))
        if not end:
            end = now
        else:
            try:
                end = datetime.strptime(end, constants.iso_date)
            except ValueError:
                end = datetime.strptime(end, constants.iso_time)

            if end > now:
                end = now
    except ValueError:
        raise exceptions.DateTimeException(
            message=(
                "Missing parameter: " +
                "'end' in format: y-m-d or y-m-dTH:M:S"))

    if end <= start:
        raise exceptions.DateTimeException(
            message="End date must be greater than start.")

    if not project_id:
        raise exceptions.NotFoundException("Missing parameter: project_id")

    valid_project = db_api.project_get(project_id)

    return valid_project, start, end
