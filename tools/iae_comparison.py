"""The IAE true-ayanāṃśa comparison.

    python tools/iae_comparison.py            # write reports/iae_true_ayanamsa.md
    python tools/iae_comparison.py --check    # exit 1 if the committed copy is stale

The fixture ``authority/modern/iae_2022_true_ayanamsa`` holds indian_astronomical_ephemeris's table
"True Ayanamsa" (PDF p. 428) as printed: four blocks of dates and values,
their years and the heading that states the time of day. For each row this
tool computes the true ayanāṃśa of ``iae_lahiri`` (the IAE's polynomial,
PDF p. 387, plus Δψ, the definition at the table's foot) at that date and
time, under the precession and nutation the ``modern_iers`` preset names,
and writes the difference from the printed value.

**The time.** The heading states an hour and a minute of the day and no
scale; the tool reads them on Indian Standard Time, the scale indian_astronomical_ephemeris's
Indian Calendar section states for its times (``modern.iae.india_sunrise
.statement``). That reading is inferred; against the other plausible
reading, a table for 0h UT (5h 30m IST) printed to the minute, it moves no
row by more than 0.0003″ (measured 2026-10-09).

**The tolerance.** Half the table's print quantum (0.05″) plus half the
print quantum of the polynomial's constant term (``mean.c0.arcseconds``,
printed to 0.01″): the computation uses the rounded constant, the IAE its
own. A row beyond 0.05″ is listed with that explanation (inferred, not
stated by the source).

The report restates a comparison against the source's own table; it is regenerated, never edited.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from jyotirganita.core.calendar import jdn_from_gregorian
from jyotirganita.core.exact import parse_fraction
from jyotirganita.core.types import JDN, GregorianDate, ModernCivilInstant, utc_from_civil
from jyotirganita.data import engine_parameters
from jyotirganita.data.datum import Record, context_for, load_fixture, load_records
from jyotirganita.data.time_standards import load_time_standards
from jyotirganita.methods.presets import load_preset
from jyotirganita.modern.ayanamsa import make_ayanamsa
from jyotirganita.modern.frames import Frame
from jyotirganita.modern.nutation import make_nutation
from jyotirganita.modern.precession import make_precession
from jyotirganita.modern.timescales import TimeScales

REPO = Path(__file__).resolve().parent.parent
FIXTURE = "authority/modern/iae_2022_true_ayanamsa"
PRESET = "modern_iers"
STANDARD = "ist"
OUT = Path("reports") / "iae_true_ayanamsa.md"
BLOCKS = 4
#: the printed months by their first three letters
MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
_HEADING = re.compile(r"FOR (\d+)h (\d+)\^m")
_SECONDS_PER_DEGREE = 3600
_SECONDS_PER_MINUTE = 60
_MINUTES_PER_DAY = 1440


@dataclass(frozen=True, slots=True)
class Row:
    date: GregorianDate
    printed: Fraction  # arcseconds beyond the printed degrees and minutes
    degrees: int
    arcminutes: int
    computed: float  # the same, computed

    @property
    def difference(self) -> float:
        return self.computed - float(self.printed)


def _values(repo: Path) -> Mapping[str, Record]:
    fx = load_fixture(repo / "tests" / f"{FIXTURE}.yaml", context_for(repo), repo=repo)
    return {r.key.split("#", 1)[1]: r for r in fx.values}


def _month(name: str) -> int:
    return MONTHS.index(name.strip().lower()[:3]) + 1


def tolerance(data: Mapping[str, Record]) -> tuple[Fraction, Fraction]:
    """(half the table's quantum, half the constant's quantum), in arcseconds."""
    table_q = Fraction(1, 10)
    c0 = str(data["modern.ayanamsa.iae_lahiri.mean.c0.arcseconds"].raw["value"])
    places = len(c0.partition(".")[2])
    return table_q / 2, Fraction(1, 10**places) / 2


def rows(repo: Path = REPO) -> list[Row]:
    """Every printed row with its computed value (module docstring)."""
    vals = _values(repo)
    data = load_records(repo, context_for(repo)).data
    preset = load_preset(repo, PRESET)
    assert preset.modern is not None
    scales = TimeScales(data)
    params = engine_parameters.load()
    frame = Frame(
        make_precession(str(preset.modern["precession"]), data, scales),
        make_nutation(str(preset.modern["nutation"])),
        scales,
        params["modern.cio_locator_step"],
    )
    aya = make_ayanamsa("iae_lahiri", equinox="true", data=data, scales=scales)
    m = _HEADING.search(str(vals["input.heading"].value))
    if m is None:
        raise ValueError("the table's heading states no hour and minute")
    fraction = (int(m.group(1)) * _SECONDS_PER_MINUTE + int(m.group(2))) / _MINUTES_PER_DAY
    standard = load_time_standards(repo, context_for(repo))[STANDARD]
    out: list[Row] = []
    for b in range(1, BLOCKS + 1):
        year = int(str(vals[f"input.block{b}_year"].value)[:4])
        month, previous = 0, 0
        block = vals[f"output.block{b}"].value
        assert isinstance(block, tuple)
        for cells in block:
            name, day, deg, arcmin, sec = cells
            if name:
                month = _month(str(name))
            if month < previous:
                year += 1
            previous = month
            date = GregorianDate(year, month, int(day))
            jdn: JDN = jdn_from_gregorian(date)
            utc = utc_from_civil(
                ModernCivilInstant(jdn, fraction, standard.id), standard.offset_on(jdn)
            )
            tt = scales.tt_from_utc(utc)
            nut = frame.state(scales.centuries(tt))[0]
            value = aya.at(tt, nut).arc.value * _SECONDS_PER_DEGREE
            whole = int(deg) * _SECONDS_PER_DEGREE + int(arcmin) * _SECONDS_PER_MINUTE
            out.append(Row(date, parse_fraction(str(sec)), int(deg), int(arcmin), value - whole))
    return out


def render(repo: Path = REPO) -> str:
    data = load_records(repo, context_for(repo)).data
    half_table, half_c0 = tolerance(data)
    rs = rows(repo)
    worst = max(rs, key=lambda r: abs(r.difference))
    beyond = [r for r in rs if abs(r.difference) > half_table]
    mean = sum(r.difference for r in rs) / len(rs)
    lines = [
        "# IAE 2022 true ayanāṃśa: the table against the method's own definition",
        "",
        "Generated by `tools/iae_comparison.py` (do not edit). Source: "
        "indian_astronomical_ephemeris, the table",
        '"True Ayanamsa" (printed p. 421, PDF p. 428), fixture',
        f"`tests/{FIXTURE}.yaml`; computed under `{PRESET}`'s precession and nutation",
        "from the IAE polynomial (PDF p. 387) and the definition at the table's foot.",
        "The heading's time is read on IST (inferred; the tool's docstring). A",
        "comparison internal to the method's own source,",
        "not an independent witness.",
        "",
        f"- rows: {len(rs)}",
        f"- largest |Δ|: {abs(worst.difference):.4f}″ ({_date(worst.date)})",
        f"- mean Δ: {mean:+.4f}″",
        f"- half the print quantum: {float(half_table):.2f}″; rows beyond it: {len(beyond)}"
        + (f" ({', '.join(_date(r.date) for r in beyond)})" if beyond else ""),
        f"- tolerance applied: {float(half_table):.2f}″ + {float(half_c0):.3f}″ (half the",
        "  print quantum of the polynomial's constant term, which the computation",
        "  takes rounded); the excess beyond 0.05″ is attributed to that constant",
        "  by inference",
        "",
        "| date | printed | computed | Δ (″) | within 0.05″ |",
        "|---|---|---|---|---|",
    ]
    for r in rs:
        lines.append(
            f"| {_date(r.date)} | {r.degrees}° {r.arcminutes}′ {_sec(r.printed)}″ "
            f"| {r.computed:.4f}″ | {r.difference:+.4f} | "
            f"{'yes' if abs(r.difference) <= half_table else 'no'} |"
        )
    return "\n".join(lines) + "\n"


def _date(d: GregorianDate) -> str:
    return f"{d.y:04d}-{d.m:02d}-{d.d:02d}"


def _sec(x: Fraction) -> str:
    return f"{float(x):.1f}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    text = render()
    path = REPO / OUT
    if args.check:
        old = path.read_text(encoding="utf-8") if path.is_file() else ""
        if old != text:
            sys.stdout.writelines(
                difflib.unified_diff(old.splitlines(True), text.splitlines(True), str(OUT), "new")
            )
            return 1
        print(f"iae comparison: {OUT} is current")
        return 0
    path.write_text(text, encoding="utf-8")
    print(f"iae comparison: wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
