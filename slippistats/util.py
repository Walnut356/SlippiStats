import enum
import re
import struct
from functools import lru_cache
from typing import Any

from .log import log


class Port(enum.IntEnum):
    NONE = -1
    P1 = 0
    P2 = 1
    P3 = 2
    P4 = 3


# Pre-allocating these prevents python from recreating the object on every struct.unpack() call
# which saves a non-negligable amount of processing time.
unpack_uint8 = struct.Struct(">B").unpack

unpack_uint16 = struct.Struct(">H").unpack

unpack_uint32 = struct.Struct(">I").unpack

unpack_int8 = struct.Struct(">b").unpack

unpack_int16 = struct.Struct(">h").unpack

unpack_int32 = struct.Struct(">i").unpack

unpack_float = struct.Struct(">f").unpack

unpack_bool = struct.Struct(">?").unpack

unpack_matchid = struct.Struct(">50s").unpack  # this one is special =)


def _indent(s):
    return re.sub(r"^", "    ", s, flags=re.MULTILINE)


def _format_collection(coll, delim_open, delim_close):
    elements = [_format(x) for x in coll]
    if elements and "\n" in elements[0]:
        return delim_open + "\n" + ",\n".join(_indent(e) for e in elements) + delim_close
    else:
        return delim_open + ", ".join(elements) + delim_close


def _format(obj):
    if isinstance(obj, float):
        return "%.02f" % obj
    elif isinstance(obj, tuple):
        return _format_collection(obj, "(", ")")
    elif isinstance(obj, list):
        return _format_collection(obj, "[", "]")
    elif isinstance(obj, enum.Enum):
        return repr(obj)
    else:
        return str(obj)


# Depreciated for performance reasons. See unpack_type objects above
def unpack(fmt, stream):
    fmt = ">" + fmt
    size = struct.calcsize(fmt)
    bytes = stream.read(size)
    if not bytes:
        raise EOFError()
    return struct.unpack(fmt, bytes)


def expect_bytes(expected_bytes, stream):
    read_bytes = stream.read(len(expected_bytes))
    if read_bytes != expected_bytes:
        raise AssertionError(f"expected {expected_bytes}, but got: {read_bytes}")


class Base:
    # __slots__: Tuple = ()

    def _attr_repr(self, attr):
        return attr + "=" + _format(getattr(self, attr))

    def __repr__(self):
        attrs = []
        for attr in dir(self):
            # uppercase names are nested classes
            if not callable(getattr(self, attr)) and not (attr.startswith("_") or attr[0].isupper()):
                s = self._attr_repr(attr)
                if s:
                    attrs.append(_indent(s))

        return "%s(\n%s)" % (self.__class__.__name__, ",\n".join(attrs))


class Enum(enum.Enum):
    def __repr__(self):
        return f"{self.value}:{self.name}"


class IntEnum(enum.IntEnum):
    def __repr__(self):
        return f"{self._value_}:{self._name_}"

    @classmethod
    def _missing_(cls, value):
        val_desc = f"0x{value:x}" if isinstance(value, int) else f"{value}"
        raise ValueError(f"{val_desc} is not a valid {cls.__name__}") from None


class EOFError(IOError):
    def __init__(self):
        super().__init__("unexpected end of file")


@lru_cache(maxsize=512)
def try_enum(enum_type, val) -> Enum | Any:
    """Attempts Enum(val). If the value is invalid, returns the given value."""
    try:
        return enum_type(val)
    except ValueError:
        log.info("unknown %s: %s" % (enum_type.__name__, val))
        return val
