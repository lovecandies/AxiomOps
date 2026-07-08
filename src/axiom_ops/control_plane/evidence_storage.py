import hashlib
import json
import os
from pathlib import Path
from typing import Any

from axiom_ops.control_plane.models import StoredArtifact


class EvidenceIntegrityError(Exception):
    pass


class EvidenceStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    @staticmethod
    def canonical_bytes(content: dict[str, Any]) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def write(
        self,
        incident_id: str,
        evidence_id: str,
        content: dict[str, Any],
    ) -> StoredArtifact:
        data = self.canonical_bytes(content)
        digest = hashlib.sha256(data).hexdigest()
        directory = self.root / incident_id
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{evidence_id}.json"
        temporary = directory / f".{evidence_id}.{os.getpid()}.tmp"
        try:
            with temporary.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return StoredArtifact(
            relative_path=target.relative_to(self.root).as_posix(),
            content_sha256=digest,
            byte_size=len(data),
        )

    def read_verified(
        self,
        relative_path: str,
        expected_sha256: str,
    ) -> dict[str, Any]:
        path = (self.root / relative_path).resolve()
        if self.root not in path.parents:
            raise EvidenceIntegrityError("evidence path escaped storage root")
        try:
            data = path.read_bytes()
        except FileNotFoundError as exc:
            raise EvidenceIntegrityError("evidence artifact is missing") from exc
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected_sha256:
            raise EvidenceIntegrityError("evidence content hash mismatch")
        try:
            return json.loads(data)
        except json.JSONDecodeError as exc:
            raise EvidenceIntegrityError("evidence artifact is not valid JSON") from exc
