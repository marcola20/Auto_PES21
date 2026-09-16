"""
teste_r1.py  --  Auto_PES21 / descobrir a tecla do R1

No painel de fim de jogo, o L1 e o R1 trocam a aba mostrada ("Pontuacao dos
jogadores", "Eventos da partida", ...). Para o script fazer isso sozinho eu
preciso saber qual tecla do TECLADO corresponde ao R1.

O metodo e o mesmo que achou o Esc: aperta cada candidata e faz uma pergunta de
sim ou nao - "o TITULO DA ABA mudou?". Medido nos prints: abas diferentes dao
sobreposicao 0.15, a mesma aba da 0.99. Nao ha limiar para calibrar errado.

ANTES DE RODAR ISTO: e mais rapido olhar direto no jogo, em
    Configuracoes -> Controles
e ver o mapeamento do teclado. Se voce achar o R1 por la, me diga a tecla e
pule este teste.

COMO USAR:
  Deixe o PES parado no MENU DE FIM DE JOGO (o painel escuro com os botoes
  Destaques / Registro / Jogar novamente / Selecionar time / Menu Principal).
  O script so troca de aba - nao confirma nada, nao inicia partida.
"""

# ====================== CONFIGURACOES ======================
SEGUNDOS_CONTAGEM = 8
PASTA_SAIDA = "diagnostico_r1"

# Candidatas. Evito de proposito Enter, Esc e as setas: essas ja tem funcao
# conhecida nessa tela e apertar seria mexer onde nao devo.
CANDIDATAS = ["e", "q", "r", "w", "tab", "pagedown", "pageup",
              "1", "2", "3", "4", "c", "v"]

PAUSA_APOS_TECLA = 1.2
# ===========================================================

import sys
import time
from pathlib import Path

import teclado
import visao


def contagem_regressiva(segundos: int) -> None:
    for restante in range(segundos, 0, -1):
        print(f"  Volte para o PES...  {restante:2d}s ", end="\r", flush=True)
        time.sleep(1)
    print("  Comecando!                       ")


def main() -> int:
    pasta = Path(PASTA_SAIDA)
    pasta.mkdir(exist_ok=True)

    print("=" * 70)
    print("  DESCOBRIR A TECLA DO R1  (troca de aba no fim de jogo)")
    print("=" * 70)
    print("\nDeixe o PES no MENU DE FIM DE JOGO (painel escuro com os 5 botoes).\n")
    contagem_regressiva(SEGUNDOS_CONTAGEM)

    # Guardo a tela inteira: alem do teste, ela me serve para refazer os
    # templates de fim de jogo e intervalo, que ainda sao do tema antigo.
    tela = visao.capturar_tela()
    tela.save(pasta / "00_fim_de_jogo.png")
    print(f"\n[1/2] Tela inicial salva em {pasta / '00_fim_de_jogo.png'}")

    antes = visao.ler_titulo_da_aba(tela)
    print(f"      titulo da aba: {sum(antes)} pixels de texto branco")
    if sum(antes) < 100:
        print("      FALHOU - nao vejo titulo de aba nenhum nessa regiao.")
        print("      O PES esta mesmo no menu de fim de jogo?")
        return 1

    print("\n[2/2] Testando as candidatas.\n")
    encontrada = None
    for tecla in CANDIDATAS:
        teclado.apertar(tecla)
        time.sleep(PAUSA_APOS_TECLA)

        tela = visao.capturar_tela()
        depois = visao.ler_titulo_da_aba(tela)
        tela.save(pasta / f"apos_{tecla}.png")

        if sum(depois) < 100:
            print(f"      {tecla:10s} a tela mudou para algo sem titulo de aba - "
                  f"PARANDO por seguranca")
            print(f"      (veja {pasta / f'apos_{tecla}.png'})")
            break

        parecenca = visao.sobreposicao(antes, depois)
        if parecenca >= visao.LIMIAR_NOME_TIME:
            print(f"      {tecla:10s} titulo igual ({parecenca:.3f}) -> nao e essa")
            continue

        print(f"      {tecla:10s} O TITULO MUDOU ({parecenca:.3f})  <<< ESTA E A TECLA")
        encontrada = tecla
        break

    print("\n" + "-" * 70)
    if encontrada is None:
        print("RESULTADO: nenhuma candidata trocou a aba.")
        print("-" * 70)
        print("Olhe o mapeamento no proprio jogo: Configuracoes -> Controles.")
        print("Me diga a tecla do R1 que eu configuro direto, sem mais testes.")
        return 1

    print(f"RESULTADO: a tecla do R1 e '{encontrada}'")
    print("-" * 70)
    print(f"Confira em {pasta}/apos_{encontrada}.png que a aba mudou mesmo.")
    print(f"\nEdite teclado.py:")
    print(f'    TECLA_R1 = "{encontrada}"')
    return 0


if __name__ == "__main__":
    try:
        codigo = main()
    except KeyboardInterrupt:
        print("\n\nInterrompido por voce (Ctrl+C).")
        codigo = 1
    sys.exit(codigo)
