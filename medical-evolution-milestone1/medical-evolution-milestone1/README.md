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
33 passed
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
│   └── golden_001/
│       ├── golden_001_state.json
│       └── golden_001_expected.txt
├── docs/
│   └── render_contract_v0_1.md
├── tests/
│   ├── test_golden_001.py
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

## Regra arquitetural

Não conectar APIs de IA neste milestone.

O objetivo desta fase é validar apenas:

1. schema;
2. normalização estrutural;
3. template;
4. renderer;
5. teste Golden.

Quando este núcleo estiver estável, a próxima etapa será adicionar FastAPI e, depois, os módulos de IA.
