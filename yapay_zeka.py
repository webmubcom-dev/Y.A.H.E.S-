import os
import json
import math
import random
import urllib.request
import urllib.parse
import webbrowser
import threading
import time
from datetime import datetime, timedelta
import numpy as np
from bs4 import BeautifulSoup
import tkinter as tk
from tkinter import messagebox
import sys

# --- SİSTEM MONİTÖRÜ ---
SISTEM_MONITOR_AKTIF = True
try:
    import psutil
except Exception:
    SISTEM_MONITOR_AKTIF = False
    print("[Uyarı]: psutil kütüphanesi bulunamadı.")

# --- KLAVYE KONTROLÜ ---
SES_KONTROL_AKTIF = True
try:
    import keyboard
except Exception:
    SES_KONTROL_AKTIF = False
    print("[Uyarı]: keyboard kütüphanesi bulunamadı.")

# --- SES TANIMA ---
SES_TANIMA_AKTIF = True
try:
    import speech_recognition as sr
except Exception:
    SES_TANIMA_AKTIF = False
    print("[Uyarı]: speech_recognition kütüphanesi bulunamadı.")

ASISTAN_SES_DURUMU = True
UYANDIRMA_KELIMELERI = ["hey yahes", "yahes", "hey yaves"]
WAKE_WORD_AKTIF = True

# --- DOSYALAR ---
RUTIN_DOSYASI = "mark_v_rutinler.json"
ALARM_DOSYASI = "mark_v_alarmlar.json"
HAFIZA_DOSYASI = "mark_v_hafiza.json"
GECMIS_DOSYASI = "mark_v_gecmis.txt"

# ============================================================
# --- RUTİN PENCERE AYARLARI ---
# ============================================================
RUTIN_PENCERE_TAM_EKRAN = True
RUTIN_PENCERE_OTOMATIK_KAPAT = False

VARSAYILAN_RUTINLER = {
    "sabah": {
        "aciklama": "Sabah rutini",
        "adimlar": ["hava_otomatik", "saat", "gunaydin"],
        "otomatik_saat": "07:00",
        "aktif": True
    }
}

MOTIVASYON_MESAJLARI = [
    "Bugün harika şeyler başaracaksınız efendim, kendinize güvenin!",
    "Her büyük yolculuk bir adımla başlar. Hadi başlayalım!",
    "Başarı, her gün tekrarlanan küçük çabaların toplamıdır.",
    "Hedefinize odaklanın, sınırları zorlayın!",
    "Bugün yapabileceğiniz en iyi şeyi yapın, gerisi gelecek."
]

# ============================================================
# --- SESLİ YANIT MOTORU (JARVIS TARZI - Edge-TTS Neural) ---
# ============================================================
SES_AKTIF = True
EDGE_TTS_AKTIF = True
try:
    import edge_tts
    import asyncio
    import pygame
    pygame.mixer.init()
except Exception as e:
    EDGE_TTS_AKTIF = False
    print(f"[Ses Uyarısı]: edge-tts yüklenemedi, pyttsx3 kullanılacak: {e}")

# Seçilen Kadın Ses Tonu (FRIDAY tarzı)
JARVIS_SES = "tr-TR-EmelNeural"

# JARVIS ses karakteri
JARVIS_RATE = "-5%"      # Yavaş, ciddi
JARVIS_PITCH = "-2Hz"    # Hafif düşük ton
JARVIS_VOLUME = "+0%"

# Yedek pyttsx3
PYTTSX3_AKTIF = True
try:
    import pyttsx3
except Exception:
    PYTTSX3_AKTIF = False

def _jarvis_bip():
    """JARVIS tarzı kısa 'bip' sesi."""
    try:
        sure = 0.08
        frekans = 880
        ornekleme = 22050
        t = np.linspace(0, sure, int(ornekleme * sure), False)
        dalga = np.sin(frekans * t * 2 * np.pi) * 0.25
        # Fade out
        fade_len = int(len(dalga) * 0.4)
        dalga[-fade_len:] *= np.linspace(1, 0, fade_len)
        ses = (dalga * 32767).astype(np.int16)
        # Stereo
        ses = np.column_stack((ses, ses))
        pygame.sndarray.make_sound(ses).play()
        time.sleep(0.1)
    except Exception:
        pass

def _edge_tts_konus(metin):
    """Edge-TTS ile Y.A.H.E.S sesini üret ve çal."""
    try:
        gecici_dosya = f"yashes_ses_{int(time.time() * 1000)}.mp3"

        async def _uret():
            communicate = edge_tts.Communicate(
                metin,
                JARVIS_SES,
                rate=JARVIS_RATE,
                pitch=JARVIS_PITCH,
                volume=JARVIS_VOLUME
            )
            await communicate.save(gecici_dosya)

        # Yeni event loop (thread güvenli)
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_uret())
            loop.close()
        except Exception:
            asyncio.run(_uret())

        # Çal
        pygame.mixer.music.load(gecici_dosya)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.05)
        pygame.mixer.music.unload()

        # Temizle
        try:
            os.remove(gecici_dosya)
        except Exception:
            pass
        return True
    except Exception as e:
        print(f"[Edge-TTS Hatası]: {e}")
        return False

def _pyttsx3_konus(metin):
    """Yedek ses motoru."""
    if not PYTTSX3_AKTIF:
        return False
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 165)
        engine.setProperty('volume', 1.0)
        voices = engine.getProperty('voices')
        for voice in voices:
            voice_info = (voice.name + voice.id).lower()
            if "turkish" in voice_info or "tolga" in voice_info or "tr" in voice_info:
                engine.setProperty('voice', voice.id)
                break
        engine.say(metin)
        engine.runAndWait()
        return True
    except Exception:
        return False

