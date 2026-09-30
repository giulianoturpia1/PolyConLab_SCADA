"""
Runtime hook to set up PySide6 environment variables properly.
"""
import os
import sys
from pathlib import Path

# Get the path to the bundled libraries
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    base_path = Path(sys._MEIPASS)
    pyside6_path = base_path / 'PySide6'
    
    # Set Qt plugin path
    os.environ['QT_PLUGIN_PATH'] = str(pyside6_path / 'plugins')
    
    # Add paths to system PATH for DLL loading
    if 'PATH' in os.environ:
        os.environ['PATH'] = f"{base_path};{base_path / 'PySide6'};{os.environ['PATH']}"
    else:
        os.environ['PATH'] = f"{base_path};{base_path / 'PySide6'}"
    
    # Set Qt library path
    os.environ['QT_LIBRARY_PATH'] = str(pyside6_path)
