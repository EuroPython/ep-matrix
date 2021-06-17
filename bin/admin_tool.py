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
import json
import os
from urllib.parse import quote
import click
import requests


BASE_URL = 'https://matrix.europython.eu'
ACCESS_TOKEN = os.environ.get('MATRIX_ACCESS_TOKEN', None)


def get_rooms(access_token, resolve_aliases=False, base_url=BASE_URL):
    """
    Return the server rooms.

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


def set_room_topic(access_token, room_id, topic, base_url=BASE_URL):
    """
    Set the given room a topic. Return the asigned topic.
    """
    assert access_token, 'access token is required (e.g. $MATRIX_ACCESS_TOKEN)'

    auth_header = {'Authorization': f'Bearer {access_token}'}
    r = requests.put(f'{base_url}/_matrix/client/r0/rooms/{room_id}/state' +
                     '/m.room.topic/',
                     headers=auth_header,
                     data=json.dumps({'topic': topic}))
    r.raise_for_status()
    return get_room_topic(access_token, room_id, base_url)


def get_room_topic(access_token, room_id, base_url=BASE_URL):
    """
    Get the given room's topic.
    """
    assert access_token, 'access token is required (e.g. $MATRIX_ACCESS_TOKEN)'

    auth_header = {'Authorization': f'Bearer {access_token}'}
    r = requests.get(f'{base_url}/_matrix/client/r0/rooms/{room_id}/state' +
                     '/m.room.topic/',
                     headers=auth_header)
    if r.status_code == 404:
        # The room never got a topic
        return ''
    r.raise_for_status()
    return r.json()['topic']


def set_room_name(access_token, room_id, name, base_url=BASE_URL):
    """
    Set the given room a human friendly name.

    This is not an alias: it is a fiendly name displayed in the UI.

    Return the asigned name.
    """
    assert access_token, 'access token is required (e.g. $MATRIX_ACCESS_TOKEN)'

    auth_header = {'Authorization': f'Bearer {access_token}'}
    r = requests.put(f'{base_url}/_matrix/client/r0/rooms/{room_id}/state' +
                     '/m.room.name/',
                     headers=auth_header,
                     data=json.dumps({'name': name}))
    r.raise_for_status()
    return get_room_name(access_token, room_id, base_url)


def get_room_name(access_token, room_id, base_url=BASE_URL):
    """
    Get the given room's human friendly name.

    This is not an alias: it is a fiendly name displayed in the UI.

    Return the currently assigned name, if any.
    """
    assert access_token, 'access token is required (e.g. $MATRIX_ACCESS_TOKEN)'

    auth_header = {'Authorization': f'Bearer {access_token}'}
    r = requests.get(f'{base_url}/_matrix/client/r0/rooms/{room_id}/state' +
                     '/m.room.name/',
                     headers=auth_header)
    if r.status_code == 404:
        # The room never got a name
        return ''
    r.raise_for_status()
    return r.json()['name']


def resolve_room_alias(room_id, access_token, base_url=BASE_URL):
    """
    Return the room alias given its ID.
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
    Get user power levels in a room.

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
    Change the user power level in a room.

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
    @click.command(name='get_rooms')
    @click.option('--access_token', help='access token', default=ACCESS_TOKEN)
    @click.option('--resolve_aliases', is_flag=True)
    @click.option('--base_url', default=BASE_URL)
    def cli_get_rooms(access_token, resolve_aliases=False, base_url=BASE_URL):
        """Return the server rooms."""
        click.echo(get_rooms(access_token, resolve_aliases, base_url))

    @click.command(name='set_room_name')
    @click.option('--access_token', help='access token', default=ACCESS_TOKEN)
    @click.option('--room_id',  '-r', help='room ID', required=True)
    @click.option('--base_url', default=BASE_URL)
    @click.argument('name')
    def cli_set_room_name(access_token, room_id, name, base_url=BASE_URL):
        """Set the given room a human friendly name."""
        click.echo(set_room_name(access_token, room_id, name, base_url))

    @click.command(name='get_room_name')
    @click.option('--access_token', help='access token', default=ACCESS_TOKEN)
    @click.option('--base_url', default=BASE_URL)
    @click.argument('room_id')
    def cli_get_room_name(access_token, room_id, base_url=BASE_URL):
        """Get the given room's human friendly name."""
        click.echo(get_room_name(access_token, room_id, base_url))

    @click.command(name='set_room_topic')
    @click.option('--access_token', help='access token', default=ACCESS_TOKEN)
    @click.option('--room_id',  '-r', help='room ID', required=True)
    @click.option('--base_url', default=BASE_URL)
    @click.argument('topic')
    def cli_set_room_topic(access_token, room_id, topic, base_url=BASE_URL):
        """Set the given room a human friendly topic."""
        click.echo(set_room_topic(access_token, room_id, topic, base_url))

    @click.command(name='get_room_topic')
    @click.option('--access_token', help='access token', default=ACCESS_TOKEN)
    @click.option('--base_url', default=BASE_URL)
    @click.argument('room_id')
    def cli_get_room_topic(access_token, room_id, base_url=BASE_URL):
        """Get the given room's human friendly topic."""
        click.echo(get_room_topic(access_token, room_id, base_url))

    @click.command(name='resolve_room_alias')
    @click.option('--access_token', help='access token', default=ACCESS_TOKEN)
    @click.option('--base_url', default=BASE_URL)
    @click.argument('room_id')
    def cli_resolve_room_alias(room_id, access_token, base_url=BASE_URL):
        """Return the room alias given its ID."""
        click.echo(resolve_room_alias(room_id, access_token, base_url))

    @click.command(name='resolve_room_id')
    @click.option('--base_url', default=BASE_URL)
    @click.argument('room_alias')
    def cli_resolve_room_id(room_alias, base_url=BASE_URL):
        """Return the room ID given its alias."""
        click.echo(resolve_room_id(room_alias, base_url))

    @click.command(name='get_room_power_levels')
    @click.option('--access_token', help='access token', default=ACCESS_TOKEN)
    @click.option('--room_id',  '-r', help='room ID', required=True)
    @click.option('--user_id', '-u', help='username', default=None)
    @click.option('--base_url', default=BASE_URL)
    def cli_get_room_power_levels(room_id, user_id, access_token,
                                  base_url=BASE_URL):
        """Get user power levels in a room."""
        click.echo(get_room_power_levels(room_id, user_id, access_token,
                                         base_url))

    @click.command(name='set_user_room_power_level')
    @click.option('--access_token', help='access token', default=ACCESS_TOKEN)
    @click.option('--room_id',  '-r', help='room ID', required=True)
    @click.option('--user_id', '-u', help='username', required=True)
    @click.option('--base_url', default=BASE_URL)
    @click.argument('level', type=int)
    def cli_set_user_room_power_level(user_id, room_id, level, access_token,
                                      base_url=BASE_URL):
        """Change the user power level in a room."""
        click.echo(set_user_room_power_level(user_id, room_id, level,
                                             access_token, base_url))

    @click.group()
    def cli():
        ...

    cli.add_command(cli_get_rooms)
    cli.add_command(cli_set_room_name)
    cli.add_command(cli_get_room_name)
    cli.add_command(cli_set_room_topic)
    cli.add_command(cli_get_room_topic)
    cli.add_command(cli_resolve_room_alias)
    cli.add_command(cli_resolve_room_id)
    cli.add_command(cli_get_room_power_levels)
    cli.add_command(cli_set_user_room_power_level)

    cli(standalone_mode=False)
