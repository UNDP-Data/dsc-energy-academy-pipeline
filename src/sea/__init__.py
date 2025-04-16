"""
This package contains an ETL pipeline to process Figma designs and transform
them into a standardised JSON format for the Sustainable Energy Academy.
It uses data entities (models) that define the basic objects to work with
[Figma API](https://www.figma.com/developers/api).
"""

from .frames import *
from .nodes import *

__version__ = "0.1.0a0"
