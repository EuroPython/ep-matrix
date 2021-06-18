#!/usr/bin/env python3
"""
Customize room permissions.

Usage:
customize_room_permissions.py -a ACCESS_TOKEN  -r room_alias|room_id PERM*
    PERM:           key:power_level
    ACCESS_TOKEN:   your Matrix access token

You can define the environment variable MATRIX_ACCESS_TOKEN to avoid having to
pass the access token on the commandline.

You can pass the special keywork "all" as room ID. This means that your desired
power levels will be applied to ALL rooms (use it with care).

Examples
* Restrict the ability to invite people to powel level 50 in #foo:example.com
    customize_room_permissions #foo:example.com invite:50

* Like above, but also restrict "change settings" to level 75
    customize_room_permissions #foo:example.com invite:50 state_default:75

Note
The keys corresponding to the various permissions are "defined" here:
https://matrix.org/docs/spec/client_server/latest#m-room-power-levels

If a given key is inside a dictionary (e.g. "m.room.name" in in "events"), just
pass it on the commandline as is and the tool is smart enough to do the right
thing.

This tool will not set a user power level in a room, for that use other tools
in ./bin/
"""
import json
import os
import click
import requests
from admin_tool import (
    get_rooms,
    get_room_power_levels,
    resolve_room_id,
)


BASE_URL = 'https://matrix.europython.eu'
ACCESS_TOKEN = os.environ.get('MATRIX_ACCESS_TOKEN', None)
SIMPLE_KEYS = {"users_default", "events_default", "state_default", "ban",
               "kick", "redact", "invite"}
EVENT_KEYS = {"m.room.name", "m.room.power_levels",
              "m.room.history_visibility", "m.room.canonical_alias",
              "m.room.avatar", "m.room.tombstone", "m.room.server_acl",
              "m.room.encryption", "m.room.topic",
              "im.vector.modular.widgets"}


@click.command()
@click.option('--access_token', help='access token', default=ACCESS_TOKEN)
@click.option('--room',  '-r', help='room ID or alias', required=True)
@click.option('--base_url', default=BASE_URL)
@click.argument('permissions', nargs=-1, required=True)
def set_room_permissions(room, permissions, access_token, base_url):
    """Set the room permissions."""

    room_ids = []
    if room == 'all':
        room_ids = get_rooms(access_token=access_token, base_url=base_url)
    elif room.startswith('!'):
        room_ids.append(room)
    elif room.startswith('#'):
        room_ids.append(resolve_room_id(room, base_url))
    else:
        raise NotImplementedError(f'unsupported room {room}')

    power_levels = {}
    event_power_levels = {}
    for permission in permissions:
        try:
            key, value = permission.split(':')
        except ValueError:
            raise ValueError(f'{permission} not in the form  key:power_level')

        value = int(value)
        if key in SIMPLE_KEYS:
            power_levels[key] = value
        elif key in EVENT_KEYS:
            event_power_levels[key] = value
        else:
            raise NotImplementedError(f'unsupported key {key}')

    for room_id in room_ids:
        # Get the current room permissions
        room_power_levels = get_room_power_levels(
            room_id,
            user_id=None,
            access_token=access_token,
            base_url=base_url
        )
        if power_levels:
            room_power_levels.update(power_levels)
        if event_power_levels:
            room_power_levels['events'].update(event_power_levels)

        # Now set the desired levels.
        auth_header = {'Authorization': f'Bearer {access_token}'}
        r = requests.put(
            f'{base_url}/_matrix/client/r0/rooms/{room_id}/state' +
            '/m.room.power_levels/',
            headers=auth_header,
            data=json.dumps(room_power_levels)
        )
        r.raise_for_status()

        # Verify
        new_power_levels = get_room_power_levels(
            room_id,
            user_id=None,
            access_token=access_token,
            base_url=base_url
        )
        assert new_power_levels == room_power_levels
    return room_power_levels


if __name__ == '__main__':
    set_room_permissions()
