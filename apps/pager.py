import asyncio
import base64
import email
import functools
import imapclient
import re
import time

import appdaemon.plugins.hass.hassapi as hass  # type: ignore

LIGHT_FLASH_COUNT = 3

IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993
IMAP_IDLE_TIMEOUT = 10 * 60  # 10mins

PROCESSED_KEYWORD = "pager_processed"


class Pager(hass.Hass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._connection = None
        self._main_loop_future = None

        self._username = self.args.get("username")
        self._password = self.args.get("password")
        self._to_email = self.args.get("email_to")
        self._from_emails = self.args.get("emails_from")

        # Create a string like 'OR (FROM a) (OR (FROM b) (FROM c))' (parentheses
        # for emphasis only) to filter against multiple sender emails.
        if self._from_emails:
            joined_from_emails = functools.reduce(
                lambda l, r: f"OR {l} {r}",
                map(lambda s: f"FROM {s}", self._from_emails),
            )
        else:
            joined_from_emails = ""
        # self._search_string = f"TO {self._to_email} {joined_from_emails} NOT KEYWORD {PROCESSED_KEYWORD}"
        self._search_string = (
            f"TO {self._to_email} NOT KEYWORD {PROCESSED_KEYWORD}"
        )

    def initialize(self):
        self.log("Starting Pager service")
        self.log(f'Using query string "{self._search_string}"')
        if not self._connect():
            self.log("Pager service failed to initialise")
        else:
            # A HA-native automation listens for the Lifeguard notification and
            # fires this event.
            #self.listen_event(
            #    event="page_fired", callback=lambda *_, **__: self._red_alert()
            #)
            # self._main_loop_future = self.submit_to_executor(self._main_loop)
            self.log("Pager service initialised")

    def terminate(self):
        self.log("Terminating Pager service")
        self._disconnect()
        self.log("Pager service terminated")

    def _connect(self):
        try:
            self._connection = imapclient.IMAPClient(IMAP_SERVER, IMAP_PORT)
            self._connection.login(self._username, self._password)
            self._connection.select_folder(folder="INBOX")
        except imapclient.exceptions.IMAPClientError as e:
            self.error(f"Failed to login: {e}")
            return False
        return True

    def _disconnect(self):
        try:
            self._connection.logout()
        except Exception as e:
            # Drop all errors. Maybe not neat, but ensures we keep running.
            self.log(f"Ignoring disconnect error during terminate: {e}")

    def _main_loop(self):
        while True:
            self._connection.idle()
            idle_responses = self._connection.idle_check(
                timeout=IMAP_IDLE_TIMEOUT
            )
            if idle_responses:
                self.log(f"IMAP notification: {idle_responses}")
            self._connection.idle_done()
            if not idle_responses:
                # No responses, we must have timed out: refresh the connection to
                # make sure we don't run into OS/network issues.
                self.log(
                    "Disconnecting and reconnecting for connection health."
                )
                self._disconnect()
                self._connect()
                continue

            # Otherwise, we know there's been email activity.
            uids = self._connection.search(self._search_string)
            if uids:
                # Tag the emails so we don't process them again.
                self.log(
                    f'Adding flag "{PROCESSED_KEYWORD}" to new emails uids {uids}'
                )
                response = self._connection.add_flags(uids, [PROCESSED_KEYWORD])
                self.log(f"Keyword response: {response}")

                # Flash lights
                self._red_alert()

    # Renamed in honour of Maximus
    def _red_alert(self):
        # TODO: save more state so we can restore afterwards.
        bedroom_light_on = self.get_state("group.bedroom_lights") == "on"
        keith_awake = self.get_state("input_boolean.keith_awake")
        self.log(
            f"Starting scene loads: keith_awake={keith_awake}, bedroom_light_on={bedroom_light_on}"
        )

        for i in range(LIGHT_FLASH_COUNT):
            if not keith_awake:
                self.call_service(
                    "scene/turn_on", entity_id="scene.bedroom_red"
                )
            self.call_service("scene/turn_on", entity_id="scene.office_red")
            time.sleep(1)

            if not keith_awake:
                self.call_service(
                    "scene/turn_on", entity_id="scene.bedroom_dim"
                )
            self.call_service(
                "scene/turn_on", entity_id="scene.office_concentrate"
            )
            time.sleep(1)

        if not bedroom_light_on:
            self.call_service(
                "light/turn_off", entity_id="group.bedroom_lights"
            )
