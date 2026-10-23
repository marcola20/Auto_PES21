"""
importar_rpa.py  --  Auto_PES21 / youtube

Traz do RPA_Youtube antigo (o repositorio separado de antes) o que e deste PC
e nao vem no git pull:

  - perfil_chrome/  o login do canal. E MOVIDO, nao copiado: tem gigas de
                    cache do Chrome, e no mesmo disco mover e instantaneo.
                    O RPA_Youtube antigo deixa de estar logado, e tudo bem:
                    ele nao e mais usado.
  - historico.csv   o que ja subiu. As linhas sao JUNTADAS com as daqui:
                    e a trava que impede subir o mesmo video duas vezes.

Se ja existir um perfil_chrome aqui (alguem clicou em "Entrar na conta do
canal" antes), ele nao e apagado: vira perfil_chrome.antes_de_importar.

Uso:
  python importar_rpa.py               -> procura o RPA_Youtube ao lado do Auto_PES21
  python importar_rpa.py "D:\\...\\RPA_Youtube"
O painel (aba YouTube) mostra um botao quando acha o RPA_Youtube ao lado.
"""

import csv
import shutil
import sys
import urllib.request
from pathlib import Path

PASTA = Path(__file__).resolve().parent
PERFIL = PASTA / "perfil_chrome"
HISTORICO = PASTA / "historico.csv"
PORTA_DEPURACAO = 9333        # a mesma do config.py: o Chrome do robo


def rpa_ao_lado():
    """O RPA_Youtube na mesma pasta que o Auto_PES21, se ainda tiver o que trazer."""
    candidato = PASTA.parent.parent / "RPA_Youtube"
    return candidato if candidato.is_dir() else None


def ler_historico(caminho: Path) -> tuple:
    """(cabecalho, linhas) do historico.csv; ([], []) se nao existir."""
    if not caminho.is_file():
        return [], []
    with caminho.open(encoding="utf-8", newline="") as f:
        linhas = list(csv.reader(f, delimiter=";"))
    return (linhas[0], linhas[1:]) if linhas else ([], [])


def situacao(pasta=None) -> dict:
    """O que ha para trazer. O painel usa para decidir se mostra o botao."""
    pasta = Path(pasta) if pasta else rpa_ao_lado()
    if not pasta or not pasta.is_dir():
        return {"pasta": None}
    _, antigas = ler_historico(pasta / "historico.csv")
    _, atuais = ler_historico(HISTORICO)
    novas = [l for l in antigas if l not in atuais]
    return {
        "pasta": str(pasta),
        "perfil": (pasta / "perfil_chrome").is_dir(),
        "historico_novas": len(novas),
    }


def chrome_do_robo_aberto() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORTA_DEPURACAO}/json/version", timeout=1):
            return True
    except OSError:
        return False


def juntar_historico(antigo: Path) -> int:
    """Acrescenta ao historico daqui as linhas do antigo que faltam. Devolve quantas."""
    cabecalho_antigo, antigas = ler_historico(antigo)
    cabecalho, atuais = ler_historico(HISTORICO)
    novas = [l for l in antigas if l not in atuais]
    if not novas:
        return 0
    with HISTORICO.open("a" if atuais or cabecalho else "w", encoding="utf-8", newline="") as f:
        escritor = csv.writer(f, delimiter=";")
        if not cabecalho:
            escritor.writerow(cabecalho_antigo)
        escritor.writerows(novas)
    return len(novas)


def mover_perfil(antigo: Path) -> None:
    if PERFIL.exists():
        reserva = PASTA / "perfil_chrome.antes_de_importar"
        n = 2
        while reserva.exists():
            reserva = PASTA / f"perfil_chrome.antes_de_importar ({n})"
            n += 1
        PERFIL.rename(reserva)
        print(f"  O perfil que ja estava aqui foi guardado em {reserva.name}")
        print("  (pode apagar essa pasta se o login trazido funcionar).")
    shutil.move(str(antigo), str(PERFIL))


def importar(pasta: Path) -> int:
    print(f"Trazendo do RPA_Youtube em {pasta}\n")
    if not pasta.is_dir():
        print("ERRO: essa pasta nao existe.")
        return 1
    # O Chrome aberto segura os arquivos do perfil: mover no meio estragaria o login.
    if chrome_do_robo_aberto():
        print("ERRO: o Chrome do robo esta aberto. Feche ele e tente de novo.")
        return 1

    historico = pasta / "historico.csv"
    if historico.is_file():
        n = juntar_historico(historico)
        print(f"historico.csv: {n} linha(s) nova(s) juntada(s)" if n
              else "historico.csv: nada novo (tudo ja estava aqui)")
    else:
        print("historico.csv: o RPA_Youtube nao tem")

    perfil = pasta / "perfil_chrome"
    if perfil.is_dir():
        try:
            mover_perfil(perfil)
        except OSError as erro:
            print(f"ERRO ao mover o perfil_chrome: {erro}")
            print("Se algum Chrome estiver usando ele, feche e tente de novo.")
            return 1
        print("perfil_chrome: login do canal trazido (movido do RPA_Youtube)")
    else:
        print("perfil_chrome: o RPA_Youtube nao tem (ja foi trazido?)")

    print("\nPronto. Confira com 'Conferir (simular)' e, na duvida sobre o login,")
    print("clique em 'Entrar na conta do canal' para ver se o Studio abre no canal certo.")
    return 0


def main() -> int:
    sys.stdout.reconfigure(errors="replace")
    pasta = Path(sys.argv[1]) if len(sys.argv) > 1 else rpa_ao_lado()
    if pasta is None:
        print("ERRO: nao achei o RPA_Youtube ao lado do Auto_PES21. Passe a pasta:")
        print('  python importar_rpa.py "D:\\Projetos\\RPA_Youtube"')
        return 1
    return importar(pasta)


if __name__ == "__main__":
    sys.exit(main())
