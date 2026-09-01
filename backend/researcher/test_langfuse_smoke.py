"""Send a smoke-test trace so we can audit Langfuse instrumentation."""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)

from observability import observe  # noqa: E402


def main() -> None:
    with observe(
        name="plan-portfolio",
        user_id="smoke-test-user",
        session_id="smoke-test-session",
        tags=["planner", "portfolio-analysis", "smoke-test"],
        metadata={"agent": "planner", "source": "smoke-test"},
        input={"job_id": "smoke-test-job"},
    ) as obs:
        obs.update(output={"status": "completed", "job_id": "smoke-test-job"})
        print("Smoke trace flushed. Check Langfuse for name=plan-portfolio")


if __name__ == "__main__":
    main()
