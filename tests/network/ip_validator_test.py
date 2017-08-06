# Copyright 2016 Red Hat, Inc.
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

from nose.plugins.attrib import attr

from testlib import VdsmTestCase, mock

from vdsm.network import errors as ne
from vdsm.network.ip import validator


class DummyRunningConfig(object):
    networks = {}


@attr(type='unit')
@mock.patch.object(validator, 'RunningConfig', DummyRunningConfig)
class TestIPNameserverValidator(VdsmTestCase):

    def test_ignore_remove_networks(self):
        validator.validate({'NET0': {'remove': True,
                                     'defaultRoute': False,
                                     'nameservers': ['8.8.8.8']}})

    def test_nameserver_defined_on_a_non_primary_network_fails(self):
        with self.assertRaises(ne.ConfigNetworkError) as cne:
            validator.validate({'NET0': {'defaultRoute': False,
                                         'nameservers': ['8.8.8.8']}})
        self.assertEqual(cne.exception.errCode, ne.ERR_BAD_PARAMS)

    def test_nameserver_faulty_ipv4_address(self):
        with self.assertRaises(ne.ConfigNetworkError) as cne:
            validator.validate({'NET0': {'defaultRoute': True,
                                         'nameservers': ['a.8.8.8']}})
        self.assertEqual(cne.exception.errCode, ne.ERR_BAD_ADDR)

    def test_nameserver_faulty_ipv6_address(self):
        with self.assertRaises(ne.ConfigNetworkError) as cne:
            validator.validate({'NET0': {'defaultRoute': True,
                                         'nameservers': ['2001:bla::1']}})
        self.assertEqual(cne.exception.errCode, ne.ERR_BAD_ADDR)

    def test_nameserver_valid_ipv4_address(self):
        validator.validate({'NET0': {'defaultRoute': True,
                                     'nameservers': ['8.8.8.8']}})

    def test_nameserver_valid_ipv6_address(self):
        validator.validate({'NET0': {'defaultRoute': True,
                                     'nameservers': ['2001::1']}})

    def test_nameserver_address_with_zone_identifier(self):
        validator.validate({'NET0': {'defaultRoute': True,
                                     'nameservers': ['fe80::1%eth1']}})


@attr(type='unit')
@mock.patch.object(validator, 'RunningConfig')
class TestIPDefaultRouteValidator(VdsmTestCase):

    def test_request_one_defroute_no_existing_defroute(self, mockRConfig):
        mockRConfig.return_value.networks = {}
        validator.validate({'NET0': {'defaultRoute': True,
                                     'nameservers': ['8.8.8.8']}})

    def test_request_no_defroute_no_existing_defroute(self, mockRConfig):
        mockRConfig.return_value.networks = {
            'NET88': {'defaultRoute': False, 'nameservers': []}}

        validator.validate({'NET0': {'defaultRoute': False,
                                     'nameservers': []}})

    def test_request_one_defroute_existing_same_defroute(self, mockRConfig):
        netname = 'NET0'
        mockRConfig.return_value.networks = {
            netname: {'defaultRoute': True, 'nameservers': ['8.8.8.8']}}

        validator.validate({netname: {'defaultRoute': True,
                                      'nameservers': ['8.8.8.8']}})

    def test_request_one_defroute_removing_existing_different_defroute(
            self, mockRConfig):
        mockRConfig.return_value.networks = {
            'NET88': {'defaultRoute': True, 'nameservers': ['8.8.8.8']}}

        validator.validate({'NET0': {'defaultRoute': True,
                                     'nameservers': ['8.8.8.8']},
                            'NET88': {'defaultRoute': False,
                                      'nameservers': []}})

    def test_request_multi_defroute(self, mockRConfig):
        mockRConfig.return_value.networks = {}
        with self.assertRaises(ne.ConfigNetworkError):
            validator.validate({'NET0': {'defaultRoute': True,
                                         'nameservers': ['8.8.8.8']},
                                'NET88': {'defaultRoute': True,
                                          'nameservers': ['8.8.8.8']}})

    def test_request_one_defroute_existing_different_defroute(self,
                                                              mockRConfig):
        mockRConfig.return_value.networks = {
            'NET88': {'defaultRoute': True, 'nameservers': ['8.8.8.8']}}

        with self.assertRaises(ne.ConfigNetworkError):
            validator.validate({'NET0': {'defaultRoute': True,
                                         'nameservers': ['8.8.8.8']}})

    def test_request_multi_defroute_removing_existing_different_defroute(
            self, mockRConfig):
        mockRConfig.return_value.networks = {
            'NET88': {'defaultRoute': True, 'nameservers': ['8.8.8.8']}}

        with self.assertRaises(ne.ConfigNetworkError):
            validator.validate({'NET0': {'defaultRoute': True,
                                         'nameservers': ['8.8.8.8']},
                                'NET88': {'defaultRoute': False,
                                          'nameservers': []},
                                'NET99': {'defaultRoute': True,
                                          'nameservers': ['8.8.8.8']}})


@attr(type='unit')
class TestStaticIpv4ConfigValidator(VdsmTestCase):

    def test_ip_address_without_netmask_fails(self):
        self._test_ip_config_fails(ipaddr='10.10.10.10')

    def test_gateway_without_ip_address_fails(self):
        self._test_ip_config_fails(gateway='10.10.10.1')

    def test_netmask_without_ip_address_fails(self):
        self._test_ip_config_fails(netmask='255.255.255.0')

    def test_invalid_ip_address_fails(self):
        self._test_ip_config_fails(ipaddr='10.10.10.10.10',
                                   netmask='255.255.255.0')

    def test_invalid_netmask_fails(self):
        self._test_ip_config_fails(ipaddr='10.10.10.10',
                                   netmask='355.255.255.0')

    def test_invalid_gateway_fails(self):
        self._test_ip_config_fails(ipaddr='10.10.10.10',
                                   netmask='255.255.255.0',
                                   gateway='abcdef')

    def test_static_and_dhcp_mix_fails(self):
        self._test_ip_config_fails(ipaddr='10.10.10.10',
                                   netmask='255.255.255.0',
                                   bootproto='dhcp')

    def test_config_without_gateway(self):
        STATIC_CONFIG = dict(ipaddr='10.10.10.10',
                             netmask='255.255.255.0')
        validator.validate_static_ipv4_config(STATIC_CONFIG)

    def test_config_with_gateway(self):
        STATIC_CONFIG = dict(ipaddr='10.10.10.10',
                             netmask='255.255.255.0',
                             gateway='10.10.10.1')
        validator.validate_static_ipv4_config(STATIC_CONFIG)

    def _test_ip_config_fails(self, **setup):
        with self.assertRaises(ne.ConfigNetworkError) as cne:
            validator.validate_static_ipv4_config(setup)
        self.assertEqual(cne.exception.errCode, ne.ERR_BAD_ADDR)
