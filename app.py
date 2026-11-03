import os
import logging

import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

#from __future__ import annotations
from datetime import date, timedelta
from typing import Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

from ferramentas import feer 

BASE_URL = "https://serpapi.com/search.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SerpApiError(Exception):
    """Erro devolvido pela SerpApi ou falha de comunicação."""

load_dotenv()

# --- Configuração (tudo via variáveis de ambiente) ---------------------------
#PAGE_TOKEN = os.environ.get("PAGE_TOKEN", "")
#META_IG_TOKEN = os.environ.get("META_IG_TOKEN", "")
META_API_VERSION = os.environ.get("META_API_VERSION", "v25.0")
FB_VERIFY_TOKEN = os.environ.get("FB_VERIFY_TOKEN", "testejetur")
IG_VERIFY_TOKEN = os.environ.get("IG_VERIFY_TOKEN", "instagramjetur2026")
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
api_key = SERPAPI_KEY

#PAGE_TOKEN = os.environ.get("PAGE_TOKEN", "")
PAGE_TOKEN = "EAAUn7i7r9zcBS7OcXgsVhuNnvxSr0LxrZAA15xVOPzLjbrKJpCiGomXPYRtxPOvV3st93BggFOKzSDCAafZB8tlMivb7ZBDHUScNc2b5Ewuz2T9p2lpQJIyUAJCWdAAou57JiuCW6R8kpHqwMZCdqZBIvjqju3hD1ZAPSzcmdZBZCvccKeI1lA6hpmD0AUIu0XebRJ808QZDZD"
#META_IG_TOKEN = os.environ.get("META_IG_TOKEN", "")
META_IG_TOKEN = "IGAAvHOrT3ZCZCFBZAGFsSTNFd1N3dEh2R1RKQmRrdmN5UEdMcHAwMllWSkhyZAThoTlZASd1ZAXaU56ZAExhaU1fTS03a0s4ZA3B6UGZAnRDhwU1p2TVpuWHF0Q0tncUpENENKb0NBQ1NkM1o1RnpGU2dSUkNQYkJ3akJLbVBpZAjFMS0ZA1YwZDZD"

APP_NAME = "lISA"

app = Flask(__name__)


@app.route("/")
def home():
    return "Webhook On"


# --- Envio de mensagens --------------------------------------------------------
def _post(url: str, payload: dict, token: str) -> bool:
    try:
        r = requests.post(
            url,
            params={"access_token": token},
            json=payload,
            timeout=10,
        )
        if r.status_code != 200:
            logger.error(f"[meta] erro {r.status_code}: {r.text}")
            return False
        return True
    except requests.RequestException as e:
        logger.error(f"[meta] falha de rede: {e}")
        return False


def enviar_facebook(recipient_id: str, texto: str) -> bool:
    if not PAGE_TOKEN:
        logger.info(f"[facebook] (sem token) → {recipient_id}: {texto[:80]}")
        return True
    url = f"https://graph.facebook.com/{META_API_VERSION}/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": texto},
        "messaging_type": "RESPONSE",
    }
    return _post(url, payload, PAGE_TOKEN)


def enviar_instagram(recipient_id: str, texto: str) -> bool:
    if not META_IG_TOKEN:
        logger.info(f"[instagram] (sem token) → {recipient_id}: {texto[:80]}")
        return True
    url = f"https://graph.instagram.com/{META_API_VERSION}/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "messaging_type": "RESPONSE",
        "message": {"text": texto},
    }
    return _post(url, payload, META_IG_TOKEN)


# --- Agente --------------------------------------------------------------------
agente = Agent(
    name="Lisa",
    model="gemini-3.8-flash",  # confirma que este modelo existe na tua conta
    instruction="""
        Voçê é um agente de suporte de viagens, consegues fazer pesquisas de voos, reservas de hoteis, pesquisar destinos, etc.
        Responda amigavelmente e seja sempre claro. Dê respostas mais resumidas focadas no objectivo.     
    """,
    tools= feer
)

session_service = InMemorySessionService()
runner = Runner(agent=agente, app_name=APP_NAME, session_service=session_service)


async def garantir_sessao(user_id: str, session_id: str):
    sessao = await session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    if sessao is None:
        await session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )


