"""Based on https://github.com/milesflo/caramelldansen-philips."""

from __future__ import annotations
import appdaemon.plugins.hass.hassapi as hass  # type: ignore

import asyncio
import itertools
import datetime

from phue import Bridge, PhueRegistrationException


ROOM_SELECTOR = "input_select.caramell_dansen_room"
SPEED = 0.2
RED = 2000
CYAN = 39000
PURPLE = 55000
YELLOW = 10000
COLOUR_ORDER = [YELLOW, RED, CYAN, PURPLE]


class CaramellDansen(hass.Hass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._effect_active = False
        self._bridge_ip = self.args.get("bridge_ip")

    def initialize(self):
        # Print group names for debugging
        print(f"All Hue groups: {[g.name for g in self.connect().groups]}")

        # Turn off any active effects, reset input.
        self.set_state(entity_id=ROOM_SELECTOR, state="")

        self.listen_state(entity_id=ROOM_SELECTOR, callback=self.room_selection_changed)

    def connect(self):
        try:
            return Bridge(self._bridge_ip)
        except PhueRegistrationException:
            self.notify(message="Press Hue bridge button.")
            raise RuntimeError(
                "Registration failed, press the button on the Bridge and retry."
            )

    async def room_selection_changed(self, _entity, _attribute, _old, new, _kwargs):
        group_id = new
        if not group_id:
            # Room deselected, stop the effect.
            self._effect_active = False
            return

        bridge = self.connect()

        # Initialise the lights
        initial_params = {"on": True, "bri": 255}
        bridge.set_group(group_id, initial_params, transitiontime=0)

        self._effect_active = True
        # Run the loop until indicated not to
        start = datetime.datetime.now()
        for hue in itertools.cycle(COLOUR_ORDER):
            if not self._effect_active:
                break

            # Set 0 transition time for a snappy flick between colours.
            # TODO: Create a connection manually using bridge parameters, to reduce latency.
            bridge.set_group(group_id, "hue", hue, transitiontime=0)
            new_time = datetime.datetime.now()
            print(f"Call took {(new_time - start).total_seconds()}s")
            start = new_time
            await asyncio.sleep(SPEED)
