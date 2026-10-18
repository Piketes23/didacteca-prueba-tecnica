import re


def detect_conflicts(action: str, instructions: str) -> list[str]:
    """Detecta valores contradictorios que el usuario pidió en la misma solicitud."""
    conflicts = []

    if action == "quiz":
        counts = sorted({int(n) for n in re.findall(r"(\d+)\s*preguntas?", instructions, re.I)})
        if len(counts) > 1:
            conflicts.append(
                "pides cantidades distintas de preguntas: " + ", ".join(map(str, counts))
            )

    if action == "activity":
        minutes = sorted({int(n) for n in re.findall(r"(\d+)\s*min", instructions, re.I)})
        if len(minutes) > 1:
            conflicts.append(
                "pides duraciones distintas: " + ", ".join(f"{m} min" for m in minutes)
            )

    return conflicts