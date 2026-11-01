"""The derived placements ``derived_ut`` and ``derived_tt``.

A siddhantic record's instants are local times on a numbered civil day
(the text's own standard, ``text_local:<text_id>``); they reach Universal
Time only by a placement made *outside* the method, at the caller's
request, and are marked derived in the record. The chain:

1. the UT1 of local mean midnight at the observer, from the JDN and the
   observer's modern longitude (the ``places.yaml`` longitude datum, by
   key), under the convention that the text's mean sunrise is
   6h local mean time at its meridian, which the field names;
2. plus the text's sunrise offset from local mean midnight as the record
   carries it (``sunrise.nadika_after_local_midnight``: 15 − cara ∓
   bhujāntara where the text applies it);
3. plus the instant's nāḍikās after sunrise (a record's day start: none);
4. where the text's time reckoning is apparent, less the equation of
   time (apparent − mean) from the source ``eot_source`` names.

Steps 1 to 3 are :func:`~jyotirganita.core.types.ut1_from_text_local`,
step 4 :func:`~jyotirganita.core.types.ut1_from_apparent_reckoning`.

No text has a ``time_reckoning`` datum (the texts state the carries, not a
statement of mean or apparent reckoning), and nothing is defaulted: the
caller names the reckoning, ``mean`` or ``apparent:<eot_source>``. The
field records ``time_reckoning: {value, basis: caller}`` and every record
carrying it is flagged ``provisional:derived_ut.time_reckoning``. The
sources:

- ``text_bhujantara``: the equation the text's own carry applies, where
  the method's carry has a ``carry.bhujantara`` statement that is not a
  deferral (``deferred.*``, which applies none) and acts on the sunrise
  time; it is already inside the sunrise offset of step 2, so step 4 adds
  nothing, and the field says so. The Sūrya-siddhānta's bhujāntara acts
  on the true place (ii.46, ``carry.bhujantara_true_place``), not on the
  time, so both Sūrya-siddhānta methods refuse it;
- ``modern:<modern preset id>``: the apparent Sun of that modern preset's
  engine (its kernel, frame and ΔT model, every one named in the preset,
  so that nothing is defaulted), at the same observer, where the method's
  carry puts no bhujāntara inside the sunrise offset (none stated,
  deferred, or applied to the place); where it applies
  the text's, ``modern:`` is refused, since the equation would be applied
  twice, and ``text_bhujantara`` is the source to name; E's argument
  needs TT, and the ΔT that preset's model gives is recorded with it,
  not iterated (``modern/eot.py``).

A source the configuration cannot serve is a hard error naming it.
``derived_tt`` is TT from that UT1 by a caller-named ΔT model of
``modern/deltat.py`` (``MODELS``; ``constant:<seconds>`` for a constant
one); outside the model's range a hard error naming it; the model's own
provenance (its range, table and tidal-acceleration record) is recorded.
No ΔT enters before TT.

Neither field is part of the configuration hash: they change no computed
field. The provenance block records what produced them under
``derived``. A modern configuration carries ``tt`` and ``ut1`` of its own
on ``sunrise`` and ``sunset``, so the derived options are refused there.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import TYPE_CHECKING, Any

from jyotirganita.core.types import (
    JDN,
    UT1,
    Nadika,
    SiddhanticCivilInstant,
    ut1_from_apparent_reckoning,
    ut1_from_text_local,
)
from jyotirganita.errors import Refusal

if TYPE_CHECKING:
    from jyotirganita.config import RunConfig

__all__ = ["CONVENTION", "DerivedChain", "derived_chain"]

MEAN = "mean"
APPARENT = "apparent"
TEXT_BHUJANTARA = "text_bhujantara"
MODERN = "modern"
#: the convention the field names
CONVENTION = (
    "the text's mean sunrise is 6h local mean time at its meridian; local mean "
    "midnight at the observer from its modern longitude"
)
BHUJANTARA_SLOT = "carry.bhujantara"
#: the carry whose bhujāntara acts on the place, not the time (Sūrya-siddhānta ii.46)
BHUJANTARA_ON_PLACE = "carry.bhujantara_true_place"


@dataclass(frozen=True, slots=True)
class _Source:
    id: str
    engine: Any  # a ModernEngine for modern:<preset>, None for text_bhujantara


class DerivedChain:
    """The derived placements one caller asked for under one configuration (module docstring)."""

    def __init__(
        self,
        config: RunConfig,
        reckoning: str,
        eot: _Source | None,
        delta_t: Any | None,
        delta_t_id: str | None,
        place_id: str,
        longitude_key: str,
        longitude: Fraction,
    ) -> None:
        self.config = config
        self.reckoning = reckoning
        self.eot = eot
        self.delta_t = delta_t
        self.delta_t_id = delta_t_id
        self.place_id = place_id
        self.longitude_key = longitude_key
        self.longitude = longitude
        self.standard = config.time_standard

    def ut1(self, jdn: JDN, sunrise: Nadika, after_sunrise: Nadika) -> tuple[UT1, Any]:
        """The UT1 of an instant ``after_sunrise`` past the text's sunrise of civil day ``jdn``."""
        instant = SiddhanticCivilInstant(jdn, after_sunrise, self.standard)
        t = ut1_from_text_local(instant, sunrise, self.longitude)
        if self.eot is None or self.eot.engine is None:
            return t, None
        from jyotirganita.modern.eot import equation_of_time
        from jyotirganita.modern.timescales import OutOfRange

        try:
            e, dt = equation_of_time(self.eot.engine, t)
        except OutOfRange as exc:
            raise Refusal("derived_ut", f"{self.eot.id}: {exc}") from None
        return ut1_from_apparent_reckoning(t, e), {"days": e.value, "delta_t_seconds": dt}

    def fields(self, jdn: JDN, sunrise: Nadika | None, after_sunrise: Nadika) -> dict[str, Any]:
        """``derived_ut`` (and ``derived_tt`` when asked) of an instant of civil day ``jdn``."""
        if sunrise is None:
            raise Refusal(
                "derived_ut",
                f"civil day {jdn.value} has no sunrise in nāḍikās after local mean midnight "
                "to place (the hybrid sunrise or a modern clock)",
            )
        t, e = self.ut1(jdn, sunrise, after_sunrise)
        ut: dict[str, Any] = {
            "value": t.jd_whole + t.jd_fraction,
            "scale": "ut1",
            "place": {"id": self.place_id, "longitude": self.longitude_key},
            "convention": CONVENTION,
            "time_reckoning": {"value": self.reckoning, "basis": "caller"},
            "eot_source": None if self.eot is None else self.eot.id,
            "equation_of_time": None,
        }
        if self.eot is not None and self.eot.engine is None:
            ut["equation_of_time"] = {
                "applied_days": 0.0,
                "note": "the text's carry applies its bhujāntara inside the sunrise offset",
            }
        elif e is not None:
            ut["equation_of_time"] = {
                "apparent_minus_mean_days": e["days"],
                "argument_delta_t_seconds": e["delta_t_seconds"],
            }
        out: dict[str, Any] = {"derived_ut": ut}
        if self.delta_t is not None:
            from jyotirganita.modern.deltat import tt_of_ut1
            from jyotirganita.modern.timescales import OutOfRange

            try:
                tt, dt = tt_of_ut1(self.delta_t, t)
            except OutOfRange as exc:
                raise Refusal("derived_tt", f"{self.delta_t_id}: {exc}") from None
            out["derived_tt"] = {
                "value": tt.jd_whole + tt.jd_fraction,
                "scale": "tt",
                "delta_t_model": self.delta_t_id,
                "delta_t_seconds": dt,
            }
        return out

    def provenance(self) -> dict[str, Any]:
        """What produced the derived fields, for the provenance block's ``derived``."""
        out: dict[str, Any] = {
            "derived_ut": {
                "chain": "io/derived.py",
                "convention": CONVENTION,
                "place": {"id": self.place_id, "longitude": self.longitude_key},
                "time_reckoning": {"value": self.reckoning, "basis": "caller"},
                "eot_source": None if self.eot is None else self.eot.id,
            }
        }
        if self.eot is not None and self.eot.engine is not None:
            out["derived_ut"]["eot_engine"] = self.eot.engine.provenance()
        if self.delta_t is not None:
            p = dict(self.delta_t.provenance("-"))
            p.pop("tidal_correction", None)
            p["tidal_correction"] = "not applicable: no kernel reads this TT"
            out["derived_tt"] = {"delta_t_model": self.delta_t_id, "model": p}
        return out


