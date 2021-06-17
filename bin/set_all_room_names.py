#!/usr/bin/env python3
"""
Given a CSV file of

room_id/room_alias,room_name

and a Matrix server URL (e.g. https://matrix.europython.eu), set the name of
all rooms in the CSV file to their room_name.

Room_id/room_alias (i.e. the first column in the CSV) can either be a room ID
(e.g. !cRZDBfEYlyGsCDKySj) or a room alias (e.g. #foo). No need to specify the
server part as it will get stripped anyway.
"""
import argparse
import csv
import os
from urllib.parse import urlparse
from admin_tool import resolve_room_id, set_room_name


BASE_URL = 'https://matrix.europython.eu'


def main(path, access_token, base_url=BASE_URL):
    room_ids = []
    room_aliases = []

    domain = urlparse(base_url).netloc.split('.', 1)[-1]
    with open(path) as f:
        reader = csv.reader(f)
        for (alias_id, name) in reader:
            # Customize the domain with base_url
            alias_id = alias_id.split(':')[0]
            fully_qualified = f'{alias_id}:{domain}'

            if alias_id.startswith('!'):
                room_ids.append((fully_qualified, name))
            elif alias_id.startswith('#'):
                room_aliases.append((fully_qualified, name))
            else:
                raise NotImplementedError(f'unsupported room {alias_id}')

    # Resolve aliases
    for alias, name in room_aliases:
        room_ids.append((resolve_room_id(alias, base_url), name))

    # Remove duplicates
    room_ids = set(room_ids)

    # Finally, set the names
    for room_id, name in room_ids:
        assigned = set_room_name(
            access_token,
            room_id,
            name,
            base_url)
        print(f'{room_id} -> {assigned}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base_url', default=BASE_URL)
    parser.add_argument(
        '--access_token', help='access token (when needed)',
        default=os.environ.get('MATRIX_ACCESS_TOKEN', '')
    )
    parser.add_argument('path')
    args = parser.parse_args()
    main(**vars(args))
