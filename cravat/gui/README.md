# Commands

To start Celery, while in multiuser, in a separate process:

``` 
celery -A cravat.gui.celery worker
```

You can run `celery --help` for other options like restricting
queues