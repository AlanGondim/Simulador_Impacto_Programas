import streamlit as st
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
import seaborn as sns
from fpdf import FPDF
from datetime import datetime
import tempfile
import os

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
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

# --- CLASSE PDF EXECUTIVA OTIMIZADA (PÁGINA ÚNICA) ---
class ExecutiveReport(FPDF):
    def __init__(self, projeto, gerente):
        super().__init__()
        self.projeto = projeto
        self.gerente = gerente

    def header(self):
        self.set_fill_color(0, 51, 102)
        self.rect(0, 0, 210, 30, 'F')
        self.set_font("Arial", 'B', 14)
        self.set_text_color(255)
        self.cell(190, 10, "MV PORTFOLIO INTELLIGENCE - PARECER TÉCNICO", ln=True, align='C')
        self.set_font("Arial", '', 8)
        self.cell(190, 5, f"Projeto: {self.projeto} | Responsável: {self.gerente}", ln=True, align='C')
        self.ln(5)

    def watermark(self):
        self.set_font("Arial", 'B', 45)
        self.set_text_color(245, 245, 245)
        with self.rotation(45, 100, 150):
            self.text(45, 190, "CONFIDENCIAL")
        self.set_text_color(0)

    def add_signatures(self):
        # Fixa as assinaturas no final da página (y=255)
        self.set_y(250)
        curr_y = self.get_y()
        self.set_draw_color(0)
        self.line(25, curr_y + 10, 85, curr_y + 10)
        self.line(125, curr_y + 10, 185, curr_y + 10)
        self.set_font("Arial", 'B', 9)
        self.set_y(curr_y + 12)
        self.set_x(25); self.cell(60, 5, self.gerente, 0, 0, 'C')
        self.set_x(125); self.cell(60, 5, "DIRETOR DE OPERAÇÕES", 0, 1, 'C')
        self.set_font("Arial", '', 7)
        self.set_x(25); self.cell(60, 5, "Gerente de Projetos", 0, 0, 'C')
        self.set_x(125); self.cell(60, 5, "Aprovação Final", 0, 1, 'C')

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="MV Simulador Impacto Pro", layout="wide")
conn = init_db()
sns.set_theme(style="whitegrid")

st.sidebar.title("📂 Menu de Auditoria")
aba = st.sidebar.radio("Navegação", ["Nova Análise", "Consultar Histórico"])

