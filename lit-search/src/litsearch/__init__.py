"""litsearch package metadata."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("litsearch")
except PackageNotFoundError:  # source tree before installation
    __version__ = "0+unknown"

ARTIFACT_SCHEMA_VERSION = 2

__all__ = ["ARTIFACT_SCHEMA_VERSION", "__version__"]
