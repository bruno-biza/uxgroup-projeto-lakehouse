# ADR 0004: Duas fontes GDELT complementares

**Data**: 2026-09-08
**Status**: aceita

## Contexto

A verificação na documentação oficial, feita **antes** de qualquer código, revelou dois limites
que decidem a arquitetura:

1. A [DOC 2.0 API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) cobre uma **janela
   móvel de 3 meses** — `startdatetime` e `enddatetime` precisam cair dentro dela.
2. `maxrecords` tem teto de **250** e a API **não tem parâmetro de paginação ou offset**.

A spec exige janela ativa de 3 meses (SC-001) **e** linha de base histórica de pelo menos
12 meses (SC-002) **e** corpus de ≥ 10 M linhas na camada bruta (SC-003). O primeiro limite
torna SC-002 impossível pela API; o segundo torna SC-003 impossível por ela.

## Decisão

Usar as duas fontes, cada uma para o que só ela alcança.

| Necessidade | Fonte | Motivo |
|-------------|-------|--------|
| Menções individuais da janela ativa | DOC 2.0 `ArtList` | Único caminho para veículo, título, idioma e país por artigo |
| Contagem por marca e denominador da categoria | DOC 2.0 `TimelineVolRaw` | Contagem real de artigos, sem sofrer o teto de 250 |
| Indicador de tom por dia | DOC 2.0 `TimelineTone` | Sinal fornecido pela fonte |
| Linha de base de 12 meses | BigQuery `gkg_partitioned` | A DOC 2.0 não alcança 12 meses |
| Corpus de ≥ 10 M linhas | BigQuery `gkg_partitioned` | 250 registros por chamada nunca chegariam lá |

## Alternativas descartadas

| Alternativa | Por que foi descartada |
|-------------|------------------------|
| Somente DOC 2.0 | Janela de 3 meses inviabiliza SC-002, e o teto de 250 inviabiliza SC-003 |
| Somente BigQuery | Custa bytes para a janela recente que a API entrega de graça, e o GKG não traz país da fonte, necessário ao recorte Brasil |
| Arquivos brutos do GDELT em S3 | Volume de download incompatível com notebook pessoal e com o prazo |

## Consequências

- Duas mecânicas de ingestão e dois formatos de landing: JSON em MongoDB, Parquet em MinIO.
- **FR-023 precisou ser reescrito**: como a enumeração exaustiva nem sempre é possível, a
  exigência passou a ser reconciliar `ArtList` contra `TimelineVolRaw` e **publicar a diferença**.
  Limitação medida é melhor que limitação escondida.
- **SC-006 precisou separar** ciclo diário de carga inicial: 630 requisições a 5 s são ~53 min,
  incompatíveis com o SLA de 20 minutos.
- O GKG **não tem país da fonte** — apenas o domínio em `V2SourceCommonName`. `dim_outlet` passa
  a ser construída via `sourcecountry:brazil` da DOC API, que usa a classificação do próprio
  GDELT e custa zero byte de BigQuery.
