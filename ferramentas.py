import os
import logging
import requests
from dotenv import load_dotenv
from typing import Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


BASE_URL = "https://serpapi.com/search.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SerpApiError(Exception):
    """Erro devolvido pela SerpApi ou falha de comunicação."""

load_dotenv()

SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
api_key = SERPAPI_KEY



# Funções do Agente
def _criar_sessao() -> requests.Session:
    sessao = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    sessao.mount("https://", HTTPAdapter(max_retries=retry))
    return sessao


_SESSAO = _criar_sessao()


def _chamar(
    engine: str,
    params: dict[str, Any],
    api_key: str | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """Chamada genérica à SerpApi, com limpeza de parâmetros e tratamento de erros."""
    chave = api_key or os.environ.get("SERPAPI_KEY")
    if not chave:
        raise SerpApiError("Define a variável de ambiente SERPAPI_KEY.")

    consulta: dict[str, Any] = {}
    for k, v in params.items():
        if v is None:
            continue
        if isinstance(v, bool):
            v = str(v).lower()
        elif isinstance(v, (list, tuple)):
            v = ",".join(str(i) for i in v)
        consulta[k] = v
    consulta["engine"] = engine
    consulta["api_key"] = chave

    try:
        resp = _SESSAO.get(BASE_URL, params=consulta, timeout=timeout)
    except requests.RequestException as e:
        raise SerpApiError(f"{engine}: falha de rede ({e})") from e

    try:
        dados = resp.json()
    except ValueError:
        raise SerpApiError(f"{engine}: resposta não JSON (HTTP {resp.status_code})")

    erro = dados.get("error")
    if erro and "hasn't returned any results" in str(erro):
        return dados  # pesquisa válida sem resultados
    if resp.status_code >= 400 or erro:
        raise SerpApiError(f"{engine}: {erro or 'HTTP ' + str(resp.status_code)}")
    return dados

def pesquisar_voos(
    origem: str,
    destino: str,
    data_ida: str,
    data_volta: str,
    adultos: int = 1,
    criancas: int = 0,
    classe=1,
    moeda: str = "EUR",
    idioma: str = "pt",
    api_key= api_key,
    **extra,
) -> dict:
    """Essa função serve para fazer pesquisas de voos
    args:
        origem : essa Variável vai guardar a origem
        destino : essa variável vai guardar o destino
        data_ida : essa variável vai armazrnar a data de ida que o usuário pretende viajar 
        data_volta : essa variável vai guardar a data de regresso 
        adultos : Essa variável vai armazenar a quantidade de adultos que vão viajar
        criancas : essa variável vai armazenar a quantidade de crianças que vão viajar
        Classe : essa variável vai guardar a classe que o usuário pretende viajar use: 1- Econômica (padrão) 2- Econômica Premium 3- Executiva 4- Primeira Classe      
    """
    return _chamar("google_flights", {
    "departure_id": origem,
    "arrival_id": destino,
    "outbound_date": data_ida,
    "return_date": data_volta,
    "type": 1 if data_volta else 2,  # 1 ida e volta, 2 só ida
    "adults": adultos,
    "children": criancas,
    "travel_class": classe,
    "currency": moeda,
    "hl": idioma,
    **extra,
    }, api_key)


def opcoes_reserva_voo(
    booking_token: str,
    origem: str,
    destino: str,
    data_ida: str,
    data_volta: str | None = None,
    moeda: str = "EUR",
    idioma: str = "pt",
    api_key: str | None = None,
    **extra,
) -> dict:
    """Google Flights Booking Options: links de compra de um voo escolhido.
    args:
        booking_token : vem do resultado de pesquisar_voos()
        origem : essa Variável vai guardar a origem
        destino : essa variável vai guardar o destino
        data_ida : essa variável vai armazrnar a data de ida que o usuário pretende viajar 
        data_volta : essa variável vai guardar a data de regresso 
    """
    return _chamar("google_flights", {
        "booking_token": booking_token,
        "departure_id": origem,
        "arrival_id": destino,
        "outbound_date": data_ida,
        "return_date": data_volta,
        "type": 1 if data_volta else 2,
        "currency": moeda,
        "hl": idioma,
        **extra,
    }, api_key) 

# Essa função serve para retornar o código do pais 
def resolver_lugar(texto):
    sug = autocompletar_voos(texto).get("suggestions", [])
    return [
        {"nome": s["name"], "tipo": s.get("type"), "id": s["id"],
         "aeroportos": [a["id"] for a in s.get("airports", [])]}
        for s in sug
    ]

def autocompletar_voos(texto: str, idioma: str = "pt", api_key: str | None = None, **extra) -> dict:
    """Google Flights Autocomplete: sugere aeroportos/cidades. [CONFIRMAR engine]"""
    return _chamar("google_flights_autocomplete", {"q": texto, "hl": idioma, **extra}, api_key)


def ofertas_voos(origem: str, moeda: str = "EUR", idioma: str = "pt", api_key: str | None = None,**extra,) -> dict:
    """ Use esta função para procurar promoções do voos
        args
            origem : Essa variável vai receber o destino de viagem
    """
    return _chamar("google_flights_deals", {
        "departure_id": origem, "currency": moeda, "hl": idioma, **extra,
    }, api_key)


def explorar_destinos(
    origem: str,
    data_ida: str | None = None,
    data_volta: str | None = None,
    moeda: str = "EUR",
    idioma: str = "pt",
    api_key: str | None = None,
    **extra,
) -> dict:
    """Use essa função para procurar destinos mais baratos a partir de uma origem.
    args: 
        origem : essa Variável vai receber a origem
        data_ida : essa variável vai receber a data de ida que o usuário pretende viajar 
        data_volta : essa variável vai receber a data de regresso 
    """
    return _chamar("google_travel_explore", {
        "departure_id": origem,
        "outbound_date": data_ida,
        "return_date": data_volta,
        "currency": moeda,
        "hl": idioma,
        **extra,
    }, api_key)


def estado_voo_tempo_real(api_key: str | None = None, **filtros) -> dict:
    """Flightradar24: voos em tempo real. Os filtros (ex.: indicativo, aeroporto)
    seguem a documentação. [CONFIRMAR parâmetros]"""
    return _chamar("flightradar24", filtros, api_key)

#Pesquisa de hoteis
def pesquisar_hoteis(
    destino: str,
    check_in: str,
    check_out: str,
    adultos: int = 2,
    criancas: int = 0,
    moeda: str = "EUR",
    idioma: str = "pt",
    pais: str | None = None,
    api_key: str | None = None,
    **extra,
) -> dict:
    """ Use esta função para pesquisar Hotels: pesquisa por destino e datas (YYYY-MM-DD).
    args
        destino : Essa variável vai receber o destino de viagens
        check_in: Essa variável vai receber o check_in,
        check_out: Essa variável vai receber o check_out,
        adultos : Essa variável vai receber a quantidade de adultos que vão viajar
        criancas : essa variável vai receber a quantidade de crianças que vão viajar
    """
    return _chamar("google_hotels", {
        "q": destino,
        "check_in_date": check_in,
        "check_out_date": check_out,
        "adults": adultos,
        "children": criancas,
        "currency": moeda,
        "hl": idioma,
        "gl": pais,
        **extra,
    }, api_key)

def detalhes_hotel(
    property_token: str,
    check_in: str,
    check_out: str,
    adultos: int = 2,
    moeda: str = "EUR",
    idioma: str = "pt",
    api_key: str | None = None,
    **extra,
) -> dict:
    """Use essa função para mostrar detalhes dos hoteis: preços por fornecedor, comodidades, etc.
    args
        property_token : Os dados dessa variável serão retornados pela função pesquisar_hoteis 
        check_in: Essa variável vai receber o check_in,
        check_out: Essa variável vai receber o check_out,
        adultos : Essa variável vai receber a quantidade de adultos que vão viajar
    """
    return _chamar("google_hotels", {
        "q": extra.pop("q", "hotel"),
        "property_token": property_token,
        "check_in_date": check_in,
        "check_out_date": check_out,
        "adults": adultos,
        "currency": moeda,
        "hl": idioma,
        **extra,
    }, api_key)


def avaliacoes_hotel(
    property_token: str,
    idioma: str = "pt",
    pagina_seguinte: str | None = None,
    api_key: str | None = None,
    **extra,
) -> dict:
    """Use essa função para fazer avaliaçõews de hoteis : Google Hotels Reviews.
    args
        property_token : vem do resultado de pesquisar_voos()
    """
    return _chamar("google_hotels_reviews", {
        "property_token": property_token,
        "hl": idioma,
        "next_page_token": pagina_seguinte,
        **extra,
    }, api_key)


def fotos_hotel(property_token: str, idioma: str = "pt", api_key: str | None = None, **extra) -> dict:
    """Google Hotels Photos. [CONFIRMAR engine]"""
    return _chamar("google_hotels_photos", {"property_token": property_token, "hl": idioma, **extra}, api_key)



feer = [pesquisar_voos, opcoes_reserva_voo, resolver_lugar, autocompletar_voos, ofertas_voos, explorar_destinos, estado_voo_tempo_real, pesquisar_hoteis, detalhes_hotel, avaliacoes_hotel, fotos_hotel]
