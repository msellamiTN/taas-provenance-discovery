#!/usr/bin/env bash
# One-command reproduction: install, test, rebuild processed data, run all experiments, draw figures.
# LLM outputs (analyst decompositions, silver labels, calibration answers) are replayed from
# data/llm_records/; set ANTHROPIC_API_KEY and use taas.llm.backends.AnthropicAnalyst to regenerate them.
set -euo pipefail
cd "$(dirname "$0")"
python3 -m pip install -q -r requirements.txt
python3 -m pytest -q
PYTHONPATH=src python3 -m taas.data.registries > /dev/null
python3 experiments/run_all.py 2>&1 | tee results/run_all.log
