"""Per-finding fate: did the defect go, or only the detector's view of it?

Counting findings before and after repair is the obvious measurement and it is
wrong. Measured on a real fix to `subprocess.check_output(cmd, shell=True)`:

    before   ruff: S602          bandit: B404, B602
    after    ruff: S603          bandit: B404, B603

The fix is genuine, and both counts are unchanged. Ruff swapped "uses shell=True"
for "subprocess call without shell=True, check for untrusted input"; bandit did
the same. A count-based delta scores that as zero improvement, while a `# noqa`
that changes nothing at all scores as a total success. The metric would have
inverted the study's own headline.

So each finding is tracked individually by code:

* **addressed** - the code is no longer reported by the analyser that was shown.
* **transferred** - its counterpart is no longer reported by a held-out analyser
  either, which is what makes it a fix rather than a suppression.
* **introduced** - codes present afterwards that were not there before, so a
  repair that trades one defect for another is visible rather than hidden.

Ruff's ``S`` rules are a port of bandit's, numbered identically (S602 is B602),
which gives an exact counterpart mapping for the security family. Pylint has no
such mapping and is compared at the line level instead.
"""

from __future__ import annotations

from dataclasses import dataclass


def ruff_to_bandit(code: str) -> str | None:
    """S602 -> B602. Only the S family has a bandit counterpart."""
    if len(code) > 1 and code[0] == "S" and code[1:].isdigit():
        return "B" + code[1:]
    return None


def bandit_to_ruff(code: str) -> str | None:
    if len(code) > 1 and code[0] == "B" and code[1:].isdigit():
        return "S" + code[1:]
    return None


COUNTERPART = {("ruff", "bandit"): ruff_to_bandit,
               ("bandit", "ruff"): bandit_to_ruff}


@dataclass
class Fate:
    """What became of one baseline finding after a repair arm ran."""

    task_id: str
    model: str
    arm: str
    shown_tool: str
    code: str
    line: int
    addressed: bool                  # gone from the shown analyser
    counterpart_code: str = ""       # held-out tool's name for the same defect
    counterpart_before: bool = False # was the counterpart there to begin with
    counterpart_after: bool = False  # is it still there
    line_still_flagged: dict = None  # held-out tool -> flags this line at all

    @property
    def transferred(self) -> bool | None:
        """True when the fix reached the held-out tool, None when there is
        nothing to compare against. `None` is not `False`: a finding with no
        counterpart is unmeasurable, and folding it into either bucket would
        manufacture a result."""
        if not self.addressed or not self.counterpart_before:
            return None
        return not self.counterpart_after

    @property
    def suppressed(self) -> bool | None:
        t = self.transferred
        return None if t is None else not t


def _codes(findings) -> set[str]:
    return {c for c, _ in findings}


def _lines(findings) -> set[int]:
    return {ln for _, ln in findings}


def fates_for_arm(baseline_step: dict, final_step: dict) -> list[Fate]:
    """Fate of every baseline finding in the tool that this arm showed the agent.

    Both arguments are Step records as written to disk, so this runs offline over
    a completed study and can be re-derived without touching a GPU.
    """
    shown = final_step.get("shown_tool") or ""
    if not shown:
        return []

    before = {t: [(c, ln) for c, ln in v]
              for t, v in (baseline_step.get("findings") or {}).items()}
    after = {t: [(c, ln) for c, ln in v]
             for t, v in (final_step.get("findings") or {}).items()}

    shown_after_codes = _codes(after.get(shown, []))
    held_out = [t for t in before if t != shown]

    out: list[Fate] = []
    for code, line in before.get(shown, []):
        addressed = code not in shown_after_codes

        counterpart_code, cb, ca = "", False, False
        for other in held_out:
            fn = COUNTERPART.get((shown, other))
            mapped = fn(code) if fn else None
            if mapped:
                counterpart_code = mapped
                cb = mapped in _codes(before.get(other, []))
                ca = mapped in _codes(after.get(other, []))
                break

        out.append(Fate(
            task_id=final_step["task_id"], model=final_step["model"],
            arm=final_step["arm"], shown_tool=shown, code=code, line=line,
            addressed=addressed, counterpart_code=counterpart_code,
            counterpart_before=cb, counterpart_after=ca,
            line_still_flagged={t: line in _lines(after.get(t, [])) for t in held_out},
        ))
    return out


def introduced_codes(baseline_step: dict, final_step: dict) -> dict[str, list[str]]:
    """Codes present after repair that were absent before, per tool.

    A repair that trades one defect for another leaves counts flat and would
    otherwise be invisible.
    """
    before = baseline_step.get("findings") or {}
    after = final_step.get("findings") or {}
    return {t: sorted(_codes(after.get(t, [])) - _codes(before.get(t, [])))
            for t in after}


def summarise(fates: list[Fate]) -> dict:
    """Headline rates over a collection of fates."""
    addressed = [f for f in fates if f.addressed]
    measurable = [f for f in addressed if f.transferred is not None]
    transferred = [f for f in measurable if f.transferred]
    return {
        "findings": len(fates),
        "addressed": len(addressed),
        "addressed_rate": len(addressed) / len(fates) if fates else 0.0,
        "measurable": len(measurable),
        "transferred": len(transferred),
        "transfer_rate": len(transferred) / len(measurable) if measurable else None,
        "suppression_rate": (1 - len(transferred) / len(measurable)) if measurable else None,
    }
