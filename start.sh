#!/bin/bash

# 1. Garante que a pasta temporária existe
mkdir -p tmp_uploads

# 2. Inicia o Worker em background (esse '&' no final é o segredo)
python -m infra.workers.listener &

# 3. Inicia a API no processo principal
# O Railway injeta a variável $PORT automaticamente
uvicorn main:app --host 0.0.0.0 --port $PORT