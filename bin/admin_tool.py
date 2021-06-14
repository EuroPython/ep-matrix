#!/usr/bin/env python3
"""
Matrix administration tool.

A note on authentication/access tokens. The actions performed by this script
require authentication against the given Matrix server (as specified by the
optional --base_url flag and defaulting to the EuroPython server).

Authentication is performed using an access token which needs to be either
passed to the script on the commandline (use the --access_token flag) or by
defining an environment variable called $MATRIX_ACCESS_TOKEN.

You can find your access token either in Element or programmatically (see
https://webapps.stackexchange.com/questions/131056).
"""
import argparse
import json
import os
import sys
from urllib.parse import quote
import requests


BASE_URL = 'https://matrix.europython.eu'


# Get list of room on the server I have joined.
def get_rooms(access_token, resolve_aliases=False, base_url=BASE_URL):
    """
    Return the list of room IDs that the user corresponding to `access_token`
    is a member of.

    If `resolve_aliases` is True, return a mapping of room ID to room alias.
    """
    assert access_token, 'access token is required (e.g. $MATRIX_ACCESS_TOKEN)'

    auth_header = {'Authorization': f'Bearer {access_token}'}
    r = requests.get(f'{base_url}/_matrix/client/r0/joined_rooms',
                     headers=auth_header)
    r.raise_for_status()

    room_ids = r.json().get('joined_rooms', [])
    if not resolve_aliases:
        return room_ids

    rooms = {}
    for _id in room_ids:
        rooms[_id] = resolve_room_alias(_id, access_token, base_url)
    return rooms


def resolve_room_alias(room_id, access_token, base_url=BASE_URL):
    """
    Translate a room ID into its alias.
    """
    assert access_token, 'access token is required (e.g. $MATRIX_ACCESS_TOKEN)'

    auth_header = {'Authorization': f'Bearer {access_token}'}
    r = requests.get(
        f'{base_url}/_matrix/client/r0/rooms/{room_id}/state/' +
        'm.room.canonical_alias',
        headers=auth_header
    )
    r.raise_for_status()
    return r.json()['alias']


def resolve_room_id(room_alias, base_url=BASE_URL):
    """
    Return the room ID given its alias.
    """
    r = requests.get(f'{base_url}/_matrix/client/r0/directory/room/' +
                     quote(room_alias))
    r.raise_for_status()
    return r.json()['room_id']


def get_room_power_levels(room_id, user_id, access_token, base_url=BASE_URL):
    """
    Given a room ID (you are a member of) return the dict of the room power
    levels. Can be used to get a list of users in that room as well.

    If `user_id` is spedified, simply return the power level for that user in
    that room or None is that user is not in the room.
    """
    assert access_token, 'access token is required (e.g. $MATRIX_ACCESS_TOKEN)'

    auth_header = {'Authorization': f'Bearer {access_token}'}
    r = requests.get(f'{base_url}/_matrix/client/r0/rooms/{room_id}/state' +
                     '/m.room.power_levels/',
                     headers=auth_header)
    if user_id is None:
        return r.json()
    return r.json().get('users', {}).get(user_id, None)


def set_user_room_power_level(user_id, room_id, level, access_token,
                              base_url=BASE_URL):
    """
    Change the power level of `user_id` in `room_id`.

    This WILL fail if your power level is <= to the one `user_id` currently
    holds in `room_id`.

    Return the new level. Raise on failure.
    """
    assert access_token, 'access token is required (e.g. $MATRIX_ACCESS_TOKEN)'

    # Get all power levels for the room
    room_levels = get_room_power_levels(room_id=room_id,
                                        user_id=None,
                                        access_token=access_token,
                                        base_url=base_url)
    room_levels['users'][user_id] = level

    auth_header = {'Authorization': f'Bearer {access_token}'}
    r = requests.put(f'{base_url}/_matrix/client/r0/rooms/{room_id}/state' +
                     '/m.room.power_levels/',
                     headers=auth_header,
                     data=json.dumps(room_levels))
    r.raise_for_status()

    new_level = get_room_power_levels(room_id, user_id, access_token, base_url)
    assert new_level == level
    return level


