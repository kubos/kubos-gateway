# Development

## Plan

1. Understand asyncio
1. Get telemetry data from UDP.
1. Format telemetry for Major Tom.
1. Send telemetry to Major Tom.
1. Get commands flowing from Major Tom.
1. Send command to sat.
1. Get command status.
1. Send pretty format command to Major Tom.
1. Send validate commands.



First time:

1. Setup a virtualenv
```bash
virtualenv virtualenv -p `which python3`
source virtualenv/bin/activate
```
1. Install dependencies
```bash
pip install git+git://github.com/aaugustin/websockets.git
```
1. Copy `config.json` to `config.local.json` and edit it.


Deactivate virtualenv:
```bash
deactivate
```

Every time:
```bash
source virtualenv/bin/activate
```

## Building and distributing

### Locally

See also [this page](http://www.puzzlr.org/install-packages-pip-conda-environment/) and [this page](https://python-packaging.readthedocs.io/en/latest/minimal.html#creating-the-scaffolding).

```bash
cd kubos_adapter
pip install -e .
```

### On PyPI

Read this: https://python-packaging.readthedocs.io/en/latest/minimal.html#publishing-on-pypi
