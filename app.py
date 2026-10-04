import streamlit as st
import urllib.request
import json
import base64
from pdf2image import convert_from_bytes
import pandas as pd
import io
import math

# --- GEMINI API ANAHTARI KONTROLÜ ---
if "GEMINI_API_KEY" in st.secrets:
    API_KEY = st.secrets["GEMINI_API_KEY"]
else:
    st.error("⚠️ API Anahtarı bulunamadı! Lütfen Streamlit Secrets ayarlarına GEMINI_API_KEY ekleyin.")
    API_KEY = None

# --- VERİTABANI & SAAT ÜCRETLERİ ---
MAKINE_VERILERI = {
    "CNC Torna": {"saat_ucreti": 1200.0, "toplam_setup_dk": 45.0, "hiz_carpani": 1.0},
    "Kayar Otomat": {"saat_ucreti": 1400.0, "toplam_setup_dk": 60.0, "hiz_carpani": 0.6},
    "Dik İşleme Merkezi (Freze)": {"saat_ucreti": 1500.0, "toplam_setup_dk": 45.0, "hiz_carpani": 1.2},
    "Taşlama": {"saat_ucreti": 1300.0, "toplam_setup_dk": 30.0, "hiz_carpani": 0.8},
    "Diş Açma / Helicoil": {"saat_ucreti": 800.0, "toplam_setup_dk": 15.0, "hiz_carpani": 0.3}
}

st.set_page_config(page_title="Endüstriyel Maliyet & Rota Asistanı V4", layout="wide")
st.title("⚙️ Görsel Yapay Zeka Destekli Maliyet & Üretim Asistanı V4")

col1, col2 = st.columns(2)
with col1:
    siparis_adedi = st.number_input("Sipariş Adedi:", min_value=1, value=80, step=10)
with col2:
    malzeme_turu = st.selectbox("Malzeme Türü:", ["4140 Islah Çeliği", "AISI 1040", "Alüminyum 5083", "Paslanmaz Çelik 304", "Alüminyum 6061"])

uploaded_file = st.file_uploader("Teknik Resim Yükle (PDF)", type=["pdf"])

