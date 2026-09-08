from dataclasses import dataclass, field

from models.medical_state import DiagnosisStatus


@dataclass(frozen=True)
class UTIHospitalisV1:
    template_profile_id: str = "UTI_HOSPITALIS_V1"
    uppercase: bool = True
    show_empty_controls: bool = False
    show_empty_therapies: bool = False
    show_empty_complementary_exams: bool = False
    show_empty_diagnosis_specification: bool = False

    # Diagnosis visibility policy (Milestone 1.1, item 8).
    # Conservative default: every status is shown, preserving the exact
    # Milestone 1 behaviour (which never filtered diagnoses by status).
    # A profile can narrow this set (e.g. hide RULED_OUT) without the
    # renderer having to make that clinical decision on its own.
    diagnosis_visible_statuses: frozenset = field(default_factory=lambda: frozenset({
        DiagnosisStatus.ACTIVE,
        DiagnosisStatus.RESOLVED,
        DiagnosisStatus.RULED_OUT,
    }))

    # --- Section titles ----------------------------------------------
    main_title: str = "## EVOLUÇÃO CLINICA MEDICA ADULTO - UTI HOSPITALIS ##"
    diagnoses_title: str = "## HIPÓTESES DIAGNÓSTICAS:"
    hpma_title: str = "## HPMA:"
    evolution_title: str = "## EVOLUÇÃO:"
    physical_exam_title: str = "## EXAME FÍSICO:"
    history_title: str = "## ANTECEDENTES PESSOAIS:"
    antibiotics_title: str = "## ANTIBIOTICOTERAPIA:"
    antibiotics_not_applicable_text: str = "NÃO SE APLICA"
    therapies_title: str = "## TERAPIAS:"
    controls_title: str = "## CONTROLES:"
    complementary_exams_title: str = "## EXAMES COMPLEMENTARES"
    icu_justification_title: str = "## JUSTIFICATIVA DE INTERNAÇÃO EM UTI:"
    consultations_title: str = "## INTERCONSULTA DE ESPECIALIDADES:"
    consultations_conduct_label: str = "CONDUTAS"
    pending_title: str = "## AGUARDO:"
    care_actions_title: str = "## CONDUTA:"

    # --- Identification / admission labels ----------------------------
    identification_label: str = "IDENTIFICAÇÃO DO PACIENTE"
    hospital_admission_label: str = "DATA DE INTERNAÇÃO HOSPITALAR"
    icu_admission_label: str = "DATA DE INTERNAÇÃO EM UTI"
    origin_label: str = "ORIGEM DO PACIENTE"

    # --- Physical exam --------------------------------------------------
    physical_exam_order: tuple[str, ...] = (
        "general", "neurologic", "cardiovascular", "respiratory", "abdominal", "extremities",
    )
    physical_exam_labels: dict[str, str] = field(default_factory=lambda: {
        "general": "GERAL",
        "neurologic": "NEURO",
        "cardiovascular": "CARDIOVASCULAR",
        "respiratory": "RESPIRATORIO",
        "abdominal": "ABDOMINAL",
        "extremities": "EXTREMIDADES",
    })

    # --- Personal history -------------------------------------------------
    history_order: tuple[str, ...] = (
        "allergies", "past_medical_history", "previous_surgeries",
        "chronic_medications", "habits", "family_history",
    )
    history_labels: dict[str, str] = field(default_factory=lambda: {
        "allergies": "ALERGIAS",
        "past_medical_history": "ANTECEDENTES PATOLOGICOS PREGRESSOS",
        "previous_surgeries": "CIRURGIAS PREVIAS",
        "chronic_medications": "MEDICAMENTO DE USO CONTINUO",
        "habits": "HABITOS E VICIOS",
        "family_history": "HISTORICO FAMILIAR",
    })

    # --- Therapies (only these two are part of this profile's layout) ---
    hemotransfusion_label: str = "HEMOTRASFUSÃO"
    niv_label: str = "VNI"

    # --- Vital sign controls ---------------------------------------------
    controls_order: tuple[str, ...] = (
        "heart_rate", "respiratory_rate", "systolic_bp", "diastolic_bp",
        "mean_arterial_pressure", "spo2", "temperature", "glucose",
        "fluid_balance_total", "fluid_balance_24h", "urine_output_24h",
    )
    control_labels: dict[str, str] = field(default_factory=lambda: {
        "heart_rate": "FC",
        "respiratory_rate": "FR",
        "systolic_bp": "PAS",
        "diastolic_bp": "PAD",
        "mean_arterial_pressure": "PAM",
        "spo2": "SPO2",
        "temperature": "TX",
        "glucose": "DX",
        "fluid_balance_total": "BALANÇO HIDRICO TOTAL",
        "fluid_balance_24h": "BALANÇO HIDRICO ULTIMAS 24H",
        "urine_output_24h": "DIURESE ULTIMAS 24H",
    })

    # --- Complementary exams subsection titles ---------------------------
    laboratory_title: str = "LABORATORIAIS GERAIS"
    urinalysis_title: str = "URINA 1"
    gasometry_title: str = "GASOMETRIAS"
    troponin_title: str = "TROPONINAS"
    imaging_title: str = "EXAMES DE IMAGEM"

    study_status_labels: dict[str, str] = field(default_factory=lambda: {
        "ORDERED": "SOLICITADO",
        "SCHEDULED": "AGENDADO",
        "PENDING": "PENDENTE",
        "CANCELLED": "CANCELADO",
    })

    general_lab_order: list[str] = field(default_factory=lambda: [
        "HB", "HT", "LC", "PLAQ", "NA", "K", "MG", "P", "CL", "CA", "CAI",
        "CR", "UR", "TGO", "TGP", "FA", "GGT", "BD", "BI", "AMILASE", "LIPASE",
        "PROTEINAS_TOTAIS", "ALBUMINA", "GLOBULINA", "FRACAO_ALBUMINA_GLOBULINA",
        "CPK", "CKMB", "PCR", "TP", "INR", "TTPA", "GLICOSE"
    ])

    urine_order: list[str] = field(default_factory=lambda: [
        "VOLUME", "ASPECTO", "COR", "ODOR", "DENSIDADE", "PH", "GLICOSE", "CETONA",
        "PROTEINAS", "HEMOGLOBINA", "BILIRRUBINA", "UROBILINOGENIO", "LEUCOCITOS",
        "HEMACIAS", "CELULAS", "CILINDROS", "BACTERIAS", "CRISTAIS",
        "FILAMENTOS_DE_MUCO", "OUTROS_ELEMENTOS"
    ])

    gas_order: list[str] = field(default_factory=lambda: [
        "PH", "PCO2", "PO2", "SATO2", "HCO3", "BE", "CO2_TOTAL",
        "NA", "K", "CA", "LACTATO", "GLICOSE"
    ])

    excluded_lab_ids: set[str] = field(default_factory=lambda: {
        "PORCENTAGEM_NORMAL", "VALOR_GLOBULAR", "HCM", "VCM", "CHCM", "RDW", "MPV"
    })


DEFAULT_TEMPLATE = UTIHospitalisV1()
