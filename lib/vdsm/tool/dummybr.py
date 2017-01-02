# Copyright 2012 Red Hat, Inc.
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
import os

from vdsm.network.netinfo import DUMMY_BRIDGE
from .. import libvirtconnection, commands, constants
from . import expose, ExtraArgsError


def createEphemeralBridge(bridgeName):
    rc, out, err = commands.execCmd([constants.EXT_BRCTL, 'addbr', bridgeName])
    if rc != 0:
        raise EnvironmentError(
            'Failed to create ephemeral dummy bridge. Err: %s' % err
        )


def addBridgeToLibvirt(bridgeName):
    conn = libvirtconnection.get(None, False)
    if bridgeName not in conn.listNetworks():
        conn.networkCreateXML(
            '''<network><name>%s</name><forward mode='bridge'/><bridge '''
            '''name='%s'/></network>''' % (bridgeName, bridgeName))


@expose('dummybr')
def main(*args):
    """
    dummybr
    Defines dummy bridge on libvirt network.
    """

    if len(args) > 1:
        raise ExtraArgsError()

    if not os.path.exists('/sys/class/net/%s' % DUMMY_BRIDGE):
        createEphemeralBridge(DUMMY_BRIDGE)
    addBridgeToLibvirt(DUMMY_BRIDGE)
