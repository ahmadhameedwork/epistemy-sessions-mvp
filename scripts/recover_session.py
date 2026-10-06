"""Resume a processing session from its last durable checkpoint. Stop the web server first."""

import argparse

from app.db import SessionLocal, init_db
from app.models import Session
from app.services.pipeline import Pipeline


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_id", type=int)
    args = parser.parse_args()
    init_db()
    with SessionLocal() as db:
        lesson = db.get(Session, args.session_id)
        if lesson is None or lesson.status != "processing":
            raise SystemExit(
                "Choose an existing processing session. Draft reviews resume through Share."
            )
    pipeline = Pipeline()
    try:
        snapshot = pipeline.graph.get_state(pipeline.config(args.session_id))
        if not snapshot.values:
            raise SystemExit("No checkpoint exists. Upload this session again.")
        if snapshot.values.get("error") and not snapshot.next:
            raise SystemExit(
                "Quiz repair was exhausted. Upload this session again; this checkpoint cannot continue."
            )
        pipeline.run(args.session_id, recover=True)
    finally:
        pipeline.close()
    with SessionLocal() as db:
        lesson = db.get(Session, args.session_id)
        if lesson.processing_error:
            raise SystemExit(lesson.processing_error)
        print(f"Session {lesson.id}: {lesson.status}")


if __name__ == "__main__":
    run()
