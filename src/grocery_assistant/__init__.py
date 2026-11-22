"""grocery-assistant: posts supermarket bonus offers to Mattermost on a schedule."""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("grocery-assistant")
except PackageNotFoundError:  # running from a source tree without installing
    __version__ = "dev"
