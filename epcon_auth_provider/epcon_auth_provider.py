import logging
import unicodedata

from twisted.internet import defer, reactor
from synapse.api.errors import HttpResponseException, SynapseError
from synapse.types import create_requester
from synapse.api.constants import Membership
from synapse.types import UserID, RoomAlias


logger = logging.getLogger(__name__)

HOMESERVER_NAME= "europython.eu"

DEFAULT_ROOMS = [
    # (#<room>_name:europython.eu, public (true/false)
    ("#info-desk:{}".format(HOMESERVER_NAME), True),
    ("#hallway:{}".format(HOMESERVER_NAME), False),
    ("#announcements:{}".format(HOMESERVER_NAME), True),
    ("#staff:{}".format(HOMESERVER_NAME), False),
    ("#speakers:{}".format(HOMESERVER_NAME), False),
    ("#coc:{}".format(HOMESERVER_NAME), False),
    ("#track1:{}".format(HOMESERVER_NAME), False),
    ("#track2:{}".format(HOMESERVER_NAME), False),
    ("#track3:{}".format(HOMESERVER_NAME), False),
    ("#track4:{}".format(HOMESERVER_NAME), False),
    ("#sprints:{}".format(HOMESERVER_NAME), True),
]

JOIN_DEFAULT = ["#info-desk:{}".format(HOMESERVER_NAME), "#sprints:{}".format(HOMESERVER_NAME), "#coc:{}".format(HOMESERVER_NAME)]

JOIN_CONFERENCE = ["#track1:{}".format(HOMESERVER_NAME),
                   "#track2:{}".format(HOMESERVER_NAME),
                   "#track3:{}".format(HOMESERVER_NAME),
                   "#track4:{}".format(HOMESERVER_NAME),
                   "#hallway:{}".format(HOMESERVER_NAME)
                   ]
JOIN_SPEAKER = ["#speakers:{}".format(HOMESERVER_NAME)]
JOIN_STAFF = ["#staff:{}".format(HOMESERVER_NAME)]


def strip_accents(text):

    try:
        text = unicode(text, 'utf-8')
    except NameError: # unicode is a default on python 3
        pass

    text = unicodedata.normalize('NFD', text)\
           .encode('ascii', 'ignore')\
           .decode("utf-8")
    return str(text)


def get_rooms_for_user(epcon_data):
    if epcon_data["is_staff"]:
        return JOIN_DEFAULT + JOIN_CONFERENCE + JOIN_SPEAKER + JOIN_STAFF
    rooms_to_join = []
    if epcon_data["is_speaker"]:
        rooms_to_join.extend(JOIN_SPEAKER)
    for ticket in epcon_data["tickets"]:
        # just in case we have an user with more than one ticket
        # in particular combined and a separated one for sprints or live stream.
        fare_code = ticket["fare_code"]
        if fare_code in ["TRPC", "TRPP"]:
            # sprinters. only default ticket
            rooms_to_join.extend(JOIN_DEFAULT)
        if fare_code in ["TRCC", "TRCP", "TRSC", "TRSP"]:
            # combined
            rooms_to_join.extend(JOIN_DEFAULT)
            rooms_to_join.extend(JOIN_CONFERENCE)
    return set(rooms_to_join)


