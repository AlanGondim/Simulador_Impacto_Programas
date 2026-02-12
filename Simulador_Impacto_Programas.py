import streamlit as st
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from fpdf import FPDF
from datetime import datetime
import tempfile
import os

# --- FUNÇÕES DE APOIO ---
def format_moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def calcular_pert(o, m, p):
    return (o + 4 * m + p) / 6

# --- BANCO DE DADOS (V14 - Correção de Schema) ---
def init_db():
    conn = sqlite3.connect('mv_simulador_impacto_programas.db')
    cursor = conn.cursor()
    # Criar tabelas se não existirem
    cursor.execute('''CREATE TABLE IF NOT EXISTS recursos_projeto 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, projeto TEXT, função TEXT, 
        senioridade TEXT, custo_hora REAL, horas INTEGER, subtotal REAL, data_registro TEXT)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS historico_pareceres 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, projeto TEXT, gerente TEXT, justificativa TEXT, 
        receita REAL, custos_atuais REAL, margem_anterior REAL, impacto_financeiro REAL, 
        p_otimista REAL, p_pessimista REAL, p_pert_resultado REAL, total_horas INTEGER, data_emissao TEXT)''')
    
    # Verificação amigável de colunas (Migrations manuais)
    cursor.execute("PRAGMA table_info(historico_pareceres)")
    colunas = [col[1] for col in cursor.fetchall()]
    if "total_horas" not in colunas:
        cursor.execute("ALTER TABLE historico_pareceres ADD COLUMN total_horas INTEGER")
    if "p_pert_resultado" not in colunas:
        cursor.execute("ALTER TABLE historico_pareceres ADD COLUMN p_pert_resultado REAL")
        
    conn.commit()
    return conn

# --- CLASSE PDF EXECUTIVA MASTER ---
class ExecutiveReport(FPDF):
    def __init__(self, dados):
        super().__init__()
        self.d = dados

    def header(self):
        self.set_fill_color(0, 51, 102); self.rect(0, 0, 210, 45, 'F')
        self.set_font("Arial", 'B', 18); self.set_text_color(255)
        self.cell(190, 15, "DOSSIÊ ESTRATÉGICO DE REEQUILÍBRIO FINANCEIRO", ln=True, align='C')
        self.set_font("Arial", 'B', 10)
        self.cell(190, 5, f"PROGRAMA: {self.d['projeto']} | GERENTE: {self.d['gerente'].upper()}", ln=True, align='C')
        self.ln(20)

    def section_header(self, title):
        self.set_font("Arial", 'B', 11); self.set_fill_color(230, 230, 230); self.set_text_color(0, 51, 102)
        self.cell(190, 10, f"  {title}", ln=True, fill=True); self.ln(4)

# --- INTERFACE ---
st.set_page_config(page_title="Simulador Impacto PRO", layout="wide")
conn = init_db()

st.sidebar.title("🛡️ MV SIMULADOR IMPACTO PROGRAMAS")
aba = st.sidebar.radio("Navegação", ["Nova Análise", "Hub de Inteligência"], key="main_nav")

