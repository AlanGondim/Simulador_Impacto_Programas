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
    return (o + 4 * m + p) / 6

def simular_monte_carlo(o, m, p, n=2000):
    if o >= p: return m, m
    simulacoes = np.random.triangular(o, m, p, n)
    return np.mean(simulacoes), np.percentile(simulacoes, 95)

# --- BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('mv_simulador_impacto_programas.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS recursos_projeto 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, projeto TEXT, função TEXT, 
        senioridade TEXT, custo_hora REAL, horas INTEGER, subtotal REAL, data_registro TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS historico_pareceres 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, projeto TEXT, gerente TEXT, categoria TEXT, justificativa TEXT, 
        receita REAL, custos_atuais REAL, margem_anterior REAL, impacto_financeiro REAL, 
        p_otimista REAL, p_pessimista REAL, p_pert_resultado REAL, 
        d_otimista REAL, d_provavel REAL, d_pessimista REAL, d_pert_resultado REAL,
        p_mc_resultado REAL, total_horas INTEGER, data_emissao TEXT)''')
    conn.commit()
    return conn

# --- CLASSE PDF EXECUTIVA MASTER (COM MARCA D'ÁGUA E ASSINATURAS) ---
class ExecutiveReport(FPDF):
    def __init__(self, dados, df_recursos=None, grafico_path=None):
        super().__init__()
        self.d = dados
        self.df_recursos = df_recursos
        self.grafico_path = grafico_path

    def header(self):
        # Topo azul escuro corporativo
        self.set_fill_color(0, 51, 102); self.rect(0, 0, 210, 45, 'F')
        # Marca d'água 45 graus
        self.set_font('Arial', 'B', 50); self.set_text_color(230, 230, 230)
        with self.rotation(45, 100, 150):
            self.text(40, 190, "CONFIDENCIAL")
        
        self.set_font("Arial", 'B', 16); self.set_text_color(255)
        self.set_y(10); self.cell(190, 15, "DOSSIE DE IMPACTO E GOVERNANCA ECONOMICA", ln=True, align='C')
        self.set_font("Arial", 'B', 10)
        self.cell(190, 5, f"PROGRAMA: {self.d['projeto']} | RESPONSAVEL: {self.d['gerente'].upper()}", ln=True, align='C')
        self.ln(25)

    def footer(self):
        self.set_y(-40)
        self.set_font("Arial", 'B', 8); self.set_text_color(0)
        # Linhas de assinatura
        self.line(20, self.get_y(), 90, self.get_y())
        self.line(120, self.get_y(), 190, self.get_y())
        self.set_y(self.get_y() + 2)
        self.set_x(20); self.cell(70, 5, "GERENTE DO PROGRAMA", align='C')
        self.set_x(120); self.cell(70, 5, "DIRETOR DE OPERACOES", align='C')

    def section(self, title):
        self.set_font("Arial", 'B', 11); self.set_fill_color(235, 235, 235); self.set_text_color(0, 51, 102)
        self.cell(190, 9, f" {title}", ln=True, fill=True); self.ln(3)

# --- INTERFACE ---
st.set_page_config(page_title="MV Simulador PRO", layout="wide")
conn = init_db()

st.sidebar.title("🛡️ MV SIMULADOR IMPACTO PRO")
aba = st.sidebar.radio("Menu Principal", ["Nova Análise", "Hub de Inteligência"])

if aba == "Nova Análise":
    # 1. INFORMAÇÕES DO PROGRAMA
    st.markdown("<h2 style='color: #003366;'>📊 1. INFORMAÇÕES DO PROGRAMA</h2>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        progs = [" ", "INS", "UNIMED SERRA GAUCHA", "UNIMED NORTE FLUMINENSE", "CLINICA GIRASSOL", "GUATEMALA", "GOOD HOPE", "EINSTEIN","MOGI DAS CRUZES", "SESA/ES", "CEMA", "RHP", "SESI/RS"]
        nome_projeto = st.selectbox("1.1. Selecione o Programa", progs)
        receita = st.number_input("1.2. Receita Líquida (R$)", value=0.0, step=1000.0)
    with c2:
        gerente_nome = st.text_input("1.3. Gerente Responsável")
        custos_at = st.number_input("1.4. Custos Totais ERP (R$)", value=0.0, step=1000.0)
    
    lista_categorias = [" ", "Go Live", "Retreinamento", "Especificações Funcionais", "Indisponibilidade de Infraestrutura", "Replanejamento", "Incompatibilidade de versão implantada"]
    cats = st.multiselect("1.5. Categoria(s) do Desvio", lista_categorias)
    justificativa = st.text_area("1.6. Justificativa Técnica Detalhada")

    # 2. ALOCAÇÃO DE RECURSOS
    st.markdown("<h2 style='color: #003366;'>👥 2. ALOCAÇÃO DE RECURSOS</h2>", unsafe_allow_html=True)

   # Formulário de Adição
    with st.expander("➕ Adicionar Novo Recurso", expanded=True):
        with st.form("form_add_rec", clear_on_submit=True):
            f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
            func = f1.selectbox("Função", ["Gerente", "Analista", "Consultor", "Dev"])
            seni = f2.selectbox("Senioridade", ["Jr", "Pl", "Sr"])
            vh = f3.number_input("Custo/Hora", value=150.0, step=5.0)
            hrs = f4.number_input("Horas", min_value=1)
            if st.form_submit_button("Confirmar Inclusão"):
                conn.cursor().execute("INSERT INTO recursos_projeto VALUES (NULL,?,?,?,?,?,?,?)", (nome_projeto, func, seni, vh, hrs, vh*hrs, datetime.now().isoformat()))
                conn.commit()
                st.rerun()

    # Gestão de Recursos Existentes (Alterar/Excluir)
    df_rec = pd.read_sql_query(f"SELECT id, função, senioridade, custo_hora, horas, subtotal FROM recursos_projeto WHERE projeto = '{nome_projeto}'", conn)
    
    if not df_rec.empty:
        st.markdown("### Recursos Alocados")
        # Exibição formatada
        df_show = df_rec.copy()
        df_show['custo_hora'] = df_show['custo_hora'].apply(format_moeda)
        df_show['subtotal'] = df_show['subtotal'].apply(format_moeda)
        st.dataframe(df_show.drop(columns=['id']), use_container_width=True)

        col_edit, col_del = st.columns(2)
        with col_edit:
            id_para_editar = st.selectbox("📝 Selecione um Recurso para AJUSTAR", df_rec['id'].tolist(), format_func=lambda x: f"ID {x} - {df_rec[df_rec['id']==x]['função'].values[0]}")
            
            with st.form("form_edit_rec"):
                rec_sel = df_rec[df_rec['id'] == id_para_editar].iloc[0]
                e1, e2, e3 = st.columns(3)
                new_vh = e1.number_input("Novo Custo/Hora", value=float(rec_sel['custo_hora']), step=5.0)
                new_hrs = e2.number_input("Novas Horas", value=int(rec_sel['horas']))
                if st.form_submit_button("💾 Salvar Alterações"):
                    conn.cursor().execute("UPDATE recursos_projeto SET custo_hora = ?, horas = ?, subtotal = ? WHERE id = ?", (new_vh, new_hrs, new_vh*new_hrs, id_para_editar))
                    conn.commit()
                    st.success("Recurso atualizado!")
                    st.rerun()

        with col_del:
            id_para_excluir = st.selectbox("🗑️ Selecione um Recurso para EXCLUIR", df_rec['id'].tolist(), key="del_sel")
            if st.button("❌ Remover Permanentemente", type="primary"):
                conn.cursor().execute("DELETE FROM recursos_projeto WHERE id = ?", (id_para_excluir,))
                conn.commit()
                st.warning("Recurso removido!")
                st.rerun()

        total_imp = df_rec['subtotal'].sum()
        total_hrs = int(df_rec['horas'].sum())

        # 3. EROSÃO DE MARGEM
        st.markdown("<h2 style='color: #003366;'>📉 3. EROSÃO DE MARGEM</h2>", unsafe_allow_html=True)
        m_ant = ((receita - custos_at) / receita * 100) if receita > 0 else 0
        m_pos = (((receita - custos_at) - total_imp) / receita * 100) if receita > 0 else 0
        
        col_g1, col_g2 = st.columns([1.5, 1])
        with col_g1:
            fig, ax = plt.subplots(figsize=(7, 4))
            sns.barplot(x=['Margem Atual', 'Margem Pós-Impacto'], y=[m_ant, m_pos], palette=['#003366', '#C0392B'], ax=ax)
            for i, v in enumerate([m_ant, m_pos]):
                ax.text(i, v + 0.5, f"{v:.2f}%", ha='center', fontweight='bold', size=12)
            st.pyplot(fig)
        with col_g2:
            st.metric("Margem Original", f"{m_ant:.2f}%")
            st.metric("Erosão Projetada", f"{m_pos:.2f}%", f"{m_pos - m_ant:.2f}%", delta_color="normal")

        # 4. MODELAGEM DE INCERTEZA
        st.markdown("<h2 style='color: #003366;'>🎲 4. MODELAGEM DE INCERTEZA</h2>", unsafe_allow_html=True)
        cp1, cp2 = st.columns(2)
        with cp1:
            st.subheader("Financeiro (PERT/Monte Carlo)")
            c_ot = st.number_input("Custo Otimista", value=total_imp * 0.9, step=1000.0)
            c_pe = st.number_input("Custo Pessimista", value=total_imp * 1.5, step=1000.0 )
            res_c_pert = calcular_pert(c_ot, total_imp, c_pe)
            _, p95_mc = simular_monte_carlo(c_ot, total_imp, c_pe)
            st.success(f"**Exposição PERT:** {format_moeda(res_c_pert)}")
            st.warning(f"**Teto de Risco P95:** {format_moeda(p95_mc)}")
        with cp2:
            st.subheader("Prazo (Dias Úteis)")
            d_prov = total_hrs / 8
            d_ot = st.number_input("Prazo Otimista", value=d_prov * 0.8, step=1.0)
            d_pe = st.number_input("Prazo Pessimista", value=d_prov * 2.0, step=1.0)
            res_d_pert = calcular_pert(d_ot, d_prov, d_pe)
            st.info(f"**Duração Esperada:** {res_d_pert:.1f} Dias")

        if st.button("🚀 PROTOCOLAR E GERAR PROTOCOLO"):
            sql = '''INSERT INTO historico_pareceres (projeto, gerente, categoria, justificativa, receita, custos_atuais, margem_anterior, impacto_financeiro, p_otimista, p_pessimista, p_pert_resultado, d_otimista, d_provavel, d_pessimista, d_pert_resultado, p_mc_resultado, total_horas, data_emissao) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'''
            conn.cursor().execute(sql, (nome_projeto, gerente_nome, ", ".join(cats), justificativa, receita, custos_at, m_ant, total_imp, c_ot, c_pe, res_c_pert, d_ot, d_prov, d_pe, res_d_pert, p95_mc, total_hrs, datetime.now().isoformat()))
            conn.commit(); st.success("Dossiê Protocolado no Hub!")

else:
    st.header("📚 Hub de Inteligência Corporativa")
    df_h = pd.read_sql_query("SELECT * FROM historico_pareceres ORDER BY data_emissao DESC", conn)
    for i, row in df_h.iterrows():
        with st.expander(f"📋 {row['projeto']} | Gerente: {row['gerente']} | PERT: {format_moeda(row['p_pert_resultado'])}"):
            st.markdown(f"**Categorias:** {row['categoria']}")
            st.markdown(f"**Justificativa Técnica:** {row['justificativa']}")
            
            # Dados Financeiros Interativos
            m_pos_h = (((row['receita']-row['custos_atuais'])-row['impacto_financeiro'])/row['receita']*100) if row['receita'] > 0 else 0
            df_det = pd.DataFrame({
                "KPI": ["Receita Líquida", "Custos Totais (ERP)", "Margem Atual", "Impacto Nominal", "Custo PERT (Risco)", "Teto MC P95", "Margem Final"],
                "Valor": [
                    format_moeda(row['receita']), 
                    format_moeda(row['custos_atuais']), 
                    f"{row['margem_anterior']:.2f}%",
                    format_moeda(row['impacto_financeiro']), 
                    format_moeda(row['p_pert_resultado']), 
                    format_moeda(row['p_mc_resultado']), 
                    f"{m_pos_h:.2f}%"
                ]
            })
            st.table(df_det)
            
            # Buscar analítico de recursos para o dossiê
            df_recursos_h = pd.read_sql_query(f"SELECT função, senioridade, horas, subtotal FROM recursos_projeto WHERE projeto = '{row['projeto']}'", conn)
            st.markdown("**Analítico de Recursos Alocados:**")
            st.dataframe(df_recursos_h, use_container_width=True)
            
            
            if st.button(f"📥 GERAR DOSSIÊ PREMIUM", key=f"pdf_{row['id']}"):
                # Gerar gráfico temporário para o PDF
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
                    fig_h, ax_h = plt.subplots(figsize=(5, 3))
                    sns.barplot(x=['Atual', 'Pós-Impacto'], y=[row['margem_anterior'], m_pos_h], palette=['#003366', '#C0392B'], ax=ax_h)
                    ax_h.set_title("Erosão de Margem (%)")
                    fig_h.savefig(tmpfile.name)
                    grafico_path = tmpfile.name

                pdf = ExecutiveReport(row.to_dict(), df_recursos=df_recursos_h, grafico_path=grafico_path)
                pdf.add_page()
                
                pdf.section("1. INFORMACOES DO PROGRAMA")
                pdf.set_font("Arial", '', 10); pdf.set_text_color(0)
                pdf.multi_cell(190, 7, f"CATEGORIAS: {row['categoria']}\nJUSTIFICATIVA: {row['justificativa']}")
                
                pdf.ln(2)
                pdf.section("2. ANALISE FINANCEIRA E EROSAO")
                pdf.cell(95, 7, f"Receita Liquida: {format_moeda(row['receita'])}", ln=0)
                pdf.cell(95, 7, f"Custos Atuais (ERP): {format_moeda(row['custos_atuais'])}", ln=1)
                pdf.cell(95, 7, f"Margem Anterior: {row['margem_anterior']:.2f}%", ln=0)
                pdf.cell(95, 7, f"Margem Pos-Impacto: {m_pos_h:.2f}%", ln=1)
                pdf.cell(190, 7, f"Impacto Nominal Estimado: {format_moeda(row['impacto_financeiro'])}", ln=1)
                
                # Plotar gráfico no PDF
                pdf.image(grafico_path, x=130, y=105, w=60)
                
                pdf.ln(5)
                pdf.section("3. ANALITICO DE RECURSOS ALOCADOS")
                pdf.set_font("Arial", 'B', 9)
                pdf.cell(50, 7, "Funcao", 1); pdf.cell(40, 7, "Senioridade", 1); pdf.cell(30, 7, "Horas", 1); pdf.cell(70, 7, "Subtotal", 1); pdf.ln()
                pdf.set_font("Arial", '', 9)
                for _, rec in df_recursos_h.iterrows():
                    pdf.cell(50, 7, str(rec['função']), 1)
                    pdf.cell(40, 7, str(rec['senioridade']), 1)
                    pdf.cell(30, 7, str(rec['horas']), 1)
                    pdf.cell(70, 7, format_moeda(rec['subtotal']), 1); pdf.ln()

                pdf.ln(5); pdf.section("4. MODELAGEM ESTATISTICA (RISCO)")
                pdf.multi_cell(190, 7, f"Custo PERT Esperado: {format_moeda(row['p_pert_resultado'])}\nTeto de Risco (Monte Carlo 95%): {format_moeda(row['p_mc_resultado'])}\nEsforco Total: {row['total_horas']} horas | Prazo (PERT): {row['d_pert_resultado']:.1f} dias.")
                
                st.download_button("Clique aqui para baixar o PDF", bytes(pdf.output(dest='S')), f"PREMIUM_{row['projeto']}.pdf")
                
                # Limpar arquivo temporário
                if os.path.exists(grafico_path):
                    os.remove(grafico_path)






