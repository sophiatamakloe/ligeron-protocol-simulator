# Ligeron Protocol Simulator

This repository models the **software-control logic** for a conceptual multi-phase exposure device. It turns sequencing and safety requirements into executable, inspectable code.

It does **not** establish medically safe exposure settings, biological efficacy, physical-device performance, regulatory compliance, or production capacity.

## What the simulator implements

- Authentication gate before activation
- Sequential RLT, UVB, and post-exposure delivery phases
- RLT/UVB and UVB/delivery mutual-exclusion interlocks
- UVB-off confirmation before delivery
- Configurable delivery-transition deadline
- Emergency shutdown from every active phase
- Adversarial invariant tests that directly force illegal actuator states and verify fail-safe shutdown
- Fault injection for authentication, shutdown, timeout, delivery, and emergency-stop scenarios
- Append-only, timestamped telemetry
- Seeded 10,000-session software simulation
- JSON summary, JSONL sample events, and self-contained HTML results dashboard

## Safety scope

The default durations are **software test inputs copied from a conceptual product brief**. They are not clinical recommendations. The simulator advances a virtual clock and never controls lights, pumps, nozzles, sensors, or other hardware.

No physical testing should use these values without qualified medical, photobiology, electrical, mechanical, regulatory, and hardware-safety review.

## Architecture

```text
Authentication
    -> RLT
    -> RLT confirmed off
    -> UVB
    -> UVB confirmed off
    -> Delivery
    -> Complete

Any fault -> Safe shutdown -> Aborted
```

Every event records the virtual timestamp, phase, event type, message, and actuator snapshot. The controller enforces that RLT and UVB are never active simultaneously and that delivery cannot operate while UVB is active.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Run the tests

```bash
pytest
pytest --cov=ligeron_protocol --cov-report=term-missing
```

## Run the seeded simulation

```bash
ligeron-sim --sessions 10000 --seed 20261005 --fault-probability 0.08
```

Artifacts are written to `artifacts/`:

- `simulation_summary.json`
- `sample_events.jsonl`
- `dashboard.html`

Open `artifacts/dashboard.html` in a browser to inspect the run.

## Interpreting performance numbers

The reported processing latency measures how long Python takes to execute this deterministic state-machine logic. It does not represent:

- Hardware switching latency
- Gemini or other model inference latency
- Database, vector-store, or network performance
- Human-perceived application response time
- Clinical or biological response
- Production concurrency capacity

The 10,000-session run validates rule execution across many seeded scenarios. It is not a claim that 10,000 physical devices or users were concurrently supported.

## Responsible résumé framing

A supportable description after reproducing the included run is:

> Directed development of and validated a Python state-machine simulator for a conceptual multi-phase exposure device, specifying safety requirements and reviewing test coverage for authentication, mutual-exclusion, sequencing, transition-deadline, and emergency-shutdown logic across 10,000 seeded synthetic sessions.

Do not convert the run into claims about physical hardware, medical safety, production users, or clinical outcomes.
