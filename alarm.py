from abc import ABC, abstractmethod
from os import system
from os.path import expanduser
from random import randint, randrange
from time import sleep
from typing import Optional

from playsound import playsound


class Alarm(ABC):
    """Abstraction over alarm sounds (dependency inversion for the checker).

    ``max_seconds`` bounds the otherwise-infinite loops, which is useful for
    testing; it defaults to ``None`` (run forever, as before).
    """

    @abstractmethod
    def sound(self, max_seconds: Optional[float] = None) -> None:
        ...


class BellAlarm(Alarm):
    def sound(self, max_seconds: Optional[float] = None) -> None:
        total_duration = 0.0
        limit = 8 * 60 * 60 if max_seconds is None else max_seconds  # 8 hours by default
        while total_duration < limit:
            duration = 1.0 / randint(5, 10)
            print("\a", end="\r")
            sleep(duration)
            total_duration += duration


class SineBellAlarm(Alarm):
    def sound(self, max_seconds: Optional[float] = None) -> None:
        total_duration = 0.0
        limit = 10.0 if max_seconds is None else min(max_seconds, 10.0)
        while total_duration < limit:
            duration = 1.0 / randint(5, 10)
            freq = randrange(200, 2000, 200)
            system("play --no-show-progress --null --channels 1 synth {} sine {}".format(duration, freq))
            total_duration += duration


class AudioFileAlarm(Alarm):
    def __init__(self, path: str):
        self.path = path

    def sound(self, max_seconds: Optional[float] = None) -> None:
        path = self.path.strip()
        if path.find("~") == 0:
            path = expanduser("~") + path[1:]
        if max_seconds is not None:
            playsound(path)  # bounded: play once
            return
        while True:
            playsound(path)


def create_alarm(path: str = None) -> Alarm:
    """Simple factory: pick the right alarm for the configured path."""
    if path is not None:
        return AudioFileAlarm(path)
    return BellAlarm()
