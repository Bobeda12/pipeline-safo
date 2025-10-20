#!/usr/bin/env bash
# exit on error
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

# GERA O BANCO DE DADOS E OS EMBEDDINGS NA HORA DO DEPLOY
# python gerar_banco_grande.py # Opcional, pode ser lento no deploy
# python pre_calcular_embeddings_ime.py # Opcional, pode ser lento no deploy-