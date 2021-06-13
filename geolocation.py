import appdaemon.plugins.hass.hassapi as hass
import json
from typing import List

# Time to wait before turning off lights
AWAY_DURATION = 45 * 60

class Geolocation(hass.Hass):
  def initialize(self):
    self.log('Starting geolocation service')
    self.listen_event(
      zone='zone.home',
      event='leave',
      entity_id='person.keith',
      callback=self.on_leave_home_zone)

  def on_leave_home_zone(self, kwargs):
    self.log(f'Keith left home: {kwargs}')
    self.run_in(delay=AWAY_DURATION, callback=self.double_check)

  def double_check(self, kwargs):
    current_state = self.get_state(entity_id='person.keith')
    self.log(f'Keith current state: {current_state}')
    if current_state != 'home':
      self.call_service('light/turn_off', entity_id='group.all_lights')