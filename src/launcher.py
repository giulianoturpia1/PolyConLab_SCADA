"""
PyInstaller entry point that configures Qt environment before launching the app.
This ensures Qt plugins are found regardless of how the app is launched.
"""
import sys
import os
from pathlib import Path

def setup_qt_environment():
    """Set up Qt environment variables for the frozen application."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_path = Path(sys._MEIPASS)
        pyside6_path = base_path / 'PySide6'
        
        # Set Qt plugin path - this is critical for finding Qt plugins
        os.environ['QT_PLUGIN_PATH'] = str(pyside6_path / 'plugins')
        
        # Set Qt library path
        os.environ['QT_LIBRARY_PATH'] = str(pyside6_path)
        
        # Add paths to system PATH
        existing_path = os.environ.get('PATH', '')
        new_path = f"{base_path}{os.pathsep}{pyside6_path}{os.pathsep}{existing_path}"
        os.environ['PATH'] = new_path

if __name__ == '__main__':
    # Set up environment before importing anything else
    setup_qt_environment()
    
    # Now import and run the main application
    from main import main
    main()
