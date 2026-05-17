import asyncio
import sys
import uvicorn

# 1. Força a política do Windows ANTES de importar a app e o loop iniciar
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# 2. Só importamos a app DEPOIS de ajustar a política do motor
from src.main import app

if __name__ == "__main__":
    # 3. Passamos a instância diretamente (app) e NÃO a string ("src.main:app")
    # Removido o reload=True para evitar a criação do Worker paralelo que quebra o motor
    uvicorn.run(app, host="127.0.0.1", port=8000)
