#!/usr/bin/env python3
"""
Given a list of Matrix usernames (in the form @username:domain.com), and an
optional power level (typically between 0 and 100 and by default 100), set the
power level of these users to that value in all rooms you (or the user the
access_token refers to) have access to.

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
import os
from admin_tool import BASE_URL, get_rooms, set_user_room_power_level_batch


def main(usernames, power_level, access_token, base_url=BASE_URL):
    room_ids = get_rooms(access_token=access_token, base_url=base_url)

    power_level_dict = {user_id: power_level for user_id in usernames}
    for room_id in room_ids:
        set_user_room_power_level_batch(
            users_levels=power_level_dict,
            room_id=room_id,
            access_token=access_token,
            base_url=base_url
        )
    return


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'usernames',
        nargs='+',
        help='Matrix username(s) to promote to admin in all rooms'
    )
    parser.add_argument(
        '--power_level',
        type=int,
        default=100,
        help='power level to assign to the input users (default 100)'
    )
    parser.add_argument(
        '--base_url',
        default=BASE_URL,
        help=f'server base URL (e.g. {BASE_URL})'
    )
    parser.add_argument(
        '--access_token',
        default=os.environ.get('MATRIX_ACCESS_TOKEN', ''),
        help='access token (here or as $MATRIX_ACCESS_TOKEN)'
    )
    args = parser.parse_args()
    if not args.access_token:
        parser.error(
            'Please either pass --access_token or define it in the env'
        )
    main(**vars(args))
