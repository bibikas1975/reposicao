# Reposição — Planeador Diário de Tarefas (resolução 15 min)

Projeto simples para gerar horários diários alocando tarefas a funcionários com base em turnos, usando um otimizador (CP‑SAT / OR‑Tools).

## Principais funcionalidades
- Carrega dados de funcionários e tarefas a partir de ficheiros TOML.
- Executa um otimizador (TaskOptimizer) para construir um horário.
- Gera um ficheiro de saída com o horário (horario_segunda.txt).

## Requisitos
- Python 3.11+ (recomendado, inclui tomllib)
  - Se usar Python < 3.11, instale tomli.
- OR‑Tools (para CP‑SAT)
- Outras dependências conforme persistence/loader e optimizer (ver exemplos abaixo).

## Instalação rápida
1. Criar um ambiente virtual (recomendado):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   .venv\Scripts\activate     # Windows
   ```

2. Instalar dependências:
   ```bash
   pip install ortools tomli
   ```

(Se preferir, crie um requirements.txt com "ortools" e "tomli" e use `pip install -r requirements.txt`.)

## Como executar
- O script principal é `main_optimizer.py`. Atualmente usa os ficheiros e o dia hardcoded:
  - Turnos: `turnos.toml`
  - Tarefas: `tarefas.toml`
  - Dia: "segunda"
  - Saída: `horario_segunda.txt`

Executar:
```
python main_optimizer.py
```

## Saída
- Em caso de sucesso, imprime o horário no terminal e grava em `horario_segunda.txt`.

## Formato esperado dos ficheiros TOML
A estrutura abaixo é um exemplo orientador. Ajuste conforme os campos concretos usados por `persistence/loader` do projecto.

Exemplo: `turnos.toml`
```toml
# turnos.toml
[[employees]]
id = "e1"
name = "Ana"
# turnos associados ao dia (ex.: "segunda")
shifts = [
  { start = "08:00", end = "12:00" },
  { start = "13:00", end = "17:00" }
]

[[employees]]
id = "e2"
name = "Bruno"
shifts = [
  { start = "09:00", end = "14:00" }
]
```

Exemplo: `tarefas.toml`
```toml
# tarefas.toml
[[tasks]]
id = "t1"
name = "Reposição prateleira A"
duration_min = 30
earliest_start = "08:00"
latest_end = "17:00"
# outros campos esperados pelo optimizer (prioridade, skills, etc.)

[[tasks]]
id = "t2"
name = "Limpeza zona B"
duration_min = 45
earliest_start = "09:00"
latest_end = "16:00"
```

## Notas importantes e recomendações
- Compatibilidade tomllib/tomli:
  - Python 3.11+ já inclui tomllib (recomendado).
  - Para Python inferiores, instale tomli e ajuste o loader se necessário.
- Robustez:
  - O script atual faz tratamento genérico de exceções ao carregar TOML; recomenda‑se validar e tratar erros mais específicos (FileNotFoundError, parse errors).
- Flexibilidade:
  - Hoje o dia e nomes de ficheiros estão hardcoded. Recomenda‑se adicionar argparse para permitir parâmetros CLI (`--day`, `--turnos`, `--tarefas`, `--out`) e expor parâmetros do solver (time_limit, workers).
- Logging:
  - Substituir prints por logging para melhor controlo em ambientes de produção.

## Sugestões para evolução
- Adicionar um README mais detalhado com exemplos reais de TOML e casos de teste.
- Expor configurações do solver (limites de tempo, paralelismo).
- Adicionar testes unitários para loader e pequenas instâncias do optimizer.
- Criar um requirements.txt e CI (linting, format, testes).

## Contribuição
- Fork -> branch -> PR. Descreva claramente alterações (ex.: adicionar CLI, melhorar validação de ficheiros, adicionar exemplos).

## Licença
- Especifique a licença do projecto (ex.: MIT) criando um ficheiro LICENSE na raiz do repositório.

Obrigado — se quiser, posso:
- Gerar um README mais extenso em inglês/português combinado;
- Criar um requirements.txt sugerido;
- Implementar argparse + logging e preparar um patch/PR (diga se quer que eu escreva o patch).