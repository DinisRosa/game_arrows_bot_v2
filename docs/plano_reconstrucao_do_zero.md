# Plano de Reconstrução do Auto-ARROWS — do Zero

> Este plano reaproveita o que já foi aprendido e validado na primeira
> versão do projeto (regras do jogo confirmadas, ordem de varrimento que
> funciona melhor, armadilhas já identificadas) para que não tenhas de
> redescobrir as mesmas coisas. O objetivo é uma sequência de passos
> **curtos, isolados e testáveis um a um** — cada passo tem um critério
> claro de "está pronto" antes de avançares para o seguinte, e cada passo
> só depende do anterior através de uma interface fixa, para que mexer no
> passo seguinte nunca obrigue a voltar a mexer no anterior.

---

## 0. Objetivo do projeto

Construir um programa que corre no PC e joga sozinho o jogo Android
**Arrows**, através da ligação USB/ADB ao telemóvel:

1. Vê o ecrã do telemóvel (captura).
2. Entende o tabuleiro (visão computacional → grelha simbólica).
3. Decide que setas pode remover (solver).
4. Toca no ecrã (atuação).
5. Repete até o nível estar completo, com deteção de erros e recuperação
   automática.

Não é um objetivo em si "usar a linguagem mais rápida possível" ou "usar
ML" — é um objetivo **de correção e depois de velocidade**, por esta
ordem. Já vimos na conversa anterior que a decisão de jogar (solver) não
beneficia de ML porque a regra do jogo é fechada e determinística; o valor
de reconstruir do zero está sobretudo em arquitetar melhor desde o início
a separação entre partes rápidas (I/O) e partes lentas (se algum dia
existirem), coisa que na v1 foi sendo descoberta por tentativa e erro.

---

## 1. Como funciona o jogo (mecânica já confirmada na v1)

- O tabuleiro é uma grelha de células. Algumas células têm uma **seta**
  com uma cabeça apontada numa de 4 direções (cima/baixo/esquerda/direita).
- As setas não ocupam necessariamente 1 célula reta — podem ter corpo
  tipo "cobra", ocupando várias células, possivelmente com curvas.
- **Regra de jogabilidade:** uma seta pode ser removida (tocada) se, a
  partir da sua cabeça e na direção que aponta, não houver nenhuma outra
  seta até à borda do tabuleiro.
- **Propriedade importante (já verificada no `solver.py` da v1):** remover
  uma seta **nunca pode bloquear outra** — só pode libertar espaço. Isto
  significa que não há sequências "erradas": jogar sempre o que está
  disponível, por qualquer ordem, resolve o tabuleiro se ele for
  solucionável. Não é preciso planear à frente nem fazer *lookahead*.
- Dois regimes de tabuleiro:
  - **Cabe no ecrã** — um único frame chega para ver tudo.
  - **Maior que o ecrã** — é preciso navegar (*pan*) e juntar vários
    frames num mapa global (*stitching*) antes de poder decidir jogadas
    com segurança.
- Zona de UI (barras superior/inferior) não faz parte do tabuleiro e deve
  ser sempre excluída da deteção.

---

## 2. Princípios de arquitetura a levar desde o dia 1

Estes princípios existem precisamente para responder à tua preocupação de
"o passo B não estragar o passo A":

1. **Camadas com interfaces fixas, não implementações fixas.**
   - `FrameSource`: dá-te um frame (imagem BGR) e sabe dizer se está
     "fresco" ou não. Não interessa a quem usa isto *como* o frame foi
     obtido (screencap, scrcpy, o que for).
   - `Vision`: recebe um frame, devolve uma grelha simbólica (setas +
     direções + ocupação). Não sabe nada de ADB nem de toques.
   - `Solver`: recebe a grelha simbólica, devolve jogadas válidas. É
     **puro** — não toca em imagens, não toca em ADB. Pode ser testado
     com tabuleiros escritos à mão, sem telemóvel nenhum ligado.
   - `Actuator`: recebe uma jogada (linha, coluna), converte em
     coordenadas de ecrã e envia o toque. Não decide nada.
   - Trocar a implementação de uma camada (ex. `FrameSource` de
     `screencap` para `scrcpy`) nunca deve obrigar a tocar nas outras —
     é exatamente esta fronteira que faltava na v1 e que forçou a
     retrofitar o `USE_STREAM` mais tarde.

