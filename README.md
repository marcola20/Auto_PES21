# Auto_PES21

Roda partidas **CPU x CPU** no PES 2021 sozinho, uma atrás da outra, e grava
cada uma com a NVIDIA (Alt+F9). Depois lê o final de cada vídeo (placar, gols,
cartões, notas), envia os resultados para o site da liga e sobe os vídeos no
YouTube como estreia.

O fluxo completo:

```
rodar_jogos.py  ->  extrair_eventos.py  ->  enviar_resultados.py  ->  youtube/upar_videos.py
 joga e grava        lê o fim do vídeo       manda para o site         sobe no YouTube
```

Quem não quer mexer em código pode fazer tudo pelo **painel no navegador**
(seção 2.0): montar a fila pelas rodadas do site, ajustar os caminhos e
rodar os quatro passos com um clique.

> **Vindo do RPA_Youtube?** Ele agora mora na pasta `youtube/` deste projeto
> (o repositório separado não é mais atualizado). Veja a seção 2.5.

---

## 1. Configurar (uma vez)

### 1.1 O que precisa ter no PC

- **Windows 10/11 em português** (o OCR do Windows, com o idioma Português,
  é usado para ler o fim do vídeo).
- **Python 3.10 ou mais novo** — na instalação, marque *"Add Python to PATH"*.
- **Git** (para o `git clone` abaixo). Sem Git, dá para baixar pelo GitHub em
  *Code → Download ZIP* e descompactar.
- **PES 2021** com o patch e o **sider**.
- **NVIDIA GeForce Experience / App** com a gravação no atalho **Alt+F9**.
- **Google Chrome**, só para subir no YouTube.

### 1.2 Baixar e instalar as dependências

```
git clone https://github.com/marcola20/Auto_PES21.git
cd Auto_PES21
pip install pillow pydirectinput imageio-ffmpeg winrt-runtime winrt-Windows.Media.Ocr winrt-Windows.Graphics.Imaging winrt-Windows.Storage.Streams winrt-Windows.Globalization winrt-Windows.Foundation winrt-Windows.Foundation.Collections
pip install playwright
```

O `playwright` é só para subir no YouTube. Não precisa de `playwright install`:
ele usa o Chrome que já está no PC.

### 1.3 Dizer onde ficam as pastas no seu PC

Rode qualquer script uma vez (por exemplo `python abrir_jogo.py --medir`). Ele
cria o arquivo **`caminhos.ini`** e para. Abra esse arquivo no Bloco de Notas e
ajuste:

```ini
[caminhos]
# Pasta onde esta o PES2021.exe
pasta_pes = D:\Jogos\eFootball PES 2021

# Pasta onde esta o sider.exe
pasta_sider = D:\Jogos\eFootball PES 2021\PES 2009 Remake

# Onde a NVIDIA salva as gravacoes do PES
pasta_videos = ~\Videos\NVIDIA\eFootball PES 2021

[youtube]
# chrome.exe. Deixe em branco para o script achar sozinho.
chrome =
# Vao no nome das playlists. Troque na virada de temporada.
edicao = 8
temporada = 3
```

O mesmo arquivo tem a seção `[site]` (seção 2.4). Tudo isso dá para editar
também pelo painel, na aba **Configuração**.

- Pode usar `\` normalmente, sem aspas.
- `~` é a sua pasta de usuário (`C:\Users\<seu nome>`).
- Esse arquivo é só seu: ele **não** vai para o GitHub.

Para descobrir a `pasta_videos`: grave qualquer coisa com Alt+F9 e veja em
que pasta o vídeo apareceu.

### 1.4 Deixar o jogo igual ao do script

O script **enxerga a tela** comparando com as imagens da pasta `templates/`.
Por isso o jogo precisa estar como foi calibrado:

| Item | Como tem que estar |
|---|---|
| Resolução | **1920x1080**, tela cheia |
| Idioma do PES | Português |
| Menu do sider | **"Menu 2"** — apague as outras pastas de `content\rndmenu` do sider (o script avisa se sobrar alguma) |
| Controles | Teclado no padrão do jogo |
| Times | Todos dentro de "Brasileirão Série A", na ordem de `times.py` |

Se algo for diferente (outra resolução, outro tema, outra fonte), os templates
não vão bater e é preciso **recalibrar** — veja a seção 3.

### 1.5 Teste rápido

```
python abrir_jogo.py --medir
```

Não aperta nada: só mostra, a cada segundo, qual tela reconheceu. Abra o PES
na mão e confira se ele reconhece as telas (título, aviso, menu KICK OFF...).

Para testar só a gravação (Alt+F9 e se o vídeo aparece na pasta):

```
python teste_gravacao.py
```

---

## 2. Usar

### 2.0 Pelo painel (o jeito fácil)

Clique duas vezes em **`Abrir painel.bat`**, na pasta do projeto. O painel
abre no navegador (`http://127.0.0.1:8021`), sem janela preta.

