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
4 passed
```

## Estrutura

```text
medical-evolution-milestone1/
├── models/
│   └── medical_state.py
├── templates/
│   └── uti_hospitalis_v1.py
├── rendering/
│   └── medical_note_renderer.py
├── golden_samples/
│   └── golden_001/
│       ├── golden_001_state.json
│       └── golden_001_expected.txt
├── tests/
│   └── test_golden_001.py
├── render_golden_001.py
├── requirements.txt
└── README.md
```

## Regra arquitetural

Não conectar APIs de IA neste milestone.

O objetivo desta fase é validar apenas:

1. schema;
2. normalização estrutural;
3. template;
4. renderer;
5. teste Golden.

Quando este núcleo estiver estável, a próxima etapa será adicionar FastAPI e, depois, os módulos de IA.
