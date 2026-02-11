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
import urllib.parse

# --- FUNÇÕES DE APOIO ---
def format_moeda(valor):
    """Formata para o padrão brasileiro R$ 1.000,00"""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def calcular_pert(o, m, p):
    """Cálculo PERT: (O + 4M + P) / 6 e Desvio Padrão: (P - O) / 6"""
    media = (o + 4 * m + p) / 6
    desvio = (p - o) / 6
    return media, desvio

# --- BANCO DE DADOS (SCHEMA AMPLIADO) ---
def init_db():
    conn = sqlite3.connect('mv_governança_v5.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS recursos_projeto 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, projeto TEXT, gerente TEXT, recurso TEXT, 
        categoria TEXT, custo_hora REAL, horas INTEGER, subtotal REAL, data_registro TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS historico_pareceres 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, projeto TEXT, gerente TEXT, justificativa_cat TEXT, 
        valor_projeto REAL, margem_original REAL, impacto_financeiro REAL, parecer_texto TEXT, 
        detalhamento TEXT, p_custo_media REAL, p_prazo_media REAL, r_escopo INTEGER, 
        r_custo REAL, r_prazo INTEGER, data_emissao TEXT)''')
    conn.commit()
    return conn

# --- CLASSE PDF MASTER ---
class ExecutiveReport(FPDF):
    def __init__(self, projeto, gerente):
        super().__init__()
        self.projeto = projeto
        self.gerente = gerente

    def header(self):
        self.set_fill_color(0, 51, 102) # Azul Marinho MV
        self.rect(0, 0, 210, 35, 'F')
        self.set_font("Arial", 'B', 15); self.set_text_color(255)
        self.cell(190, 10, "MV PORTFOLIO INTELLIGENCE - DOSSIÊ DE RISCO PRO", ln=True, align='C')
        self.set_font("Arial", '', 9)
        self.cell(190, 5, f"Programa: {self.projeto} | Gerente do Programa: {self.gerente}", ln=True, align='C')
        self.ln(20)

    def footer_signatures(self):
        self.set_y(260)
        self.line(25, self.get_y(), 85, self.get_y())
        self.line(125, self.get_y(), 185, self.get_y())
        self.set_font("Arial", 'B', 9); self.set_text_color(0)
        self.set_x(25); self.cell(60, 5, self.gerente, align='C')
        self.set_x(125); self.cell(60, 5, "DIRETOR DE OPERAÇÕES", align='C')

# --- CONFIGURAÇÃO STREAMLIT ---
st.set_page_config(page_title="Simulador Impact Programa PRO", layout="wide")
conn = init_db()
sns.set_theme(style="whitegrid")

st.sidebar.title("🛡️ Sentinel PRO V5")
aba = st.sidebar.radio("Navegação", ["Nova Análise", "Hub de Inteligência"])

if aba == "Nova Análise":
    st.markdown("<h2 style='color: #003366;'>📋 Registro e Simulação de Impacto</h2>", unsafe_allow_html=True)
    
    # 1. IDENTIFICAÇÃO DO PROGRAMA
    c1, c2 = st.columns([2, 2])
    with c1: 
        prog_list = ["INS", "UNIMED SERRA GAUCHA", "UNIMED NORTE FLUMINENSE", "CLINICA GIRASSOL", 
                     "GUATEMALA", "GOOD HOPE", "EINSTEIN", "MOGI DAS CRUZES", "SESA/ES", "CEMA", "RHP", "SESI/RS"]
        nome_projeto = st.selectbox("Selecione o Programa", prog_list)
    with c2: 
        gerente_nome = st.text_input("Gerente do Programa")
    
    just_cats = st.multiselect("Justificativas do Desvio (Múltipla Seleção)", 
                               ["Mudança de Go Live", "Retreinamento", "Alteração Especificações Funcionais", 
                                "Infraestrutura", "Versão Produto", "Erro de Estimativa"])

    # 2. LANÇAMENTO DINÂMICO
    st.subheader("👥 Alocação de Esforço em Tempo Real")
    with st.form("form_rec", clear_on_submit=True):
        col_rec, col_per, col_vh, col_h = st.columns([3, 2, 1, 1])
        with col_rec: r_nome = st.text_input("Nome do Recurso")
        with col_per: r_perfil = st.selectbox("Perfil", ["Consultor", "Analista", "Dev", "Gerente"])
        with col_vh: r_vh = st.number_input("R$/Hora", value=150.0)
        with col_h: r_hrs = st.number_input("Horas", min_value=1)
        if st.form_submit_button("➕ Inserir Linha"):
            if nome_projeto and r_nome:
                conn.cursor().execute("INSERT INTO recursos_projeto (projeto, gerente, recurso, categoria, custo_hora, horas, subtotal, data_registro) VALUES (?,?,?,?,?,?,?,?)",
                                       (nome_projeto, gerente_nome, r_nome, r_perfil, r_vh, r_hrs, r_vh*r_hrs, datetime.now().isoformat()))
                conn.commit()

    df_db = pd.read_sql_query(f"SELECT recurso, horas, subtotal FROM recursos_projeto WHERE projeto = '{nome_projeto}'", conn)
    if not df_db.empty:
        st.table(df_db.assign(subtotal=df_db['subtotal'].apply(format_moeda)))
        total_extra = df_db['subtotal'].sum()
    else: total_extra = 0.0

    # 3. MODELAGEM PERT (CUSTO E PRAZO)
    st.markdown("---")
    st.subheader("🎲 Modelagem de Incerteza (Análise PERT)")
    
    col_pc1, col_pc2 = st.columns(2)
    with col_pc1:
        st.caption("Cenários de Custo (Financeiro)")
        c_o = st.number_input("Otimista (R$)", value=total_extra * 0.9, key="co")
        c_m = st.number_input("Provável (R$)", value=total_extra, key="cm")
        c_p = st.number_input("Pessimista (R$)", value=total_extra * 1.4, key="cp")
        media_c, d_c = calcular_pert(c_o, c_m, c_p)
    
    with col_pc2:
        st.caption("Cenários de Prazo (Dias Adicionais)")
        d_o = st.number_input("Otimista (Dias)", value=5, key="do")
        d_m = st.number_input("Provável (Dias)", value=10, key="dm")
        d_p = st.number_input("Pessimista (Dias)", value=25, key="dp")
        media_d, d_d = calcular_pert(d_o, d_m, d_p)
    
    st.info(f"💡 **Expectativa PERT:** Custo Médio {format_moeda(media_c)} | Atraso Médio: {media_d:.1f} dias.")

    # 4. RADAR CHART (TRIÂNGULO DE FERRO)
    st.subheader("📐 Impacto nas Restrições")
    r_esc = st.slider("Impacto em Escopo (1-10)", 1, 10, 5)
    r_pra = st.slider("Impacto em Prazo (1-10)", 1, 10, 5)
    r_cus = (total_extra / 50000) * 10 # Normalização
    
    # Criando gráfico menor e amarelo
    categories = ['Escopo', 'Custo', 'Prazo']
    values = [r_esc, r_cus, r_pra]
    values += values[:1]
    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
    angles += angles[:1]

    fig_radar, ax = plt.subplots(figsize=(3, 3), subplot_kw=dict(polar=True))
    ax.plot(angles, values, color='yellow', linewidth=2)
    ax.fill(angles, values, color='orange', alpha=0.3, hatch='///')
    ax.set_yticklabels([])
    plt.xticks(angles[:-1], categories, color='grey', size=8)
    st.pyplot(fig_radar)

    # 5. JUSTIFICATIVA E PARECER
    st.subheader("📝 Detalhamento das Justificativas")
    desc_detalhada = st.text_area("Descreva tecnicamente as causas e o plano de mitigação para aprovação:")

    if st.button("🚀 Protocolar Dossiê Final"):
        conn.cursor().execute('''INSERT INTO historico_pareceres 
            (projeto, gerente, justificativa_cat, valor_projeto, margem_original, impacto_financeiro, 
             parecer_texto, detalhamento, p_custo_media, p_prazo_media, r_escopo, r_custo, r_prazo, data_emissao) 
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', 
            (nome_projeto, gerente_nome, ", ".join(just_cats), 1000000.0, 35.0, total_extra, 
             "Parecer Gerencial", desc_detalhada, media_c, media_d, r_esc, r_cus, r_pra, datetime.now().isoformat()))
        conn.commit(); st.balloons()

