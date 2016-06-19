#
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#

from __future__ import absolute_import

from collections import namedtuple

from . import utils
from . import cpuarch


_PATH = '/proc/cpuinfo'
CpuInfo = namedtuple('CpuInfo', 'flags, frequency, model, ppcmodel, platform,'
                     'machine')


@utils.memoized
def _cpuinfo():
    '''
    Parse cpuinfo-like file, keeping the values in module's runtime variables.

    Arguments:

    source      Optional. Accepts a string indicating path to the cpuinfo-like
                file. If not supplied, default path (/proc/cpuinfo) is used.
    '''
    fields = {}

    if cpuarch.is_ppc(cpuarch.real()):
        fields['flags'] = ['powernv']
    if cpuarch.is_x86(cpuarch.real()):
        fields['platform'] = 'unavailable'
        fields['machine'] = 'unavailable'
        fields['ppcmodel'] = 'unavailable'

    with open(_PATH) as info:
        for line in info:
            if not line.strip():
                continue

            key, value = [part.strip() for part in line.split(':', 1)]

            if key == 'flags':  # x86_64
                fields['flags'] = value.split()
            elif key == 'cpu MHz':  # x86_64
                fields['frequency'] = value
            elif key == 'clock':  # ppc64, ppc64le
                fields['frequency'] = value[:-3]
            elif key == 'model name':  # x86_64
                fields['model'] = value
            elif key == 'model':  # ppc64le
                fields['ppcmodel'] = value
            elif key == 'cpu':  # ppc64, ppc64le
                fields['model'] = value
            elif key == 'platform':  # ppc64, ppc64le
                fields['platform'] = value
            elif key == 'machine':  # ppc64, ppc64le
                fields['machine'] = value

            if len(fields) == 6:
                break

        return CpuInfo(**fields)


def flags():
    '''
    Get the CPU flags.

    Returns:

    A list of flags supported by current CPU as parsed by parse() procedure
    or
    raises UnsupportedArchitecture exception or KeyError if cpuinfo format
    is invalid.

    '''
    return _cpuinfo().flags


def frequency():
    '''
    Get the CPU frequency.

    Returns:

    A floating point number representing the CPU frequency in MHz
    or
    raises UnsupportedArchitecture exception or KeyError if cpuinfo format
    is invalid.
    '''
    return _cpuinfo().frequency


def model():
    '''
    Get the CPU identification.

    Returns:

    A string representing the name of the CPU
    or
    raises UnsupportedArchitecture exception or KeyError if cpuinfo format
    is invalid.
    '''
    return _cpuinfo().model


def ppcmodel():
    '''
    Get the POWER CPU identification.

    Returns:

    A string representing the identification of the POWER CPU
    or
    raises UnsupportedArchitecture exception or KeyError if cpuinfo format
    is invalid.
    '''
    return _cpuinfo().ppcmodel


def platform():
    '''
    Get the CPU platform.

    Returns:

    A string representing the platform of POWER CPU
    or
    raises UnsupportedArchitecture exception or KeyError if cpuinfo format
    is invalid.
    '''
    return _cpuinfo().platform


def machine():
    '''
    Get the CPU machine.

    Returns:

    A string representing the name of POWER machine
    or
    raises UnsupportedArchitecture exception or KeyError if cpuinfo format
    is invalid.
    '''
    return _cpuinfo().machine
