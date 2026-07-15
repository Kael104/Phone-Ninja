"""Phone Ninja — local motion-controlled fruit-slice game."""

from __future__ import annotations

from config.settings import SETTINGS
from game.engine import Engine


def main() -> None:
    engine = Engine(SETTINGS)
    engine.run()


if __name__ == "__main__":
    main()
