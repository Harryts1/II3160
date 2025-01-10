# Health Based Dietary Catering

## 🌟 Deskripsi
Aplikasi web berbasis FastAPI yang menyediakan rekomendasi diet dan layanan perencanaan makanan berbasis AI. Sistem ini mengintegrasikan Groq AI untuk saran menu yang dipersonalisasi dan dilengkapi fitur pelacakan kesehatan pengguna serta kustomisasi menu.

## 🎯 Fitur
- Rekomendasi diet berbasis AI menggunakan Groq AI
- Perencanaan makanan personal
- Manajemen profil kesehatan
- Autentikasi pengguna dengan Auth0
- Kustomisasi menu
- Pelacakan perkembangan kesehatan
- Integrasi generator resep
- Bantuan chatbot AI

## 🏗️ Struktur Repository
```
II3160/
├── docs/                  # Dokumentasi dan laporan
│   └── Tugas_Besar.pdf    # Laporan tugas besar
├── src/                   # Kode sumber
│   ├── frontend/               # File HTML/CSS/JS
│   │   ├── image               # Daftar gambar yang digunakan
│   │   │   ├── AF.png
│   │   │   ├── GS.png
│   │   │   ├── HB.jpg
│   │   │   ├── MB.jpg
│   │   │   ├── QP.jpg
│   │   │   └── VBB.jpg
│   │   ├── dashboard.html      # HTML dashboard
│   │   ├── index.html          # HTML hero page
│   │   ├── main.css            # CSS yang digunakan
│   │   └── main.js             # Java Script yang digunakan
│   ├── _pycache_/           # Cache Python
│   ├── Dockerfile           # Konfigurasi Docker
│   ├── docker-compose.yml   # Konfigurasi Docker Compose
│   ├── main.py              # File utama backend
│   ├── Procfile             # File proses untuk deployment
│   ├── requirements.txt     # Dependensi python
│   └── runtime.txt          # Versi Python yang digunakan
├── railway.toml        # Konfigurasi Railway
├── venv                # Virtual environment Python
└── README.md           # Dokumentasi proyek
```

## 🌐 Link Penting
- Website: https://ii3160-production.up.railway.app/
- Dokumentasi API: https://ii3160-production.up.railway.app/docs
- Repository GitHub: https://github.com/Harryts1/II3160

## 📄 Dokumentasi
Dokumentasi lengkap termasuk laporan tugas besar dapat ditemukan di direktori `docs`.

## 💡 Panduan Integrasi API

### 1. Persiapan
1. Buat akun di aplikasi melalui: https://ii3160-production.up.railway.app/
2. Lengkapi profil kesehatan Anda untuk mendapatkan rekomendasi yang lebih akurat

### 2. Cara Menggunakan API

#### Autentikasi
Sistem menggunakan Auth0 untuk autentikasi:
```python
import requests

def redirect_to_login():
    login_url = "https://ii3160-production.up.railway.app/login"
    return login_url
```

#### Mendapatkan Menu
```python
import requests

def get_menu_items():
    response = requests.get("https://ii3160-production.up.railway.app/menu-items")
    return response.json()
```

#### Mendapatkan Rekomendasi Diet
```python
import requests

def get_recommendations(user_preferences):
    url = "https://ii3160-production.up.railway.app/recommendations"
    
    data = {
        "goals": ["weight_loss"],  # atau "muscle_gain", "maintenance"
        "activity_level": "sedentary",  # atau "light", "moderate", "active"
        "restrictions": ["vegetarian"],  # atau "gluten_free", "dairy_free"
        "health_conditions": "diabetes"  # sesuai kondisi kesehatan
    }
    
    response = requests.post(url, json=data)
    return response.json()
```

#### Membuat Diet Plan
```python
import requests

def create_diet_plan(user_id, plan_details):
    url = "https://ii3160-production.up.railway.app/diet-plans"
    
    data = {
        "user_id": user_id,
        "start_date": "2024-01-10T00:00:00",
        "end_date": "2024-02-10T00:00:00",
        "calories_target": 2000,
        "protein_target": 150,
        "carbs_target": 200,
        "fat_target": 70,
        "special_instructions": "Hindari makanan pedas"
    }
    
    response = requests.post(url, json=data)
    return response.json()
```

### 3. API Terintegrasi

#### Recipe Generator API (Steven Adrian Corne – 18222101)

#### Chatbot API (Jonathan Wiguna – 18222019)