def konustur(metin):
    """JARVIS tarzı sesli yanıt."""
    if not ASISTAN_SES_DURUMU:
        print(f"\n> [Ses Kapalı]: {metin}\n")
        return

    # Metni temizle
    temiz_metin = (str(metin)
                   .replace("http://", "").replace("https://", "")
                   .replace("www.", "").replace("|", ",")
                   .replace("->", "sonuç")
                   .replace("<b>", "").replace("</b>", "")
                   .replace("<br>", " ")
                   .replace("⚠️", "").replace("✓", "")
                   .replace("⏰", "").replace("🔊", "")
                   .replace("🔇", "").replace("📌", "")
                   .replace("🟢", "").replace("⚪", ""))

    print(f"\n> {temiz_metin}")

    if not SES_AKTIF:
        return

    # JARVIS bip sesi
    if EDGE_TTS_AKTIF:
        try:
            _jarvis_bip()
        except Exception:
            pass

    # Önce Edge-TTS (EmelNeural sesi)
    if EDGE_TTS_AKTIF:
        if _edge_tts_konus(temiz_metin):
            return

    # Yedek: pyttsx3
    _pyttsx3_konus(temiz_metin)

# --- MASAÜSTÜ BİLDİRİM ---
def bildirim_goster(baslik, mesaj):
    def arayuz():
        p = tk.Tk()
        p.overrideredirect(True)
        p.configure(bg="#0b0f19")
        p.attributes("-topmost", True)
        sw = p.winfo_screenwidth()
        sh = p.winfo_screenheight()
        p.geometry(f"320x95+{sw - 340}+{sh - 145}")
        tk.Label(p, text=baslik, font=("Helvetica", 11, "bold"), fg="#00ffff", bg="#0b0f19").pack(anchor="w", padx=10, pady=(10, 2))
        tk.Label(p, text=mesaj, font=("Helvetica", 9), fg="#ffffff", bg="#0b0f19", wraplength=300).pack(anchor="w", padx=10)
        p.after(2500, p.destroy)
        p.mainloop()
    threading.Thread(target=arayuz, daemon=True).start()

# --- TAB TUŞU SES KONTROLÜ ---
def tab_ses_kontrol_dinleyicisi():
    global ASISTAN_SES_DURUMU
    if not SES_KONTROL_AKTIF:
        return
    def tab_basildi(e):
        global ASISTAN_SES_DURUMU
        ASISTAN_SES_DURUMU = not ASISTAN_SES_DURUMU
        if ASISTAN_SES_DURUMU:
            bildirim_goster("🔊 Ses Açıldı", "Asistan sesli yanıtlar aktif.")
            print("\n[Bilgi]: Ses AÇILDI.")
        else:
            bildirim_goster("🔇 Ses Kapatıldı", "Asistan ses özellikleri gizlendi.")
            print("\n[Bilgi]: Ses KAPATILDI.")
    keyboard.on_press_key("tab", tab_basildi)

if SES_KONTROL_AKTIF:
    threading.Thread(target=tab_ses_kontrol_dinleyicisi, daemon=True).start()

