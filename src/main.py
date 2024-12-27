from fastapi import FastAPI, HTTPException, Depends, Request, Response, Security
from pydantic import BaseModel
from typing import List, Dict, Optional
import openai
from starlette.config import Config
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.base_client.errors import MismatchingStateError
from starlette.responses import RedirectResponse
from functools import wraps
import jwt
from datetime import datetime
import httpx
from jwt.algorithms import RSAAlgorithm
import json
from fastapi.openapi.utils import get_openapi
from fastapi.security import OAuth2AuthorizationCodeBearer
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime

# MongoDB connection
config = Config('.env')
MONGO_URL = config('MONGO_URL', cast=str)
client = AsyncIOMotorClient(MONGO_URL)
db = client.dietary_catering

# Configuration
config = Config('.env')
AUTH0_CLIENT_ID = config('AUTH0_CLIENT_ID', cast=str)
AUTH0_CLIENT_SECRET = config('AUTH0_CLIENT_SECRET', cast=str)
AUTH0_DOMAIN = config('AUTH0_DOMAIN', cast=str)
AUTH0_CALLBACK_URL = config('AUTH0_CALLBACK_URL', cast=str)
AUTH0_AUDIENCE = config('AUTH0_AUDIENCE', cast=str)
SECRET_KEY = config('SECRET_KEY', cast=str)


# Models
class User(BaseModel):
    id: Optional[str] = None
    name: str
    email: str
    phone: str
    health_profile: dict = {
        "age": int,
        "weight": float,
        "height": float,
        "medical_conditions": List[str],
        "allergies": List[str],
        "dietary_preferences": List[str]
    }
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()

class Consultation(BaseModel):
    id: Optional[str] = None
    user_id: str
    consultation_date: datetime
    concerns: str
    diet_goals: List[str]
    preferred_contact_time: str
    status: str = "pending"  # pending, completed, cancelled
    notes: Optional[str] = None
    created_at: datetime = datetime.now()

class DietPlan(BaseModel):
    id: Optional[str] = None
    user_id: str
    start_date: datetime
    end_date: datetime
    meal_plan: List[dict]
    calories_target: int
    protein_target: int
    carbs_target: int
    fat_target: int
    special_instructions: Optional[str] = None
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()

class Order(BaseModel):
    id: Optional[str] = None
    user_id: str
    diet_plan_id: str
    start_date: datetime
    duration_days: int
    meals_per_day: int
    total_amount: float
    payment_status: str = "pending"
    delivery_address: dict
    special_requests: Optional[str] = None
    created_at: datetime = datetime.now()

class MenuItem(BaseModel):
    id: Optional[str] = None
    name: str
    description: str
    nutrition_info: dict = {
        "calories": int,
        "protein": float,
        "carbs": float,
        "fat": float
    }
    price: float
    category: str
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Healthy Salad",
                "description": "Fresh garden salad with grilled chicken",
                "nutrition_info": {
                    "calories": 350,
                    "protein": 25.0,
                    "carbs": 20.0,
                    "fat": 15.0
                },
                "price": 45000,
                "category": "main_course"
            }
        }

# FastAPI Setup
app = FastAPI(
    title="Health Based Dietary Catering API",
    description="API for managing dietary plans with Auth0 authentication",
    version="1.0.0",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    swagger_ui_oauth2_redirect_url="/oauth2-redirect",
    swagger_ui_init_oauth={
        "clientId": AUTH0_CLIENT_ID,
        "appName": "Health Based Dietary Catering",
        "scopes": "openid profile email"
    }
)

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
templates = Jinja2Templates(directory="frontend/templates")