if aba == "Nova Análise":
    st.markdown("<h2 style='color: #003366;'>📋 1. INFORMAÇÕES GERAIS DO PROGRAMA</h2>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        progs = [" ", "INS", "UNIMED SERRA GAUCHA", "UNIMED NORTE FLUMINENSE", "CLINICA GIRASSOL", "GUATEMALA", "GOOD HOPE","EINSTEIN", "MOGI DAS CRUZES", "SESA/ES", "CEMA", "SESI/RS"]
        nome_projeto = st.selectbox("1.1. Selecione o programa", progs)
    with c2:
        gerente_nome = st.text_input("1.2. Gerente do Programa")
    justificativa = st.text_area("1.3. Justificativa do impacto")

    st.markdown("<h2 style='color: #003366;'>📊 2. ESTRUTURA ATUAL DE CUSTOS</h2>", unsafe_allow_html=True)
    cc1, cc2, cc3 = st.columns(3)
    with cc1: receita = st.number_input("2.1. Receita Líquida (R$)", min_value=0.0, step=1000.0, value=1000.0, format="%.2f")
    with cc2: custos_at = st.number_input("2.2. Custos totais (R$)", min_value=0.0, step=1000.0, value=1000.0, format="%.2f")
    with cc3:
        m_atual = ((receita - custos_at) / receita * 100) if receita > 0 else 0
        st.metric("2.3. Margem atual", f"{m_atual:.2f}%")

    st.markdown("<h2 style='color: #003366;'>👥 3. DIMENSIONAMENTO DE IMPACTO</h2>", unsafe_allow_html=True)
    with st.form("recurso_form"):
        f1, f2, f3, f4 = st.columns([2, 2, 1, 1])
        func = f1.selectbox("Função", [" ","Gerente", "Analista", "Consultor", "Dev"])
        seni = f2.selectbox("Senioridade", ["Junior", "Pleno", "Senior"])
        vh = f3.number_input("R$/Hora", value=150.0)
        hrs = f4.number_input("Horas", min_value=1)
        if st.form_submit_button("➕ Adicionar Recurso"):
            conn.cursor().execute("INSERT INTO recursos_projeto (projeto, função, senioridade, custo_hora, horas, subtotal, data_registro) VALUES (?,?,?,?,?,?,?)",
                                   (nome_projeto, func, seni, vh, hrs, vh*hrs, datetime.now().isoformat()))
            conn.commit()

    df_rec = pd.read_sql_query(f"SELECT função, senioridade, horas, subtotal FROM recursos_projeto WHERE projeto = '{nome_projeto}'", conn)
    if not df_rec.empty:
        st.table(df_rec.assign(subtotal=df_rec['subtotal'].apply(format_moeda)))
        c_provavel = df_rec['subtotal'].sum()
        total_hrs = int(df_rec['horas'].sum())
        
        c1p, c2p = st.columns(2)
        with c1p:
            st.info(f"**3.1. Custo Provável:** {format_moeda(c_provavel)}")
            c_ot = st.number_input("3.2. Custo Otimista (Manual)", value=0.0)
            c_pe = st.number_input("3.3. Custo Pessimista (Manual)", value=0.0)
            res_pert = calcular_pert(c_ot, c_provavel, c_pe) if (c_ot > 0 and c_pe > 0) else 0
            st.success(f"**Cenário PERT:** {format_moeda(res_pert)}")
            
        with c2p:
            m_pos = (((receita - custos_at) - c_provavel) / receita * 100) if receita > 0 else 0
            fig, ax = plt.subplots(figsize=(6, 4))
            valores = [m_atual, m_pos]
            sns.barplot(x=['Margem Atual', 'Margem Pós-Impacto'], y=valores, palette=['#003366', '#C0392B'], ax=ax)
            for i, v in enumerate(valores):
                ax.text(i, v + 0.5, f"{v:.2f}%", ha='center', fontweight='bold')
            st.pyplot(fig)

    if st.button("🚀 Protocolar Dossiê"):
        # CORREÇÃO: Inserção nomeando as colunas para evitar o OperationalError de contagem
        sql = '''INSERT INTO historico_pareceres 
                 (projeto, gerente, justificativa, receita, custos_atuais, margem_anterior, 
                  impacto_financeiro, p_otimista, p_pessimista, p_pert_resultado, total_horas, data_emissao) 
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?)'''
        conn.cursor().execute(sql, (nome_projeto, gerente_nome, justificativa, receita, custos_at, m_atual, 
                                    c_provavel, c_ot, c_pe, res_pert, total_hrs, datetime.now().isoformat()))
        conn.commit(); st.success("Dossiê Protocolado!")

else:
    st.header("📚 Hub de Inteligência")
    df_h = pd.read_sql_query("SELECT * FROM historico_pareceres ORDER BY data_emissao DESC", conn)
    
    for i, row in df_h.iterrows():
        with st.expander(f"📋 {row['projeto']} | Impacto: {format_moeda(row['impacto_financeiro'])}"):
            if st.button(f"📥 Baixar PDF Detalhado", key=f"pdf_{row['id']}"):
                pdf = ExecutiveReport(row.to_dict()); pdf.add_page()
                
                pdf.section_header("1. INFORMAÇÕES GERAIS E JUSTIFICATIVA")
                pdf.set_font("Arial", '', 10)
                pdf.multi_cell(190, 7, f"Gerente: {row['gerente']}\nJustificativa: {row['justificativa']}")
                
                pdf.ln(5); pdf.section_header("2. ANALISE DE IMPACTO NA MARGEM")
                m_pos_h = (((row['receita'] - row['custos_atuais']) - row['impacto_financeiro']) / row['receita'] * 100) if row['receita'] > 0 else 0
                pdf.cell(95, 8, "Receita Liquida", 1); pdf.cell(95, 8, format_moeda(row['receita']), 1, 1)
                pdf.cell(95, 8, "Margem Anterior", 1); pdf.cell(95, 8, f"{row['margem_anterior']:.2f}%", 1, 1)
                pdf.cell(95, 8, "Margem Atualizada", 1); pdf.cell(95, 8, f"{m_pos_h:.2f}%", 1, 1)
                
                pdf.ln(5); pdf.section_header("3. GRAU DE CONFIANÇA SINTÉTICO (PERT)")
                detalhe_pert = (f"Com base no esforco de {row['total_horas']} horas adicionais, a analise de confianca "
                                f"identificou um custo provavel de {format_moeda(row['impacto_financeiro'])}. "
                                f"A variabilidade estatistica (PERT) projeta uma exposicao de {format_moeda(row['p_pert_resultado'])} "
                                f"considerando os cenarios otimista e pessimista informados.")
                pdf.multi_cell(190, 7, detalhe_pert)
                
                st.download_button("Salvar PDF", bytes(pdf.output(dest='S')), f"DOSSIE_{row['projeto']}.pdf")







