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
- [5. Distribution](#5-distribution)
  - [5.1. Building with PyInstaller](#51-building-with-pyinstaller)
  - [5.2. Creating the Installer with InstallForge](#52-creating-the-installer-with-installforge)
- [6. Contact Information](#6-contact-information)

---

## 1. Introduction and Prerequisites

### 1.1. Introduction

PolyConLab_SCADA is a desktop application that communicates with the PolyConLab PLC over WiFi (or Ethernet, depending on the firmware build) using the SCPI protocol (TCP on port 80). It allows operators to monitor sensor readings, control actuators, and track the system state through a graphical interface built with **PySide6** and designed visually using **Qt Designer**.

The application is distributed as a standalone Windows executable produced by **PyInstaller** and packaged into an installer using **InstallForge**.

The total size of the SCADA app once installed is around 700 MB, make sure to have enough space before installing it. The installer itself is around 180 MB.

### 1.2. Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.12.10** — Download from [python.org](https://www.python.org/downloads/release/python-31210/). During installation, check **"Add Python to PATH"**.
- **Git** — Download from [git-scm.com](https://git-scm.com/).
- **InstallForge** *(for distribution only)* — Download from [installforge.net](https://installforge.net/). Required only when building the final Windows installer.

> **Note:** Qt Designer is bundled with PySide6 and does **not** require a separate installation. It becomes available as `pyside6-designer` after installing the Python dependencies.

### 1.3. Network Configuration

By default the PLC hosts its own **WiFi access point** from inside the enclosure (no router or switch required) and runs a DHCP server, so the PC only has to join that network. The SCADA connects to the PLC's fixed address, which is also its default connection setting (editable from **Configuración**).

#### PLC network settings (WiFi, default)

| Parameter | Value |
|---|---|
| SSID | `PolyConLab` (overridable per deployment in the firmware build flags) |
| IP address | `192.168.4.1` |
| Subnet mask | `255.255.255.0` |
| Port | `80` (TCP) |

The WiFi password is set in the firmware (`WIFI_AP_PASSWORD` in `lib/Definitions/Config.hpp`, overridable through PlatformIO `build_flags`). The PC gets its address from the PLC by DHCP — leave the WiFi adapter on *Automatic (DHCP)*.

> **Ethernet builds:** if the firmware is built with `-DTRANSPORT_ETHERNET`, the PLC instead listens on `192.168.1.100` (`config::kEthernetIp`), port `80`. Give the PC's Ethernet adapter a static address in the same `/24` subnet (e.g. `192.168.1.10`, mask `255.255.255.0`, no gateway) and set the SCADA's IP to `192.168.1.100` in **Configuración**.

#### Verifying the Connection

Once the PC has joined the PLC's network, verify connectivity before launching the SCADA:

```powershell
ping 192.168.4.1
```

If the PLC is powered and the firmware is running, you should receive replies. If the ping times out, check that the PC is connected to the PLC's WiFi network (not another one) and that the PLC firmware is running.

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
│   └── ui/                   # Qt Designer source files (.ui). Edit these in Qt Designer.
├── installer/                # PyInstaller .spec file. The InstallForge .ifp project is created locally and not tracked in version control.
├── src/
│   ├── main.py               # Application entry point.
│   ├── comms/                # TCP client and SCPI protocol parsing.
│   ├── models/               # Domain models: Device and Sensor enums.
│   ├── network/              # Raw TCP transport.
│   ├── ui/
│   │   ├── main_window_ui.py # Generated glue — NEVER edit by hand. Regenerate with build_ui.py.
│   │   ├── scada_state.py    # SCADA-side state machine and control permission table.
│   │   ├── sensor_panel.py   # Coordinator between sensor cards, chart, and PLC client.
│   │   ├── style/            # Visual infrastructure (colours, animations). No logic.
│   │   │   ├── anim.py
│   │   │   └── palette.py
│   │   ├── widgets/          # Reusable custom Qt widgets (promoted in Qt Designer).
│   │   │   ├── actuator_row.py
│   │   │   ├── sensor_card.py
│   │   │   └── temperature_chart.py
│   │   └── windows/          # Top-level windows and dialogs.
│   │       ├── log_window.py
│   │       ├── main_window.py
│   │       └── settings_dialog.py
│   └── utils/                # Shared utility functions.
├── build_ui.py               # Helper script: converts assets/ui/*.ui → src/ui/*_ui.py.
├── requirements.txt
├── ruff.toml
└── README.md
```

**Notes:**
- All visual design work happens in `assets/ui/` using Qt Designer.
- `.ui` files are compiled to `*_ui.py` modules in `src/ui/` by running `build_ui.py`. They are never loaded at runtime directly.
- Python application logic lives in `src/`.
- For a full walkthrough of the widget development cycle (promoted widgets, signal wiring, Qt Designer shortcuts), see [src/ui/widgets/README.md](src/ui/widgets/README.md).

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

## 5. Distribution

The application is distributed as a standalone Windows executable. The process involves two tools:

1. **PyInstaller** — bundles the Python application and all its dependencies into a single `.exe`.
2. **InstallForge** — wraps the executable into a Windows installer (`.exe` setup wizard).

### 5.1. Building with PyInstaller

With the virtual environment active and from the repository root:

```powershell
pyinstaller installer/polyconlab_scada.spec
```

PyInstaller will produce the standalone executable at:

```text
dist/PolyConLab_SCADA/PolyConLab_SCADA.exe
```

> **Before your first build:** Run `python build_ui.py` to ensure all `.ui` files have been compiled to Python modules.

### 5.2. Creating the Installer with InstallForge

The InstallForge project file (`.ifp`) is **not tracked in version control** and must be created once per machine. After the first-time setup, you only need to open the saved project and click Build.

This generates a file that can then be re-run should the SCADA have any changes. This is mainly for creating an installer for the SCADA, for Windows.

> **Prerequisite:** Complete section 5.1 first. The `dist/PolyConLab_SCADA/` folder must exist before configuring InstallForge.

#### 5.2.1. First-time Setup

InstallForge's settings are organised in a sidebar on the left with five groups: **General**, **Setup**, **Dialogs**, **System**, and **Build**. Work through them top to bottom.

---

##### Step 1 — Create a new project

1. Launch InstallForge.
2. Go to **File → New** to create a blank project.

---

##### Step 2 — General → General

Fill in the application metadata:

| Field | Value |
|---|---|
| Application Name | `PolyConLab SCADA` |
| Application Version | e.g. `1.0.0` |
| Company Name | `FING-UdelaR` |
| Website | *(optional)* |

Under the "Languages" tab, check the box for the language which the installer should be available in. Check the "Spanish" box.

---

##### Step 3 — Setup → Files

This is the most important step — it tells InstallForge what to bundle.

1. Click **Add Folder** in the toolbar.

    1.1 Browse to `dist\PolyConLab_SCADA\` inside the repository root and select the folder inside it. It should be `_internal`.

2. Click **Add Folder** in the toolbar.

    2.1 Browse to `dist\PolyConLab_SCADA\` and select the executable named `PolyConLab_SCADA.exe`.

3. Leave the destination as the installation root (`<InstallPath>`).

After this step the file list should show the folder and executable file we just selected.

---

##### Step 4 — Setup → Uninstallation

Enable the uninstaller so the app appears in Windows **Apps & features**:

1. Check **Include Uninstaller**.

2. Leave the name as `Uninstaller`.

---

##### Step 5 — Dialogs → Finish

We should let the user be able to instantly run the SCADA after installation, for this reason, follow the next steps. These will allow the user to do so. Do the following:

1. Check **Run Application**.

2. Leave the name as `<InstallPath>\PolyConLab_SCADA.exe`.

3. No arguments needed.

---

##### Step 6 — System → Shortcuts

The installer creates a shortcut so users can launch the app from the Desktop:

1. Click **Add**.
2. Fill in the shortcut details:
   - **Shortcut Name:** `PolyConLab SCADA`
   - **Target:** `<InstallPath>\PolyConLab_SCADA.exe`
   - **Destination:** `Desktop`

***Note***: These steps can be copied to allow users to shortcut the SCADA from the Start Menu as well.

---

##### Step 7 — Build → Build

In the Build tab, inside Build, we set the final steps before creating the installer for our SCADA application. To do so, follow the next steps.

1. Next to **Setup File**, click `…` and browse to `installer\` inside the repository root.
2. Set the filename to `PolyConLab_SCADA_Setup.exe`.

The full path should read something like:
```
C:\...\PolyConLab_SCADA\installer\PolyConLab_SCADA_Setup.exe
```

The `PolyConLab_SCADA_Setup.exe` is the installer we will be distributing.

---

##### Step 8 — Save the Project

1. Go to **File → Save As**.
2. Save as `installer\polyconlab_scada.ifp` inside the repository root.

This path is in `.gitignore` and will not be committed to the repository.

---

##### Step 9 — Build

1. Click **Build** in the top toolbar (or go to **Build → Build**).
2. InstallForge will package all files and write the installer to `installer\PolyConLab_SCADA_Setup.exe`.

---

#### 5.2.2. Subsequent Builds

Once the `.ifp` project file exists on your machine, rebuilding is a two-step process:

1. Re-run PyInstaller to refresh `dist\PolyConLab_SCADA\` (see section 5.1).
2. Open InstallForge, load `installer\polyconlab_scada.ifp`, and click **Build**.

The finished installer will always be placed at `installer\PolyConLab_SCADA_Setup.exe` (excluded from version control).

---

## 6. Contact Information

For any questions or further information, please reach out to:

- **Giuliano Turpía**: [giuliano.turpia@fing.edu.uy](mailto:giuliano.turpia@fing.edu.uy)
- **Sofía Miranda**: [sofia.miranda@fing.edu.uy](mailto:sofia.miranda@fing.edu.uy)
- **Francisco Galietta**: [francisco.galietta@fing.edu.uy](mailto:francisco.galietta@fing.edu.uy)
