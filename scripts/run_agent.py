"""Run the three structured LLM nodes against a sample transcript."""

import argparse
import json

from app.agent.nodes import AgentNodes, output_from_state
from app.agent.state import initial_state
from app.config import ROOT


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", choices=["1", "2", "3"], default="2")
    args = parser.parse_args()
    text = (ROOT / f"data/transcripts/session-{args.sample}.txt").read_text(
        encoding="utf-8"
    )
    previous = (
        (ROOT / "data/transcripts/session-1.txt").read_text(encoding="utf-8")
        if args.sample == "2"
        else None
    )
    state = initial_state(0, text, previous)
    nodes = AgentNodes()
    state.update(nodes.extract_topics(state))
    state.update(nodes.evaluate_progress(state))
    state.update(nodes.generate_quiz(state))
    state.update(nodes.validate_quiz(state))
    if not state["quiz_valid"]:
        raise SystemExit("Invalid quiz: " + "; ".join(state["validation_errors"]))
    print(json.dumps(output_from_state(state), indent=2))


if __name__ == "__main__":
    run()
