# AI Trader scripts

## Python virtual environment

To create a new python visrtual enviroment, and install any library we need.

```bash
python3 -m venv .venv
```

Για να ενεργοποιήσουμε το visrtual enviroment

- Σε macOS / Linux:

```bash
source .venv/bin/activate
```

- Σε Windows:

```PowerShell
.venv\Scripts\activate
```

### Extract python requirements

```bash
pip freeze > requirements.txt
```

## News analysis

For news you will need an API Key from <a href="https://newsapi.org/" target="_blank">newsapi.org</a>

## Enviroment

copy `.env.sample` to `.env` and fill your `newsapi.org` API Key.