async def get_current_user(request: Request):
    token = request.session.get('token')
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated"
        )
    
    try:
        payload = await verify_token(token)
        return payload
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=str(e)
        )

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Add security schemes
    openapi_schema["components"] = {
        "securitySchemes": {
            "OAuth2": {
                "type": "oauth2",
                "flows": {
                    "authorizationCode": {
                        "authorizationUrl": f"https://{AUTH0_DOMAIN}/authorize",
                        "tokenUrl": f"https://{AUTH0_DOMAIN}/oauth/token",
                        "scopes": {
                            "openid": "OpenID connect",
                            "profile": "Profile",
                            "email": "Email"
                        }
                    }
                }
            }
        }
    }
    
    # Add global security
    openapi_schema["security"] = [
        {
            "OAuth2": [
                "openid",
                "profile",
                "email"
            ]
        }
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

# Add CORS middleware if needed
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://18222081-ii3160-fastapiproject.vercel.app",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="session",
    max_age=1800,
    same_site="none",
    https_only=True
)
# OAuth Setup with Auth0
oauth = OAuth()
oauth.register(
    "auth0",
    client_id=AUTH0_CLIENT_ID,
    client_secret=AUTH0_CLIENT_SECRET,
    server_metadata_url=f'https://{AUTH0_DOMAIN}/.well-known/openid-configuration',
    authorize_url=f"https://{AUTH0_DOMAIN}/authorize",
    access_token_url=f"https://{AUTH0_DOMAIN}/oauth/token",
    api_base_url=f"https://{AUTH0_DOMAIN}",
    client_kwargs={
        "scope": "openid profile email",
        "response_type": "code",
        "audience": AUTH0_AUDIENCE,
        "timeout": 60.0 
    }
)

# Authentication utilities
async def verify_token(token: str):
    try:
        # Fetch JWKS
        async with httpx.AsyncClient() as client:
            jwks_response = await client.get(f'https://{AUTH0_DOMAIN}/.well-known/jwks.json')
            jwks = jwks_response.json()

        # Find the key that matches our token
        header = jwt.get_unverified_header(token)
        key = None
        for jwk in jwks['keys']:
            if jwk['kid'] == header['kid']:
                key = RSAAlgorithm.from_jwk(json.dumps(jwk))
                break
        
        if not key:
            raise HTTPException(status_code=401, detail="Unable to find appropriate key")

        # Verify token
        payload = jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            audience=AUTH0_AUDIENCE,
            issuer=f"https://{AUTH0_DOMAIN}/"
        )
        return payload
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

# Routes
@app.get("/", response_class=HTMLResponse)
async def serve_home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login")
async def login(request: Request):
    """
    Initiates the Auth0 login process.
    """
    try:
        return await oauth.auth0.authorize_redirect(
            request,
            AUTH0_CALLBACK_URL,
            prompt="login"
        )
    except Exception as e:
        print(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/callback")
async def callback(request: Request):
    try:
        token = await oauth.auth0.authorize_access_token(request)
        userinfo = await oauth.auth0.userinfo(token=token)
        request.session['token'] = token['access_token']
        request.session['user'] = dict(userinfo)
        
        # Cek user di database
        existing_user = await db.users.find_one({"email": userinfo.get("email")})
        
        if existing_user:
            # User lama, langsung ke dashboard
            return RedirectResponse(url='/dashboard', status_code=303)
        else:
            # User baru, buat data default
            user_data = {
                "name": userinfo.get("name", ""),
                "email": userinfo.get("email", ""),
                "phone": "",
                "health_profile": {
                    "age": 0,
                    "weight": 0.0,
                    "height": 0.0,
                    "medical_conditions": [],
                    "allergies": [],
                    "dietary_preferences": []
                },
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            await db.users.insert_one(user_data)
            # Redirect ke halaman lengkapi profil
            return RedirectResponse(url='/complete-profile', status_code=303)
    except Exception as e:
        print(f"Callback error: {str(e)}")
        return RedirectResponse(url='/login')
    
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = request.session.get('user')
    if not user:
        return RedirectResponse(url='/login')
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})
        
@app.get("/logout")
async def logout(request: Request):
    # Clear session
    request.session.clear()
    
    # Construct Auth0 logout URL
    return RedirectResponse(
        url=f"https://{AUTH0_DOMAIN}/v2/logout?"
        f"client_id={AUTH0_CLIENT_ID}&"
        f"returnTo=https://18222081-ii3160-fastapiproject.vercel.app"
    )

