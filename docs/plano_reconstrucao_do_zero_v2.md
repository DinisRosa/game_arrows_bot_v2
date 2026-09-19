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
   sobre uma ligação ADB ao vivo.

---

## 2a. Decisões da v1 a NÃO repetir

Isto é a resposta direta ao que pediste: reli o projeto todo à procura de
decisões que foram tomadas cedo, por conveniência de protótipo, e que
depois nunca mais foram reconsideradas — mesmo depois de o projeto crescer
para além do que essas decisões aguentavam bem. Nenhuma delas é
"vergonhosa" (são normais em qualquer protótipo que cresce), mas não faz
sentido levá-las para uma base que queres que seja forte desde o início.

### 1. A representação do tabuleiro ainda não tem "dono" por célula — herança direta de uma assunção inicial errada

Isto é o exemplo mais concreto e mais importante que encontrei. A
primeira versão da grelha assumia setas retas, de 1 célula. Foi corrigido
mais tarde para aceitar corpos tipo "cobra", com várias células e curvas
— mas essa correção foi feita **só na deteção visual** (reconhecer a
forma). Olhando para `build_occupancy` no `vision.py`, cada célula
continua a ser classificada só como `EMPTY` / `OCCUPIED` / `UNKNOWN`, sem
nenhuma noção de **a que seta pertence** cada célula ocupada. E o
`is_playable` do solver simplesmente para na primeira célula `OCCUPIED`
que encontra no caminho.

Isto levanta uma pergunta que a v1 nunca respondeu, porque a
representação nunca deu espaço para a fazer: **o que acontece se o corpo
de uma seta curvar de volta para a frente da sua própria cabeça?** Com a
representação atual, o solver via-a-ia marcar essa seta como bloqueada
pelo seu próprio corpo — o que pode estar certo (se o jogo realmente
funcionar assim) ou errado (se o jogo permitir uma seta "passar" pelo seu
próprio corpo ao sair). Não sei qual das duas é a regra real do jogo, e é
exatamente por isso que vale a pena decidir isto conscientemente na
reconstrução, em vez de herdar uma representação que nunca foi desenhada
para conseguir sequer fazer esta pergunta. **Recomendação:** desde o
início, cada célula ocupada devia guardar também a que seta pertence
(ex. um id em vez de um booleano), para que o solver possa, se for caso
disso, ignorar o próprio corpo de uma seta ao verificar se ela está livre.

### 2. Dois loops de jogo paralelos (`bot.py` vs. `play_grid.py`) — e uma autocrítica ao meu próprio plano anterior

A v1 tem duas implementações praticamente paralelas do mesmo ciclo
"captura → deteta → resolve → toca → repete": uma para tabuleiros que
cabem no ecrã, outra para tabuleiros gigantes com stitching. Isto é
sintoma de o suporte a tabuleiros gigantes ter sido "colado" ao código
existente em vez de a arquitetura ter sido pensada desde o início como
"o tabuleiro pode sempre precisar de mais do que 1 frame — um tabuleiro
pequeno é só o caso em que 1 frame já chega".

**E percebi, ao rever isto, que a versão anterior deste plano repetia o
mesmo erro** — tinha uma "Fase 5: loop para tabuleiros pequenos" separada
de uma "Fase 7: loop para tabuleiros gigantes". Corrigi isto mais abaixo:
passa a existir **um único loop de jogo**, que usa sempre o critério de
cobertura (Fase 5a) para decidir quantos frames precisa — para um
tabuleiro pequeno, isso resolve-se com 1 frame só, sem precisar de nenhum
código especial de "modo pequeno".

### 3. Margens de UI como constantes de pixels fixas

`TOP_MARGIN = 400` e `BOTTOM_MARGIN = 300` estão escritos à mão em
`stitch.py`, presumivelmente calibrados uma vez, para uma resolução, e
nunca mais revistos. Isto é frágil a mudanças de resolução, orientação ou
a uma futura alteração da UI do jogo (ex. um banner novo). **Recomendação:**
na reconstrução, calcula as margens como proporção da altura do ecrã
detetada em `wm size`, ou — melhor ainda — deteta a fronteira real da UI
por conteúdo (onde a zona de jogo realmente começa/acaba), não por um
número de pixels fixo escrito no código.

