import appdaemon.plugins.hass.hassapi as hass
import asyncio
import enum
import json
from typing import List

EVENT_PREFIX = 'HA: '
BEDROOM_BUTTON = 'flic_80e4da77f54b'

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
    self.log('Starting Schedule service')
    self._command_mappings = {
      'Wakeup': self.on_wakeup,
      'Relax': self.on_relax,
      'Hoover': self.on_hoover,
    }

    if await self.now_is_between('sunrise', 'sunset'):
      self._state = State.SUN_UP
    else:
      self._state = State.SUN_DOWN
    self.log(f'Initialised state to: {self._state}')

    await self.run_at_sunrise(callback=self.on_sun_change, state=State.SUN_UP)
    await self.run_at_sunset(callback=self.on_sun_change, state=State.SUN_DOWN)
    await self.listen_event(
      event='flic_click',
      button_name=BEDROOM_BUTTON,
      callback=self.on_bedroom_button_click)
    await self.listen_event(
      event='google_calendar_event',
      callback=self.on_calendar_event,
    )

  async def on_sun_change(self, kwargs):
    new_state = kwargs.get('state')
    self.log(f'Sun state changed: {new_state}')
    async with self._state_lock:
      self._state = new_state

  async def on_bedroom_button_click(self, _, data, __):
    self.log(f'Bedroom button click: {data}')
    click_type = data.get('click_type')
    async with self._state_lock:
      self.log(f'Current state: {self._state}')
      if click_type == 'single':
        if self._state == State.SUN_DOWN:
          await self.light_turn_off('group.all_lights')
        elif self._state == State.SUN_UP:
          await self.scene_turn_on('scene.bedroom_bright')
        else:
          self.log('Ignoring press, it conflicts with wakeup.')
      elif click_type == 'double':
        # Double press is essentially the opposite of single press
        if self._state == State.SUN_DOWN:
          await self.scene_turn_on('scene.bedroom_dim')
          await self.scene_turn_on('scene.living_room_dim')
          await self.scene_turn_on('scene.office_room_dim')
        elif self._state == State.SUN_UP:
          await self.light_turn_off('group.bedroom_lights')

  async def on_calendar_event(self, _, data, *args):
    self.log(f'Calendar event: {data}')
    title = data.get('title', None)
    if not title or not title.startswith(EVENT_PREFIX):
      return

    command = title[len(EVENT_PREFIX):]
    command_function = self._command_mappings.get(command, self.default_calendar_handler)
    await command_function(data)

  async def default_calendar_handler(self, event):
    self.log(f'Loading scenes from event: {event}')
    await self.apply_scenes_from_event(event)

  async def on_relax(self, event):
    if await self.get_state(entity_id='group.office_lights'):
      self.log('Loading relax scenes')
      await self.apply_scenes_from_event(event)

  async def on_wakeup(self, event):
    ALARM_INITIAL_DELAY = 5 # 5s, how long to wait before starting the alarm
    ALARM_DURATION = 5 * 60 # 5min, how long the alarm audio file is

    # Prevent any other state changes while we're in sequence
    async with self._state_lock:
      original_state = self._state
      self._state = State.IN_WAKEUP

      self.log('Loading wakeup scenes')
      await self.apply_scenes_from_event(event)

      # Start listening for a button press to signal "I'm awake"
      media_player_lock = asyncio.Lock()
      # None represents "not yet started", True is started, False is stopped or
      # should not start.
      play_alarm = None
      alarm_stopped = asyncio.Event()

      callback_handle = None
      callback_handle_lock = asyncio.Lock() # Guard against concurrent callbacks
      async def flic_click_callback(event, data, kwargs):
        if data.get('click_type') != 'single':
          return
        async with callback_handle_lock:
          if callback_handle is None:
            return
          await self.cancel_listen_event(callback_handle)
          callback_handle = None

        nonlocal play_alarm
        async with media_player_lock:
          self.log('Stopping alarm')
          if play_alarm:
            await self.call_service(
              'media_player/media_stop',
              entity_id='media_player.bedroom_speaker')
          play_alarm = False
          alarm_stopped.set()

      callback_handle = await self.listen_event(
        event='flic_click',
        button_name=BEDROOM_BUTTON,
        timeout=ALARM_INITIAL_DELAY + ALARM_DURATION,
        callback=flic_click_callback)

      # Wait before starting to play the alarm, in case the lights are
      # sufficient to wake up.
      await asyncio.sleep(ALARM_INITIAL_DELAY)

      async with media_player_lock:
        # If we've not been told to stop the alarm already, play it
        if play_alarm is None:
          self.log('Starting alarm')
          play_alarm = True
          await self.call_service(
            'media_player/play_media',
            entity_id='media_player.bedroom_speaker',
            media_content_id='http://192.168.0.2:8123/local/alarm.mp3',
            media_content_type='music')

      # Wait until either the button is pressed or the alarm finishes. We still
      # hold the state r+w locks, so no other state changes can happen.
      await asyncio.wait_for(alarm_stopped.wait(), timeout=ALARM_DURATION)
      self._state = original_state
    # release state r+w locks

    await asyncio.sleep(30 * 60) # 30mins
    self.log('Turning off bedroom lights')
    await self.light_turn_off('group.bedroom_lights')

  async def apply_scenes_from_event(self, event):
    scenes = json.loads(event.get('description', ''))
    self.log(f'Applying scenes: {scenes}')
    for scene_data in scenes.get('scenes', [scenes]):
      await self.scene_turn_on(**scene_data)

  async def on_hoover(self, _):
    await self.activate_hoover()

  async def light_turn_off(self, entity_id, **kwargs):
    self.log(f'Turning off lights: {entity_id}: {kwargs}')
    await self.call_service('light/turn_off', entity_id=entity_id, **kwargs)

  async def scene_turn_on(self, entity_id, **kwargs):
    self.log(f'Turning on scene: {entity_id}: {kwargs}')
    await self.call_service('scene/turn_on', entity_id=entity_id, **kwargs)

  async def activate_hoover(self, _):
    self.log('Activating hoover')
    await self.call_service('vacuum/start', 'vacuum.hoover')