2. **Frescura explícita.** Qualquer `FrameSource` deve poder responder
   "não tenho a certeza que isto é atual" em vez de devolver
   silenciosamente um frame antigo. Isto evita o bug do "frozen frame"
   que a v1 só apanhou depois de já estar em produção.

3. **Segurança > velocidade sempre que houver dúvida.** Célula
   desconhecida bloqueia a jogada, tal como na v1.

4. **Modo de simulação (*dry-run*) desde o primeiro dia** do loop de jogo
   — decidir jogadas sem enviar toques reais, para testar o raciocínio
   sem arriscar penalizações no jogo.

5. **Tudo o que não precisa do telemóvel, testa-se sem o telemóvel.**
   Guarda frames de exemplo em disco (`fixtures/`) desde o passo 2. A
   visão e o solver devem correr sobre esses ficheiros nos testes, não
   sobre uma ligação ADB ao vivo — isto é o que te permite mexer no passo
   5 sem arriscar partir o passo 3.

---

## 3. Ordem de construção — visão geral e porquê

Respondendo diretamente à tua dúvida ("grelhas primeiro ou stitching
primeiro?"): **grelhas (deteção num único frame) sempre primeiro.**
Stitching não é uma etapa paralela à deteção de grelha — é *literalmente*
"aplicar a deteção de grelha a vários frames e depois fundir os
resultados". Não é possível construir o stitching sem já teres a deteção
de 1 frame a funcionar bem, porque é o bloco que se repete lá dentro. A
ordem correta é:

```
Ambiente/ligação
   ↓
Captura de 1 frame (fiável, nem que seja lenta)
   ↓
Deteção de grelha + setas NUM frame        ← aqui só entra 1 imagem
   ↓
Solver (puro, offline)                     ← pode ser feito em paralelo
   ↓
Loop de jogo para tabuleiros que cabem no ecrã   ← primeiro bot "a sério"
   ↓
Stitching (multi-frame → mapa global)      ← só faz sentido aqui
   ↓
Loop de jogo para tabuleiros gigantes (stitching + sincronização)
   ↓
Robustez / recuperação automática
   ↓
Otimização de velocidade (troca de FrameSource, batch de toques)
   ↓
Medir e só depois decidir sobre mudar de linguagem
```

---

## Fase 1 — Ambiente e ligação

**Objetivo:** confirmar que consegues falar com o telemóvel.

**O que fazer:**
- Instalar ADB (Android Platform Tools).
- Ativar Depuração USB no telemóvel, autorizar o PC.
- `adb devices` → deve mostrar o dispositivo com estado `device`.
- `adb shell wm size` → anota a resolução (precisas dela mais à frente).

**Critério de aceitação:** `adb devices` mostra o telemóvel autorizado, de
forma repetível (desliga e liga o cabo, confirma que volta a aparecer).

**Isolamento:** nenhum código Python ainda. Isto é só ferramentas de
sistema — nada aqui pode ser "estragado" por passos futuros.

---

## Fase 2 — Captura de um frame (fiável antes de rápida)

**Objetivo:** ter uma função `get_frame() -> np.ndarray` que funciona
sempre, mesmo que lenta.

**O que fazer:**
- Implementar só com `adb exec-out screencap -p`, exatamente como na v1.
  Não uses scrcpy já aqui — a prioridade deste passo é **correção**, não
  velocidade. A troca por algo mais rápido acontece isolada, na Fase 9.
- Define já a interface como uma classe/protocolo simples, por exemplo:
  ```python
  class FrameSource(Protocol):
      def get_frame(self) -> np.ndarray: ...
      def is_fresh(self) -> bool: ...   # screencap: sempre True
  ```
- Guarda 5–10 screenshots reais em `fixtures/frames/` (tabuleiros
  diferentes, incluindo um "cabe no ecrã" e um "maior que o ecrã").

**Critério de aceitação:** consegues chamar `get_frame()` 20 vezes
seguidas sem falhas e sem frames corrompidos, e tens os `fixtures/`
guardados.

**Isolamento:** a partir daqui, **todos os passos seguintes de visão e
solver podem correr só com os ficheiros em `fixtures/`, sem o telemóvel
ligado.** Isso é o que te vai permitir trabalhar nos próximos passos sem
depender de teres sempre o telemóvel à mão.

---

## Fase 3 — Deteção de grelha e setas num único frame

**Objetivo:** transformar 1 imagem numa grelha simbólica: células vazias,
ocupadas, e cabeças de seta com direção.

**O que fazer:**
- Começa pela abordagem mais simples possível: grelha fixa definida à
  mão (linhas/colunas e limites do tabuleiro anotados manualmente num dos
  `fixtures/`), só para validar a pipeline de classificação de células.
- Só depois avança para deteção automática da grelha (posição dos pontos,
  espaçamento entre células) — a v1 já validou que autocorrelação sobre
  as posições dos pontos funciona bem para encontrar o espaçamento da
  grelha; não precisas de reinventar essa parte do zero, só reimplementar
  com calma.
- Trata a deteção da cabeça e da direção da seta como uma função à parte
  da deteção da grelha — mais fácil de testar isoladamente.

**Critério de aceitação:** para cada imagem em `fixtures/frames/`,
consegues gerar uma grelha simbólica e confirmar visualmente (desenhando
a grelha + setas detetadas sobre a imagem) que bate certo, incluindo nos
casos com setas "cobra".

**Isolamento:** este passo só lê ficheiros de `fixtures/`. Nada aqui
depende do solver nem de ADB. Podes correr um teste automático que compara
a deteção com um resultado esperado gravado à mão para 2–3 `fixtures`.

---

## Fase 4 — Solver (pode ser feito em paralelo com a Fase 3)

**Objetivo:** função pura `playable_moves(grid, heads) -> list[move]`.

**O que fazer:**
- Implementar a regra: seta jogável = linha reta da cabeça até à borda
  sem outra seta nem célula desconhecida no caminho.
- Testar com tabuleiros **escritos à mão em código/JSON**, não com
  imagens — isto é propositadamente o passo mais isolado de todo o plano.

**Critério de aceitação:** um pequeno conjunto de tabuleiros de teste
(incluindo casos com 0 jogadas, 1 jogada, tabuleiro totalmente resolúvel)
passa com o resultado esperado.

**Isolamento:** zero dependências de imagem, ADB ou I/O. Podes mexer
nisto à vontade sem nunca poderes partir a Fase 2 ou 3, e vice-versa.

---

## Fase 5 — Loop de jogo para tabuleiros que cabem no ecrã

**Objetivo:** o primeiro bot "a jogar a sério", limitado a níveis simples
(sem stitching).

**O que fazer:**
- Juntar Fase 2 (frame) → Fase 3 (grelha) → Fase 4 (jogadas) → converter
  `(linha, coluna)` em coordenadas de ecrã → enviar toque → aguardar →
  repetir.
- Modo `dry-run` primeiro (imprime a jogada em vez de tocar), só depois
  liga os toques reais.
- Deteção simples de "nível terminado" (sem cabeças de seta na grelha).

**Critério de aceitação:** resolve, sozinho e do início ao fim, pelo
menos 3 níveis reais que cabem no ecrã, sem intervenção manual.

**Isolamento:** este é o primeiro ponto onde juntas tudo — é normal que
aqui apareçam bugs de integração. Mas nota que se um bug aparecer, sabes
exatamente em que camada procurar primeiro (testa a Fase 3 e a Fase 4
outra vez isoladamente com os `fixtures` desse nível específico, antes de
mexer na Fase 5).

---

## Fase 6 — Stitching: juntar vários frames num mapa global

**Objetivo:** reconstruir um tabuleiro maior que o ecrã, aplicando a
deteção da Fase 3 a vários frames e fundindo-os num mapa único.

**Ordem de varrimento — resposta direta à tua dúvida sobre centro vs.
canto:** começa logo por **centro para fora** (*center-out*), não por um
canto. Isto já foi comparado na prática na v1: varrer a partir de um
canto superior esquerdo precisava de 25–40 passos (deslize + captura +
deteção) para cobrir um tabuleiro grande; varrer a partir do centro, em
"braços" (cima, baixo, esquerda, direita, depois diagonais) com paragem
antecipada assim que as setas todas já foram vistas, reduziu isto para
4–8 passos. Não há razão para voltar a testar a versão por canto — seria
repetir um passo cujo resultado já se conhece.

**O que fazer:**
- Alinhar frames consecutivos por *template matching* (encontrar o
  deslocamento em pixels entre dois frames sobrepostos).
- Fundir as grelhas locais de cada frame numa grelha global, usando o
  deslocamento acumulado.
- Parar cedo assim que o número de cabeças de seta esperado já foi
  encontrado (evita varrer área vazia desnecessariamente).

**Critério de aceitação:** para 2–3 tabuleiros grandes gravados em
`fixtures/` (sequências de frames com deslocamento conhecido), o mapa
global reconstruído bate certo com o que se vê a olho.

**Isolamento:** o stitching usa a Fase 3 (deteção por frame) como uma
caixa preta — se a Fase 3 estiver bem testada e estável, mexer no
algoritmo de fusão (Fase 6) não deve exigir voltar a mexer na deteção por
frame.

---

## Fase 7 — Loop de jogo para tabuleiros gigantes

**Objetivo:** juntar Fase 5 + Fase 6: jogar tabuleiros que precisam de
stitching, incluindo sincronizar a vista ao vivo com o mapa global
(saber a que célula do mapa corresponde o centro do ecrã neste momento).

**Critério de aceitação:** resolve pelo menos 1 nível "gigante" do
início ao fim.

---

## Fase 8 — Robustez e recuperação automática

**Objetivo:** o bot não deve ficar preso quando algo correr mal.

**O que fazer (lições já documentadas na v1, vale a pena trazê-las já
para a arquitetura desde este ponto):**
- Verificar estabilidade da imagem antes de agir (duas capturas seguidas
  iguais) para não decidir com base numa animação a meio.
- Se não houver jogadas válidas mas ainda houver setas visíveis →
  reconhecer inconsistência entre o mapa mental e a realidade, limpar o
  estado e refazer o stitching do zero em vez de insistir num mapa
  errado.
- Limite máximo de jogadas/tentativas antes de parar e avisar, em vez de
  ciclar para sempre.

**Critério de aceitação:** provocar deliberadamente uma dessincronização
(ex. mexer manualmente no telemóvel a meio de uma run) e confirmar que o
bot se recupera sozinho, em vez de travar ou tocar às cegas.

---

## Fase 9 — Otimizar a captura (aqui entra o scrcpy-server)

**Objetivo:** trocar só a implementação de `FrameSource`, sem tocar em
mais nada, por uma opção mais rápida — e só agora, porque só agora tens
uma baseline correta para comparar.

**Melhor forma de usar o scrcpy-server, concretamente:**

Não precisas de reimplementar o protocolo do scrcpy à mão (é o que a v1
tentou fazer de forma artesanal com `screenrecord`+FIFO, e foi aí que
apareceu o bug do "frozen frame"). Existe uma biblioteca Python madura
que já faz exatamente isto — `py-scrcpy-client` (pacote `scrcpy-client`
no PyPI). Ela:
- Envia o `scrcpy-server.jar` para o telemóvel via ADB e corre-o lá.
- Liga-se ao socket local que o servidor expõe e descodifica o H.264
  já por ti (usa `av`/PyAV por baixo).
- Expõe um modelo de eventos: registas um *callback* `on_frame(frame)`
  que recebe sempre o frame mais recente (ou, em modo *threaded*, um
  `client.last_frame` sempre atualizado em segundo plano) — ou seja, o
  problema do "drenar o buffer manualmente" que a v1 teve de resolver à
  mão já vem resolvido de fábrica.
- Também expõe `client.control` para enviar toques/gestos diretamente
  pelo mesmo canal, o que pode vir a ser uma segunda otimização (ver
  nota abaixo), independente da captura.

**Como integrar sem arriscar as fases anteriores:**
```python
class ScrcpyFrameSource:
    def __init__(self, device=None):
        self._client = scrcpy.Client(device=device)
        self._client.add_listener(scrcpy.EVENT_FRAME, self._on_frame)
        self._latest = None
        self._latest_ts = 0.0
        self._client.start(threaded=True)

    def _on_frame(self, frame):
        if frame is not None:
            self._latest = frame
            self._latest_ts = time.monotonic()

    def get_frame(self) -> np.ndarray:
        return self._latest

    def is_fresh(self, max_age: float = 0.2) -> bool:
        return self._latest is not None and (time.monotonic() - self._latest_ts) < max_age
```
Porque isto respeita a interface `FrameSource` definida na Fase 2, todas
as Fases 3 a 8 continuam a funcionar sem alterações — só trocas qual
`FrameSource` é passado ao loop principal. Se `is_fresh()` disser "não",
cai-se de volta ao `screencap` como *fallback* de segurança, tal como
planeado para o `USE_STREAM` na v1, mas desta vez com a fronteira certa
desde o início.

**Critério de aceitação:** o mesmo conjunto de tabuleiros de teste das
fases 5/7 continua a resolver corretamente (mesmo resultado que com
`screencap`), agora com tempo de stitching medido substancialmente mais
baixo.

**Nota sobre toques via scrcpy:** já tens no v1 o envio de toques via
shell ADB persistente com *batching* (<1 ms por lote), o que já é muito
rápido. Vale a pena medir se `client.control` do scrcpy traz alguma
diferença real antes de o adotares — pode não valer a complexidade extra
se o `tap_batch` já não for o gargalo.

---

## Fase 10 — Medir, só depois decidir sobre mudar de linguagem

Respondendo diretamente à tua pergunta sobre C# (ou outra linguagem mais
rápida): a abordagem correta é exatamente a que já sugeriste — **primeiro
Python, medir, e só portar se os números justificarem.**

