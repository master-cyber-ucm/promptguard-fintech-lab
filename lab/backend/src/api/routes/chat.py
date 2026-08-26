from fastapi import APIRouter, Request
from collections import deque

# Importaciones corregidas (ruta absoluta desde src/)
from src.agents.clara_simple import get_clara_agent_simple
from src.agents.clara_complex import get_clara_agent_complex
from src.agents.security import (
    is_safe_prompt,
    is_safe_context,
    is_personality_consistent,
    user_prompt_history,
)

router = APIRouter(prefix="/chat")

@router.post("/simple-prompt")
async def chat_simple(request: Request):
    print("######### HE ENTRADO EN CHAT_SIMPLE #########")

    agent = get_clara_agent_simple()
    data = await request.json()

    print("BODY RECIBIDO:")
    print(data)

    user_prompt = data.get("prompt", "")

    print("PROMPT EXTRAIDO:")
    print(repr(user_prompt))

    user_id = data.get("user_id", "unknown")

    # Validar longitud del prompt
    if len(user_prompt) > 500:
        return {"error": "El prompt es demasiado largo"}, 403

    # Validar caracteres sospechosos (payload splitting)
    SUSPICIOUS_CHARS = ["\n", "---", "<<<", ">>>"]
    if any(char in user_prompt for char in SUSPICIOUS_CHARS):
        return {"error": "El prompt contiene caracteres no permitidos"}, 403

    # Validar prompt individual
    if not is_safe_prompt(user_prompt):
        return {"error": "Prompt bloqueado por políticas de seguridad"}, 403

    # Validar contexto completo (payload splitting)
    if not is_safe_context(user_id, user_prompt):
        return {"error": "Contexto bloqueado por políticas de seguridad"}, 403

    # Llamar al agente y depuración temporal
    result = await agent.run(user_prompt)

    print("=" * 80)
    print("TIPO:", type(result))
    print("RESULTADO:", result)
    print("OUTPUT:", result.output)
    print("OUTPUT TYPE:", type(result.output))

    # Si existe información de mensajes, imprimirla
    if hasattr(result, "all_messages"):
        print("MENSAJES:")
        try:
            print(result.all_messages())
        except Exception as e:
            print(e)

    print("=" * 80)

    response = str(result.output)

    # Validar consistencia de personalidad
    if not is_personality_consistent(response):
        user_prompt_history[user_id] = deque(maxlen=5)
        return {
            "response": "Mi personalidad es inmutable. Solo soy Clara, tu asistente bancario. La conversación se ha reiniciado por seguridad.",
            "context_reset": True
        }, 403

    return {"response": response}

@router.post("/complex-prompt")
async def chat_complex(request: Request):
    print("######### HE ENTRADO EN CHAT_COMPLEX #########")

    agent = get_clara_agent_complex()
    data = await request.json()

    print("BODY RECIBIDO:")
    print(data)

    user_prompt = data.get("prompt", "")

    print("PROMPT EXTRAIDO:")
    print(repr(user_prompt))

    user_id = data.get("user_id", "unknown")

    if len(user_prompt) > 500:
        return {"error": "El prompt es demasiado largo"}, 403

    SUSPICIOUS_CHARS = ["\n", "---", "<<<", ">>>"]
    if any(char in user_prompt for char in SUSPICIOUS_CHARS):
        return {"error": "El prompt contiene caracteres no permitidos"}, 403

    if not is_safe_prompt(user_prompt):
        return {"error": "Prompt bloqueado por políticas de seguridad"}, 403

    if not is_safe_context(user_id, user_prompt):
        return {"error": "Contexto bloqueado por políticas de seguridad"}, 403

    # Llamar al agente y depuración temporal
    result = await agent.run(user_prompt)

    print("=" * 80)
    print("TIPO:", type(result))
    print("RESULTADO:", result)
    print("OUTPUT:", result.output)
    print("OUTPUT TYPE:", type(result.output))

    # Si existe información de mensajes, imprimirla
    if hasattr(result, "all_messages"):
        print("MENSAJES:")
        try:
            print(result.all_messages())
        except Exception as e:
            print(e)

    print("=" * 80)

    response = str(result.output)

    if not is_personality_consistent(response):
        user_prompt_history[user_id] = deque(maxlen=5)
        return {
            "response": "Mi personalidad es inmutable. Solo soy Clara, tu asistente bancario. La conversación se ha reiniciado por seguridad.",
            "context_reset": True
        }, 403

    return {"response": response}

@router.post("/complex-with-context")
async def chat_complex_with_context(request: Request):
    print("######### HE ENTRADO EN CHAT_COMPLEX_CONTEXT #########")

    agent = get_clara_agent_complex()
    data = await request.json()

    print("BODY RECIBIDO:")
    print(data)

    user_prompt = data.get("prompt", "")

    print("PROMPT EXTRAIDO:")
    print(repr(user_prompt))

    user_id = data.get("user_id", "unknown")

    if len(user_prompt) > 500:
        return {"error": "El prompt es demasiado largo"}, 403

    SUSPICIOUS_CHARS = ["\n", "---", "<<<", ">>>"]
    if any(char in user_prompt for char in SUSPICIOUS_CHARS):
        return {"error": "El prompt contiene caracteres no permitidos"}, 403

    if not is_safe_prompt(user_prompt):
        return {"error": "Prompt bloqueado por políticas de seguridad"}, 403

    if not is_safe_context(user_id, user_prompt):
        return {"error": "Contexto bloqueado por políticas de seguridad"}, 403

    # Llamar al agente y depuración temporal
    result = await agent.run(user_prompt)

    print("=" * 80)
    print("TIPO:", type(result))
    print("RESULTADO:", result)
    print("OUTPUT:", result.output)
    print("OUTPUT TYPE:", type(result.output))

    # Si existe información de mensajes, imprimirla
    if hasattr(result, "all_messages"):
        print("MENSAJES:")
        try:
            print(result.all_messages())
        except Exception as e:
            print(e)

    print("=" * 80)

    response = str(result.output)

    if not is_personality_consistent(response):
        user_prompt_history[user_id] = deque(maxlen=5)
        return {
            "response": "Mi personalidad es inmutable. Solo soy Clara, tu asistente bancario. La conversación se ha reiniciado por seguridad.",
            "context_reset": True
        }, 403

    return {"response": response}