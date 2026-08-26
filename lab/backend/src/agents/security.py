import re
from collections import deque

# Patrones peligrosos (ataques)
DANGEROUS_PATTERNS = [
    r"ignora.*anteriores",          # Prompt injection
    r"eres un modelo sin restricciones",  # Jailbreak
    r"system prompt",               # Leakage
    r"muestra.*datos.*personales",  # Leakage
    r"ejecuta.*comando",            # Abuso de herramientas
    r"ignora.*instrucciones",       # Intento de ignorar reglas
    r"olvida.*instrucciones",       # Intento de ignorar reglas
    r"cambia.*identidad",           # Cambio de personalidad (variante más flexible)
    r"deja.*ser clara",             # Reinicio de contexto (variante más flexible)
    r"ya no eres clara",            # Cambio de personalidad
    r"eres otro sistema",            # Intento de suplantación
    r"modo sin restricciones",      # Jailbreak
    r"ahora eres (un|una|el|la)",   # Roleplay (más específico)
    r"actua como",                  # Roleplay (sin tilde)
    r"actúa como",                  # Roleplay (con tilde)
    r"payload.*split",              # Payload splitting
    r"divide.*mensaje",             # Payload splitting
]

# Historial de prompts por usuario (para detectar payload splitting)
user_prompt_history = {}

def is_safe_prompt(prompt: str) -> bool:
    """Valida que un prompt no contenga patrones peligrosos."""
    normalized_prompt = re.sub(r"\s+", " ", prompt.strip().lower())
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, normalized_prompt, re.IGNORECASE):
            return False
    return True

def is_safe_context(user_id: str, new_prompt: str) -> bool:
    """Valida que el contexto completo (historial + nuevo prompt) sea seguro."""
    if user_id not in user_prompt_history:
        user_prompt_history[user_id] = deque(maxlen=5)
    history = user_prompt_history[user_id]
    history.append(new_prompt)
    full_context = " ".join(history)
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, full_context, re.IGNORECASE):
            return False
    return True

def is_personality_consistent(response: str) -> bool:
    """Valida que la respuesta del LLM no indique un cambio de personalidad."""
    PERSONALITY_CHANGE_PATTERNS = [
        r"ahora soy",                  # Cambio de rol
        r"mi nombre es (?!clara)",    # Cambio de identidad (excluye "Mi nombre es Clara")
        r"soy un.*malicioso",          # Personalidad no autorizada
        r"olvida que soy clara",       # Intento de reinicio
        r"ya no soy clara",            # Cambio de personalidad
    ]
    for pattern in PERSONALITY_CHANGE_PATTERNS:
        if re.search(pattern, response, re.IGNORECASE):
            return False
    return True