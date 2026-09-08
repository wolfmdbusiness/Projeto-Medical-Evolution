"""Required evaluation snippets (Milestone 2.0B, item 24).

Small, synthetic/de-identified fragments derived from the shapes already
established by the Goldens — never a real patient record. This is the
single source of truth for snippet text: both the offline
`FakeExamExtractor`-driven tests (via the matching fixture in
`recorded_responses/`) and the live DeepSeek tests (item 25) extract
against these exact same strings, so results are directly comparable.

`SNIPPET_SOURCE_IDS` doubles as the recorded-response fixture filename
convention: `recorded_responses/<source_id>.json`.
"""

from __future__ import annotations

from exam_extraction.evaluation import ExpectedItem

SNIPPETS: dict[str, str] = {
    "SNIPPET-EASY": "HB 12,0; HT 36,0; NA 140; K 4,0",
    "SNIPPET-OPERATORS": "PCR <0,6; TFG >90; BETA HCG <2,0",
    "SNIPPET-ALIASES": "LEUCO 8330; PLQ 270K; RNI 1,03; U 25",
    "SNIPPET-UNKNOWN-ANALYTE": "CA1 1,33",
    "SNIPPET-GAS": "28/08 (VENOSA): PH 7,360; PCO2 48,0; PO2 47,0",
    "SNIPPET-MICROBIOLOGY": (
        "31/08: CULTURA DE VIGILANCIA PARA ESBL >> NEGATIVO\n"
        "31/08: CULTURA DE VIGILANCIA PARA ESBL 02 >> NEGATIVO\n"
        "31/08: CULTURA DE VIGILANCIA PARA ESBL 03 >> NEGATIVO\n"
        "31/08: CULTURA DE VIGILANCIA PARA ESBL 04 >>"
    ),
    "SNIPPET-TEMPORAL-AMBIGUITY": "31/08 (13:20): NA 140\n31/08: NA 141",
    "SNIPPET-EXTERNAL": "D DÍMERO >4000 (VR<500) - REALIZADO EM SERVIÇO EXTERNO",
    "SNIPPET-DIAGNOSTIC-STUDY": "02/09: ENDOSCOPIA DIGESTIVA ALTA\n>> GASTRITE ANTRAL ENANTEMATOSA LEVE",
    "SNIPPET-INVALID-DATE": "31/09: COLONOSCOPIA\n>> SOLICITADO",
}

# Ground truth for the evaluation harness (items 22-23). Only what should
# be extracted+grounded is asserted here; whether an analyte resolves to a
# specific canonical id is a separate, informational question the harness
# reports on but does not require to pass (item 31 -- the alias registry is
# never widened just to make an evaluation snippet score better).
EXPECTED_ITEMS: dict[str, list[ExpectedItem]] = {
    "SNIPPET-EASY": [
        ExpectedItem("general_lab", "HB"),
        ExpectedItem("general_lab", "HT"),
        ExpectedItem("general_lab", "NA"),
        ExpectedItem("general_lab", "K"),
    ],
    "SNIPPET-OPERATORS": [
        ExpectedItem("general_lab", "PCR"),
        ExpectedItem("general_lab", "TFG"),
        ExpectedItem("general_lab", "BETA HCG"),
    ],
    "SNIPPET-ALIASES": [
        ExpectedItem("general_lab", "LEUCO"),
        ExpectedItem("general_lab", "PLQ"),
        ExpectedItem("general_lab", "RNI"),
        ExpectedItem("general_lab", "U"),
    ],
    "SNIPPET-UNKNOWN-ANALYTE": [
        ExpectedItem("general_lab", "CA1", expect_unresolved=True),
    ],
    "SNIPPET-GAS": [
        # The panel itself is a groundable item too (its specimen/dateline
        # claim), labeled by GroundingRecord as its raw_specimen_type.
        ExpectedItem("blood_gas", "VENOSA"),
        ExpectedItem("blood_gas_observation", "PH"),
        ExpectedItem("blood_gas_observation", "PCO2"),
        ExpectedItem("blood_gas_observation", "PO2"),
    ],
    "SNIPPET-MICROBIOLOGY": [
        ExpectedItem("microbiology", "CULTURA DE VIGILANCIA PARA ESBL"),
        ExpectedItem("microbiology", "CULTURA DE VIGILANCIA PARA ESBL 02"),
        ExpectedItem("microbiology", "CULTURA DE VIGILANCIA PARA ESBL 03"),
        ExpectedItem("microbiology", "CULTURA DE VIGILANCIA PARA ESBL 04"),
    ],
    "SNIPPET-TEMPORAL-AMBIGUITY": [
        # Appears twice, at two different spans -- grounding must keep both
        # occurrences distinct (item 15), so both are expected here too.
        ExpectedItem("general_lab", "NA"),
        ExpectedItem("general_lab", "NA"),
    ],
    "SNIPPET-EXTERNAL": [
        ExpectedItem("general_lab", "D DÍMERO"),
    ],
    "SNIPPET-DIAGNOSTIC-STUDY": [
        ExpectedItem("diagnostic_study", "ENDOSCOPIA DIGESTIVA ALTA"),
        # The finding is its own groundable item under the study, labeled
        # (like every diagnostic_study_finding record) by the parent
        # study's raw_name.
        ExpectedItem("diagnostic_study_finding", "ENDOSCOPIA DIGESTIVA ALTA"),
    ],
    "SNIPPET-INVALID-DATE": [
        ExpectedItem("diagnostic_study", "COLONOSCOPIA"),
        ExpectedItem("diagnostic_study_finding", "COLONOSCOPIA"),
    ],
}
