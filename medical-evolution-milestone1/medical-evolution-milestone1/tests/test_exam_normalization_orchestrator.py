"""Milestone 2.0A: orchestrator-level normalization behaviors, using
de-identified fragments derived from GOLDEN-002..008 (item 23).
"""

from exam_extraction.models import (
    BloodGasCandidate,
    BloodGasObservationCandidate,
    DiagnosticStudyCandidate,
    Evidence,
    ExamExtractionCandidate,
    ExamSourceEnvelope,
    GeneralLabCandidate,
    MicrobiologyCandidate,
    TroponinCandidate,
)
from exam_normalization.orchestrator import normalize_extraction_candidate
from exam_normalization.temporal import parse_exam_temporal
from models.medical_state import (
    DiagnosticStudyProcedureStatus,
    DiagnosticStudyResultStatus,
    GasSpecimenType,
    SourceType,
)


def _ev(text: str) -> Evidence:
    return Evidence(evidence_text=text)


def _envelope(source_id: str = "SRC-TEST", source_type: SourceType = SourceType.MEDICAL_EVOLUTION, reference_year: int = None) -> ExamSourceEnvelope:
    # A real document carries its own dateline; this is what lets the
    # normalizer complete a bare "31/08" into a full date (item 10).
    document_temporal_value = parse_exam_temporal(f"01/01/{reference_year}") if reference_year else None
    return ExamSourceEnvelope(
        source_id=source_id, patient_ref="PATIENT-GOLDEN-TEST", source_type=source_type,
        raw_text="(fragment)", document_temporal_value=document_temporal_value,
    )


# --- same-day analyte ambiguity (item 11), fragment from GOLDEN-003 CR ----

def test_same_day_same_analyte_ambiguity_is_flagged_never_arbitrarily_chosen():
    # "31/08 (13:20): ... CR 0,85" and "31/08: ... CR 0,99" (GOLDEN-003)
    candidate = ExamExtractionCandidate(
        source_id="SRC-G003",
        general_labs=[
            GeneralLabCandidate(raw_name="CR", raw_value="0,85", raw_temporal="31/08 (13:20)", source_order=1, evidence=_ev("CR 0,85"), source_ref="SRC-G003"),
            GeneralLabCandidate(raw_name="CR", raw_value="0,99", raw_temporal="31/08", source_order=2, evidence=_ev("CR 0,99"), source_ref="SRC-G003"),
        ],
    )
    batch = normalize_extraction_candidate(candidate, _envelope("SRC-G003", reference_year=2026))
    assert {o.value.raw_value for o in batch.laboratory_observations} == {"0,85", "0,99"}
    assert any(w.category == "SAME_DAY_TEMPORAL_AMBIGUITY" for w in batch.warnings)


def test_same_day_same_analyte_with_both_times_is_not_flagged():
    candidate = ExamExtractionCandidate(
        source_id="SRC-X",
        general_labs=[
            GeneralLabCandidate(raw_name="K", raw_value="3,5", raw_temporal="31/08 (08:00)", source_order=1, evidence=_ev("K 3,5"), source_ref="SRC-X"),
            GeneralLabCandidate(raw_name="K", raw_value="4,0", raw_temporal="31/08 (18:00)", source_order=2, evidence=_ev("K 4,0"), source_ref="SRC-X"),
        ],
    )
    batch = normalize_extraction_candidate(candidate, _envelope("SRC-X", reference_year=2026))
    assert not any(w.category == "SAME_DAY_TEMPORAL_AMBIGUITY" for w in batch.warnings)


# --- troponins stay individual/independent (item 14) ----------------------

