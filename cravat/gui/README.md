# Commands
## Running the GUI
To start the GUI in Flask, run:

```
python -m pip install -e .
oc gui
```

If for some reason you want to run the GUI in aiohttp:

```
oc gui --aiohttp
```

at some point in the future aiohttp support will break and not come back.

## Job Workers

If the GUI is running outside multi-user mode then it will spawn celery 
workers automatically (see `cravat_web.py`).

To start Celery, while in multiuser, in a separate process:

``` 
celery -A cravat.gui.celery worker
```

You can run `celery --help` for other options like restricting
queues.  Here `cravat.gui.celery` is the dotted Python path to our configured 
celery `App` instance.

On macOS, billiard (4.3+) starts pool processes with `spawn` rather than
`fork`, which requires setting `FORKED_BY_MULTIPROCESSING` like this:

```
FORKED_BY_MULTIPROCESSING=1 celery -A cravat.gui.celery worker
```

Workers started through `python -m cravat.gui.workers` or by the GUI set this
automatically.