"""sikw00fcot: SiKW00F drone MAVLink telemetry to Cursor-on-Target gateway."""

__version__ = "1.0.0"

from .commands import cli, main  # noqa: F401
from .functions import (  # noqa: F401
    detection_to_cot,
    detection_to_cot_xml,
    mav_to_cot,
    mav_to_cot_xml,
    status_to_cot,
    status_to_cot_xml,
)
from .scan_commands import cli as scan_cli  # noqa: F401
from .sentinel_commands import cli as sentinel_cli  # noqa: F401