# --- 3D ANİMASYON ---
class Yahes3DAnimasyon:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.configure(bg="#010205")
        self.genislik = self.root.winfo_screenwidth()
        self.yukseklik = self.root.winfo_screenheight()
        self.root.geometry(f"{self.genislik}x{self.yukseklik}+0+0")
        self.canvas = tk.Canvas(self.root, width=self.genislik, height=self.yukseklik, bg="#010205", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.aci = 0.0
        self.z_mesafe = 350.0
        self.sayac = 0
        self.animasyon_dongusu()
        self.root.mainloop()

    def projeksiyon(self, x, y, z):
        focal_length = 500.0
        faktor = focal_length / (max(1.0, z + self.z_mesafe))
        return self.genislik / 2 + x * faktor, self.yukseklik / 2 + y * faktor, faktor

    def animasyon_dongusu(self):
        self.canvas.delete("all")
        self.sayac += 1
        self.aci += 0.03
        salinim_x = math.sin(self.aci) * 20
        salinim_y = math.cos(self.aci * 0.7) * 10
        for derinlik_z in range(50, 0, -4):
            renk_tonu = int(40 + (50 - derinlik_z) * 3.5)
            renk = f"#00{hex(min(255, max(50, renk_tonu)))[2:].zfill(2)}ff"
            x2d, y2d, faktor = self.projeksiyon(salinim_x, salinim_y, derinlik_z)
            font_boyutu = int(85 * faktor)
            if font_boyutu > 5:
                self.canvas.create_text(x2d, y2d, text="Y.A.H.E.S", font=("Helvetica", font_boyutu, "bold"), fill=renk)
        x2d, y2d, faktor = self.projeksiyon(salinim_x, salinim_y, 0)
        self.canvas.create_text(x2d, y2d, text="Y.A.H.E.S", font=("Helvetica", int(85 * faktor), "bold"), fill="#00ffff")
        if self.sayac > 95:
            self.root.quit()
            self.root.destroy()
            return
        self.root.after(25, self.animasyon_dongusu)

# --- MİKROFONDAN KOMUT ALMA ---
def sesli_komut_al(sessiz=False):
    if not SES_TANIMA_AKTIF:
        return ""
    r = sr.Recognizer()
    with sr.Microphone() as source:
        if not sessiz:
            print("\n[Dinleniyor...]")
        r.adjust_for_ambient_noise(source, duration=0.4)
        try:
            audio = r.listen(source, timeout=5, phrase_time_limit=7)
            komut = r.recognize_google(audio, language="tr-TR")
            if not sessiz:
                print(f"Algılanan: {komut}")
            return komut.lower().strip()
        except Exception:
            return ""

# --- UYANDIRMA KELİMESİ ---
wake_word_event = threading.Event()
wake_word_durdur = threading.Event()

def wake_word_dinleyici():
    if not SES_TANIMA_AKTIF or not WAKE_WORD_AKTIF:
        return
    r = sr.Recognizer()
    r.energy_threshold = 300
    r.dynamic_energy_threshold = True
    print("\n[Wake Word]: 'Hey Yahes' diyerek beni uyandırabilirsiniz.")
    while not wake_word_durdur.is_set():
        try:
            with sr.Microphone() as source:
                r.adjust_for_ambient_noise(source, duration=0.3)
                try:
                    audio = r.listen(source, timeout=3, phrase_time_limit=4)
                    metin = r.recognize_google(audio, language="tr-TR").lower().strip()
                    for kelime in UYANDIRMA_KELIMELERI:
                        if kelime in metin or "yahes" in metin:
                            print(f"\n[Wake Word]: '{metin}'")
                            threading.Thread(target=konustur, args=("Buyurun efendim.",), daemon=True).start()
                            wake_word_event.set()
                            break
                except Exception:
                    continue
        except Exception:
            time.sleep(1)

def wake_word_baslat():
    threading.Thread(target=wake_word_dinleyici, daemon=True).start()

# --- HAFIZA YARDIMCILARI ---
def hafiza_yukle():
    if os.path.exists(HAFIZA_DOSYASI):
        try:
            with open(HAFIZA_DOSYASI, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def hafiza_kaydet(data):
    with open(HAFIZA_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def gecmise_yaz(metin):
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(GECMIS_DOSYASI, "a", encoding="utf-8") as f:
        f.write(f"[{zaman}] {metin}\n")

UNVANLAR = ["efendim", "değerli dostum", "üstadım", "kıymetli kullanıcım"]
def unvan_getir(kullanici_adi):
    return f"{kullanici_adi} {random.choice(UNVANLAR)}"

RASTGELE_BILGILER = [
    "İnsan beyninin depolama kapasitesi yaklaşık 2.5 petabayt.",
    "Dünyadaki toplam karınca ağırlığı, tüm insanların toplam ağırlığına yakındır.",
    "Işık hızı saniyede yaklaşık 300.000 kilometredir.",
    "Python dili adını Monty Python'dan almıştır."
]

# --- SİSTEM MONİTÖRÜ ---
def sistem_durumu_getir():
    if not SISTEM_MONITOR_AKTIF:
        return "psutil yüklü değil."
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        rapor = f"İşlemci yüzde {cpu:.1f}. Bellek yüzde {ram.percent:.1f}. Disk yüzde {disk.percent:.1f}."
        try:
            batarya = psutil.sensors_battery()
            if batarya:
                rapor += f" Batarya yüzde {batarya.percent:.0f}."
        except Exception:
            pass
        return rapor
    except Exception as e:
        return f"Hata: {e}"

def sistem_durumu_detayli():
    if not SISTEM_MONITOR_AKTIF:
        konustur("Sistem monitörü aktif değil.")
        return
    try:
        print("\n--- DETAYLI SİSTEM RAPORU ---")
        print(f"CPU Çekirdek : {psutil.cpu_count(logical=True)}")
        print(f"CPU Kullanım : %{psutil.cpu_percent(interval=0.5)}")
        ram = psutil.virtual_memory()
        print(f"RAM Toplam   : {ram.total / (1024**3):.2f} GB")
        print(f"RAM Kullanım : {ram.used / (1024**3):.2f} GB (%{ram.percent})")
        for d in psutil.disk_partitions():
            try:
                u = psutil.disk_usage(d.mountpoint)
                print(f"Disk {d.mountpoint:8s}: %{u.percent} ({u.free / (1024**3):.1f} GB boş)")
            except Exception:
                pass
        try:
            b = psutil.sensors_battery()
            if b:
                print(f"Batarya      : %{b.percent:.0f} ({'Şarj oluyor' if b.power_plugged else 'Prizde değil'})")
        except Exception:
            pass
        print("-----------------------------\n")
    except Exception as e:
        print(f"[Sistem Hatası]: {e}")

# --- ALARM PENCERESİ ---
def alarm_penceresi_goster(mesaj, tur):
    def arayuz():
        p = tk.Tk()
        p.title(f"Y.A.H.E.S - {tur.upper()}")
        p.geometry("450x280")
        p.configure(bg="#0b0f19")
        p.attributes("-topmost", True)
        tk.Label(p, text=f"⚠️ {tur.upper()}", font=("Helvetica", 14, "bold"), fg="#00ffff", bg="#0b0f19").pack(pady=20)
        tk.Label(p, text=mesaj, font=("Helvetica", 12), fg="#ffffff", bg="#0b0f19", wraplength=400, justify="center").pack(pady=10)
        tk.Button(p, text="KAPAT", font=("Helvetica", 11, "bold"), bg="#ff4444", fg="#ffffff", command=p.destroy, width=20, height=2).pack(pady=20)
        p.mainloop()
    threading.Thread(target=arayuz, daemon=True).start()

# ============================================================
# --- RUTİN PENCERESİ (SÜRESİZ - SEN KAPATANA KADAR AÇIK) ---
# ============================================================
def rutin_penceresi_goster(rutin_adi, aciklama, adimlar, isim):
    def arayuz():
        pencere = tk.Tk()
        pencere.title(f"⏰ Y.A.H.E.S - {rutin_adi.upper()} RUTİNİ")
        pencere.configure(bg="#01050f")

        if RUTIN_PENCERE_TAM_EKRAN:
            pencere.attributes("-fullscreen", True)
        else:
            sw = pencere.winfo_screenwidth()
            sh = pencere.winfo_screenheight()
            w, h = 900, 700
            x = (sw - w) // 2
            y = (sh - h) // 2
            pencere.geometry(f"{w}x{h}+{x}+{y}")

        pencere.attributes("-topmost", True)
        pencere.lift()
        pencere.focus_force()

        canvas = tk.Canvas(pencere, bg="#01050f", highlightthickness=0)
        canvas.pack(fill="both", expand=True)

        W = pencere.winfo_screenwidth() if RUTIN_PENCERE_TAM_EKRAN else 900
        H = pencere.winfo_screenheight() if RUTIN_PENCERE_TAM_EKRAN else 700

        anim_sayac = [0]
        kapat_btn = [None]
        saat_lbl = [None]
        saat_guncelle_aktif = [True]

        def ciz_arka_plan():
            canvas.delete("bg_anim")
            t = anim_sayac[0] * 0.05
            for i in range(0, H, 6):
                genislik = 80 + math.sin(t + i * 0.02) * 60
                renk_tonu = int(30 + math.sin(t + i * 0.01) * 20)
                renk = f"#00{max(10, min(255, renk_tonu)):02x}ff"
                canvas.create_line(0, i, genislik, i, fill=renk, width=1, tags="bg_anim")
                canvas.create_line(W, i, W - genislik, i, fill=renk, width=1, tags="bg_anim")

        def ciz_icerik():
            canvas.delete("icerik")

            canvas.create_text(
                W // 2, H * 0.13,
                text=f"⏰ {rutin_adi.upper()} RUTİNİ",
                font=("Helvetica", int(H * 0.06), "bold"),
                fill="#00ffff", tags="icerik"
            )

            if aciklama:
                canvas.create_text(
                    W // 2, H * 0.23,
                    text=aciklama,
                    font=("Helvetica", int(H * 0.025)),
                    fill="#aaddff", tags="icerik"
                )

            selamlama = f"Günaydın {isim}!" if "sabah" in rutin_adi else f"Merhaba {isim}!"
            canvas.create_text(
                W // 2, H * 0.31,
                text=selamlama,
                font=("Helvetica", int(H * 0.03), "italic"),
                fill="#ffffff", tags="icerik"
            )

            simdi = datetime.now()
            canvas.create_text(
                W // 2, H * 0.38,
                text=simdi.strftime("%d.%m.%Y  %H:%M"),
                font=("Helvetica", int(H * 0.022)),
                fill="#88bbdd", tags="icerik"
            )

            canvas.create_text(
                W // 2, H * 0.45,
                text="— YAPILACAKLAR —",
                font=("Helvetica", int(H * 0.022), "bold"),
                fill="#00ffff", tags="icerik"
            )

            y_baslangic = H * 0.51
            for i, adim in enumerate(adimlar):
                gosterim = adim
                if adim == "hava_otomatik":
                    gosterim = "🌤  Hava durumunu kontrol et"
                elif adim == "saat":
                    gosterim = "🕐  Saati kontrol et"
                elif adim == "gunaydin":
                    gosterim = "☀️  Günaydın mesajı"
                elif adim == "iyigeceler":
                    gosterim = "🌙  İyi geceler mesajı"
                elif adim == "motivasyon":
                    gosterim = "💪  Motivasyon"
                elif adim == "doviz":
                    gosterim = "💱  Döviz kurlarını kontrol et"
                elif adim == "bilgi":
                    gosterim = "💡  Günün bilgisi"
                elif adim == "sistem":
                    gosterim = "💻  Sistem durumu"
                else:
                    gosterim = f"•  {adim}"

                canvas.create_text(
                    W // 2, y_baslangic + i * (H * 0.055),
                    text=gosterim,
                    font=("Helvetica", int(H * 0.028)),
                    fill="#ffffff", tags="icerik"
                )

            canvas.create_text(
                W // 2, H * 0.85,
                text="Bu pencere siz kapatana kadar açık kalacak",
                font=("Helvetica", int(H * 0.018), "italic"),
                fill="#6688aa", tags="icerik"
            )

            if kapat_btn[0]:
                kapat_btn[0].destroy()
            kapat_btn[0] = tk.Button(
                pencere,
                text="✓  RUTİNİ KAPAT",
                font=("Helvetica", int(H * 0.022), "bold"),
                bg="#00aaff", fg="#ffffff",
                activebackground="#0088cc", activeforeground="#ffffff",
                relief="flat", bd=0, cursor="hand2",
                command=pencere.destroy
            )
            kapat_btn[0].place(relx=0.5, rely=0.91, anchor="center", width=int(W * 0.3), height=int(H * 0.06))

        def saat_guncelle():
            while saat_guncelle_aktif[0]:
                try:
                    if saat_lbl[0]:
                        saat_lbl[0].config(text=datetime.now().strftime("%d.%m.%Y  %H:%M:%S"))
                except Exception:
                    break
                time.sleep(1)

        def animasyon_dongusu():
            anim_sayac[0] += 1
            ciz_arka_plan()
            if anim_sayac[0] == 1:
                ciz_icerik()
            pencere.bind("<Escape>", lambda e: pencere.destroy())
            pencere.after(50, animasyon_dongusu)

        animasyon_dongusu()
        pencere.mainloop()
        saat_guncelle_aktif[0] = False

    threading.Thread(target=arayuz, daemon=True).start()

# --- ALARM YARDIMCILARI ---
def alarmlari_yukle():
    if os.path.exists(ALARM_DOSYASI):
        try:
            with open(ALARM_DOSYASI, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def alarmlari_kaydet(alarmlar):
    with open(ALARM_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(alarmlar, f, ensure_ascii=False, indent=4)

# --- RUTİN SİSTEMİ ---
def rutinleri_yukle():
    if os.path.exists(RUTIN_DOSYASI):
        try:
            with open(RUTIN_DOSYASI, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return VARSAYILAN_RUTINLER
    with open(RUTIN_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(VARSAYILAN_RUTINLER, f, ensure_ascii=False, indent=4)
    return VARSAYILAN_RUTINLER

def rutinleri_kaydet(rutinler):
    with open(RUTIN_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(rutinler, f, ensure_ascii=False, indent=4)

def rutin_calistir(rutin_adi, isim, otomatik=False):
    rutinler = rutinleri_yukle()
    rutin_adi = rutin_adi.lower().strip()
    if rutin_adi not in rutinler:
        if not otomatik:
            konustur(f"'{rutin_adi}' adında bir rutin bulunamadı.")
        return

    rutin = rutinler[rutin_adi]
    if otomatik and not rutin.get("aktif", False):
        return

    baslik = f"{'[OTOMATİK] ' if otomatik else ''}{rutin_adi.upper()} RUTİNİ"
    print(f"\n===== {baslik} =====")

    rutin_penceresi_goster(
        rutin_adi=rutin_adi,
        aciklama=rutin.get("aciklama", ""),
        adimlar=rutin.get("adimlar", []),
        isim=isim
    )

    def sesli_anlat():
        konustur(f"{rutin_adi} rutini başlatılıyor. {rutin.get('aciklama', '')}")
        for adim in rutin.get("adimlar", []):
            try:
                if adim == "hava_otomatik":
                    konustur(hava_durumu_getir("Istanbul"))
                elif adim == "saat":
                    konustur(f"Şu an saat {datetime.now().strftime('%H:%M, %d.%m.%Y')}")
                elif adim == "gunaydin":
                    konustur(f"Günaydın {unvan_getir(isim)}! Umarım harika bir gün geçirirsiniz.")
                elif adim == "iyigeceler":
                    konustur(f"İyi geceler {unvan_getir(isim)}!")
                elif adim == "motivasyon":
                    konustur(random.choice(MOTIVASYON_MESAJLARI))
                elif adim == "doviz":
                    konustur(doviz_kuru_getir())
                elif adim == "bilgi":
                    konustur(random.choice(RASTGELE_BILGILER))
                elif adim == "sistem":
                    konustur(sistem_durumu_getir())
                else:
                    konustur(adim)
                time.sleep(0.5)
            except Exception as e:
                print(f"[Rutin Hata]: {adim} -> {e}")
        konustur(f"{rutin_adi} rutini tamamlandı.")

    threading.Thread(target=sesli_anlat, daemon=True).start()
    print(f"===== {baslik} BİTTİ =====\n")

def rutin_ekle_interaktif():
    print("\n========== YENİ RUTİN EKLE ==========")
    rutin_adi = input("Rutin adı (örn: sabah, iş, spor): ").strip().lower()
    if not rutin_adi:
        print("Rutin adı boş olamaz.")
        return

    aciklama = input("Açıklama: ").strip() or "Kullanıcı tanımlı rutin"

    print("\n--- HAZIR ADIMLAR ---")
    print("  hava_otomatik, saat, gunaydin, iyigeceler, motivasyon, doviz, bilgi, sistem")
    print("  VEYA kendi metniniz (örn: 'Toplantıya hazırlan')")

    adimlar_str = input("\nAdımlar (virgülle): ").strip()
    if not adimlar_str:
        print("En az bir adım girmelisiniz.")
        return
    adimlar = [a.strip().strip("'\"") for a in adimlar_str.split(",") if a.strip()]

    print("\n--- OTOMATİK ÇALIŞMA ---")
    otomatik_saat = input("Her gün saat kaçta çalışsın? (SS:DD) [boş = elle]: ").strip()

    aktif = False
    if otomatik_saat:
        import re
        if re.match(r'^\d{1,2}[:\.]\d{2}$', otomatik_saat):
            parcalar = otomatik_saat.replace(".", ":").split(":")
            otomatik_saat = f"{int(parcalar[0]):02d}:{int(parcalar[1]):02d}"
            aktif = True
            print(f"✓ Her gün saat {otomatik_saat}'de otomatik çalışacak.")
        else:
            print("⚠ Geçersiz saat. Otomatik devre dışı.")
            otomatik_saat = ""

    rutinler = rutinleri_yukle()
    rutinler[rutin_adi] = {
        "aciklama": aciklama,
        "adimlar": adimlar,
        "otomatik_saat": otomatik_saat,
        "aktif": aktif
    }
    rutinleri_kaydet(rutinler)
    print(f"\n✓ '{rutin_adi}' rutini kaydedildi!")

def rutin_duzenle(rutin_adi):
    rutinler = rutinleri_yukle()
    rutin_adi = rutin_adi.lower().strip()
    if rutin_adi not in rutinler:
        print(f"'{rutin_adi}' bulunamadı.")
        return
    r = rutinler[rutin_adi]
    print(f"\n===== DÜZENLE: {rutin_adi} =====")
    print(f"Açıklama: {r.get('aciklama', '')}")
    print(f"Adımlar : {', '.join(r.get('adimlar', []))}")
    print(f"Otomatik: {r.get('otomatik_saat', '') or 'Yok'}")

    yeni_aciklama = input(f"Yeni açıklama [{r.get('aciklama', '')}]: ").strip()
    if yeni_aciklama:
        r["aciklama"] = yeni_aciklama

    yeni_adimlar = input(f"Yeni adımlar [{', '.join(r.get('adimlar', []))}]: ").strip()
    if yeni_adimlar:
        r["adimlar"] = [a.strip().strip("'\"") for a in yeni_adimlar.split(",") if a.strip()]

    yeni_saat = input(f"Yeni saat (SS:DD) [boş = elle]: ").strip()
    if yeni_saat:
        import re
        if yeni_saat.lower() in ["yok", "hayir", "hayır"]:
            r["otomatik_saat"] = ""
            r["aktif"] = False
        elif re.match(r'^\d{1,2}[:\.]\d{2}$', yeni_saat):
            parcalar = yeni_saat.replace(".", ":").split(":")
            r["otomatik_saat"] = f"{int(parcalar[0]):02d}:{int(parcalar[1]):02d}"
            r["aktif"] = True

    rutinler[rutin_adi] = r
    rutinleri_kaydet(rutinler)
    print(f"\n✓ '{rutin_adi}' güncellendi!")

def rutin_sil(rutin_adi):
    rutinler = rutinleri_yukle()
    rutin_adi = rutin_adi.lower().strip()
    if rutin_adi in rutinler:
        del rutinler[rutin_adi]
        rutinleri_kaydet(rutinler)
        print(f"✓ '{rutin_adi}' silindi.")
    else:
        print(f"'{rutin_adi}' bulunamadı.")

def rutin_listele():
    rutinler = rutinleri_yukle()
    if not rutinler:
        print("Kayıtlı rutin yok.")
        return
    print("\n" + "="*60)
    print("KAYITLI RUTİNLER")
    print("="*60)
    for ad, r in rutinler.items():
        durum = f"🟢 AKTİF - Her gün {r.get('otomatik_saat')}" if r.get("aktif") else "⚪ ELLE"
        print(f"\n📌 {ad.upper()}  [{durum}]")
        print(f"   Açıklama : {r.get('aciklama', '')}")
        print(f"   Adımlar  : {', '.join(r.get('adimlar', []))}")
    print("\n" + "="*60)

# --- ARKA PLAN RUTİN KONTROLÜ ---
def arka_plan_rutin_kontrol():
    son_calistirilan = {}
    print("[Rutin Kontrol]: Arka plan aktif. Saati gelen rutinler otomatik açılacak.")
    while True:
        try:
            simdi = datetime.now()
            simdiki_saat = simdi.strftime("%H:%M")
            simdiki_gun = simdi.strftime("%Y-%m-%d")

            rutinler = rutinleri_yukle()
            isim = hafiza_yukle().get("isim", "Kullanıcı")

            for ad, r in rutinler.items():
                if not r.get("aktif", False):
                    continue
                otomatik_saat = r.get("otomatik_saat", "")
                if not otomatik_saat:
                    continue

                if otomatik_saat == simdiki_saat:
                    anahtar = f"{simdiki_gun} {simdiki_saat}"
                    if son_calistirilan.get(ad) == anahtar:
                        continue

                    print(f"\n⏰ [OTOMATİK RUTİN]: '{ad}' saati geldi ({otomatik_saat})! Tam ekran pencere açılıyor...")
                    bildirim_goster(f"⏰ Rutin: {ad}", f"Saat {otomatik_saat} - Pencere açıldı")
                    son_calistirilan[ad] = anahtar

                    threading.Thread(
                        target=rutin_calistir,
                        args=(ad, isim, True),
                        daemon=True
                    ).start()
        except Exception as e:
            print(f"[Rutin Arka Plan Hatası]: {e}")

        time.sleep(20)

# --- ARKA PLAN ALARM KONTROLÜ ---
def arka_plan_alarm_kontrol():
    while True:
        try:
            alarmlar = alarmlari_yukle()
            simdiki_zaman = datetime.now().strftime("%Y-%m-%d %H:%M")
            guncellenmis = []
            degisiklik = False
            for alarm in alarmlar:
                if alarm["zaman"] <= simdiki_zaman and not alarm.get("caldi", False):
                    turu = alarm.get("tur", "Hatırlatma")
                    mesaj = alarm.get("mesaj", "Vakit geldi!")
                    konustur(f"Dikkat {turu} vaktiniz geldi! {mesaj}")
                    alarm_penceresi_goster(mesaj, turu)
                    alarm["caldi"] = True
                    degisiklik = True
                if not alarm.get("caldi", False):
                    guncellenmis.append(alarm)
            if degisiklik:
                alarmlari_kaydet(guncellenmis)
        except Exception as e:
            print(f"[Alarm Hatası]: {e}")
        time.sleep(10)

threading.Thread(target=arka_plan_alarm_kontrol, daemon=True).start()
threading.Thread(target=arka_plan_rutin_kontrol, daemon=True).start()

def akilli_zaman_cozumle(metin):
    simdi = datetime.now()
    hedef_zaman = simdi + timedelta(hours=1)
    metin = metin.lower()
    import re
    saat_bulgu = re.search(r'(\d{1,2})[:\.](\d{2})', metin)
    if saat_bulgu:
        saat = int(saat_bulgu.group(1))
        dakika = int(saat_bulgu.group(2))
        if "yarın" in metin:
            hedef_gun = simdi + timedelta(days=1)
            hedef_zaman = hedef_gun.replace(hour=saat, minute=dakika, second=0, microsecond=0)
        else:
            hedef_zaman = simdi.replace(hour=saat, minute=dakika, second=0, microsecond=0)
            if hedef_zaman < simdi:
                hedef_zaman += timedelta(days=1)
    return hedef_zaman.strftime("%Y-%m-%d %H:%M")

def menuyu_goster():
    komutlar = """
--- MARK V Y.A.H.E.S - KOMUTLAR ---
• google, youtube, wiki, hava, doviz, saat, uyg, bilgi
• alarm, alarmlar, sistem, sistem detay
• rutin       : Rutinleri listele
• rutin <ad>  : Rutini hemen çalıştır (pencere açılır)
• rutin ekle  : Yeni rutin oluştur
• rutin düzenle <ad> : Düzenle
• rutin sil <ad>     : Sil
• +, -, *, /  : Matematik
• cikis       : Çıkış
-----------------------------------------
⏰ Rutin saati gelince TAM EKRAN pencere açılır
   ve SİZ KAPATANA KADAR AÇIK KALIR.
   (Otomatik kapanma YOKTUR)
    """
    print(komutlar)

# --- WEB SERVİSLERİ ---
def google_ara(sorgu):
    try:
        url = f"https://www.google.com/search?q={urllib.parse.quote(sorgu)}&hl=tr"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode('utf-8', errors='ignore')
            soup = BeautifulSoup(html, 'html.parser')
            results = []
            for g in soup.find_all('div', class_='g'):
                title = g.find('h3')
                snippet = g.find('div', class_='VwiC3b') or g.find('div', class_='IsZA1e')
                if title and snippet:
                    results.append(f"{title.get_text().strip()}: {snippet.get_text().strip()}")
                if len(results) >= 2: break
            return "Sonuçlar: " + " | ".join(results) if results else "Bulunamadı."
    except:
        return "Google hatası."

def hava_durumu_getir(sehir="Istanbul"):
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(sehir)}&count=1&language=tr&format=json"
        req = urllib.request.Request(geo_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            geo_data = json.loads(response.read().decode('utf-8'))
            if "results" not in geo_data or not geo_data["results"]:
                return f"{sehir} bulunamadı."
            lat = geo_data["results"][0]["latitude"]
            lon = geo_data["results"][0]["longitude"]
            sehir_adi = geo_data["results"][0]["name"]
            ulke = geo_data["results"][0].get("country", "")
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
        req_w = urllib.request.Request(weather_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_w, timeout=5) as response_w:
            w_data = json.loads(response_w.read().decode('utf-8'))
            c = w_data.get("current", {})
            hava_durumlari = {0: "Açık", 1: "Genellikle açık", 2: "Parçalı bulutlu", 3: "Çok bulutlu",
                              45: "Sisli", 51: "Çisenti", 61: "Hafif yağmurlu", 63: "Yağmurlu",
                              71: "Hafif kar", 95: "Fırtınalı"}
            return f"{sehir_adi}: {hava_durumlari.get(c.get('weather_code', 0), 'Bulutlu')}. Sıcaklık {c.get('temperature_2m')} derece, nem yüzde {c.get('relative_humidity_2m')}, rüzgar {c.get('wind_speed_10m')} km/s."
    except Exception:
        return "Hava durumu alınamadı."

def vikipedi_ara(sorgu):
    try:
        search_url = f"https://tr.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(sorgu)}&format=json"
        req = urllib.request.Request(search_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            results = data.get("query", {}).get("search", [])
            if not results: return "Bulunamadı."
            baslik = results[0]["title"]
        summary_url = f"https://tr.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(baslik)}"
        req2 = urllib.request.Request(summary_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req2, timeout=5) as r2:
            extract = json.loads(r2.read().decode('utf-8')).get("extract")
            return f"{baslik}: {extract}"
    except Exception:
        return "Vikipedi hatası."

def doviz_kuru_getir():
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            try_kuru = data['rates'].get('TRY', 0)
            eur_kuru = data['rates'].get('EUR', 1)
            eur_try = try_kuru / eur_kuru if eur_kuru else 0
            return f"1 Dolar: {try_kuru:.2f} TL, 1 Euro: {eur_try:.2f} TL."
    except:
        return "Döviz alınamadı."

def youtube_ara_ve_ac(sorgu):
    webbrowser.open(f"https://www.youtube.com/results?search_query={urllib.parse.quote(sorgu)}")
    return f"{sorgu} için YouTube açıldı."

def sistem_uygulamasi_ac(uygulama_adi):
    u = uygulama_adi.lower()
    if "hesap" in u or "calc" in u:
        os.system("calc")
        return "Hesap makinesi açılıyor."
    elif "not" in u or "notepad" in u:
        os.system("notepad")
        return "Not defteri açılıyor."
    return "Uygulama bulunamadı."

# --- ANA DÖNGÜ ---
def main():
    Yahes3DAnimasyon()

    print("==========================================")
    print("     MARK V Y.A.H.E.S - YAPAY ZEKA       ")
    print("==========================================")

    hafiza = hafiza_yukle()
    if "isim" not in hafiza:
        konustur("Size nasıl hitap etmemi istersiniz?")
        isim = input("İsminiz (Enter = sesli): ").strip()
        if not isim and SES_TANIMA_AKTIF:
            konustur("Dinliyorum...")
            isim = sesli_komut_al()
        if not isim:
            isim = "Kullanıcı"
        hafiza["isim"] = isim
        hafiza_kaydet(hafiza)
        konustur(f"Tanıştığımıza memnun oldum {isim}.")
    else:
        isim = hafiza["isim"]
        konustur(f"Tekrar hoş geldiniz {unvan_getir(isim)}!")

    menuyu_goster()
    print("\n[Rutin Sistemi]: Aktif. 'sabah' rutini her gün 07:00'de otomatik açılacak.")
    print("[Rutin Sistemi]: Pencere siz kapatana kadar açık kalır.")

    if WAKE_WORD_AKTIF and SES_TANIMA_AKTIF:
        wake_word_baslat()

    while True:
        if wake_word_event.is_set():
            wake_word_event.clear()
            print(f"\n[{isim}] Wake word algılandı...")
            islem = sesli_komut_al()
            if not islem:
                continue
        else:
            girdi = input(f"\n[{isim}] 's' (sesli) veya komut: ").strip().lower()
            if girdi == 's':
                islem = sesli_komut_al()
                if not islem:
                    continue
            else:
                islem = girdi if girdi else input(f"[{isim}] Komut: ").lower().strip()

        if not islem: continue
        gecmise_yaz(f"Komut: {islem}")

        if islem == "cikis":
            wake_word_durdur.set()
            konustur(f"Görüşmek üzere {unvan_getir(isim)}!")
            break

        elif any(k in islem for k in ["selam", "merhaba", "nasılsın", "nasıl"]):
            konustur(random.choice([
                f"Teşekkür ederim {unvan_getir(isim)}, iyiyim.",
                "Harika çalışıyorum efendim!",
                "Çok iyiyim teşekkürler."
            ]))

        elif any(k in islem for k in ["teşekkür", "sağol"]):
            konustur(f"Rica ederim {unvan_getir(isim)}.")

        elif islem in ["yardim", "menu", "komutlar"]:
            menuyu_goster()

        elif islem in ["sistem", "cpu", "ram", "işlemci"]:
            konustur(sistem_durumu_getir())
            sistem_durumu_detayli()

        elif islem in ["sistem detay", "detaylı sistem"]:
            sistem_durumu_detayli()

        elif islem in ["rutin", "rutinler"]:
            rutin_listele()

        elif islem.startswith("rutin ekle"):
            rutin_ekle_interaktif()

        elif islem.startswith("rutin düzenle"):
            ad = islem.replace("rutin düzenle", "").strip()
            if ad: rutin_duzenle(ad)

        elif islem.startswith("rutin sil"):
            ad = islem.replace("rutin sil", "").strip()
            if ad:
                onay = input(f"'{ad}' silinsin mi? (e/h): ").strip().lower()
                if onay == "e": rutin_sil(ad)

        elif islem.startswith("rutin "):
            ad = islem.replace("rutin", "").strip()
            if ad:
                rutin_calistir(ad, isim, otomatik=False)

        elif islem in ["google", "ara"]:
            konustur("Ne aratmak istersiniz?")
            sorgu = sesli_komut_al() if SES_TANIMA_AKTIF else input("Arama: ").strip()
            if not sorgu: sorgu = input("Arama: ").strip()
            if sorgu: konustur(google_ara(sorgu))

        elif islem in ["youtube", "yt"]:
            konustur("YouTube'da ne aratayım?")
            sorgu = sesli_komut_al() if SES_TANIMA_AKTIF else input("YouTube: ").strip()
            if not sorgu: sorgu = input("YouTube: ").strip()
            if sorgu: konustur(youtube_ara_ve_ac(sorgu))

        elif islem in ["wiki", "vikipedi"]:
            konustur("Vikipedi'de ne aratayım?")
            konu = sesli_komut_al() if SES_TANIMA_AKTIF else input("Konu: ").strip()
            if not konu: konu = input("Konu: ").strip()
            if konu: konustur(vikipedi_ara(konu))

        elif islem in ["saat"]:
            konustur(f"Şu an saat {datetime.now().strftime('%H:%M, %d.%m.%Y')}")

        elif islem in ["hava", "havadurumu"]:
            konustur("Hangi şehir?")
            sehir = sesli_komut_al() if SES_TANIMA_AKTIF else input("Şehir: ").strip()
            if not sehir: sehir = input("Şehir: ").strip()
            sehir = sehir if sehir else "Istanbul"
            konustur(hava_durumu_getir(sehir))

        elif islem in ["uyg", "uygulama"]:
            konustur("Hangi uygulama?")
            uyg = sesli_komut_al() if SES_TANIMA_AKTIF else input("Uygulama: ").strip()
            if not uyg: uyg = input("Uygulama: ").strip()
            konustur(sistem_uygulamasi_ac(uyg))

        elif islem in ["doviz", "kur"]:
            konustur(doviz_kuru_getir())

        elif islem == "bilgi":
            konustur(random.choice(RASTGELE_BILGILER))

        elif islem in ["alarm", "hatirlatma"]:
            konustur("Ne zaman? Örnek: yarın 07:00")
            zaman = sesli_komut_al() if SES_TANIMA_AKTIF else input("Zaman: ").strip()
            if not zaman: zaman = input("Zaman: ").strip()
            hesaplanan = akilli_zaman_cozumle(zaman)
            konustur("Mesaj ne olsun?")
            mesaj = sesli_komut_al() if SES_TANIMA_AKTIF else input("Mesaj: ").strip()
            if not mesaj: mesaj = input("Mesaj: ").strip()
            if mesaj:
                liste = alarmlari_yukle()
                liste.append({"tur": "alarm", "zaman": hesaplanan, "mesaj": mesaj, "caldi": False})
                alarmlari_kaydet(liste)
                konustur(f"{hesaplanan} için alarm kuruldu.")

        elif islem in ["alarmlar"]:
            liste = alarmlari_yukle()
            aktifler = [a for a in liste if not a.get("caldi", False)]
            if aktifler:
                konustur(f"{len(aktifler)} aktif alarm var.")
                for a in aktifler:
                    print(f"-> {a['zaman']} | {a['mesaj']}")
            else:
                konustur("Aktif alarm yok.")

        elif islem in ["+", "-", "*", "/"]:
            try:
                s1 = float(input("1. Sayı: "))
                s2 = float(input("2. Sayı: "))
                res = s1+s2 if islem=="+" else (s1-s2 if islem=="-" else (s1*s2 if islem=="*" else (s1/s2 if s2!=0 else "Hata")))
                konustur(f"Sonuç: {res}")
            except:
                konustur("Hatalı giriş.")

        else:
            konustur(f"'{islem}' anlaşılamadı. 'yardim' yazın.")

if __name__ == "__main__":
    main()