def _text_carry(config: RunConfig) -> tuple[Any, str | None]:
    """The method's ``carry.bhujantara`` record and, where it applies none, why not."""
    rec = config.run.resolved.procedures.get(BHUJANTARA_SLOT)
    if rec is None or rec.kind == "gap":
        return rec, f"{config.method_id}'s carry states no bhujāntara ({BHUJANTARA_SLOT})"
    from jyotirganita.siddhantic.procedures import REGISTRY

    named = REGISTRY.get(str(rec.raw.get("procedure", "")))
    if named is not None and named.slot == "deferred":
        return rec, (
            f"{config.method_id}'s carry is deferred ({rec.key}, {named.name}), so no "
            "bhujāntara is applied"
        )
    if named is not None and named.name == BHUJANTARA_ON_PLACE:
        # the Sūrya-siddhānta's bhujāntara moves the true place (ii.46), not its sunrise
        # time, so no equation of time is inside the sunrise offset
        return rec, (
            f"{config.method_id}'s carry applies its bhujāntara to the true place "
            f"({rec.key}, {named.name}), not to the sunrise time"
        )
    return rec, None


def _eot_source(config: RunConfig, spec: str) -> _Source:
    carry, none_applied = _text_carry(config)
    if spec == TEXT_BHUJANTARA:
        if none_applied is not None:
            raise Refusal(
                "derived_ut",
                f"{TEXT_BHUJANTARA}: {none_applied}; name modern:<modern preset id> or mean",
            )
        return _Source(TEXT_BHUJANTARA, None)
    kind, sep, preset_id = spec.partition(":")
    if kind != MODERN or not sep or not preset_id:
        raise Refusal(
            "derived_ut",
            f"apparent:{spec}: the equation of time's source is {TEXT_BHUJANTARA} or "
            "modern:<modern preset id>",
        )
    if none_applied is None:
        # the text's equation is already inside the sunrise offset of step 2; a modern
        # one in step 4 would apply the equation of time twice
        raise Refusal(
            "derived_ut",
            f"apparent:{spec}: {config.method_id}'s carry already applies the text's "
            f"bhujāntara ({carry.key}) inside the sunrise offset, so a modern equation "
            f"would apply the equation of time twice; name {TEXT_BHUJANTARA}",
        )
    from jyotirganita.methods.presets import PresetError, load_preset, modern_run, resolve
    from jyotirganita.modern.kernels import KernelError
    from jyotirganita.regions.places import PlaceError

    try:
        preset = load_preset(config.repo, preset_id)
        if preset.engine != "modern":
            raise PresetError(f"{preset_id} is not a modern preset")
        res = resolve(preset, config.observer)
        from jyotirganita.config import _conventions

        conv = _conventions(config.repo, preset, config.records, config.eras)
        run = modern_run(config.repo, preset, res, conv, config.records)
    except (PresetError, PlaceError, FileNotFoundError, ValueError, KernelError) as e:
        # KernelError: a modern preset whose kernel is not fetched
        raise Refusal("derived_ut", f"apparent:{spec}: {e}") from None
    return _Source(f"modern:{preset_id}", run.engine)


