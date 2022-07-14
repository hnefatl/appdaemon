"""Handle simple button presses to remove duplication in HA automations."""

import re
from typing import Any, Dict
import itertools

import appdaemon.plugins.hass.hassapi as hass  # type: ignore

import zha_buttons
import default_scene_service


# "scenes", but really just arguments to turn_on
_MANUAL_MODE_SCENES = [
    {
        "entity_id": "group.bedroom_lights",
        "color_name": "red",
        "brightness_pct": 100,
    },
    {
        "entity_id": "group.bedroom_lights",
        "color_name": "green",
        "brightness_pct": 100,
    },
    {
        "entity_id": "group.bedroom_lights",
        "color_name": "blue",
        "brightness_pct": 100,
    },
    {"entity_id": "scene.bedroom_arctic_aurora"},
]


class Buttons(hass.Hass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._manual_mode_scene_iterator = 0

    def initialize(self):
        self.listen_event(
            event=zha_buttons.EVENT_TYPE, callback=self._button_press
        )

    def _button_press(
        self, _event_name: str, data: Dict[str, Any], _kwargs: Any
    ):
        info = zha_buttons.button_click_from_event_kwargs(data)
        self.log(info)
        if info is None:
            return
        (device, button, press) = info

        if device.name == "remote_control":
            self._remote_control_logic(*info)
        elif device.name == "bedroom_dimmer":
            self._bedroom_dimmer_logic(*info)
        elif device.name.endswith("dimmer"):
            self._dimmer_logic(*info)

    def _remote_control_logic(
        self,
        device: zha_buttons.Button,
        button: str,
        press: zha_buttons.ButtonPress,
    ):
        if button == "right":
            self.call_service(
                service="switch/toggle", entity_id="switch.table_light"
            )
        elif button == "left":
            self.call_service(
                service="switch/toggle", entity_id="switch.daisy_chain"
            )
        elif button == "bottom":
            self.call_service(service="light/turn_off", area_id="living_room")
        else:
            self.fire_event(
                event=default_scene_service.EVENT_NAME,
                rooms=["living_room"],
            )

    def _dimmer_logic(
        self,
        device: zha_buttons.Button,
        button: str,
        press: zha_buttons.ButtonPress,
    ):
        room_match = re.match(r"(.*)_dimmer", device.name)
        if room_match is None:
            return
        room = room_match[1]
        self.log(room)
        if button == "top":
            self.fire_event(
                event=default_scene_service.EVENT_NAME, rooms=[room]
            )
        else:
            self.call_service(service="light/turn_off", area_id=room)

    def _bedroom_dimmer_logic(
        self,
        device: zha_buttons.Button,
        button: str,
        press: zha_buttons.ButtonPress,
    ):
        bedroom_manual_control = self.get_entity(
            "input_boolean.bedroom_manual_control"
        )
        is_manual_control = bedroom_manual_control.get_state() == "on"
        if press == zha_buttons.ButtonPress.HOLD:
            if button == "top":
                bedroom_manual_control.turn_on()
                self._manual_mode_scene_iterator = -1
                self.log("manual bedroom lights on")
            elif button == "bottom":
                bedroom_manual_control.turn_off()
                self.log("manual bedroom lights off")
            return
        elif not is_manual_control:
            # single press + not in manual control mode, behave like a normal
            # dimmer
            self._dimmer_logic(device, button, press)
            return

        # We're in manual mode and got a single press
        if button == "top":
            self._manual_mode_scene_iterator += 1
        elif button == "bottom":
            self._manual_mode_scene_iterator -= 1
        self._manual_mode_scene_iterator %= len(_MANUAL_MODE_SCENES)
        scene = _MANUAL_MODE_SCENES[self._manual_mode_scene_iterator]
        self.log(f"manual lights to: {scene}")

        self.turn_on(**scene)
