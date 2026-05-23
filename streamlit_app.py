"""Streamlit Community Cloud 진입점.

루트 경로에 entry point를 두어야 배포 시 인식됨.
실제 앱은 04_prototype/app.py.
"""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).parent / "04_prototype" / "app.py"), run_name="__main__")
