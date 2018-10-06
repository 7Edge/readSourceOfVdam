#
# Copyright 2014-2016 Red Hat, Inc.
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#

from __future__ import absolute_import
from __future__ import division
from time import sleep
import os

from subprocess import Popen
from testlib import VdsmTestCase

from vdsm.common import zombiereaper


class zombieReaperTests(VdsmTestCase):

    def setUp(self):
        zombiereaper.registerSignalHandler()

    def tearDown(self):
        zombiereaper.unregisterSignalHandler()

    def testProcessDiesAfterBeingTracked(self):
        p = Popen(["sleep", "1"])
        zombiereaper.autoReapPID(p.pid)
        # wait for the grim reaper to arrive
        sleep(4)

        # Throws error because pid is not found or is not child
        self.assertRaises(OSError, os.waitpid, p.pid, os.WNOHANG)

    def testProcessDiedBeforeBeingTracked(self):
        p = Popen(["sleep", "0"])
        # wait for the process to die
        sleep(1)

        zombiereaper.autoReapPID(p.pid)

        # Throws error because pid is not found or is not child
        self.assertRaises(OSError, os.waitpid, p.pid, os.WNOHANG)


class RegisterTests(VdsmTestCase):

    # testrunner calls zombiereaper.registerSignalHandler so for testing
    # purposes unregisterSignalHandler is called.
    def setUp(self):
        self.unregistered = True
        if zombiereaper._registered:
            self.unregistered = True
            zombiereaper.unregisterSignalHandler()

    def tearDown(self):
        if self.unregistered:
            zombiereaper.registerSignalHandler()

    def testUnregistered(self):
        self.assertRaises(RuntimeError, zombiereaper.autoReapPID, 12345)