class EpconAuthProvider:

    def __init__(self, config, account_handler):
            self.account_handler = account_handler
            self._hs = account_handler._hs
            self.http_client = account_handler._http_client
            self.store = self._hs.get_datastore()

            if not config.endpoint:
                raise RuntimeError('Missing endpoint config')

            self.endpoint = config.endpoint
            self.admin_user = config.admin_user
            self.config = config
            logger.info('Endpoint: %s', self.endpoint)

    async def create_epcon_rooms(self):
        # fixme: move it to a different script.

        if not await self.account_handler.check_user_exists(self.admin_user):
            logger.info("Not creating default rooms as %s doesn't exists", self.admin_user)
            return

        logger.info("Attempt to create default rooms for EuroPython")
        room_creation_handler = self._hs.get_room_creation_handler()
        requester = create_requester(self.admin_user)
        for room_alias_name, public in DEFAULT_ROOMS:
            logger.info("Creating %s", room_alias_name)
            try:
                room_alias = RoomAlias.from_string(room_alias_name)
                stub_config = {
                    "preset": "public_chat" if public else "private_chat",
                    "room_alias_name": room_alias.localpart,
                    "creation_content": {"m.federate": False}
                }
                info, _ = await room_creation_handler.create_room(
                    create_requester(self.admin_user),
                    config=stub_config,
                    ratelimit=False,
                )
            except Exception as e:
                logger.error("Failed to create default channel %r: %r", room_alias_name, e)


    @staticmethod
    def parse_config(config):
        _require_keys(config, ["endpoint", "admin_user"])

        class _RestConfig(object):
            endpoint = ''

        rest_config = _RestConfig()
        rest_config.endpoint = config["endpoint"]
        rest_config.admin_user = config["admin_user"]


        return rest_config

    async def check_3pid_auth(self, medium, address, password):
        """
        Handle authentication against thirdparty login types, such as email
        Args:
            medium (str): Medium of the 3PID (e.g email, msisdn).
            address (str): Address of the 3PID (e.g bob@example.com for email).
            password (str): The provided password of the user.

         Returns:
             user_id (str|None): ID of the user if authentication successful. None otherwise.
         """
         # Only e-mail supported email
        if medium != "email":
            logger.debug("Not going to auth medium: %s, address: %s", medium, address)
            return None
        logger.info("going to check auth for %s", address)

        epcon_data = await self.auth_with_epcon(address, password)

        if not epcon_data:
            logger.info("Auth failed for %s", address)
            return None
        logger.info("%s successfully authenticated with epcon. profile: %s", address, epcon_data)

        # If no tickets found inside epcon_data return false.
        tickets = epcon_data.get("tickets", None)
        if not tickets:
            logger.info("Auth failed for %s - no tickets found", address)
            raise SynapseError(code=400, errcode="no_tickets_found", msg='Login failed: No tickets found for user.')

        user_id = await self._get_or_create_userid(epcon_data)
        try:
            await self._apply_user_policies(user_id, epcon_data)
        except Exception as e:
            logger.error("Error joining rooms :%r", e)
        logger.info("User registered. address: '%s' user_id: '%s'", address, user_id)
        return user_id

    async def _apply_user_policies(self, user_id, epcon_data):
        # first invite the user.
        if user_id == self.admin_user:
            await self.create_epcon_rooms()
        room_hanlder = self._hs.get_room_member_handler()
        room_ids = await self.store.get_rooms_for_user(user_id)
        rooms_to_join = get_rooms_for_user(epcon_data)

        for room_alias in rooms_to_join:
            try:
                room_id, _ = await room_hanlder.lookup_room_alias(RoomAlias.from_string(room_alias))
                logger.info("room_id for room_alias '%s' is: '%s'", room_alias, room_id)
                if room_id.to_string() in room_ids:
                    logger.info("%s is already a member of %s", user_id, room_alias)
                    continue
                logger.info("Adding %s to room: %s", user_id, room_alias)
                await room_hanlder.update_membership(requester=create_requester(self.admin_user),
                                               target=UserID.from_string(user_id),
                                               room_id=room_id.to_string(),
                                               action=Membership.INVITE,
                                               ratelimit=False,
                                                     )
                # force join
                room_hanlder = self._hs.get_room_member_handler()
                await room_hanlder.update_membership(requester=create_requester(user_id),
                                               target=UserID.from_string(user_id),
                                               room_id=room_id.to_string(),
                                               action=Membership.JOIN,
                                               ratelimit=False,
                                               )
            except Exception as e:
                logger.error("Eror adding %s to %s: %r", user_id, room_alias, e)

    def get_local_part(self, epcon_data):
        first_name = epcon_data["first_name"]
        last_name = epcon_data["last_name"]
        username = epcon_data["username"]
        return strip_accents(f"{first_name}.{last_name}.{username}".lower())

    async def _get_or_create_userid(self, epcon_data):
        localpart = self.get_local_part(epcon_data)
        user_id = self.account_handler.get_qualified_user_id(localpart)
        if await self.account_handler.check_user_exists(user_id):
            logger.info("User already exists in Matrix. email: %s", epcon_data["email"])
            # exists, authentication complete
            return user_id
        logger.info("User %s is new. Registering in Matrix", localpart)

        # register a new user
        user_id = await self.register_user(epcon_data)
        return user_id

    async def auth_with_epcon(self, email, password):
        try:
            result = await self.http_client.post_json_get_json(
                self.endpoint, {"email": email, "password": password})
        except HttpResponseException as e:
            raise e.to_synapse_error() from e
        if "error" in result:
            logger.info("Error authenticating '%s'", email)
            logger.info("Error message %s", result.get("message"))
            return False
        return result

    def register_user(self, epcon_data):
        localpart = self.get_local_part(epcon_data)
        return defer.ensureDeferred(
            self._hs.get_registration_handler().register_user(
                localpart=localpart,
                default_display_name=f'{epcon_data["first_name"]} {epcon_data["last_name"]}',
                bind_emails=[epcon_data["email"]],
                admin=epcon_data["is_staff"]
            )
        )



def _require_keys(config, required):
    missing = [key for key in required if key not in config]
    if missing:
        raise Exception(
            "Epcon Auth enabled but missing required config values: {}".format(
                ", ".join(missing)
            )
        )
