# Contributing

Use fictional or explicitly redistributable documents only. Keep API keys, real-company exports, application storage, chat histories, and raw private reports outside the checkout.

Run `python3 -m unittest discover -s tests -v` before submitting changes. A provider/retrieval change also needs a live run against the unchanged question suite, with hardware/model versions and unresolved failures recorded. Do not modify expected answers merely to make a model's output pass.

Document material decisions in `docs/decisions/README.md`: requirement, alternatives, tradeoff, evidence, and reconsideration trigger. Prefer existing upstream features over a new UI or backend service.

Label agent assessments as agent assessments. Human acceptance requires an actual human review. A test without a model is a tooling test, not a live RAG result.
