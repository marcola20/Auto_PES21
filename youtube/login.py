"""
login.py  --  RPA_Youtube

Rode UMA vez (e de novo so se o YouTube deslogar):
  python login.py

Abre o Chrome com o perfil do robo. Entre na conta Google do canal, confira
que o YouTube Studio abre no canal certo e feche o Chrome. O login fica salvo
em perfil_chrome/ e o upar_videos.py reaproveita.
"""

import studio


def main() -> int:
    studio.abrir_chrome("https://studio.youtube.com")
    print("Chrome aberto. Faca o login na conta do canal, confira o Studio")
    print("e depois FECHE o Chrome.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
