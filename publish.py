"""
Script to publish Python package.
Run via "poetry run publish"
@Piotr Styczyński 2021
"""
from pathlib import Path

from poetry_publish.publish import poetry_publish

import mtkcpu


def publish():
    poetry_publish(
        package_root=Path(mtkcpu.__file__).parent.parent,
        version=mtkcpu.__version__,
    )
