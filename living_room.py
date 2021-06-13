import appdaemon.plugins.hass.hassapi as hass
import json
from typing import List

LIVING_ROOM_BUTTON = 'flic_80e4da77d793'

class LivingRoom(hass.Hass):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    # Double-click enters a special selector mode for more customisation
    self._mode_selector = False

  def initialize(self):
    self.log('Starting Living Room service')
    self.listen_event(
      event='flic_click',
      button_name=LIVING_ROOM_BUTTON,
      callback=self.on_button_click)

  def on_button_click(self, _, data, __):
    self.log(f'Living room button click: {data}')

    click_type = data.get('click_type')

    if not self._mode_selector:
      # "Normal" mode, for first clicks
      if click_type == 'single':
        self.call_service('scene/turn_on', entity_id='scene.reading_chair_bright')
        self.call_service('light/turn_off', entity_id='group.sofa_lights')
      elif click_type == 'double':
        self.log('Entering mode selector')
        self._mode_selector = True
        def callback(*_):
          self.log('Exiting mode selector due to timeout')
          self._mode_selector = False
        self.run_in(delay=5, callback=callback)
      elif click_type == 'hold':
        self.call_service('scene/turn_on', entity_id='scene.living_room_spring_blossom')
    else:
      # Special selection mode, after a double-click
      self._mode_selector = False
      self.log('Exiting mode selector due to click')
      if click_type == 'single':
        self.call_service('switch/toggle', entity_id='switch.daisy_chain')
      elif click_type == 'double':
        self.call_service('switch/toggle', entity_id='switch.table_light')
      elif click_type == 'hold':
        self.call_service('light/turn_off', entity_id='group.living_room_lights')