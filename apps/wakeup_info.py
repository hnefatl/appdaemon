from typing import Any, Iterable, Collection

import dataclasses
import datetime
import json
import dateutil.parser
import requests
import zoneinfo

import typed_hass

TIMEZONE = zoneinfo.ZoneInfo("Europe/London")

MOCK_DATA = """{"data":{"timelines":[{"timestep":"1h","endTime":"2024-10-11T00:00:00+01:00","startTime":"2024-10-09T00:00:00+01:00","intervals":[{"startTime":"2024-10-09T00:00:00+01:00","values":{"dewPoint":11.38,"humidity":91,"precipitationIntensity":0,"precipitationProbability":0,"temperature":12.88,"uvIndex":0}},{"startTime":"2024-10-09T01:00:00+01:00","values":{"dewPoint":11.38,"humidity":89,"precipitationIntensity":0.69,"precipitationProbability":20,"temperature":13.19,"uvIndex":0}},{"startTime":"2024-10-09T02:00:00+01:00","values":{"dewPoint":11.31,"humidity":89,"precipitationIntensity":0,"precipitationProbability":0,"temperature":13,"uvIndex":0}},{"startTime":"2024-10-09T03:00:00+01:00","values":{"dewPoint":11.31,"humidity":90,"precipitationIntensity":0.61,"precipitationProbability":25,"temperature":12.81,"uvIndex":0}},{"startTime":"2024-10-09T04:00:00+01:00","values":{"dewPoint":11.13,"humidity":91,"precipitationIntensity":0,"precipitationProbability":0,"temperature":12.38,"uvIndex":0}},{"startTime":"2024-10-09T05:00:00+01:00","values":{"dewPoint":10.88,"humidity":93,"precipitationIntensity":0,"precipitationProbability":0,"temperature":12.13,"uvIndex":0}},{"startTime":"2024-10-09T06:00:00+01:00","values":{"dewPoint":10.88,"humidity":92,"precipitationIntensity":0,"precipitationProbability":0,"temperature":12.19,"uvIndex":0}},{"startTime":"2024-10-09T07:00:00+01:00","values":{"dewPoint":10.88,"humidity":92,"precipitationIntensity":0,"precipitationProbability":0,"temperature":12.19,"uvIndex":0}},{"startTime":"2024-10-09T08:00:00+01:00","values":{"dewPoint":11.69,"humidity":93,"precipitationIntensity":0,"precipitationProbability":0,"temperature":12.81,"uvIndex":0}},{"startTime":"2024-10-09T09:00:00+01:00","values":{"dewPoint":11.63,"humidity":91,"precipitationIntensity":0,"precipitationProbability":0,"temperature":13.19,"uvIndex":0}},{"startTime":"2024-10-09T10:00:00+01:00","values":{"dewPoint":11.5,"humidity":86,"precipitationIntensity":0,"precipitationProbability":0,"temperature":13.81,"uvIndex":0}},{"startTime":"2024-10-09T11:00:00+01:00","values":{"dewPoint":11.31,"humidity":81,"precipitationIntensity":0,"precipitationProbability":0,"temperature":14.5,"uvIndex":1}},{"startTime":"2024-10-09T12:00:00+01:00","values":{"dewPoint":11,"humidity":78,"precipitationIntensity":0,"precipitationProbability":0,"temperature":14.69,"uvIndex":1}},{"startTime":"2024-10-09T13:00:00+01:00","values":{"dewPoint":10.81,"humidity":74,"precipitationIntensity":0,"precipitationProbability":0,"temperature":15.38,"uvIndex":1}},{"startTime":"2024-10-09T14:00:00+01:00","values":{"dewPoint":10.38,"humidity":69,"precipitationIntensity":0,"precipitationProbability":0,"temperature":16,"uvIndex":1}},{"startTime":"2024-10-09T15:00:00+01:00","values":{"dewPoint":10.19,"humidity":67,"precipitationIntensity":0,"precipitationProbability":0,"temperature":16.19,"uvIndex":0}},{"startTime":"2024-10-09T16:00:00+01:00","values":{"dewPoint":10.38,"humidity":70,"precipitationIntensity":0,"precipitationProbability":0,"temperature":15.88,"uvIndex":0}},{"startTime":"2024-10-09T17:00:00+01:00","values":{"dewPoint":10.38,"humidity":74,"precipitationIntensity":0,"precipitationProbability":0,"temperature":15.13,"uvIndex":0}},{"startTime":"2024-10-09T18:00:00+01:00","values":{"dewPoint":11,"humidity":82,"precipitationIntensity":0,"precipitationProbability":0,"temperature":14,"uvIndex":0}},{"startTime":"2024-10-09T19:00:00+01:00","values":{"dewPoint":10.88,"humidity":86,"precipitationIntensity":0,"precipitationProbability":0,"temperature":13.19,"uvIndex":0}},{"startTime":"2024-10-09T20:00:00+01:00","values":{"dewPoint":10.5,"humidity":88,"precipitationIntensity":0,"precipitationProbability":0,"temperature":12.38,"uvIndex":0}},{"startTime":"2024-10-09T21:00:00+01:00","values":{"dewPoint":10.5,"humidity":88,"precipitationIntensity":0,"precipitationProbability":0,"temperature":12.5,"uvIndex":0}},{"startTime":"2024-10-09T22:00:00+01:00","values":{"dewPoint":10,"humidity":84,"precipitationIntensity":0,"precipitationProbability":0,"temperature":12.63,"uvIndex":0}},{"startTime":"2024-10-09T23:00:00+01:00","values":{"dewPoint":9.5,"humidity":83,"precipitationIntensity":0,"precipitationProbability":0,"temperature":12.31,"uvIndex":0}},{"startTime":"2024-10-10T00:00:00+01:00","values":{"dewPoint":10,"humidity":85,"precipitationIntensity":0,"precipitationProbability":0,"temperature":12.31,"uvIndex":0}},{"startTime":"2024-10-10T01:00:00+01:00","values":{"dewPoint":9.53,"humidity":83.95,"precipitationIntensity":0,"precipitationProbability":0,"temperature":12.16,"uvIndex":0}},{"startTime":"2024-10-10T02:00:00+01:00","values":{"dewPoint":9.29,"humidity":86.06,"precipitationIntensity":0,"precipitationProbability":0,"temperature":11.54,"uvIndex":0}},{"startTime":"2024-10-10T03:00:00+01:00","values":{"dewPoint":9.04,"humidity":83.02,"precipitationIntensity":0.14,"precipitationProbability":6,"temperature":11.83,"uvIndex":0}},{"startTime":"2024-10-10T04:00:00+01:00","values":{"dewPoint":8.53,"humidity":82.76,"precipitationIntensity":0.02,"precipitationProbability":10,"temperature":11.35,"uvIndex":0}},{"startTime":"2024-10-10T05:00:00+01:00","values":{"dewPoint":7.84,"humidity":81.32,"precipitationIntensity":0,"precipitationProbability":0,"temperature":10.91,"uvIndex":0}},{"startTime":"2024-10-10T06:00:00+01:00","values":{"dewPoint":6.81,"humidity":80.56,"precipitationIntensity":0.08,"precipitationProbability":10,"temperature":10,"uvIndex":0}},{"startTime":"2024-10-10T07:00:00+01:00","values":{"dewPoint":7.12,"humidity":85.13,"precipitationIntensity":0.27,"precipitationProbability":10,"temperature":9.49,"uvIndex":0}},{"startTime":"2024-10-10T08:00:00+01:00","values":{"dewPoint":6.68,"humidity":83.71,"precipitationIntensity":0.04,"precipitationProbability":10,"temperature":9.29,"uvIndex":0}},{"startTime":"2024-10-10T09:00:00+01:00","values":{"dewPoint":5.65,"humidity":79.92,"precipitationIntensity":0.27,"precipitationProbability":15,"temperature":8.93,"uvIndex":0}},{"startTime":"2024-10-10T10:00:00+01:00","values":{"dewPoint":4.78,"humidity":71.87,"precipitationIntensity":0,"precipitationProbability":0,"temperature":9.6,"uvIndex":1}},{"startTime":"2024-10-10T11:00:00+01:00","values":{"dewPoint":4.17,"humidity":64.48,"precipitationIntensity":0,"precipitationProbability":0,"temperature":10.59,"uvIndex":1}},{"startTime":"2024-10-10T12:00:00+01:00","values":{"dewPoint":4.02,"humidity":60.26,"precipitationIntensity":0,"precipitationProbability":0,"temperature":11.44,"uvIndex":2}},{"startTime":"2024-10-10T13:00:00+01:00","values":{"dewPoint":3.75,"humidity":57.5,"precipitationIntensity":0,"precipitationProbability":0,"temperature":11.87,"uvIndex":1}},{"startTime":"2024-10-10T14:00:00+01:00","values":{"dewPoint":3.2,"humidity":54.34,"precipitationIntensity":0,"precipitationProbability":0,"temperature":12.13,"uvIndex":1}},{"startTime":"2024-10-10T15:00:00+01:00","values":{"dewPoint":2.76,"humidity":53.05,"precipitationIntensity":0,"precipitationProbability":0,"temperature":12.03,"uvIndex":1}},{"startTime":"2024-10-10T16:00:00+01:00","values":{"dewPoint":2.14,"humidity":51.8,"precipitationIntensity":0,"precipitationProbability":0,"temperature":11.72,"uvIndex":0}},{"startTime":"2024-10-10T17:00:00+01:00","values":{"dewPoint":1.59,"humidity":52.2,"precipitationIntensity":0,"precipitationProbability":0,"temperature":11.01,"uvIndex":0}},{"startTime":"2024-10-10T18:00:00+01:00","values":{"dewPoint":1.81,"humidity":58.55,"precipitationIntensity":0,"precipitationProbability":0,"temperature":9.53,"uvIndex":0}},{"startTime":"2024-10-10T19:00:00+01:00","values":{"dewPoint":1.95,"humidity":67.51,"precipitationIntensity":0,"precipitationProbability":0,"temperature":7.58,"uvIndex":0}},{"startTime":"2024-10-10T20:00:00+01:00","values":{"dewPoint":2.06,"humidity":73.02,"precipitationIntensity":0,"precipitationProbability":0,"temperature":6.55,"uvIndex":0}},{"startTime":"2024-10-10T21:00:00+01:00","values":{"dewPoint":2.07,"humidity":77.11,"precipitationIntensity":0,"precipitationProbability":0,"temperature":5.77,"uvIndex":0}},{"startTime":"2024-10-10T22:00:00+01:00","values":{"dewPoint":2.15,"humidity":79.72,"precipitationIntensity":0,"precipitationProbability":0,"temperature":5.37,"uvIndex":0}},{"startTime":"2024-10-10T23:00:00+01:00","values":{"dewPoint":2.1,"humidity":85.47,"precipitationIntensity":0,"precipitationProbability":0,"temperature":4.32,"uvIndex":0}},{"startTime":"2024-10-11T00:00:00+01:00","values":{"dewPoint":2.03,"humidity":90.1,"precipitationIntensity":0,"precipitationProbability":0,"temperature":3.5,"uvIndex":0}}]}]}}
"""


