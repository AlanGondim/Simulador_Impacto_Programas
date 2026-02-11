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
    media = (o + 4 * m + p) / 6
    desvio = (p - o) / 6
    return media, desvio

# --- BANCO DE DADOS (V10 - Consolidada) ---
def init_db():
    conn = sqlite3.connect('mv_governança_executiva_v10.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS recursos_projeto 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, projeto TEXT, recurso TEXT, 
        categoria TEXT, custo_hora REAL, horas INTEGER, subtotal REAL, data_registro TEXT)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS historico_pareceres 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, projeto TEXT, gerente TEXT, justificativa_cat TEXT, 
        valor_projeto REAL, margem_original REAL, impacto_financeiro REAL, detalhamento TEXT, 
        p_custo_media REAL, p_prazo_media REAL, p_prazo_horas REAL, r_escopo INTEGER, 
        r_custo REAL, r_prazo INTEGER, data_emissao TEXT)''')
    conn.commit()
    return conn

# --- CLASSE PDF EXECUTIVA MASTER ---
class ExecutiveReport(FPDF):
    def __init__(self, projeto, gerente):
        super().__init__()
        self.projeto = projeto
        self.gerente = gerente

    def header(self):
        self.set_fill_color(0, 51, 102) 
        self.rect(0, 0, 210, 45, 'F')
        self.set_font("Arial", 'B', 18); self.set_text_color(255)
        self.cell(190, 15, "DOSSIÊ DE IMPACTO E GOVERNANÇA ECONÓMICA", ln=True, align='C')
        self.set_font("Arial", 'B', 10)
        self.cell(190, 5, f"PROGRAMA: {self.projeto} | RESPONSÁVEL: {self.gerente.upper()}", ln=True, align='C')
        self.set_font("Arial", '', 8)
        self.cell(190, 5, f"DOCUMENTO CONFIDENCIAL - EMITIDO EM {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='C')
        self.ln(20)

    def section_title(self, title, color=(0, 51, 102)):
        self.set_font("Arial", 'B', 12); self.set_fill_color(240, 240, 240); self.set_text_color(*color)
        self.cell(190, 10, f"  {title}", ln=True, fill=True)
        self.ln(3)

    def footer_signatures(self):
        self.set_y(250)
        self.line(20, self.get_y(), 90, self.get_y())
        self.line(120, self.get_y(), 190, self.get_y())
        self.set_font("Arial", 'B', 9); self.set_text_color(0)
        self.set_y(self.get_y() + 2)
        self.set_x(20); self.cell(70, 5, "GERENTE DO PROGRAMA", align='C')
        self.set_x(120); self.cell(70, 5, "DIRETORIA DE OPERAÇÕES", align='C')

# --- INTERFACE ---
st.set_page_config(page_title="Simulador Impacto PRO", layout="wide")
conn = init_db()

st.sidebar.title("🛡️ MV Impacto Programas PRO")
aba = st.sidebar.radio("Navegação", ["Nova Análise", "Hub de Inteligência"])

if aba == "Nova Análise":
    st.markdown("<h2 style='color: #003366;'>📋 Elaboração de Dossiê de Aprovação</h2>", unsafe_allow_html=True)
    
    # 1. IDENTIFICAÇÃO
    c1, c2 = st.columns(2)
    with c1: 
        progs = [" ","INS", "UNIMED SERRA GAUCHA", "UNIMED NORTE FLUMINENSE", "CLINICA GIRASSOL", "GUATEMALA", "EINSTEIN", "MOGI DAS CRUZES", "SESA/ES", "CEMA", "RHP", "SESI/RS"]
        nome_projeto = st.selectbox("Selecione o Programa", progs)
        v_contrato = st.number_input("Valor do Contrato (R$)", value=100000.0)
    with c2: 
        gerente_nome = st.text_input("Gerente do Programa")
        m_original = st.slider("Margem Original Planeada (%)", 0.0, 100.0, 35.0)
        just_cats = st.multiselect("Motivadores do Desvio", ["Mudança de Go Live", "Retreinamento", "Especificações Funcionais","Erro de Escopo", "Infraestrutura", "Versão Produto"])

    # 2. LANÇAMENTO DE RECURSOS
    st.subheader("👥 Alocação de Esforço em Tempo Real")
    with st.form("form_rec", clear_on_submit=True):
        cl1, cl2, cl3 = st.columns([3, 1, 1])
        r_nome = cl1.text_input("Recurso / Atividade")
        r_vh = cl2.number_input("Custo R$/Hora", value=150.0)
        r_hr = cl3.number_input("Horas Adicionais", min_value=1)
        if st.form_submit_button("➕ Inserir Linha de Esforço"):
            conn.cursor().execute("INSERT INTO recursos_projeto (projeto, recurso, categoria, custo_hora, horas, subtotal, data_registro) VALUES (?,?,?,?,?,?,?)",
                                   (nome_projeto, r_nome, "PERFIL", r_vh, r_hr, r_vh*r_hr, datetime.now().isoformat()))
            conn.commit()

    df_db = pd.read_sql_query(f"SELECT recurso, horas, subtotal FROM recursos_projeto WHERE projeto = '{nome_projeto}'", conn)
    total_impacto = df_db['subtotal'].sum() if not df_db.empty else 0.0
    total_horas = df_db['horas'].sum() if not df_db.empty else 0.0
    
    # Cálculos de Margem
    lucro_orig = v_contrato * (m_original / 100)
    novo_lucro = lucro_orig - total_impacto
    nova_margem = (novo_lucro / v_contrato) * 100 if v_contrato > 0 else 0
    erosao_pp = m_original - nova_margem

    # Termômetro de Risco Visual
    cor_risco = "green" if erosao_pp < 5 else "orange" if erosao_pp < 15 else "red"
    st.markdown(f"### 🌡️ Termómetro de Impacto: <span style='color:{cor_risco}'>{erosao_pp:.2f} % de Erosão</span>", unsafe_allow_html=True)
    
    st.table(df_db.assign(subtotal=df_db['subtotal'].apply(format_moeda)))

    # 3. PERT E RADAR
    st.markdown("---")
    col_p, col_r = st.columns([2, 1])
    with col_p:
        st.subheader("🎲 Modelagem de Incerteza (PERT)")
        c_o = st.number_input("Custo Otimista", value=total_impacto * 0.9)
        c_m = st.number_input("Custo Provável", value=total_impacto)
        c_p = st.number_input("Custo Pessimista", value=total_impacto * 1.5)
        media_c, _ = calcular_pert(c_o, c_m, c_p)
        
        d_o = st.number_input("Prazo Otimista (Dias)", value=max(1.0, total_horas/8 * 0.8))
        d_m = st.number_input("Prazo Provável (Dias)", value=max(1.0, total_horas/8))
        d_p = st.number_input("Prazo Pessimista (Dias)", value=max(2.0, total_horas/8 * 2))
        media_d, _ = calcular_pert(d_o, d_m, d_p)
        st.info(f"**Média Estatística:** {format_moeda(media_c)} | Atraso Médio: {media_d:.1f} dias.")

    with col_r:
        st.subheader("📐 Radar de Restrições")
        r_esc = st.slider("Escopo", 1, 10, 5)
        r_pra = st.slider("Prazo", 1, 10, 5)
        r_cus = min(10, (total_impacto / (v_contrato*0.1 if v_contrato > 0 else 1)) * 10)
        
        labels = ['Escopo', 'Custo', 'Prazo']
        stats = [r_esc, r_cus, r_pra]; stats += stats[:1]
        angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist(); angles += angles[:1]
        fig_rad, ax = plt.subplots(figsize=(2.5, 2.5), subplot_kw=dict(polar=True))
        ax.plot(angles, stats, color='yellow', linewidth=2)
        ax.fill(angles, stats, color='orange', alpha=0.3, hatch='///')
        plt.xticks(angles[:-1], labels, size=9, fontweight='bold')
        st.pyplot(fig_rad)

    detalhamento = st.text_area("📝 Justificativa Técnica Detalhada (Resumo Executivo):")

    if st.button("🚀 Gerar e Protocolar Dossiê"):
        conn.cursor().execute('''INSERT INTO historico_pareceres 
            (projeto, gerente, justificativa_cat, valor_projeto, margem_original, impacto_financeiro, detalhamento, 
             p_custo_media, p_prazo_media, r_escopo, r_custo, r_prazo, data_emissao) 
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''', 
            (nome_projeto, gerente_nome, ", ".join(just_cats), v_contrato, m_original, total_impacto, detalhamento, 
             media_c, media_d, r_esc, r_cus, r_pra, datetime.now().isoformat()))
        conn.commit(); st.success("Dossiê Protocolado com Sucesso!")

# --- HUB DE INTELIGÊNCIA ---
else:
    st.header("📚 Hub de Inteligência Interativo")
    df_h = pd.read_sql_query("SELECT * FROM historico_pareceres ORDER BY data_emissao DESC", conn)
    
    for i, row in df_h.iterrows():
        with st.expander(f"📄 {row['projeto']} | Impacto: {format_moeda(row['impacto_financeiro'])}"):
            st.markdown("### Resumo de Auditoria")
            col1, col2, col3 = st.columns(3)
            col1.metric("Valor Contrato", format_moeda(row['valor_projeto']))
            
            l_orig = row['valor_projeto'] * (row['margem_original']/100)
            n_margem = ((l_orig - row['impacto_financeiro']) / row['valor_projeto']) * 100
            
            col2.metric("Margem Original", f"{row['margem_original']}%")
            col3.metric("Margem Pós-Impacto", f"{n_margem:.2f}%", f"{n_margem - row['margem_original']:.2f}%", delta_color="inverse")

            if st.button(f"📥 Baixar Dossiê Executivo", key=f"pdf_{row['id']}"):
                pdf = ExecutiveReport(row['projeto'], row['gerente'])
                pdf.add_page()
                
                # 1. RESUMO EXECUTIVO
                pdf.section_title("1. RESUMO EXECUTIVO DO IMPACTO")
                pdf.set_font("Arial", '', 10)
                pdf.multi_cell(190, 7, f"O programa {row['projeto']} registou um impacto financeiro nominal de {format_moeda(row['impacto_financeiro'])}.\n"
                                       f"IMPACTO NA MARGEM: Redução de {row['margem_original']}% para {n_margem:.2f}% ({abs(n_margem - row['margem_original']):.2f} p.p.).\n"
                                       f"MOTIVADORES: {row['justificativa_cat']}.\n\nNOTAS: {row['detalhamento']}")
                
                # 2. RADAR E PERT
                pdf.ln(5); pdf.section_title("2. ANÁLISE DE RISCO E INCERTEZA (PERT)")
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(95, 8, "Custo Médio Ponderado (PERT)", 1); pdf.cell(95, 8, format_moeda(row['p_custo_media']), 1, 1, 'C')
                pdf.cell(95, 8, "Atraso Médio Estimado", 1); pdf.cell(95, 8, f"{row['p_prazo_media']:.1f} Dias", 1, 1, 'C')
                
                # Inserir Radar no PDF
                labels = ['Escopo', 'Custo', 'Prazo']
                stats = [row['r_escopo'], row['r_custo'], row['r_prazo']]; stats += stats[:1]
                angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist(); angles += angles[:1]
                fig_pdf, ax_pdf = plt.subplots(figsize=(3, 3), subplot_kw=dict(polar=True))
                ax_pdf.plot(angles, stats, color='yellow', linewidth=2)
                ax_pdf.fill(angles, stats, color='orange', alpha=0.3, hatch=' ')
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    fig_pdf.savefig(tmp.name, bbox_inches='tight')
                    pdf.ln(5); pdf.image(tmp.name, x=70, w=70)

                pdf.footer_signatures()
                st.download_button("Salvar Dossiê", bytes(pdf.output(dest='S')), f"DOSSIE_PRO_{row['projeto']}.pdf")


