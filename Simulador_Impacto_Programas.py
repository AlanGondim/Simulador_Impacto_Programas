import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from fpdf import FPDF
from datetime import datetime
import tempfile
import os

# --- MOTOR DE BANCO DE DADOS (Persistente no Streamlit Cloud) ---
def init_db():
    # Usamos o st.connection para garantir que a conexão persista no deploy
    conn = st.connection('solicitacoes_db', type='sql')
    
    # Criamos as tabelas se não existirem
    with conn.session as s:
        s.execute('''CREATE TABLE IF NOT EXISTS recursos_projeto 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, projeto TEXT, gerente TEXT, recurso TEXT, 
            categoria TEXT, custo_hora REAL, horas INTEGER, subtotal REAL, data_registro TEXT)''')
        s.execute('''CREATE TABLE IF NOT EXISTS historico_pareceres 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, projeto TEXT, gerente TEXT, justificativa_cat TEXT, 
            valor_projeto REAL, margem_original REAL, impacto_financeiro REAL, parecer_texto TEXT, data_emissao TEXT)''')
        s.commit()
    return conn

# --- CLASSE PDF ---
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
        self.ln(25); curr_y = self.get_y()
        self.line(20, curr_y + 15, 90, curr_y + 15)
        self.line(120, curr_y + 15, 190, curr_y + 15)
        self.set_font("Arial", 'B', 10); self.set_y(curr_y + 18)
        self.set_x(20); self.cell(70, 10, "GERENTE DE PROJETO", align='C')
        self.set_x(120); self.cell(70, 10, "DIRETORIA DE OPERACOES", align='C')

# --- INICIALIZAÇÃO ---
st.set_page_config(page_title="MV Simulador de Impacto em Programas Pro", layout="wide")
db_conn = init_db()
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
                with db_conn.session as s:
                    s.execute("INSERT INTO recursos_projeto (projeto, gerente, recurso, categoria, custo_hora, horas, subtotal, data_registro) VALUES (:p, :g, :r, :c, :ch, :h, :s, :d)",
                               {"p": nome_projeto, "g": gerente_nome, "r": rec, "c": cat, "ch": vh, "h": hr, "s": vh*hr, "d": datetime.now().isoformat()})
                    s.commit()
                st.success("Recurso Gravado com Sucesso!")
            else: st.warning("Campos Obrigatórios ausentes.")

    st.markdown("### 💰 3. Analise de Erosao de Margem")
    f1, f2, f3 = st.columns(3)
    with f1: v_proj = st.number_input("Valor Contrato (R$)", value=1000000.0)
    with f2: m_orig = st.slider("Margem Original (%)", 0.0, 100.0, 35.0)
    with f3: parecer = st.text_area("Justificativa e Plano de Ação")

    # Busca segura usando o st.connection
    df_db = db_conn.query(f"SELECT * FROM recursos_projeto WHERE projeto = '{nome_projeto}'")
    
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

    fig, ax = plt.subplots(figsize=(10, 5))
    plot_data = pd.DataFrame({
        'Status': ['Original', 'Original', 'Impactado', 'Impactado'],
        'Metrica': ['Valor Contrato', 'Lucro Liquido', 'Valor Contrato', 'Lucro Liquido'],
        'Valor (R$)': [v_proj, lucro_orig, v_final, novo_lucro]
    })
    cor_lucro = "#B24B22" if n_margem >= 10 else "#FF0000"
    sns.barplot(data=plot_data, x='Status', y='Valor (R$)', hue='Metrica', palette=["#1B6DBE", cor_lucro], ax=ax)
    for container in ax.containers: ax.bar_label(container, fmt='R$ {:,.2f}', padding=3)
    ax.set_ylim(0, max(v_proj, v_final) * 1.25)
    st.pyplot(fig)

    if st.button("🚀 Gerar Parecer e Protocolar"):
        if total_extra == 0: st.error("Adicione recursos primeiro.")
        else:
            with db_conn.session as s:
                s.execute("INSERT INTO historico_pareceres (projeto, gerente, justificativa_cat, valor_projeto, margem_original, impacto_financeiro, parecer_texto, data_emissao) VALUES (:p, :g, :j, :v, :m, :i, :pt, :d)",
                           {"p": nome_projeto, "g": gerente_nome, "j": just_cat, "v": v_proj, "m": m_orig, "i": total_extra, "pt": parecer, "d": datetime.now().isoformat()})
                s.commit()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                fig.savefig(tmp.name, bbox_inches='tight')
                pdf = ExecutiveReport(nome_projeto, gerente_nome)
                pdf.add_page(); pdf.watermark()
                pdf.set_font("Arial", 'B', 12); pdf.set_fill_color(240); pdf.cell(190, 10, " 1. RESUMO EXECUTIVO DE IMPACTO", ln=True, fill=True)
                pdf.set_font("Arial", '', 11)
                texto = (f"O projeto {nome_projeto} sofreu alteracao devido a: {just_cat}. Valor original R$ {v_proj:,.2f} -> Novo R$ {v_final:,.2f}. Margem caiu de {m_orig}% para {n_margem:.2f}%.")
                pdf.multi_cell(190, 7, texto)
                pdf.image(tmp.name, x=45, w=120)
                pdf.approval_block()
                st.download_button("📥 Baixar Parecer", bytes(pdf.output(dest='S')), f"PARECER_{nome_projeto}.pdf")
            os.remove(tmp.name)

else:
    st.subheader("📚 Histórico de Auditorias")
    # Consulta robusta
    df_hist = db_conn.query("SELECT * FROM historico_pareceres ORDER BY data_emissao DESC")
    st.dataframe(df_hist, use_container_width=True)