@app.get("/complete-profile", response_class=HTMLResponse)
async def complete_profile(request: Request):
    user = request.session.get('user')
    if not user:
        return RedirectResponse(url='/login')
        
    # Cek apakah profil sudah lengkap
    db_user = await db.users.find_one({"email": user['email']})
    if db_user and db_user['health_profile']['age'] > 0:
        return RedirectResponse(url='/dashboard')
        
    return templates.TemplateResponse("complete_profile.html", {
        "request": request, 
        "user": user
    })

@app.post("/users", response_model=User, tags=["users"])
async def create_user(user: User, current_user: dict = Depends(get_current_user)):
    """
    Create a new user.
    Requires authentication.
    """
    user_dict = user.dict()
    result = await db.users.insert_one(user_dict)
    user_dict['id'] = str(result.inserted_id)
    return user_dict

@app.get("/users", response_model=List[User], tags=["users"])
async def get_users(current_user: dict = Depends(get_current_user)):
    """
    Get all users.
    Requires authentication.
    """
    try:
        users = await db.users.find().to_list(length=None)
        for user in users:
            user['id'] = str(user['_id'])
            del user['_id']
        return users
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/menu_items", response_model=MenuItem)
async def create_menu_item(menu_item: MenuItem, current_user: dict = Depends(get_current_user)):
    """
    Create a new menu item.
    Requires authentication.
    """
    menu_dict = menu_item.dict()
    result = await db.menu_items.insert_one(menu_dict)
    menu_dict['id'] = str(result.inserted_id)
    return menu_dict

@app.get("/menu_items/{menu_item_id}", response_model=MenuItem)
async def get_menu_item(menu_item_id: str, current_user: dict = Depends(get_current_user)):
    """
    Get menu item by ID.
    Requires authentication.
    """
    item = await db.menu_items.find_one({"_id": menu_item_id})
    if item:
        item['id'] = str(item['_id'])
        del item['_id']
        return item
    raise HTTPException(status_code=404, detail="Menu item not found")

@app.post("/diet-plans", response_model=DietPlan)
async def create_diet_plan(diet_plan: DietPlan, current_user: dict = Depends(get_current_user)):
    diet_plan_dict = diet_plan.dict()
    recommendation = generate_diet_recommendation(diet_plan)
    diet_plan_dict['recommended_by_ai'] = True
    result = await db.diet_plans.insert_one(diet_plan_dict)
    diet_plan_dict['id'] = str(result.inserted_id)
    return diet_plan_dict



def generate_diet_recommendation(diet_plan: DietPlan):
    return "Diet recommendation functionality coming soon"

#def generate_diet_recommendation(diet_plan: DietPlan):
#    prompt = f"Berikan rekomendasi diet sehat berdasarkan menu berikut: {diet_plan.menu_items}"
#    response = openai.Completion.create(
#        engine="davinci",
        #prompt=prompt,
        #max_tokens=1024,
        #n=1,
        #stop=None,
        #temperature=0.5,
    #)
    #return response.choices[0].text

# User operations
# Consultation operations
@app.post("/consultations/", response_model=Consultation)
async def create_consultation(consultation: Consultation):
    consultation_dict = consultation.dict()
    result = await db.consultations.insert_one(consultation_dict)
    consultation_dict['id'] = str(result.inserted_id)
    return consultation_dict

# Diet Plan operations
@app.post("/diet-plans/", response_model=DietPlan)
async def create_diet_plan(diet_plan: DietPlan):
    diet_plan_dict = diet_plan.dict()
    result = await db.diet_plans.insert_one(diet_plan_dict)
    diet_plan_dict['id'] = str(result.inserted_id)
    return diet_plan_dict

# Order operations
@app.post("/orders/", response_model=Order)
async def create_order(order: Order):
    order_dict = order.dict()
    result = await db.orders.insert_one(order_dict)
    order_dict['id'] = str(result.inserted_id)
    return order_dict