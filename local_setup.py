"""
Quick start for running the TripNegotiator locally.

This script helps you:
  1. Set up a virtual environment
  2. Install dependencies
  3. Run local tests (no AWS needed)
  4. See the multi-agent negotiation in action
"""

import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd, description):
    """Run a shell command and report results."""
    print(f"\n{'='*70}")
    print(f"▶ {description}")
    print(f"{'='*70}")
    print(f"$ {cmd}\n")
    
    result = subprocess.run(cmd, shell=True, cwd=project_root)
    
    if result.returncode != 0:
        print(f"\n❌ Command failed: {description}")
        return False
    
    print(f"✅ {description} complete")
    return True


project_root = Path(__file__).parent


def main():
    print("""
    ╔════════════════════════════════════════════════════════════════════╗
    ║           TripNegotiator - Local Testing Setup                     ║
    ╚════════════════════════════════════════════════════════════════════╝
    """)
    
    # Detect OS and Python
    is_windows = sys.platform == "win32"
    python_cmd = sys.executable
    
    print(f"OS: {'Windows' if is_windows else 'Unix/Mac'}")
    print(f"Python: {python_cmd}")
    print(f"Project: {project_root}\n")
    
    # Step 1: Create virtual environment
    venv_path = project_root / "venv"
    if not venv_path.exists():
        if not run_command(f"{python_cmd} -m venv venv", "Create virtual environment"):
            return False
    else:
        print(f"\n✅ Virtual environment already exists at {venv_path}")
    
    # Step 2: Activate venv and install dependencies
    if is_windows:
        activate_cmd = str(venv_path / "Scripts" / "activate.bat") + " && "
        pip_cmd = str(venv_path / "Scripts" / "pip.exe")
    else:
        activate_cmd = f"source {venv_path}/bin/activate && "
        pip_cmd = f"{venv_path}/bin/pip"
    
    if not run_command(f"{pip_cmd} install --upgrade pip", "Upgrade pip"):
        return False
    
    if not run_command(f"{pip_cmd} install -r requirements.txt", "Install dependencies"):
        return False
    
    # Step 3: Run tests
    if is_windows:
        pytest_cmd = str(venv_path / "Scripts" / "pytest.exe")
    else:
        pytest_cmd = f"{venv_path}/bin/pytest"
    
    print(f"\n{'='*70}")
    print(f"Ready to run tests!")
    print(f"{'='*70}\n")
    
    print("Option 1: Run with pytest (structured output)")
    print(f"  {pytest_cmd} tests/test_negotiation.py -v -s\n")
    
    print("Option 2: Run as demo (colored output)")
    if is_windows:
        python_exe = str(venv_path / "Scripts" / "python.exe")
    else:
        python_exe = f"{venv_path}/bin/python"
    print(f"  {python_exe} tests/test_negotiation.py\n")
    
    print("Option 3: Run linter")
    if is_windows:
        flake8_cmd = str(venv_path / "Scripts" / "flake8.exe")
    else:
        flake8_cmd = f"{venv_path}/bin/flake8"
    print(f"  {flake8_cmd} agents/ shared/ tests/ --max-line-length=100\n")


if __name__ == "__main__":
    main()
