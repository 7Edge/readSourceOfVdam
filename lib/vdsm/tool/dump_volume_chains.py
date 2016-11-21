# Copyright 2015-2016 Red Hat, Inc.
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
from __future__ import print_function
from collections import defaultdict
import argparse

from . import expose

from vdsm import client
from vdsm.config import config
from vdsm import utils

# BLANK_UUID is re-declared here since it cannot be imported properly. This
# constant should be introduced under lib publicly available
_BLANK_UUID = '00000000-0000-0000-0000-000000000000'
_NAME = 'dump-volume-chains'


class DumpChainsError(Exception):
    pass


class NoConnectedStoragePoolError(DumpChainsError):
    pass


class ChainError(DumpChainsError):
    def __init__(self, volumes_children):
        self.volumes_children = volumes_children


class DuplicateParentError(ChainError):
    description = ("More than one volume pointing to the same parent volume "
                   "e.g: (_BLANK_UUID<-a), (a<-b), (a<-c)")


class NoBaseVolume(ChainError):
    description = ("no volume with a parent volume Id _BLANK_UUID found e.g: "
                   "(a<-b), (b<-c)")


class ChainLoopError(ChainError):
    description = ("A loop found in the volume chain. This happens if a "
                   "volume points to one of it's parent volume e.g.: "
                   "(BLANK_UUID<-a), (a<-b), (b<-c), (c<-a)")


class OrphanVolumes(ChainError):
    description = ("There are volumes that are part of an image and are "
                   "pointing to volumes which are not part of the chain e.g: "
                   "(BLANK_UUID<-a), (a<-b), (c<-d)")


@expose(_NAME)
def dump_chains(*args):
    """
    dump-volume-chains
    Query VDSM about the existing structure of image volumes and prints
    them in an ordered fashion with optional additional info per volume.
    """
    parsed_args = _parse_args(args)
    cli = client.connect(parsed_args.host, parsed_args.port,
                         use_tls=parsed_args.use_ssl)
    with utils.closing(cli):
        image_chains, volumes_info = _get_volumes_chains(
            cli, parsed_args.sd_uuid)
        _print_volume_chains(image_chains, volumes_info)


def _parse_args(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('sd_uuid', help="storage domain UUID")
    parser.add_argument('-u', '--unsecured', action='store_false',
                        dest='use_ssl', default=True,
                        help="use unsecured connection")
    parser.add_argument('-H', '--host', default='localhost')
    parser.add_argument(
        '-p', '--port', default=config.getint('addresses', 'management_port'))

    return parser.parse_args(args=args[1:])


def _get_volumes_chains(cli, sd_uuid):
    """there can be only one storage pool in a single VDSM context"""
    pools = cli.Host.getConnectedStoragePools()
    if not pools:
        raise NoConnectedStoragePoolError('There is no connected storage '
                                          'pool to this server')
    sp_uuid, = pools
    images_uuids = cli.StorageDomain.getImages(storagedomainID=sd_uuid)

    image_chains = {}  # {image_uuid -> vol_chain}
    volumes_info = {}  # {vol_uuid-> vol_info}

    for img_uuid in images_uuids:
        volumes = cli.StorageDomain.getVolumes(
            storagedomainID=sd_uuid, storagepoolID=sp_uuid,
            imageID=img_uuid)

        # to avoid 'double parent' bug here we don't use a dictionary
        volumes_children = []  # [(parent_vol_uuid, child_vol_uuid),]

        for vol_uuid in volumes:
            vol_info = cli.Volume.getInfo(
                volumeID=vol_uuid, storagepoolID=sp_uuid,
                storagedomainID=sd_uuid, imageID=img_uuid)

            volumes_info[vol_uuid] = vol_info

            parent_uuid = vol_info['parent']
            volumes_children.append((parent_uuid, vol_uuid))

        try:
            image_chains[img_uuid] = _build_volume_chain(volumes_children)
        except ChainError as e:
            image_chains[img_uuid] = e

    return image_chains, volumes_info


def _build_volume_chain(volumes_children):
    volumes_by_parents = dict(volumes_children)
    if len(volumes_by_parents) < len(volumes_children):
        raise DuplicateParentError(volumes_children)

    child_vol = _BLANK_UUID
    chain = []  # ordered vol_UUIDs
    while True:
        child_vol = volumes_by_parents.get(child_vol)
        if child_vol is None:
            break  # end of chain
        if child_vol in chain:
            raise ChainLoopError(volumes_children)
        chain.append(child_vol)

    if not chain and volumes_by_parents:
        raise NoBaseVolume(volumes_children)

    if len(chain) < len(volumes_by_parents):
        raise OrphanVolumes(volumes_children)

    return chain


def _print_volume_chains(image_chains, volumes_info):
    if not image_chains:
        print()
        _print_line("(no images found)")
        print()
        return
    print()
    print('Images volume chains (base volume first)')
    for img_uuid, vol_chain in image_chains.iteritems():
        print()
        _print_line(img_uuid, 'image:')
        print()
        if isinstance(vol_chain, ChainError):
            chain_err = vol_chain
            _print_line(chain_err.description)
            _print_line('Volumes and children:')
            print()
            for parent, child in chain_err.volumes_children:
                _print_line('- %s <- %s' % (parent, child))
                _print_vol_info(volumes_info[child])
                print()
        else:
            for vol in vol_chain:
                _print_line('- ' + vol)
                _print_vol_info(volumes_info[vol])
                print()


def _print_vol_info(volume_info):
    robust_volume_info = defaultdict(lambda: '(missing)', volume_info)
    info_fmt = "status: {d[status]}, voltype: {d[voltype]}, " \
               "format: {d[format]}, legality: {d[legality]}, type: {d[type]}"
    formatted_info = info_fmt.format(d=robust_volume_info)
    _print_line('  ' + formatted_info)


def _print_line(body, title=''):
    print('{0:^13}{1}'.format(title, body))
