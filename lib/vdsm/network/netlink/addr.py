# Copyright 2014-2017 Red Hat, Inc.
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
from ctypes import (CFUNCTYPE, byref, c_char, c_int, c_void_p, sizeof)
from functools import partial
import errno

from . import _cache_manager, _nl_cache_get_first, _nl_cache_get_next
from . import _int_char_proto, _int_proto, _void_proto
from . import _pool
from . import libnl
from .link import _nl_link_cache, _link_index_to_name


def iter_addrs():
    """Generator that yields an information dictionary for each network address
    in the system."""
    with _pool.socket() as sock:
        with _nl_addr_cache(sock) as addr_cache:
            with _nl_link_cache(sock) as link_cache:  # for index to label
                addr = _nl_cache_get_first(addr_cache)
                while addr:
                    yield _addr_info(addr, link_cache=link_cache)
                    addr = _nl_cache_get_next(addr)


def _addr_info(addr, link_cache=None):
    """Returns a dictionary with the address information."""
    index = _rtnl_addr_get_ifindex(addr)
    local_address = _rtnl_addr_get_local(addr)
    data = {
        'index': index,
        'family': libnl.nl_af2str(_rtnl_addr_get_family(addr)),
        'prefixlen': _rtnl_addr_get_prefixlen(addr),
        'scope': libnl.rtnl_scope2str(_rtnl_addr_get_scope(addr)),
        'flags': _addr_flags(addr),
        'address': libnl.nl_addr2str(local_address) if local_address else None
    }
    try:
        data['label'] = _link_index_to_name(index, cache=link_cache)
    except IOError as err:
        if err.errno != errno.ENODEV:
            raise
    return data


def split(addr):
    """Split an addr dict from iter_addrs"""
    # for 32bits address, the address field is slashless
    return addr['address'].split('/')[0], addr['prefixlen']


def cidr_form(addr):
    return '{}/{}'.format(*split(addr))


def is_primary(addr):
    return 'secondary' not in addr['flags']


def is_permanent(addr):
    return 'permanent' in addr['flags']


def _addr_flags(addr):
    """Returns the textual representation of the address flags"""
    flags = (c_char * (libnl.CHARBUFFSIZE * 2))()
    return frozenset(_rtnl_addr_flags2str(_rtnl_addr_get_flags(addr), flags,
                     sizeof(flags)).split(b','))


# C function prototypes
# http://docs.python.org/2/library/ctypes.html#function-prototypes
# This helps ctypes know the calling conventions it should use to communicate
# with the binary interface of libnl and which types it should allocate and
# cast. Without it ctypes fails when not running on the main thread.
_addr_alloc_cache = CFUNCTYPE(c_int, c_void_p, c_void_p)(
    ('rtnl_addr_alloc_cache', libnl.LIBNL_ROUTE))


def _rtnl_addr_alloc_cache(sock):
    """Wraps the new addr alloc cache to expose the libnl1 signature"""
    cache = c_void_p()
    err = _addr_alloc_cache(sock, byref(cache))
    if err:
        raise IOError(-err, libnl.nl_geterror(err))
    return cache


_nl_addr_cache = partial(_cache_manager, _rtnl_addr_alloc_cache)

_rtnl_addr_get_ifindex = _int_proto(
    ('rtnl_addr_get_ifindex', libnl.LIBNL_ROUTE))
_rtnl_addr_get_family = _int_proto(('rtnl_addr_get_family', libnl.LIBNL_ROUTE))
_rtnl_addr_get_prefixlen = _int_proto(
    ('rtnl_addr_get_prefixlen', libnl.LIBNL_ROUTE))
_rtnl_addr_get_scope = _int_proto(('rtnl_addr_get_scope', libnl.LIBNL_ROUTE))
_rtnl_addr_get_flags = _int_proto(('rtnl_addr_get_flags', libnl.LIBNL_ROUTE))
_rtnl_addr_get_local = _void_proto(('rtnl_addr_get_local', libnl.LIBNL_ROUTE))
_rtnl_addr_flags2str = _int_char_proto(
    ('rtnl_addr_flags2str', libnl.LIBNL_ROUTE))
