from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Tuple

CtxRetType = Tuple[Argv, Dict[str, Any]]

Argv = List[str]
MakeParseFnRet = Callable[[Argv], Tuple[CtxRetType, Tuple]]

def _MakeParseFn(fn: Callable, metadata: dict) -> MakeParseFnRet: ...
