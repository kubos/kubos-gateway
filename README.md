# Development

## Plan

1. Fix timestamps in KubOS


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


Every time:

```bash
source virtualenv/bin/activate
python run.py
```

Deactivate virtualenv:
```bash
deactivate
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
