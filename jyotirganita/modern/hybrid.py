"""The geometric sunrise for the siddhantic hybrid alternative.

:class:`GeometricSunrise` implements ``siddhantic.engine.SunriseProvider``
from the modern rise and set (``modern/riseset.py``) under the engine's
named ``sunrise_event``: the sunrise of civil day *d* as a fraction of the
day after local mean midnight at the observer, and the sunset after it
the same way (so that the month rules that read the sunset
serve the hybrid). The engine it wraps must
read its civil days on local mean time (the ``lmt`` standard) at the same
place as the siddhantic observer (the place ids are compared); its
sunrise is the first rise of the Sun between that day's local mean
midnights (``ModernEngine.day_bounds``).

The siddhantic engine quantises the fraction to
``siddhantic.hybrid_sunrise_quantum`` and flags every record
``hybrid_sunrise:modern_geometric`` (``siddhantic/engine.py``). The
provider's id names the event (reference, refraction model, dip), the ΔT
model and the kernel, and is recorded in the run's provenance.
"""

from __future__ import annotations

from jyotirganita.core.types import JDN
from jyotirganita.modern.engine import ModernEngine
from jyotirganita.siddhantic.engine import Observer

__all__ = ["GeometricSunrise"]


class GeometricSunrise:
    """A ``SunriseProvider`` over the modern rise and set (module docstring)."""

    def __init__(self, engine: ModernEngine) -> None:
        if engine.standard.kind != "local_mean_time":
            raise ValueError(
                f"the geometric sunrise reads local mean time; the engine's standard is "
                f"{engine.standard.id} (name a modern preset on local mean time)"
            )
        self.engine = engine
        c = engine.config
        self._id = (
            f"modern:sunrise_event={c.sunrise_event.id};delta_t={engine.delta_t.id};"
            f"kernel={engine.ephemeris.entry.id}"
        )

    @property
    def id(self) -> str:
        return self._id

    def sunrise_fraction(self, jdn: JDN, observer: Observer) -> float:
        """The sunrise of ``jdn`` as a fraction of the day after local mean midnight."""
        if observer.id != self.engine.observer.id:
            raise ValueError(
                f"the geometric sunrise is computed at {self.engine.observer.id}, not {observer.id}"
            )
        sunrise = self.engine.day_bounds(jdn)[1]
        return self.engine.civil_of_tt(sunrise, jdn).local_fraction

    def sunset_fraction(self, jdn: JDN, observer: Observer) -> float | None:
        """The sunset after that sunrise, as the same fraction (``None``: no sunset that day)."""
        if observer.id != self.engine.observer.id:
            raise ValueError(
                f"the geometric sunset is computed at {self.engine.observer.id}, not {observer.id}"
            )
        sunset = self.engine.day_bounds(jdn)[2]
        return None if sunset is None else self.engine.civil_of_tt(sunset, jdn).local_fraction
