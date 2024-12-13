"""Handle simple button presses to remove duplication in HA automations."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

import dataclasses
from typing import Any, Callable, Dict

import appdaemon.plugins.hass.hassapi as hass  # pyright: ignore[reportMissingTypeStubs]

import zha_buttons
import default_scene_service


@dataclasses.dataclass
class SceneState:
    colour: str
    brightness: float


class RoomController:
    def __init__(
        self,
        hass: hass.Hass,
        room_name: str,
        lights_entity_id: str,
        manual_control_entity_id: str,
        colours: list[str],
    ):
        self._hass = hass
        # Immutable
        self._room_name = room_name
        self._lights_entity_id = lights_entity_id
        self._manual_control_entity_id = manual_control_entity_id
        self._colours = colours
        self._default_brightness = 80.0

        # Mutable
        self._scene: SceneState | None = None
        self._colour_iterator = 0

    def handle(
        self,
        _device: zha_buttons.Button,
        button: str,
        press: zha_buttons.ButtonPress,
    ):
        manual_control = self._hass.get_entity(self._manual_control_entity_id)
        is_manual_control = manual_control.get_state() == "on"

        if button == "centre" and press is zha_buttons.ButtonPress.SINGLE:
            manual_control.toggle()
            is_manual_control = not is_manual_control

            self._hass.log(f"manual lights set to: {is_manual_control}")
            if not is_manual_control:
                self._scene = None
                self._hass.fire_event(
                    event=default_scene_service.EVENT_NAME,
                    rooms=[self._room_name],
                )
                return

        if not is_manual_control:
            self._hass.log("manual control disabled, ignoring")
            return
        if self._scene is None:
            self._colour_iterator = 0
            self._scene = SceneState(
                colour=self._colours[self._colour_iterator],
                brightness=self._default_brightness,
            )

        if button in {"left", "right"}:
            if button == "right":
                self._colour_iterator += 1
            elif button == "left":
                self._colour_iterator -= 1

            self._colour_iterator %= len(self._colours)
            self._scene.colour = self._colours[self._colour_iterator]

        if button in {"top", "bottom"}:
            if button == "top":
                self._scene.brightness = min(self._scene.brightness + 20, 100)
            elif button == "bottom":
                self._scene.brightness = max(self._scene.brightness - 20, 0)

        self._hass.log(f"manual scene to: {self._scene}")
        self._hass.turn_on(
            entity_id=self._lights_entity_id,
            color_name=self._scene.colour,
            brightness_pct=self._scene.brightness,
        )


class Remotes(hass.Hass):

    def __init__(self, *args: ..., **kwargs: ...):
        super().__init__(*args, **kwargs)

        self._controllers: dict[
            str, Callable[[zha_buttons.Button, str, zha_buttons.ButtonPress], None]
        ] = {
            "bedroom_remote": RoomController(
                self,
                room_name="bedroom",
                lights_entity_id="group.bedroom_lights",
                manual_control_entity_id="input_boolean.bedroom_manual_control",
                colours=["orange", "red", "green", "blue", "purple"],
            )
        }

    def initialize(self):
        self.listen_event(event=zha_buttons.EVENT_TYPE, callback=self._button_press)

    def _button_press(self, _event_name: str, data: Dict[str, Any], _kwargs: Any):
        info = zha_buttons.button_click_from_event_kwargs(data)
        self.log(str(info))
        if info is None:
            return
        (device, _button, _press) = info

        if controller := self._controllers.get(device.name):
            controller.handle(*info)
