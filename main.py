import cv2
import os
import time
import google.generativeai as genai
from PIL import Image
from gtts import gTTS
import pygame
import speech_recognition as sr
import json
from datetime import datetime
import pygame.mixer

class LongTermMemory:
    def __init__(self, memory_file='long_term_memory.json'):
        self.memory_file = memory_file
        self.memory = self.load_memory()

    def load_memory(self):
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return {'conversations': [], 'user_preferences': {}}
        except Exception as e:
            print(f"Hafıza yüklenirken hata: {e}")
            return {'conversations': [], 'user_preferences': {}}

    def save_memory(self):
        try:
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.memory, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Hafıza kaydedilirken hata: {e}")

    def add_conversation(self, user_input, bot_response):
        conversation = {
            'timestamp': datetime.now().isoformat(),
            'user_input': user_input,
            'bot_response': bot_response
        }
        self.memory['conversations'].append(conversation)
        self.memory['conversations'] = self.memory['conversations'][-50:]
        self.save_memory()

    def get_recent_context(self, limit=5):
        return self.memory['conversations'][-limit:]

    def add_user_preference(self, key, value):
        self.memory['user_preferences'][key] = value
        self.save_memory()

    def get_user_preference(self, key, default=None):
        return self.memory['user_preferences'].get(key, default)

class GeminiInteractiveVoiceChat:
    def __init__(self):
        # Klasör ve API ayarları
        self.output_folder = "captured_images"
        self.api_key = "GEMİNİ_API_KEY"
        os.makedirs(self.output_folder, exist_ok=True)
        
        # Gemini AI konfigürasyonu
        genai.configure(api_key=self.api_key)
        self.chat_model = genai.GenerativeModel('gemini-1.5-flash')
        self.vision_model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Ses ve konuşma ayarları
        pygame.mixer.init()
        self.recognizer = sr.Recognizer()
        
        # Tetikleme ve çıkış kelimeleri
        self.trigger_words = [
            "baksana", "nasıl", "nasılım", "güzel mi", "yakışmış mı", 
            "olmuş mu", "duruyorum", "görünüyorum", "bakar mısın"
        ]
        self.exit_words = ["çıkış", "exit", "çık", "kapat"]
        
        # Uzun süreli hafıza
        self.long_term_memory = LongTermMemory()

    def speak_text(self, text):
        try:
            temp_file = f"temp_speech_{int(time.time())}.mp3"
            tts = gTTS(text=text, lang='tr')
            tts.save(temp_file)
            pygame.mixer.music.load(temp_file)
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            os.remove(temp_file)
            
        except Exception as e:
            print(f"Ses oluşturma sırasında bir hata oluştu: {str(e)}")

    def capture_and_analyze(self):
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            print("Kamera açılamadı!")
            return None
        
        time.sleep(0.5)
        
        ret, frame = cap.read()
        if ret:
            timestamp = int(time.time())
            file_name = f"image_{timestamp}.jpg"
            file_path = os.path.join(self.output_folder, file_name)
            cv2.imwrite(file_path, frame)
            
            cap.release()
            
            try:
                image = Image.open(file_path)
                prompt = "Bu fotoğrafı analiz et ve kişinin görünümü, kıyafetleri ve genel görünüşü hakkında samimi bir değerlendirme yap.Anak çok uzatma. İki çok yakın arkadaşmışsınız gibi konuş."
                response = self.vision_model.generate_content([prompt, image])
                return response.text
            except Exception as e:
                return f"Görüntü analizi sırasında bir hata oluştu: {str(e)}"
        cap.release()
        return "Görüntü alınamadı."

    def should_analyze_image(self, text):
        text = text.lower()
        return any(word in text for word in self.trigger_words)

    def listen_for_speech(self):
        with sr.Microphone() as source:
            print("Dinliyorum...")
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            try:
                audio = self.recognizer.listen(source, timeout=5)
                text = self.recognizer.recognize_google(audio, language="tr-TR")
                return text.lower()
            except sr.UnknownValueError:
                self.speak_text("Sizi anlayamadım, tekrar deneyin.")
                return ""
            except sr.RequestError:
                self.speak_text("Ses tanıma servisiyle bağlantı kurulamadı.")
                return ""

    def chat(self):
        print("Sesli sohbete hoş geldiniz! Çıkış yapmak için 'çıkış' deyin.")
        
        while True:
            user_input = self.listen_for_speech()
            
            if not user_input:
                continue
            
            print(f"Sen: {user_input}")
            
            # Çıkış kontrolü
            if any(exit_word in user_input for exit_word in self.exit_words):
                goodbye_msg = "Görüşürüz!"
                print(goodbye_msg)
                self.speak_text(goodbye_msg)
                break
            
            # Son 5 mesajın kontekstini al (sadece son 5 mesaj)
            previous_context = self.long_term_memory.get_recent_context(limit=5)
            context_text = " ".join([f"Önceki: {conv['user_input']} - Cevap: {conv['bot_response']}" 
                                    for conv in previous_context])
            
            # Görüntü analizi kontrolü

            if self.should_analyze_image(user_input):
                print("\nFotoğraf çekiliyor...")
                
                analysis = self.capture_and_analyze()
                print("\nAI: " + analysis)
                self.speak_text(analysis)
                
                # Görüntü analizini hafızaya kaydet
                self.long_term_memory.add_conversation(user_input, analysis)
            else:
                try:
                    # Kontekst ile birlikte yanıt üret (sadece son 5 prompt)
                    full_prompt = f"Son 5 mesaj konteksti:\n{context_text}\n\nSon kullanıcı mesajı: {user_input}. custom_instruction:Eğer önceki mesajlar yoksa konuşmaya devam et ve bunu dile getirmeden devam et.Yakın iki arkadaş gibi konuş benimle"
                    response = self.chat_model.generate_content(full_prompt)
                    
                    # Konuşmayı hafızaya kaydet
                    self.long_term_memory.add_conversation(user_input, response.text)
                    
                    print("\nGemini: " + response.text)
                    self.speak_text(response.text)
                    
                except Exception as e:
                    error_msg = f"Bir hata oluştu: {str(e)}"
                    print(error_msg)
                    self.speak_text("Üzgünüm, bir hata oluştu")

def main():
    chat = GeminiInteractiveVoiceChat()
    chat.chat()

if __name__ == "__main__":
    main()
