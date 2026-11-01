"""Run the built app with isolated settings, then exit its Qt event loop."""
import os
from pathlib import Path
import subprocess
import tempfile
import sys


if __name__ == '__main__':
    exe = Path(__file__).resolve().parents[1] / 'dist' / 'Portal' / 'Portal.exe'
    if len(sys.argv) > 1:
        exe = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, LOCALAPPDATA=tmp, QT_QPA_PLATFORM='offscreen')
        result = subprocess.run([str(exe), '--smoke-test'], env=env, timeout=30)
        if result.returncode:
            raise SystemExit(result.returncode)
        print('Portal.exe: startup and Qt event loop OK')
