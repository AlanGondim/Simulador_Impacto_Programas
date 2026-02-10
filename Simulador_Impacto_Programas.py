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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recursos_projeto (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto TEXT,
            gerente TEXT,
            recurso TEXT,
            categoria TEXT,
            custo_hora REAL,
            horas INTEGER,
            subtotal REAL,
            data_registro TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico_pareceres (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto TEXT,
            gerente TEXT,
            justificativa_cat TEXT,
            valor_projeto REAL,
            margem_original REAL,
            impacto_financeiro REAL,
            parecer_texto TEXT,
            data_emissao TEXT
        )
    ''')
    conn.commit()
    return conn

# --- CLASSE PDF EXECUTIVA ---
class ExecutiveReport(FPDF):
    def __init__(self, projeto, gerente):
        super().__init__()
        self.projeto = projeto
        self.gerente = gerente

    def header(self):
        # Topo em Azul Marinho
        self.set_fill_color(0, 51, 102)
        self.rect(0, 0, 210, 35, 'F')
        self.set_font("Arial", 'B', 15)
        self.set_text_color(255, 255, 255)
        self.cell(190, 10, "MV PORTFOLIO INTELLIGENCE - PARECER TÉCNICO", ln=True, align='C')
        self.set_font("Arial", '', 9)
        self.cell(190, 5, f"Projeto: {self.projeto} | Responsável: {self.gerente}", ln=True, align='C')
        self.ln(20)

    def watermark(self):
        self.set_font("Arial", 'B', 50)
        self.set_text_color(235, 235, 235)
        with self.rotation(45, 100, 150):
            self.text(35, 190, "CONFIDENCIAL")
        self.set_text_color(0)

# --- INICIALIZAÇÃO ---
st.set_page_config(page_title="MV Simulador Impacto Pro", layout="wide")
conn = init_db()
sns.set_theme(style="whitegrid")

# 1. IDENTIFICAÇÃO DO PROJETO
st.sidebar.title("📂 Menu de Auditoria")
aba = st.sidebar.radio("Navegação", ["Nova Análise", "Consultar Histórico"])

if aba == "Nova Análise":
    st.subheader("📌 1. Identificação do Projeto e Responsável")
    c_id1, c_id2, c_id3 = st.columns([2, 2, 1])
    with c_id1: nome_projeto = st.text_input("Nome do Projeto").upper()
    with c_id2: gerente_nome = st.text_input("Gerente de Projeto")
    with c_id3: 
        just_cat = st.selectbox("Categoria", [
            "Mudança de data de Go Live", "Retreinamento", 
            "Alteração de Especificações Funcionais", "Indisponibilidade de Infraestrutura", "Versão de Produto"
        ])

    # 2. LANÇAMENTO DE CUSTOS
    with st.expander("👤 2. Adicionar Esforço Adicional", expanded=True):
        c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
        with c1: rec_nome = st.text_input("Recurso")
        with c2: cat_prof = st.selectbox("Perfil", ["Consultor", "Analista", "Dev", "Gerente"])
        with c3: v_h = st.number_input("Custo/Hora", value=150.0)
        with c4: hrs = st.number_input("Horas", min_value=1)
        
        if st.button("💾 Gravar Recurso no Banco"):
            if nome_projeto and gerente_nome and rec_nome:
                cursor = conn.cursor()
                total = v_h * hrs
                cursor.execute('''INSERT INTO recursos_projeto 
                                (projeto, gerente, recurso, categoria, custo_hora, horas, subtotal, data_registro) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
                                (nome_projeto, gerente_nome, rec_nome, cat_prof, v_h, hrs, total, datetime.now().isoformat()))
                conn.commit()
                st.success(f"Recurso salvo para o projeto {nome_projeto}")
            else: st.error("Preencha Nome do Projeto, Gerente e Recurso.")

    # 3. ANÁLISE FINANCEIRA
    st.markdown("### 💰 3. Simulação de Impacto Financeiro")
    f1, f2, f3 = st.columns(3)
    with f1: v_proj = st.number_input("Valor Contrato Original (R$)", value=1000000.0)
    with f2: m_original = st.slider("Margem Atual (%)", 0.0, 100.0, 30.0)
    with f3: parecer = st.text_area("Notas Adicionais da Auditoria")

    # Cálculos
    df_db = pd.read_sql_query(f"SELECT * FROM recursos_projeto WHERE projeto = '{nome_projeto}'", conn)
    total_extra = df_db['subtotal'].sum() if not df_db.empty else 0.0
    
    valor_final_projeto = v_proj + total_extra
    lucro_orig = v_proj * (m_original / 100)
    novo_lucro = lucro_orig - total_extra # Considerando que o custo extra sai da margem
    nova_margem = (novo_lucro / v_proj) * 100 if v_proj > 0 else 0

    # Dashboard Streamlit
    st.divider()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Valor Projeto (Original)", f"R$ {v_proj:,.2f}")
    k2.metric("Impacto (Custo Extra)", f"R$ {total_extra:,.2f}", delta_color="inverse")
    k3.metric("Margem Original", f"{m_original}%")
    k4.metric("Nova Margem", f"{nova_margem:.2f}%", f"{nova_margem - m_original:.2f}%", delta_color="inverse")

    # 4. GRÁFICO SEABORN (ANTES E DEPOIS)
    if not df_db.empty:
        st.markdown("### 📈 Visualização de Impacto Nominal")
        fig, ax = plt.subplots(figsize=(10, 5))
        data_plot = pd.DataFrame({
            'Cenário': ['Original', 'Impactado', 'Original', 'Impactado'],
            'Valor (R$)': [v_proj, valor_final_projeto, lucro_orig, novo_lucro],
            'Tipo': ['Custo Total', 'Custo Total', 'Margem Líquida', 'Margem Líquida']
        })
        sns.barplot(data=data_plot, x='Cenário', y='Valor (R$)', hue='Tipo', palette=['#003366', '#B22222'], ax=ax)
        st.pyplot(fig)

    # 5. GERAÇÃO DO RELATÓRIO
    if st.button("🚀 Finalizar Parecer & Gerar PDF"):
        # Salvar histórico
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO historico_pareceres 
                        (projeto, gerente, justificativa_cat, valor_projeto, margem_original, impacto_financeiro, parecer_texto, data_emissao) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                        (nome_projeto, gerente_nome, just_cat, v_proj, m_original, total_extra, parecer, datetime.now().isoformat()))
        conn.commit()

        # Criar PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            fig.savefig(tmp.name, bbox_inches='tight')
            img_path = tmp.name

        pdf = ExecutiveReport(nome_projeto, gerente_nome)
        pdf.add_page(); pdf.watermark()
        
        # RESUMO EXECUTIVO CONCLUSIVO
        pdf.set_font("Arial", 'B', 12)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(190, 10, " 1. RESUMO EXECUTIVO DE IMPACTO", ln=True, fill=True)
        pdf.ln(2)
        pdf.set_font("Arial", '', 11)
        
        conclusao = (
            f"O presente parecer analisa o impacto financeiro no projeto {nome_projeto}, sob gestão de {gerente_nome}, "
            f"decorrente da categoria: {just_cat}.\n\n"
            f"Originalmente orçado em R$ {v_proj:,.2f} com uma margem de rentabilidade de {m_original}%, o projeto sofreu um "
            f"incremento de custo operacional de R$ {total_extra:,.2f}. Com esta alteração, o custo consolidado passa a ser "
            f"R$ {valor_final_projeto:,.2f}, resultando na erosão direta do lucro líquido.\n\n"
            f"O impacto nominal reduz a margem do projeto de {m_original}% para {nova_margem:.2f}%, "
            f"representando uma perda de {abs(nova_margem - m_original):.2f} pontos percentuais de lucratividade."
        )
        pdf.multi_cell(190, 7, conclusao)
        
        pdf.ln(5); pdf.image(img_path, x=35, w=140)
        
        # DETALHAMENTO DE RECURSOS
        pdf.ln(10); pdf.set_font("Arial", 'B', 11); pdf.cell(190, 10, " 2. DETALHAMENTO DE RECURSOS ADICIONAIS", ln=True, fill=True)
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(80, 8, " Recurso", 1); pdf.cell(40, 8, " Perfil", 1); pdf.cell(30, 8, " Horas", 1); pdf.cell(40, 8, " Subtotal", 1, ln=True)
        pdf.set_font("Arial", '', 9)
        for _, row in df_db.iterrows():
            pdf.cell(80, 8, f" {row['recurso']}", 1); pdf.cell(40, 8, f" {row['categoria']}", 1)
            pdf.cell(30, 8, f" {row['horas']}", 1); pdf.cell(40, 8, f" R$ {row['subtotal']:,.2f}", 1, ln=True)

        pdf_bytes = pdf.output(dest='S')
        st.download_button("📥 Baixar Parecer Executivo", bytes(pdf_bytes), f"AUDITORIA_{nome_projeto}.pdf")
        os.remove(img_path)

else:
    st.subheader("📚 Histórico de Auditorias")
    df_hist = pd.read_sql_query("SELECT * FROM historico_pareceres ORDER BY data_emissao DESC", conn)
    st.dataframe(df_hist, use_container_width=True)