if aba == "Nova Análise":
    st.subheader("📌 1. Identificação")
    c_id1, c_id2, c_id3 = st.columns([2, 2, 1])
    with c_id1: nome_projeto = st.text_input("Nome do Projeto").upper()
    with c_id2: gerente_nome = st.text_input("Gerente de Projeto")
    with c_id3: just_cat = st.selectbox("Categoria", ["Mudança Go Live", "Retreinamento", "Alt. Especificações", "Infraestrutura", "Versão Produto"])

    with st.expander("👤 2. Lançamento de Recursos", expanded=True):
        c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
        with c1: rec_nome = st.text_input("Recurso")
        with c2: cat_prof = st.selectbox("Perfil", ["Consultor", "Analista", "Dev", "Gerente"])
        with c3: v_h = st.number_input("R$/Hora", value=150.0)
        with c4: hrs = st.number_input("Horas", min_value=1)
        if st.button("💾 Gravar Recurso"):
            if nome_projeto and rec_nome:
                conn.cursor().execute('''INSERT INTO recursos_projeto (projeto, gerente, recurso, categoria, custo_hora, horas, subtotal, data_registro) VALUES (?,?,?,?,?,?,?,?)''', 
                (nome_projeto, gerente_nome, rec_nome, cat_prof, v_h, hrs, v_h*hrs, datetime.now().isoformat()))
                conn.commit(); st.success("Gravado!")

    # Tabela de Conferência
    df_db = pd.read_sql_query(f"SELECT recurso, categoria, horas, subtotal FROM recursos_projeto WHERE projeto = '{nome_projeto}'", conn)
    if not df_db.empty:
        st.table(df_db)
        total_extra = df_db['subtotal'].sum()
    else: total_extra = 0.0

    st.markdown("### 💰 3. Simulação Financeira")
    f1, f2, f3 = st.columns(3)
    with f1: v_proj = st.number_input("Valor Contrato (R$)", value=1000000.0)
    with f2: m_orig = st.slider("Margem Original (%)", 0.0, 100.0, 30.0)
    with f3: parecer = st.text_area("Justificativa")

    lucro_orig = v_proj * (m_orig / 100)
    v_final = v_proj + total_extra
    novo_lucro = lucro_orig - total_extra
    n_margem = (novo_lucro / v_proj) * 100 if v_proj > 0 else 0

    if not df_db.empty:
        fig, ax = plt.subplots(figsize=(8, 3.5)) # Gráfico menor para caber na página
        data_p = pd.DataFrame({'Cenário': ['Original', 'Impactado', 'Original', 'Impactado'], 'Valor': [v_proj, v_final, lucro_orig, novo_lucro], 'Tipo': ['Contrato', 'Contrato', 'Lucro', 'Lucro']})
        sns.barplot(data=data_p, x='Cenário', y='Valor', hue='Tipo', palette=['#003366', '#B22222'], ax=ax)
        for p in ax.patches:
            if p.get_height() != 0:
                ax.annotate(f'R$ {p.get_height():,.0f}', (p.get_x() + p.get_width() / 2., p.get_height()), ha='center', va='center', xytext=(0, 7), textcoords='offset points', fontsize=8, fontweight='bold')
        ax.set_ylim(0, max(v_proj, v_final) * 1.2); st.pyplot(fig)

    if st.button("🚀 Gerar Relatório Página Única"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            fig.savefig(tmp.name, bbox_inches='tight'); img_path = tmp.name
        
        pdf = ExecutiveReport(nome_projeto, gerente_nome)
        pdf.add_page(); pdf.watermark()
        
        pdf.set_font("Arial", 'B', 10); pdf.set_fill_color(240); pdf.cell(190, 8, " 1. RESUMO EXECUTIVO", ln=True, fill=True)
        pdf.set_font("Arial", '', 9)
        txt = (f"Análise de impacto no projeto {nome_projeto} ({just_cat}). "
               f"O valor original de R$ {v_proj:,.2f} ({m_orig}%) sofreu impacto de R$ {total_extra:,.2f}. "
               f"O custo total agora é R$ {v_final:,.2f}, com margem reduzida para {n_margem:.2f}% "
               f"(perda de {abs(n_margem-m_orig):.2f} p.p.).")
        pdf.multi_cell(190, 5, txt)
        
        pdf.ln(2); pdf.image(img_path, x=45, w=120)
        
        pdf.ln(2); pdf.set_font("Arial", 'B', 10); pdf.cell(190, 8, " 2. RECURSOS ADICIONAIS", ln=True, fill=True)
        pdf.set_font("Arial", 'B', 8)
        pdf.cell(90, 6, " Recurso", 1); pdf.cell(30, 6, " Horas", 1); pdf.cell(70, 6, " Subtotal", 1, ln=True)
        pdf.set_font("Arial", '', 8)
        for _, row in df_db.iterrows():
            pdf.cell(90, 5, f" {row['recurso']}", 1); pdf.cell(30, 5, f" {row['horas']}", 1); pdf.cell(70, 5, f" R$ {row['subtotal']:,.2f}", 1, ln=True)

        pdf.ln(2); pdf.set_font("Arial", 'B', 10); pdf.cell(190, 8, " 3. JUSTIFICATIVA E PARECER", ln=True, fill=True)
        pdf.set_font("Arial", 'I', 8); pdf.multi_cell(190, 5, parecer, border=1)
        
        pdf.add_signatures()
        st.download_button("📥 Baixar PDF", bytes(pdf.output(dest='S')), f"AUDITORIA_{nome_projeto}.pdf")
        os.remove(img_path)
else:
    st.dataframe(pd.read_sql_query("SELECT * FROM historico_pareceres", conn))
