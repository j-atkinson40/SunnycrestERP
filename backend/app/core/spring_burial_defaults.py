"""Spring burial season defaults by state.

Used during tenant onboarding to auto-populate season start/end dates
when the admin indicates the facility handles spring burials.
"""

SPRING_BURIAL_SEASON_DEFAULTS: dict[str, dict[str, str]] = {
    "MN": {"start": "10-15", "end": "05-01"},
    "WI": {"start": "11-01", "end": "04-15"},
    "MI": {"start": "11-01", "end": "04-15"},
    "ND": {"start": "10-15", "end": "05-01"},
    "SD": {"start": "10-15", "end": "05-01"},
    "IA": {"start": "11-01", "end": "04-01"},
    "IL": {"start": "11-15", "end": "04-01"},
    "IN": {"start": "11-15", "end": "04-01"},
    "OH": {"start": "11-15", "end": "04-01"},
    "PA": {"start": "11-15", "end": "04-01"},
    "NY": {"start": "11-01", "end": "04-15"},
    "VT": {"start": "11-01", "end": "05-01"},
    "NH": {"start": "11-01", "end": "05-01"},
    "ME": {"start": "10-15", "end": "05-01"},
    "MA": {"start": "11-15", "end": "04-01"},
    "CT": {"start": "11-15", "end": "04-01"},
    "NJ": {"start": "11-15", "end": "04-01"},
    "DEFAULT": {"start": "11-01", "end": "05-01"},
}


def get_season_defaults(state_code: str | None) -> dict[str, str]:
    """Return the spring burial season start/end for a given state code."""
    if state_code and state_code.upper() in SPRING_BURIAL_SEASON_DEFAULTS:
        return SPRING_BURIAL_SEASON_DEFAULTS[state_code.upper()]
    return SPRING_BURIAL_SEASON_DEFAULTS["DEFAULT"]
