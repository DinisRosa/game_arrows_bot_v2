# Histórico de Commits e Desenvolvimento — Auto-ARROWS-V2

Este documento serve como enciclopédia e registo cronológico detalhado de todas as alterações efetuadas no repositório `Auto-ARROWS-V2`.

> **Regra Obrigatória:** Antes de cada novo `git commit`, este ficheiro deve ser atualizado com um novo registo no final, detalhando minuciosamente as alterações, ficheiros modificados, motivação técnica e resultados de testes efetuados nesse commit.

---

## 📜 Histórico de Commits Anteriores

| Commit | Data / Hora (ISO) | Autor | Mensagem do Commit |
| :--- | :--- | :--- | :--- |
| `13969d7` | 2026-09-19 18:51:27 +0100 | Dinis Rosa | Initial commit: Auto-ARROWS-V2 setup, plan v2, UI mask, and streaming FrameSource |
| `8a483fb` | 2026-09-19 18:58:40 +0100 | Dinis Rosa | Phase 3.1: Implement Grid Geometry, pitch & phase origin detection |
| `42a6ed6` | 2026-09-19 19:02:01 +0100 | Dinis Rosa | Phase 3.2: Implement ArrowHead detection and directional classification |
| `58c8bad` | 2026-09-19 19:03:28 +0100 | Dinis Rosa | Phase 3 complete: Grid geometry, ArrowHead classification, and symbolic cell ownership mapping |
| `2917635` | 2026-09-19 19:13:55 +0100 | Dinis Rosa | Fix Direction pixel_delta mappings and directional arrow debug indicators |
| `ef801a8` | 2026-09-19 19:23:06 +0100 | Dinis Rosa | fix(vision): discriminate true arrowheads from flat tail ends using dynamic wing width thresholding |
| `2f2afad` | 2026-09-19 19:26:50 +0100 | Dinis Rosa | feat(solver): implement pure deterministic Solver class with 100% unit test coverage |
| `a27c4e4` | 2026-09-19 19:29:28 +0100 | Dinis Rosa | feat(bot): rename types to game_types, implement Actuator and unified AutoArrowsBot main loop |
| `40511fb` | 2026-09-19 19:33:03 +0100 | Dinis Rosa | docs(historico): create commit history documentation encyclopedia and pre-commit workflow rule |

---

## 🔍 Registo Detalhado de Commits

### Commit `a27c4e4`
- **Data/Hora:** 2026-09-19 19:29:28 +0100
- **Mensagem:** `feat(bot): rename types to game_types, implement Actuator and unified AutoArrowsBot main loop`
- **Autor:** Dinis Rosa

#### Motivação e Objetivos:
1. Concluir as Fases 5 e 6 da reconstrução do Auto-ARROWS-V2: Atuação de toques via ADB e Loop Principal de Jogo (`AutoArrowsBot`).
2. Resolver um conflito de importação do Python no qual o ficheiro local `src/types.py` estava a ocultar (`shadowing`) o módulo padrão `types` da biblioteca standard do Python (que causava `ImportError: cannot import name 'GenericAlias' from 'types'`).

#### Alterações Detalhadas Efetuadas:
1. **Renomeação de Módulo:**
   - O ficheiro `src/types.py` foi renomeado para `src/game_types.py`.
   - Adicionada a classe `@dataclass class Move` em `src/game_types.py` contendo `arrow_id`, `head`, `tap_x_px`, `tap_y_px`.
   - Atualizadas todas as importações em `src/vision.py`, `src/solver.py`, `tests/test_solver.py` de `from src.types` para `from src.game_types`.

2. **Criação do Atuador (`src/actuator.py`):**
   - Criada a classe `Actuator(device_id, dry_run)`.
   - Método `tap(x, y)`: envia comando de toque via ADB `adb shell input tap x y` ou imprime no terminal se `dry_run=True`.
   - Método `execute_move(move, delay_after=0.05)`: executa o toque nas coordenadas exatas da cabeça da seta em pixels.
   - Teste unitário em `tests/test_actuator.py` a validar a execução do modo simulação.

3. **Criação do Loop Principal (`src/bot.py`):**
   - Criada a classe `AutoArrowsBot` que coordena a pipeline completa:
     `FrameSource` (captura) $\rightarrow$ `VisionDetector` (visão/grelha) $\rightarrow$ `Solver` (cálculo de jogadas) $\rightarrow$ `Actuator` (toques).
   - Adicionado `sys.path.insert` para permitir invocação direta como script CLI.
   - CLI configurado com suporte para `--fixture`, `--live`, `--dry-run` e `--no-dry-run`.