def _delta_t(config: RunConfig, spec: str) -> tuple[Any, str]:
    from jyotirganita.modern.deltat import MODELS, make_model
    from jyotirganita.modern.timescales import TimeScales

    model_id, sep, seconds = spec.partition(":")
    data = config.records.data
    try:
        if model_id == "constant":
            if not sep or not seconds:
                raise ValueError("ΔT model constant takes its seconds: constant:<seconds>")
            constant = Fraction(seconds)
            float(constant)  # the model reads it as a float: 1e400 overflows here, not later
            model = make_model(model_id, TimeScales(data), data, constant_seconds=constant)
        else:
            if sep:
                raise ValueError(f"ΔT model {model_id} takes no argument")
            model = make_model(model_id, TimeScales(data), data)
    except (ValueError, ZeroDivisionError, OverflowError) as e:
        # constant:1/0 and constant:1e400
        raise Refusal("derived_tt", f"{spec!r}: {e} (models: {', '.join(MODELS)})") from None
    return model, spec


def derived_chain(
    config: RunConfig,
    derived_ut: str | None,
    derived_tt: str | None = None,
) -> DerivedChain | None:
    """The chain the caller's ``--derived-ut`` and ``--derived-tt`` name, or ``None``."""
    if derived_ut is None and derived_tt is None:
        return None
    if config.kind != "siddhantic":
        raise Refusal(
            "derived_ut",
            f"{config.preset.id} is a modern preset: its sunrise and sunset carry tt and ut1 "
            "of their own; the derived placements are a siddhantic record's",
        )
    if derived_ut is None:
        raise Refusal("derived_tt", "TT is derived from derived_ut: name --derived-ut as well")
    reckoning, sep, source = derived_ut.partition(":")
    if reckoning == MEAN and not sep:
        eot = None
    elif reckoning == APPARENT and sep and source:
        if "procedure.sunrise" in config.overrides:
            raise Refusal(
                "derived_ut",
                f"--derived-ut {derived_ut} with --set procedure.sunrise="
                f"{config.overrides['procedure.sunrise']}: the geometric sunrise is on local "
                "mean time, its day fractions are mean time by construction, so only "
                "--derived-ut mean places them",
            )
        eot = _eot_source(config, source)
    else:
        raise Refusal(
            "derived_ut",
            f"{derived_ut!r}: the caller names the reckoning, mean or apparent:<eot_source> "
            f"({TEXT_BHUJANTARA} or modern:<modern preset id>); no text states one",
        )
    from jyotirganita.regions.places import PlaceError, load_modern_place

    region, _, place = config.observer.partition("/")
    try:
        mp = load_modern_place(config.repo, region, place, config.records.data)
    except PlaceError as e:
        raise Refusal(
            "derived_ut", f"{config.observer}: {e}; derived_ut needs a modern longitude"
        ) from None
    model, model_id = (None, None) if derived_tt is None else _delta_t(config, derived_tt)
    # at user coordinates the longitude is the caller's, not a datum's
    longitude = mp.statements[1] if mp.statements else f"user:{mp.longitude_deg}"
    return DerivedChain(
        config,
        reckoning,
        eot,
        model,
        model_id,
        mp.id,
        longitude,
        mp.longitude_deg,
    )