async def perguntar_ao_agente(user_id: str, pergunta: str):
    await garantir_sessao(user_id, user_id)
    mensagem = types.Content(role="user", parts=[types.Part(text=pergunta)])

    resposta = None
    async for ev in runner.run_async(
        user_id=user_id, session_id=user_id, new_message=mensagem
    ):
        if ev.is_final_response() and ev.content and ev.content.parts:
            resposta = ev.content.parts[0].text
    return resposta

@app.post("/receber")
async def chat():
    dados = request.get_json(silent=True) or {} # Pegando os dados que serão inseridos nesse endpoint
    # Armazenando os dados em cada variável
    pergunta = dados.get("pergunta")
    user_id = dados.get("user_id", "u1")
    session_id = dados.get("session_id", "s1")

    # Verifica se a variável "pergunta" esta vazia ou não
    if not pergunta:
        return jsonify({"erro": "O campo 'pergunta' é obrigatório."}), 400

    # Executando a sessão
    await garantir_sessao(user_id, session_id)

    # Tratando as mensagens dos usuários para um formato que o bot entenda
    mensagem = types.Content(role="user", parts=[types.Part(text=pergunta)])
    
    ferramentas = [] # Criando uma variável para armazenar as ferramentas que o bot usou se caso queira saber quais ferramentas ele usou na conversa
    resposta = None

    # Processando a mensagem do usuário para o bot gerar uma resposta em seguida
    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=mensagem
    ):
        for call in event.get_function_calls():
            ferramentas.append({"nome": call.name, "args": dict(call.args)})
        if event.is_final_response() and event.content:
            resposta = event.content.parts[0].text

    # Retornando um json final contendo a reposta do bot, a sessão da conversa e a lista de ferramentas usando pelo bot
    return jsonify(
        {
            "session_id": session_id,
            "resposta": resposta,
            "ferramentas_usadas": ferramentas,
        }
    )



# --- Webhook do Facebook Messenger ---------------------------------------------
@app.route("/facebook", methods=["GET", "POST"])
async def facebook_webhook():
    # 1. Validação (GET)
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        verify_token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and verify_token == FB_VERIFY_TOKEN:
            logger.info("Facebook webhook verificado com sucesso.")
            return challenge, 200
        logger.warning("Falha na verificação do Facebook webhook.")
        return "Token de verificação inválido", 403

    # 2. Receber mensagens (POST)
    body = request.get_json(silent=True)
    if not body or body.get("object") != "page":
        return "Not Found", 404

    try:
        for entry in body.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event.get("sender", {}).get("id")
                msg = event.get("message", {})

                if not sender_id or msg.get("is_echo") or not msg.get("text"):
                    continue

                logger.info(f"Facebook msg de {sender_id}: {msg['text']}")
                resposta = await perguntar_ao_agente(sender_id, msg["text"])

                if resposta:
                    enviar_facebook(sender_id, resposta)
    except Exception as e:
        logger.error(f"Erro no webhook do Facebook: {e}")

    # Responde sempre 200 para a Meta não reenviar o mesmo evento
    return "EVENT_RECEIVED", 200


# --- Webhook do Instagram ------------------------------------------------------
@app.route("/webhook/instagram", methods=["GET", "POST"])
async def instagram_webhook():
    # 1. Validação (GET)
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        verify_token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and verify_token == IG_VERIFY_TOKEN:
            logger.info("Instagram webhook verificado com sucesso.")
            return challenge, 200
        logger.warning("Falha na verificação do Instagram webhook.")
        return "Token de verificação inválido", 403

    # 2. Receber mensagens (POST)
    body = request.get_json(silent=True)
    logger.info(f"Instagram webhook payload: {body}")

    if not body or body.get("object") not in ("instagram", "page"):
        return "Not Found", 404

    try:
        for entry in body.get("entry", []):
            for event in entry.get("messaging", []):
                sender_igsid = event.get("sender", {}).get("id")
                msg = event.get("message", {})

                if not sender_igsid or msg.get("is_echo") or not msg.get("text"):
                    continue

                logger.info(f"Instagram msg de {sender_igsid}: {msg['text']}")
                resposta = await perguntar_ao_agente(sender_igsid, msg["text"])
                enviar_instagram(sender_igsid, resposta)
    except Exception as e:
        logger.error(f"Erro ao processar POST do Instagram: {e}")

    return "EVENT_RECEIVED", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
