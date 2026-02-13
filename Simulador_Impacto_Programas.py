import streamlit as st
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from fpdf import FPDF
from datetime import datetime
import tempfile

# --- FUNÇÕES DE ESTATÍSTICA ---
def format_moeda(valor):
    """Formata para o padrão brasileiro: R$ 1.000,00"""
    # f"{valor:,.2f}" gera 1,234.56
    # Invertemos para o padrão BR: ponto para milhar, vírgula para decimal
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def calcular_pert(o, m, p):
    return (o + 4 * m + p) / 6

def simular_monte_carlo(o, m, p, n=2000):
    if o >= p: return m, m
    simulacoes = np.random.triangular(o, m, p, n)
    return np.mean(simulacoes), np.percentile(simulacoes, 95) # P95 para segurança executiva

# --- BANCO DE DADOS (V19) ---
def init_db():
    conn = sqlite3.connect('mv_impacto_programas.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS recursos_projeto 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, projeto TEXT, função TEXT, 
        senioridade TEXT, custo_hora REAL, horas INTEGER, subtotal REAL, data_registro TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS historico_pareceres 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, projeto TEXT, gerente TEXT, justificativa TEXT, 
        receita REAL, custos_atuais REAL, margem_anterior REAL, impacto_financeiro REAL, 
        p_otimista REAL, p_pessimista REAL, p_pert_resultado REAL, 
        d_otimista REAL, d_provavel REAL, d_pessimista REAL, d_pert_resultado REAL,
        p_mc_resultado REAL, total_horas INTEGER, data_emissao TEXT)''')
    conn.commit()
    return conn

# --- CLASSE PDF EXECUTIVA MASTER (LAYOUT PREMIUM) ---
class ExecutiveReport(FPDF):
    def __init__(self, dados):
        super().__init__()
        self.d = dados
    def header(self):
        self.set_fill_color(0, 51, 102); self.rect(0, 0, 210, 45, 'F')
        self.set_font("Arial", 'B', 18); self.set_text_color(255)
        self.cell(190, 15, "DOSSIÊ DE IMPACTO E GOVERNANÇA ECONÔMICA", ln=True, align='C')
        self.set_font("Arial", 'B', 10); self.cell(190, 5, f"PROGRAMA: {self.d['projeto']} | GERENTE: {self.d['gerente'].upper()}", ln=True, align='C')
        self.ln(20)
    def section(self, title):
        self.set_font("Arial", 'B', 12); self.set_fill_color(240, 240, 240); self.set_text_color(0, 51, 102)
        self.cell(190, 10, f"  {title}", ln=True, fill=True); self.ln(3)

# --- INTERFACE ---
st.set_page_config(page_title="MV Simulador Impacto PRO", layout="wide")
conn = init_db()

st.sidebar.title("🛡️ MV IMPACTO PRO")
aba = st.sidebar.radio("Navegação", ["Nova Análise", "Hub de Inteligência"])

if aba == "Nova Análise":
    st.markdown("<h2 style='color: #003366;'>📊 1. INFORMAÇÕES DO PROGRAMA</h2>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        nome_projeto = st.selectbox("Programa", [" ", "INS", "UNIMED SERRA GAUCHA","UNIMED NORTE FLUMINENSE", "CLINICA GIRASSOL","GUATEMALA", "GOOD HOPE", "EINSTEIN", "MOGI DAS CRUZES", "SESA/ES", "CEMA", "RHP", "SESI/RS"])
        receita = st.number_input("Receita Líquida (R$)", value=1000.0, step=1000.0)
    with c2:
        gerente_nome = st.text_input("Gerente Responsável")
        custos_at = st.number_input("Custos Totais ERP (R$)", value=0.0, step=1000.0)
    
    justificativa = st.text_area("Justificativa Técnica do Desvio")

    st.markdown("<h2 style='color: #003366;'>👥 2. ALOCAÇÃO DE RECURSOS E CUSTOS</h2>", unsafe_allow_html=True)
    with st.form("form_rec"):
        f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
        func = f1.selectbox("Função", ["Gerente", "Analista", "Consultor", "Dev"])
        seni = f2.selectbox("Senioridade", ["Jr", "Pl", "Sr"])
        vh = f3.number_input("Custo/Hora", value=150.0, step=5.0)
        hrs = f4.number_input("Horas Extras", min_value=1)
        if st.form_submit_button("➕ Adicionar Esforço"):
            conn.cursor().execute("INSERT INTO recursos_projeto VALUES (NULL,?,?,?,?,?,?,?)", (nome_projeto, func, seni, vh, hrs, vh*hrs, datetime.now().isoformat()))
            conn.commit()

    df_rec = pd.read_sql_query(f"SELECT * FROM recursos_projeto WHERE projeto = '{nome_projeto}'", conn)
    if not df_rec.empty:
        df_display = df_rec[['função', 'senioridade', 'custo_hora', 'horas', 'subtotal']].copy()
        df_display['custo_hora'] = df_display['custo_hora'].apply(format_moeda)
        df_display['subtotal'] = df_display['subtotal'].apply(format_moeda)
        
        st.table(df_display)
        
        total_impacto = df_rec['subtotal'].sum()
        total_horas = int(df_rec['horas'].sum())

        st.markdown("<h2 style='color: #003366;'>🎲 3. MODELAGEM DE INCERTEZA (PRAZO & CUSTO)</h2>", unsafe_allow_html=True)
        col_pert1, col_pert2 = st.columns(2)
        
        with col_pert1:
            st.subheader("📅 PERT de Prazo (Dias)")
            d_prov = total_horas / 8 # Estimativa base 8h/dia
            d_ot = st.number_input("Prazo Otimista (Dias)", value=d_prov * 0.8)
            d_pe = st.number_input("Prazo Pessimista (Dias)", value=d_prov * 2.0)
            res_d_pert = calcular_pert(d_ot, d_prov, d_pe)
            st.metric("Duração Esperada (PERT)", f"{res_d_pert:.1f} Dias")

        with col_pert2:
            st.subheader("💰 PERT de Custo (Financeiro)")
            c_ot = st.number_input("Custo Otimista (R$)", value=total_impacto * 0.9)
            c_pe = st.number_input("Custo Pessimista (R$)", value=total_impacto * 1.5)
            res_c_pert = calcular_pert(c_ot, total_impacto, c_pe)
            mean_mc, p95_mc = simular_monte_carlo(c_ot, total_impacto, c_pe)
            st.metric("Exposição Financeira (PERT)", format_moeda(res_c_pert))
            st.metric("Risco Probabilístico (Monte Carlo P95)", format_moeda(p95_mc))

    if st.button("🚀 Protocolar Reequilíbrio"):
        sql = '''INSERT INTO historico_pareceres (projeto, gerente, justificativa, receita, custos_atuais, margem_anterior, impacto_financeiro, p_otimista, p_pessimista, p_pert_resultado, d_otimista, d_provavel, d_pessimista, d_pert_resultado, p_mc_resultado, total_horas, data_emissao) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'''
        conn.cursor().execute(sql, (nome_projeto, gerente_nome, justificativa, receita, custos_at, (receita-custos_at)/receita*100, total_impacto, c_ot, c_pe, res_c_pert, d_ot, d_prov, d_pe, res_d_pert, p95_mc, total_horas, datetime.now().isoformat()))
        conn.commit(); st.success("Protocolado!")

else:
    st.header("📚 Hub de Inteligência Corporativa")
    df_h = pd.read_sql_query("SELECT * FROM historico_pareceres ORDER BY data_emissao DESC", conn)
    for i, row in df_h.iterrows():
        with st.expander(f"📋 {row['projeto']} | Gerente: {row['gerente']} | Status: Protocolado"):
            st.markdown(f"**Justificativa:** {row['justificativa']}")
            
            # Layout do Hub conforme solicitado
            df_fin = pd.DataFrame({"Indicador": ["Receita", "Impacto PERT", "Horas Totais"], "Valor": [format_moeda(row['receita']), format_moeda(row['p_pert_resultado']), f"{row['total_horas']}h"]})
            st.table(df_fin)
            
            if st.button(f"📥 Gerar Dossiê Premium", key=f"pdf_{row['id']}"):
                pdf = ExecutiveReport(row.to_dict()); pdf.add_page()
                
                pdf.section("1. ANÁLISE DE MARGEM E DRE")
                m_pos = (((row['receita']-row['custos_atuais'])-row['impacto_financeiro'])/row['receita']*100)
                pdf.set_font("Arial", '', 10); pdf.cell(190, 7, f"Receita: {format_moeda(row['receita'])} | Margem Anterior: {row['margem_anterior']:.2f}% | Margem Pos: {m_pos:.2f}%", ln=True)
                
                pdf.ln(5); pdf.section("2. MODELAGEM DE CONFIANCA (MONTE CARLO & PERT)")
                txt_est = (f"Para este desvio, aplicamos 2.000 iteracoes de Monte Carlo. "
                           f"O Custo PERT calculado foi de {format_moeda(row['p_pert_resultado'])}. "
                           f"A simulacao Monte Carlo P95 indica uma reserva de {format_moeda(row['p_mc_resultado'])} "
                           f"para cobrir 95% dos cenários de risco financeiro.")
                pdf.multi_cell(190, 7, txt_est)
                
                pdf.ln(5); pdf.section("3. ENGENHARIA DE CRONOGRAMA (PERT PRAZO)")
                txt_prazo = (f"Duração Otimista: {row['d_otimista']:.1f} dias | Provavel: {row['d_provavel']:.1f} dias | Pessimista: {row['d_pessimista']:.1f} dias.\n"
                             f"DURACAO ESPERADA DO IMPACTO: {row['d_pert_resultado']:.1f} DIAS UTEIS.")
                pdf.multi_cell(190, 7, txt_prazo)
                
                st.download_button("Salvar Dossiê", bytes(pdf.output(dest='S')), f"DOSSIE_MV_{row['projeto']}.pdf")







