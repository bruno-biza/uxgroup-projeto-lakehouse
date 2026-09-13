# Contrato — Componentes de IA

Dois usos, ambos sujeitos ao Princípio XIII: cache, prompt versionado, determinismo por entrada,
auditabilidade e **fallback determinístico obrigatório**.

## Regra que vale para os dois

```python
class AIResult(BaseModel):
    output: dict            # validado contra esquema estrito — nunca texto livre
    prompt_version: str
    input_hash: str
    used_fallback: bool
    schema_valid: bool
    created_at: datetime
```

1. **Cache por `input_hash`**: mesma entrada ⇒ mesma saída, sem nova chamada. Sem isso o
   Princípio IX (idempotência) e o Princípio III (reconstrução offline) quebram.
2. **Prompt versionado** em `src/ai/prompts/`, com a versão gravada em toda saída.
3. **Saída validada contra esquema estrito**; saída inválida cai no fallback.
4. **Fallback determinístico por regras é o que roda na suíte de testes.** Não é degradação: é o
   modo padrão de teste. Garante que a suíte roda offline e que a demo sobrevive ao fim da cota.
5. **Custo zero**: exclusivamente camada gratuita ou execução local.

## Componente 1 — Desambiguação de menção (Camada 4)

**Entrada**: título, veículo e contexto de um candidato que as Camadas 1–3 não resolveram.
**Saída**: `{"is_brand": bool, "confidence": float, "reason": str}`.

- Confiança baixa ⇒ **fila de revisão humana**, não decisão automática.
- **Portão de produção**: só entra se superar a linha de base por regras no conjunto de avaliação,
  com o ganho documentado em números. Sem ganho comprovado, não entra — e isso também é um
  resultado publicável.
- Fallback: decisão por regras (a própria Camada 3 com limiar mais conservador).

## Componente 2 — Explicador de anomalia

**Entrada**: uma anomalia detectada e as menções daquele dia.
**Saída**: `{"hypothesis": str, "supporting_mention_ids": [str], "status": "nao_verificada"}`.

- Gravado **sempre** com rótulo de hipótese não verificada e status de revisão (FR-028).
- **Nunca apresentado como fato. Nunca alimenta outra métrica.** Não existe caminho de linhagem
  saindo da hipótese para qualquer fato ou dimensão — isso é verificável no grafo do dbt.
- Fallback: resumo determinístico por regras — os N veículos e títulos mais frequentes do dia,
  sem interpretação.

## Testes

| Teste | Verifica |
|-------|----------|
| Suíte inteira com `used_fallback=True` | Nenhuma chamada de modelo é necessária para testar |
| Mesma entrada 2× ⇒ 1 chamada | Cache funciona |
| Saída fora do esquema ⇒ fallback | Validação estrita |
| Prompt alterado ⇒ nova `prompt_version` | Rastreabilidade |
| Hipótese não tem aresta de saída na linhagem | Não alimenta métrica |
| Relatório compara IA × linha de base por regras | Portão de produção |