def set_user_room_power_level_batch(users_levels, room_id, access_token,
                                    base_url=BASE_URL):
    """
    Given a mapping of {user_id: power_level} and a room_id, set the power
    level of these users according to the mapping. This WILL fail if any of the
    users already has a power level >= to yours.

    Return the new mapping.
    """
    assert access_token, 'access token is required (e.g. $MATRIX_ACCESS_TOKEN)'

    # Get all power levels for the room
    room_levels = get_room_power_levels(room_id=room_id,
                                        user_id=None,
                                        access_token=access_token,
                                        base_url=base_url)
    original_levels = dict(**room_levels['users'])
    room_levels['users'].update(users_levels)

    # Is there any difference?
    if room_levels['users'] == original_levels:
        return original_levels

    auth_header = {'Authorization': f'Bearer {access_token}'}
    r = requests.put(f'{base_url}/_matrix/client/r0/rooms/{room_id}/state' +
                     '/m.room.power_levels/',
                     headers=auth_header,
                     data=json.dumps(room_levels))
    r.raise_for_status()

    new_level_dict = get_room_power_levels(room_id, None, access_token,
                                           base_url)
    new_level_dict = new_level_dict['users']
    for user_id, level in users_levels.items():
        assert new_level_dict.get(user_id, None) == level
    return new_level_dict


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(title='subcommands',
                                       description='valid subcommands')

    # The power_level subcommands
    get_power_level_parser = subparsers.add_parser(
        'get_power_level',
        help='get power level(s) for users/rooms'
    )
    get_power_level_parser.add_argument('--base_url', default=BASE_URL)
    get_power_level_parser.add_argument(
        '--access_token', help='access token (when needed)',
        default=os.environ.get('MATRIX_ACCESS_TOKEN', '')
    )
    get_power_level_parser.add_argument(
        '--room_id',  '-r', help='room ID', required=True
    )
    get_power_level_parser.add_argument(
        '--user_id', '-u', help='username', default=None, required=False
    )
    get_power_level_parser.set_defaults(func=get_room_power_levels)

    set_power_level_parser = subparsers.add_parser(
        'set_power_level',
        help='set power level for users/rooms'
    )
    set_power_level_parser.add_argument('--base_url', default=BASE_URL)
    set_power_level_parser.add_argument(
        '--access_token', help='access token (when needed)',
        default=os.environ.get('MATRIX_ACCESS_TOKEN', '')
    )
    set_power_level_parser.add_argument(
        '--room_id',  '-r', help='room ID', required=True
    )
    set_power_level_parser.add_argument(
        '--user_id', '-u', help='username', required=True
    )
    set_power_level_parser.add_argument(
        'level', type=int, help='0 <= power_level <= 100'
    )
    set_power_level_parser.set_defaults(func=set_user_room_power_level)

    # Room list/info subcommands
    get_rooms_parser = subparsers.add_parser('get_rooms', help='list rooms')
    get_rooms_parser.add_argument('--base_url', default=BASE_URL)
    get_rooms_parser.add_argument(
        '--access_token', help='access token (when needed)',
        default=os.environ.get('MATRIX_ACCESS_TOKEN', '')
    )
    get_rooms_parser.add_argument(
        '--resolve_aliases', action='store_true', default=False
    )
    get_rooms_parser.set_defaults(func=get_rooms)

    resolve_room_id_parser = subparsers.add_parser('resolve_room_id',
                                                   help='room alias -> id')
    resolve_room_id_parser.add_argument('--base_url', default=BASE_URL)
    resolve_room_id_parser.add_argument('room_alias', help='room alias')
    resolve_room_id_parser.set_defaults(func=resolve_room_id)

    resolve_room_alias_parser = subparsers.add_parser('resolve_room_alias',
                                                      help='room id -> alias')
    resolve_room_alias_parser.add_argument('--base_url', default=BASE_URL)
    resolve_room_alias_parser.add_argument(
        '--access_token', help='access token (when needed)',
        default=os.environ.get('MATRIX_ACCESS_TOKEN', '')
    )
    resolve_room_alias_parser.add_argument('room_id', help='room id')
    resolve_room_alias_parser.set_defaults(func=resolve_room_alias)

    args = parser.parse_args()
    if not vars(args):
        parser.print_help()
        sys.exit(1)

    args = vars(args)
    if 'func' in args:
        fn = args.pop('func')
        print(fn(**args))
