"""The engine protocol the calendar layer sees.

Both engines implement :class:`Engine`; the calendar layer, the record and
the search are written against it and against nothing else. The protocol
is generic over the numeric family ``A`` (``ExactArc`` for the siddhantic
engine, ``FloatArc`` for the modern one) and over the instant form ``I``
(``SiddhanticCivilInstant`` or ``ModernCivilInstant``), so that an exact
and a float value never meet.

An engine instance is bound to one method's resolved configuration and
one observer: :meth:`Engine.civil_day` needs both. Instants are built only
through :meth:`Engine.instant`, as the frame's start plus a duration after
it (nāḍikās after sunrise under the siddhantic engine).

Stable: members are added, never
changed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from jyotirganita.core.types import (
    JDN,
    ExactArc,
    FloatArc,
    ModernCivilInstant,
    Nadika,
    NotModelled,
    SiddhanticCivilInstant,
    SiderealLongitude,
    TropicalLongitude,
    TrueOfDate,
)

__all__ = ["Capabilities", "CivilDayFrame", "Engine"]


@dataclass(frozen=True, slots=True)
class Capabilities:
    """What an engine serves.

    ``bodies`` are the bodies :meth:`Engine.sidereal_longitude` serves;
    ``not_modelled`` maps each quantity the engine does not serve
    (``latitude``, ``daily_motion``, ``distance``, ``eclipses``, ``intraday``,
    ...) to the reason, naming the package that keys it where one does.
    """

    bodies: tuple[str, ...]
    node: bool
    not_modelled: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CivilDayFrame[I: (SiddhanticCivilInstant, ModernCivilInstant)]:
    """A civil day under an engine's civil-day convention.

    ``start`` and ``end`` are the day's start and the next day's start;
    under the siddhantic engine both are sunrises and ``start`` is
    ``sunrise``. ``sunrise_after_local_midnight`` is the siddhantic
    sunrise in nāḍikās after local mean midnight;
    the modern engine leaves it ``None``. ``meridian`` names the local
    meridian (the text's meridian for the siddhantic engine, with the
    observer's offset from it). ``flags`` are the record flags the frame's
    construction raises (``provisional:<key>`` of a provisional sunrise
    rule, ``hybrid_sunrise:modern_geometric``). ``day_length_nadika``
    is the siddhantic day's computed length to the next sunrise;
    the modern engine leaves it ``None``.
    """

    jdn: JDN
    start: I
    end: I
    sunrise: I
    sunset: I | NotModelled
    sunrise_after_local_midnight: Nadika | None
    meridian: str
    flags: tuple[str, ...] = ()
    day_length_nadika: Nadika | None = None


class Engine[A: (ExactArc, FloatArc), I: (SiddhanticCivilInstant, ModernCivilInstant)](Protocol):
    """The engine protocol. ``A``: numeric family; ``I``: instant form."""

    @property
    def time_base(self) -> type:
        """``Ahargana`` (siddhantic) or ``TT`` (modern): a type, not a flag."""
        ...

    @property
    def capabilities(self) -> Capabilities:
        """Bodies served and what is not modelled."""
        ...

    def civil_day(self, jdn: JDN) -> CivilDayFrame[I]:
        """The civil day ``jdn`` at the engine's observer."""
        ...

    def instant(self, jdn: JDN, after_start: Nadika) -> I:
        """The instant ``after_start`` after the start of civil day ``jdn``."""
        ...

    def sidereal_longitude(self, body: str, instant: I) -> SiderealLongitude[A]:
        """The body's sidereal longitude in the method's frame."""
        ...

    def tropical_longitude(
        self, body: str, instant: I
    ) -> TropicalLongitude[TrueOfDate] | NotModelled:
        """The true-of-date tropical longitude (modern engine); ``not_modelled`` otherwise."""
        ...

    def daily_motion(self, body: str, day: JDN) -> A | NotModelled:
        """The text's gati (siddhantic) or the numerical rate (modern)."""
        ...

    def node(self, instant: I) -> SiderealLongitude[A] | NotModelled:
        """The Moon's ascending node: Rāhu for output and the node for latitude alike."""
        ...

    def latitude(self, body: str, instant: I) -> A | NotModelled:
        """The body's latitude by the text's rule, or ``not_modelled``."""
        ...
