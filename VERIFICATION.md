# Verification Record

## Verified run

- Date: October 5, 2026
- Python: 3.12.14
- Seed: 20261005
- Synthetic sessions: 10,000
- Injected-fault probability: 8%

## Automated tests

- Tests passed: 25
- Tests failed: 0
- Overall coverage reported by coverage.py: 94%
- Line coverage: 94.1%
- Branch coverage: 78.4%

The suite covers normal completion, authentication failure, RLT shutdown failure, UVB shutdown failure, delivery-transition timeout, delivery-system failure, emergency stops in all three active phases, immutable telemetry, monotonic event sequencing, reproducible scenario generation, artifact creation, and the command-line workflow. Three adversarial tests bypass normal transitions and directly force illegal actuator/phase states: simultaneous RLT and UVB, simultaneous UVB and delivery, and entry into delivery before UVB-off confirmation. Each test verifies that the invariant guard records the expected safety violation, aborts the session, and returns every actuator to the safe-off state.

## Seeded simulation results

- Completed sessions: 9,221
- Sessions safely aborted after injected faults: 779
- Injected faults detected: 779 of 779
- Undetected injected faults: 0
- False aborts: 0
- Safety-invariant violations: 0
- Telemetry events generated: 88,324
- Python state-machine p50 processing time: 0.01944 ms
- Python state-machine p95 processing time: 0.044116 ms
- Python state-machine p99 processing time: 0.235051 ms

The latency measurements above describe only execution of deterministic Python state-machine logic on the test environment used for this run. They are not measurements of hardware switching, model inference, network traffic, databases, physical devices, biological response, or production concurrency.

## Claim boundary

This run supports the statement that the repository executed 10,000 seeded synthetic protocol sessions and that its modeled interlocks detected every injected fault in this defined scenario set.

It does not support claims that:

- 10,000 physical devices or production users were supported concurrently.
- Any physical exposure protocol is medically safe or clinically effective.
- A hardware system achieved the reported Python processing latency.
- The simulator validates biological, mitochondrial, dermatological, or neurological outcomes.
- The modeled fault distribution represents real-world device reliability.

## Reproduction

```bash
python -m pip install -e ".[dev]"
python -m pytest --cov=ligeron_protocol --cov-report=term-missing
python -m ligeron_protocol.cli \
  --sessions 10000 \
  --seed 20261005 \
  --fault-probability 0.08 \
  --output-dir artifacts
```

The test command writes coverage data when the XML option is included. The simulation writes a JSON summary, representative JSONL telemetry, and a self-contained HTML dashboard.
