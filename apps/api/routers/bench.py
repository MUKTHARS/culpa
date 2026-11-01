import json
from pathlib import Path

from fastapi import APIRouter

from core.config import get_settings
from core.errors import NotFound

router = APIRouter(prefix="/bench", tags=["bench"])


@router.get("/results")
def results():
    path = Path(get_settings().bench_dir) / "results.json"
    if not path.exists():
        raise NotFound("no benchmark results yet; run `python bench/run.py`")
    return json.loads(path.read_text(encoding="utf-8"))
