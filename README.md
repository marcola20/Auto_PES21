# RPA_Youtube

Sobe para o YouTube os jogos gravados pelo
[Auto_PES21](https://github.com/marcola20/Auto_PES21), cada um programado como
**estreia** (de 20 em 20 minutos), com título, descrição, miniatura e playlist
da competição.

---

## 1. Configurar (uma vez)

### 1.1 O que precisa ter no PC

- **Python 3.10 ou mais novo** — na instalação, marque *"Add Python to PATH"*.
- **Google Chrome** instalado.
- O **YouTube Studio em português** (o script procura os botões pelo texto).

### 1.2 Baixar e instalar

```
git clone https://github.com/marcola20/RPA_Youtube.git
cd RPA_Youtube
pip install playwright
```

Não precisa de `playwright install`: o script usa o Chrome que já está no PC.

### 1.3 Dizer onde ficam as pastas no seu PC

Rode:

```
python login.py
```

Na primeira vez ele cria o arquivo **`caminhos.ini`** e para. Abra no Bloco de
Notas e ajuste:

```ini
[caminhos]
# Onde a NVIDIA salva as gravacoes do PES (a mesma pasta_videos do Auto_PES21)
pasta_videos = ~\Videos\NVIDIA\eFootball PES 2021

# chrome.exe. Deixe em branco para o script achar sozinho.
chrome =
```

- Pode usar `\` normalmente, sem aspas.
- `~` é a sua pasta de usuário (`C:\Users\<seu nome>`).
- Esse arquivo é só seu: ele **não** vai para o GitHub.

### 1.4 Entrar na conta do canal

```
python login.py
```

Abre um Chrome separado (do robô). Entre na conta Google do canal, confira se o
YouTube Studio abre **no canal certo** e **feche o Chrome**. O login fica salvo
na pasta `perfil_chrome/`, que é só sua e **nunca** vai para o GitHub.

Só precisa repetir se o YouTube deslogar.

### 1.5 Ajustar a temporada, playlists, descrições e capas

Em `config.py`:

| O quê | Onde |
|---|---|
| Edição e temporada | `EDICAO` e `TEMPORADA` |
| Nome das playlists | `COMPETICOES` → `playlist` (tem que ser o nome **exato** da playlist no canal, e ela já tem que existir) |
| Rodadas aceitas | `COMPETICOES` → `rodadas` |
| Intervalo entre estreias | `MINUTOS_ENTRE_JOGOS` |

Descrições e miniaturas de cada competição são os arquivos
`descricao_*.txt` e `capa_*.jpg` na pasta do projeto — é só trocar.

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
3. Estreia ou Privado
4. Se for estreia: data e horário do primeiro jogo

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

**Primeira vez? Use `--simular` e depois `--limite 1 --pausar`.**

### 2.3 Se der erro

Na dúvida, o script **para tudo**. Ele salva um print e o HTML da página em
`diagnostico/` para ver o que aconteceu.

O vídeo que falhou pode ter ficado como **rascunho** no YouTube Studio —
apague lá antes de rodar de novo.
