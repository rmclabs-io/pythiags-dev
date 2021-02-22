"""Type definitions."""

from typing import Dict
from typing import Tuple

from pythiags import Consumer
from pythiags import Producer

MetadataExtractionMap = Dict[str, Tuple[Producer, Consumer]]
