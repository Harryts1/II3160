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

    class Config:
        schema_extra = {
            "example": {
                "id": 1,
                "name": "John Doe",
                "email": "john@example.com",
                "health_profile": {
                    "age": 30,
                    "weight": 70,
                    "height": 175,
                    "medical_conditions": ["none"]
                }
            }
        }

class MenuItem(BaseModel):
    id: int
    name: str
    description: str
    nutrition_info: dict

    class Config:
        schema_extra = {
            "example": {
                "id": 1,
                "name": "Salad",
                "description": "Fresh garden salad",
                "nutrition_info": {
                    "calories": 150,
                    "protein": 5,
                    "carbohydrates": 10,
                    "fat": 7
                }
            }
        }

class DietPlan(BaseModel):
    id: int
    user_id: int
    menu_items: List[MenuItem]
    recommended_by_ai: bool

    class Config:
        schema_extra = {
            "example": {
                "id": 1,
                "user_id": 1,
                "menu_items": [
                    {
                        "id": 1,
                        "name": "Salad",
                        "description": "Fresh garden salad",
                        "nutrition_info": {
                            "calories": 150,
                            "protein": 5,
                            "carbohydrates": 10,
                            "fat": 7
                        }
                    }
                ],
                "recommended_by_ai": True
            }
        }

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
app = FastAPI(
    title="Health Based Dietary Catering API",
    description="API for managing dietary plans with Auth0 authentication",
    version="1.0.0"
)


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

origins = [
    "https://18222081-ii3160-fastapiproject.vercel.app",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://18222081-ii3160-fastapiproject.vercel.app/login",  # Add login endpoint
    "https://18222081-ii3160-fastapiproject.vercel.app/callback",  # Add callback endpoint
    "*"  # Temporarily allow all origins for testing
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Specify methods explicitly
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Then add session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="session",
    max_age=1800,
    same_site="none",  # Changed back to "none" for cross-origin requests
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
        "audience": AUTH0_AUDIENCE
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
    """
    Initiates the Auth0 login process with improved error handling.
    """
    try:
        redirect_uri = AUTH0_CALLBACK_URL
        # Add headers for CORS
        response = await oauth.auth0.authorize_redirect(
            request,
            redirect_uri,
            audience=AUTH0_AUDIENCE,
            prompt="login"
        )
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return response
    except Exception as e:
        print(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Authentication failed", "error": str(e)}
        )

@app.get("/callback")
async def callback(request: Request):
    """
    Handles the Auth0 callback with improved error handling and security.
    """
    try:
        token = await oauth.auth0.authorize_access_token(request)
        userinfo = await oauth.auth0.userinfo(token=token)
        
        # Store only necessary information
        request.session['token'] = token['access_token']
        request.session['user'] = {
            'sub': userinfo['sub'],
            'email': userinfo['email']
        }
        
        # Redirect to frontend
        return RedirectResponse(
            url='https://18222081-ii3160-fastapiproject.vercel.app',
            status_code=302
        )
    except Exception as e:
        print(f"Callback error: {str(e)}")
        return RedirectResponse(
            url='https://18222081-ii3160-fastapiproject.vercel.app/login',
            status_code=302
        )
        
@app.get("/logout")
async def logout(request: Request):
    try:
        request.session.clear()
        return RedirectResponse(
            url=f"https://{AUTH0_DOMAIN}/v2/logout?"
            f"client_id={AUTH0_CLIENT_ID}&"
            f"returnTo=https://18222081-ii3160-fastapiproject.vercel.app"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"message": "Logout failed", "error": str(e)}
        )

@app.post("/users", 
    response_model=User,
    tags=["users"],
    summary="Create new user",
    responses={
        200: {"description": "Success"},
        401: {"description": "Not authenticated"}
    }
)
async def create_user(user: User, current_user: dict = Depends(get_current_user)):
    """
    Create a new user.
    Requires authentication.
    """
    users.append(user)
    return user

@app.get(
    "/users/{user_id}",
    response_model=User,
    tags=["users"],
    summary="Get user by ID",
    responses={
        200: {"description": "Success"},
        401: {"description": "Not authenticated"},
        404: {"description": "User not found"}
    }
)
async def get_user(user_id: int, current_user: dict = Depends(get_current_user)):
    """
    Get user information by user ID.
    Requires authentication.
    """
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