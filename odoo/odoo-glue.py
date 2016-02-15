#!/usr/bin/env python
#
# Copyright 2015 Catalyst IT Ltd
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

import argparse
import collections
import ConfigParser
import datetime
from decimal import Decimal
import math
import oerplib
import os
import prettytable
import re
import six
import sys
import time
import traceback

from keystoneclient.v2_0 import client as keystone_client
import odoorpc
from oslo_utils import importutils
from oslo_utils import strutils
from retrying import retry

from distilclient.client import Client as DistilClient


TENANT = collections.namedtuple('Tenant', ['id', 'name'])
REGION_MAPPING = {'nz_wlg_2': 'NZ-WLG-2', 'nz-por-1': 'NZ-POR-1'}
OERP_PRODUCTS = {}

TRAFFIC_MAPPING = {'n1.international-in': 'Inbound International Traffic',
    'n1.international-out': 'Outbound International Traffic',
    'n1.national-in': 'Inbound National Traffic',
    'n1.national-out': 'Outbound National Traffic'}

def arg(*args, **kwargs):
    def _decorator(func):
        func.__dict__.setdefault('arguments', []).insert(0, (args, kwargs))
        return func
    return _decorator


class OdooShell(object):

    def get_base_parser(self):
            parser = argparse.ArgumentParser(
                prog='odoo-glue',
                description='Odoo glue script for Catalyst Cloud billing.',
                add_help=False,
            )

            # Global arguments
            parser.add_argument('-h', '--help',
                                action='store_true',
                                help=argparse.SUPPRESS,
                                )

            parser.add_argument('-a', '--os-auth-url', metavar='OS_AUTH_URL',
                                type=str, required=False, dest='OS_AUTH_URL',
                                default=os.environ.get('OS_AUTH_URL', None),
                                help='Keystone Authentication URL')

            parser.add_argument('-u', '--os-username', metavar='OS_USERNAME',
                                type=str, required=False, dest='OS_USERNAME',
                                default=os.environ.get('OS_USERNAME', None),
                                help='Username for authentication')

            parser.add_argument('-p', '--os-password', metavar='OS_PASSWORD',
                                type=str, required=False, dest='OS_PASSWORD',
                                default=os.environ.get('OS_PASSWORD', None),
                                help='Password for authentication')

            parser.add_argument('-t', '--os-tenant-name',
                                metavar='OS_TENANT_NAME',
                                type=str, required=False,
                                dest='OS_TENANT_NAME',
                                default=os.environ.get('OS_TENANT_NAME', None),
                                help='Tenant name for authentication')

            parser.add_argument('-r', '--os-region-name',
                                metavar='OS_REGION_NAME',
                                type=str, required=False,
                                dest='OS_REGION_NAME',
                                default=os.environ.get('OS_REGION_NAME', None),
                                help='Region for authentication')

            parser.add_argument('-c', '--os-cacert', metavar='OS_CACERT',
                                dest='OS_CACERT',
                                default=os.environ.get('OS_CACERT'),
                                help='Path of CA TLS certificate(s) used to '
                                'verify the remote server\'s certificate. '
                                'Without this option glance looks for the '
                                'default system CA certificates.')

            parser.add_argument('-k', '--insecure',
                                default=False,
                                action='store_true', dest='OS_INSECURE',
                                help='Explicitly allow script to perform '
                                '\"insecure SSL\" (https) requests. '
                                'The server\'s certificate will not be '
                                'verified against any certificate authorities.'
                                ' This option should be used with caution.')

            parser.add_argument('-d', '--debug',
                                default=False,
                                action='store_true', dest='DEBUG',
                                help='Print the details of running.')

            return parser

    def get_subcommand_parser(self):
        parser = self.get_base_parser()
        self.subcommands = {}
        subparsers = parser.add_subparsers(metavar='<subcommand>')
        submodule = importutils.import_module('odoo-glue')
        self._find_actions(subparsers, submodule)
        self._find_actions(subparsers, self)
        return parser

    def _find_actions(self, subparsers, actions_module):
        for attr in (a for a in dir(actions_module) if a.startswith('do_')):
            command = attr[3:].replace('_', '-')
            callback = getattr(actions_module, attr)
            desc = callback.__doc__ or ''
            help = desc.strip().split('\n')[0]
            arguments = getattr(callback, 'arguments', [])

            subparser = subparsers.add_parser(command,
                                              help=help,
                                              description=desc,
                                              add_help=False,
                                              formatter_class=HelpFormatter
                                              )
            subparser.add_argument('-h', '--help',
                                   action='help',
                                   help=argparse.SUPPRESS,
                                   )
            self.subcommands[command] = subparser
            for (args, kwargs) in arguments:
                subparser.add_argument(*args, **kwargs)
            subparser.set_defaults(func=callback)

    @arg('command', metavar='<subcommand>', nargs='?',
         help='Display help for <subcommand>.')
    def do_help(self, args):
        """Display help about this program or one of its subcommands.

        """
        if getattr(args, 'command', None):
            if args.command in self.subcommands:
                self.subcommands[args.command].print_help()
            else:
                raise Exception("'%s' is not a valid subcommand" %
                                args.command)
        else:
            self.parser.print_help()

    def init_client(self, args):
        try:
            keystone = keystone_client.Client(username=args.OS_USERNAME,
                                              password=args.OS_PASSWORD,
                                              tenant_name=args.OS_TENANT_NAME,
                                              auth_url=args.OS_AUTH_URL,
                                              region_name=args.OS_REGION_NAME,
                                              cacert=args.OS_CACERT,
                                              insecure=args.OS_INSECURE)
            self.keystone = keystone

            for region in REGION_MAPPING.keys():
                d = DistilClient(os_username=args.OS_USERNAME,
                                 os_password=args.OS_PASSWORD,
                                 os_tenant_name=args.OS_TENANT_NAME,
                                 os_auth_url=args.OS_AUTH_URL,
                                 os_region_name=region,
                                 os_cacert=args.OS_CACERT,
                                 insecure=args.OS_INSECURE)
                setattr(self, 'distil' + region.replace('-', '_'), d)

            self.debug = args.DEBUG
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback,
                                      limit=2, file=sys.stdout)
            sys.exit(1)

    def main(self, argv):
        parser = self.get_base_parser()
        (options, args) = parser.parse_known_args(argv)

        subcommand_parser = self.get_subcommand_parser()
        self.parser = subcommand_parser

        if options.help or not argv:
            self.do_help(options)
            return 0

        args = subcommand_parser.parse_args(argv)
        if args.func == self.do_help:
            self.do_help(args)
            return 0

        try:
            self.init_client(args)
            args.func(self, args)
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback,
                                      limit=2, file=sys.stdout)
            sys.exit(1)