### 4. Estado global em singletons de módulo

`adb_client._shell_proc` e `capture._stream` são variáveis globais ao
nível do módulo, não objetos passados explicitamente. Funciona, mas
dificulta testar (não dá para ter duas sessões, mocking é mais difícil,
há estado escondido). Isto é inconsistente com o princípio de "camadas
com interfaces" que já defini para o `FrameSource` — **a mesma lógica
devia aplicar-se à ligação ADB e ao `Actuator`**: um objeto de sessão
explícito, passado a quem precisa dele, não um global.

### 5. Caminho de scan por canto mantido morto ao lado do center-out

`capture_grid` (varrimento por canto superior esquerdo) continua no
código ao lado de `capture_grid_centered` (center-out), mesmo depois de
o center-out ter sido comprovado melhor. É um sintoma de "acrescentar
sem podar" — cada tentativa fica para sempre no código, mesmo quando já
se sabe que não é a melhor. **Recomendação:** na reconstrução, implementa
só o center-out com cobertura geométrica (Fase 5a); não vale a pena
recriar a versão por canto "só para ter lá", já sabes que não é a melhor.

### 6. Vários scripts com `__main__` próprios em vez de um ponto de entrada único

`bot.py`, `play_grid.py`, `stitch.py`, `capture.py` e `calibrate.py` têm
cada um o seu próprio bloco `if __name__ == "__main__":`. Reflete
crescimento orgânico (cada nova capacidade virou um novo ficheiro
executável) em vez de uma decisão de arquitetura sobre como o programa
deve ser invocado. Não é grave, mas vale a pena decidir desde o início:
um único ponto de entrada com subcomandos (`auto-arrows play`,
`auto-arrows calibrate`, `auto-arrows debug-capture`, ...) em vez de
vários scripts soltos.

---

## 3. Ordem de construção — visão geral e porquê

