from abc import ABC, abstractmethod
from os import system
from os.path import expanduser
from random import randint, randrange
from time import sleep

from playsound import playsound


class Alarm(ABC):
    """Abstraction over alarm sounds (dependency inversion for the checker)."""

    @abstractmethod
    def sound(self) -> None:
        ...


class BellAlarm(Alarm):
    def sound(self) -> None:
        total_duration = 0.0
        while total_duration < 8 * 60 * 60:  # 8 hours
            duration = 1.0 / randint(5, 10)
            print("\a", end="\r")
            sleep(duration)
            total_duration += duration


class SineBellAlarm(Alarm):
    def sound(self) -> None:
        total_duration = 0.0
        while total_duration < 10.0:
            duration = 1.0 / randint(5, 10)
            freq = randrange(200, 2000, 200)
            system("play --no-show-progress --null --channels 1 synth {} sine {}".format(duration, freq))
            total_duration += duration


class AudioFileAlarm(Alarm):
    def __init__(self, path: str):
        self.path = path

    def sound(self) -> None:
        path = self.path.strip()
        if path.find("~") == 0:
            path = expanduser("~") + path[1:]
        while True:
            playsound(path)


def create_alarm(path: str = None) -> Alarm:
    """Simple factory: pick the right alarm for the configured path."""
    if path is not None:
        return AudioFileAlarm(path)
    return BellAlarm()
