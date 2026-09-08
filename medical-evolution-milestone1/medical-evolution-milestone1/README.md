# Medical Evolution — Milestone 1

Primeiro núcleo determinístico do projeto **Prompt Evolução Médica**.

## Objetivo

Provar a seguinte relação antes de integrar qualquer IA:

```text
DADOS ESTRUTURADOS CORRETOS
        ↓
MEDICAL STATE v0.3
        ↓
UTI_HOSPITALIS_V1
        ↓
RENDERER DETERMINÍSTICO
        ↓
DOCUMENTO FINAL REPRODUZÍVEL
```

O Golden Sample 001 foi **desidentificado**. Nenhum nome real de paciente foi mantido.

Ele é uma **versão padronizada do caso de referência**, usada como target determinístico; não preserva necessariamente inconsistências ocasionais do texto clínico original.

## Requisitos

- Python 3.11 ou superior
- pip

## Instalação

```bash
python -m venv .venv
```

### macOS / Linux

```bash
source .venv/bin/activate
```

### Windows PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

Depois:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Renderizar o Golden Sample

```bash
python render_golden_001.py
```

## Rodar os testes

```bash
pytest -q
```

Resultado esperado:

```text
99 passed
```

## Estrutura

```text
medical-evolution-milestone1/
├── models/
│   └── medical_state.py
├── templates/
│   ├── uti_hospitalis_v1.py
│   └── registry.py
├── rendering/
│   ├── medical_note_renderer.py
│   ├── renderability_gate.py
│   └── text_utils.py
├── golden_samples/
│   ├── golden_001/   (STRICT_RENDER_REFERENCE)
│   │   ├── golden_001_state.json
│   │   └── golden_001_expected.txt
│   └── golden_002 .. golden_008/   (SEMANTIC_RENDER_REFERENCE)
│       ├── golden_00X_state.json
│       └── golden_00X_audit_notes.json   (003/004/005/007/008 only)
├── docs/
│   ├── render_contract_v0_1.md
│   ├── golden_sample_roles_v0_1.md
│   └── audit_findings_v0_1.md
├── tests/
│   ├── test_golden_001.py
│   ├── test_golden_002_semantic.py .. test_golden_008_semantic.py
│   ├── test_audit_case_metadata.py
│   ├── test_temporal_and_semantics.py
│   ├── test_strict_models.py
│   ├── test_renderability_gate.py
│   ├── test_template_profile.py
│   ├── test_diagnosis_policy.py
│   ├── test_differential.py
│   └── test_render_contract.py
├── render_golden_001.py
├── requirements.txt
└── README.md
```

## Milestone 1.1

Reforço do núcleo determinístico antes de qualquer IA/API/frontend:

- Modelos Pydantic estritos (`extra="forbid"`): campo desconhecido ou
  digitado errado agora falha a validação em vez de ser ignorado.
- Vocabulários antes livres (status de diagnóstico, medicação, evento
  clínico, consulta, pendência, ação de cuidado, estudo diagnóstico, tipo de
  fonte) viraram Enums.
- Renderability gate (`rendering/renderability_gate.py`): o renderer recusa
  gerar o documento quando `validation.overall_status` é `PROCESSING`,
  `REVIEW_REQUIRED` ou `FAILED`, ou quando existe conflito/unresolved ativo,
  ou quando um campo efetivamente exibido tem `validation_status=CONFLICT`
  ou `UNRESOLVED`. Lança `RenderNotAllowedError` com a lista de motivos.
- `state.meta.template_profile_id` deixou de ser decorativo: é resolvido via
  `templates/registry.py` (`get_template_profile`), com erro explícito para
  profile desconhecido ou incompatível com o template fornecido.
- Diferencial do leucograma (SEG%, EOS%, BASO%, ...) passou a ter estrutura
  própria (`LabObservation.differential`); `reference_range` voltou a
  significar apenas intervalo de referência.
- Textos de apresentação (títulos de seção, rótulos) migraram do renderer
  para `UTIHospitalisV1`; ver `docs/render_contract_v0_1.md` para a
  classificação de todo campo do Medical State (renderizado, insumo
  derivado, não renderizado neste profile, ou módulo futuro).

## Milestone 1.2 — Golden Expansion & Semantic Core Hardening

Incorpora os comportamentos recorrentes de 7 casos clínicos reais
desidentificados (GOLDEN-002..008), sem IA/OCR/API externa/FastAPI/banco/
frontend/CDS. `GOLDEN-001` continua `STRICT_RENDER_REFERENCE` (byte-a-byte
estável); os demais são `SEMANTIC_RENDER_REFERENCE` — ver
`docs/golden_sample_roles_v0_1.md`.

- `TemporalValue` (raw/normalized/precision/period/validation_status)
  substitui strings soltas para datas de admissão e de evolução; datas
  impossíveis (ex. "31/09") são preservadas em `raw` e nunca corrigidas
  silenciosamente.
- Interconsultas ganham `consultations_section_state`
  (`PRESENT`/`NOT_REQUESTED`/`UNKNOWN`), `ConsultationStatus` ampliado
  (`REQUESTED`/`PENDING`/`ANSWERED`/`COMPLETED`/...), `conclusions[]`
  distinto de `recommendations[]`, e agrupamento de entradas adjacentes da
  mesma especialidade sob um único cabeçalho.
- `DiagnosticStudy` separa `procedure_status` de `result_status` (um exame
  pode estar `PERFORMED` com laudo `PENDING`, sem colapsar em um status só).
- `icu_context.explicit_justifications` é uma lista (múltiplas
  justificativas), e `requirement_status_history` registra
  `REQUIRED`/`NO_LONGER_REQUIRED` de forma append-only, sem apagar histórico.
- `LabObservation.value` ganha `operator`/`normalized_numeric_value`
  (`>4000` nunca vira `4000`); `reference_range` aceita `reference_raw`
  unilateral (`VR<500`); `BloodGas.specimen_type` é estruturado
  (`ARTERIAL`/`VENOUS`/`CAPILLARY`).
- Microbiologia/sorologia passou a ser diretamente renderizada (título
  neutro no Template Profile); nunca deduplicada por nome/data.
- Duas medições do mesmo analito no mesmo dia sem ordem temporal clara
  nunca são resolvidas arbitrariamente — ambas são mantidas visíveis.
- `Medication.started_at`/`documented_therapy_day` habilitam
  "CEFTRIAXONE D1: 02/09" na ANTIBIOTICOTERAPIA; nova seção opcional
  "## EM USO DE:" deriva de `medications[]` ativos não-antibióticos.
- `AUDIT_CASE`: metadata de conflitos conhecidos (CONTRADICTED /
  POTENTIAL_TEMPORAL_CONFLICT / STALE_DOCUMENTATION — ver
  `docs/audit_findings_v0_1.md`) para GOLDEN-003/004/005/007/008; nenhum
  auditor foi implementado.

## Regra arquitetural

Não conectar APIs de IA neste milestone.

O objetivo desta fase é validar apenas:

1. schema;
2. normalização estrutural;
3. template;
4. renderer;
5. teste Golden.

Quando este núcleo estiver estável, a próxima etapa será adicionar FastAPI e, depois, os módulos de IA.
