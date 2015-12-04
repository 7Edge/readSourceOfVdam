#
# Copyright 2015 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#
from __future__ import absolute_import
import copy
import netaddr
import string

from .netinfo import addresses
from .netinfo import bonding
from .netinfo import bridges
from .netinfo import mtus
from . import utils
from .netconfpersistence import BaseConfig


class KernelConfig(BaseConfig):
    # TODO: after the netinfo API is refactored, we should decide if we need
    # TODO: the dependency of KernelConfig in a NetInfo object.
    # TODO: The only real dependency is on the products of
    # TODO: NetInfo.getNicsVlanAndBondingForNetwork and on NetInfo.Bondings
    def __init__(self, netinfo):
        super(KernelConfig, self).__init__({}, {})
        self._netinfo = netinfo
        for net, net_attr in self._analyze_netinfo_nets(netinfo):
            self.setNetwork(net, net_attr)
        for bond, bond_attr in self._analyze_netinfo_bonds(netinfo):
            self.setBonding(bond, bond_attr)

    def __eq__(self, other):
        normalized_other = normalize(other)
        return (self.networks == normalized_other.networks
                and self.bonds == normalized_other.bonds)

    def _analyze_netinfo_nets(self, netinfo):
        for net, net_attr in netinfo.networks.iteritems():
            yield net, _translate_netinfo_net(net, net_attr, netinfo)

    def _analyze_netinfo_bonds(self, netinfo):
        for bond, bond_attr in netinfo.bondings.iteritems():
            yield bond, _translate_netinfo_bond(bond_attr)


def normalize(running_config):
    config_copy = copy.deepcopy(running_config)

    _normalize_bridge(config_copy)
    _normalize_vlan(config_copy)
    _normalize_mtu(config_copy)
    _normalize_blockingdhcp(config_copy)
    _normalize_dhcp(config_copy)
    _normalize_bonding_opts(config_copy)
    _normalize_bonding_nics(config_copy)
    _normalize_address(config_copy)
    _normalize_ifcfg_keys(config_copy)

    return config_copy


def _translate_netinfo_net(net, net_attr, netinfo_):
    nics, _, vlan_id, bond = \
        netinfo_.getNicsVlanAndBondingForNetwork(net)
    attributes = {}
    _translate_bridged(attributes, net_attr)
    _translate_mtu(attributes, net_attr)
    _translate_vlan(attributes, vlan_id)
    if bond:
        _translate_bonding(attributes, bond)
    elif nics:
        _translate_nics(attributes, nics)
    _translate_ipaddr(attributes, net_attr)
    _translate_hostqos(attributes, net_attr)

    return attributes


def _translate_ipaddr(attributes, net_attr):
    attributes['bootproto'] = 'dhcp' if net_attr['dhcpv4'] else 'none'
    attributes['dhcpv6'] = net_attr['dhcpv6']
    ifcfg = net_attr.get('cfg')
    # TODO: we must not depend on 'cfg', which is configurator-dependent.
    # TODO: Look up in the routing table instead.
    if ifcfg and ifcfg.get('DEFROUTE') == 'yes':
        attributes['defaultRoute'] = True
    else:
        attributes['defaultRoute'] = False
    # only static addresses are part of {Persistent,Running}Config.
    if attributes['bootproto'] == 'none':
        if net_attr['addr']:
            attributes['ipaddr'] = net_attr['addr']
        if net_attr['netmask']:
            attributes['netmask'] = net_attr['netmask']
        if net_attr['gateway']:
            attributes['gateway'] = net_attr['gateway']
    if not attributes['dhcpv6']:
        non_local_addresses = _translate_ipv6_addr(net_attr['ipv6addrs'])
        if non_local_addresses:
            attributes['ipv6addr'] = non_local_addresses
        if net_attr['ipv6gateway'] != '::':
            attributes['ipv6gateway'] = net_attr['ipv6gateway']


def _translate_ipv6_addr(ipv6_addrs):
    return [
        addr for addr in ipv6_addrs
        if not netaddr.IPAddress(addr.split('/')[0]).is_link_local()]


def _translate_nics(attributes, nics):
    nic, = nics
    attributes['nic'] = nic


def _translate_bonding(attributes, bond):
    attributes['bonding'] = bond


def _translate_vlan(attributes, vlan):
    if vlan is not None:
        attributes['vlan'] = str(vlan)


def _translate_mtu(attributes, net_attr):
    attributes['mtu'] = net_attr['mtu']


def _translate_bridged(attributes, net_attr):
    attributes['bridged'] = net_attr['bridged']
    if net_attr['bridged']:
        attributes['stp'] = bridges.stp_booleanize(net_attr['stp'])


def _translate_netinfo_bond(bond_attr):
    return {
        'nics': sorted(bond_attr['slaves']),
        'options': bonding.bondOptsForIfcfg(bond_attr['opts'])
    }


def _translate_hostqos(attributes, net_attr):
    if net_attr.get('hostQos'):
        attributes['hostQos'] = _remove_zero_values_in_net_qos(
            net_attr['hostQos'])


