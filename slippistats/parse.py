from __future__ import annotations

import io
import mmap
import os
from pathlib import Path
from typing import Any, BinaryIO, Callable

import ubjson

from .event import End, EventType, Frame, Start
from .log import log
from .metadata import Metadata
from .util import (
    Enum,
    expect_bytes,
    unpack_int32,
    unpack_uint8,
    unpack_uint16,
)

# TODO parse maybe to pass around metadata/start event to allow for "smarter" parsing (e.g. enum char states by char)
# otherwise, frame event does contain character so that can be used

# It would also carry slippi file version which could make parsing not require try-except

# Also might be worth not enuming anything at parse time and instead using the "get()" to enum.
# Saves processing time for everyenum value not used.
# try_enum does take a pretty significant portion of the Game instantiation time


class ParseEvent(Enum):
    """Parser events, used as keys for event handlers.
    Docstrings indicate the type of object that will be passed to each handler."""

    METADATA = "metadata"
    METADATA_RAW = "metadata_raw"
    START = "start"
    FRAME = "frame"
    END = "end"
    FRAME_START = "frame_start"
    ITEM = "item"
    FRAME_END = "frame_end"


class ParseError(IOError):
    def __init__(self, message, filename=None, pos=None):
        super().__init__(message)
        self.filename = filename
        self.pos = pos

    def __str__(self):
        return f'Parse error ({self.filename or "?"} {self.pos if self.pos else "?"}): {super().__str__()}'


def _parse_event_payloads(stream):
    (code,) = unpack_uint8(stream.read(1))
    (this_size,) = unpack_uint8(stream.read(1))

    event_type = EventType(code)
    if event_type is not EventType.EVENT_PAYLOADS:
        raise ValueError(f"expected event payloads, but got {event_type}")

    this_size -= 1  # includes size byte for some reason
    command_count = this_size // 3
    if command_count * 3 != this_size:
        raise ValueError(f"payload size not divisible by 3: {this_size}")

    sizes = {}
    for i in range(command_count):
        (code,) = unpack_uint8(stream.read(1))
        (size,) = unpack_uint16(stream.read(2))
        sizes[code] = size
        try:
            EventType(code)
        except ValueError:
            log.info("ignoring unknown event type: 0x%02x" % code)

    # log.debug(f'event payload sizes: {sizes}')
    return (2 + this_size, sizes)


# This essentially acts as a jump table in _parse_event,
# saves a lot of processing on a potentially very hot match statement and enum call
# If python was compiled, this would probably be unnecessary.
EVENT_TYPE_PARSE = {
    # EventType.GAME_START: lambda stream, replay_version: Start._parse(stream, replay_version),
    EventType.FRAME_START: lambda stream, replay_version: Frame.Event(
        Frame.Event.Id(stream, replay_version), Frame.Event.Type.START, stream, replay_version
    ),
    EventType.FRAME_PRE: lambda stream, replay_version: Frame.Event(
        Frame.Event.PortId(stream, replay_version), Frame.Event.Type.PRE, stream, replay_version
    ),
    EventType.FRAME_POST: lambda stream, replay_version: Frame.Event(
        Frame.Event.PortId(stream, replay_version), Frame.Event.Type.POST, stream, replay_version
    ),
    EventType.ITEM: lambda stream, replay_version: Frame.Event(
        Frame.Event.Id(stream, replay_version), Frame.Event.Type.ITEM, stream, replay_version
    ),
    EventType.FRAME_END: lambda stream, replay_version: Frame.Event(
        Frame.Event.Id(stream, replay_version), Frame.Event.Type.END, stream, replay_version
    ),
    EventType.GAME_END: lambda stream, replay_version: End._parse(stream, replay_version),
}


