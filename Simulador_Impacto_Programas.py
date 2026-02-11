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
    """Padrão Brasileiro R$ 1.000.000,00"""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def calcular_pert(o, m, p):
    """Fórmula PERT: (O + 4M + P) / 6"""
    media = (o + 4 * m + p) / 6
    desvio = (p - o) / 6
    return media, desvio

# --- MOTOR DE BANCO DE DADOS COM EVOLUÇÃO DE SCHEMA ---
def init_db():
    conn = sqlite3.connect('mv_governança_pro_v10.db')
    cursor = conn.cursor()
    
    # Tabela de Recursos
    cursor.execute('''CREATE TABLE IF NOT EXISTS recursos_projeto 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, projeto TEXT, gerente TEXT, recurso TEXT, 
        categoria TEXT, custo_hora REAL, horas INTEGER, subtotal REAL, data_registro TEXT)''')
    
    # Tabela de Pareceres (Base)
    cursor.execute('''CREATE TABLE IF NOT EXISTS historico_pareceres 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, projeto TEXT, gerente TEXT, justificativa_cat TEXT, 
        valor_projeto REAL, margem_original REAL, impacto_financeiro REAL, detalhamento TEXT, data_emissao TEXT)''')
    
    # Evolução de Schema: Adiciona colunas se não existirem
    colunas_extras = [
        ("p_custo_media", "REAL"), ("p_prazo_media", "REAL"), ("p_prazo_horas", "REAL"),
        ("r_escopo", "INTEGER"), ("r_custo", "REAL"), ("r_prazo", "INTEGER")
    ]
    cursor.execute("PRAGMA table_info(historico_pareceres)")
    colunas_existentes = [col[1] for col in cursor.fetchall()]
    
    for nome_col, tipo_col in colunas_extras:
        if nome_col not in colunas_existentes:
            cursor.execute(f"ALTER TABLE historico_pareceres ADD COLUMN {nome_col} {tipo_col}")
            
    conn.commit()
    return conn

