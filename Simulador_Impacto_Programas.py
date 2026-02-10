import streamlit as st
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
import seaborn as sns
from fpdf import FPDF
from datetime import datetime
import tempfile
import os

# --- MOTOR DE BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('mv_governança_v2.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS recursos_projeto (
        id INTEGER PRIMARY KEY AUTOINCREMENT, projeto TEXT, gerente TEXT, recurso TEXT, 
        categoria TEXT, custo_hora REAL, horas INTEGER, subtotal REAL, data_registro TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS historico_pareceres (
        id INTEGER PRIMARY KEY AUTOINCREMENT, projeto TEXT, gerente TEXT, justificativa_cat TEXT, 
        valor_projeto REAL, margem_original REAL, impacto_financeiro REAL, parecer_texto TEXT, data_emissao TEXT)''')
    conn.commit()
    return conn

# --- CLASSE PDF EXECUTIVA ---
class ExecutiveReport(FPDF):
    def __init__(self, projeto, gerente):
        super().__init__()
        self.projeto = projeto
        self.gerente = gerente

    def header(self):
        self.set_fill_color(15, 20, 25) # Cinza Grafite Profundo
        self.rect(0, 0, 210, 30, 'F')
        self.set_font("Arial", 'B', 14); self.set_text_color(255) 
        self.cell(190, 10, "MV PORTFOLIO INTELLIGENCE - PARECER TECNICO", ln=True, align='C')
        self.set_font("Arial", '', 8); self.set_text_color(200)
        self.cell(190, 5, f"Programa: {self.projeto} | Responsavel: {self.gerente}", ln=True, align='C')
        self.ln(5)

    def add_signatures(self):
        self.set_y(250); curr_y = self.get_y()
        self.line(25, curr_y + 10, 85, curr_y + 10); self.line(125, curr_y + 10, 185, curr_y + 10)
        self.set_font("Arial", 'B', 9); self.set_text_color(0)
        self.set_y(curr_y + 12); self.set_x(25); self.cell(60, 5, self.gerente, 0, 0, 'C')
        self.set_x(125); self.cell(60, 5, "DIRETOR DE OPERACOES", 0, 1, 'C')

# --- CONFIGURAÇÃO E TEMA ---
st.set_page_config(page_title="MV Impact Program", layout="wide")
conn = init_db()
sns.set_theme(style="whitegrid") # Whitegrid nos gráficos para legibilidade total

# Cores Acessíveis
CYAN_ACCESSIBLE = "#00D4FF"  # Ciano mais brilhante
ORANGE_ACCESSIBLE = "#FF9F00" # Laranja mais saturado
BG_DARK = "#0E1117"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {BG_DARK}; color: white; }}
    /* Melhorando a cor dos textos das métricas e descrições */
