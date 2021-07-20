from typing import Dict
from synapse.module_api import ModuleApi
from synapse.events import EventBase
from synapse.types import StateMap


class SuperRulesSet:
    def __init__(self, config: Dict, module_api: ModuleApi):
        self.id_server = config.get("id_server", None)
        self.module_api = module_api

    @staticmethod
    def parse_config(config: Dict) -> Dict:
        return config

    async def on_create_room(self, requester, config, is_requester_admin):
        return config.get('is_direct', False) or is_requester_admin

    async def check_event_allowed(self, event: EventBase,
                                  state_events: StateMap[EventBase]) -> bool:
        return True
