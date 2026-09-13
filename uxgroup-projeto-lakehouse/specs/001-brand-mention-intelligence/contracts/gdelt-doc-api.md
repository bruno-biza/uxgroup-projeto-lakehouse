# Contrato — GDELT DOC 2.0 API

**Status**: parâmetros e operadores **CONFIRMADOS** na documentação oficial
([fonte](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)). Limite de requisições
**PARCIAL** — GDELT não publica o número.

Base: `https://api.gdeltproject.org/api/v2/doc/doc`

## Contrato de saída do cliente do projeto

```python
class GdeltRequest(BaseModel):
    query: str              # operadores vão AQUI DENTRO, nunca como parâmetro próprio
    mode: Literal["ArtList", "TimelineVolRaw", "TimelineVol", "TimelineTone"]
    format: Literal["json"] = "json"
    startdatetime: str      # YYYYMMDDHHMMSS — obrigatoriamente dentro dos últimos 3 meses
    enddatetime: str
    maxrecords: int = 250   # teto rígido da API; só vale para ArtList

class GdeltResponse(BaseModel):
    request_hash: str
    raw_body: str           # gravado antes de qualquer parse — Princípio III
    http_status: int
    attempts: int
    truncated_at_max: bool  # len(articles) == 250 → o dia precisa ser fatiado
```

## Modos usados e por quê

| Modo | Uso | Limitação confirmada |
|------|-----|---------------------|
| `ArtList` | Menções individuais (US3): `url`, `title`, `domain`, `language`, `sourcecountry`, `seendate` | **250 por chamada, sem paginação** |
| `TimelineVolRaw` | Contagem real por dia — numerador e denominador do SoV | Sem teto de 250 |
| `TimelineVol` | Volume normalizado pela cobertura total (percentual) | É a normalização do próprio GDELT — o nome da métrica precisa dizer isso (FR-020a) |
| `TimelineTone` | Tom médio por dia (US9) | Sinal aproximado (FR-021) |

## Construção da query por camada de identificação

| Camada | Padrão | Exemplo |
|--------|--------|---------|
| 1 — âncora de domínio | `"<dominio>"` | `"reals.bet.br"` |
| 2 — nome único | frase exata | `"brazino777"` |
| 3 — ambíguo com contexto | `near<N>:"..."` + exclusões | `near20:"reals aposta" -domain:<veiculos_excluidos>` |
| Categoria (denominador) | união taxonomia + lista de termos | `(theme:... OR "casa de apostas" OR ...)` |
| Recorte Brasil | `sourcecountry:brazil` | Também constrói `dim_outlet` (D9) |

## Invariantes que viram teste (Princípio II)

1. Toda requisição carrega `User-Agent` com nome do projeto e contato.
   **Imitar navegador é proibido** — teste falha se o UA contiver `Mozilla`.
2. Duas requisições idênticas ⇒ **exatamente uma** ida à rede (cache por `request_hash`).
3. Intervalo mínimo de **5 s** entre requisições, em série.
4. `429`/`5xx` ⇒ backoff exponencial com jitter, teto de tentativas, e então falha limpa.
5. Limite de requisições por execução lido de config; ao atingir, a execução para.
6. `truncated_at_max = true` ⇒ o dia é fatiado em subjanelas e reconsultado.

## Reconciliação FR-023

Para cada `(marca, dia)`: `count(ArtList)` vs `TimelineVolRaw`. A diferença é **gravada e
publicada**, não corrigida silenciosamente. É o que torna a limitação da API auditável em vez de
invisível.

## Licença e atribuição (Princípio XII)

Uso irrestrito, sem custo, para fins acadêmicos, comerciais ou governamentais. Exige citação ao
GDELT Project e link para `https://www.gdeltproject.org/` — ambos no README e no rodapé do dbt docs.
