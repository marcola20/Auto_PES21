# youtube — subir os jogos no YouTube

Parte do [Auto_PES21](../README.md) (antes era o repositório separado
RPA_Youtube). Sobe para o YouTube os jogos gravados, cada um programado como
**estreia** (de 20 em 20 minutos, ou o intervalo que você escolher) ou como
**privado**, com título, descrição, miniatura e playlist da competição.

O jeito fácil é o painel (`python painel.py`, na pasta de cima), aba
**YouTube**. Este arquivo explica o que fica por trás e o uso pelo terminal.

---

## 1. Configurar (uma vez)

### 1.1 O que precisa ter no PC

Além do que o Auto_PES21 já pede:

- **Google Chrome** instalado.
- O **YouTube Studio em português** (o script procura os botões pelo texto).
- O `playwright`: `pip install playwright`. Não precisa de
  `playwright install`: o script usa o Chrome que já está no PC.

### 1.2 Caminhos, edição e temporada

Ficam no **`caminhos.ini` do Auto_PES21** (a pasta de cima), o mesmo da
gravação — a `pasta_videos` é a mesma. Pelo painel, aba **Configuração**; ou
no Bloco de Notas:

```ini
[youtube]
# chrome.exe. Deixe em branco para o script achar sozinho.
chrome =
# Vao no nome das playlists. Troque na virada de temporada.
edicao = 8
temporada = 3
```

Sem `edicao` ou `temporada` o script para: um número velho iria para o nome da
playlist de todos os vídeos.

### 1.3 Entrar na conta do canal

Pelo painel, botão **Entrar na conta do canal**; ou, de dentro desta pasta:

```
python login.py
```

Abre um Chrome separado (do robô). Entre na conta Google do canal, confira se o
YouTube Studio abre **no canal certo** e **feche o Chrome**. O login fica salvo
na pasta `perfil_chrome/`, que é só sua e **nunca** vai para o GitHub.

Só precisa repetir se o YouTube deslogar.

**Vindo do RPA_Youtube?** Copie da pasta antiga para esta (`youtube/`) o
`historico.csv` (**importante**: é ele que impede subir o mesmo vídeo duas
vezes) e a pasta `perfil_chrome` (o login; sem ela, é só fazer o login de
novo).

### 1.4 Playlists, descrições e capas

Em `config.py`:

| O quê | Onde |
|---|---|
| Nome das playlists | `COMPETICOES` → `playlist` (tem que ser o nome **exato** da playlist no canal, e ela já tem que existir) |
| Rodadas aceitas | `COMPETICOES` → `rodadas` |
| Intervalo padrão entre estreias (o script pergunta na hora; Enter usa este) | `MINUTOS_ENTRE_JOGOS` |

Descrições e miniaturas de cada competição são os arquivos
`descricao_*.txt` e `capa_*.jpg` desta pasta — é só trocar.

---

## 2. Usar

### 2.1 Subir os vídeos

Deixe na `pasta_videos` **só os vídeos que vão subir agora** (soltos na
pasta; subpastas são ignoradas). Então:

```
python upar_videos.py
```

Ele pergunta:

1. Qual competição (Série A, Série B, Copa, Supercopa)
2. Qual rodada
3. A ordem dos jogos — mostra os vídeos da pasta (com duração) e você pode
   reordenar ou deixar algum de fora
4. Estreia ou Privado
5. Se for estreia: data e horário do primeiro jogo, e o intervalo entre as
   estreias (Enter = 20 minutos)

Na ordem dos jogos, `+` põe dois (ou mais) jogos **no mesmo horário**:

```
Ordem dos jogos? 1+2,3,4
```

→ os jogos 1 e 2 estreiam juntos às 18:00, o 3 às 18:20 e o 4 às 18:40.
Enter mantém a ordem de gravação, um jogo por horário.

Mostra o plano (título e horário de cada vídeo), pede confirmação e sobe um
por um. O título é o nome do arquivo + rodada + competição:

```
<nome do vídeo> | 3ª Rodada | Brasileirão - Série A
```

Cada vídeo programado vai para a subpasta **`Enviados`** e é anotado em
`historico.csv`, para nunca subir duas vezes.

### 2.2 Opções

| Comando | O que faz |
|---|---|
| `python upar_videos.py --simular` | só mostra o plano, não abre o navegador |
| `python upar_videos.py --pausar` | para antes de cada "Programar" para você conferir |
| `python upar_videos.py --limite 1` | sobe só o primeiro (bom para testar) |
| `python upar_videos.py --listar` | competições e vídeos em JSON (o painel usa) |
| `python upar_videos.py --plano plano.json` | respostas num `.json` em vez de perguntar (o painel usa) |

**Primeira vez? Use `--simular` e depois `--limite 1 --pausar`.**

### 2.3 Se der erro

Na dúvida, o script **para tudo**. Ele salva um print e o HTML da página em
`diagnostico/` para ver o que aconteceu.

O vídeo que falhou pode ter ficado como **rascunho** no YouTube Studio —
apague lá antes de rodar de novo.
