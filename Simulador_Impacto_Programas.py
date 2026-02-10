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
    conn = sqlite3.connect('mv_governança_v3.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS recursos_projeto 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, projeto TEXT, gerente TEXT, recurso TEXT, 
        categoria TEXT, custo_hora REAL, horas INTEGER, subtotal REAL, data_registro TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS historico_pareceres 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, projeto TEXT, gerente TEXT, justificativa_cat TEXT, 
        valor_projeto REAL, margem_original REAL, impacto_financeiro REAL, parecer_texto TEXT, data_emissao TEXT)''')
    conn.commit()
    return conn

# --- CLASSE PDF DE ALTO NÍVEL ---
class ExecutiveReport(FPDF):
    def __init__(self, projeto, gerente):
        super().__init__()
        self.projeto = projeto
        self.gerente = gerente

    def header(self):
        self.set_fill_color(0, 51, 102)
        self.rect(0, 0, 210, 35, 'F')
        self.set_font("Arial", 'B', 15); self.set_text_color(255)
        self.cell(190, 10, "MV PORTFOLIO INTELLIGENCE - PARECER TECNICO", ln=True, align='C')
        self.set_font("Arial", '', 9)
        self.cell(190, 5, f"Projeto: {self.projeto} | Responsavel: {self.gerente}", ln=True, align='C')
        self.ln(20)

    def watermark(self):
        self.set_font("Arial", 'B', 50); self.set_text_color(240, 240, 240)
        with self.rotation(45, 100, 150): self.text(35, 190, "CONFIDENCIAL")
        self.set_text_color(0)

    def approval_block(self):
        self.ln(25)
        curr_y = self.get_y()
        self.line(20, curr_y + 15, 90, curr_y + 15)
        self.line(120, curr_y + 15, 190, curr_y + 15)
        self.set_font("Arial", 'B', 10)
        self.set_y(curr_y + 18)
        self.set_x(20); self.cell(70, 10, "GERENTE DE PROJETO", align='C')
        self.set_x(120); self.cell(70, 10, "DIRETORIA DE OPERACOES", align='C')

# --- INTERFACE ---
st.set_page_config(page_title="MV Simulador de Impacto em Programas Pro", layout="wide")
conn = init_db()
sns.set_theme(style="whitegrid")

st.sidebar.title("📂 Governanca")
aba = st.sidebar.radio("Navegação", ["Nova Análise", "Histórico"])

if aba == "Nova Análise":
    st.subheader("📌 1. Identificacao Estrategica")
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1: nome_projeto = st.text_input("Nome do Projeto").upper()
    with c2: gerente_nome = st.text_input("Gerente de Projeto")
    with c3: just_cat = st.selectbox("Justificativa", ["Mudança de Go Live", "Retreinamento", "Alteração Funcional", "Infraestrutura", "Versão Produto"])

    with st.expander("👤 2. Esforco Adicional", expanded=True):
        col_rec, col_cat, col_cust, col_hrs = st.columns([3, 2, 1, 1])
        with col_rec: rec = st.text_input("Recurso")
        with col_cat: cat = st.selectbox("Perfil", ["Consultor", "Analista", "Dev", "Gerente"])
        with col_cust: vh = st.number_input("R$/Hora", value=150.0)
        with col_hrs: hr = st.number_input("Horas", min_value=1)
        if st.button("💾 Gravar Recurso"):
            if nome_projeto and rec:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO recursos_projeto (projeto, gerente, recurso, categoria, custo_hora, horas, subtotal, data_registro) VALUES (?,?,?,?,?,?,?,?)",
                               (nome_projeto, gerente_nome, rec, cat, vh, hr, vh*hr, datetime.now().isoformat()))
                conn.commit(); st.success("Registrado.")
            else: st.warning("Nome do Projeto e Recurso sao obrigatorios.")

    st.markdown("### 💰 3. Analise de Erosao de Margem")
    f1, f2, f3 = st.columns(3)
    with f1: v_proj = st.number_input("Valor Contrato (R$)", value=1000000.0)
    with f2: m_orig = st.slider("Margem Original (%)", 0.0, 100.0, 35.0)
    with f3: parecer = st.text_area("Justificativa e Plano de Ação")

    # Busca dados do banco para os calculos
    df_db = pd.read_sql_query(f"SELECT * FROM recursos_projeto WHERE projeto = '{nome_projeto}'", conn)
    total_extra = df_db['subtotal'].sum() if not df_db.empty else 0.0
    v_final = v_proj + total_extra
    lucro_orig = v_proj * (m_orig / 100)
    novo_lucro = lucro_orig - total_extra
    n_margem = (novo_lucro / v_proj) * 100 if v_proj > 0 else 0

    st.divider()
    res1, res2, res3 = st.columns(3)
    res1.metric("Valor Projeto (Impactado)", f"R$ {v_final:,.2f}", f"+ R$ {total_extra:,.2f}", delta_color="inverse")
    res2.metric("Margem Original", f"{m_orig}%")
    res3.metric("Nova Margem", f"{n_margem:.2f}%", f"{n_margem - m_orig:.2f}%", delta_color="inverse")

    # --- GERACAO DO GRAFICO COM CORES CONDICIONAIS ---
    fig, ax = plt.subplots(figsize=(10, 5))
    plot_data = pd.DataFrame({
        'Status': ['Original', 'Original', 'Impactado', 'Impactado'],
        'Metrica': ['Valor Contrato', 'Lucro Liquido', 'Valor Contrato', 'Lucro Liquido'],
        'Valor (R$)': [v_proj, lucro_orig, v_final, novo_lucro]
    })
    
    # Definindo cores base: Azul Executivo e Vermelho Executivo
    # Se a margem cair abaixo de 10%, mudamos o vermelho para Alerta Brilhante
    cor_lucro = "#B24B22" if n_margem >= 10 else "#FF0000"
    paleta_customizada = ["#1B6DBE", cor_lucro]
    
    bars = sns.barplot(data=plot_data, x='Status', y='Valor (R$)', hue='Metrica', palette=paleta_customizada, ax=ax)
    
    # Adicionando os valores em cima das barras
    for container in ax.containers:
        ax.bar_label(container, fmt='R$ {:,.2f}', padding=3, fontsize=9, fontweight='bold')

    # Ajustando o limite superior para o texto não cortar e título
    ax.set_ylim(0, max(v_proj, v_final) * 1.25)
    ax.set_title(f"Impacto Financeiro no Projeto: {nome_projeto}", fontsize=12, fontweight='bold', pad=20)
    
    st.pyplot(fig)

    if n_margem < 10:
        st.error(f"🚨 ALERTA CRÍTICO: A nova margem de {n_margem:.2f}% está abaixo do limite de segurança (10%).")

    if st.button("🚀 Gerar Parecer e Protocolar"):
        if total_extra == 0:
            st.error("Adicione recursos antes de gerar o parecer.")
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                fig.savefig(tmp.name, bbox_inches='tight')
                img_path = tmp.name

            pdf = ExecutiveReport(nome_projeto, gerente_nome)
            pdf.add_page(); pdf.watermark()
            
            # Resumo Executivo Estruturado
            pdf.set_font("Arial", 'B', 12); pdf.set_fill_color(240); pdf.cell(190, 10, " 1. RESUMO EXECUTIVO DE IMPACTO", ln=True, fill=True)
            pdf.set_font("Arial", '', 11)
            
            # Texto conforme solicitado: X -> X+Y e Z -> Z-n
            texto = (f"O projeto {nome_projeto}, sob gestao de {gerente_nome}, sofreu alteracao devido a: {just_cat}.\n\n"
                     f"O valor do projeto era R$ {v_proj:,.2f} e com esta alteracao passa a ser R$ {v_final:,.2f} (+ R$ {total_extra:,.2f}). "
                     f"Este cenario implica diretamente na rentabilidade do contrato, impactando na margem do projeto de {m_orig}% para {n_margem:.2f}%.\n\n"
                     f"A erosao total de lucratividade e de {abs(n_margem-m_orig):.2f} pontos percentuais, exigindo revisao imediata do plano de custos.")
            pdf.multi_cell(190, 7, texto)
            
            pdf.ln(5); pdf.image(img_path, x=45, w=120)
            
            pdf.ln(10); pdf.set_font("Arial", 'B', 11); pdf.cell(190, 10, " 2. PLANO DE ACAO E JUSTIFICATIVA", ln=True, fill=True)
            pdf.set_font("Arial", 'I', 10); pdf.multi_cell(190, 7, parecer, border=1)
            
            # Bloco de Assinaturas da Diretoria
            pdf.approval_block()

            st.download_button("📥 Baixar Parecer para Assinatura", bytes(pdf.output(dest='S')), f"PARECER_{nome_projeto}.pdf")
            os.remove(img_path)

else:
    st.subheader("📚 Histórico de Auditorias")
    df_hist = pd.read_sql_query("SELECT * FROM historico_pareceres ORDER BY data_emissao DESC", conn)
    st.dataframe(df_hist, use_container_width=True) 