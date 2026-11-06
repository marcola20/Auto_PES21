"""
certificados.py  --  Auto_PES21

Faz o Python confiar nos certificados HTTPS de sempre MAIS os do pacote
certifi. Basta importar (o painel, o caminhos.py e o youtube/config.py ja
importam).

Por que: o Python no Windows so confia nos certificados raiz que ja estao
no Windows. O Windows baixa os que faltam quando o Edge precisa, mas o
Chrome tem a lista dele - num PC que so usa o Chrome, o raiz do site
(Google Trust Services, via Cloudflare) pode nunca ter chegado ao Windows,
e o Python recusa: CERTIFICATE_VERIFY_FAILED. O certifi traz a lista inteira.
"""

import ssl


def _contexto() -> ssl.SSLContext:
    contexto = ssl.create_default_context()
    try:
        import certifi
        contexto.load_verify_locations(certifi.where())
    except (ImportError, OSError, ssl.SSLError):
        pass    # sem certifi: fica so com os do Windows, como antes
    return contexto


# O urllib (e o http.client) chama esta funcao para cada conexao HTTPS sem
# contexto proprio.
ssl._create_default_https_context = _contexto
