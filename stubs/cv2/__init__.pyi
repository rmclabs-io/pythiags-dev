from typing import List
from typing import Tuple
from typing import Any
import numpy as np
RETR_TREE: int
CHAIN_APPROX_SIMPLE: int

Contours = np.ndarray

def findContours(
    image:np.ndarray,
    mode:int,
    method:int
) -> Tuple[Contours, Any]: ...
