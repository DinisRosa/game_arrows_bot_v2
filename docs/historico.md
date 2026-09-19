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

### Commit Seguinte (Saneamento de Linguagem)
- **Data/Hora:** 2026-09-19 19:35:00 +0100
- **Mensagem:** `docs(historico): sanitize phrasing to maintain professional documentation tone`
- **Autor:** Dinis Rosa

#### Motivação e Objetivos:
1. Remover expressões informais do documento de histórico e da regra de trabalho, assegurando um tom estritamente profissional e técnico.

#### Alterações Detalhadas Efetuadas:
1. **Atualização em `docs/historico.md` e `.agents/AGENTS.md`:**
   - Substituídas todas as ocorrências de phrasings informais por linguagem profissional ("detalhando minuciosamente", "passo a passo", "registo detalhado").

---
