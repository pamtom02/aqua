import asyncio
from typing import Any


async def simulate_execution(config: dict[str, Any]) -> dict[str, Any]:
    scene_id = config.get("scene_id", "")
    if scene_id == "scene_fail":
        raise RuntimeError(
            "Excepción interna: Fallo al procesar los tensores de la escena."
        )
    if scene_id == "scene_timeout":
        await asyncio.sleep(2.0)
    else:
        await asyncio.sleep(0.1)
    return {"accuracy": 0.98, "processed_pixels": 102400}