def test_troponins_are_not_subject_to_same_day_ambiguity_policy():
    # GOLDEN-001 has 4 individual troponin readings across 2 days -- all
    # must survive untouched, and never trigger the general-lab ambiguity
    # warning even when two share a day.
    candidate = ExamExtractionCandidate(
        source_id="SRC-G001",
        troponins=[
            TroponinCandidate(raw_name="TROPONINA", raw_value="0,13", raw_temporal="02/09 (13:34)", source_order=1, evidence=_ev("TROPONINA 0,13"), source_ref="SRC-G001"),
            TroponinCandidate(raw_name="TROPONINA", raw_value="0,15", raw_temporal="02/09 (16:38)", source_order=2, evidence=_ev("TROPONINA 0,15"), source_ref="SRC-G001"),
            TroponinCandidate(raw_name="TROPONINA", raw_value="<0,1", raw_temporal="02/09 (19:37)", source_order=3, evidence=_ev("TROPONINA <0,1"), source_ref="SRC-G001"),
            TroponinCandidate(raw_name="TROPONINA", raw_value="<0,1", raw_temporal="03/09 (01:28)", source_order=4, evidence=_ev("TROPONINA <0,1"), source_ref="SRC-G001"),
        ],
    )
    batch = normalize_extraction_candidate(candidate, _envelope("SRC-G001"))
    assert len(batch.troponins) == 4
    assert not any(w.category == "SAME_DAY_TEMPORAL_AMBIGUITY" for w in batch.warnings)


# --- microbiology: repeated cultures preserved, missing stays missing -----

def test_repeated_cultures_preserved_individually_and_missing_result_stays_missing():
    # GOLDEN-004 fragment: ESBL x4 (all negative) + one entry with no result.
    candidate = ExamExtractionCandidate(
        source_id="SRC-G004",
        microbiology=[
            MicrobiologyCandidate(raw_name="CULTURA DE VIGILANCIA PARA ESBL", raw_result="RESULTADO NEGATIVO", source_order=1, evidence=_ev("ESBL negativo"), source_ref="SRC-G004"),
            MicrobiologyCandidate(raw_name="CULTURA DE VIGILANCIA PARA ESBL 02", raw_result="RESULTADO NEGATIVO", source_order=2, evidence=_ev("ESBL 02 negativo"), source_ref="SRC-G004"),
            MicrobiologyCandidate(raw_name="CULTURA DE VIGILANCIA PARA ESBL 03", raw_result="RESULTADO NEGATIVO", source_order=3, evidence=_ev("ESBL 03 negativo"), source_ref="SRC-G004"),
            MicrobiologyCandidate(raw_name="CULTURA DE VIGILANCIA PARA ESBL 04", raw_result="RESULTADO NEGATIVO", source_order=4, evidence=_ev("ESBL 04 negativo"), source_ref="SRC-G004"),
            MicrobiologyCandidate(raw_name="CULTURA PARA ENTEROCOCCUS SPP RESISTENTES À VANCOMICINA 04", raw_result=None, source_order=5, evidence=_ev("sem resultado"), source_ref="SRC-G004"),
        ],
    )
    batch = normalize_extraction_candidate(candidate, _envelope("SRC-G004"))
    assert len(batch.microbiology_serology) == 5  # never merged/deduplicated by name
    last = batch.microbiology_serology[-1]
    assert last.result.value is None  # MISSING, never copied from the previous "NEGATIVO"
    from models.medical_state import ValidationStatus
    assert last.result.validation_status == ValidationStatus.MISSING
    negatives = [m for m in batch.microbiology_serology if m.result.value == "RESULTADO NEGATIVO"]
    assert len(negatives) == 4


# --- blood gas as its own event + VENOSA specimen (item 13) ---------------

def test_blood_gas_is_its_own_event_with_venous_specimen():
    candidate = ExamExtractionCandidate(
        source_id="SRC-G008",
        blood_gases=[
            BloodGasCandidate(
                raw_specimen_type="VENOSA", raw_temporal="28/08", source_order=1,
                evidence=_ev("28/08 (VENOSA): PH 7,360; PCO2 48,0"),
                source_ref="SRC-G008",
                observations=[
                    BloodGasObservationCandidate(raw_name="PH", raw_value="7,360", source_order=1, evidence=_ev("PH 7,360"), source_ref="SRC-G008"),
                    BloodGasObservationCandidate(raw_name="PCO2", raw_value="48,0", source_order=2, evidence=_ev("PCO2 48,0"), source_ref="SRC-G008"),
                ],
            ),
        ],
    )
    batch = normalize_extraction_candidate(candidate, _envelope("SRC-G008"))
    assert len(batch.blood_gases) == 1
    gas = batch.blood_gases[0]
    assert gas.specimen_type == GasSpecimenType.VENOUS
    assert len(gas.observations) == 2


# --- diagnostic study: procedure vs result, no inference from hints -------