Para não precisar nem abrir a pasta: no painel, aba **Configuração**, clique
em **Criar atalho na Área de Trabalho** (ou rode `python criar_atalho.py`).
Aparece o atalho **Auto PES21**, com ícone de bola, que abre o painel com um
clique duplo. Ele sempre abre a versão atual do código, então continua
valendo depois de um `git pull`. Só precisa ser criado de novo se o Python
for reinstalado em outra pasta.

- Clicar no atalho com o painel já aberto só abre a página de novo: não sobe
  um segundo painel.
- Para desligar, use **Fechar painel**, no canto de cima. Fechar só a aba do
  navegador deixa o painel ligado (o atalho abre de novo a mesma página).
- Pelo terminal também funciona: `python painel.py` (Ctrl+C fecha).

- **Jogos:** escolha a competição e a rodada (vêm do site). Os jogos que
  ainda faltam já vêm marcados; desmarque o que não quiser e clique em
  *Adicionar à fila*. Jogos já jogados no site ou já gravados na pasta de
  vídeos vêm desmarcados. Dá para juntar rodadas e competições na mesma fila,
  mudar a ordem e incluir um jogo avulso.
- **Rodar jogos:** o painel olha o PES antes de apertar qualquer tecla:
  - fechado: abre o sider e o jogo (como o `--abrir`);
  - aberto na seleção de times, ou em uma tela do caminho até ela (título,
    menu, escolha de lado): continua de lá;
  - aberto em qualquer outra tela: não aperta nada, avisa e mostra a foto do
    que viu.

  Depois do clique o PES vem para a frente: **não mexa no mouse nem no
  teclado** até acabar.
- **Extrair eventos / Simular envio / Enviar resultados:** os mesmos scripts
  das seções 2.3 e 2.4, com a saída aparecendo no painel.
- **Vídeos:** cada jogo da pasta e em que passo está (falta extrair,
  revisar, pronto para enviar, enviado).
- **YouTube:** competição, rodada, quais vídeos e em que ordem (*junto* =
  mesmo horário do de cima), estreia ou privado, data e intervalo. Mostra o
  título e o horário de cada vídeo antes de subir. O botão *Entrar na conta
  do canal* abre o Chrome do robô para o login (seção 2.5).
- **Configuração:** edita o `caminhos.ini` e confere se o PES2021.exe, o
  sider.exe, a pasta de vídeos e o Chrome estão onde você disse.

O painel só chama os scripts: tudo abaixo continua funcionando pelo terminal.

### 2.1 Montar a lista de jogos

Abra `rodar_jogos.py` e edite a lista `JOGOS` no topo:

```python
JOGOS = [
    ("Flamengo", "Palmeiras"),
    ("Santos", "Grêmio"),
    ("Santos", "Cruzeiro", "Supercopa"),   # jogo fora da liga: 3º item = competição
]
```

Os nomes precisam existir em `times.py` (acento e maiúscula são opcionais).
Para ver a lista: `python times.py`.

### 2.2 Rodar e gravar

Com o PES **fechado** (o script abre o sider e o jogo sozinho):

```
python rodar_jogos.py --abrir
```

Ou, com o PES já aberto na **lista de times do painel "Em casa"** (controle no
meio, CPU x CPU):

```
python rodar_jogos.py
```

Você tem 10 segundos para clicar na janela do PES. Depois disso **não mexa no
mouse nem no teclado**.

Ou deixe o script decidir (é o que o painel usa):

```
python rodar_jogos.py --auto
```

Com o PES fechado, abre; aberto na seleção de times ou no caminho até ela,
continua de lá; em outra tela, para sem apertar nada. `--fila arquivo.json`
troca a lista `JOGOS` por um `.json` no formato
`[{"casa": "Santos", "fora": "Grêmio", "competicao": "Copa"}]`. Cada jogo vira um vídeo chamado
`Casa vs Fora.mp4` na `pasta_videos`.

Se parar no meio, o script diz em qual jogo parou e se o vídeo dele foi salvo.
Tire da lista `JOGOS` os que já foram e rode de novo.

