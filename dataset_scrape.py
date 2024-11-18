import streamlit as st
import pandas as pd
import requests
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# Streamlit başlığı
st.title('SofaScore Maç Verileri Çekme Uygulaması')

# Maç ID girişi
game_ids_input = st.text_area('Maç ID\'lerini girin (virgülle ayrılmış):', '12528186,12528217,12528239')

# Maç ID'lerini virgül ile ayırarak listeye çevirme
game_ids = [game_id.strip() for game_id in game_ids_input.split(',')]

if st.button('Verileri Çek'):
    # WebDriver kurulumu (Chrome)
    driver = webdriver.Chrome()

    # Boş bir DataFrame oluşturuluyor
    all_normalized_data = pd.DataFrame()

    for game_id in game_ids:
        # URL ve veri çekme
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

        # JSON verisini okuma
        try:
            all_shot_maps_data = pd.read_json(data)
            all_shot_maps_data["game_id"] = game_id
        except ValueError:
            st.error(f"{game_id} için JSON verisi hatalı.")
            continue

        # groups sütununu düzleştirme
        def normalize_groups(df):
            normalized_rows = []
            
            for _, row in df.iterrows():
                game_id = row['game_id']
                stats = row['statistics']
                groups = stats.get('groups', [])
                
                # period bilgisi burada yer alabilir, kontrol ediyoruz
                period = stats.get('period', 'UNKNOWN')
                
                for group in groups:
                    group_name = group.get('groupName', 'UNKNOWN')
                    statistics = group.get('statisticsItems', [])
                    
                    for stat in statistics:
                        stat.update({'game_id': game_id, 'period': period, 'groupName': group_name})
                        normalized_rows.append(stat)
                        
            return pd.DataFrame(normalized_rows)

        # groups sütununu normalize etme
        normalized_data = normalize_groups(all_shot_maps_data)

        # API isteği ile takımların isimlerini alma
        url = f'https://www.sofascore.com/api/v1/event/{game_id}'
        response = requests.get(url)
        data = response.json()

        home_team = data['event']['homeTeam']['name']
        away_team = data['event']['awayTeam']['name']

        # home ve away sütunlarını takım isimleri ile güncelleme
        normalized_data.loc[normalized_data["name"] == "Expected goals", "home"] = home_team
        normalized_data.loc[normalized_data["name"] == "Expected goals", "away"] = away_team

        # Silmek istediğiniz sütunların listesi
        columns_to_drop = ['compareCode', 'statisticsType', 'valueType','renderType','key','groupName','homeTotal','awayTotal']

        # Bu sütunları normalized_data veri setinden silme
        normalized_data = normalized_data.drop(columns=columns_to_drop)

        # "ALL" periyotlarını seçme
        if 'period' in normalized_data.columns:
            normalized_data = normalized_data[normalized_data["period"] == "ALL"]

        # Güncellenmiş veri setini all_normalized_data'ya ekleme
        all_normalized_data = pd.concat([all_normalized_data, normalized_data], ignore_index=True)

    # WebDriver'ı kapatma
    driver.quit()

    # Son olarak, sadece "Expected goals" verilerini filtreleme
    final_df = all_normalized_data[all_normalized_data["name"].isin(["Expected goals", "Corner kicks"])]

    # Sonuçları yazdırma
    st.write(final_df)
