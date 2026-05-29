# PolyConLab_SCADA

Repository that holds all the SCADA-related utilities for the PolyConLab system, used to monitor and control the ESP32-based PLC from a PC. Part of a Final Degree Project for the Facultad de Ingeniería, UDELAR. For more information about the firmware running on the PLC, please refer to the [PolyConLab_FW](../PolyConLab_FW/README.md) repository.

## Table of Contents

- [1. Introduction and Prerequisites](#1-introduction-and-prerequisites)
  - [1.1. Introduction](#11-introduction)
  - [1.2. Prerequisites](#12-prerequisites)
  - [1.3. Network Configuration](#13-network-configuration)
- [2. Setting Up the Project](#2-setting-up-the-project)
- [3. Running the Application](#3-running-the-application)
- [4. UI Development with Qt Designer](#4-ui-development-with-qt-designer)
  - [4.1. Project Structure](#41-project-structure)
  - [4.2. Opening Qt Designer](#42-opening-qt-designer)
  - [4.3. Generating Python Code from .ui Files](#43-generating-python-code-from-ui-files)
- [5. Adding Functionality to Widgets](#5-adding-functionality-to-widgets)
  - [5.1. The Four-Layer Architecture](#51-the-four-layer-architecture)
  - [5.2. Adding a Standard Widget](#52-adding-a-standard-widget)
  - [5.3. Adding a Custom (Promoted) Widget](#53-adding-a-custom-promoted-widget)
  - [5.4. Connecting Signals to Python Functions](#54-connecting-signals-to-python-functions)
  - [5.5. Static Connections in Qt Designer](#55-static-connections-in-qt-designer)
- [6. Code Quality](#6-code-quality)
  - [6.1. Installation](#61-installation)
  - [6.2. Usage](#62-usage)
- [7. Distribution](#7-distribution)
  - [7.1. Building with PyInstaller](#71-building-with-pyinstaller)
  - [7.2. Creating the Installer with InstallForge](#72-creating-the-installer-with-installforge)
- [8. Known Issues](#8-known-issues)
  - [8.1. PySide6 and PyInstaller](#81-pyside6-and-pyinstaller)
  - [8.2. Qt Designer Not Starting](#82-qt-designer-not-starting)
- [9. Contact Information](#9-contact-information)

---

## 1. Introduction and Prerequisites

### 1.1. Introduction

PolyConLab_SCADA is a desktop application that communicates with the PolyConLab PLC over Ethernet using the SCPI protocol (TCP on port 80). It allows operators to monitor sensor readings, control actuators, and track the system state through a graphical interface built with **PySide6** and designed visually using **Qt Designer**.

The application is distributed as a standalone Windows executable produced by **PyInstaller** and packaged into an installer using **InstallForge**.

The total size of the SCADA app once installed is around 700 MB, make sure to have enough space before installing it. The installer itself is around 180 MB.

### 1.2. Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.12.10** — Download from [python.org](https://www.python.org/downloads/release/python-31210/). During installation, check **"Add Python to PATH"**.
- **Git** — Download from [git-scm.com](https://git-scm.com/).
- **InstallForge** *(for distribution only)* — Download from [installforge.net](https://installforge.net/). Required only when building the final Windows installer.

> **Note:** Qt Designer is bundled with PySide6 and does **not** require a separate installation. It becomes available as `pyside6-designer` after installing the Python dependencies.

### 1.3. Network Configuration

The SCADA communicates with the PLC over a **direct Ethernet connection** (no router or switch required). The PLC has a fixed static IP address; the PC running the SCADA must be on the same subnet for the TCP connection to succeed.

#### PLC network settings

| Parameter | Value |
|---|---|
| IP address | `192.168.1.1` |
| Subnet mask | `255.255.255.0` |
| Port | `80` (TCP) |

#### PC Ethernet adapter settings

Assign the PC's Ethernet adapter a **static** IP address that is in the same `/24` subnet as the PLC. Any address in the range `192.168.1.2` – `192.168.1.254` (other than `192.168.1.1`, which is the PLC) is valid. Example:

| Parameter | Value |
|---|---|
| IP address | `192.168.1.100` |
| Subnet mask | `255.255.255.0` |
| Default gateway | *(leave blank)* |
| DNS | *(leave blank)* |

#### How to configure the adapter on Windows

1. Open **Settings → Network & Internet → Ethernet → (your adapter) → Edit** (under "IP assignment").
2. Switch the assignment from *Automatic (DHCP)* to **Manual**.
3. Enable **IPv4** and fill in the values from the table above.
4. Click **Save**.

Alternatively, using PowerShell as **Administrator** (replace `"Ethernet"` with your adapter's actual name if different):

```powershell
netsh interface ip set address "Ethernet" static 192.168.1.100 255.255.255.0
```

> **Note:** This configuration only applies to the adapter connected to the PLC. Any other adapters (Wi-Fi, secondary Ethernet) are unaffected and can remain on DHCP.

#### Verifying the Connection

Once the adapter is configured, verify connectivity before launching the SCADA:

```powershell
ping 192.168.1.1
```

If the PLC is powered and the Ethernet link is up, you should receive replies. If the ping times out, double-check the cable, the adapter settings, and that the PLC firmware is running.

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
├── installer/            # PyInstaller .spec file. The InstallForge .ifp project is created locally and not tracked in version control.
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

**Notes:**
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

## 5. Adding Functionality to Widgets

This section explains the full cycle: from dropping a widget in Qt Designer to having it call Python code at runtime.

### 5.1. The Four-Layer Architecture

Every piece of UI passes through four layers. Understanding this prevents confusion about which file to edit.

```
assets/ui/main_window.ui        ← visual layout (Qt Designer source)
        │
        │  python build_ui.py
        ▼
src/ui/main_window_ui.py        ← generated glue — NEVER edit by hand
src/ui/widgets.py               ← custom widget classes (SensorCard, ActuatorRow, …)
src/ui/main_window.py           ← application logic, signal wiring, public API
```

| Layer | What you change | When |
|---|---|---|
| `.ui` | Position, size, widget type, object name | Adding or resizing widgets |
| `widgets.py` | Visual behaviour of custom widgets | Adding a new custom widget class |
| `main_window.py` | What happens when the user interacts | Adding signals, slots, animations |
| `main_window_ui.py` | **Nothing** — regenerate with `build_ui.py` | After every `.ui` save |

---

### 5.2. Adding a Standard Widget

A **standard widget** is any built-in Qt class (`QPushButton`, `QLabel`, `QSlider`, etc.) that does not need custom Python code for its visual representation.

**Step 1 — Place it in Qt Designer**

1. Open Qt Designer:
   ```powershell
   pyside6-designer assets\ui\main_window.ui
   ```
2. Drag the desired widget from the Widget Box onto the canvas.
3. In the **Property Editor** (bottom-right), set `objectName` to a descriptive snake_case name, e.g. `btn_emergency_stop`.
4. Set any static properties (text, minimum size, enabled, etc.) in the Property Editor.
5. Save (`Ctrl+S`).

**Step 2 — Regenerate the Python class**

```powershell
python build_ui.py
```

After this step, `setupUi()` in `main_window_ui.py` will create `self.btn_emergency_stop` automatically.

**Step 3 — Reference it in `main_window.py`**

Access the widget via `self._ui.<objectName>`:

```python
# In _configure_widgets():
self._ui.btn_emergency_stop.setText("Paro de Emergencia")

# In _connect_signals():
self._ui.btn_emergency_stop.clicked.connect(self._on_emergency_stop)

# New slot method:
def _on_emergency_stop(self) -> None:
    """Handle the emergency stop button press."""
    self.log("Paro de emergencia activado.")
    # ... send command to PLC
```

---

### 5.3. Adding a Custom (Promoted) Widget

A **promoted widget** is a standard Qt widget whose class is replaced at runtime by one of your own Python classes (e.g. `_SensorCard`, `_ActuatorRow`). Use this when the widget needs custom painting or behaviour that Qt Designer cannot provide.

**Step 1 — Write the class in `widgets.py`**

Your class must:
- Extend a standard Qt class (`QFrame`, `QWidget`, etc.)
- Accept `parent` as its **first** argument with a default of `None` — `setupUi` passes only the parent

```python
# src/ui/widgets.py

class MyGauge(QFrame):
    """Circular gauge widget for displaying a percentage value."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # build internal layout here …

    def configure(self, label: str) -> None:
        """Override the default label set in __init__."""
        ...

    def set_value(self, percent: float) -> None:
        """Update the displayed percentage."""
        ...
```

**Step 2 — Promote the widget in Qt Designer**

1. Drag a **base widget** (e.g. `QFrame`) onto the canvas.
2. Right-click it → **Promote to…**
3. Fill in the form:

   | Field | Value |
   |---|---|
   | Base class name | `QFrame` (must match what your class extends) |
   | Promoted class name | `MyGauge` |
   | Header file | `ui.widgets` |

4. Click **Add**, then **Promote**.
5. Set `objectName` (e.g. `gauge_pressure`) and any size constraints.
6. Save and run `python build_ui.py`.

**Step 3 — Call `configure()` in `main_window.py`**

`setupUi` constructs the widget with only the parent argument. Set its runtime properties in `_configure_widgets()`:

```python
def _configure_widgets(self) -> None:
    ...
    self._ui.gauge_pressure.configure("Presión")
```

---

### 5.4. Connecting Signals to Python Functions

All signal wiring belongs in `_connect_signals()` in `main_window.py`. Every interactive widget exposes one or more **signals**; connect each to a method (slot) on `MainWindow`.

**Common signal patterns**

```python
def _connect_signals(self) -> None:
    # Button clicked
    self._ui.btn_my_action.clicked.connect(self._on_my_action)

    # Slider or spinbox value changed
    self._ui.my_slider.valueChanged.connect(self._on_slider_changed)

    # Check box toggled
    self._ui.chk_enable.toggled.connect(self._on_enable_toggled)

    # Custom widget signal (defined with Signal() in widgets.py)
    self._ui.my_gauge.value_changed.connect(self._on_gauge_value)
```

**Slot naming convention**

| Trigger | Slot name |
|---|---|
| User presses a button | `_on_<objectName>` |
| TCP / hardware event | `_on_tcp_<event>` |
| Menu action | `_toggle_<thing>` or `_open_<dialog>` |

**Full example — adding a "Reset counters" button**

```python
# _connect_signals():
self._ui.btn_reset.clicked.connect(self._on_btn_reset)

# New slot:
def _on_btn_reset(self) -> None:
    """Send the reset command to the PLC and log the action."""
    self._tcp.send(b"RESET\r\n")
    self.log("Contadores reiniciados.")
```

---

### 5.5. Static Connections in Qt Designer

For simple widget-to-widget connections that need no Python logic (e.g. a slider synced to a spin box), wire them directly in Qt Designer instead of in Python:

1. Press **F4** (or select Edit → Edit Signals/Slots mode).
2. Drag from the **sender** widget to the **receiver** widget.
3. Choose the signal and slot in the dialog (e.g. `valueChanged(int)` → `setValue(int)`).
4. Save and run `python build_ui.py`.

The connection is emitted inside the generated `setupUi()` and requires no code in `main_window.py`.

> **Note:** The existing `heater_slider ↔ heater_spinbox` bidirectional sync is wired this way.

---

## 6. Code Quality

This project uses [Ruff](https://docs.astral.sh/ruff/) for both linting and formatting. Configuration is defined in `ruff.toml`.

### 6.1. Installation

Ruff is included in `requirements.txt` and is installed as part of the standard setup step. No additional installation is needed.

### 6.2. Usage

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

## 7. Distribution

The application is distributed as a standalone Windows executable. The process involves two tools:

1. **PyInstaller** — bundles the Python application and all its dependencies into a single `.exe`.
2. **InstallForge** — wraps the executable into a Windows installer (`.exe` setup wizard).

### 7.1. Building with PyInstaller

With the virtual environment active and from the repository root:

```powershell
pyinstaller installer/polyconlab_scada.spec
```

PyInstaller will produce the standalone executable at:

```text
dist/PolyConLab_SCADA/PolyConLab_SCADA.exe
```

> **Before your first build:** Run `python build_ui.py` to ensure all `.ui` files have been compiled to Python modules.

### 7.2. Creating the Installer with InstallForge

The InstallForge project file (`.ifp`) is **not tracked in version control** and must be created once per machine. After the first-time setup, you only need to open the saved project and click Build.

This generates a file that can then be re-run should the SCADA have any changes. This is mainly for creating an installer for the SCADA,for Windows.

> **Prerequisite:** Complete section 7.1 first. The `dist/PolyConLab_SCADA/` folder must exist before configuring InstallForge.

#### 7.2.1. First-time Setup

InstallForge's settings are organised in a sidebar on the left with five groups: **General**, **Setup**, **Dialogs**, **System**, and **Build**. Work through them top to bottom.

---

##### Step 1 — Create a new project**

1. Launch InstallForge.
2. Go to **File → New** to create a blank project.

---

##### Step 2 — General → General**

Fill in the application metadata:

| Field | Value |
|---|---|
| Application Name | `PolyConLab SCADA` |
| Application Version | e.g. `1.0.0` |
| Company Name | `FING-UdelaR` |
| Website | *(optional)* |

Under the "Languages" tab, check the box for the language which the installer should be available in. Check the "Spanish" box.

---

##### Step 3 — Setup → Files**

This is the most important step — it tells InstallForge what to bundle.

1. Click **Add Folder** in the toolbar.

    1.1 Browse to `dist\PolyConLab_SCADA\` inside the repository root and select the folder inside it. It should be `_internal`.

2. Click **Add Folder** in the toolbar.

    2.1 Browse to `dist\PolyConLab_SCADA\` and select the executable named `PolyConLab_SCADA.exe`.

3. Leave the destination as the installation root (`<InstallPath>`).

After this step the file list should show the folder and executable file we just selected.

---

##### Step 4 — Setup → Uninstallation**

Enable the uninstaller so the app appears in Windows **Apps & features**:

1. Check **Include Uninstaller**.

2. Leave the name as `Uninstaller`.

---

##### Step 5 — Dialogs → Finish**

We should let the user be able to instantly run the SCADA after installation, for this reason, follow the next steps. These will allow the user to do so. Do the following:

1. Check **Run Application**.

2. Leave the name as `<InstallPath>\PolyConLab_SCADA.exe`.

3. No arguments needed.

---

##### Step 6 — System → Shortcuts**

The installer creates a shortcut so users can launch the app from the Desktop:

1. Click **Add**.
2. Fill in the shortcut details:
   - **Shortcut Name:** `PolyConLab SCADA`
   - **Target:** `<InstallPath>\PolyConLab_SCADA.exe`
   - **Destination:** `Desktop`

***Note***: These steps can be copied to allow users to shortcut the SCADA from the Start Menu as well.

---

##### Step 7 — Build → Build**

In the Build tab, inside Build, we set the final steps before creating the installer four our SCADA application. To do so, follow the next steps.

1. Next to **Setup File**, click `…` and browse to `installer\` inside the repository root.
2. Set the filename to `PolyConLab_SCADA_Setup.exe`.

The full path should read something like:
```
C:\...\PolyConLab_SCADA\installer\PolyConLab_SCADA_Setup.exe
```

The `PolyConLab_SCADA_Setup.exe` is the installer we will be distributing.

---

##### Step 8 — Save the Project**

1. Go to **File → Save As**.
2. Save as `installer\polyconlab_scada.ifp` inside the repository root.

This path is in `.gitignore` and will not be committed to the repository.

---

##### Step 9 — Build**

1. Click **Build** in the top toolbar (or go to **Build → Build**).
2. InstallForge will package all files and write the installer to `installer\PolyConLab_SCADA_Setup.exe`.

---

#### 7.2.2. Subsequent Builds

Once the `.ifp` project file exists on your machine, rebuilding is a two-step process:

1. Re-run PyInstaller to refresh `dist\PolyConLab_SCADA\` (see section 7.1).
2. Open InstallForge, load `installer\polyconlab_scada.ifp`, and click **Build**.

The finished installer will always be placed at `installer\PolyConLab_SCADA_Setup.exe` (excluded from version control).

---

## 8. Known Issues

### 8.1. PySide6 and PyInstaller

PyInstaller may miss some PySide6 plugins or QML modules, resulting in a packaged app that crashes on startup. If this happens, add the following flag to the `Analysis` block in `installer/polyconlab_scada.spec`:

```python
from PyInstaller.utils.hooks import collect_all
datas, binaries, hiddenimports = collect_all('PySide6')
```

Then re-run `pyinstaller installer/polyconlab_scada.spec`.

### 8.2. Qt Designer Not Starting

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

## 9. Contact Information

For any questions or further information, please reach out to:

- **Giuliano Turpía**: [giuliano.turpia@fing.edu.uy](mailto:giuliano.turpia@fing.edu.uy)
- **Sofía Miranda**: [sofia.miranda@fing.edu.uy](mailto:sofia.miranda@fing.edu.uy)
- **Francisco Galietta**: [francisco.galietta@fing.edu.uy](mailto:francisco.galietta@fing.edu.uy)
