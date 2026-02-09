import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import re
import requests
import json
from datetime import datetime
import urllib.parse

# --- CONFIGURAÇÃO DE INTEGRAÇÃO (Backend) ---
# Seu Link do Google Apps Script
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbyonfmXBRHuokBbHHtt3lmtgvtwICcomgOJh3pz_ToUDUZRjeYNxb29b5sRRhztc54-/exec"

# --- CONFIGURAÇÃO DE TESTE ---
MODO_TESTE = True 
ZAP_TESTE = "5519992071423" 

# --- CONFIGURAÇÃO DA PÁGINA ---
URL_CSV = "Cadastro dos Lifegroups.csv"
st.set_page_config(page_title="LifeGroups | Paz São Paulo", page_icon="💙", layout="centered")

# --- ESTILOS CSS ---
st.markdown("""
<style>
    div.stButton > button:first-child {
        width: 100%;
        background-color: #1C355E;
        color: white;
        border-radius: 8px;
        font-weight: bold;
        text-transform: uppercase;
    }
    .filter-label { font-weight: 600; color: #1C355E; }
    h1 { color: #1C355E; }
    
    /* Ajuste das Abas para não cortar texto no celular */
    .stTabs [data-baseweb="tab-list"] { 
        gap: 8px; 
    }
    .stTabs [data-baseweb="tab"] { 
        background-color: #f0f2f6; 
        color: #1C355E; 
        font-weight: bold;
        padding: 10px 15px; /* Reduzi o padding lateral */
        font-size: 14px; /* Fonte levemente menor para caber */
    }
    .stTabs [aria-selected="true"] { 
        background-color: #1C355E; 
        color: white; 
    }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES ---
def extrair_zap(texto):
    if pd.isna(texto): return None
    limpo = str(texto).replace("-", "").replace("(", "").replace(")", "").replace(" ", "")
    encontrado = re.search(r'\d{10,13}', limpo)
    if encontrado:
        num = encontrado.group()
        return '55' + num if not num.startswith('55') else num
    return None

def limpar_endereco_visual(location):
    """
    Função melhorada para garantir que sempre mostre Rua e Bairro,
    mesmo que o geocoder devolva os dados desorganizados.
    """
    try:
        end = location.raw.get('address', {})
        rua = end.get('road', '')
        numero = end.get('house_number', '')
        bairro = end.get('suburb', end.get('neighbourhood', ''))
        cidade = end.get('city', end.get('town', end.get('municipality', '')))
        
        partes = []
        if rua: partes.append(rua)
        if numero: partes.append(numero)
        if bairro: partes.append(bairro)
        
        texto_final = ", ".join(partes)
        
        if cidade: 
            texto_final += f" - {cidade}"
            
        # Se ficou muito curto (tipo só "681"), pega o endereço bruto (primeiras 2 partes)
        if len(texto_final) < 5 or not rua:
            bruto = location.address.split(',')
            if len(bruto) >= 2:
                return f"{bruto[0]}, {bruto[1]}" # Pega Rua e Bairro/Cidade do bruto
            return location.address # Pega tudo se falhar
            
        return texto_final
    except:
        # Fallback total
        return location.address.split(',')[0]

def enviar_para_webhook(dados):
    if not WEBHOOK_URL:
        return False, "URL do Webhook não configurada."
    try:
        headers = {"Content-Type": "application/json"}
        response = requests.post(WEBHOOK_URL, data=json.dumps(dados), headers=headers)
        
        if response.status_code == 200:
            try:
                resposta = response.json()
                if resposta.get("status") == "success":
                    return True, resposta.get("message", "Sucesso")
                else:
                    return False, resposta.get("message", "Erro desconhecido no Script")
            except:
                 return True, "Sucesso (Sem JSON)"
        else:
            return False, f"Erro HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)

@st.cache_data(ttl=600)
def carregar_dados():
    try:
        df = pd.read_csv(URL_CSV)
        df.columns = df.columns.str.strip()
        df = df.dropna(subset=['Nome do Life'])
        geolocator = Nominatim(user_agent="app_paz_v5_fix")
        latitudes = []
        longitudes = []
        for endereco in df['Endereço']:
            if not isinstance(endereco, str) or endereco.strip() == "":
                latitudes.append(None); longitudes.append(None)
                continue
            try:
                query = f"{endereco}, Brasil"
                loc = geolocator.geocode(query, timeout=10)
                if loc:
                    latitudes.append(loc.latitude); longitudes.append(loc.longitude)
                else:
                    latitudes.append(None); longitudes.append(None)
            except:
                latitudes.append(None); longitudes.append(None)
        df['lat'] = latitudes
        df['lon'] = longitudes
        return df.dropna(subset=['lat', 'lon'])
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

def obter_lat_lon_usuario(endereco):
    geolocator = Nominatim(user_agent="app_paz_user_v5")
    try:
        query = f"{endereco}, São Paulo, Brasil"
        loc = geolocator.geocode(query)
        if not loc: loc = geolocator.geocode(f"{endereco}, Brasil")
        if loc:
            return loc.latitude, loc.longitude, limpar_endereco_visual(loc)
        return None, None, None
    except:
        return None, None, None

def exibir_cartoes(dataframe, nome_user, zap_user, is_online=False):
    for index, row in dataframe.iterrows():
        with st.container():
            st.markdown("---")
            c1, c2 = st.columns([1.5, 1])
            
            bairro = row['Bairro'] if 'Bairro' in row else "Região não informada"
            lider_original = row['Líderes']
            
            if MODO_TESTE:
                tel_lider = ZAP_TESTE 
            else:
                tel_lider = extrair_zap(row['Telefone'])
            
            with c1:
                st.markdown(f"### 💙 {row['Nome do Life']}")
                if is_online:
                    st.write("📍 **Life Online** (Sem fronteiras 🌎)")
                else:
                    st.write(f"📍 **{bairro}** ({row['distancia']:.1f} km)")
                st.caption(f"{row['Tipo de Life']} | {row['Modo']}")
                st.write(f"📅 {row['Dia da Semana']} às {row['Horário de Início']}")
            
            with c2:
                if tel_lider:
                    # Botão 1: Webhook
                    btn_key = f"btn_auto_{index}"
                    
                    if st.button("🚀 Quero Participar", key=btn_key):
                        if not nome_user or not zap_user:
                            st.error("⚠️ Preencha Nome e WhatsApp no topo!")
                        else:
                            with st.spinner("Enviando solicitação..."):
                                dados = {
                                    "visitante_nome": nome_user,
                                    "visitante_zap": zap_user,
                                    "life_nome": row['Nome do Life'],
                                    "lider_nome": lider_original,
                                    "lider_zap": tel_lider,
                                    "modo": row['Modo']
                                }
                                ok, info = enviar_para_webhook(dados)
                                if ok:
                                    st.success("✅ Enviado! Líder avisado.")
                                    st.balloons()
                                    if MODO_TESTE:
                                        st.caption("ℹ️ Modo Teste: E-mail enviado para filipecx@gmail.com")
                                else:
                                    st.error(f"Falha: {info}")
                                    st.code(info)

                    # Botão 2: Fallback WhatsApp
                    msg_zap = f"Olá, sou {nome_user}. Tenho interesse no LifeGroup {row['Nome do Life']}."
                    link_zap = f"https://wa.me/{tel_lider}?text={urllib.parse.quote(msg_zap)}"
                    
                    st.markdown(f"""
                    <a href="{link_zap}" target="_blank" style="text-decoration:none;">
                        <div style="background-color:#eee;color:#333;padding:8px;border-radius:6px;text-align:center;font-weight:bold;font-size:12px;margin-top:5px;border:1px solid #ccc;">
                            📞 Ou chame no WhatsApp
                        </div>
                    </a>
                    """, unsafe_allow_html=True)
                else:
                    st.error("Sem contato")

# --- APP START ---
try: st.image("logo_menor.png", width=150)
except: pass

st.title("Encontre seu LifeGroup")
if MODO_TESTE: st.warning("⚠️ MODO DE TESTE: Msgs para Filipe")

if 'buscou' not in st.session_state:
    st.session_state.buscou = False
if 'resultados' not in st.session_state:
    st.session_state.resultados = pd.DataFrame()
if 'lat_user' not in st.session_state:
    st.session_state.lat_user = None

df_geral = carregar_dados()

opcoes_tipo = sorted(df_geral['Tipo de Life'].unique().tolist()) if not df_geral.empty else []
opcoes_dia = sorted(df_geral['Dia da Semana'].unique().tolist()) if not df_geral.empty else []
opcoes_modo = sorted(df_geral['Modo'].unique().tolist()) if not df_geral.empty else []

with st.form("form_busca"):
    st.markdown("### 1. Seus Dados")
    c1, c2 = st.columns(2)
    with c1: nome = st.text_input("Nome", key="input_nome")
    with c2: whatsapp = st.text_input("WhatsApp (com DDD)", key="input_zap")
    
    endereco_usuario = st.text_input("Endereço ou Bairro", placeholder="Ex: Rua Henrique Felipe da Costa")
    
    st.markdown("---")
    st.markdown("### 2. Preferências")
    f1, f2, f3 = st.columns(3)
    with f1: filtro_tipo = st.multiselect("Público", options=opcoes_tipo, default=opcoes_tipo)
    with f2: filtro_dia = st.multiselect("Dias", options=opcoes_dia, default=opcoes_dia)
    with f3: filtro_modo = st.multiselect("Modo", options=opcoes_modo, default=opcoes_modo)
    
    btn_buscar = st.form_submit_button("🔍 BUSCAR")

if btn_buscar:
    st.session_state.buscou = True
    
    if not nome or not whatsapp or not endereco_usuario:
        st.warning("⚠️ Preencha todos os campos.")
        st.session_state.buscou = False
    elif df_geral.empty:
        st.error("Base vazia.")
    else:
        df_filtrado = df_geral[
            (df_geral['Tipo de Life'].isin(filtro_tipo)) &
            (df_geral['Dia da Semana'].isin(filtro_dia)) &
            (df_geral['Modo'].isin(filtro_modo))
        ]
        
        lat, lon, end_bonito = obter_lat_lon_usuario(endereco_usuario)
        
        if lat:
            st.session_state.lat_user = lat
            st.session_state.lon_user = lon
            st.session_state.end_bonito = end_bonito
            
            if not df_filtrado.empty:
                df_online = df_filtrado[df_filtrado['Modo'].astype(str).str.contains("Online", case=False)]
                df_presencial = df_filtrado[~df_filtrado['Modo'].astype(str).str.contains("Online", case=False)]
                
                if not df_presencial.empty:
                    user_loc = (lat, lon)
                    df_presencial['distancia'] = df_presencial.apply(lambda r: geodesic(user_loc, (r['lat'], r['lon'])).km, axis=1)
                    df_presencial = df_presencial.sort_values(by='distancia')
                
                st.session_state.df_presencial = df_presencial
                st.session_state.df_online = df_online
            else:
                st.session_state.df_presencial = pd.DataFrame()
                st.session_state.df_online = pd.DataFrame()
        else:
            st.error("Endereço não encontrado.")
            st.session_state.buscou = False

if st.session_state.buscou and st.session_state.lat_user:
    st.info(
        f"📍 **Referência:** {st.session_state.end_bonito}\n\n"
        "Usamos este endereço para calcular a distância. Não é aqui? Edite acima."
    )
    
    nome_atual = st.session_state.input_nome
    zap_atual = st.session_state.input_zap
    
    df_p = st.session_state.get('df_presencial', pd.DataFrame())
    df_o = st.session_state.get('df_online', pd.DataFrame())
    
    if not df_p.empty and not df_o.empty:
        # TÍTULOS DE ABAS ENCURTADOS PARA NÃO CORTAR
        t1, t2 = st.tabs(["📍 Presencial", "💻 Online"])
        with t1:
            exibir_cartoes(df_p.head(3), nome_atual, zap_atual, False)
            if len(df_p) > 3:
                with st.expander(f"➕ Ver mais {len(df_p)-3}..."):
                    exibir_cartoes(df_p.iloc[3:], nome_atual, zap_atual, False)
        with t2:
            exibir_cartoes(df_o, nome_atual, zap_atual, True)
            
    elif not df_p.empty:
        st.markdown("### 📍 Presencial Próximo")
        exibir_cartoes(df_p.head(3), nome_atual, zap_atual, False)
        if len(df_p) > 3:
            with st.expander(f"➕ Ver mais {len(df_p)-3}..."):
                exibir_cartoes(df_p.iloc[3:], nome_atual, zap_atual, False)
                
    elif not df_o.empty:
        st.markdown("### 💻 Opções Online")
        exibir_cartoes(df_o, nome_atual, zap_atual, True)
    else:
        st.warning("Nenhum resultado encontrado.")