class HelpFormatter(argparse.HelpFormatter):
    def start_section(self, heading):
        # Title-case the headings
        heading = '%s%s' % (heading[0].upper(), heading[1:])
        super(HelpFormatter, self).start_section(heading)


@arg('--tenant-id', type=str, metavar='TENANT_ID',
     dest='TENANT_ID', required=False,
     help='The specific tenant which will be quoted.')
@arg('--start', type=str, metavar='START',
     dest='START', required=True,
     help='Start date for quote.')
@arg('--end', type=str, metavar='END',
     dest='END', required=True,
     help='End date for quote.')
@arg('--dry-run', type=bool, metavar='DRY_RUN',
     dest='DRY_RUN', required=False, default=False,
     help='Do not actually create the sales order in Odoo.')
@arg('--audit', type=bool, metavar='AUDIT',
     dest='AUDIT', required=False, default=False,
     help='Do nothing but check if there is out-of-sync between OpenStack'
     ' and OpenERP')
def do_quote(shell, args):
    """
    Iterate all tenants from OpenStack and create sales order in Odoo.
    """
    user_roles = shell.keystone.session.auth.auth_ref['user']['roles']
    if {u'name': u'admin'} not in user_roles:
        print('Admin permission is required.')
        return

    login_odoo(shell)

    done = []
    skip = []

    if not args.TENANT_ID:
        tenants = shell.keystone.tenants.list()

        try:
            with open('done_tenants.txt') as f:
                done = f.read().splitlines()

            with open('skip_tenants.txt') as f:
                skip = f.read().splitlines()
        except IOError:
            pass
    else:
        tenant_object = shell.keystone.tenants.get(args.TENANT_ID)
        tenants = [TENANT(id=args.TENANT_ID, name=tenant_object.name)]

    for tenant in tenants:
        if tenant.id in done and not args.AUDIT:
            print ("Skipping tenant: %s already completed." % tenant.name)
            continue

        if tenant.id in skip and not args.AUDIT:
            print ("Skipping tenant: %s already skipped." % tenant.name)
            continue

        partner = find_oerp_partner_for_tenant(shell, tenant)
        if not partner or args.AUDIT:
            continue
        root_partner = find_root_partner(shell, partner)

        usage = get_tenant_usage(shell, tenant.id, args.START, args.END)
        if not usage:
            continue

        pricelist, _ = root_partner['property_product_pricelist']
        try:
            build_sales_order(shell, args, pricelist, usage, partner,
                              tenant.name, tenant.id)
        except Exception as e:
            print "Failed to create sales order for tenant: %s" % tenant.name
            with open('failed_tenants.txt', 'a') as f:
                f.write(tenant.id + "\n")
            raise e

        with open('done_tenants.txt', 'a') as f:
            f.write(tenant.id + "\n")


