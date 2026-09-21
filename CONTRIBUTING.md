# Contributing

## Development setup

```bash
python -m pip install -e ".[dev,ml]"
PYTHONPATH=src python -m unittest discover -v
```

PowerShell:

```powershell
python -m pip install -e ".[dev,ml]"
$env:PYTHONPATH = "src"
python -m unittest discover -v
```

## Change requirements

- Keep the fallback control path deterministic and safe without network access or a model file.
- Add or update tests for behavior changes in control, navigation, alerting, or energy policy.
- Keep telemetry changes backward compatible. Add optional fields instead of renaming existing fields.
- Do not weaken the overheat lockout, watchdog, acknowledgement, or minimum duty constraints.
- Document any hardware-specific assumptions in `docs/hardware.md`.

## Pull requests

A useful pull request contains:

1. The problem and expected behavior.
2. The implementation boundary and affected interfaces.
3. Test evidence for normal, boundary, and failure behavior.
4. Safety implications for any change that can energize a heater or transmit SOS.

## Commit style

Use short imperative subjects, for example:

```text
control: clamp unconscious duty after overheat recovery
api: add device drift endpoint
firmware: isolate hardware comparator input
```

