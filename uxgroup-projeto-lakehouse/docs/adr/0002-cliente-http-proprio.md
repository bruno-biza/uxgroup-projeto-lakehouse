# ADR 0002: Cliente HTTP próprio em vez do pacote `gdeltdoc`

**Data**: 2026-09-08
**Status**: aceita

## Contexto

Existe um cliente Python maduro para a DOC 2.0 API:
[`gdeltdoc`](https://github.com/alex9smith/gdelt-doc-api), versão 1.12.0, manutenção ativa e
publicação automatizada no PyPI. Reusar seria o instinto correto na maioria dos projetos.

O Princípio II (NÃO-NEGOCIÁVEL) exige, cumulativamente: User-Agent descritivo com identificação
do projeto e contato, backoff exponencial com jitter, teto de tentativas, timeout, limite
configurável de requisições por execução, requisições em série por padrão e cache local em disco.

O repositório do `gdeltdoc` tem
[issue aberta](https://github.com/alex9smith/gdelt-doc-api/issues/22) especificamente sobre o
tratamento da resposta de rate limit — que é o comportamento mais crítico para nós, já que o
GDELT não publica o número do seu limite.

## Decisão

Implementar cliente próprio fino sobre `requests`, usando o `gdeltdoc` apenas como **referência
de leitura** para a construção das URLs.

## Alternativas descartadas

| Alternativa | Por que foi descartada |
|-------------|------------------------|
| Adotar `gdeltdoc` diretamente | O conjunto de garantias do Princípio II é exatamente o que precisamos controlar; o comportamento sob rate limit do pacote não é confiável para o nosso caso |
| Adotar `gdeltdoc` atrás da interface abstrata do projeto | A abstração esconderia, mas não corrigiria, o comportamento sob rate limit — e é justamente o que mais importa contra um bem público |
| Contribuir a correção upstream | Custo de dias num prazo de 7. Fora de escopo, ainda que seja a coisa certa a fazer depois |

## Consequências

- ~200 linhas de código nosso, com teste dedicado para cada um dos seis invariantes do contrato.
- Controle total sobre o comportamento contra a fonte, que é um bem público mantido por um
  projeto sem fins lucrativos e cujo custo de servir é pago por terceiros.
- **O que piora**: perdemos atualizações futuras do pacote e assumimos a manutenção. Aceito
  porque a superfície da API que usamos é pequena — quatro modos e um punhado de operadores.
- O intervalo de 5 s entre requisições é **escolha conservadora nossa**, não número publicado
  pelo GDELT. Na ausência de limite oficial, a folga é responsabilidade de quem consome.
