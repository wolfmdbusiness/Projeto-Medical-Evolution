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

## Regra arquitetural (Milestone 1)

Não conectar APIs de IA neste milestone.

O objetivo desta fase é validar apenas:

1. schema;
2. normalização estrutural;
3. template;
4. renderer;
5. teste Golden.

## Milestone 2.0A / 2.0A.1 — MOD-EXAMES extraction core (determinístico)

Antes de qualquer LLM real: o contrato e o pipeline que uma extração real
vai alimentar.

```text
RAW EXAM TEXT
  -> ExamSourceEnvelope
  -> ExamExtractionCandidate     (exam_extraction/)
  -> validação Pydantic estrita
  -> normalização determinística (exam_normalization/)
  -> NormalizedExamBatch
  -> apply_exam_batch()
  -> MedicalState
```

- Um extrator nunca escreve em `MedicalState` diretamente.
- `resolve_canonical_id` nunca aceita um `raw_name` desconhecido como se
  fosse canônico: retorna `None` (⇒ `validation_status=UNRESOLVED`) salvo
  quando o nome está no `ALIAS_REGISTRY` ou em `KNOWN_CANONICAL_IDS` — é
  isso que impede `CA1` de ser silenciosamente tratado como `CAI`.
- `DiagnosticStudy.ordered_at/scheduled_at/performed_at/resulted_at` são
  `TemporalValue`, reaproveitando as mesmas regras temporais (data
  impossível como `31/09` nunca é corrigida).
- Idempotência vive em `processing_key` (por item) +
  `Provenance.processing_metadata`, nunca como marcador dentro de
  `source_refs` (que permanece só com ids de fonte clínica/documental).

## Milestone 2.0B — Single Live Extractor (DeepSeek)

Conecta exatamente um extrator LLM real (`DeepSeekExamExtractor`,
`deepseek-v4-flash`, `thinking` desabilitado, `response_format` JSON) ao
contrato `ExamExtractionCandidate`, com uma etapa determinística de
*evidence grounding* entre a extração e a normalização:

```text
ExamSourceEnvelope
  -> DeepSeekExamExtractor.extract()
  -> ExamExtractionCandidate
  -> validação Pydantic estrita
  -> evidence grounding (exam_extraction/grounding.py)
  -> normalização determinística
  -> NormalizedExamBatch -> apply_exam_batch() -> MedicalState
```

- `exam_normalization` nunca importa nada de `exam_extraction.providers`
  — só o `Protocol ExamExtractor` (`exam_extraction/base.py`).
- Grounding classifica cada item como `GROUNDED` / `UNGROUNDED` /
  `AMBIGUOUS` contra `ExamSourceEnvelope.raw_text`; só `GROUNDED` chega a
  virar fato clínico — o resto vai para `unmapped`, nunca some
  silenciosamente.
- Identidade de ocorrência estável (`source_id` + categoria + span de
  caracteres) alimenta o `processing_key` existente — reordenar a saída
  do LLM não duplica nada; duas ocorrências idênticas em posições
  distintas do texto continuam preservadas separadamente.
- `canonical_hint` do extrator nunca é autoridade — só
  `resolve_canonical_id(raw_name)` decide.
- `FakeExamExtractor` + fixtures gravadas (`exam_extraction/fixtures/`)
  mantêm `pytest -q` inteiramente offline; testes reais contra a DeepSeek
  ficam em `pytest -m live` (nunca rodam por padrão).
- Ver `docs/mod_exames_2_0b_live_findings.md` para os resultados da
  avaliação ao vivo (precision/recall/hallucination por snippet).

Não conectar Provider B, OCR, imagem, FastAPI, banco ou frontend nesta
etapa — ver a especificação do Milestone 2.0B para a lista completa.

## Milestone 2.0B.1 — Extraction Prompt 002