def mean[T](xs: Collection[float], default: T = None) -> float | T:
    if not xs:
        return default
    return sum(xs) / len(xs)


@dataclasses.dataclass(frozen=True)
class ForecastSnapshot:
    precipitation_probability: float | None
    precipitation_intensity: float | None
    temperature: float | None
    humidity: float | None
    dew_point: float | None
    uv_index: float | None


type Hour = int


class Forecast:
    def __init__(self, data: str):
        self.days = dict[datetime.date, dict[Hour, ForecastSnapshot]]()

        for timeline in json.loads(data)["data"]["timelines"][0]["intervals"]:
            time = dateutil.parser.parse(timeline["startTime"]).astimezone(TIMEZONE)

            if time.date() not in self.days:
                self.days[time.date()] = {}
            self.days[time.date()][time.hour] = ForecastSnapshot(
                precipitation_probability=timeline["values"].get(
                    "precipitationProbability"
                ),
                precipitation_intensity=timeline["values"].get(
                    "precipitationIntensity"
                ),
                temperature=timeline["values"].get("temperature"),
                humidity=timeline["values"].get("humidity"),
                dew_point=timeline["values"].get("dewPoint"),
                uv_index=timeline["values"].get("uvIndex"),
            )

    def __str__(self) -> str:
        return str(self.days)

    def _get_value(self, field: str, hour: Hour, day_delta: int) -> float | None:
        key = datetime.date.today() + datetime.timedelta(days=day_delta)
        if not (day_info := self.days.get(key)):
            raise ValueError(key)
            return None
        if not (hour_info := day_info.get(hour)):
            raise ValueError("b")
            return None
        return getattr(hour_info, field)

    def _get_values(
        self, field: str, hours: Iterable[Hour], day_delta: int = 0
    ) -> list[float]:
        return [
            val for hour in hours if (val := self._get_value(field, hour, day_delta))
        ]

    def precipitation_probability(self, hour: Hour, day_delta: int = 0) -> float | None:
        return self._get_value("precipitation_probability", hour, day_delta)

    def precipitation_intensity(self, hour: Hour, day_delta: int = 0) -> float | None:
        return self._get_value("precipitation_intensity", hour, day_delta)

    def temperature(self, hour: Hour, day_delta: int = 0) -> float | None:
        return self._get_value("temperature", hour, day_delta)

    def temperatures(self, hours: Iterable[Hour], day_delta: int = 0) -> list[float]:
        return self._get_values("temperature", hours, day_delta)


