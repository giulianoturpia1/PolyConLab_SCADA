"""Network settings: where the PLC is and how long to wait for it."""

from __future__ import annotations

# Default PLC endpoint: the firmware's WiFi access-point address (config::kApIp) and SCPI
# server port (config::kWifiServerPort). Editable at runtime from Configuración.
DEFAULT_HOST = "192.168.4.1"
DEFAULT_PORT = 80

# Valid range for the port field in the connection settings dialog.
PORT_MIN = 1
PORT_MAX = 65_535

# How long (ms) a TCP connection attempt may take before it is abandoned.
CONNECT_TIMEOUT_MS = 5_000
