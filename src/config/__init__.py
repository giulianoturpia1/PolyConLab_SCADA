"""Central, editable configuration for the SCADA.

Every behaviour tunable lives in one of the modules below, grouped by concern, so a value
is changed in one place instead of being hunted down across the code base:

* :mod:`config.network` — PLC address, port and connection timeout.
* :mod:`config.polling` — how often the PLC is polled and how long replies are awaited.
* :mod:`config.data` — measurement log size, CSV export limits and the chart's window/range.

The look of the application has its own central home in :mod:`ui.style`:
:mod:`ui.style.palette` (colors), :mod:`ui.style.metrics` (sizes, fonts, spacing) and
:mod:`ui.style.anim` (animation durations).

Protocol strings, UI labels and state maps are definitions, not tunables, and stay next to
the code that owns them (:mod:`comms.protocol`, :mod:`ui.scada_state`, ...).
"""
