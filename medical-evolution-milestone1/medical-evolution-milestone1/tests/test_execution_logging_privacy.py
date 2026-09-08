"""Milestone 2.0B, item 30: `run_extraction`'s logging never carries raw
clinical text, patient identifiers, or a credential -- only ids, counts,
timing, and error codes."""

import logging

from exam_extraction.execution import run_extraction
from exam_extraction.fake import FakeExamExtractor
from exam_extraction.models import Evidence, ExamExtractionCandidate, ExamSourceEnvelope, GeneralLabCandidate
from models.medical_state import SourceType

_SENSITIVE_TEXT = "PACIENTE TESTE CONFIDENCIAL 99/99: HB 12,0 NAO DEVE APARECER EM LOG"


def _envelope() -> ExamSourceEnvelope:
    return ExamSourceEnvelope(
        source_id="SRC-LOG", patient_ref="PATIENT-GOLDEN-TEST",
        source_type=SourceType.MEDICAL_EVOLUTION, raw_text=_SENSITIVE_TEXT,
    )


def test_successful_run_never_logs_raw_text(caplog):
    candidate = ExamExtractionCandidate(
        source_id="SRC-LOG",
        general_labs=[
            GeneralLabCandidate(raw_name="HB", raw_value="12,0", source_order=1, evidence=Evidence(evidence_text="HB 12,0"), source_ref="SRC-LOG"),
        ],
    )
    extractor = FakeExamExtractor({"SRC-LOG": candidate})
    with caplog.at_level(logging.DEBUG, logger="mod_exames.execution"):
        run_extraction(_envelope(), extractor, provider="FAKE", model="fake-v0")

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert _SENSITIVE_TEXT not in log_text
    assert "CONFIDENCIAL" not in log_text


def test_failed_run_never_logs_raw_text_either(caplog):
    extractor = FakeExamExtractor({})  # no recorded response -> ProviderFailure
    with caplog.at_level(logging.DEBUG, logger="mod_exames.execution"):
        run_extraction(_envelope(), extractor, provider="FAKE", model="fake-v0")

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert _SENSITIVE_TEXT not in log_text
    assert "CONFIDENCIAL" not in log_text
