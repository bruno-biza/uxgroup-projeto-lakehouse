# Contrato — Identificador de Marca

O núcleo técnico do projeto e o entregável que sustenta toda métrica (Princípio IV).

## Interface

```python
class BrandIdentification(BaseModel):
    brand_id: str
    layer: Literal[1, 2, 3, 4]      # camada que decidiu
    method: str                      # sinal legível: "dominio_canonico", "near20+contexto", ...
    confidence: float                # 0–1
    above_floor: bool                # confidence >= CONFIG.confidence_floor
    floor_version: str

def identify(content: Content, registry: BrandRegistry) -> list[BrandIdentification]:
    """Aplica as camadas em ordem de confiança decrescente.

    Para em quanto uma camada decide. A camada que decidiu é gravada, porque a
    precisão é medida POR CAMADA — é isso que permite dizer qual regra está errada
    quando o número cai, em vez de só saber que caiu.
    """
```

## As quatro camadas

### Camada 1 — âncora de domínio (confiança máxima)

Domínio oficial `.bet.br` no conteúdo ou na URL do artigo. Praticamente sem falso positivo.
Validada pelo fato confirmado de que **desde 01/01/2025 toda operadora autorizada no Brasil usa
`.bet.br`** ([SPA/MF](https://www.gov.br/fazenda/pt-br/composicao/orgaos/secretaria-de-premios-e-apostas)).

### Camada 2 — nome único

Frase exata para nomes de baixa ambiguidade: **Brazino777**, **Superbet**.

### Camada 3 — nome ambíguo com contexto

Coocorrência com termos da categoria em janela de proximidade **mais** lista de exclusão. Cada caso
é tratado nominalmente e cada um vira estrato do conjunto de avaliação:

| Marca | Colide com | Estratégia |
|-------|-----------|------------|
| **Reals** | moeda ("reais"), clubes de futebol | Proximidade com termos do setor + exclusão de contexto financeiro e esportivo-clubístico |
| **Bingo** | o jogo, uso coloquial ("bingo!") | Exclusão de contexto de jogo genérico e de interjeição |
| **Esportiva** | expressão "aposta esportiva", **nome de veículo de imprensa** | Exclusão da expressão como sequência; exclusão de veículos cujo nome contenha a palavra — a menção **pelo** veículo não é menção **à** marca |
| **BetGO** | termos e siglas genéricos | Frase exata + proximidade com termos do setor |
| **KTO** | siglas genéricas | Frase exata + proximidade; sigla curta exige contexto mais forte |

### Camada 4 — desambiguação assistida por modelo

**Apenas** para o que as camadas 1–3 deixam indefinido. Saída validada contra esquema estrito;
confiança baixa vai para fila de revisão humana. Só entra em produção se superar a linha de base
por regras no conjunto de avaliação, com o ganho publicado em número (Princípio XIII).

## Contrato do avaliador

```python
def evaluate(identifier_version: str) -> EvaluationReport:
    """precision, recall e F1 por marca E por camada, contra o conjunto rotulado.

    Por camada, não só no agregado: uma precisão agregada de 90% pode esconder
    uma Camada 3 a 60% compensada por uma Camada 1 a 100%.
    """
```

## Invariantes que viram teste

1. Toda menção contabilizada tem `layer`, `method` e `confidence` gravados (FR-004).
2. **Piso de confiança único** para todas as marcas — piso por marca é proibido, porque tornaria os
   denominadores do SoV não comparáveis (FR-004a).
3. Menções abaixo do piso são preservadas e consultáveis, nunca apagadas (FR-004c).
4. A precisão é medida sobre **a mesma população** que alimenta as métricas: apenas acima do piso.
5. **Regressão de precisão em qualquer marca reprova a suíte** (Princípio IV).
6. Meta: ≥ 85% de precisão para Reals, Bingo, Esportiva, BetGO e KTO (SC-005).
7. Nenhuma métrica de negócio é publicada sem a precisão vigente documentada (FR-007).

## Saída publicada

`docs/evaluation_report.md`, gerado automaticamente, publicado junto do dbt docs, com precisão,
revocação e F1 por marca e por camada, a versão do identificador, a versão do conjunto de avaliação
e a data da medição. **É o principal artefato da apresentação.**
