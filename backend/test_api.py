import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient
from llama_index.core import Settings
from llama_index.core.embeddings import MockEmbedding

import main
import rag


class UploadTests(unittest.TestCase):
    def test_duplicate_filename_is_rejected_instead_of_indexing_conflicting_versions(
        self,
    ):
        with (
            TemporaryDirectory() as directory,
            patch.dict(
                os.environ, {"OPENAI_API_KEY": "test-only", "RAG_CONTEXTUAL": "0"}
            ),
            patch.object(main, "DATA_DIR", Path(directory)),
            patch.object(rag, "_index", None),
            patch.object(rag, "_documents_meta", []),
            patch.object(rag, "configure_models"),
        ):
            Settings.embed_model = MockEmbedding(embed_dim=8)
            client = TestClient(main.app)
            original = client.post(
                "/api/upload",
                files={"file": ("plans.md", b"# Plans\nQuota: 7 requests.")},
            )
            self.assertEqual(original.status_code, 200)
            replacement = client.post(
                "/api/upload",
                files={"file": ("plans.md", b"# Plans\nQuota: 19 requests.")},
            )
            self.assertEqual(replacement.status_code, 409)
            self.assertEqual(
                client.get("/api/documents").json()["documents"],
                original.json()["documents"],
            )
