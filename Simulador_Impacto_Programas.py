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

# --- CLASSE PDF EXECUTIVA OTIMIZADA (PÁGINA ÚNICA) ---
class ExecutiveReport(FPDF):
    def __init__(self, projeto, gerente):
        super().__init__()
        self.projeto = projeto
        self.gerente = gerente

    def header(self):
        self.set_fill_color(0, 51, 102)
        self.rect(0, 0, 210, 30, 'F')
        self.set_font("Arial", 'B', 14); self.set_text_color(255)
        self.cell(190, 10, "MV PORTFOLIO INTELLIGENCE - PARECER TÉCNICO", ln=True, align='C')
        self.set_font("Arial", '', 8); self.cell(190, 5, f"Projeto: {self.projeto} | Responsável: {self.gerente}", ln=True, align='C')
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
        self.set_x(125); self.cell(60, 5, "DIRETOR DE OPERAÇÕES", 0, 1, 'C')

# --- CONFIGURAÇÃO E TEMA ---
st.set_page_config(page_title="MV Impact Sentinel", layout="wide")
conn = init_db()
sns.set_theme(style="whitegrid")

# CSS para Estilo NotebookLM
st.markdown("""
    <style>
    .metric-card {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #003366;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    .infographic-title {
        color: #003366;
        font-weight: bold;
        border-bottom: 2px solid #003366;
        padding-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

st.sidebar.title("🛡️ MV Sentinel Pro")
aba = st.sidebar.radio("Navegação", ["Nova Análise", "Consultar Histórico"])

if aba == "Nova Análise":
    st.subheader("📌 1. Identificação do Projeto")
    # ... (Mantém o código de input original para brevidade)
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

    if st.button("🚀 Finalizar e Protocolar Parecer"):
        conn.cursor().execute('''INSERT INTO historico_pareceres (projeto, gerente, justificativa_cat, valor_projeto, margem_original, impacto_financeiro, parecer_texto, data_emissao) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                                (nome_projeto, gerente_nome, just_cat, v_proj, m_orig, total_extra, parecer, datetime.now().isoformat()))
        conn.commit(); st.success("Parecer arquivado com sucesso no histórico!")

# --- ABA DE HISTÓRICO COM INTERFACE INFOGRÁFICA (NotebookLM Style) ---
else:
    st.markdown("<h1 class='infographic-title'>📚 Intelligence Hub: Histórico de Auditorias</h1>", unsafe_allow_html=True)
    
    df_hist = pd.read_sql_query("SELECT * FROM historico_pareceres ORDER BY data_emissao DESC", conn)
    
    if df_hist.empty:
        st.info("Nenhum parecer protocolado.")
    else:
        for index, row in df_hist.iterrows():
            # Título do Card Expansível
            expander_label = f"📄 {row['data_emissao'][:10]} | {row['projeto']} | Gerente: {row['gerente']} | Impacto: R$ {row['impacto_financeiro']:,.2f}"
            
            with st.expander(expander_label):
                # Layout Estilo Infográfico
                st.markdown(f"### 📊 Insight do Projeto: {row['projeto']}")
                
                # Colunas de métricas NotebookLM
                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    st.markdown(f"<div class='metric-card'><b>Valor Projeto</b><br><span style='font-size:20px'>R$ {row['valor_projeto']:,.2f}</span></div>", unsafe_allow_html=True)
                with m2:
                    st.markdown(f"<div class='metric-card'><b>Erosão Nominal</b><br><span style='font-size:20px; color:#B22222'>R$ {row['impacto_financeiro']:,.2f}</span></div>", unsafe_allow_html=True)
                with m3:
                    st.markdown(f"<div class='metric-card'><b>Margem Original</b><br><span style='font-size:20px'>{row['margem_original']}%</span></div>", unsafe_allow_html=True)
                with m4:
                    nova_m = ((row['valor_projeto']*(row['margem_original']/100)) - row['impacto_financeiro']) / row['valor_projeto'] * 100
                    st.markdown(f"<div class='metric-card'><b>Nova Margem</b><br><span style='font-size:20px; color:{'red' if nova_m < 10 else 'green'}'>{nova_m:.2f}%</span></div>", unsafe_allow_html=True)

                # Gráfico e Justificativa lado a lado
                st.ln = 5
                col_graph, col_txt = st.columns([1.5, 1])
                
                with col_graph:
                    # Gerar gráfico específico para esta linha
                    fig_h, ax_h = plt.subplots(figsize=(7, 4))
                    l_orig = row['valor_projeto'] * (row['margem_original']/100)
                    l_novo = l_orig - row['impacto_financeiro']
                    sns.barplot(x=['Lucro Original', 'Lucro Real'], y=[l_orig, l_novo], palette=['#003366', '#B22222'], ax=ax_h)
                    ax_h.set_title("Erosão de Lucratividade")
                    st.pyplot(fig_h)
                
                with col_txt:
                    st.markdown("#### 📝 Justificativa Técnica")
                    st.info(f"**Categoria:** {row['justificativa_cat']}")
                    st.write(row['parecer_texto'])
                    
                    # Botão para gerar o PDF desta linha específica
                    if st.button(f"📥 Baixar PDF: {row['projeto']}", key=f"btn_{row['id']}"):
                        pdf = ExecutiveReport(row['projeto'], row['gerente'])
                        pdf.add_page(); pdf.watermark()
                        
                        # Bloco 1: Resumo
                        pdf.set_font("Arial", 'B', 12); pdf.set_fill_color(240); pdf.cell(190, 8, " 1. RESUMO EXECUTIVO", ln=True, fill=True)
                        pdf.set_font("Arial", '', 10)
                        pdf.multi_cell(190, 6, f"Projeto auditado: {row['projeto']}\nJustificativa: {row['justificativa_cat']}\nImpacto Nominal: R$ {row['impacto_financeiro']:,.2f}")
                        
                        # Bloco 2: Gráfico (Salvar temporário)
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_img:
                            fig_h.savefig(tmp_h_img := tmp_img.name, bbox_inches='tight')
                            pdf.ln(5); pdf.image(tmp_h_img, x=45, w=120)
                        
                        # Bloco 3: Parecer
                        pdf.ln(5); pdf.set_font("Arial", 'B', 12); pdf.cell(190, 8, " 2. PARECER DO GERENTE", ln=True, fill=True)
                        pdf.set_font("Arial", 'I', 9); pdf.multi_cell(190, 6, row['parecer_texto'], border=1)
                        
                        pdf.add_signatures()
                        st.download_button("Clique aqui para salvar o PDF", bytes(pdf.output(dest='S')), f"PARECER_{row['projeto']}.pdf")
                        os.remove(tmp_h_img)
