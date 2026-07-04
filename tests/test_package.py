import subprocess
import sys
import venv
from pathlib import Path

def test_package_launchd_templates_included(tmp_path):
    # 1. Create a fresh temp venv
    venv_dir = tmp_path / "venv"
    venv.create(venv_dir, with_pip=True)
    
    # Determine python and pip binary paths
    if sys.platform == "win32":
        venv_python = venv_dir / "Scripts" / "python.exe"
        venv_pip = venv_dir / "Scripts" / "pip.exe"
    else:
        venv_python = venv_dir / "bin" / "python"
        venv_pip = venv_dir / "bin" / "pip"
        
    # Get Briefly project root
    project_root = Path(__file__).resolve().parent.parent
    
    # 2. Run pip install --no-deps .
    # This installs the briefly package in non-editable mode
    subprocess.run([str(venv_pip), "install", "--no-deps", str(project_root)], check=True)
    
    # 3. Check if templates can be resolved and read via importlib.resources inside the installed package
    test_code = """
import importlib.resources
import sys

try:
    daily_tpl = importlib.resources.files("briefly.templates.launchd").joinpath("com.briefly.dailyrun.plist")
    web_tpl = importlib.resources.files("briefly.templates.launchd").joinpath("com.briefly.web.plist")
    
    daily_text = daily_tpl.read_text(encoding="utf-8")
    web_text = web_tpl.read_text(encoding="utf-8")
    
    assert "com.briefly.dailyrun" in daily_text
    assert "com.briefly.web" in web_text
    print("SUCCESS")
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)
"""
    res = subprocess.run(
        [str(venv_python), "-c", test_code],
        capture_output=True,
        text=True
    )
    assert res.returncode == 0
    assert "SUCCESS" in res.stdout
