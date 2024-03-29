"""Based on https://github.com/milesflo/caramelldansen-philips."""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations
import appdaemon.plugins.hass.hassapi as hass # pyright: ignore[reportMissingTypeStubs]

import asyncio
import itertools

from typing import Any

from phue import Bridge, Group, PhueRegistrationException # pyright: ignore[reportMissingTypeStubs]


ROOM_SELECTOR_ENTITY_ID = "input_select.caramell_dansen_room"
USE_GROUP_API_ENTITY_ID = "input_boolean.caramell_dansen_use_group_api"
SPEED = 0.2
RED = 2000
CYAN = 39000
PURPLE = 55000
YELLOW = 10000
COLOUR_ORDER = [YELLOW, RED, CYAN, PURPLE]


class CaramellDansen(hass.Hass):
    def __init__(self, *args: ..., **kwargs: ...):
        super().__init__(*args, **kwargs)
        self._effect_active = False
        self._bridge_ip: str = self.args.get("bridge_ip")

    def initialize(self):
        # Turn off any active effects, reset input.
        self.set_state(entity_id=ROOM_SELECTOR_ENTITY_ID, state="")

        self.listen_state(
            entity_id=ROOM_SELECTOR_ENTITY_ID, callback=self.room_selection_changed
        )

    def connect(self):
        try:
            return Bridge(self._bridge_ip)
        except PhueRegistrationException:
            self.notify(message="Press Hue bridge button.")
            raise RuntimeError(
                "Registration failed, press the button on the Bridge and retry."
            )

    async def room_selection_changed(self, _entity: str , _attribute: str, _old: ..., new: ..., _kwargs: ...):
        group_name = new
        if not group_name:
            # Room deselected, stop the effect.
            self._effect_active = False
            return

        use_group_api: bool = self.get_state(entity_id=USE_GROUP_API_ENTITY_ID) == "on"

        bridge = self.connect()

        if use_group_api:
            def update_lights(params: dict[str, Any]):
              bridge.set_group(group_name, params, transitiontime=0)
        else:
            group = Group(bridge, group_name)
            light_ids = [light.light_id for light in group.lights]

            def update_lights(params: dict[str, Any]):
                bridge.set_light(light_ids, params, transitiontime=0)

        # Initialise the lights
        initial_params = {"on": True, "bri": 255}
        update_lights(initial_params)

        self._effect_active = True
        # Run the loop until indicated not to
        for hue in itertools.cycle(COLOUR_ORDER):
            if not self._effect_active:
                break

            update_lights({"hue": hue})
            await asyncio.sleep(SPEED)