def find_oerp_partner_for_tenant(shell, tenant):
    try:
        tenant_obj_ids = shell.Tenant.search([('tenant_id', '=', tenant.id)])

        if len(tenant_obj_ids) != 1:
            print('ERROR: tenant %s, %s is not set up in OpenERP.' %
                  (tenant.id, tenant.name))
            return

        tenant_obj = shell.Tenant.read(tenant_obj_ids[0])

        return shell.Partner.read(tenant_obj['partner_id'][0])
    except odoorpc.error.RPCError as e:
        print(e.info)
        raise


def find_root_partner(shell, partner):
    while partner['parent_id']:
        parent_id, parent_name = partner['parent_id']
        log(shell.debug,
            'Walking to parent of [%s,%s]: [%s,%s] to find pricelist' % (
                partner['id'], partner['name'],
                parent_id, parent_name))

        partner = shell.Partner.read(parent_id)

    return partner


def find_oerp_product(shell, region, name):
    product_name = '%s.%s' % (REGION_MAPPING[region], name)
    if product_name not in OERP_PRODUCTS:
        log(shell.debug, 'Looking up product in oerp: %s' % product_name)

        ps = shell.Product.search([('name_template', '=', product_name),
                                   ('sale_ok', '=', True),
                                   ('active', '=', True)])
        if len(ps) > 1:
            print('WARNING: %d products found for %s' % (len(ps),
                                                         product_name))

        if len(ps) == 0:
            print('ERROR: no matching product for %s' % product_name)
            return None

        OERP_PRODUCTS[product_name] = shell.Product.read(ps[0])

    return OERP_PRODUCTS[product_name]


def get_tenant_usage(shell, tenant, start, end):
    usage = []
    for region in REGION_MAPPING.keys():
        distil_client = getattr(shell, 'distil' + region.replace('-', '_'))
        raw_usage = distil_client.get_usage(tenant, start, end)

        if not raw_usage:
            return None

        traffic = {'n1.national-in': 0,
                   'n1.national-out': 0,
                   'n1.international-in': 0,
                   'n1.international-out': 0}

        for res_id, res in raw_usage['usage']['resources'].items():
            for service_usage in res['services']:
                if service_usage['volume'] == 'unknown unit conversion':
                    print('WARNING: Bogus unit: %s' % res.get('type'))
                    continue

                if service_usage['name'] == 'bandwidth':
                    #print('WARNING: Metering data for bandwidth; unsupported')
                    continue

                # server-side rater is broken so do it here.
                if service_usage['unit'] == 'byte':
                    v = Decimal(service_usage['volume'])
                    service_usage['unit'] = 'gigabyte'
                    service_usage['volume'] = str(v /
                                                  Decimal(1024 * 1024 * 1024))

                if service_usage['unit'] == 'second':
                    # convert seconds to hours, rounding up.
                    v = Decimal(service_usage['volume'])
                    service_usage['unit'] = 'hour'
                    service_usage['volume'] = str(math.ceil(v /
                                                            Decimal(60 * 60)))

                # drop zero usages.
                if not Decimal(service_usage['volume']):
                    print('WARNING: Dropping 0-volume line: %s' %
                          (service_usage,))
                    continue

                if Decimal(service_usage['volume']) <= 0.00001:
                    # Precision threshold for volume.
                    print('WARNING: Dropping 0.00001-volume line: %s' %
                          (service_usage,))
                    continue

                name = res.get('name', res.get('ip address', ''))
                if name == '':
                    name = res_id

                if service_usage['name'] in ('n1.national-in',
                                             'n1.national-out',
                                             'n1.international-in',
                                             'n1.international-out'):
                    #print('WARNING: We will skip traffic billing for now.')
                    traffic[service_usage['name']] += float(service_usage['volume'])
                else:
                    usage.append({'product': service_usage['name'],
                                  'name': name,
                                  'volume': float(service_usage['volume']),
                                  'region': region})

        # Aggregate traffic data
        for type, volume in traffic.items():
            print('Region: %s, traffic type: %s, volume: %s' %
                  (region, type, str(volume)))
            usage.append({'product': type,
                          'name': TRAFFIC_MAPPING[type],
                          'volume': math.floor(volume),
                          'region': region})

    return wash_usage(usage, start, end)