if uploaded_file and API_KEY:
    with st.spinner("🧠 Kıdemli Üretim Mühendisi Yapay Zeka Teknik Resmi İnceliyor..."):
        try:
            # PDF'i yüksek çözünürlüklü görsele ve base64 formatına çevir
            images = convert_from_bytes(uploaded_file.read(), dpi=300)
            if not images:
                st.error("PDF görselleştirilemedi.")
                st.stop()
                
            img_bytes = io.BytesIO()
            images[0].save(img_bytes, format='JPEG')
            base64_image = base64.b64encode(img_bytes.getvalue()).decode('utf-8')

            # Güncel ve aktif model uç noktası (gemini-2.5-flash)
            url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={API_KEY}"
            
            prompt_text = """
            Sen kıdemli bir imalat ve endüstri mühendisisin. Bu teknik resmi detaylıca incele ve şu bilgileri eksiksiz bir JSON formatında ver:
            1. geometri: Parçanın geometrisi ("Silindirik (Mil/Boru)" veya "Prizmatik (Plaka/Kütük)").
            2. dis_cap: Silindirikse dış çap (mm cinsinden sayı). Prizmatikse 0 yaz.
            3. boy: Silindirikse toplam maksimum boy (mm cinsinden sayı). Prizmatikse 0 yaz.
            4. en: Prizmatikte X ölçüsü, silindirikse 0.
            5. kalinlik: Prizmatikte Z ölçüsü, silindirikse 0.
            6. operasyonlar: Gerekli olan makinelerin listesi (Şu listeden seç: "CNC Torna", "Kayar Otomat", "Dik İşleme Merkezi (Freze)", "Taşlama", "Diş Açma / Helicoil").
            7. uretim_rotasi: Adım adım yapım aşamalarını içeren metin (Örn: 1. Şerit testerede kütük kesimi, 2. CNC Torna ile dış çap tornalama vb.).
            8. kritik_notlar: Isıl işlem, sertlik (HRC), eloksal veya özel tolerans/diş uyarıları.
            
            Sadece geçerli bir JSON döndür, başka açıklama yazma. Format:
            {
              "geometri": "...",
              "dis_cap": 0.0,
              "boy": 0.0,
              "en": 0.0,
              "kalinlik": 0.0,
              "operasyonlar": ["..."],
              "uretim_rotasi": "...",
              "kritik_notlar": "..."
            }
            """

            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt_text},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": base64_image
                            }
                        }
                    ]
                }]
            }

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )

            with urllib.request.urlopen(req) as response:
                res_json = json.loads(response.read().decode('utf-8'))
                raw_text = res_json['candidates'][0]['content']['parts'][0]['text']

            clean_text = raw_text.replace("```json", "").replace("```", "").strip()
            veri = json.loads(clean_text)

            st.success("✅ Teknik Resim Başarıyla Analiz Edildi!")

            st.markdown("### 📐 Yapay Zeka Tarafından Çıkarılan Ölçüler (Kontrol / Düzenleme)")
            c1, c2, c3 = st.columns(3)
            
            if veri["geometri"] == "Silindirik (Mil/Boru)":
                b_x = c1.number_input("Dış Çap (Ø mm):", value=float(veri["dis_cap"]))
                b_y = c2.number_input("Maksimum Boy (mm):", value=float(veri["boy"]))
                b_z = 0.0
            else:
                b_x = c1.number_input("En (X mm):", value=float(veri["en"]))
                b_y = c2.number_input("Boy (Y mm):", value=float(veri["boy"]))
                b_z = c3.number_input("Kalınlık (Z mm):", value=float(veri["kalinlik"]))

            if veri.get("kritik_notlar"):
                st.warning(f"⚠️ **Üretim ve Kalite Notları:** {veri['kritik_notlar']}")

            st.markdown("### 📋 Adım Adım İmalat Rotası (Üretim Planı)")
            st.info(veri.get("uretim_rotasi", "Rota belirtilmedi."))

            secilen_operasyonlar = st.multiselect(
                "Kullanılacak Üretim İstasyonları:", 
                options=list(MAKINE_VERILERI.keys()), 
                default=veri.get("operasyonlar", ["CNC Torna"])
            )

            if (b_x > 0 and b_y > 0) or (b_z > 0):
                if veri["geometri"] == "Silindirik (Mil/Boru)":
                    ham_cap = math.ceil((b_x + 5) / 5.0) * 5
                    ham_boy = b_y + 5
                    hacim_ham = math.pi * ((ham_cap / 2) ** 2) * ham_boy
                    hacim_bitmis = math.pi * ((b_x / 2) ** 2) * b_y
                    yogunluk = 0.00000270 if "Alüminyum" in malzeme_turu else 0.00000785
                    birim_kg = round(hacim_ham * yogunluk, 3)
                else:
                    hacim_ham = (b_x + 5) * (b_y + 5) * (b_z + 3)
                    hacim_bitmis = b_x * b_y * b_z
                    birim_kg = round(hacim_ham * 0.00000785, 3)

                kaldirilan_talas = hacim_ham - hacim_bitmis
                temiz_sure_faktoru = 35000 if "Alüminyum" in malzeme_turu else 15000
                baz_sure = kaldirilan_talas / temiz_sure_faktoru if kaldirilan_talas > 0 else 0.5

                birim_sure = 0.0
                birim_iscilik = 0.0
                islem_detaylari = []

                for i, islem in enumerate(secilen_operasyonlar):
                    mak = MAKINE_VERILERI[islem]
                    islem_yuku = 1.0 if i == 0 else 0.15 
                    
                    kesim_suresi = (baz_sure * mak["hiz_carpani"]) * islem_yuku
                    birim_setup = mak["toplam_setup_dk"] / siparis_adedi
                    
                    toplam_makine_suresi = kesim_suresi + birim_setup
                    makine_maliyeti = (toplam_makine_suresi / 60) * mak["saat_ucreti"]
                    
                    birim_sure += toplam_makine_suresi
                    birim_iscilik += makine_maliyeti
                    
                    islem_detaylari.append({
                        "Operasyon": islem,
                        "Kesim Süresi (Dk)": round(kesim_suresi, 2),
                        "Setup Süresi (Dk/Birim)": round(birim_setup, 2),
                        "Toplam Süre (Dk)": round(toplam_makine_suresi, 2),
                        "Birim İşçilik (TL)": round(makine_maliyeti, 2)
                    })

                kg_fiyat = 75.0 if "Paslanmaz" in malzeme_turu else (120.0 if "Alüminyum" in malzeme_turu else 45.0)
                birim_malzeme = birim_kg * kg_fiyat
                birim_maliyet = birim_malzeme + birim_iscilik
                toplam_maliyet = birim_maliyet * siparis_adedi

                st.markdown("---")
                tab1, tab2, tab3 = st.tabs(["📊 Genel Maliyet Özeti", "⚙️ İstasyon Süreleri", "💰 Maliyet Kırılımı"])
                
                with tab1:
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Birim Hammadde", f"{birim_kg} kg")
                    m2.metric("Birim Tahmini Süre", f"{round(birim_sure, 2)} Dakika")
                    m3.metric("Birim Çıplak Maliyet", f"{round(birim_maliyet, 2)} TL")
                    st.success(f"**{siparis_adedi} Adet Toplam Proje Maliyeti:** {round(toplam_maliyet, 2)} TL")
                
                with tab2:
                    df_operasyon = pd.DataFrame(islem_detaylari)
                    st.dataframe(df_operasyon, use_container_width=True)

                with tab3:
                    df_maliyet = pd.DataFrame({
                        "Gider Kalemi": ["Hammadde Maliyeti", "İşçilik & Operasyon"],
                        "Tutar (TL)": [round(birim_malzeme * siparis_adedi, 2), round(birim_iscilik * siparis_adedi, 2)]
                    })
                    st.bar_chart(df_maliyet.set_index("Gider Kalemi"))

        except Exception as e:
            st.error(f"Sistem Hatası: {e}")
