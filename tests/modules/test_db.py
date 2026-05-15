import asyncio
from sqlalchemy import text
from src.infrastructure.database.session import engine

async def testar_conexao():
    print("A tentar ligar à base de dados...")
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("✅ SUCESSO ABSOLUTO! A aplicação conseguiu ligar-se.")
    except Exception as e:
        print(f"\n❌ ERRO EXATO ENCONTRADO:\n{type(e).__name__}: {e}\n")

if __name__ == "__main__":
    asyncio.run(testar_conexao())