**Como decidir com dados, não com intuição:**
1. Depois da Fase 9, instrumenta o loop principal com `time.perf_counter()`
   à volta de cada camada (`FrameSource`, `Vision`, `Solver`, `Actuator`).
2. Corre um conjunto de níveis de referência e regista quanto tempo cada
   camada consome, em percentagem do total.
3. **Só considera portar para outra linguagem a camada que continuar a
   dominar o tempo total depois da Fase 9.** Pela experiência da v1, é
   muito provável que continue a ser I/O (ADB/rede/USB) mesmo depois do
   scrcpy — nesse caso, nenhuma linguagem resolve isso, porque o limite
   está fora do teu código.
4. Se, e só se, a visão computacional ou o solver aparecerem a consumir
   uma fatia significativa (ex. >20% do tempo total) depois do passo 9,
   aí sim faz sentido portar **só essa camada** — graças à separação em
   interfaces da Fase 0, isso significa reescrever um módulo, não o
   projeto todo.
5. Sobre a escolha da linguagem, se chegares a este ponto: para
   visão computacional especificamente, C++ e Rust são as escolhas mais
   naturais no ecossistema (OpenCV nativo, sem custo de *binding*, muitas
   ferramentas de automação Android já existem nessas linguagens). C# é
   perfeitamente viável (existem `OpenCvSharp` e clientes ADB para .NET)
   mas é uma escolha menos comum neste nicho especificamente — se já
   souberes bem C#, isso pesa mais na prática do que a diferença teórica
   de performance entre linguagens compiladas, especialmente numa camada
   que, pelos números da v1, provavelmente nem vai ser a que precisa de
   ser portada.

**Critério de aceitação desta fase:** uma tabela de tempos por camada,
para pelo menos 5 execuções reais, que te diga com números — não com
suposição — se vale a pena avançar para uma reescrita parcial.

---

## Resumo da ordem final

```
1. Ambiente/ADB
2. Captura de 1 frame (screencap, correto antes de rápido)
3. Deteção de grelha + setas (1 frame)         ← "grelhas primeiro"
4. Solver puro (paralelo à Fase 3)
5. Bot para tabuleiros pequenos (primeira versão jogável)
6. Stitching (center-out, já validado)         ← "stitching depois"
7. Bot para tabuleiros gigantes
8. Robustez/recuperação
9. Troca de FrameSource para scrcpy-client
10. Medir → decidir se compensa portar para outra linguagem
```
