# CLAUDE.md

## Contexto do projeto

Este repositório é o Milestone 1 do projeto Prompt Evolução Médica.

O objetivo desta etapa NÃO é integrar IA, OCR, APIs externas, banco de dados ou frontend.

O objetivo é provar deterministicamente:

```text
Medical State válido
→ Template Profile
→ Renderer
→ documento final reproduzível
```

## Restrições obrigatórias

1. Não alterar a arquitetura sem explicar explicitamente a razão.
2. Não adicionar IA nesta etapa.
3. Não remover proveniência ou estados de validação.
4. Não transformar texto gerado em fonte clínica primária.
5. Não inserir dados clínicos que não existam no Golden Sample.
6. O Golden Sample é desidentificado e deve permanecer assim.
7. Não substituir testes de igualdade exata por testes mais frouxos apenas para fazê-los passar.
8. Corrigir o código quando o teste falhar; não degradar o teste sem justificativa.

## Primeiro objetivo

Execute:

```bash
python -m venv .venv
```

Ative o ambiente, instale `requirements.txt` e rode:

```bash
pytest -q
```

Depois rode:

```bash
python render_golden_001.py
```

Verifique se o renderer produz o arquivo esperado.

## Próxima tarefa após testes verdes

Faça uma revisão técnica do Milestone 1 e entregue:

1. bugs encontrados;
2. inconsistências entre schema e renderer;
3. pontos onde o schema está permissivo demais;
4. riscos de acoplamento;
5. sugestões pequenas e incrementais;
6. NÃO implemente alterações arquiteturais grandes sem aprovação.

## Critério de conclusão

`pytest -q` deve permanecer verde.