Iteração estritamente limitada ao prompt: os 6 `EXTRACTION_SCHEMA_FAILURE`
do prompt `2.0b-prompt-001` (ver findings acima) vinham de um único
exemplo no prompt (`general_labs`) que o modelo generalizava para buckets
com campos incompatíveis (`microbiology`, `diagnostic_studies`,
`blood_gases`, `unmapped`, `extraction_warnings`).

- `exam_extraction/schema_guide.py`: renderiza
  `ExamExtractionCandidate.model_json_schema()` em texto compacto e
  determinístico — fonte de verdade única, sem segunda taxonomia manual
  que possa divergir dos modelos Pydantic.
- `exam_extraction/prompts/mod_exames_2_0b_002.py`
  (`MOD_EXAMES_EXTRACTION_PROMPT_VERSION = "2.0b-prompt-002"`): embute o
  schema guide + um exemplo completo e schema-válido com um item em CADA
  bucket (nunca só `general_labs`). Prompt 001 preservado inalterado no
  repositório para auditoria.
- Nenhum modelo Pydantic foi alterado; `extra="forbid"` permanece em
  todos os modelos strict.
- `DeepSeekExamExtractor` agora aponta para o prompt 002 por padrão, com
  `build_messages_fn`/`prompt_version` sobrescrevíveis (usado para o
  benchmark 001 vs 002 lado a lado).
- Resultado ao vivo: schema success 10/10 em duas execuções independentes
  (contra 6/10 e 4/10 do prompt 001 nas mesmas duas execuções) — ver
  `docs/mod_exames_2_0b_1_live_findings.md` para a tabela completa e os
  dois casos restantes documentados (não corrigidos por retry ou
  afrouxamento de schema, conforme vedado nesta etapa).

## Milestone 2.0B.2 — DeepSeek Extraction Stability Calibration

Mede e melhora a estabilidade do `deepseek-v4-flash` como extrator, sem
afrouxar nenhum contrato.

- `DeepSeekExamExtractor` agora envia `temperature=0` explicitamente
  (`thinking` continua `disabled`; `top_p` não é tocado).
- `exam_extraction/prompts/mod_exames_2_0b_003.py`
  (`MOD_EXAMES_EXTRACTION_PROMPT_VERSION = "2.0b-prompt-003"`): mesma
  base do prompt 002 (schema guide + um exemplo por bucket), com uma
  regra nova — `evidence_text` deve ser o menor trecho literal contínuo
  que sustenta exclusivamente aquele item, nunca a linha inteira
  compartilhada entre vários itens. Prompts 001 e 002 preservados
  inalterados.
- `exam_extraction/evaluation.py`: `hallucination_rate` foi separado em
  `true_hallucination_rate` (só itens UNGROUNDED — texto que nunca
  existiu na fonte) e `ambiguity_rate` (só itens AMBIGUOUS — evidência
  real, porém não atribuível com segurança a um item). Nenhum dos dois
  muda o que acontece com o item: ambos continuam bloqueados de entrar em
  qualquer bucket clínico (`exam_extraction/grounding.py`, inalterado
  nesta etapa). `ExpectedItem` ganhou `optional=True`, usado para
  corrigir a ground truth de `SNIPPET-INVALID-DATE` — um
  `diagnostic_study_finding` para "SOLICITADO" passa a ser creditável se
  presente, mas nunca obrigatório.
- Benchmark de estabilidade: 10 snippets × 5 execuções independentes = 50
  chamadas ao vivo. Resultado: schema success 50/50 (100%), grounded rate
  dos itens aceitos 100%, true hallucination rate 0%, precision média e
  mínima 100%, recall médio e mínimo 100% — todas as seis metas do item
  14 atingidas com folga. `CA1` nunca promovido a `CAI` (mesmo com
  `canonical_hint="CAI"`), `ESBL 04` sempre sem resultado, `31/09` nunca
  corrigido — confirmado nas 5 execuções. Ver
  `docs/mod_exames_2_0b_2_stability_benchmark.md` para a tabela completa
  por execução.
