from pathlib import Path
from setuptools import setup, find_packages

PROJECT_ROOT = Path(__file__).parent.resolve()
SCRIPTS_DIR = PROJECT_ROOT / "bin"

script_files = []
if SCRIPTS_DIR.exists():
    for path in sorted(SCRIPTS_DIR.iterdir()):
        if path.is_file() and path.suffix not in {".csv", ".json"}:
            script_files.append(str(path.relative_to(PROJECT_ROOT)))

setup(
    name="daylily-ephemeral-cluster",
    version="0.7.350",
    packages=find_packages(),
    include_package_data=True,
    scripts=script_files,
    install_requires=[],
)
