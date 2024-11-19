from fastapi import FastAPI, HTTPException, Depends, Request, Response
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

# Configuration
config = Config('.env')
AUTH0_CLIENT_ID = config('AUTH0_CLIENT_ID', cast=str)
AUTH0_CLIENT_SECRET = config('AUTH0_CLIENT_SECRET', cast=str)
AUTH0_DOMAIN = config('AUTH0_DOMAIN', cast=str)
AUTH0_CALLBACK_URL = config('AUTH0_CALLBACK_URL', cast=str)
AUTH0_AUDIENCE = config('AUTH0_AUDIENCE', cast=str)
SECRET_KEY = config('SECRET_KEY', cast=str)

#openai.api_key = config('OPENAI_API_KEY', cast=str)

# Models
class User(BaseModel):
    id: int
    name: str
    email: str
    health_profile: dict

class MenuItem(BaseModel):
    id: int
    name: str
    description: str
    nutrition_info: dict

class DietPlan(BaseModel):
    id: int
    user_id: int
    menu_items: List[MenuItem]
    recommended_by_ai: bool

# Sample Data
users: List[User] = [
    User(id=1, name="Alice Smith", email="alice@example.com", health_profile={"age": 30, "weight": 65, "height": 170, "medical_conditions": ["none"]}),
    User(id=2, name="Bob Johnson", email="bob@example.com", health_profile={"age": 45, "weight": 80, "height": 180, "medical_conditions": ["hypertension"]}),
]

menu_items: List[MenuItem] = [
    MenuItem(id=1, name="Salad", description="Fresh garden salad with mixed greens.", nutrition_info={"calories": 150, "protein": 5, "carbohydrates": 10, "fat": 7}),
    MenuItem(id=2, name="Grilled Chicken", description="Grilled chicken breast with herbs.", nutrition_info={"calories": 200, "protein": 30, "carbohydrates": 0, "fat": 5}),
]

diet_plans: List[DietPlan] = []

# FastAPI Setup
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Add CORS middleware if needed
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://18222081-ii3160-fastapiproject.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="session",
    max_age=1800,
    same_site="lax",
    https_only=True
)

# OAuth Setup with Auth0
oauth = OAuth()
oauth.register(
    "auth0",
    client_id=AUTH0_CLIENT_ID,
    client_secret=AUTH0_CLIENT_SECRET,
    server_metadata_url=f'https://{AUTH0_DOMAIN}/.well-known/openid-configuration',
    client_kwargs={
        "scope": "openid profile email",
        "response_type": "code",
        "token_endpoint_auth_method": "client_secret_post",
        "redirect_uri": AUTH0_CALLBACK_URL
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

# Modified dependency for getting current user
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
# Routes
@app.get("/")
async def home():
    return {
        "message": "Welcome to the Health Based Dietary Catering!",
        "endpoints": {
            "auth": {
                "login": "/login",
                "logout": "/logout",
                "callback": "/callback"
            },
            "users": "/users/{user_id}",
            "menu_items": "/menu_items/{menu_item_id}",
            "diet_plans": "/diet_plans"
        }
    }

@app.get("/login")
async def login(request: Request):
    try:
        return await oauth.auth0.authorize_redirect(
            request,
            AUTH0_CALLBACK_URL
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/callback")
async def callback(request: Request):
    try:
        token = await oauth.auth0.authorize_access_token(request)
        print("Token:", token)  # Debug log
        userinfo = await oauth.auth0.userinfo(token=token)
        print("Userinfo:", userinfo)  # Debug log
        request.session['token'] = token['access_token']
        request.session['user'] = dict(userinfo)
        return RedirectResponse(url='/')
    except Exception as e:
        print("Error:", str(e))  # Debug log
        return RedirectResponse(url='/login')
        
@app.get("/logout")
async def logout(request: Request):
    # Clear session
    request.session.clear()
    
    # Construct Auth0 logout URL
    return RedirectResponse(
        url=f"https://{AUTH0_DOMAIN}/v2/logout?"
        f"client_id={AUTH0_CLIENT_ID}&"
        f"returnTo=http://127.0.0.1:8000"
    )

@app.post("/users", response_model=User)
async def create_user(user: User, current_user: dict = Depends(get_current_user)):
    users.append(user)
    return user

@app.get("/users/{user_id}", response_model=User)
async def get_user(user_id: int, current_user: dict = Depends(get_current_user)):
    for user in users:
        if user.id == user_id:
            return user
    raise HTTPException(status_code=404, detail="User not found")

@app.post("/menu_items", response_model=MenuItem)
async def create_menu_item(menu_item: MenuItem, current_user: dict = Depends(get_current_user)):
    menu_items.append(menu_item)
    return menu_item

@app.get("/menu_items/{menu_item_id}", response_model=MenuItem)
async def get_menu_item(menu_item_id: int, current_user: dict = Depends(get_current_user)):
    for item in menu_items:
        if item.id == menu_item_id:
            return item
    raise HTTPException(status_code=404, detail="Menu item not found")

@app.post("/diet_plans", response_model=DietPlan)
async def create_diet_plan(diet_plan: DietPlan, current_user: dict = Depends(get_current_user)):
    recommendation = generate_diet_recommendation(diet_plan)
    diet_plan.recommended_by_ai = True
    diet_plans.append(diet_plan)
    return diet_plan

def generate_diet_recommendation(diet_plan: DietPlan):
    prompt = f"Berikan rekomendasi diet sehat berdasarkan menu berikut: {diet_plan.menu_items}"
    response = openai.Completion.create(
        engine="davinci",
        prompt=prompt,
        max_tokens=1024,
        n=1,
        stop=None,
        temperature=0.5,
    )
    return response.choices[0].text