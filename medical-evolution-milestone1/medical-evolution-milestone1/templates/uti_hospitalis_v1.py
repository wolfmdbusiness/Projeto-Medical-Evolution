from dataclasses import dataclass, field


@dataclass(frozen=True)
class UTIHospitalisV1:
    template_profile_id: str = "UTI_HOSPITALIS_V1"
    uppercase: bool = True
    show_empty_controls: bool = False
    show_empty_therapies: bool = False
    show_empty_complementary_exams: bool = False
    show_empty_diagnosis_specification: bool = False

    laboratory_title: str = "LABORATORIAIS GERAIS"
    urinalysis_title: str = "URINA 1"
    gasometry_title: str = "GASOMETRIAS"
    troponin_title: str = "TROPONINAS"
    imaging_title: str = "EXAMES DE IMAGEM"

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
