from pathlib import Path

TESTS_DIR = Path(__file__).parent.resolve()

PROJECT_DIR = TESTS_DIR.parent


FIXTURES = Path(__file__).parent.resolve() / "fixtures"

GST_PIPELINES = FIXTURES / "gst_pipelines"
DS_PIPELINES = FIXTURES / "ds_pipelines"
PYTHIA_PIPELINES = FIXTURES / "pythia_pipelines"
