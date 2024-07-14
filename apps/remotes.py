"""Handle simple button presses to remove duplication in HA automations."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from typing import Any, Callable, Dict

import appdaemon.plugins.hass.hassapi as hass  # pyright: ignore[reportMissingTypeStubs]

import zha_buttons
import default_scene_service


# "scenes", but really just arguments to turn_on
_MANUAL_MODE_SCENES = [
    {
        "entity_id": "group.bedroom_lights",
        "color_name": "red",
        "brightness_pct": 80,
    },
    {
        "entity_id": "group.bedroom_lights",
        "color_name": "green",
        "brightness_pct": 80,
    },
    {
        "entity_id": "group.bedroom_lights",
        "color_name": "blue",
        "brightness_pct": 80,
    },
    {
        "entity_id": "group.bedroom_lights",
        "color_name": "purple",
        "brightness_pct": 80,
    },
    {"entity_id": "scene.bedroom_arctic_aurora"},
]


class Remotes(hass.Hass):

    def __init__(self, *args: ..., **kwargs: ...):
        super().__init__(*args, **kwargs)
        self._manual_mode_scene_iterator = 0

        self._behaviours: dict[
            str, Callable[[zha_buttons.Button, str, zha_buttons.ButtonPress], None]
        ] = {
            "bedroom_remote": self._bedroom_remote_logic,
        }

    def initialize(self):
        self.listen_event(event=zha_buttons.EVENT_TYPE, callback=self._button_press)

    def _button_press(self, _event_name: str, data: Dict[str, Any], _kwargs: Any):
        info = zha_buttons.button_click_from_event_kwargs(data)
        self.log(str(info))
        if info is None:
            return
        (device, _button, _press) = info

        if behaviour := self._behaviours.get(device.name):
            behaviour(*info)

    def _bedroom_remote_logic(
        self,
        device: zha_buttons.Button,
        button: str,
        press: zha_buttons.ButtonPress,
    ):
        bedroom_manual_control = self.get_entity("input_boolean.bedroom_manual_control")

        if button == "centre" and press is zha_buttons.ButtonPress.SINGLE:
            is_manual_control = bedroom_manual_control.get_state() == "on"
            bedroom_manual_control.toggle()
            # This is awkward but toggling then fetching the state actually races, despite being synchronous
            # calls (we get "off" immediately after toggling on).
            is_manual_control = not is_manual_control
            self._manual_mode_scene_iterator = 0

            self.log(f"manual lights set to: {is_manual_control}")
            if is_manual_control:
                self.turn_on(**_MANUAL_MODE_SCENES[0])
            else:
                self.fire_event(
                    event=default_scene_service.EVENT_NAME,
                    rooms=["bedroom"],
                )
            return

        is_manual_control = bedroom_manual_control.get_state() == "on"
        if not is_manual_control:
            self.log("no action, not manual control")
            return

        if button in {"left", "right"}:
            if button == "right":
                self._manual_mode_scene_iterator += 1
            elif button == "left":
                self._manual_mode_scene_iterator -= 1

            self._manual_mode_scene_iterator %= len(_MANUAL_MODE_SCENES)
            scene = _MANUAL_MODE_SCENES[self._manual_mode_scene_iterator]
            self.log(f"manual lights to: {scene}")
            self.turn_on(**scene)
        elif button in {"top", "bottom"}:
            pass
            # TODO: figure out how to wire in brightness, probably via more structured scene definitions