def _parse_event(event_stream, payload_sizes, replay_version):
    (code,) = unpack_uint8(event_stream.read(1))
    # log.debug(f'Event: 0x{code:x}')

    # It's not great, but ripping this out saves something like 15-30% of processing time. tell() is INCREDIBLY slow
    # remember starting pos for better error reporting
    # try: base_pos = event_stream.tell() if event_stream.seekable() else None
    # except AttributeError: base_pos = None

    try:
        size = payload_sizes[code]
    except KeyError:
        raise ValueError("unexpected event type: 0x%02x" % code)

    stream = io.BytesIO(event_stream.read(size))

    try:
        event = EVENT_TYPE_PARSE.get(code, None)
        if callable(event):
            event = event(stream, replay_version)
        # try:
        #     try: event_type = EventType(code)
        #     except ValueError: event_type = None

        #     match event_type:
        #         case EventType.FRAME_PRE:
        #             event = Frame.Event(Frame.Event.PortId(stream),
        #                                 Frame.Event.Type.PRE,
        #                                 stream)
        #         case EventType.FRAME_POST:
        #             event = Frame.Event(Frame.Event.PortId(stream),
        #                                 Frame.Event.Type.POST,
        #                                 stream)
        #         case EventType.ITEM:
        #             event = Frame.Event(Frame.Event.Id(stream),
        #                                 Frame.Event.Type.ITEM,
        #                                 stream)
        #         case EventType.FRAME_START:
        #             event = Frame.Event(Frame.Event.Id(stream),
        #                                 Frame.Event.Type.START,
        #                                 stream)
        #         case EventType.FRAME_END:
        #             event = Frame.Event(Frame.Event.Id(stream),
        #                                 Frame.Event.Type.END,
        #                                 stream)
        #         case EventType.GAME_START:
        #             event = Start._parse(stream)
        #         case EventType.GAME_END:
        #             event = End._parse(stream)
        #         case _:
        #             event = None

        return (1 + size, event, code)
    except Exception as exc:
        # Calculate the stream position of the exception as best we can.
        # This won't be perfect: for an invalid enum, the calculated position
        # will be *after* the value at minimum, and may be farther than that
        # due to `unpack`ing multiple values at once. But it's better than
        # leaving it up to the `catch` clause in `parse`, because that will
        # always report a position that's at the end of an event (due to
        # `event_stream.read` above).
        raise ParseError(str(exc))  # pos = base_pos + stream.tell() if base_pos else None)


# exceptional ugliness to implement a jump table instead of a bunch of conditionals or a match statement.
def _pre_frame(
    current_frame: Frame,
    event: Frame.Event,
    handlers: dict,
    skip_frames,
    total_size,
    bytes_read,
    payload_sizes,
    stream,
    replay_version,
):
    # Accumulate all events for a single frame into a single `Frame` object.

    # We can't use Frame Bookend events to detect end-of-frame,
    # as they don't exist before Slippi 3.0.0.
    if current_frame and current_frame.index != event.id.frame:
        current_frame._finalize()
        handlers[Frame](current_frame)
        current_frame = None

    if not current_frame:
        current_frame = Frame(event.id.frame)

    port = current_frame.ports[event.id.port]
    if not port:
        port = Frame.Port()
        current_frame.ports[event.id.port] = port
    if not event.id.is_follower:
        data = port.leader
    else:
        if port.follower is None:
            port.follower = Frame.Port.Data()
        data = port.follower
    data._pre = event.raw_data
    return current_frame


def _post_frame(
    current_frame,
    event,
    handlers,
    skip_frames,
    total_size,
    bytes_read,
    payload_sizes,
    stream,
    replay_version,
):
    # Accumulate all events for a single frame into a single `Frame` object.

    # We can't use Frame Bookend events to detect end-of-frame,
    # as they don't exist before Slippi 3.0.0.
    if current_frame and current_frame.index != event.id.frame:
        current_frame._finalize()
        handlers[Frame](current_frame)
        current_frame = None

    if not current_frame:
        current_frame = Frame(event.id.frame)

    port = current_frame.ports[event.id.port]
    if not port:
        port = Frame.Port()
        current_frame.ports[event.id.port] = port
    if not event.id.is_follower:
        data = port.leader
    else:
        if port.follower is None:
            port.follower = Frame.Port.Data()
        data = port.follower
    data._post = event.raw_data
    return current_frame


def _item_frame(
    current_frame,
    event,
    handlers,
    skip_frames,
    total_size,
    bytes_read,
    payload_sizes,
    stream,
    replay_version,
):
    # Accumulate all events for a single frame into a single `Frame` object.

    # We can't use Frame Bookend events to detect end-of-frame,
    # as they don't exist before Slippi 3.0.0.
    if current_frame and current_frame.index != event.id.frame:
        current_frame._finalize()
        handlers[Frame](current_frame)
        current_frame = None

    if not current_frame:
        current_frame = Frame(event.id.frame)

    current_frame.items.append(Frame.Item._parse(event.raw_data, replay_version))
    return current_frame


