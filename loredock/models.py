"""Typed application records and the boundary to the upstream service.

AnythingLLM payloads remain dynamic at the HTTP boundary. Validated manifests and
ingestion state use explicit records so orchestration does not depend on HTTP.
"""

from pathlib import Path
from typing import Any, Protocol, TypedDict

PathLike = str | Path
JSONObject = dict[str, Any]


class KnowledgeAPI(Protocol):
    """Operations needed by ingestion and evaluation; implemented by Client."""

    def get(self, path: str) -> JSONObject: ...

    def post(self, path: str, body: JSONObject) -> JSONObject: ...

    def workspace(self, slug: str) -> JSONObject: ...


class Document(TypedDict):
    id: str
    title: str
    file: str
    workspace: str
    owner: str
    date: str
    authority: str
    source_url: str
    text: str
    sha256: str


class Manifest(TypedDict):
    id: str
    classification: str
    workspaces: dict[str, str]
    documents: list[Document]
    manifest_path: str


class IndexedDocument(TypedDict):
    sha256: str
    locations: list[str]
    workspace: str


class IngestionState(TypedDict):
    workspaces: dict[str, str]
    documents: dict[str, IndexedDocument]
    pending: dict[str, IndexedDocument]
    classification: str
    manifest_path: str


class Question(TypedDict):
    id: str
    kind: str
    workspace: str
    question: str
    rubric: str
    expected_sources: list[str]
