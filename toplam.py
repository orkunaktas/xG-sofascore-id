import streamlit as st
import pandas as pd
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# Veri çekme fonksiyonu
def get_sofascore_data(game_ids):
    driver = webdriver.Chrome()
    all_normalized_data = pd.DataFrame()

    for game_id in game_ids:
        url = f'https://api.sofascore.com/api/v1/event/{game_id}/statistics'
        driver.get(url)
        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "pre")))
        except Exception as e:
            st.error(f"{game_id} için sayfa yüklenirken hata oluştu: {e}")
            continue

        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        data = soup.get_text()

        try:
            all_shot_maps_data = pd.read_json(data)
            all_shot_maps_data["game_id"] = game_id
        except ValueError:
            st.error(f"{game_id} için JSON verisi hatalı.")
            continue

        def normalize_groups(df):
            normalized_rows = []
            for _, row in df.iterrows():
                game_id = row['game_id']
                stats = row['statistics']
                groups = stats.get('groups', [])
                period = stats.get('period', 'UNKNOWN')
                for group in groups:
                    group_name = group.get('groupName', 'UNKNOWN')
                    statistics = group.get('statisticsItems', [])
                    for stat in statistics:
                        stat.update({'game_id': game_id, 'period': period, 'groupName': group_name})
                        normalized_rows.append(stat)
            return pd.DataFrame(normalized_rows)

        normalized_data = normalize_groups(all_shot_maps_data)

        url = f'https://www.sofascore.com/api/v1/event/{game_id}'
        response = requests.get(url)
        data = response.json()
        home_team = data['event']['homeTeam']['name']
        away_team = data['event']['awayTeam']['name']
        normalized_data.loc[normalized_data["name"] == "Expected goals", "home"] = home_team
        normalized_data.loc[normalized_data["name"] == "Expected goals", "away"] = away_team

        columns_to_drop = ['compareCode', 'statisticsType', 'valueType', 'renderType', 'key', 'groupName', 'homeTotal', 'awayTotal']
        normalized_data = normalized_data.drop(columns=columns_to_drop)
        if 'period' in normalized_data.columns:
            normalized_data = normalized_data[normalized_data["period"] == "ALL"]

        all_normalized_data = pd.concat([all_normalized_data, normalized_data], ignore_index=True)

    driver.quit()
    return all_normalized_data

# Uygulama UI
st.sidebar.title("SofaScore Maç Verileri Uygulaması")
st.sidebar.markdown("""
Uygulama Seçimi:
- **Site 1**: Belirtilen maç ID'leri için SofaScore verilerini çeker.
- **Site 2**: Çekilen verileri gösterir.
""")
app_selection = st.sidebar.radio("Uygulama Seçimi", ["Site 1", "Site 2"])

st.title("📊 SofaScore Verileri Çekme ve Görselleştirme")
st.markdown("Bu uygulama ile SofaScore'dan maç verilerini çekebilir ve takım bazlı **Expected Goals (xG)** verilerini görüntüleyebilirsiniz.")

if app_selection == "Site 1":
    st.subheader('Site 1: Maç Verisi Çekme')
    st.markdown("Maç ID'lerini aşağıdaki alana virgül ile ayrılmış şekilde girin:")
    game_ids_input = st.text_area('Maç ID\'lerini girin:', '12528186,12528217,12528239', help="Birden fazla maç ID'si girerken virgül ile ayırın.")
    game_ids = [game_id.strip() for game_id in game_ids_input.split(',')]

    if st.button('Verileri Çek'):
        st.info("Veriler çekiliyor, lütfen bekleyin...")
        all_normalized_data = get_sofascore_data(game_ids)
        st.session_state.all_normalized_data = all_normalized_data
        st.success("Veriler başarıyla çekildi!")

    team_name = st.text_input('Takım adı girin (örnek: Fenerbahçe):')
    if 'all_normalized_data' in st.session_state and team_name:
        final_df = st.session_state.all_normalized_data[st.session_state.all_normalized_data["name"] == "Expected goals"]
        home_xg = final_df[final_df["home"] == team_name]["homeValue"].mean()
        away_xg = final_df[final_df["away"] == team_name]["awayValue"].mean()
        overall_xg = (home_xg + away_xg) / 2

        st.subheader(f'⚽ {team_name} için Expected Goals (xG) Verileri')
        st.metric(label="Ev Sahibi xG Ortalaması", value=f"{home_xg:.2f}")
        st.metric(label="Deplasman xG Ortalaması", value=f"{away_xg:.2f}")
        st.metric(label="Genel Ortalama xG", value=f"{overall_xg:.2f}")

elif app_selection == "Site 2":
    st.subheader('Site 2: Verileri Görüntüleme')
    st.markdown("Belirtilen maç ID'leri için çekilen verileri aşağıda görebilirsiniz.")
    game_ids_input = st.text_area('Maç ID\'lerini girin:', '12528186,12528217,12528239', help="Birden fazla maç ID'si girerken virgül ile ayırın.")
    game_ids = [game_id.strip() for game_id in game_ids_input.split(',')]

    if st.button('Verileri Çek ve Göster'):
        all_normalized_data = get_sofascore_data(game_ids)
        final_df = all_normalized_data[(all_normalized_data["name"] == "Expected goals")]
        st.dataframe(final_df.style.format({"homeValue": "{:.2f}", "awayValue": "{:.2f}"}))
