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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#

from __future__ import absolute_import
from __future__ import division

import xml.etree.ElementTree as etree

import six


def fromstring(data):
    parser = etree.XMLParser()
    if isinstance(data, six.binary_type):
        parser.feed(data)
    else:
        # ElementTree prefers binary type
        parser.feed(data.encode('utf-8'))
    return parser.close()


def indent(element, level=0, s="    "):
    """
    Modify element indentation in-place.

    Based on http://effbot.org/zone/element-lib.htm#prettyprint
    """
    i = "\n" + level * s
    if len(element):
        if not element.text or not element.text.strip():
            element.text = i + s
        if not element.tail or not element.tail.strip():
            element.tail = i
        for element in element:
            indent(element, level + 1, s)
        if not element.tail or not element.tail.strip():
            element.tail = i
    else:
        if level and (not element.tail or not element.tail.strip()):
            element.tail = i
