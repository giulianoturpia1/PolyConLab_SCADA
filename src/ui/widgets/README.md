# UI Widgets

## Widget Inventory

Quick reference for every named widget in `main_window.ui`. The **Edit** column tells you where to make changes.

### Custom (promoted) widgets

These have a Python class in `src/ui/widgets/`. Layout changes go in Qt Designer; behaviour changes go in the Python file.

| Object name | Class | Python file | Purpose |
|---|---|---|---|
| `card_tin` | `SensorCard` | `sensor_card.py` | T. Entrada reading tile |
| `card_tout` | `SensorCard` | `sensor_card.py` | T. Salida reading tile |
| `card_tcam` | `SensorCard` | `sensor_card.py` | T. Camisa reading tile |
| `card_tmez` | `SensorCard` | `sensor_card.py` | T. Mezcla reading tile |
| `card_flow` | `SensorCard` | `sensor_card.py` | Caudal reading tile |
| `card_lvl` | `SensorCard` | `sensor_card.py` | Nivel reading tile |
| `row_heater` | `ActuatorRow` | `actuator_row.py` | Calentador ON/OFF row |
| `row_pump` | `ActuatorRow` | `actuator_row.py` | Bomba ON/OFF row |
| `row_mixer` | `ActuatorRow` | `actuator_row.py` | Mezclador ON/OFF row |
| `row_valve1` | `ActuatorRow` | `actuator_row.py` | Válvula 1 Abrir/Cerrar row |

### Chart view

`chart_view` is a plain `QChartView` placed in Qt Designer. Its size and position are set there; all chart behaviour (series, axes, rolling window) is controlled by `temperature_chart.py`.

### Standard Qt widgets

Layout and static text in Qt Designer (`assets/ui/main_window.ui`). Runtime behaviour wired in `src/ui/windows/main_window.py`.

| Object name | Qt class | Purpose |
|---|---|---|
| `action_connection` | `QAction` | Configuración → Conexión… (opens SettingsDialog) |
| `action_log` | `QAction` | Avanzado → Logs (opens LogWindow) |
| `lbl_conn` | `QLabel` | Connection status indicator (● Conectado / Desconectado) |
| `lbl_logo` | `QLabel` | Logo image in header |
| `lbl_setpoint` | `QLabel` | "Temperatura:" label for heater setpoint row |
| `lbl_state` | `QLabel` | PLC FSM state badge |
| `lbl_title` | `QLabel` | App title in header |
| `btn_ack` | `QPushButton` | Acknowledge fault and proceed to MANUAL |
| `btn_connect` | `QPushButton` | Connect / Disconnect / Cancel toggle |
| `btn_estop` | `QPushButton` | Graceful shutdown (EVT:SHUTDOWN + disconnect) |
| `btn_pause` | `QPushButton` | Send EVT:PAUSE |
| `btn_resume` | `QPushButton` | Send EVT:UNPAUSE |
| `btn_retry` | `QPushButton` | Retry full sensor checkup |
| `heater_slider` | `QSlider` | Heater setpoint (synced to spinbox via Qt Designer) |
| `heater_spinbox` | `QSpinBox` | Heater setpoint (synced to slider via Qt Designer) |

> `heater_slider` ↔ `heater_spinbox` are kept in sync by a static signal connection wired directly in Qt Designer — no Python code needed for the sync itself.

---

## Adding Functionality to Widgets

This section explains the full cycle: from dropping a widget in Qt Designer to having it call Python code at runtime.

## The Four-Layer Architecture

Every piece of UI passes through four layers. Understanding this prevents confusion about which file to edit.

```
assets/ui/main_window.ui            ← visual layout (Qt Designer source)
        │
        │  python build_ui.py
        ▼
src/ui/main_window_ui.py            ← generated glue — NEVER edit by hand
src/ui/widgets/                     ← custom widget classes (SensorCard, ActuatorRow, …)
src/ui/windows/main_window.py       ← application logic, signal wiring, public API
```

| Layer | What you change | When |
|---|---|---|
| `.ui` | Position, size, widget type, object name | Adding or resizing widgets |
| `src/ui/widgets/` | Visual behaviour of custom widgets | Adding a new custom widget class |
| `src/ui/windows/main_window.py` | What happens when the user interacts | Adding signals, slots, animations |
| `main_window_ui.py` | **Nothing** — regenerate with `build_ui.py` | After every `.ui` save |

---

## Adding a Standard Widget

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
    self.log("Paro de emergencia activado.")
    # ... send command to PLC
```

---

## Adding a Custom (Promoted) Widget

A **promoted widget** is a standard Qt widget whose class is replaced at runtime by one of your own Python classes (e.g. `SensorCard`, `ActuatorRow`). Use this when the widget needs custom painting or behaviour that Qt Designer cannot provide.

**Step 1 — Write the class in `src/ui/widgets/`**

Create a new file (e.g. `src/ui/widgets/my_gauge.py`). Your class must:
- Extend a standard Qt class (`QFrame`, `QWidget`, etc.)
- Accept `parent` as its **first** argument with a default of `None` — `setupUi` passes only the parent

```python
# src/ui/widgets/my_gauge.py

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

Then re-export it from `src/ui/widgets/__init__.py` so Qt Designer's generated import resolves:

```python
# src/ui/widgets/__init__.py
from ui.widgets.my_gauge import MyGauge
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

> The **Header file** field maps to the Python import path. `ui.widgets` resolves to this package's `__init__.py`, which is why every new widget class must be exported there.

**Step 3 — Call `configure()` in `main_window.py`**

`setupUi` constructs the widget with only the parent argument. Set its runtime properties in `_configure_widgets()`:

```python
def _configure_widgets(self) -> None:
    ...
    self._ui.gauge_pressure.configure("Presión")
```

---

## Connecting Signals to Python Functions

All signal wiring belongs in `_connect_signals()` in `src/ui/windows/main_window.py`. Every interactive widget exposes one or more **signals**; connect each to a method (slot) on `MainWindow`.

**Common signal patterns**

```python
def _connect_signals(self) -> None:
    # Button clicked
    self._ui.btn_my_action.clicked.connect(self._on_my_action)

    # Slider or spinbox value changed
    self._ui.my_slider.valueChanged.connect(self._on_slider_changed)

    # Check box toggled
    self._ui.chk_enable.toggled.connect(self._on_enable_toggled)

    # Custom widget signal (defined with Signal() in the widget class)
    self._ui.my_gauge.value_changed.connect(self._on_gauge_value)
```

**Slot naming convention**

| Trigger | Slot name |
|---|---|
| User presses a button | `_on_<objectName>` |
| TCP / hardware event | `_on_tcp_<event>` |
| Menu action | `_toggle_<thing>` or `_open_<dialog>` |


---

## Static Connections in Qt Designer

For simple widget-to-widget connections that need no Python logic (e.g. a slider synced to a spin box), wire them directly in Qt Designer instead of in Python:

1. Press **F4** (or select Edit → Edit Signals/Slots mode).
2. Drag from the **sender** widget to the **receiver** widget.
3. Choose the signal and slot in the dialog (e.g. `valueChanged(int)` → `setValue(int)`).
4. Save and run `python build_ui.py`.

The connection is emitted inside the generated `setupUi()` and requires no code in `main_window.py`.

> **Note:** The existing `heater_slider ↔ heater_spinbox` bidirectional sync is wired this way.