def test_recommended_solicitar_never_becomes_ordered_without_a_real_hint():
    # item 17: mentioning a study in a "recommended" context must not be
    # inferred as ORDERED just because it's a diagnostic study candidate.
    candidate = ExamExtractionCandidate(
        source_id="SRC-G004",
        diagnostic_studies=[
            DiagnosticStudyCandidate(
                raw_name="USG DOPPLER DE SISTEMA PORTA + VCI", source_order=1,
                evidence=_ev("RECOMENDADO SOLICITAR USG DOPPLER DE SISTEMA PORTA + VCI"),
                source_ref="SRC-G004",
                procedure_status_hint=None,  # no structured hint provided
            ),
        ],
    )
    batch = normalize_extraction_candidate(candidate, _envelope("SRC-G004"))
    study = batch.diagnostic_studies[0]
    assert study.procedure_status != DiagnosticStudyProcedureStatus.ORDERED
    assert study.procedure_status == DiagnosticStudyProcedureStatus.UNKNOWN


def test_diagnostic_study_procedure_and_result_status_are_independent_axes():
    candidate = ExamExtractionCandidate(
        source_id="SRC-G005",
        diagnostic_studies=[
            DiagnosticStudyCandidate(
                raw_name="RM E ANGIORM ARTERIAL E VENOSA DE CRÂNIO", source_order=1,
                evidence=_ev("PENDENTE LAUDO DE RM E ANGIORM"),
                source_ref="SRC-G005",
                procedure_status_hint="PERFORMED",
                result_status_hint="PENDING",
            ),
        ],
    )
    batch = normalize_extraction_candidate(candidate, _envelope("SRC-G005"))
    study = batch.diagnostic_studies[0]
    assert study.procedure_status == DiagnosticStudyProcedureStatus.PERFORMED
    assert study.result_status == DiagnosticStudyResultStatus.PENDING


def test_unstructured_status_hint_text_is_never_trusted():
    candidate = ExamExtractionCandidate(
        source_id="SRC-Y",
        diagnostic_studies=[
            DiagnosticStudyCandidate(
                raw_name="TC DE CRANIO", source_order=1, evidence=_ev("TC DE CRANIO"), source_ref="SRC-Y",
                procedure_status_hint="provavelmente solicitado ontem",  # free text, not an enum value
            ),
        ],
    )
    batch = normalize_extraction_candidate(candidate, _envelope("SRC-Y"))
    assert batch.diagnostic_studies[0].procedure_status == DiagnosticStudyProcedureStatus.UNKNOWN


# --- external provenance (item 22) ----------------------------------------

def test_external_source_provenance_is_preserved():
    candidate = ExamExtractionCandidate(
        source_id="SRC-G007-EXT",
        general_labs=[
            GeneralLabCandidate(
                raw_name="D DIMERO", raw_value=">4000", raw_reference_range="VR<500", source_order=1,
                evidence=_ev("D DÍMERO >4000 (VR<500)"), source_ref="SRC-G007-EXT",
            ),
        ],
    )
    batch = normalize_extraction_candidate(candidate, _envelope("SRC-G007-EXT", SourceType.EXTERNAL_LAB_REPORT))
    obs = batch.laboratory_observations[0]
    assert "SRC-G007-EXT" in obs.source_refs
    assert obs.reference_range.reference_raw == "VR<500"
    assert obs.reference_range.upper == 500.0
    assert obs.value.operator.value == ">"


# --- VCM/HCM storable despite being display-excluded (item 21) -----------

def test_display_excluded_analytes_are_still_normalized_and_stored():
    candidate = ExamExtractionCandidate(
        source_id="SRC-G005",
        general_labs=[
            GeneralLabCandidate(raw_name="VCM", raw_value="79,5", source_order=1, evidence=_ev("VCM 79,5"), source_ref="SRC-G005"),
            GeneralLabCandidate(raw_name="HCM", raw_value="25,8", source_order=2, evidence=_ev("HCM 25,8"), source_ref="SRC-G005"),
        ],
    )
    batch = normalize_extraction_candidate(candidate, _envelope("SRC-G005"))
    canonical_ids = {o.analyte.canonical_id for o in batch.laboratory_observations}
    assert {"VCM", "HCM"} <= canonical_ids
    # Normalization never consults a display policy -- that's the Template
    # Profile's job, applied only later, at render time.