4. **Validação de Testes:**
   - Executada a suite de testes com 6 testes unitários a passar (100% OK).
   - Executado o bot em modo `--dry-run` sobre a captura `screenshot_1.png`: 57 cabeças detetadas $\rightarrow$ 13 jogadas jogáveis calculadas e simuladas com sucesso.

### Commit `40511fb`
- **Data/Hora:** 2026-09-19 19:33:03 +0100
- **Mensagem:** `docs(historico): create commit history documentation encyclopedia and pre-commit workflow rule`
- **Autor:** Dinis Rosa

#### Motivação e Objetivos:
1. Atender ao pedido do utilizador de manter uma enciclopédia/documentação viva de commits (`docs/historico.md`).
2. Garantir que todas as alterações futuras sejam registadas detalhadamente antes de cada commit.

#### Alterações Detalhadas Efetuadas:
1. **Criação do Ficheiro `docs/historico.md`:**
   - Criada a tabela cronológica com os commits anteriores (Hash, Data/Hora ISO, Autor, Mensagem).
   - Adicionada a secção de registo detalhado para o commit `a27c4e4` (bot, actuator, game_types).
   - Adicionada a regra explícita de atualização obrigatória antes de cada novo commit.

2. **Criação da Regra do Workspace (`.agents/AGENTS.md`):**
   - Registada a instrução de trabalho que torna obrigatória a atualização do `docs/historico.md` antes de qualquer execução de `git commit`.

### Commit `a9c8fd2`
- **Data/Hora:** 2026-09-19 19:44:07 +0100
- **Mensagem:** `fix(vision): correct grid origin pixel mapping in build_grid to fix false-positive playable moves`
- **Autor:** Dinis Rosa

#### Motivação e Objetivos:
1. Corrigir um erro crítico na construção da grelha simbólica (`build_grid` em `src/vision.py`) identificado pelo utilizador através dos testes das imagens `screenshot_3`, `screenshot_5` e `screenshot_7`.
2. A função auxiliar `grid_to_px(r, c)` estava erroneamente a utilizar `geom.x0` e `geom.y0` (fases modulares `0..pitch`) em vez de `geom.min_x` e `geom.min_y` (coordenadas reais da origem da grelha em pixels). Isto fazia com que a amostragem de ocupação ocorresse na margem superior esquerda fora do tabuleiro, classificando erradamente quase todas as células como `EMPTY` e gerando dezenas de falsos positivos de jogadas válidas.

#### Alterações Detalhadas Efetuadas:
1. **Correção em `src/vision.py` (`build_grid`):**
   - Atualizada a função `grid_to_px(r, c)` para retornar `(geom.min_x + c * pitch, geom.min_y + r * pitch)`.
   - Adicionada uma primeira passagem de amostragem de ocupação que marca como `OCCUPIED` qualquer célula cujo centro coincida com pixels escuros de linha de seta em `dark_mask`.
   - Mantida a segunda passagem de rastreamento de cobras para associação de `arrow_id`.

2. **Resultados Verificados:**
   - `screenshot_3.png`: Falsos positivos reduzidos de 9 para **exatamente 2 jogadas válidas** (conforme esperado pelo utilizador).
   - `screenshot_5.png`: Falsos positivos reduzidos de 8 para **exatamente 0 jogadas válidas** (conforme esperado pelo utilizador).
   - `screenshot_7.png`: Falsos positivos reduzidos de 12 para **5 jogadas válidas** (conforme esperado pelo utilizador).

### Commit Seguinte (Organização da Pasta `fixtures/frames/`)
- **Data/Hora:** 2026-09-19 19:47:00 +0100
- **Mensagem:** `refactor(fixtures): reorganize fixtures/frames into dedicated subdirectories`
- **Autor:** Dinis Rosa

#### Motivação e Objetivos:
1. Atender à solicitação do utilizador para organizar a pasta `fixtures/frames/`, que acumulava dezenas de imagens misturadas de capturas originais, visualizações de depuração e modelos.
2. Facilitar a navegação e a clareza sobre o propósito de cada ficheiro de imagem no repositório.

#### Alterações Detalhadas Efetuadas:
1. **Reestruturação de Subpastas em `fixtures/frames/`:**
   - Criada a subpasta `fixtures/frames/screenshots/` contendo as capturas brutas do tabuleiro (`screenshot_1.png` a `screenshot_7.png`).
   - Criada a subpasta `fixtures/frames/debug/` contendo as imagens geradas com overlays de depuração (`debug_*.png`, `overlay_verification.png`, `test_scrcpy_output.png`).
   - Criada a subpasta `fixtures/frames/templates/` contendo os templates de setas (`template_*.png`).

2. **Atualização de Módulos e Scripts:**
   - Atualizado `src/bot.py` para utilizar o novo caminho `fixtures/frames/screenshots/screenshot_1.png` como fallback do leitor offline.

---