# --- CLASSE PDF EXECUTIVA MASTER ---
class ExecutiveReport(FPDF):
    def __init__(self, projeto, gerente):
        super().__init__()
        self.projeto = projeto
        self.gerente = gerente

    def header(self):
        self.set_fill_color(0, 51, 102) # Azul Marinho MV
        self.rect(0, 0, 210, 40, 'F')
        self.set_font("Arial", 'B', 16); self.set_text_color(255)
        self.cell(190, 15, "DOSSIÊ ESTRATÉGICO DE IMPACTO E REEQUILÍBRIO", ln=True, align='C')
        self.set_font("Arial", 'B', 10)
        self.cell(190, 5, f"PROGRAMA: {self.projeto} | GERENTE: {self.gerente.upper()}", ln=True, align='C')
        self.set_text_color(200); self.set_font("Arial", '', 8)
        self.cell(190, 5, f"EMITIDO EM: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='C')
        self.ln(15)

    def section_header(self, title):
        self.set_font("Arial", 'B', 11); self.set_fill_color(230, 230, 230); self.set_text_color(0, 51, 102)
        self.cell(190, 10, f"  {title}", ln=True, fill=True)
        self.ln(3)

    def footer_signatures(self):
        self.set_y(250)
        self.line(25, self.get_y(), 85, self.get_y())
        self.line(125, self.get_y(), 185, self.get_y())
        self.set_font("Arial", 'B', 9); self.set_text_color(0)
        self.set_y(self.get_y() + 2)
        self.set_x(25); self.cell(60, 5, "GERENTE DO PROGRAMA", align='C')
        self.set_x(125); self.cell(60, 5, "DIRETORIA DE OPERAÇÕES", align='C')

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Impacto Programas PRO", layout="wide")
conn = init_db()
sns.set_theme(style="whitegrid")

st.sidebar.title("🛡️ MV Impacto Programas PRO")
aba = st.sidebar.radio("Navegação", ["Nova Análise", "Hub de Inteligência"])

if aba == "Nova Análise":
    st.markdown("<h2 style='color: #003366;'>📋 Elaboração de Dossiê de Impacto</h2>", unsafe_allow_html=True)
    
    # 1. IDENTIFICAÇÃO
    c1, c2 = st.columns(2)
    with c1:
        lista_progs = [" ", "INS", "UNIMED SERRA GAUCHA", "UNIMED NORTE FLUMINENSE", "CLINICA GIRASSOL", "GUATEMALA", "GOOD HOPE", "EINSTEIN", "MOGI DAS CRUZES", "SESA/ES", "CEMA", "RHP", "SESI/RS"]
        nome_prog = st.selectbox("Selecione o Programa", lista_progs)
        v_contrato = st.number_input("Valor Original do Contrato (R$)", value=100000.0)
    with c2:
        gerente_nome = st.text_input("Gerente do Programa")
        justificativas = st.multiselect("Justificativas do Desvio", ["Mudança de Go Live", "Retreinamento", "Infraestrutura", "Especificações Funcionais", "Escopo", "Versão Produto"])

    # 2. LANÇAMENTO DINÂMICO DE RECURSOS
    st.subheader("👥 Lançamento de Esforço Adicional")
    with st.form("form_rec", clear_on_submit=True):
        cl1, cl2, cl3 = st.columns([3, 1, 1])
        with cl1: r_nome = st.text_input("Nome do Recurso / Atividade")
        with cl2: r_vh = st.number_input("Custo R$/Hora", value=150.0)
        with cl3: r_hr = st.number_input("Horas", min_value=1)
        if st.form_submit_button("➕ Inserir Linha"):
            conn.cursor().execute("INSERT INTO recursos_projeto (projeto, recurso, categoria, custo_hora, horas, subtotal, data_registro) VALUES (?,?,?,?,?,?,?)",
                                   (nome_prog, r_nome, "PRO", r_vh, r_hr, r_vh*r_hr, datetime.now().isoformat()))
            conn.commit()

    df_db = pd.read_sql_query(f"SELECT recurso, horas, subtotal FROM recursos_projeto WHERE projeto = '{nome_prog}'", conn)
    total_impacto = df_db['subtotal'].sum() if not df_db.empty else 0.0
    st.write(f"**Impacto Acumulado Atual: {format_moeda(total_impacto)}**")
    st.dataframe(df_db.assign(subtotal=df_db['subtotal'].apply(format_moeda)), use_container_width=True)

    # 3. MODELAGEM PERT (CUSTO E PRAZO AUTOMÁTICO)
    st.markdown("---")
    st.subheader("🎲 Modelagem de Incerteza (PERT)")
    cp1, cp2 = st.columns(2)
    with cp1:
        st.caption("Cenários de Custo Financeiro")
        co_c = st.number_input("Otimista (C)", value=total_impacto * 0.9)
        cm_c = st.number_input("Provável (C)", value=total_impacto)
        cp_c = st.number_input("Pessimista (C)", value=total_impacto * 1.5)
        media_c, _ = calcular_pert(co_c, cm_c, cp_c)
        st.info(f"Média PERT Custo: {format_moeda(media_c)}")
    with cp2:
        st.caption("Cenários de Prazo (Dias para Horas)")
        co_d = st.number_input("Otimista (Dias)", value=2)
        cm_d = st.number_input("Provável (Dias)", value=5)
        cp_d = st.number_input("Pessimista (Dias)", value=15)
        media_d, _ = calcular_pert(co_d, cm_d, cp_d)
        media_h = media_d * 8 # Conversão automática
        st.info(f"Média PERT Prazo: {media_d:.1f} Dias ({media_h:.1f} Horas)")

    # 4. RADAR CHART (COMPACTO)
    st.markdown("---")
    c_rad, c_det = st.columns([1, 2])
    with c_rad:
        st.subheader("📐 Radar de Impacto")
        r_esc = st.slider("Escopo", 1, 10, 5)
        r_pra = st.slider("Prazo", 1, 10, 5)
        r_cus = min(10, (total_impacto / (v_contrato*0.1 if v_contrato > 0 else 1)) * 10)
        
        labels = ['Escopo', 'Custo', 'Prazo']
        stats = [r_esc, r_cus, r_pra]; stats += stats[:1]
        angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist(); angles += angles[:1]
        
        fig_rad, ax = plt.subplots(figsize=(2.5, 2.5), subplot_kw=dict(polar=True))
        ax.plot(angles, stats, color='yellow', linewidth=2)
        ax.fill(angles, stats, color='orange', alpha=0.3, hatch='///')
        plt.xticks(angles[:-1], labels, size=8, fontweight='bold')
        st.pyplot(fig_rad)

    with c_det:
        st.subheader("📝 Justificativa Técnica")
        detalhamento = st.text_area("Descreva o plano de ação e mitigação:", height=150)

    if st.button("🚀 Protocolar Dossiê de Reequilíbrio"):
        conn.cursor().execute('''INSERT INTO historico_pareceres 
            (projeto, gerente, justificativa_cat, valor_projeto, margem_original, impacto_financeiro, detalhamento, 
             p_custo_media, p_prazo_media, p_prazo_horas, r_escopo, r_custo, r_prazo, data_emissao) 
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', 
            (nome_prog, gerente_nome, ", ".join(justificativas), v_contrato, 35.0, total_impacto, detalhamento, 
             media_c, media_d, media_h, r_esc, r_cus, r_pra, datetime.now().isoformat()))
        conn.commit(); st.success("Protocolado!")

# --- HUB DE INTELIGÊNCIA (INTERATIVO) ---
else:
    st.header("📚 Hub de Inteligência - Histórico de Auditorias")
    df_h = pd.read_sql_query("SELECT * FROM historico_pareceres ORDER BY data_emissao DESC", conn)
    
    for i, row in df_h.iterrows():
        label = f"📋 {row['data_emissao'][:10]} | Programa: {row['projeto']} | Impacto: {format_moeda(row['impacto_financeiro'])}"
        with st.expander(label):
            st.markdown(f"### Dossiê: {row['projeto']}")
            col1, col2, col3 = st.columns(3)
            col1.metric("Valor Contrato", format_moeda(row['valor_projeto']))
            col2.metric("Impacto PERT (Custo)", format_moeda(row['p_custo_media']))
            col3.metric("Impacto PERT (Prazo)", f"{row['p_prazo_media']:.1f} d")
            
            st.write(f"**Justificativas:** {row['justificativa_cat']}")
            st.info(f"**Resumo Executivo:** {row['detalhamento']}")

            if st.button(f"📥 Gerar Dossiê Executivo PDF", key=f"pdf_{row['id']}"):
                pdf = ExecutiveReport(row['projeto'], row['gerente'])
                pdf.add_page()
                
                # Seção 1
                pdf.section_header("1. RESUMO EXECUTIVO DO IMPACTO")
                pdf.set_font("Arial", '', 10)
                pdf.multi_cell(190, 7, f"O programa {row['projeto']} apresenta uma necessidade de reequilibrio financeiro nominal de {format_moeda(row['impacto_financeiro'])} sobre um contrato de {format_moeda(row['valor_projeto'])}.\n\nMOTIVADORES: {row['justificativa_cat']}.\n\nPLANO DE MITIGACAO: {row['detalhamento']}")
                
                # Seção 2: Radar
                pdf.ln(5); pdf.section_header("2. ANÁLISE VISUAL DE RESTRIÇÕES (RADAR)")
                labels = ['Escopo', 'Custo', 'Prazo']
                stats = [row['r_escopo'], row['r_custo'], row['r_prazo']]; stats += stats[:1]
                angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist(); angles += angles[:1]
                fig_pdf, ax_pdf = plt.subplots(figsize=(3, 3), subplot_kw=dict(polar=True))
                ax_pdf.plot(angles, stats, color='yellow', linewidth=2)
                ax_pdf.fill(angles, stats, color='orange', alpha=0.3, hatch='///')
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    fig_pdf.savefig(tmp.name, bbox_inches='tight')
                    pdf.image(tmp.name, x=70, w=70)
                
                # Seção 3: PERT
                pdf.ln(5); pdf.section_header("3. MODELAGEM DE INCERTEZA (PERT)")
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(95, 8, "Variavel de Risco", 1, 0, 'C', True); pdf.cell(95, 8, "Expectativa Media (PERT)", 1, 1, 'C', True)
                pdf.set_font("Arial", '', 10)
                pdf.cell(95, 8, "Custo de Reequilibrio", 1); pdf.cell(95, 8, format_moeda(row['p_custo_media']), 1, 1, 'C')
                pdf.cell(95, 8, "Prazo Adicional", 1); pdf.cell(95, 8, f"{row['p_prazo_media']:.1f} Dias ({row['p_prazo_horas']:.1f} h)", 1, 1, 'C')
                
                pdf.footer_signatures()
                st.download_button("Salvar Arquivo", bytes(pdf.output(dest='S')), f"DOSSIE_EXECUTIVO_{row['projeto']}.pdf")

