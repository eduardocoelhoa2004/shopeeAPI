# Plano de Ação: Central das Ofertas (Automação de Imagens e Múltiplos Posts)

Este documento detalha o plano de engenharia para transformar o robô numa máquina capaz de publicar grades de ofertas (como o "TOP DESCONTOS") com imagens compostas automaticamente usando Python e Pillow.

## 🗄️ Fase 1: Preparar os Dados (Extrair Fotos da Shopee)
Ensinar a base de dados e a API da Shopee a puxar e guardar as fotografias dos produtos.

* **1.1. Atualizar o Modelo (`src/modules/shopee/models.py`)**
  * Adicionar a coluna: `image_url: Mapped[str] = mapped_column(String(2048), nullable=True)` à tabela `ShopeeOffer`.
* **1.2. Criar a Migração (Alembic)**
  * Rodar o comando para gerar a migração (`alembic revision --autogenerate`) e aplicá-la na base de dados (`alembic upgrade head`).
* **1.3. Atualizar o Cliente da Shopee (`src/modules/shopee/client.py`)**
  * Na query GraphQL do método `get_offer_list`, adicionar o campo de imagem (ex: `image` ou `imageUrl`) para que a Shopee devolva a foto do produto em alta resolução.
* **1.4. Atualizar o Serviço da Shopee (`src/modules/shopee/service.py`)**
  * Mapear o novo campo de imagem no método `_map_offer_fields` e guardá-lo no momento do `session.add(new_offer)`.

---

## 🧠 Fase 2: O Cérebro do Lote (Batching & Gemini)
Ensinar o robô a processar ofertas em pacotes (batches) em vez de apenas uma de cada vez.

* **2.1. Atualizar a IA (`src/infrastructure/external_apis/gemini.py`)**
  * Criar o método `generate_batch_caption(self, offers: list[dict])`.
  * Injetar o prompt do template "TOP OFERTAS DO DIA" com os 4 links organizados para a IA formatar o texto unificado.
* **2.2. Atualizar o Serviço do Facebook (`src/modules/facebook/service.py`)**
  * Alterar a busca na base de dados de `limit(1)` para buscar até 4 ofertas de uma vez (ex: `_get_next_unpublished_offers`).

---

## 🎨 Fase 3: O Estúdio de Arte (Python Pillow)
A fase da magia visual. Instalar a biblioteca gráfica e ensinar o Python a gerar o post como um designer.

* **3.1. Instalar Dependências (`requirements.txt`)**
  * Adicionar as bibliotecas `Pillow` (para manipulação de imagens) e `aiofiles` (para lidar com ficheiros assincronamente).
* **3.2. Criar o Serviço de Imagem (`src/infrastructure/image/generator.py`)**
  * Criar a classe `ImageGeneratorService`.
  * **Passos do gerador:**
    1. Descarregar as imagens da Shopee em memória.
    2. Abrir a máscara/template do Canva (ex: `template_grade.png`).
    3. Colar as fotos nas coordenadas (X, Y) exatas dos quadrados do layout.
    4. Escrever os preços correspondentes usando a fonte *Montserrat* na cor Amarela (`#FFC107`).
    5. Guardar a imagem finalizada temporariamente (ex: `output_ofertas.jpg`) para envio.

---

## 🚀 Fase 4: O Novo Carteiro do Facebook
Atualizar a integração com o Facebook para suportar o envio de ficheiros de imagem nativos.

* **4.1. Atualizar o Cliente do Facebook (`src/modules/facebook/client.py`)**
  * Criar o método `post_photo(self, message: str, image_path: str)`.
  * Mudar a rota do endpoint de `/{page_id}/feed` para `/{page_id}/photos`, enviando a imagem finalizada como *multipart/form-data*.
* **4.2. Orquestração Final (`src/modules/facebook/service.py`)**
  * Criar o maestro: o método `publish_offer_batch`. O fluxo será:
    1. Recolher 4 ofertas da base de dados.
    2. Enviar a lista para o Gemini gerar o texto da legenda.
    3. Enviar os URLs das imagens para o `ImageGeneratorService` criar a arte final da grade.
    4. Enviar a arte gerada e o texto para o `FacebookClient` publicar.
    5. Marcar as 4 ofertas como publicadas (`is_published_facebook = True`) na base de dados.