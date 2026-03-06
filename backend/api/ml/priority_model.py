"""Very lightweight priority scoring logic.

This mirrors the procedural calculation used by ``Disaster.compute_priority``
but is kept in its own module so it can later be swapped for a trained
model if necessary (e.g. regression on historical dispatch and outcome
data).

The formula is intentionally simple for now:

    score = severity * population
    if response_time > 0:
        score /= response_time

Other factors (distance, available resources, etc.) can be added later.
"""

from __future__ import annotations

def calculate_priority(severity: float, population: float, response_time: float | None = None) -> float:
    """Return a priority score for a potential incident.

    ``severity`` should be a normalized value (e.g. 0–5).
    ``population`` is the number of people likely affected.
    ``response_time`` is the estimated arrival time in minutes of the
    closest responder; if supplied the score is divided by this value so
    that quickly reachable incidents are treated as more urgent.

    The result may be 0 if either severity or population is 0.
    """
    base = severity * population
    if response_time and response_time > 0:
        return base / response_time
    return base


# convenience wrapper that mirrors the model method above
class PriorityModel:
    """Encapsulate the priority calculation so a more complex ML-based
    implementation can be substituted later.

    Currently the ``predict`` method simply delegates to
    :func:`calculate_priority`.
    """

    def predict(self, severity: float, population: float, response_time: float | None = None) -> float:
        return calculate_priority(severity, population, response_time)
