# Auto_PES21

Roda partidas **CPU x CPU** no PES 2021 sozinho, uma atrás da outra, e grava
cada uma com a NVIDIA (Alt+F9). Depois lê o final de cada vídeo (placar, gols,
cartões, notas) e envia os resultados para o site da liga.

O fluxo completo:

```
rodar_jogos.py  ->  extrair_eventos.py  ->  enviar_resultados.py  ->  (RPA_Youtube)
 joga e grava        lê o fim do vídeo       manda para o site         sobe no YouTube
```

---

## 1. Configurar (uma vez)

### 1.1 O que precisa ter no PC

- **Windows 10/11 em português** (o OCR do Windows, com o idioma Português,
  é usado para ler o fim do vídeo).
- **Python 3.10 ou mais novo** — na instalação, marque *"Add Python to PATH"*.
- **PES 2021** com o patch e o **sider**.
- **NVIDIA GeForce Experience / App** com a gravação no atalho **Alt+F9**.

### 1.2 Baixar e instalar as dependências

```
git clone https://github.com/marcola20/Auto_PES21.git
cd Auto_PES21
pip install pillow pydirectinput imageio-ffmpeg winrt-runtime winrt-Windows.Media.Ocr winrt-Windows.Graphics.Imaging winrt-Windows.Storage.Streams winrt-Windows.Globalization winrt-Windows.Foundation winrt-Windows.Foundation.Collections
```

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
```

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
mouse nem no teclado**. Cada jogo vira um vídeo chamado
`Casa vs Fora ｜ Série X.mp4` na `pasta_videos`.

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

| Comando | O que faz |
|---|---|
| `python extrair_eventos.py` | todo vídeo que ainda não tem `.json` |
| `python extrair_eventos.py "arquivo.mp4"` | só esse (refaz) |
| `python extrair_eventos.py --forcar` | refaz todos |

### 2.4 Enviar para o site da liga

Precisa de duas variáveis de ambiente (peça o token ao admin do site). No
PowerShell, uma vez só:

```
setx CBFV_API_URL "https://cbfv-app.onrender.com"
setx CBFV_API_TOKEN "seu-token-aqui"
```

Feche e abra o terminal de novo, e então:

```
python enviar_resultados.py --simular   # só mostra o que enviaria
python enviar_resultados.py             # envia
```

`.json` com `"status": "revisar"` é pulado. O que já foi enviado fica anotado e
não é mandado de novo (a não ser que o `.json` mude).

### 2.5 Outros utilitários

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