def _start_frame(
    current_frame,
    event,
    handlers,
    skip_frames,
    total_size,
    bytes_read,
    payload_sizes,
    stream,
    replay_version,
):
    # Accumulate all events for a single frame into a single `Frame` object.

    # We can't use Frame Bookend events to detect end-of-frame,
    # as they don't exist before Slippi 3.0.0.
    if current_frame and current_frame.index != event.id.frame:
        current_frame._finalize()
        handlers[Frame](current_frame)
        current_frame = None

    if not current_frame:
        current_frame = Frame(event.id.frame)

    current_frame.items.append(Frame.Start._parse(event.raw_data, replay_version))
    return current_frame


def _end_frame(
    current_frame,
    event,
    handlers,
    skip_frames,
    total_size,
    bytes_read,
    payload_sizes,
    stream,
    replay_version,
):
    # Accumulate all events for a single frame into a single `Frame` object.

    # We can't use Frame Bookend events to detect end-of-frame,
    # as they don't exist before Slippi 3.0.0.
    if current_frame and current_frame.index != event.id.frame:
        current_frame._finalize()
        handlers[Frame](current_frame)
        current_frame = None

    if not current_frame:
        current_frame = Frame(event.id.frame)

    current_frame.end = Frame.End._parse(event.raw_data, replay_version)
    return current_frame


def _game_start(
    current_frame,
    event,
    handlers,
    skip_frames,
    total_size,
    bytes_read,
    payload_sizes,
    stream,
    replay_version,
):
    handlers[Start](event)
    if skip_frames and total_size != 0:
        skip = total_size - bytes_read - payload_sizes[EventType.GAME_END.value] - 1
        stream.seek(skip, os.SEEK_CUR)
        bytes_read += skip
    return current_frame


def _game_end(
    current_frame,
    event,
    handlers,
    skip_frames,
    total_size,
    bytes_read,
    payload_sizes,
    stream,
    replay_version,
):
    handlers[End](event)
    return current_frame


def _do_nothing(
    current_frame,
    event,
    handlers,
    skip_frames,
    total_size,
    bytes_read,
    payload_sizes,
    stream,
    replay_version,
):
    pass


thing = {
    EventType.GAME_START: _game_start,
    EventType.FRAME_START: _start_frame,
    EventType.FRAME_PRE: _pre_frame,
    EventType.FRAME_POST: _post_frame,
    EventType.ITEM: _item_frame,
    EventType.FRAME_END: _end_frame,
    EventType.GAME_END: _game_end,
    16: _do_nothing,
}


