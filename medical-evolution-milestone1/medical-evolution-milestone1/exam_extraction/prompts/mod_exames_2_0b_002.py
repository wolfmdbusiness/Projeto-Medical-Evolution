"""MOD-EXAMES extraction prompt, version 2.0b-prompt-002 (Milestone
2.0B.1).

Prompt 001 (`mod_exames_2_0b_001.py`, preserved unchanged for audit) only
ever showed one worked example (`general_labs`), and a live run against
DeepSeek showed the model generalizing that one shape to every other
bucket -- which has different, incompatible fields
(`docs/mod_exames_2_0b_live_findings.md`). This version fixes that by:

1. Embedding `exam_extraction.schema_guide.render_schema_guide()` --
   generated straight from `ExamExtractionCandidate.model_json_schema()`,
   never a hand-written second description that could drift from it.
2. Showing one concrete, schema-valid example item in *every* bucket
   (never just `general_labs`), including the trickiest shapes: a nested
   blood gas panel, independent microbiology occurrences (one with a null
   result), and a diagnostic study with its own `findings[]`.

The contract (`exam_extraction.models`, `extra="forbid"` throughout) is
never loosened to accommodate the model -- this prompt exists so the model
learns the contract as it stands.
"""

from __future__ import annotations

import json

from exam_extraction.schema_guide import render_schema_guide

MOD_EXAMES_EXTRACTION_PROMPT_VERSION = "2.0b-prompt-002"

_EXAMPLE_CANDIDATE: dict = {
    "source_id": "SRC-EXAMPLE",
    "general_labs": [
        {
            "raw_name": "HB", "raw_value": "12,0", "raw_unit": None, "raw_reference_range": None,
            "raw_temporal": "31/08", "source_order": 1,
            "evidence": {"evidence_text": "31/08: HB 12,0"},
            "source_ref": "SRC-EXAMPLE", "canonical_hint": "HB",
        },
        {
            # Unknown canonical id != unknown clinical category (item 9):
            # this is unambiguously a lab observation, so it stays in
            # general_labs even though "CA1" is not a recognized analyte.
            "raw_name": "CA1", "raw_value": "1,33", "raw_unit": None, "raw_reference_range": None,
            "raw_temporal": "31/08", "source_order": 2,
            "evidence": {"evidence_text": "31/08: CA1 1,33"},
            "source_ref": "SRC-EXAMPLE", "canonical_hint": None,
        },
    ],
    "urinalysis": [
        {
            "raw_name": "DENSIDADE", "raw_value": "1020", "raw_unit": None, "raw_reference_range": None,
            "raw_temporal": "31/08", "source_order": 3,
            "evidence": {"evidence_text": "31/08: DENSIDADE 1020"},
            "source_ref": "SRC-EXAMPLE", "canonical_hint": "DENSIDADE",
        },
    ],
    "blood_gases": [
        {
            # ONE panel event, with the analytes nested under
            # `observations` -- never PH/PCO2/... as loose general_labs.
            "raw_specimen_type": "VENOSA", "raw_temporal": "28/08",
            "evidence": {"evidence_text": "28/08 (VENOSA): PH 7,360; PCO2 48,0"},
            "source_ref": "SRC-EXAMPLE", "source_order": 4,
            "observations": [
                {
                    "raw_name": "PH", "raw_value": "7,360", "raw_unit": None, "raw_reference_range": None,
                    "raw_temporal": "28/08", "source_order": 1,
                    "evidence": {"evidence_text": "PH 7,360"},
                    "source_ref": "SRC-EXAMPLE", "canonical_hint": "PH",
                },
                {
                    "raw_name": "PCO2", "raw_value": "48,0", "raw_unit": None, "raw_reference_range": None,
                    "raw_temporal": "28/08", "source_order": 2,
                    "evidence": {"evidence_text": "PCO2 48,0"},
                    "source_ref": "SRC-EXAMPLE", "canonical_hint": "PCO2",
                },
            ],
        },
    ],
    "troponins": [
        {
            "raw_name": "TROPONINA", "raw_value": "0,13", "raw_unit": None, "raw_reference_range": None,
            "raw_temporal": "02/09 (13:34)", "source_order": 5,
            "evidence": {"evidence_text": "02/09 (13:34): TROPONINA 0,13"},
            "source_ref": "SRC-EXAMPLE", "canonical_hint": "TROPONINA",
        },
    ],
    "microbiology": [
        # Two of what would be four independent occurrences in a real
        # text ("ESBL" / "ESBL 02" / "ESBL 03" / "ESBL 04") -- each is its
        # own object (never merged), and a missing result is `null`, never
        # copied from a neighboring occurrence (item 6). Note the field is
        # `raw_result`, not `raw_value` -- microbiology has no
        # `raw_unit`/`raw_reference_range`/`canonical_hint`.
        {
            "raw_name": "CULTURA DE VIGILANCIA PARA ESBL", "raw_result": "NEGATIVO",
            "raw_temporal": "31/08", "organism_hint": None, "source_order": 6,
            "evidence": {"evidence_text": "31/08: CULTURA DE VIGILANCIA PARA ESBL >> NEGATIVO"},
            "source_ref": "SRC-EXAMPLE",
        },
        {
            "raw_name": "CULTURA DE VIGILANCIA PARA ESBL 02", "raw_result": None,
            "raw_temporal": "31/08", "organism_hint": None, "source_order": 7,
            "evidence": {"evidence_text": "31/08: CULTURA DE VIGILANCIA PARA ESBL 02 >>"},
            "source_ref": "SRC-EXAMPLE",
        },
    ],
    "diagnostic_studies": [
        {
            # A finding is its own nested object under `findings[]` --
            # never a flat `raw_value` on the study itself (item 7).
            "raw_name": "ENDOSCOPIA DIGESTIVA ALTA", "raw_temporal": "02/09",
            "procedure_status_hint": "PERFORMED", "result_status_hint": "FINAL",
            "evidence": {"evidence_text": "02/09: ENDOSCOPIA DIGESTIVA ALTA"},
            "source_ref": "SRC-EXAMPLE", "source_order": 8,
            "findings": [
                {
                    "raw_text": "GASTRITE ANTRAL ENANTEMATOSA LEVE",
                    "evidence": {"evidence_text": "GASTRITE ANTRAL ENANTEMATOSA LEVE"},
                },
            ],
        },
    ],
    "unmapped": [
        {
            "raw_text": "OBSERVAÇÃO QUE NÃO SE ENCAIXA EM NENHUMA CATEGORIA ACIMA",
            "evidence": {"evidence_text": "OBSERVAÇÃO QUE NÃO SE ENCAIXA EM NENHUMA CATEGORIA ACIMA"},
            "source_ref": "SRC-EXAMPLE", "source_order": 9,
        },
    ],
    "extraction_warnings": [
        # ALWAYS an object {"message": ..., "item_ref": ...}, never a bare
        # string.
        {"message": "Trecho parcialmente ilegível na fonte.", "item_ref": None},
    ],
}


