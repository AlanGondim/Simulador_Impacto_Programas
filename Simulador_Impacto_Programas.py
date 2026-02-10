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
        # Header em Ciano Escuro Profundo
        self.set_fill_color(10, 25, 41)
        self.rect(0, 0, 210, 30, 'F')
        self.set_font("Arial", 'B', 14); self.set_text_color(0, 255, 255) # Ciano Neon
        self.cell(190, 10, "MV PORTFOLIO INTELLIGENCE - PARECER TECNICO", ln=True, align='C')
        self.set_font("Arial", '', 8); self.set_text_color(200)
        self.cell(190, 5, f"Programa: {self.projeto} | Responsavel: {self.gerente}", ln=True, align='C')
        self.ln(5)

    def watermark(self):
        self.set_font("Arial", 'B', 45); self.set_text_color(245, 245, 245)
        with self.rotation(45, 100, 150): self.text(45, 190, "CONFIDENCIAL")
        self.set_text_color(0)

    def add_signatures(self):
        self.set_y(250); curr_y = self.get_y()
        self.line(25, curr_y + 10, 85, curr_y + 10); self.line(125, curr_y + 10, 185, curr_y + 10)
        self.set_font("Arial", 'B', 9); self.set_y(curr_y + 12)
        self.set_x(25); self.cell(60, 5, self.gerente, 0, 0, 'C')
        self.set_x(125); self.cell(60, 5, "DIRETOR DE OPERACOES", 0, 1, 'C')

# --- CONFIGURAÇÃO E TEMA ---
st.set_page_config(page_title="MV Impact Sentinel", layout="wide")
conn = init_db()
sns.set_theme(style="darkgrid") # Tema escuro para destacar o Neon

# Cores Neon Definidas
CYAN_NEON = "#00F5FF"
ORANGE_NEON = "#FF8C00"
DARK_BG = "#0A1929"

# CSS NotebookLM Premium
st.markdown(f"""
    <style>
    .stApp {{ background-color: {DARK_BG}; color: white; }}
    .metric-card {{ 
        background-color: #132F4C; padding: 15px; border-radius: 12px; 
        border: 1px solid {CYAN_NEON}; box-shadow: 0 0 10px rgba(0,245,255,0.2);
    }}
    .infographic-title {{ color: {CYAN_NEON}; font-weight: bold; border-bottom: 2px solid {ORANGE_NEON}; padding-bottom: 10px; }}
    </style>
    """, unsafe_allow_html=True)

st.sidebar.title("🛡️ MV Sentinel Pro")
aba = st.sidebar.radio("Navegação", ["Nova Análise", "Consultar Histórico"])

