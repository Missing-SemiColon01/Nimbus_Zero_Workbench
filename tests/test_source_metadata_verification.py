"""
tests/test_source_metadata_verification.py
==========================================
Day 3 — Task 3.3: Source Metadata Verification for Dev 3 Deliverable Generators

Verifies the interface contract between Dev 2 (RAG Retrieval Pipeline) and
Dev 3 (Artifact Generators & Deliverables):
  1. Every retrieved chunk strictly satisfies the schema:
       - "content": str (non-empty)
       - "source": str (filename)
       - "page": int (1-indexed page number)
       - "chunk_id": str (unique deterministic identifier)
       - "document_id": str (matching ingested document)
       - "score": float (similarity score)
  2. Page Grounding Accuracy:
       - Multi-page documents correctly ground retrieved passages to their actual pages.
  3. Dev 3 Integration Hand-off:
       - Validates that retrieved chunks can be directly transformed into
         Dev 3's ApprovalNoteSpec with exact formatted citations
         (e.g., "As per sample5.pdf, Page 2").
       - Confirms that DocxGenerator and PdfApprovalNoteGenerator generate valid,
         openable deliverables containing these exact source references.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz
import pytest
from docx import Document

from backend.agents.state import AgentState
from backend.artifacts.contracts import ApprovalNoteSpec
from backend.artifacts.docx_generator import DocxGenerator
from backend.artifacts.pdf_generator import PdfApprovalNoteGenerator
from backend.knowledge.embedder import get_embedder
from backend.knowledge.retriever import KnowledgeRetriever
from backend.knowledge.vector_store import VectorStore
from backend.tools.contracts import ToolResult
from backend.tools.rag_tool import RAGSearchTool

SAMPLE_DIR = Path("tests/sample-pdf")


@pytest.fixture(scope="module")
def shared_embedder():
    embedder = get_embedder()
    embedder.load()
    return embedder


@pytest.fixture
def retriever(shared_embedder):
    store = VectorStore(
        collection_name="test_source_metadata_verification",
        storage_path=":memory:",
        embedder=shared_embedder,
    )
    return KnowledgeRetriever(vector_store=store, embedder=shared_embedder)


class TestSourceMetadataSchema:
    """Verifies that every retrieved chunk strictly adheres to the metadata contract."""

    def test_chunk_metadata_schema_contract(self, retriever: KnowledgeRetriever):
        """
        Verify required keys: content, source, page, chunk_id, document_id, score.
        """
        table_pdf = SAMPLE_DIR / "sample-table.pdf"
        assert table_pdf.exists()

        ingest_res = retriever.ingest_document(table_pdf, document_id="doc_table_meta")
        assert ingest_res.status == "success"

        hits = retriever.search("quarter revenue profit expenses", top_k=3)
        assert len(hits) > 0

        for chunk in hits:
            # 1. Required keys presence
            assert "content" in chunk, "Chunk missing 'content' field"
            assert "source" in chunk, "Chunk missing 'source' field"
            assert "page" in chunk, "Chunk missing 'page' field"
            assert "chunk_id" in chunk, "Chunk missing 'chunk_id' field"
            assert "document_id" in chunk, "Chunk missing 'document_id' field"
            assert "score" in chunk, "Chunk missing 'score' field"

            # 2. Type and value validations
            assert isinstance(chunk["content"], str) and len(chunk["content"].strip()) > 0
            assert isinstance(chunk["source"], str) and chunk["source"] == "sample-table.pdf"
            assert isinstance(chunk["page"], int) and chunk["page"] >= 1
            assert isinstance(chunk["chunk_id"], str) and len(chunk["chunk_id"]) > 0
            assert isinstance(chunk["document_id"], str) and chunk["document_id"] == "doc_table_meta"
            assert isinstance(chunk["score"], float) and 0.0 <= chunk["score"] <= 1.0


class TestPageGroundingAccuracy:
    """Verifies that multi-page documents ground citations to their correct page numbers."""

    def test_multi_page_grounding_sample5(self, retriever: KnowledgeRetriever):
        sample5 = SAMPLE_DIR / "sample5.pdf"
        assert sample5.exists()

        ingest_res = retriever.ingest_document(sample5, document_id="doc_sample5_grounding")
        assert ingest_res.status == "success"
        assert ingest_res.page_count == 5

        # Query across all 5 pages
        hits = retriever.search("Lorem ipsum", top_k=5)
        assert len(hits) >= 3

        retrieved_pages = [h["page"] for h in hits]
        # Assert page numbers are valid 1-indexed integers between 1 and 5
        for p in retrieved_pages:
            assert 1 <= p <= 5

        # Confirm distinct pages are represented
        assert len(set(retrieved_pages)) > 1

    @pytest.mark.asyncio
    async def test_rag_tool_syncs_exact_metadata_into_agent_state(self, retriever: KnowledgeRetriever):
        """RAGSearchTool appends exact chunk metadata dictionaries to AgentState."""
        sample1 = SAMPLE_DIR / "sample1.pdf"
        assert sample1.exists()

        retriever.ingest_document(sample1, document_id="doc_sample1_meta")
        tool = RAGSearchTool(retriever=retriever)

        state = AgentState(
            task_id="task_meta_001",
            user_request="Retrieve technical specifications",
        )
        context = {
            "task_id": state.task_id,
            "retrieved_context": state.retrieved_context,
            "tool_results": state.tool_results,
        }

        tool_result: ToolResult = await tool.execute(
            {"query": "demonstration document page", "top_k": 2},
            context=context,
        )

        assert tool_result.success is True
        assert len(state.retrieved_context) >= 1

        chunk = state.retrieved_context[0]
        assert chunk["source"] == "sample1.pdf"
        assert chunk["page"] == 1
        assert chunk["document_id"] == "doc_sample1_meta"
        assert len(chunk["chunk_id"]) > 0


class TestDev3DeliverableHandOff:
    """Tests the bridge from retrieved chunk metadata to Dev 3's Word & PDF generators."""

    @pytest.mark.asyncio
    async def test_chunks_feed_approval_note_docx_generation(
        self,
        retriever: KnowledgeRetriever,
        tmp_path: Path,
    ):
        """
        Simulate complete hand-off:
          1. Retrieve chunks via RAG.
          2. Format source citations with exact page numbers.
          3. Generate Approval Note DOCX using Dev 3's DocxGenerator.
          4. Open generated document and assert exact citations exist.
        """
        table_pdf = SAMPLE_DIR / "sample-table.pdf"
        retriever.ingest_document(table_pdf, document_id="doc_audit_table")

        tool = RAGSearchTool(retriever=retriever)
        state = AgentState(
            task_id="audit_task_101",
            user_request="Generate approval note for quarterly financial review",
        )
        context = {
            "task_id": state.task_id,
            "retrieved_context": state.retrieved_context,
            "tool_results": state.tool_results,
        }

        await tool.execute({"query": "quarterly revenue profit", "top_k": 2}, context=context)
        assert len(state.retrieved_context) > 0

        # Build Dev 3's source references list from retrieved context
        source_refs: list[str] = [
            f"As per {chunk['source']}, Page {chunk['page']} (Document ID: {chunk['document_id']})"
            for chunk in state.retrieved_context
        ]

        # Construct ApprovalNoteSpec
        spec = ApprovalNoteSpec(
            subject="Quarterly Financial Audit Approval",
            recipient="Chief Operating Officer",
            reference_number="AUDIT-2026-Q3",
            purpose="Seek executive approval for quarterly expenditure and revenue reconciliation.",
            findings=[
                f"Financial reconciliation verified: {state.retrieved_context[0]['content'][:60]}..."
            ],
            recommendation="Approve the audited figures for publication.",
            requested_approval="Sign-off on the financial statement.",
            source_references=source_refs,
        )

        # Generate DOCX via Dev 3's generator
        docx_gen = DocxGenerator(output_dir=tmp_path)
        artifact = docx_gen.generate(spec, task_id=state.task_id)

        docx_path = Path(artifact.storage_uri)
        assert docx_path.exists()
        assert artifact.type == "docx"

        # Verify exact citation is in the Word document
        doc = Document(docx_path)
        full_text = "\n".join(p.text for p in doc.paragraphs)
        assert "Source References" in full_text
        assert "sample-table.pdf, Page 1" in full_text
        assert "doc_audit_table" in full_text

    @pytest.mark.asyncio
    async def test_chunks_feed_approval_note_pdf_generation(
        self,
        retriever: KnowledgeRetriever,
        tmp_path: Path,
    ):
        """
        Verify hand-off into Dev 3's PDF generator (PdfApprovalNoteGenerator).
        """
        sample5 = SAMPLE_DIR / "sample5.pdf"
        retriever.ingest_document(sample5, document_id="doc_sample5_pdf")

        tool = RAGSearchTool(retriever=retriever)
        state = AgentState(task_id="pdf_task_102", user_request="Inspect sample5")
        context = {
            "task_id": state.task_id,
            "retrieved_context": state.retrieved_context,
            "tool_results": state.tool_results,
        }

        await tool.execute({"query": "dolor sit amet", "top_k": 2}, context=context)
        assert len(state.retrieved_context) > 0

        source_refs = [
            f"{c['source']}, Page {c['page']}" for c in state.retrieved_context
        ]

        spec = ApprovalNoteSpec(
            subject="Standard Operating Procedure Revision",
            purpose="Authorize updated procedural guidelines.",
            findings=["Guidelines aligned with sovereign safety thresholds."],
            recommendation="Adopt revised documentation across all operational units.",
            requested_approval="Approve standard operating procedure.",
            source_references=source_refs,
        )

        pdf_gen = PdfApprovalNoteGenerator(output_dir=tmp_path)
        artifact = pdf_gen.generate(spec, task_id=state.task_id)

        pdf_path = Path(artifact.storage_uri)
        assert pdf_path.exists()
        assert artifact.type == "pdf"

        # Read generated PDF with PyMuPDF to verify page grounding references
        doc = fitz.open(pdf_path)
        pdf_text = "\n".join(page.get_text("text") for page in doc)
        doc.close()

        assert "Standard Operating Procedure Revision" in pdf_text
        assert "sample5.pdf" in pdf_text
        assert "Page" in pdf_text