def wash_usage(usage, start, end):
    """Wash the usage data to filter something we want to skip/cost-free"""
    if not usage:
        return
    start = time.mktime(time.strptime(start, '%Y-%m-%dT%H:%M:%S'))
    end = time.mktime(time.strptime(end, '%Y-%m-%dT%H:%M:%S'))
    free_hours = (end - start) / 3600

    network_hours = 0
    router_hours = 0
    region = 'nz_wlg_2'
    for u in usage:
        if u['product'] == 'n1.network':
            network_hours += u['volume']

        if u['product'] == 'n1.router':
            router_hours += u['volume']
            # TODO(flwang): Any region is ok for the discount for now, given
            # we're using same price for different region. But we may need
            # better way in the future. And at least one network and one
            # router are in the same region. So it should be safe to use it
            # for displaying the discount line item.
            # A special case is user has two network/router in two different
            # regions and either of them are not used full month, so at that
            # case, user maybe see the discount line item is placed at one of
            # regions, but the number should be correct.
            region = u['region']

    free_network_hours = (network_hours if network_hours <= free_hours
                          else free_hours)
    if free_network_hours:
        usage.append({'product': 'n1.network', 'name': 'FREE NETWORK TIER',
                      'volume': -free_network_hours, 'region': region})

    free_router_hours = (router_hours if router_hours <= free_hours
                         else free_hours)
    if free_router_hours:
        usage.append({'product': 'n1.router', 'name': 'FREE ROUTER TIER',
                      'volume': -free_router_hours, 'region': region})

    return usage


def get_price(shell, pricelist, product, volume):
    price = shell.Pricelist.price_get([pricelist], product['id'],
                                      volume if volume >= 0
                                      else 0)[str(pricelist)]

    return price if volume >= 0 else -price


@retry(stop_max_attempt_number=3, wait_fixed=1000)
def build_sales_order(shell, args, pricelist, usage, partner, tenant_name,
                      tenant_id):
    end_timestamp = datetime.datetime.strptime(args.END, '%Y-%m-%dT%H:%M:%S')
    billing_date = str((end_timestamp - datetime.timedelta(days=1)).date())

    try:
        # Pre check, fetch all the products first.
        for m in usage:
            if not find_oerp_product(shell, m['region'], m['product']):
                sys.exit(1)
    except Exception as e:
        print(e.info)
        raise

    log(shell.debug, 'Building sale.order')
    try:
        order_dict = {
            'partner_id': partner['id'],
            'pricelist_id': pricelist,
            'partner_invoice_id': partner['id'],
            'partner_shipping_id': partner['id'],
            'order_date': billing_date,
            'note': 'Tenant: %s (%s)' % (tenant_name, tenant_id),
            'section_id': 10,
        }
        order = 'DRY_RUN_MODE'
        print_dict(order_dict)

        if not args.DRY_RUN:
            order = shell.Order.create(order_dict)
            shell.order_id = order
            print('Order id: %s' % order)

        # Sort by product
        usage_dict_list = []
        for m in sorted(usage, key=lambda m: m['product']):
            prod = find_oerp_product(shell, m['region'], m['product'])

            # TODO(flwang): 1. select the correct unit; 2. map via position
            usage_dict = {
                'order_id': order,
                'product_id': prod['id'],
                'product_uom': prod['uom_id'][0],
                'product_uom_qty': math.fabs(m['volume']),
                'name': m['name'],
                'price_unit': get_price(shell, pricelist, prod, m['volume'])
            }
            if usage_dict['product_uom_qty'] < 0.005:
                # Odoo will round the product_uom_qty and if it's under 0.0005
                # then it would be rounded to 0 and as a result the quoting
                # will fail.
                print('%s is too small.' % str(usage_dict['product_uom_qty']))
                continue

            usage_dict_list.append(usage_dict)

            if not args.DRY_RUN:
                shell.Orderline.create(usage_dict)

        print_list(
            usage_dict_list,
            ['product_id', 'product_uom', 'product_uom_qty', 'name',
             'price_unit']
        )

        shell.order_id = None
    except odoorpc.error.RPCError as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback,
                                  limit=2, file=sys.stdout)
        print(e.info)

        # Cancel the quotation.
        if shell.order_id:
            print('Cancel order: %s' % shell.order_id)
            update_order_status(shell, shell.order_id)

        raise e
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback,
                                  limit=2, file=sys.stdout)
        print(e)
        raise e


