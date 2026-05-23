# PolyConLab_SCADA

Repository that holds all the SCADA-related utilities for the PolyConLab system, used to monitor and control the ESP32-based PLC from a PC. Part of a Final Degree Project for the Facultad de Ingeniería, UDELAR. For more information about the firmware running on the PLC, please refer to the [PolyConLab_FW](../PolyConLab_FW/README.md) repository.

## Table of Contents

- [1. Introduction and Prerequisites](#1-introduction-and-prerequisites)
- [2. Setting Up the Project](#2-setting-up-the-project)
- [3. Running the Application](#3-running-the-application)
- [4. UI Development with Qt Designer](#4-ui-development-with-qt-designer)
  - [4.1. Project Structure](#41-project-structure)
  - [4.2. Opening Qt Designer](#42-opening-qt-designer)
  - [4.3. Generating Python Code from .ui Files](#43-generating-python-code-from-ui-files)
- [5. Code Quality](#5-code-quality)
  - [5.1. Installation](#51-installation)
  - [5.2. Usage](#52-usage)
- [6. Distribution](#6-distribution)
  - [6.1. Building with PyInstaller](#61-building-with-pyinstaller)
  - [6.2. Creating the Installer with InstallForge](#62-creating-the-installer-with-installforge)
- [7. Known Issues](#7-known-issues)
  - [7.1. PySide6 and PyInstaller](#71-pyside6-and-pyinstaller)
  - [7.2. Qt Designer Not Starting](#72-qt-designer-not-starting)
- [8. Contact Information](#8-contact-information)

---

## 1. Introduction and Prerequisites

### 1.1. Introduction

PolyConLab_SCADA is a desktop application that communicates with the PolyConLab PLC over Ethernet using the SCPI protocol (TCP on port 80). It allows operators to monitor sensor readings, control actuators, and track the system state through a graphical interface built with **PySide6** and designed visually using **Qt Designer**.

The application is distributed as a standalone Windows executable produced by **PyInstaller** and packaged into an installer using **InstallForge**.

### 1.2. Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.12.10** — Download from [python.org](https://www.python.org/downloads/release/python-31210/). During installation, check **"Add Python to PATH"**.
- **Git** — Download from [git-scm.com](https://git-scm.com/).
- **InstallForge** *(for distribution only)* — Download from [installforge.net](https://installforge.net/). Required only when building the final Windows installer.

> **Note:** Qt Designer is bundled with PySide6 and does **not** require a separate installation. It becomes available as `pyside6-designer` after installing the Python dependencies.

---

## 2. Setting Up the Project

1. Open a terminal (PowerShell or Command Prompt).

2. Clone the repository:

   ```powershell
   git clone <repository-url>
   cd PolyConLab_SCADA
   ```

3. Create a virtual environment:

   ```powershell
   python -m venv .venv
   ```

4. Activate the virtual environment:

   ```powershell
   .venv\Scripts\activate
   ```

   You should see `(.venv)` at the start of your prompt. **All subsequent commands in this guide assume the virtual environment is active.**

5. Install all dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

---

## 3. Running the Application

With the virtual environment active and from the repository root:

```powershell
python src/main.py
```

> **Important:** Always run from the **repository root**, not from inside `src/`.

---

## 4. UI Development with Qt Designer

### 4.1. Project Structure

The repository is organized as follows:

```text
PolyConLab_SCADA/
├── assets/
│   └── ui/               # Qt Designer source files (.ui). Edit these in Qt Designer.
├── installer/            # PyInstaller .spec file and InstallForge .ifp project.
├── src/
│   ├── main.py           # Application entry point.
│   ├── comms/            # TCP client and SCPI protocol parsing.
│   ├── ui/               # PySide6 window/widget classes. Generated *_ui.py files also land here.
│   ├── models/           # Data models (sensor readings, device state, etc.).
│   └── utils/            # Shared utility functions.
├── build_ui.py           # Helper script: converts assets/ui/*.ui → src/ui/*_ui.py.
├── requirements.txt
├── ruff.toml
└── README.md
```

**Workflow summary:**
- All visual design work happens in `assets/ui/` using Qt Designer.
- `.ui` files are compiled to `*_ui.py` modules in `src/ui/` by running `build_ui.py`. They are never loaded at runtime directly.
- Python application logic lives in `src/`.

### 4.2. Opening Qt Designer

With the virtual environment active:

```powershell
pyside6-designer
```

This opens the Qt Designer application. To create or edit a UI file, open or create a `.ui` file inside `assets/ui/`. After saving, run `build_ui.py` to compile the changes.

### 4.3. Generating Python Code from .ui Files

Run the helper script from the repository root:

```powershell
python build_ui.py
```

This scans `assets/ui/` for all `.ui` files and converts each one to a corresponding `*_ui.py` module inside `src/ui/`. For example, `assets/ui/main_window.ui` becomes `src/ui/main_window_ui.py`.

You can then use the generated module in your window class:

```python
from PySide6.QtWidgets import QMainWindow
from ui.main_window_ui import Ui_MainWindow


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
```

> **Note:** Generated `*_ui.py` files are excluded from version control (see `.gitignore`). Always run `python build_ui.py` after pulling changes that modify any `.ui` file.

---

## 5. Code Quality

This project uses [Ruff](https://docs.astral.sh/ruff/) for both linting and formatting. Configuration is defined in `ruff.toml`.

### 5.1. Installation

Ruff is included in `requirements.txt` and is installed as part of the standard setup step. No additional installation is needed.

### 5.2. Usage

Run the linter to check for issues:

```powershell
ruff check src/
```

Run the formatter to auto-format all source files:

```powershell
ruff format src/
```

Fix auto-fixable lint issues:

```powershell
ruff check --fix src/
```

It is recommended to run these commands before committing changes to keep the codebase consistent.

---

## 6. Distribution

The application is distributed as a standalone Windows executable. The process involves two tools:

1. **PyInstaller** — bundles the Python application and all its dependencies into a single `.exe`.
2. **InstallForge** — wraps the executable into a Windows installer (`.exe` setup wizard).

### 6.1. Building with PyInstaller

With the virtual environment active and from the repository root:

```powershell
pyinstaller installer/polyconlab_scada.spec
```

PyInstaller will produce the standalone executable at:

```text
dist/PolyConLab_SCADA/PolyConLab_SCADA.exe
```

> **Before your first build:** Run `python build_ui.py` to ensure all `.ui` files have been compiled to Python modules.

### 6.2. Creating the Installer with InstallForge

1. Open **InstallForge**.
2. Load the project file: `installer/polyconlab_scada.ifp`.
3. Under **Files**, verify that the source path points to `dist/PolyConLab_SCADA/`.
4. Click **Build** to generate the installer executable.

The finished installer will be placed in `installer/Output/` (excluded from version control).

> **First-time setup:** If the `.ifp` file does not yet exist, open InstallForge, configure a new project pointing to `dist/PolyConLab_SCADA/`, and save it as `installer/polyconlab_scada.ifp` so it can be committed to the repository.

---

## 7. Known Issues

### 7.1. PySide6 and PyInstaller

PyInstaller may miss some PySide6 plugins or QML modules, resulting in a packaged app that crashes on startup. If this happens, add the following flag to the `Analysis` block in `installer/polyconlab_scada.spec`:

```python
from PyInstaller.utils.hooks import collect_all
datas, binaries, hiddenimports = collect_all('PySide6')
```

Then re-run `pyinstaller installer/polyconlab_scada.spec`.

### 7.2. Qt Designer Not Starting

If `pyside6-designer` fails to launch or is not found, ensure the virtual environment is active and that `PySide6` was installed correctly:

```powershell
pip show PySide6
pyside6-designer --version
```

If the command still fails, try invoking it as a Python module:

```powershell
python -m PySide6.scripts.designer
```

---

## 8. Contact Information

For any questions or further information, please reach out to:

- **Giuliano Turpía**: [giuliano.turpia@fing.edu.uy](mailto:giuliano.turpia@fing.edu.uy)
- **Sofía Miranda**: [sofia.miranda@fing.edu.uy](mailto:sofia.miranda@fing.edu.uy)
- **Francisco Galietta**: [francisco.galietta@fing.edu.uy](mailto:francisco.galietta@fing.edu.uy)