if aba == "Nova Análise":
    st.markdown("<h2 class='infographic-title'>📌 Definição do Escopo</h2>", unsafe_allow_html=True)
    c_id1, c_id2, c_id3 = st.columns([2, 2, 1])
    with c_id1: nome_projeto = st.selectbox("Selecione o Programa", ["CEMA", "EINSTEIN", "GIRASSOL", "OUTROS"])
    with c_id2: gerente_nome = st.text_input("Gerente de Projeto")
    with c_id3: just_cat = st.selectbox("Categoria", ["Mudança Go Live", "Retreinamento", "Alt. Especificações", "Infraestrutura", "Versão Produto"])

    with st.expander("👤 2. Lançamento de Nome do Recurso", expanded=True):
        c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
        with c1: rec_nome = st.text_input("Nome do Recurso")
        with c2: cat_prof = st.selectbox("Perfil", ["Consultor", "Analista", "Dev", "Gerente"])
        with c3: v_h = st.number_input("R$/Hora", value=150.0)
        with c4: hrs = st.number_input("Horas", min_value=1)
        if st.button("⚡ Gravar Recurso Neon"):
            conn.cursor().execute('''INSERT INTO recursos_projeto (projeto, gerente, recurso, categoria, custo_hora, horas, subtotal, data_registro) VALUES (?,?,?,?,?,?,?,?)''', 
            (nome_projeto, gerente_nome, rec_nome, cat_prof, v_h, hrs, v_h*hrs, datetime.now().isoformat()))
            conn.commit(); st.success("Registrado no ecossistema!")

    df_db = pd.read_sql_query(f"SELECT recurso, categoria, horas, subtotal FROM recursos_projeto WHERE projeto = '{nome_projeto}'", conn)
    if not df_db.empty:
        st.table(df_db); total_extra = df_db['subtotal'].sum()
    else: total_extra = 0.0

    st.markdown(f"<h3 style='color:{ORANGE_NEON}'>💰 3. Simulação Financeira</h3>", unsafe_allow_html=True)
    f1, f2, f3 = st.columns(3)
    with f1: v_proj = st.number_input("Valor Contrato (R$)", value=1000000.0)
    with f2: m_orig = st.slider("Margem Original (%)", 0.0, 100.0, 30.0)
    with f3: parecer = st.text_area("Justificativa Técnica")

    lucro_orig = v_proj * (m_orig / 100)
    v_final = v_proj + total_extra
    novo_lucro = lucro_orig - total_extra
    n_margem = (novo_lucro / v_proj) * 100 if v_proj > 0 else 0

    if st.button("🚀 Protocolar Parecer"):
        conn.cursor().execute('''INSERT INTO historico_pareceres (projeto, gerente, justificativa_cat, valor_projeto, margem_original, impacto_financeiro, parecer_texto, data_emissao) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (nome_projeto, gerente_nome, just_cat, v_proj, m_orig, total_extra, parecer, datetime.now().isoformat()))
        conn.commit(); st.balloons()

else:
    st.markdown("<h1 class='infographic-title'>📚 Hub de Auditoria: Filtros Avançados</h1>", unsafe_allow_html=True)
    
    # Filtro de Busca
    search_query = st.text_input("🔍 Buscar por Programa ou Gerente:", "").upper()
    
    df_hist = pd.read_sql_query("SELECT * FROM historico_pareceres ORDER BY data_emissao DESC", conn)
    if search_query:
        df_hist = df_hist[df_hist['projeto'].str.contains(search_query) | df_hist['gerente'].str.upper().contains(search_query)]

    for index, row in df_hist.iterrows():
        with st.expander(f"📊 {row['projeto']} | Impacto: R$ {row['impacto_financeiro']:,.2f}"):
            m1, m2, m3, m4 = st.columns(4)
            with m1: st.markdown(f"<div class='metric-card'><b>Valor Orig.</b><br>{CYAN_NEON} R$ {row['valor_projeto']:,.0f}</div>", unsafe_allow_html=True)
            with m2: st.markdown(f"<div class='metric-card'><b>Erosão</b><br><span style='color:{ORANGE_NEON}'>R$ {row['impacto_financeiro']:,.0f}</span></div>", unsafe_allow_html=True)
            
            lucro_p = (row['valor_projeto']*(row['margem_original']/100))
            nova_m = (lucro_p - row['impacto_financeiro']) / row['valor_projeto'] * 100
            
            with m3: st.markdown(f"<div class='metric-card'><b>M. Original</b><br>{row['margem_original']}%</div>", unsafe_allow_html=True)
            with m4: st.markdown(f"<div class='metric-card'><b>M. Final</b><br><span style='color:{CYAN_NEON if nova_m > 15 else ORANGE_NEON}'>{nova_m:.2f}%</span></div>", unsafe_allow_html=True)

            fig_h, ax_h = plt.subplots(figsize=(7, 4), facecolor=DARK_BG)
            ax_h.set_facecolor(DARK_BG)
            l_orig = row['valor_projeto'] * (row['margem_original']/100)
            l_novo = l_orig - row['impacto_financeiro']
            
            bars = sns.barplot(x=['Planejado', 'Impactado'], y=[l_orig, l_novo], palette=[CYAN_NEON, ORANGE_NEON], ax=ax_h)
            for p in ax_h.patches:
                ax_h.annotate(f'R$ {p.get_height():,.0f}', (p.get_x() + p.get_width() / 2., p.get_height()), 
                              ha='center', va='bottom', color='white', fontweight='bold', fontsize=10, xytext=(0, 5), textcoords='offset points')
            
            ax_h.tick_params(colors='white'); ax_h.set_title("Erosão de Lucratividade (R$)", color=CYAN_NEON)
            st.pyplot(fig_h)

            if st.button(f"📥 Gerar PDF Master: {row['projeto']}", key=f"pdf_{row['id']}"):
                pdf = ExecutiveReport(row['projeto'], row['gerente'])
                pdf.add_page(); pdf.watermark()
                pdf.set_font("Arial", 'B', 12); pdf.set_fill_color(10, 25, 41); pdf.set_text_color(0, 245, 255)
                pdf.cell(190, 8, " 1. RESUMO EXECUTIVO", ln=True, fill=True)
                pdf.set_text_color(0); pdf.set_font("Arial", '', 10)
                txt = (f"Programa: {row['projeto']} | Impacto: R$ {row['impacto_financeiro']:,.2f}\n"
                       f"Margem: {row['margem_original']}% -> {nova_m:.2f}%")
                pdf.multi_cell(190, 6, txt)
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_img:
                    fig_h.savefig(tmp_img.name, bbox_inches='tight', facecolor=fig_h.get_facecolor())
                    pdf.ln(5); pdf.image(tmp_img.name, x=45, w=120)
                
                pdf.add_signatures()
                st.download_button("Salvar Documento", bytes(pdf.output(dest='S')), f"PARECER_{row['projeto']}.pdf")