def dump_all(shell, model, fields):
    """Only for debug """
    print('%s:' % model)
    ids = shell.oerp.search(model, [])
    for _id in ids:
        obj = shell.oerp.read(model, _id)
        print(' %s %s' % (_id, {f: obj[f] for f in fields}))


def log(debug, msg):
    """A tiny log method to print running details."""
    if debug:
        print(msg)


def print_list(objs, fields, formatters={}):
    pt = prettytable.PrettyTable([f for f in fields], caching=False)
    pt.align = 'l'

    for o in objs:
        row = []
        for field in fields:
            if field in formatters:
                row.append(formatters[field](o))
            else:
                field_name = field.lower().replace(' ', '_')
                if type(o) == dict and field in o:
                    data = o[field_name]
                else:
                    data = getattr(o, field_name, None) or ''
                row.append(data)
        pt.add_row(row)

    print(strutils.encodeutils.safe_encode((pt.get_string())))


def login_odoo(shell):
    conf = ConfigParser.ConfigParser()
    conf.read(['glue.ini'])

    shell.oerp = odoorpc.ODOO(conf.get('odoo', 'hostname'),
                              protocol=conf.get('odoo', 'protocol'),
                              port=conf.getint('odoo', 'port'),
                              version=conf.get('odoo', 'version'))

    shell.oerp.login(conf.get('odoo', 'database'),
                     conf.get('odoo', 'user'),
                     conf.get('odoo', 'password'))

    shell.Order = shell.oerp.env['sale.order']
    shell.Orderline = shell.oerp.env['sale.order.line']
    shell.Tenant = shell.oerp.env['cloud.tenant']
    shell.Partner = shell.oerp.env['res.partner']
    shell.Pricelist = shell.oerp.env['product.pricelist']
    shell.Product = shell.oerp.env['product.product']


def check_duplicate(order):
    return False


def update_order_status(shell, order_id, new_status='cancel'):
    print('Processing order: %s' % order_id)

    order = shell.Order.browse(order_id)

    # Just a placeholder for further improvement.
    is_dup = check_duplicate(order)
    if not is_dup:
        print "changing state: %s -> %s" % (order.state, new_status)
        # By default when updating values of a record, the change is
        # automatically sent to the server.
        order.state = new_status


@arg('--new-status', '-s', type=str, metavar='STATUS',
     dest='STATUS', required=True,
     choices=['manual', 'cancel', 'draft'],
     help='The new status of the quotation.')
@arg('--company', '-c', type=str, metavar='COMPANY',
     dest='COMPANY', required=False,
     help='Company of the quotation customer to filter with.')
@arg('--tenant-id', '-t', type=str, metavar='TENANT_ID',
     dest='TENANT_ID', required=False,
     help='Tenant of quotations to filter with.')
@arg('--id', type=str, metavar='ORDER_ID',
     dest='ORDER_ID', required=False,
     help='Order ID to update. If it is given, COMPANY and TENANT_ID will be'
          'ignored. NOTE: This is NOT the Quotation Number.')
def do_update_quote(shell, args):
    """Updates quotations."""
    login_odoo(shell)

    if args.ORDER_ID:
        creterion = [('id', '=', args.ORDER_ID)]
    else:
        creterion = [('state', '=', 'draft')]
        if args.COMPANY:
            creterion.append(('company_id.name', 'ilike', args.COMPANY))
        if args.TENANT_ID:
            tenant_object = shell.keystone.tenants.get(args.TENANT_ID)
            partner = find_oerp_partner_for_tenant(shell, tenant_object)
            creterion.append(('partner_id', '=', partner['id']))

    ids = shell.Order.search(creterion)
    for id in ids:
        try:
            update_order_status(shell, id, args.STATUS)
        except odoorpc.error.RPCError as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback,
                                      limit=2, file=sys.stdout)
            print(e.info)
            print('Failed to update order: %s' % id)
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback,
                                      limit=2, file=sys.stdout)
            print(e)
            print('Failed to update order: %s' % id)


def print_dict(d, max_column_width=80):
    pt = prettytable.PrettyTable(['Property', 'Value'], caching=False)
    pt.align = 'l'
    pt.max_width = max_column_width
    [pt.add_row(list(r)) for r in six.iteritems(d)]
    print(strutils.encodeutils.safe_encode(pt.get_string(sortby='Property')))


if __name__ == '__main__':
    try:
        OdooShell().main(sys.argv[1:])
    except KeyboardInterrupt:
        print("Terminating...")
        sys.exit(1)
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback,
                                  limit=2, file=sys.stdout)