## 🚀 Endpoints API

### Endpoint Autentikasi

#### Login
```http
GET /login
```
Mengarahkan pengguna ke halaman login Auth0.

#### Callback
```http
GET /callback
```
Menangani callback autentikasi Auth0 dan menyiapkan sesi pengguna.

#### Logout
```http
GET /logout
```
Menghapus sesi pengguna dan mengarahkan ke halaman logout Auth0.

### Manajemen Profil

#### Update Profil
```http
POST /update-profile
```
Memperbarui informasi profil kesehatan pengguna.

Data Form yang Dikirim:
```json
{
  "phone": "string",
  "age": "integer",
  "weight": "float",
  "height": "float",
  "medical_conditions": "kondisi,medis,dipisah,koma",
  "allergies": "alergi,dipisah,koma",
  "dietary_preferences": "preferensi,diet,dipisah,koma"
}
```

Respons:
```json
{
  "status": "success",
  "message": "Profil berhasil diperbarui",
  "modified_count": 1,
  "upserted_id": "string (opsional)"
}
```

### Manajemen Menu

#### Mendapatkan Daftar Menu
```http
GET /menu-items
```
Mengambil semua item menu yang tersedia.

Respons:
```json
[
  {
    "name": "string",
    "description": "string",
    "nutrition_info": {
      "calories": "integer",
      "protein": "float",
      "carbs": "float",
      "fat": "float"
    },
    "price": "float",
    "category": "string"
  }
]
```

#### Membuat Menu Baru
```http
POST /menu-items
```
Membuat item menu baru (khusus admin).

Body Request:
```json
{
  "name": "string",
  "description": "string",
  "nutrition_info": {
    "calories": "integer",
    "protein": "float",
    "carbs": "float",
    "fat": "float"
  },
  "price": "float",
  "category": "string"
}
```

### Rencana Diet

#### Membuat Rencana Diet
```http
POST /diet-plans
```
Membuat rencana diet baru untuk pengguna.

Body Request:
```json
{
  "user_id": "string",
  "start_date": "datetime",
  "end_date": "datetime",
  "meal_plan": [
    {
      "day": "integer",
      "meals": [
        {
          "type": "string",
          "menu_item_id": "string",
          "portions": "integer"
        }
      ]
    }
  ],
  "calories_target": "integer",
  "protein_target": "integer",
  "carbs_target": "integer",
  "fat_target": "integer",
  "special_instructions": "string"
}
```

#### Mendapatkan Rencana Diet Pengguna
```http
GET /diet-plans/{user_id}
```
Mengambil semua rencana diet untuk pengguna tertentu.

### Rekomendasi AI

#### Mendapatkan Rekomendasi
```http
POST /recommendations
```
Menghasilkan rekomendasi diet personal menggunakan Groq AI.

Body Request:
```json
{
  "goals": ["string"],
  "activity_level": "string",
  "restrictions": ["string"],
  "health_conditions": "string"
}
```

Respons:
```json
{
  "nutritionGoals": {
    "Calories": "string",
    "Protein": "string",
    "Carbs": "string",
    "Fat": "string"
  },
  "menuItems": [
    {
      "name": "string",
      "calories": "string",
      "description": "string"
    }
  ],
  "healthAdvice": "string",
  "generated_at": "datetime"
}
```


## 🔧 Instalasi Lokal

1. Clone repository
```bash
git clone https://github.com/Harryts1/II3160.git
```

2. Install dependensi
```bash
pip install -r requirements.txt
```

3. Siapkan variabel environment dalam file `.env`:
```
MONGO_URL=url_mongodb_anda
AUTH0_CLIENT_ID=client_id_auth0_anda
AUTH0_CLIENT_SECRET=client_secret_auth0_anda
AUTH0_DOMAIN=domain_auth0_anda
AUTH0_CALLBACK_URL=url_callback_anda
AUTH0_AUDIENCE=audience_anda
SECRET_KEY=secret_key_anda
GROQ_API_KEY=api_key_groq_anda
```

4. Jalankan aplikasi
```bash
uvicorn main:app --reload
```

## 👥 Kontributor
- Harry Truman Suhalim (18222081)

## 📞 Kontak
Jika Anda memiliki pertanyaan atau mengalami kesulitan dalam integrasi API, silakan hubungi:
- WhatsApp: +62 812-7572-0872
- Email: harrytrumanshalim@gmail.com