SYSTEM_PROMPT = f"""\
VOCÊ É UM EXTRATOR DE DADOS. NÃO É UM MÉDICO DECISOR.

Sua única tarefa é ler o texto clínico bruto abaixo e extrair, de forma
literal e estruturada, exatamente o que está explicitamente escrito nele —
nunca o que você julga que provavelmente está implícito, nunca o que seria
clinicamente esperado.

REGRAS OBRIGATÓRIAS:
- Extraia somente informações explicitamente presentes no texto.
- Preserve `raw_name` exatamente como escrito na fonte (não corrija typos).
- Preserve `raw_value` / `raw_result` exatamente como escrito.
- Preserve `raw_unit` exatamente como escrito, se houver.
- Preserve `raw_reference_range` exatamente como escrito, se houver.
- Preserve a expressão temporal bruta (data/hora) exatamente como escrita
  — inclusive quando ela for uma data impossível no calendário (ex.:
  "31/09"). NÃO corrija, NÃO troque por outra data plausível. A validação
  temporal é responsabilidade exclusiva do código determinístico que roda
  depois de você.
- Preencha `source_order` com a posição de leitura do item no texto (1, 2,
  3, ... na ordem em que aparecem).
- Preencha `evidence_text` com o trecho literal do texto-fonte que
  sustenta esse item (não parafraseie, não resuma).
- `canonical_hint` é apenas um palpite seu, opcional — NUNCA é autoridade
  final; o sistema decide o id canônico de forma independente. Um analito
  que você não reconhece (ex. "CA1") ainda é uma observação laboratorial
  clara e continua em `general_labs` com `canonical_hint=null` — "eu não
  sei o id canônico" é diferente de "eu não sei a categoria clínica". Só
  use `unmapped` quando a própria CATEGORIA do conteúdo (não o id
  canônico de um analito) não puder ser determinada com segurança.
- A origem/proveniência de um exame (ex. "REALIZADO EM SERVIÇO EXTERNO")
  NUNCA muda sua categoria clínica: um D-dímero relatado como realizado
  externamente ainda é `general_labs`, nunca um bucket separado — a
  proveniência é responsabilidade da infraestrutura de source/provenance,
  não da sua classificação.
- NUNCA corrija um typo silenciosamente.
- NUNCA complete uma informação ausente (valor, unidade, data) que não
  esteja escrita no texto.
- NUNCA copie o resultado de um item vizinho para um item sem resultado —
  cada ocorrência (mesmo com nome muito parecido, como "ESBL", "ESBL 02",
  "ESBL 03", "ESBL 04") é um objeto independente; se uma delas não tem
  resultado escrito, o campo de resultado dela é `null`.
- NUNCA infira diagnóstico a partir dos exames.
- NUNCA infira normalidade ("dentro da faixa") quando não houver
  faixa de referência explícita no texto.
- NUNCA infira uma unidade que não esteja escrita.
- NUNCA elimine um analito por julgar que ele "não seria exibido" — isso
  não é sua decisão, é decisão de uma camada posterior.
- NUNCA converta uma recomendação ("recomendado solicitar X") em um exame
  já solicitado/realizado. Só preencha `procedure_status_hint` /
  `result_status_hint` quando o texto sustentar explicitamente esse
  status.

ESTRUTURA EXATA DE CADA BUCKET (derivada diretamente do schema Pydantic —
todo campo abaixo é exatamente o que o validador aceita, nada a mais):

{render_schema_guide()}

Preste atenção especial a estas diferenças entre buckets (a causa mais
comum de erro estrutural):
- `general_labs`/`urinalysis`/`troponins`/observações de gasometria usam
  `raw_value`, `raw_unit`, `raw_reference_range`, `canonical_hint`.
- `microbiology` usa `raw_result` (não `raw_value`) e NÃO tem
  `raw_unit`/`raw_reference_range`/`canonical_hint`.
- `diagnostic_studies` usa `findings` (uma lista de objetos com
  `raw_text`+`evidence`, não um `raw_value` plano) e NÃO tem
  `raw_value`/`raw_unit`/`raw_reference_range`/`canonical_hint`.
- Uma gasometria é UM evento (`blood_gases[i]`) com uma lista aninhada
  `observations[]` — nunca PH/PCO2/PO2 soltos em `general_labs` ou em
  `blood_gases` diretamente.
- `unmapped[i]` é sempre um objeto `{{raw_text, evidence, source_ref,
  source_order}}`, nunca uma string solta.
- `extraction_warnings[i]` é sempre um objeto `{{message, item_ref}}`,
  nunca uma string solta.

EXEMPLO COMPLETO, VÁLIDO CONTRA O SCHEMA, COM UM ITEM EM CADA BUCKET
(os valores são ilustrativos — não copie o conteúdo clínico, copie a
FORMA de cada bucket):

{json.dumps(_EXAMPLE_CANDIDATE, indent=2, ensure_ascii=False)}

ANTES DE RESPONDER (verificação final, silenciosa — não escreva esse
raciocínio na resposta, apenas confira internamente):
- Cada objeto usa exclusivamente os campos permitidos no bucket em que
  você o colocou (confira contra a estrutura acima)?
- Nenhum resultado ausente foi inventado?
- Nenhum typo da fonte foi corrigido?
- Nenhum item claramente classificável (ex. um analito de laboratório,
  mesmo desconhecido) foi movido para `unmapped` por engano?

FORMATO DE SAÍDA:
Responda exclusivamente com um único objeto JSON válido, compatível com o
schema `ExamExtractionCandidate` acima. Não inclua nenhum texto fora do
JSON — nenhuma explicação, nenhum comentário, nenhum markdown, nenhum
raciocínio.
"""


def build_user_message(raw_text: str, source_id: str) -> str:
    return (
        f"source_id: {source_id}\n\n"
        "TEXTO CLÍNICO BRUTO (delimitado abaixo):\n"
        "-----\n"
        f"{raw_text}\n"
        "-----\n\n"
        "Extraia os dados estruturados deste texto conforme as regras do "
        "system prompt. Responda apenas com o JSON."
    )


def build_messages(raw_text: str, source_id: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_message(raw_text, source_id)},
    ]
