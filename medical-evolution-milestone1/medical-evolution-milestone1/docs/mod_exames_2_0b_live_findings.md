# MOD-EXAMES 2.0B — Live Evaluation Findings

Resultado de uma execução de `pytest -m live` contra a API real da
DeepSeek (`deepseek-v4-flash`, `thinking` desabilitado, `response_format`
JSON), usando exclusivamente os 10 snippets sintéticos/desidentificados de
`exam_extraction/fixtures/snippets.py` (Milestone 2.0B, item 24). Nenhum
prontuário completo foi usado nesta etapa (item 21).

Estes números são de uma execução específica; um LLM real não é
determinístico entre chamadas (duas mensagens idênticas podem produzir
JSON estruturalmente diferente), então os resultados podem variar em
execuções futuras. O propósito deste documento é registrar o
comportamento observado e a causa raiz de cada falha, não travar a
implementação em um score específico (item 31).

## Resumo

| Snippet | Status | Precision | Recall | Hallucination | Observação |
|---|---|---|---|---|---|
| SNIPPET-EASY | SUCCESS | 1.00 | 1.00 | 0.00 | — |
| SNIPPET-OPERATORS | SUCCESS | 1.00 | 1.00 | 0.00 | — |
| SNIPPET-ALIASES | SUCCESS | 1.00 | 1.00 | 0.00 | — |
| SNIPPET-TEMPORAL-AMBIGUITY | SUCCESS | 1.00 | 1.00 | 0.00 | — |
| SNIPPET-UNKNOWN-ANALYTE | EXTRACTION_SCHEMA_FAILURE | — | — | — | ver causa (1) |
| SNIPPET-GAS | EXTRACTION_SCHEMA_FAILURE | — | — | — | ver causa (2) |
| SNIPPET-MICROBIOLOGY | EXTRACTION_SCHEMA_FAILURE | — | — | — | ver causa (3) |
| SNIPPET-EXTERNAL | EXTRACTION_SCHEMA_FAILURE | — | — | — | ver causa (1) |
| SNIPPET-DIAGNOSTIC-STUDY | EXTRACTION_SCHEMA_FAILURE | — | — | — | ver causa (3) |
| SNIPPET-INVALID-DATE | EXTRACTION_SCHEMA_FAILURE | — | — | — | ver causa (1)+(3) |

4/10 sucesso, 6/10 falha de schema, 0/10 falha de provider/rede/JSON
inválido, 0 alucinação clínica observada nos casos bem-sucedidos (nenhum
item ungrounded/ambíguo quando a extração teve sucesso estrutural).

Latência observada: ~1.5s–3.1s por chamada. Tokens de entrada
~885–970, saída ~180–620 (todos dentro do `max_tokens=4096` configurado).

## Causas raiz identificadas (não corrigidas — ver item 31)

**(1) `unmapped[]` enviado como lista de strings, não de objetos
`UnmappedCandidate`.** Em vez de `{"raw_text": "...", "evidence":
{"evidence_text": "..."}, "source_ref": "...", "source_order": N}`, o
modelo às vezes envia só a string bruta. O exemplo JSON reduzido no
prompt (`mod_exames_2_0b_001.py`) nunca demonstra a forma de `unmapped`
nem de `extraction_warnings` — só de `general_labs`.

**(2) `blood_gases[]` "achatado".** O modelo tratou cada analito da
gasometria (PH/PCO2/PO2) como um item solto no nível de `blood_gases`
(shape de `ObservationCandidate`), em vez de agrupá-los sob um único
painel (`raw_specimen_type` + `observations: [...]`), que é a estrutura
exigida por `BloodGasCandidate`.

**(3) Campos de `ObservationCandidate` aplicados a
`MicrobiologyCandidate`/`DiagnosticStudyCandidate`.** O modelo generalizou
o único exemplo do prompt (um item de `general_labs`, com `raw_value`,
`raw_unit`, `raw_reference_range`, `canonical_hint`) para outros buckets
que não têm esses campos — `MicrobiologyCandidate` espera `raw_result`
(não `raw_value`) e não tem `raw_unit`/`raw_reference_range`/
`canonical_hint`; `DiagnosticStudyCandidate` espera `findings: [...]`
(não `raw_value`) e também não tem esses três campos. Os modelos Pydantic
estritos (`extra="forbid"`) corretamente rejeitaram os campos extras —
isso é o comportamento pretendido do contrato, não um bug do validador.

`extraction_warnings[]` também apareceu como lista de strings em vez de
objetos `ExtractionWarning` em algumas execuções.

## Por que isso não foi "corrigido" agora

Todas as três causas apontam para o mesmo problema: **o exemplo JSON no
prompt (`2.0b-prompt-001`) só demonstra a forma de um `general_labs`
item.** O modelo nunca alucinou um dado clínico nos casos observados — os
valores extraídos (`raw_name`/`raw_value`/`raw_result`/`evidence_text`)
estavam corretos onde chegaram a ser emitidos; o problema é estrutural
(forma do envelope), não de conteúdo.

A correção natural seria expandir o exemplo do prompt para cobrir pelo
menos um item de cada bucket (`microbiology`, `diagnostic_studies`,
`blood_gases`, `unmapped`, `extraction_warnings`) — isso pertence a uma
próxima versão do prompt (`2.0b-prompt-002` ou posterior), decidida por
um humano, não a este milestone. Alargar o schema Pydantic para aceitar
os campos extras enviados pelo modelo foi deliberadamente descartado
(item 31): isso deformaria o contrato para acomodar um erro de forma do
extrator, em vez de manter o contrato como a fonte de verdade contra a
qual o extrator é avaliado.

## O que já está provado funcionando

- Autenticação via proxy do Claude Code Cloud, sem `DEEPSEEK_API_KEY` e
  sem header `Authorization` manual (item 2A).
- `canonical_hint` nunca é autoridade — mesmo quando o modelo o preenche
  (ex. `"pH"`, `"D-dimer"`, `"Cultura de vigilância para ESBL"`), só
  `resolve_canonical_id(raw_name)` decide o `canonical_id`.
- Grounding: em todos os 4 casos SUCCESS, 100% dos itens ficaram
  `GROUNDED` (0 ungrounded, 0 ambíguo) — o texto que o modelo citou como
  evidência sempre existia literalmente no `raw_text`.
- Nenhuma falha de rede, nenhum `EMPTY_PROVIDER_RESPONSE`, nenhum JSON
  sintaticamente inválido nesta execução — o `response_format:
  json_object` da DeepSeek cumpriu sua garantia de JSON válido em 100%
  das respostas; o schema `ExamExtractionCandidate` é o que rejeitou 6/10.
