"""Web API for the live dashboard (``make ui``).

The API is a thin layer over the same code the CLI runs:

* live runs start ``python -m minerllm guided ...`` as a subprocess and stream its
  execution trace (the JSONL file the bridge already writes) as Server-Sent Events;
* replays stream a recorded trace from ``results/raw`` at a chosen speed, so the
  demo works with no network and no API keys;
* results come from the files ``make report`` writes.

Nothing here changes how mining, ranking or verification work.
"""
