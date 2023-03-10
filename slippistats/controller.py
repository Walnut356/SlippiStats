from __future__ import annotations
from enum import IntFlag

from .util import Base


class Triggers(Base):
    __slots__ = 'logical', 'physical'

    logical: float  #: Processed analog trigger position
    physical: Triggers.Physical  #: Physical analog trigger positions (useful for APM)

    def __init__(self, logical: float, physical_x: float, physical_y: float):
        self.logical = logical
        self.physical = self.Physical(physical_x, physical_y)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return other.logical == self.logical and other.physical == self.physical

    class Physical(Base):
        __slots__ = 'l', 'r'

        l: float
        r: float

        def __init__(self, l: float, r: float):
            self.l = l
            self.r = r

        def __eq__(self, other):
            if not isinstance(other, self.__class__):
                return NotImplemented
            # Should we add an epsilon to these comparisons?
            # When are people going to be comparing trigger states for equality, other than in our tests?
            return other.l == self.l and other.r == self.r


class Buttons(Base):
    __slots__ = 'logical', 'physical'

    logical: Buttons.Logical  #: Processed button-state bitmask
    physical: Buttons.Physical  #: Physical button-state bitmask

    def __init__(self, logical, physical):
        self.logical = self.Logical(logical)
        self.physical = self.Physical(physical)

    def __eq__(self, other):
        if not isinstance(other, Buttons):
            return NotImplemented
        return other.logical is self.logical and other.physical is self.physical

    class Logical(IntFlag):
        TRIGGER_ANALOG = 2**31
        CSTICK_RIGHT = 2**23
        CSTICK_LEFT = 2**22
        CSTICK_DOWN = 2**21
        CSTICK_UP = 2**20
        JOYSTICK_RIGHT = 2**19
        JOYSTICK_LEFT = 2**18
        JOYSTICK_DOWN = 2**17
        JOYSTICK_UP = 2**16
        START = 2**12
        Y = 2**11
        X = 2**10
        B = 2**9
        A = 2**8
        L = 2**6
        R = 2**5
        Z = 2**4
        DPAD_UP = 2**3
        DPAD_DOWN = 2**2
        DPAD_RIGHT = 2**1
        DPAD_LEFT = 2**0
        NONE = 0

    class Physical(IntFlag):
        START = 2**12
        Y = 2**11
        X = 2**10
        B = 2**9
        A = 2**8
        L = 2**6
        R = 2**5
        Z = 2**4
        DPAD_UP = 2**3
        DPAD_DOWN = 2**2
        DPAD_RIGHT = 2**1
        DPAD_LEFT = 2**0
        NONE = 0

        def pressed(self):
            """Returns a list of all buttons being pressed."""
            pressed = []
            for button in self.__class__:
                if self & button:
                    pressed.append(button)
            return pressed