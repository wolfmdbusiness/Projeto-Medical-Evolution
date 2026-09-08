# Render Contract v0.1 — UTI_HOSPITALIS_V1

Este documento existe para que um campo do Medical State ausente no texto
final nunca seja confundido com **perda silenciosa de dados**. Todo campo do
`MedicalState` está classificado abaixo em uma das quatro categorias:

- **DIRECTLY_RENDERED** — o `medical_note_renderer.py` imprime este campo (ou
  um subconjunto filtrado dele) diretamente no texto clínico.
- **DERIVED_INPUT** — o campo não aparece como texto, mas é consumido para
  decidir *se*/*como* renderizar (ex.: o renderability gate) ou é entrada
  para um módulo futuro de derivação (auditoria, evolução automática, etc.).
- **NOT_RENDERED_IN_THIS_PROFILE** — o dado é válido e preservado no schema,
  mas o profile `UTI_HOSPITALIS_V1` ainda não define um layout para ele.
- **FUTURE_MODULE** — depende de uma decisão de produto/layout que ainda não
  foi tomada (nova seção, novo módulo clínico).

Esta classificação é sobre **apresentação**, não sobre validade do dado: um
campo `NOT_RENDERED_IN_THIS_PROFILE` continua sendo validado normalmente pelo
schema estrito e pode ser usado por outro profile ou módulo no futuro.

## Identificação / admissão / diagnóstico

| Campo | Classificação |
|---|---|
| `display_identification` | DIRECTLY_RENDERED |
| `admission.hospital_admission_date` | DIRECTLY_RENDERED |
| `admission.icu_admission_date` | DIRECTLY_RENDERED |
| `admission.origin` | DIRECTLY_RENDERED |
| `diagnoses[].main` / `.specifications` | DIRECTLY_RENDERED (filtrado por `template.diagnosis_visible_statuses`, ver abaixo) |
| `diagnoses[].status` | DERIVED_INPUT (decide visibilidade via template) |
| `hpma.text` | DIRECTLY_RENDERED |
| `evolution_history[].text` | DIRECTLY_RENDERED |
| `clinical_events` | **DERIVED_INPUT** — reservado para um futuro MOD-EVOLUÇÃO / trilha de auditoria; não é impresso na nota atual. |

### Política de visibilidade de diagnóstico (item 8)

`Diagnosis.status` não é mais uma decisão clínica fixa no renderer: é uma
política configurável em `UTIHospitalisV1.diagnosis_visible_statuses`.

Default conservador (Milestone 1.1): **todos os status são exibidos**
(`ACTIVE`, `RESOLVED`, `RULED_OUT`), preservando exatamente o comportamento
do Milestone 1 (que nunca filtrava por status) e mantendo o Golden Sample
estável. Um profile pode restringir esse conjunto (por exemplo, ocultar
`RULED_OUT`) sem que essa lógica fique hardcoded no renderer.

## Exame físico / antecedentes / antibioticoterapia

| Campo | Classificação |
|---|---|
| `physical_exam.*` (6 campos) | DIRECTLY_RENDERED |
| `history.*` (6 campos) | DIRECTLY_RENDERED |
| `medications[]` com `status=ACTIVE` e classificação `ANTIBIOTIC` | DIRECTLY_RENDERED (seção ANTIBIOTICOTERAPIA) |
| `medications[]` — demais (não antibiótico ou inativas) | NOT_RENDERED_IN_THIS_PROFILE — dado preservado, sem seção de "medicações gerais" neste profile. |

## Terapias

| Campo | Classificação |
|---|---|
| `therapies.hemotransfusion` | DIRECTLY_RENDERED |
| `therapies.niv` | DIRECTLY_RENDERED |
| `therapies.invasive_mechanical_ventilation` | **NOT_RENDERED_IN_THIS_PROFILE / FUTURE_MODULE** — layout de VMI ainda não definido; dado presente e validado no schema. |
| `therapies.renal_replacement_therapy` | **NOT_RENDERED_IN_THIS_PROFILE / FUTURE_MODULE** — layout de TRS ainda não definido; dado presente e validado no schema. |

## Controles / exames complementares

| Campo | Classificação |
|---|---|
| `controls.*` (11 campos) | DIRECTLY_RENDERED |
| `complementary_exams.laboratory_observations` (exceto `excluded_lab_ids`) | DIRECTLY_RENDERED |
| `complementary_exams.laboratory_observations[].differential` | DIRECTLY_RENDERED (apenas para o analito `LC`, formatado entre colchetes) |
| `complementary_exams.urinalysis` | DIRECTLY_RENDERED |
| `complementary_exams.blood_gases` | DIRECTLY_RENDERED |
| `complementary_exams.troponins` | DIRECTLY_RENDERED |
| `complementary_exams.diagnostic_studies` | DIRECTLY_RENDERED |
| `complementary_exams.microbiology_serology` | **NOT_RENDERED_IN_THIS_PROFILE** — item 10: nenhum layout foi inventado sem definição funcional. O dado é mantido no schema, validado normalmente, e aguarda decisão de produto sobre como exibir organismo/susceptibilidade. |
| `complementary_exams.unmapped` | NOT_RENDERED_IN_THIS_PROFILE — bucket de triagem para dados ainda não mapeados a um campo formal; não deve aparecer no texto clínico. |

## UTI / interconsultas / pendências / condutas

| Campo | Classificação |
|---|---|
| `icu_context.explicit_justification` | DIRECTLY_RENDERED |
| `icu_context.active_supports` | **DERIVED_INPUT** — insumo para justificativa/evolução futura; não impresso hoje. |
| `icu_context.monitoring_requirements` | **DERIVED_INPUT** — idem. |
| `icu_context.instabilities` | **DERIVED_INPUT** — idem. |
| `icu_context.risk_factors` | **DERIVED_INPUT** — idem. |
| `consultations[]` | DIRECTLY_RENDERED |
| `pending[]` | DIRECTLY_RENDERED (filtrado por `status`) |
| `care_actions[]` | DIRECTLY_RENDERED |

## Metadados / validação / proveniência

| Campo | Classificação |
|---|---|
| `meta.template_profile_id` | DERIVED_INPUT — resolve qual `UTIHospitalisV1` é usado (`templates.registry.get_template_profile`); não aparece no texto. |
| `validation.overall_status` | DERIVED_INPUT — consumido pelo renderability gate (`rendering/renderability_gate.py`) para permitir ou bloquear a renderização. |
| `validation.conflicts` / `validation.unresolved` | DERIVED_INPUT — idem; um item ativo bloqueia a renderização mesmo com `overall_status=READY`. |
| `validation.warnings` | DERIVED_INPUT — reservado para uma camada de UI futura; não é escrito dentro do texto clínico. |
| `*.validation_status` em campos efetivamente exibidos | DERIVED_INPUT — `CONFLICT`/`UNRESOLVED` bloqueiam a renderização (ver gate); `MISSING`/`NEGATED`/`NOT_APPLICABLE` são semântica normal do campo. |
| `provenance.sources` | NOT_RENDERED_IN_THIS_PROFILE — preservado para auditoria/proveniência; não impresso no texto clínico nesta etapa. |

## Regra geral

Se um campo não está listado explicitamente acima, ele deve ser tratado como
**NOT_RENDERED_IN_THIS_PROFILE** até que este documento seja atualizado — não
como uma omissão acidental.
