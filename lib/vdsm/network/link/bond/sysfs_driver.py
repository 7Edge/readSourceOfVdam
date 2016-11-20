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

from contextlib import contextmanager
import logging
import os

from vdsm.network.link import iface

from . import BondAPI
from . import sysfs_options


class BondSysFS(BondAPI):

    BONDING_MASTERS = '/sys/class/net/bonding_masters'
    BONDING_PATH = '/sys/class/net/%s/bonding'
    BONDING_SLAVES = BONDING_PATH + '/slaves'
    BONDING_ACTIVE_SLAVE = BONDING_PATH + '/active_slave'

    def __init__(self, name, slaves=(), options=None):
        super(BondSysFS, self).__init__(name, slaves, options)

    def __enter__(self):
        self._init_exists = self.exists()
        self._init_slaves = self._slaves
        self._init_options = self._options
        return self

    def __exit__(self, ex_type, ex_value, traceback):
        if ex_type is not None:
            logging.info('Bond {} transaction failed, reverting...'.format(
                self._master))
            self._revert_transaction()

    def create(self):
        with open(self.BONDING_MASTERS, 'w') as f:
            f.write('+%s' % self._master)
        logging.info('Bond {} has been created.'.format(self._master))
        if self._slaves:
            self.add_slaves(self._slaves)

    def destroy(self):
        with open(self.BONDING_MASTERS, 'w') as f:
            f.write('-%s' % self._master)
        logging.info('Bond {} has been destroyed.'.format(self._master))

    def add_slaves(self, slaves):
        for slave in slaves:
            with _preserve_iface_state(slave):
                iface.down(slave)
                with open(self.BONDING_SLAVES % self._master, 'w') as f:
                    f.write('+%s' % slave)
            logging.info('Slave {} has been added to bond {}.'.format(
                slave, self._master))
            self._slaves.add(slave)

    def del_slaves(self, slaves):
        for slave in slaves:
            with _preserve_iface_state(slave):
                iface.down(slave)
                with open(self.BONDING_SLAVES % self._master, 'w') as f:
                    f.write('-%s' % slave)
            logging.info('Slave {} has been removed from bond {}.'.format(
                slave, self._master))
            self._slaves.remove(slave)

    def set_options(self, options):
        self._options = dict(options)
        sysfs_options.set_options(self._master, options)
        logging.info('Bond {} options set: {}.'.format(self._master, options))

    def exists(self):
        return os.path.exists(self.BONDING_PATH % self._master)

    def active_slave(self):
        with open(self.BONDING_ACTIVE_SLAVE % self._master) as f:
            return f.readline().rstrip()

    @staticmethod
    def bonds():
        with open(BondSysFS.BONDING_MASTERS) as f:
            return f.read().rstrip().split()

    def _import_existing(self):
        with open(self.BONDING_SLAVES % self._master) as f:
            self._slaves = set(f.readline().split())
        # TODO: Support options
        self._options = None

    def _revert_transaction(self):
        if self.exists():
            # Did not exist, partially created (some slaves failed to be added)
            if not self._init_exists:
                self.destroy()
            # Existed, failed on some editing (slaves or options editing)
            else:
                slaves2remove = self._slaves - self._init_slaves
                slaves2add = self._init_slaves - self._slaves
                self.del_slaves(slaves2remove)
                self.add_slaves(slaves2add)
                # TODO: Options support
        # We assume that a non existing bond with a failed transaction is not
        # a reasonable scenario and leave it to upper levels to handle it.


@contextmanager
def _preserve_iface_state(dev):
    dev_was_up = iface.is_up(dev)
    try:
        yield
    finally:
        if dev_was_up and not iface.is_up(dev):
            iface.up(dev)


Bond = BondSysFS