### 2.3 Ler os resultados dos vídeos

```
python extrair_eventos.py
```

Cria, ao lado de cada vídeo, um `.json` com placar, gols, assistências,
cartões, substituições e notas. Se o OCR ficou em dúvida, o `.json` sai com
`"status": "revisar"` e o motivo em `"avisos"` — corrija na mão e mude para
`"ok"`.

Os nomes dos jogadores são corrigidos pelo elenco de cada time na base de
jogadores do PES que o site usa (o OCR lê "Petrbech" em vez de "Petr Čech").
Para isso, aponte `base_jogadores`, na seção `[site]` do `caminhos.ini`, para o
arquivo `pes-jogadores.json.gz` do repositório do site (`Fc25_Draft`). Essa base
é uma foto do save: quem mudou de time depois dela vem do elenco atual de cada
time no site (a `url` da mesma seção; sem internet, vale a última cópia, em
`elencos_site.json`). Sem nenhum dos dois, os nomes ficam como o OCR leu.

Gol contra: o PES escreve só "Gol contra" na linha do tempo, sem dizer quem
fez. O evento sai como `"tipo": "gol_contra"`, com `"lado"` do time que ganhou
o gol e `"jogador": null`, e o `.json` fica em `"revisar"`: ponha o nome do
autor (do time adversário) em `"jogador"` e mude para `"ok"`.

| Comando | O que faz |
|---|---|
| `python extrair_eventos.py` | todo vídeo que ainda não tem `.json` |
| `python extrair_eventos.py "arquivo.mp4"` | só esse (refaz) |
| `python extrair_eventos.py --forcar` | refaz todos |

### 2.4 Enviar para o site da liga

Precisa do endereço e do token do site (peça o token ao admin). Uma vez só,
preencha a seção `[site]` do `caminhos.ini` — ele fica só neste PC e não vai
para o GitHub:

```
[site]
url = https://cbfv-app.onrender.com
token = seu-token-aqui
```

Depois é só:

```
python enviar_resultados.py --simular   # só mostra o que enviaria
python enviar_resultados.py             # envia
```

`.json` com `"status": "revisar"` é pulado. O que já foi enviado fica anotado e
não é mandado de novo (a não ser que o `.json` mude).

### 2.5 Subir no YouTube

Pelo painel (aba **YouTube**) ou pelo terminal, de dentro da pasta `youtube`:

```
cd youtube
python login.py          # uma vez: entrar na conta do canal
python upar_videos.py    # pergunta competição, rodada, ordem e horário
```

Detalhes (playlists, descrições, capas, opções): [youtube/README.md](youtube/README.md).

**Vindo do RPA_Youtube?** Copie da pasta antiga para `Auto_PES21\youtube\`:

- `historico.csv` — **importante**: é ele que impede subir o mesmo vídeo
  duas vezes;
- a pasta `perfil_chrome` — o login do canal (sem ela, é só rodar o
  `login.py` de novo).

O `caminhos.ini` antigo não serve mais: o `chrome` vai para a seção
`[youtube]` do `caminhos.ini` daqui, junto com `edicao` e `temporada`
(antes ficavam no `config.py`).

### 2.6 Outros utilitários

| Comando | Para que serve |
|---|---|
| `python renomear_video.py "arquivo.mp4" Casa Fora` | renomeia na mão um vídeo que o loop não conseguiu renomear |
| `python capturar_telas.py` | tira prints da tela para diagnóstico |

Sempre rode os scripts **de dentro da pasta do projeto** (eles procuram
`templates/` a partir dela).

---

## 3. Recalibrar (se o jogo estiver diferente)

Se sua resolução, tema ou fonte forem diferentes, refaça os templates com o
jogo aberto na tela certa:

| Comando | Quando rodar |
|---|---|
| `python calibrar_times.py` | na lista de times — fotografa o nome de cada time |
| `python calibrar_ligas.py casa` / `fora` | com o painel da liga ativo |
| `python calibrar_painel.py intervalo` | no painel escuro do intervalo |
| `python calibrar_painel.py fim` | no painel escuro de fim de jogo |
| `python calibrar_painel.py replay` | durante um replay, com a caixa de informação na tela |
| `python calibrar_painel.py formacao` | na tela de formação, já parada |

Os templates de abertura (`templates/abertura_*.png`) são recortes da tela
de título, aviso, menu e submenu. Se não baterem, `abrir_jogo.py --medir` vai
mostrar a tela como não reconhecida.
