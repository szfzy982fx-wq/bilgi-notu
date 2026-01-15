import streamlit as st
import os
import sqlite3
from moviepy.editor import VideoFileClip
from openai import OpenAI

# --- AYARLAR ---
# Veritabanı ve klasör isimleri
DB_NAME = "video_notlari.db"
VIDEO_KLASORU = "temp_videos"

# Klasör yoksa oluştur
if not os.path.exists(VIDEO_KLASORU):
    os.makedirs(VIDEO_KLASORU)

# --- VERİTABANI İŞLEMLERİ ---
def veritabani_kur():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS notlar
                 (id INTEGER PRIMARY KEY, baslik TEXT, ozet TEXT, tam_metin TEXT)''')
    conn.commit()
    conn.close()

def not_kaydet(baslik, ozet, tam_metin):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO notlar (baslik, ozet, tam_metin) VALUES (?, ?, ?)", (baslik, ozet, tam_metin))
    conn.commit()
    conn.close()

def notlari_getir(arama_kelimesi=""):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    if arama_kelimesi:
        c.execute("SELECT baslik, ozet FROM notlar WHERE tam_metin LIKE ? OR baslik LIKE ?", 
                  ('%'+arama_kelimesi+'%', '%'+arama_kelimesi+'%'))
    else:
        c.execute("SELECT baslik, ozet FROM notlar ORDER BY id DESC")
    veriler = c.fetchall()
    conn.close()
    return veriler

# --- ANA PROGRAM ---
st.set_page_config(page_title="Video Notu Asistanı", page_icon="🎥")
veritabani_kur()

st.title("🎥 Video -> Eğitim Notu Dönüştürücü")

# Yan menü (Sidebar) - API Anahtarı girişi
with st.sidebar:
    st.header("Ayarlar")
    api_key = st.text_input("OpenAI API Anahtarı", type="password", placeholder="sk-...")
    st.info("Videolar işlendikten sonra otomatik silinir, sadece notlar saklanır.")

# Ana ekran sekmeleri
tab1, tab2 = st.tabs(["📤 Video Yükle", "🔍 Notlarda Ara"])

with tab1:
    uploaded_file = st.file_uploader("Bir video dosyası seçin (MP4)", type=["mp4", "mov"])
    
    if uploaded_file and st.button("Notu Çıkar ve Kaydet"):
        if not api_key:
            st.error("Lütfen önce sol menüden OpenAI API Anahtarınızı girin.")
        else:
            client = OpenAI(api_key=api_key)
            status_text = st.empty()
            progress_bar = st.progress(0)
            
            try:
                # 1. Videoyu geçici olarak kaydet
                status_text.text("Video işleniyor...")
                video_path = os.path.join(VIDEO_KLASORU, uploaded_file.name)
                with open(video_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                progress_bar.progress(20)

                # 2. Sesi ayıkla
                status_text.text("Ses ayrıştırılıyor...")
                video = VideoFileClip(video_path)
                audio_path = video_path.replace(".mp4", ".mp3")
                video.audio.write_audiofile(audio_path, logger=None)
                video.close() # Dosyayı serbest bırak
                progress_bar.progress(40)

                # 3. Sesi yazıya dök (Transcription)
                status_text.text("Yapay zeka dinliyor ve yazıyor...")
                with open(audio_path, "rb") as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1", 
                        file=audio_file
                    )
                full_text = transcript.text
                progress_bar.progress(70)

                # 4. Özeti çıkar (GPT-4)
                status_text.text("Eğitim notları hazırlanıyor...")
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "Sen uzman bir eğitim asistanısın. Verilen metni ders notu formatında özetle. Başlıklar ve maddeler kullan."},
                        {"role": "user", "content": f"Aşağıdaki metni özetle:\n\n{full_text}"}
                    ]
                )
                summary = response.choices[0].message.content
                progress_bar.progress(90)

                # 5. Kaydet ve Temizle
                not_kaydet(uploaded_file.name, summary, full_text)
                
                # Temizlik (Video ve ses dosyasını sil)
                os.remove(video_path)
                os.remove(audio_path)
                
                progress_bar.progress(100)
                status_text.success("İşlem Tamamlandı! 'Notlarda Ara' sekmesine bakabilirsin.")
                st.markdown(f"### 📝 {uploaded_file.name} Özeti")
                st.write(summary)

            except Exception as e:
                st.error(f"Bir hata oluştu: {e}")

with tab2:
    arama = st.text_input("Notlarda kelime ara...", placeholder="Örn: Python, Tarih...")
    sonuclar = notlari_getir(arama)
    
    if sonuclar:
        for baslik, ozet in sonuclar:
            with st.expander(f"📄 {baslik}"):
                st.markdown(ozet)
    else:
        st.info("Henüz kaydedilmiş bir not yok veya aramanızla eşleşen sonuç bulunamadı.")