def _remove_zero_values_in_net_qos(net_qos):
    """
    net_qos = {'out': {
            'ul': {'m1': 0, 'd': 0, 'm2': 8000000},
            'ls': {'m1': 4000000, 'd': 100000, 'm2': 3000000}}}
    stripped_qos = {'out': {
            'ul': {'m2': 8000000},
            'ls': {'m1': 4000000, 'd': 100000, 'm2': 3000000}}}"""
    stripped_qos = {}
    for part, part_config in net_qos.iteritems():
        stripped_qos[part] = dict(part_config)  # copy
        for curve, curve_config in part_config.iteritems():
            stripped_qos[part][curve] = dict((k, v) for k, v
                                             in curve_config.iteritems()
                                             if v != 0)
    return stripped_qos


def _normalize_stp(net_attr):
    stp = net_attr.pop('stp', net_attr.pop('STP', None))
    net_attr['stp'] = bridges.stp_booleanize(stp)


def _normalize_vlan(config_copy):
    for net_attr in config_copy.networks.itervalues():
        if 'vlan' in net_attr:
            net_attr['vlan'] = str(net_attr['vlan'])


def _normalize_bridge(config_copy):
    for net_attr in config_copy.networks.itervalues():
        if utils.tobool(net_attr.get('bridged', True)):
            net_attr['bridged'] = True
            _normalize_stp(net_attr)
        else:
            net_attr['bridged'] = False


def _normalize_mtu(config_copy):
    for net_attr in config_copy.networks.itervalues():
        if 'mtu' in net_attr:
            net_attr['mtu'] = str(net_attr['mtu'])
        else:
            net_attr['mtu'] = mtus.DEFAULT_MTU


def _normalize_blockingdhcp(config_copy):
    for net_attr in config_copy.networks.itervalues():
        if 'blockingdhcp' in net_attr:
            net_attr.pop('blockingdhcp')


def _normalize_dhcp(config_copy):
    for net_attr in config_copy.networks.itervalues():
        dhcp = net_attr.get('bootproto')
        if dhcp is None:
            net_attr['bootproto'] = 'none'
        else:
            net_attr['bootproto'] = dhcp
        net_attr['dhcpv6'] = net_attr.get('dhcpv6', False)
    return config_copy


def _normalize_bonding_opts(config_copy):
    for bond, bond_attr in config_copy.bonds.iteritems():
        # TODO: globalize default bond options from Bond in models.py
        normalized_opts = _parse_bond_options(
            bond_attr.get('options'))
        normalized_opts.pop('custom', None)
        bond_attr['options'] = bonding.bondOptsForIfcfg(normalized_opts)
    # before d18e2f10 bondingOptions were also part of networks, so in case
    # we are upgrading from an older version, they should be ignored if
    # they exist.
    # REQUIRED_FOR upgrade from vdsm<=4.16.20
    for net_attr in config_copy.networks.itervalues():
        net_attr.pop('bondingOptions', None)


def _normalize_bonding_nics(config_copy):
    for bond_attr in config_copy.bonds.itervalues():
        if 'nics' in bond_attr:
            bond_attr['nics'].sort()


def _normalize_address(config_copy):
    for net_attr in config_copy.networks.itervalues():
        prefix = net_attr.pop('prefix', None)
        if prefix is not None:
            net_attr['netmask'] = addresses.prefix2netmask(int(prefix))
        if 'ipv6addr' in net_attr:
            net_attr['ipv6addr'] = [net_attr['ipv6addr']]
        if 'defaultRoute' not in net_attr:
            net_attr['defaultRoute'] = False


def _normalize_ifcfg_keys(config_copy):
    # ignore keys in persisted networks that might originate from vdsm-reg.
    # these might be a result of calling setupNetworks with ifcfg values
    # that come from the original interface that is serving the management
    # network. for 3.5, VDSM still supports passing arbitrary values
    # directly to the ifcfg files, e.g. 'IPV6_AUTOCONF=no'. we filter them
    # out here since kernelConfig will never report them.
    # TODO: remove when 3.5 is unsupported.
    def unsupported(key):
        return set(key) <= set(
            string.ascii_uppercase + string.digits + '_')

    for net_attr in config_copy.networks.itervalues():
        for k in net_attr.keys():
            if unsupported(k):
                net_attr.pop(k)


def _parse_bond_options(opts):
    if not opts:
        return {}

    opts = dict((pair.split('=', 1) for pair in opts.split()))

    # force a numeric bonding mode
    mode = opts.get('mode',
                    bonding.getAllDefaultBondingOptions()['0']['mode'][-1])
    if mode in bonding.BONDING_MODES_NUMBER_TO_NAME:
        numeric_mode = mode
    else:
        numeric_mode = bonding.BONDING_MODES_NAME_TO_NUMBER[mode]
        opts['mode'] = numeric_mode

    defaults = bonding.getDefaultBondingOptions(numeric_mode)
    return dict(
        (k, v) for k, v in opts.iteritems() if v != defaults.get(k))
