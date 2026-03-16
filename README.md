# PvOutputVisualization

Simple dashboard getting data from pvoutput and generating visualization which can be shown in AMWeb.

The background color matches the background of AMWeb, thereby integrates nicely into it:

![screenshot](docs/screenshot.png)

To run you simply need either an `.env` file (for local development)

```
PVOUTPUT_API_KEY=abcdef
PVOUTPUT_SYSTEM_ID=112047
```

or inject the keys as environment variables, see [docker-compose.yml](docker-compose.yml).