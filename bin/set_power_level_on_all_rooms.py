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

Note on CSV option and format
The script has the ability to read usernames from either the commandline OR
from a CSV file (via the --from_csv commandline flag). If usernames are
specified both as arguments and in a CSV file, then the CSV file takes
precedence and the ones specified as arguments are going to be ignored.

The CSV file is expected to have no header and it is expected to contain the
Matrix usernames as the LAST column. All other columns will be ignored.


DANGER DANGER DANGER DANGER DANGER DANGER DANGER DANGER DANGER DANGER DANGER

This script will NOT downgrade users unless the --force flag is used. Please
think carefully before using that flag.

DANGER DANGER DANGER DANGER DANGER DANGER DANGER DANGER DANGER DANGER DANGER
"""
import argparse
import csv
import os
import warnings
from admin_tool import BASE_URL, get_rooms, set_user_room_power_level_batch


def _read_usernames_from_csv_file(path):
    usernames = []
    with open(path) as f:
        reader = csv.reader(f)
        for row in reader:
            usernames.append(row[-1])
    return usernames


def main(usernames, power_level, access_token, from_csv, force=False,
         base_url=BASE_URL):
    if from_csv:
        usernames = _read_usernames_from_csv_file(from_csv)
    if not usernames:
        warnings.warn('No username specified: nothing to do.')
        return

    room_ids = get_rooms(access_token=access_token, base_url=base_url)

    power_level_dict = {user_id: power_level for user_id in usernames}
    for room_id in room_ids:
        set_user_room_power_level_batch(
            users_levels=power_level_dict,
            room_id=room_id,
            access_token=access_token,
            base_url=base_url,
            do_not_downgrade=not force,
        )
    return


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'usernames',
        nargs='*',
        help='Matrix username(s) to promote to admin in all rooms'
    )
    parser.add_argument(
        '--from_csv',
        default='',
        help='Read usernames from a CSV instead (see docstr for format info)'
    )
    parser.add_argument(
        '--force',
        default=False,
        action='store_true',
        help='Force setting of the given level to all users. ' +
             'DANGER: this will downgrade some users for sure. ' +
             'Are you really sure you want to do that? ' +
             'Not passing this flag is almost certainly what you want.'
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
    if not args.usernames and not args.from_csv:
        parser.error(
            'Please either specify usernames as arguments or use --from_csv'
        )
    main(**vars(args))