# --- HUB DE INTELIGÊNCIA (INTERATIVO) ---
else:
    st.header("📚 Intelligence Hub: Histórico de Pareceres")
    df_h = pd.read_sql_query("SELECT * FROM historico_pareceres ORDER BY data_emissao DESC", conn)
    
    for i, row in df_h.iterrows():
        with st.expander(f"📄 {row['data_emissao'][:10]} | PROG: {row['projeto']} | Impacto: {format_moeda(row['impacto_financeiro'])}"):
            st.write(f"**Gerente do Programa:** {row['gerente']}")
            st.write(f"**Causas:** {row['justificativa_cat']}")
            
            # Resumo PERT
            c1, c2 = st.columns(2)
            c1.metric("Média PERT Custo", format_moeda(row['p_custo_media']))
            c2.metric("Média PERT Prazo", f"{row['p_prazo_media']:.1f} dias")
            
            st.info(f"**Detalhamento:** {row['detalhamento']}")

            if st.button(f"📥 Gerar PDF do Dossiê", key=f"pdf_{row['id']}"):
                pdf = ExecutiveReport(row['projeto'], row['gerente'])
                pdf.add_page()
                
                pdf.set_font("Arial", 'B', 12); pdf.set_fill_color(240); pdf.cell(190, 10, " 1. RESUMO E JUSTIFICATIVAS", ln=True, fill=True)
                pdf.set_font("Arial", '', 10)
                pdf.multi_cell(190, 7, f"O programa {row['projeto']} sofreu impacto nominal de {format_moeda(row['impacto_financeiro'])}.\nJustificativas: {row['justificativa_cat']}.\n\nDetalhamento Tecnico: {row['detalhamento']}")
                
                pdf.ln(5); pdf.set_font("Arial", 'B', 12); pdf.cell(190, 10, " 2. MODELAGEM ESTATISTICA (PERT)", ln=True, fill=True)
                pdf.set_font("Arial", '', 10)
                pdf.cell(190, 7, f"Custo Medio Estimado (Incerteza): {format_moeda(row['p_custo_media'])}", ln=True)
                pdf.cell(190, 7, f"Prazo Adicional Medio Estimado: {row['p_prazo_media']:.1f} dias", ln=True)
                
                pdf.footer_signatures()
                st.download_button("Clique para salvar o PDF", bytes(pdf.output(dest='S')), f"DOSSIE_{row['projeto']}.pdf")