def _parse_events(stream, payload_sizes, total_size, handlers, skip_frames):
    # `total_size` will be zero for in-progress replays
    current_frame = None
    bytes_read = 0
    event = None
    replay_version = None

    (event_code,) = unpack_uint8(stream.read(1))
    if event_code == 0x36:
        b = payload_sizes[event_code]
    else:
        raise ValueError(f"expected event code 0x36 (Game Start),got value {event_code}")

    start_block = io.BytesIO(stream.read(b))
    try:
        event = Start._parse(start_block)
    except Exception as exc:
        raise ParseError(str(exc))

    bytes_read += b + 1

    replay_version = event.slippi_version

    while (total_size == 0 or bytes_read < total_size) and not isinstance(event, End):
        (b, event, event_code) = _parse_event(stream, payload_sizes, replay_version)
        bytes_read += b

        # Manual jump table implementation to avoid the giant inefficient commented block below
        # For non-frame entities, current_frame is passed back without modification
        # The handlers are all closures, so it doesn't matter where they're invoked, they'll still build the Game object
        current_frame = thing[event_code](
            current_frame,
            event,
            handlers,
            skip_frames,
            total_size,
            bytes_read,
            payload_sizes,
            stream,
            replay_version,
        )

        # pattern matching a type requires type constructor, probably doesn't actually construct the type?
        # see: https://stackoverflow.com/questions/70815197
        # match event:
        #     case Frame.Event() if not skip_frames:
        #         # Accumulate all events for a single frame into a single `Frame` object.

        #         # We can't use Frame Bookend events to detect end-of-frame,
        #         # as they don't exist before Slippi 3.0.0.
        #         if current_frame and current_frame.index != event.id.frame:
        #             current_frame._finalize()
        #             handlers[Frame](current_frame)
        #             current_frame = None

        #         if not current_frame:
        #             current_frame = Frame(event.id.frame)

        #         match event.type:
        #             case Frame.Event.Type.PRE | Frame.Event.Type.POST:
        #                 port = current_frame.ports[event.id.port]
        #                 if not port:
        #                     port = Frame.Port()
        #                     current_frame.ports[event.id.port] = port
        #                 if event.id.is_follower:
        #                     if port.follower is None:
        #                         port.follower = Frame.Port.Data()
        #                         data = port.follower
        #                 else:
        #                     data = port.leader

        #                 if event.type is Frame.Event.Type.PRE:
        #                     data._pre = event.data
        #                 else:
        #                     data._post = event.data
        #             case Frame.Event.Type.ITEM:
        #                 current_frame.items.append(Frame.Item._parse(event.data))
        #             case Frame.Event.Type.START:
        #                 current_frame.start = Frame.Start._parse(event.data)
        #             case Frame.Event.Type.END:
        #                 current_frame.end = Frame.End._parse(event.data)
        #             case _:
        #                 raise ValueError(f'unknown frame data type: {event.data}')
        #     # Start/End events are put at the end for optimization purposes - frame events happen far more frequently.
        #     case Start():
        #         handlers[Start](event)
        #         if skip_frames and total_size !=0:
        #             skip = total_size - bytes_read - payload_sizes[EventType.GAME_END.value] - 1
        #             stream.seek(skip, os.SEEK_CUR)
        #             bytes_read += skip
        #             continue
        #     case End():
        #         handlers[End](event)

    if current_frame:
        current_frame._finalize()
        handlers[Frame](current_frame)


def _parse(stream, handlers, skip_frames):
    # For efficiency, don't send the whole file through ubjson.
    # Instead, assume `raw` is the first element. This is brittle and
    # ugly, but it's what the official parser does so it should be OK.
    expect_bytes(b"{U\x03raw[$U#l", stream)
    (length,) = unpack_int32(stream.read(4))

    (bytes_read, payload_sizes) = _parse_event_payloads(stream)
    if length != 0:
        length -= bytes_read

    _parse_events(stream, payload_sizes, length, handlers, skip_frames)

    expect_bytes(b"U\x08metadata", stream)

    json = ubjson.load(stream)
    handlers[dict](json)

    metadata = Metadata._parse(json)
    handlers[Metadata](metadata)

    expect_bytes(b"}", stream)


def _parse_try(source: BinaryIO, handlers, skip_frames):
    """Wrap parsing exceptions with additional information."""

    try:
        _parse(source, handlers, skip_frames)
    except Exception as exception:
        exception = exception if isinstance(exception, ParseError) else ParseError(str(exception))

        try:
            exception.filename = source.name  # type: ignore
        except AttributeError:
            pass

        try:
            # prefer provided position info, as it will be more accurate
            if not exception.pos and source.seekable():  # type: ignore
                exception.pos = source.tell()  # type: ignore
        # not all stream-like objects support `seekable` (e.g. HTTP requests)
        except AttributeError:
            pass

        raise exception


def _parse_open(source: os.PathLike, handlers, skip_frames) -> None:
    with mmap.mmap(os.open(source, os.O_RDONLY), 0, access=mmap.ACCESS_READ) as f:
        _parse_try(f, handlers, skip_frames)


def parse(
    source: BinaryIO | str | os.PathLike,
    handlers: dict[Any, Callable[..., None]],
    skip_frames: bool = False,
) -> None:
    """Parse a Slippi replay.
    :param input: replay file object or path
    :param handlers: dict of parse event keys to handler functions. Each event will be passed to the corresponding handler as it occurs.
    :param skip_frames: when true, skip past all frame data. Requires input to be seekable.
    """

    if isinstance(source, str):
        _parse_open(Path(source), handlers, skip_frames)
    elif isinstance(source, os.PathLike):
        _parse_open(source, handlers, skip_frames)
    else:
        _parse_try(source, handlers, skip_frames)
