# Contributing

Use fictional or explicitly redistributable documents only. Keep API keys, real-company exports, application storage, chat histories, and raw private reports outside the checkout.

Run `python3 -m unittest discover -s tests -v` before submitting changes. A provider/retrieval change also needs a live run against the unchanged question suite, with hardware/model versions and unresolved failures recorded. Do not modify expected answers merely to make a model's output pass.

For development, use a virtual environment and `python -m pip install --editable '.[dev]'`. Run `ruff check loredock tests`, `ruff format --check loredock tests`, and `mypy`. CI enforces these checks on Python 3.10 and 3.13. Development tools are optional; the CLI has no third-party runtime dependencies.

Annotate application functions and keep validated domain records in `loredock/models.py`. `KnowledgeAPI` is a small structural interface; `Client` adapts AnythingLLM's HTTP API to it. Keep transport concerns in that adapter and orchestration in focused functions. Dynamic JSON belongs at service/report boundaries. Add abstractions only when they clarify a real dependency or repeated behavior. Explain recovery invariants and tradeoffs in docstrings or comments instead of narrating obvious statements.

Document material decisions in `docs/decisions/README.md`: requirement, alternatives, tradeoff, evidence, and reconsideration trigger. Prefer existing upstream features over a new UI or backend service.

Label agent assessments as agent assessments. Human acceptance requires an actual human review. A test without a model is a tooling test, not a live RAG result.
