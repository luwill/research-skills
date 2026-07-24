"""mir_audit — static auditor for medical-imaging review manuscripts.

Split from a single 3963-line module into strictly-layered submodules:
constants -> model -> parsing/profile -> projectio -> checks_* -> report -> core -> cli.
The public API is unchanged; audit_manuscript.py remains the CLI entry point.
"""
from __future__ import annotations

from .constants import *  # noqa: F401,F403
from .model import *  # noqa: F401,F403
from .parsing import *  # noqa: F401,F403
from .profile import *  # noqa: F401,F403
from .projectio import *  # noqa: F401,F403
from .checks_text import *  # noqa: F401,F403
from .checks_config import *  # noqa: F401,F403
from .checks_human import *  # noqa: F401,F403
from .checks_artifacts import *  # noqa: F401,F403
from .checks_claims import *  # noqa: F401,F403
from .report import *  # noqa: F401,F403
from .core import *  # noqa: F401,F403
from .cli import *  # noqa: F401,F403