class WakeupInfo(typed_hass.Hass):
    def initialize(self):
        self.listen_event(event="ANNOUNCE_WEATHER", callback=self.on_event)
        # await self.on_event("", {"mock": True, "print_raw_data": True}, {})

    def on_event(
        self, _event_name: str, data: dict[str, Any], _user_args: dict[str, Any]
    ):
        use_mock_data = data.get("mock", False)
        print_raw_data = data.get("print_raw_data", False)
        result: str
        if use_mock_data:
            result = MOCK_DATA
            self.info_log("using mock data")
        else:
            self.info_log("Fetching weather")
            response = requests.post(
                url="https://api.tomorrow.io/v4/timelines",
                params={"apikey": self.args.get("api_key")},
                # https://docs.tomorrow.io/reference/post-timelines
                json={
                    "location": self.args.get("location"),
                    "units": "metric",
                    # https://docs.tomorrow.io/reference/data-layers-core
                    "fields": [
                        "precipitationProbability",
                        "precipitationIntensity",
                        "temperature",
                        "humidity",
                        "dewPoint",
                        "uvIndex",
                    ],
                    "timesteps": ["1h"],
                    "timezone": "auto",
                    "startTime": "nowMinus1d",
                    "endTime": "nowPlus1d",
                },
            )
            self.info_log("Fetched weather")
            if response.status_code != 200:
                raise RuntimeError(f"{response.status_code}: {response.text}")
            result = response.text

        forecast = Forecast(result)
        if print_raw_data:
            print(result)

        messages = list[str]()

        if datetime.datetime.today().weekday() <= 5:
            # On workdays, warn about rain only during commute times.
            rain_chances = {
                hour: forecast.precipitation_probability(hour=hour)
                for hour in [9, 10, 18, 19]
            }
            morning_rain_chance = (rain_chances.get(9) or 0) + (
                rain_chances.get(10) or 0
            )
            evening_rain_chance = (rain_chances.get(18) or 0) + (
                rain_chances.get(19) or 0
            )
            self.info_log(f"rain chances: {rain_chances}")
            if morning_rain_chance > 0:
                messages.append("It'll rain in the morning.")
            if evening_rain_chance > 0:
                messages.append("It'll rain in the evening.")
        else:
            # On weekends, warn about any rain since I might go out at any time.
            # TODO
            pass

        today_mean_temp = mean(forecast.temperatures(hours=range(9, 18)))
        yesterday_mean_temp = mean(
            forecast.temperatures(hours=range(9, 18), day_delta=-1)
        )
        self.info_log(
            f"today mean temp: {today_mean_temp}, yesterday mean temp: {yesterday_mean_temp}"
        )
        if yesterday_mean_temp is not None and today_mean_temp is not None:
            if today_mean_temp <= yesterday_mean_temp - 2:
                messages.append("It'll be cold today.")
            if today_mean_temp >= yesterday_mean_temp + 2:
                messages.append("It'll be hot today.")

        if messages:
            self.tts_speak(
                "\n".join(messages),
                media_player=typed_hass.MediaPlayer("bedroom_speaker"),
            )
