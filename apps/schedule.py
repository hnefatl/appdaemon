import appdaemon.plugins.hass.hassapi as hass  # type: ignore
import asyncio
import enum
import json
from typing import List

# BEDROOM_BUTTON = "406a8b92e13d77d79941d59e37f03211"
VACUUM_ENTITY_ID = "vacuum.roborock_s6"


class State(enum.Enum):
    SUN_DOWN = 1
    SUN_UP = 2

    IN_WAKEUP = 3


class Schedule(hass.Hass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._state = State.SUN_DOWN
        self._state_lock = asyncio.Lock()

    async def initialize(self):
        self.log("Starting Schedule service")
        self._command_mappings = {
            "Wakeup": self.on_wakeup,
            "Relax": self.on_relax,
            "Hoover": self.on_hoover,
        }

        if await self.now_is_between("sunrise", "sunset"):
            self._state = State.SUN_UP
        else:
            self._state = State.SUN_DOWN
        self.log(f"Initialised state to: {self._state}")

        await self.run_at_sunrise(
            callback=self.on_sun_change, state=State.SUN_UP
        )
        await self.run_at_sunset(
            callback=self.on_sun_change, state=State.SUN_DOWN
        )
        # await self.listen_event(event="zha_event", device_id=BEDROOM_BUTTON, callback=self.on_bedroom_button_click)
        await self.listen_state(
            entity="calendar.home_assistant",
            # Get the entire state dict containing the event title etc, not just the
            # "state" attribute.
            attribute="all",
            callback=self.on_calendar_event,
        )

    async def on_sun_change(self, kwargs):
        new_state = kwargs.get("state")
        self.log(f"Sun state changed: {new_state}")
        async with self._state_lock:
            self._state = new_state

    async def on_bedroom_button_click(self, _, data, __):
        self.log(f"Bedroom button click: {data}")
        command = data.get("command")
        async with self._state_lock:
            self.log(f"Current state: {self._state}")
            if command == "toggle":
                if self._state == State.SUN_DOWN:
                    await self.light_turn_off("group.all_lights")
                elif self._state == State.SUN_UP:
                    await self.scene_turn_on("scene.bedroom_bright")
                else:
                    self.log("Ignoring press, it conflicts with wakeup.")
            elif command == "step_with_on_off":
                # Double press is essentially the opposite of single press
                if self._state == State.SUN_DOWN:
                    await self.scene_turn_on("scene.bedroom_dim")
                    await self.scene_turn_on("scene.living_room_dim")
                    await self.scene_turn_on("scene.office_dim")
                    await self.scene_turn_on("scene.corridor_dim")
                elif self._state == State.SUN_UP:
                    await self.light_turn_off("group.bedroom_lights")

    async def on_calendar_event(self, _, __, data, *___, **____):
        self.log(f"Calendar event: {data}")
        # For some reason these events trigger 3 times, off-on-off. The on event
        # is actually at the end of the event, not the start.
        if data.get("state") != "on":
            self.log("Skipping event as state isn't 'on'.")
            return

        attributes = data.get("attributes", {})
        title = attributes.get("message", None)
        if not title:
            return

        command_function = self._command_mappings.get(
            title, self.default_calendar_handler
        )
        await command_function(attributes)

    async def default_calendar_handler(self, event):
        self.log(f"Loading scenes from event: {event}")
        await self.apply_scenes_from_event(event)

    async def on_relax(self, event):
        if await self.get_state(entity_id="group.office_lights"):
            self.log("Loading relax scenes")
            await self.apply_scenes_from_event(event)

    async def on_wakeup(self, event):
        ALARM_INITIAL_DELAY = (
            5  # 5s, how long to wait before starting the alarm
        )
        ALARM_DURATION = 5 * 60  # 5min, how long the alarm audio file is

        # Prevent any other state changes while we're in sequence
        async with self._state_lock:
            try:
                original_state = self._state
                self._state = State.IN_WAKEUP

                self.log("Loading wakeup scenes")
                await self.apply_scenes_from_event(event)

                # Start listening for a button press to signal "I'm awake"
                media_player_lock = asyncio.Lock()
                # None represents "not yet started", True is started, False is stopped or
                # should not start.
                play_alarm = None
                alarm_stopped = asyncio.Event()

                callback_handle = None
                callback_handle_lock = (
                    asyncio.Lock()
                )  # Guard against concurrent callbacks

                async def flic_click_callback(event, data, kwargs):
                    nonlocal callback_handle
                    nonlocal play_alarm
                    if data.get("command") != "toggle":
                        return
                    async with callback_handle_lock:
                        if callback_handle is None:
                            return
                        await self.cancel_listen_event(callback_handle)
                        callback_handle = None

                    async with media_player_lock:
                        self.log("Stopping alarm")
                        if play_alarm:
                            await self.call_service(
                                "media_player/media_stop",
                                entity_id="media_player.bedroom_speaker",
                            )
                        play_alarm = False
                        alarm_stopped.set()

                callback_handle = await self.listen_event(
                    event="zha_event",
                    device_id=BEDROOM_BUTTON,
                    timeout=ALARM_INITIAL_DELAY + ALARM_DURATION,
                    callback=flic_click_callback,
                )

                # Wait before starting to play the alarm, in case the lights are
                # sufficient to wake up.
                await asyncio.sleep(ALARM_INITIAL_DELAY)

                async with media_player_lock:
                    # If we've not been told to stop the alarm already, play it
                    if play_alarm is None:
                        self.log("Starting alarm")
                        play_alarm = True
                        await self.call_service(
                            "media_player/play_media",
                            entity_id="media_player.bedroom_speaker",
                            media_content_id="http://10.20.1.2:8123/local/alarm.mp3",
                            media_content_type="music",
                        )

                # Wait until either the button is pressed or the alarm finishes. We still
                # hold the state r+w locks, so no other state changes can happen.
                await asyncio.wait_for(
                    alarm_stopped.wait(), timeout=ALARM_DURATION
                )
            except:
                # Always reset state, even if an error happens.
                self._state = original_state
                raise
        # release state r+w locks

        await asyncio.sleep(30 * 60)  # 30mins
        self.log("Turning off bedroom lights")
        await self.light_turn_off("group.bedroom_lights")

    async def apply_scenes_from_event(self, event):
        description = event.get("description")
        if not description:
            self.log("No description for calendar event")
            return
        scenes = json.loads(description)
        self.log(f"Applying scenes: {scenes}")
        for scene_data in scenes.get("scenes", [scenes]):
            await self.scene_turn_on(**scene_data)

    async def on_hoover(self, *args, **kwargs):
        await self.activate_hoover()

    async def light_turn_off(self, entity_id, **kwargs):
        self.log(f"Turning off lights: {entity_id}: {kwargs}")
        await self.call_service("light/turn_off", entity_id=entity_id, **kwargs)

    async def scene_turn_on(self, entity_id, **kwargs):
        self.log(f"Turning on scene: {entity_id}: {kwargs}")
        await self.call_service("scene/turn_on", entity_id=entity_id, **kwargs)

    async def activate_hoover(self):
        self.log("Activating hoover")
        await self.call_service("vacuum/start", entity_id=VACUUM_ENTITY_ID)