Respondendo diretamente à tua dúvida ("grelhas primeiro ou stitching
primeiro?"): **grelhas (deteção num único frame) sempre primeiro.**
Stitching não é uma etapa paralela à deteção de grelha — é *literalmente*
"aplicar a deteção de grelha a vários frames e depois fundir os
resultados". A ordem correta é:

```
Ambiente/ligação
   ↓
Captura de 1 frame (fiável, nem que seja lenta)
   ↓
Deteção de grelha + setas NUM frame        ← aqui só entra 1 imagem
   ↓
Solver (puro, offline)                     ← pode ser feito em paralelo
   ↓
Stitching + critério de cobertura (multi-frame → mapa global)
   ↓
Loop de jogo ÚNICO (pequeno e gigante são o mesmo código, sem duplicar)
   ↓
Robustez / recuperação automática
   ↓
Otimização de velocidade (troca de FrameSource, batch de toques)
   ↓
Medir e só depois decidir sobre mudar de linguagem
```

Nota a diferença face à primeira versão deste plano: já não há uma fase
separada de "bot para tabuleiros pequenos" — foi fundida com a fase
seguinte, exatamente pela razão apontada no ponto 2 da secção anterior.

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

## Fase 2 — Captura de alta velocidade (Stream scrcpy-server / H.264)

**Objetivo:** Ter uma classe `ScrcpyFrameSource` que fornece frames em tempo real (60+ FPS, <10 ms de latência) via *stream* H.264 / scrcpy-server, com `ADBFrameSource` (*screencap*) como *fallback* de segurança.

**O que fazer:**
- Implementar a interface unificada `FrameSource` (Protocolo Python):
  ```python
  class FrameSource(Protocol):
      def get_frame(self) -> np.ndarray: ...
      def is_fresh(self, max_age: float = 0.5) -> bool: ...
  ```
- Implementar `ScrcpyFrameSource` que descodifica o fluxo de vídeo H.264 em segundo plano diretamente para arrays BGR em memória.
- Implementar `ADBFrameSource` (`screencap`) como plano de contingência caso o stream seja interrompido.
- Passar a sessão ADB como objeto explícito (sem singletons).
- Guardar os screenshots de teste em `fixtures/frames/` (tabuleiros normais, com *pan*, com *zoom* e jogados).

**Critério de aceitação:** Chamar `get_frame()` devolve o frame mais recente em <10 ms com `is_fresh() == True`, e a suite de testes funciona tanto sobre a ligação ao vivo como sobre os ficheiros em `fixtures/`.

**Isolamento:** Todos os módulos de visão e solver dependem apenas do protocolo `FrameSource`, podendo correr sem o telemóvel conectado usando `FileFrameSource('fixtures/...')`.

---

## Fase 3 — Deteção de grelha e setas num único frame

**Objetivo:** transformar 1 imagem numa grelha simbólica: células vazias,
ocupadas (com o id da seta a que pertencem — ver ponto 1 da secção 2a), e
cabeças de seta com direção.

**O que fazer:**
- Começa pela abordagem mais simples possível: grelha fixa definida à
  mão (linhas/colunas e limites do tabuleiro anotados manualmente num dos
  `fixtures/`), só para validar a pipeline de classificação de células.
- Só depois avança para deteção automática da grelha (posição dos pontos,
  espaçamento entre células) — a v1 já validou que autocorrelação sobre
  as posições dos pontos funciona bem para encontrar o espaçamento da
  grelha; não precisas de reinventar essa parte do zero.
- Trata a deteção da cabeça e da direção da seta como uma função à parte
  da deteção da grelha.
- Ao classificar células ocupadas, tenta já associar cada componente
  ligado de pixels de seta a um id (mesmo que seja só "componente conexo
  nº N") — é isto que dá ao solver, mais tarde, a possibilidade de saber
  "esta célula ocupada é do próprio corpo desta seta ou de outra".

**Critério de aceitação:** para cada imagem em `fixtures/frames/`,
consegues gerar uma grelha simbólica e confirmar visualmente (desenhando
a grelha + setas detetadas sobre a imagem) que bate certo, incluindo nos
casos com setas "cobra" e com setas cujo corpo curva perto da própria
cabeça.

**Isolamento:** este passo só lê ficheiros de `fixtures/`. Nada aqui
depende do solver nem de ADB.

---

## Fase 4 — Solver (pode ser feito em paralelo com a Fase 3)

**Objetivo:** função pura `playable_moves(grid, heads) -> list[move]`.

**O que fazer:**
- Implementar a regra: seta jogável = linha reta da cabeça até à borda
  sem célula desconhecida nem célula ocupada **por outra seta** no
  caminho (decide conscientemente, e confirma no jogo real, se o próprio
  corpo da seta deve ou não contar como bloqueio — ver ponto 1 da secção
  2a).
- Testar com tabuleiros **escritos à mão em código/JSON**, não com
  imagens — incluindo pelo menos um caso sintético em que o corpo de uma
  seta curva de volta para a frente da própria cabeça, para forçar a
  decisão consciente do ponto anterior em vez de a deixar por defeito.

**Critério de aceitação:** um pequeno conjunto de tabuleiros de teste
(0 jogadas, 1 jogada, tabuleiro totalmente resolúvel, e o caso da seta
curvada sobre si própria) passa com o resultado esperado.

**Isolamento:** zero dependências de imagem, ADB ou I/O.

---

## Fase 5 — Stitching: juntar vários frames num mapa global

**Objetivo:** reconstruir o tabuleiro completo aplicando a deteção da
Fase 3 a vários frames e fundindo-os num mapa único — usado tanto para
tabuleiros pequenos (onde o "mapa" acaba por ser só 1 frame) como
gigantes.

**Ordem de varrimento — resposta direta à tua dúvida sobre centro vs.
canto:** começa logo por **centro para fora** (*center-out*), não por um
canto. Isto já foi comparado na prática na v1: por canto precisava de
25–40 passos para cobrir um tabuleiro grande; por centro, em "braços"
(cima, baixo, esquerda, direita, depois diagonais), caiu para 4–8 passos.
Não vale a pena recriar a versão por canto (ver ponto 5 da secção 2a).

**O que fazer:**
- Capturar sempre o frame central primeiro. Se a Fase 5a (abaixo)
  determinar que já cobre o tabuleiro todo, para aqui — é este o caso de
  um tabuleiro pequeno, sem nenhum código especial.
- Só se não cobrir tudo, expandir em braços retos e depois diagonais,
  sempre a verificar a cobertura entre cada passo.
- Alinhar frames consecutivos por *template matching* (deslocamento em
  pixels entre frames sobrepostos).
- Fundir as grelhas locais de cada frame numa grelha global.

**Critério de aceitação:** para `fixtures/` com 1 frame só (tabuleiro
pequeno) e para `fixtures/` com várias dezenas de frames conhecidos
(tabuleiro grande), o mapa global reconstruído bate certo com o que se vê
a olho, nos dois casos, com o mesmo código.

**Isolamento:** o stitching usa a Fase 3 (deteção por frame) como uma
caixa preta.

### Fase 5a — Parar de capturar por cobertura geométrica, não por contagem de setas

Isto resolve diretamente o desperdício que já observaste: o bot ir buscar
os 4 cantos do *center-out* mesmo quando o centro + os 4 braços retos já
tinham coberto tudo.

**Diagnóstico do problema da v1:** só sabia parar cedo através de
`stop_heads_count` — comparar quantas cabeças de seta já viu com um total
esperado. Duas fraquezas: (1) o total esperado nem sempre é conhecido com
confiança, (2) o critério é sobre *setas encontradas*, não sobre *área
vista* — não impede de ir buscar um canto que geometricamente já se sabe
estar coberto.

**A alternativa correta — critério geométrico:**

1. Cada frame capturado, depois de saberes o tamanho de célula e a fase
   da grelha (calculados a partir do frame central, logo ao início),
   passa a ter um **retângulo de cobertura conhecido**, em coordenadas de
   célula: a área do ecrã que esse frame mostra, excluindo as margens de
   UI.
2. Mantém a **união desses retângulos** à medida que capturas frames.
3. Depois de capturares o centro + os 4 braços retos (a "cruz"), calcula
   a **bounding box total do tabuleiro**: sabes que uma direção chegou ao
   limite real quando o deslocamento entre frames fica ~0 (o *clamping*
   que já existe hoje na v1) — a partir das 4 direções que baterem no
   limite, já conheces os 4 lados do tabuleiro.
4. Calcula os 4 retângulos de canto que ficam de fora da cruz. **Só vais
   buscar um canto se essa área ainda tiver alguma célula não coberta.**
   Se a cruz já cobre tudo (ecrã grande relativamente ao tabuleiro, como
   no caso que descreveste, ou tabuleiro pequeno em que 1 frame já chega),
   os cantos — ou os braços seguintes — são simplesmente saltados.
5. Os dois critérios não competem, complementam-se: para assim que
   **cobertura geométrica completa** OU **todas as setas esperadas já
   vistas** — o que vier primeiro.

**Nota sobre o teu modo manual ("eu movo, tu tiras a foto"):** é uma boa
ideia como ferramenta de depuração para gerar `fixtures/` com
deslocamentos conhecidos — mas não é preciso como mecanismo principal se
a cobertura geométrica funcionar bem: automatiza exatamente o que o modo
manual te ia dar controlo para fazer, sem precisares de estar presente em
cada nível.

**Critério de aceitação:** repetir o caso que observaste (centro + 4
braços já cobre tudo) e confirmar que os cantos deixam de ser capturados;
e, separadamente, um tabuleiro em que os cantos são mesmo precisos,
confirmar que continuam a ser capturados corretamente.

**Isolamento:** alteração só dentro da função de varrimento — não muda a
interface de saída do stitching (continua a devolver `[(frame, offset)]`).

---

## Fase 6 — Loop de jogo (único, sem duplicar pequeno/gigante)

**Objetivo:** o primeiro bot "a jogar a sério", do início ao fim, com
**um único** caminho de código para tabuleiros pequenos e gigantes —
correção direta ao ponto 2 da secção 2a.

**O que fazer:**
- Juntar Fase 2 (frame) → Fase 5+5a (mapa, com cobertura mínima
  necessária) → Fase 3 (grelha, já aplicada durante o stitching) →
  Fase 4 (jogadas) → converter `(linha, coluna)` em coordenadas de ecrã →
  enviar toque → aguardar → repetir.
- Modo `dry-run` primeiro, só depois liga os toques reais.
- Deteção simples de "nível terminado" (sem cabeças de seta no mapa).
- Testa primeiro com os `fixtures/` de 1 frame (equivalente ao antigo
  "modo pequeno"), depois com os de vários frames (equivalente ao antigo
  "modo gigante") — **mesmo código nos dois casos**, só os dados de teste
  mudam.

**Critério de aceitação:** resolve, sozinho e do início ao fim, pelo
menos 3 níveis pequenos e 1 nível gigante, sem nenhuma bifurcação de
código entre os dois casos.

**Isolamento:** este é o primeiro ponto onde juntas tudo — se aparecer
um bug, testa a Fase 3, 4 ou 5 isoladamente com os `fixtures` desse nível
específico antes de mexer aqui.

---

## Fase 7 — Robustez e recuperação automática

**Objetivo:** o bot não deve ficar preso quando algo correr mal.

**O que fazer (lições já documentadas na v1):**
- Verificar estabilidade da imagem antes de agir (duas capturas seguidas
  iguais) para não decidir com base numa animação a meio.
- Se não houver jogadas válidas mas ainda houver setas visíveis →
  reconhecer inconsistência, limpar o estado e refazer o stitching do
  zero.
- Limite máximo de jogadas/tentativas antes de parar e avisar.

**Critério de aceitação:** provocar deliberadamente uma dessincronização
e confirmar que o bot se recupera sozinho, em vez de travar ou tocar às
cegas.

---

## Fase 8 — Ajustes e Otimização do Stream (scrcpy / H.264)

**Objetivo:** Afinar os parâmetros de streaming (resolução, bitrate e *fps*) do `ScrcpyFrameSource` que já está em funcionamento desde a Fase 2.

**O que fazer:**
- O `ScrcpyFrameSource` já é o motor principal de captura do projeto desde a Fase 2.
- Nesta fase, realizam-se testes de *benchmarking* de latência (medindo tempos de *frame delivery* < 10 ms).
- Ajustar resolução dinâmica (ex.: `600x1332`) para maximizar a velocidade de processamento de imagem OpenCV sem perder precisão nas cabeças de seta.

**Critério de aceitação:** Latência de captura sustentada abaixo dos 10 ms por frame em corridas de longa duração.

---

## Fase 9 — Medir, só depois decidir sobre mudar de linguagem

Respondendo diretamente à tua pergunta sobre C# (ou outra linguagem mais
rápida): **primeiro Python, medir, e só portar se os números
justificarem.**

**Como decidir com dados, não com intuição:**
1. Depois da Fase 8, instrumenta o loop principal com `time.perf_counter()`
   à volta de cada camada (`FrameSource`, `Vision`, `Solver`, `Actuator`).
2. Corre um conjunto de níveis de referência e regista quanto tempo cada
   camada consome, em percentagem do total.
3. **Só considera portar para outra linguagem a camada que continuar a
   dominar o tempo total depois da Fase 8.** É muito provável que
   continue a ser I/O (ADB/rede/USB) mesmo depois do scrcpy — nesse caso,
   nenhuma linguagem resolve isso.
4. Se, e só se, a visão computacional ou o solver aparecerem a consumir
   uma fatia significativa (ex. >20% do tempo total), aí sim faz sentido
   portar **só essa camada** — graças à separação em interfaces da
   secção 2, isso significa reescrever um módulo, não o projeto todo.
5. Sobre a escolha da linguagem, se chegares a este ponto: para visão
   computacional, C++ e Rust são as escolhas mais naturais (OpenCV
   nativo, sem custo de *binding*). C# é viável (`OpenCvSharp`, clientes
   ADB para .NET existem) mas é uma escolha menos comum neste nicho — se
   já souberes bem C#, isso pesa mais na prática do que a diferença
   teórica de performance, especialmente numa camada que provavelmente
   nem vai ser a que precisa de ser portada.

**Critério de aceitação:** uma tabela de tempos por camada, para pelo
menos 5 execuções reais, que te diga com números se vale a pena avançar
para uma reescrita parcial.

---

## Resumo da ordem final

```
1. Ambiente/ADB
2. Captura de 1 frame (screencap, correto antes de rápido)
3. Deteção de grelha + setas (1 frame, com "dono" por célula ocupada)
4. Solver puro (paralelo à Fase 3)
5. Stitching + 5a. Critério de cobertura geométrica (center-out)
6. Loop de jogo ÚNICO (pequeno e gigante = mesmo código)
7. Robustez/recuperação
8. Troca de FrameSource para scrcpy-client
9. Medir → decidir se compensa portar para outra linguagem
```
