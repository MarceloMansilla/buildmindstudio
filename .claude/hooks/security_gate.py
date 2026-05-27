#!/usr/bin/env python3
"""
PreToolUse hook: Security gate para PayFlow API.
Bloquea comandos peligrosos y acceso a archivos sensibles.
Usa JSON decision control (permissionDecision) para dar razones claras.
"""
import sys
import json
import re


def check_bash_command(cmd: str) -> tuple[bool, str]:
    """Verifica si un comando Bash es seguro. Retorna (bloqueado, razón)."""
    dangerous_patterns = [
        (r"rm\s+(-[rf]+\s+|.*--no-preserve-root)", "Borrado recursivo/forzado"),
        (r"git\s+(reset\s+--hard|push\s+(-f|--force))", "Operación git destructiva"),
        (r"sudo\s+", "Ejecución con privilegios elevados"),
        (r"chmod\s+777", "Permisos excesivamente permisivos"),
        (r"(curl|wget).*\|\s*(ba)?sh", "Ejecución de script remoto por pipe"),
        (r"DROP\s+(TABLE|DATABASE)", "Borrado de estructura de BD"),
        (r"DELETE\s+FROM\s+\w+\s*;?\s*$", "DELETE sin WHERE"),
    ]
    for pattern, reason in dangerous_patterns:
        if re.search(pattern, cmd, re.IGNORECASE):
            return True, reason

    sensitive_files = [
        ".env", ".env.local", ".env.production",
        "id_rsa", "id_ed25519", ".pem", ".key",
    ]
    for f in sensitive_files:
        if f in cmd:
            return True, f"Acceso a archivo sensible: {f}"

    prod_patterns = [
        (r"(psql|mysql|mongo).*prod", "Cliente de BD apuntando a producción"),
        (r"ssh.*prod", "SSH a servidor de producción"),
    ]
    for pattern, reason in prod_patterns:
        if re.search(pattern, cmd, re.IGNORECASE):
            return True, reason

    return False, ""


def check_file_write(file_path: str) -> tuple[bool, str]:
    """Verifica si la escritura a un archivo es segura."""
    protected = [
        (r"\.env($|\.)", "Archivo de variables de entorno"),
        (r"(id_rsa|id_ed25519|\.pem|\.key)$", "Archivo de claves privadas"),
        (r"alembic/versions/.*\.py$", "Migración de BD (requiere revisión manual)"),
    ]
    for pattern, reason in protected:
        if re.search(pattern, file_path, re.IGNORECASE):
            return True, reason
    return False, ""


def main():
    input_data = json.load(sys.stdin)
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    blocked = False
    reason = ""

    if tool_name == "Bash":
        blocked, reason = check_bash_command(tool_input.get("command", ""))
    elif tool_name in ("Write", "Edit", "MultiEdit"):
        blocked, reason = check_file_write(tool_input.get("file_path", ""))

    if blocked:
        json.dump({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Bloqueado por política de seguridad: {reason}"
            }
        }, sys.stdout)

    sys.exit(0)


if __name__ == "__main__":
    main()