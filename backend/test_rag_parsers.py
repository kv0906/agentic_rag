import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from llama_index.core import Document
from rag import (
    _load_markdown_documents,
    _parse_documents,
)


class MarkdownParserTests(unittest.TestCase):
    def test_splits_markdown_by_heading_and_keeps_section_paths(self) -> None:
        markdown = """# Guide
Intro.

## Install
Run pnpm install.

## Usage
Start the app.
"""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "guide.md"
            path.write_text(markdown, encoding="utf-8")

            documents = _load_markdown_documents(path, "guide.md")
            nodes = _parse_documents(documents, "guide.md")

        self.assertEqual(
            [node.metadata["section"] for node in nodes],
            ["Guide", "Guide / Install", "Guide / Usage"],
        )
        self.assertIn("## Install", nodes[1].get_content())
        self.assertEqual(nodes[1].metadata["filename"], "guide.md")

    def test_sentence_splits_an_oversized_markdown_section(self) -> None:
        markdown = "# Large section\n\n" + "A complete sentence. " * 800
        with TemporaryDirectory() as directory:
            path = Path(directory) / "large.markdown"
            path.write_text(markdown, encoding="utf-8")

            documents = _load_markdown_documents(path, "large.markdown")
            nodes = _parse_documents(documents, "large.markdown")

        self.assertGreater(len(nodes), 1)
        self.assertTrue(
            all(node.metadata["section"] == "Large section" for node in nodes)
        )

    def test_rejects_empty_markdown(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "empty.md"
            path.write_text(" \n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "No text"):
                _load_markdown_documents(path, "empty.md")


class PdfParserRegressionTests(unittest.TestCase):
    def test_sentence_splits_pdf_pages_and_keeps_page_metadata(self) -> None:
        documents = [
            Document(
                text="First page sentence.",
                metadata={"filename": "guide.pdf", "page": 1, "page_label": "1"},
            ),
            Document(
                text="Second page sentence.",
                metadata={"filename": "guide.pdf", "page": 2, "page_label": "2"},
            ),
        ]

        nodes = _parse_documents(documents, "guide.pdf")

        self.assertEqual([node.metadata["page"] for node in nodes], [1, 2])
        self.assertEqual(
            [node.get_content() for node in nodes],
            ["First page sentence.", "Second page sentence."],
        )


if __name__ == "__main__":
    unittest.main()
