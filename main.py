from fastapi import FastAPI, HTTPException, Depends, Request, Response, Security
from pydantic import BaseModel
from typing import List, Dict, Optional
from groq import Groq
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
import logging
import asyncio
from pymongo.server_api import ServerApi
import certifi
import ssl
from fastapi.responses import FileResponse
import re
from typing import Dict, Any
import random
import os

# Configuration
config = Config('.env')
MONGO_URL = config('MONGO_URL', cast=str)
AUTH0_CLIENT_ID = config('AUTH0_CLIENT_ID', cast=str)
AUTH0_CLIENT_SECRET = config('AUTH0_CLIENT_SECRET', cast=str)
AUTH0_DOMAIN = config('AUTH0_DOMAIN', cast=str)
AUTH0_CALLBACK_URL = config('AUTH0_CALLBACK_URL', cast=str)
AUTH0_AUDIENCE = config('AUTH0_AUDIENCE', cast=str)
SECRET_KEY = config('SECRET_KEY', cast=str)
GROQ_API_KEY = config('GROQ_API_KEY', cast=str)


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

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Tambahkan di bagian awal setelah inisialisasi app
@app.on_event("startup")
async def startup_event():
    logger.info("Application is starting up...")
    
    # Add a small delay to ensure proper initialization
    await asyncio.sleep(5)
    
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info("Checking environment variables...")
    
    try:
        # Only attempt MongoDB connection if URL is configured
        if MONGO_URL:
            client = AsyncIOMotorClient(
                MONGO_URL,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=5000,
                maxPoolSize=1
            )
            await client.admin.command('ping')
            logger.info("MongoDB connection successful")
    except Exception as e:
        # Log error but don't fail startup
        logger.error(f"MongoDB connection failed: {str(e)}")
        
    logger.info("Startup complete")

@app.get("/health")
async def health_check():
    logger.debug("Health check endpoint hit")
    try:
        # Simpel check ke MongoDB
        if mongodb_client:
            await mongodb_client.admin.command('ping')
            logger.debug("MongoDB health check passed")
            return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        # Tetap return ok meskipun database error
        return {"status": "ok", "database": "error"}
    
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.debug(f"Request path: {request.url.path}")
    try:
        response = await call_next(request)
        logger.debug(f"Response status: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"Request failed: {str(e)}")
        raise

@app.get("/")
async def root():
    logger.info("Root endpoint called")
    return {"message": "API is running"}

@app.get("/minimal-health")
async def minimal_health():
    logger.info("Health check endpoint called")
    return {"status": "ok"}

# Initialize Groq
groq_client = None

def get_groq_client():
    global groq_client
    if groq_client is None:
        try:
            groq_client = Groq(api_key=GROQ_API_KEY)
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize AI service"
            )
    return groq_client

async def call_groq_api(prompt: str) -> Dict[str, Any]:
    """Make an async call to the Groq API with improved formatting."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = """You are a professional dietary catering consultant. Provide menu recommendations 
    in the following format:

    1. Nutritional Goals
    - Daily calories
    - Protein
    - Carbs
    - Fat

    2. Menu Recommendations
    Breakfast:
    - [Name of dish] (calories)
    Brief description focusing on key ingredients and benefits

    Lunch:
    - [Name of dish] (calories)
    Brief description focusing on key ingredients and benefits

    Dinner:
    - [Name of dish] (calories)
    Brief description focusing on key ingredients and benefits

    3. Health Advice
    Please provide health advice in clear bullet points:
    • Daily nutrition targets
    • Exercise recommendations
    • Hydration guidelines
    • General wellness tips

    Keep descriptions concise and focused on what the customer needs to know."""
    
    payload = {
        "model": "mixtral-8x7b-32768",
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.7,
        "max_tokens": 2048,
        "top_p": 1
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

# Global MongoDB connection
mongodb_client = None
mongodb_db = None

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
# Database connection utility function
async def get_database():
    try:
        logger.info(f"Connecting to MongoDB at: {MONGO_URL[:20]}...")
        client = AsyncIOMotorClient(
            MONGO_URL,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=5000,
            maxPoolSize=1
        )
        await client.admin.command('ping')
        db = client.dietary_catering
        
        # Ensure collections exist
        collections = await db.list_collection_names()
        required_collections = ['users', 'menu_items', 'diet_plans']
        
        for collection in required_collections:
            if collection not in collections:
                await db.create_collection(collection)
                
        # Create indexes if they don't exist
        await db.users.create_index("email", unique=True)
        await db.menu_items.create_index("name")
        await db.diet_plans.create_index("user_id")
        
        return db
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

# MongoDB Connection Function
async def init_mongodb():
    global mongodb_client, mongodb_db
    try:
        # Create MongoDB client with SSL configurations
        mongodb_client = AsyncIOMotorClient(
            MONGO_URL,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=10000,
            maxPoolSize=10,
            retryWrites=True,
            retryReads=True,
            ssl=True,
            ssl_cert_reqs='CERT_NONE',  
            tls=True,
            tlsAllowInvalidCertificates=True  
        )
        
        # Test connection with longer timeout
        await asyncio.wait_for(
            mongodb_client.admin.command('ping'),
            timeout=30.0
        )
        
        logger.info("MongoDB connection test successful")
        mongodb_db = mongodb_client.dietary_catering
        
        return mongodb_db
    except asyncio.TimeoutError:
        logger.error("MongoDB connection timeout")
        raise HTTPException(
            status_code=500,
            detail="Database connection timeout. Please try again later."
        )
    except Exception as e:
        logger.error(f"MongoDB initialization error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Database connection failed: {str(e)}"
        )

# @app.on_event("startup")
# async def startup_db_client():
#     global mongodb_client, mongodb_db
#     try:
#         # Logging awal
#         logger.info("Starting MongoDB connection initialization...")
#         logger.info(f"Connecting to MongoDB at: {MONGO_URL[:20]}...")
        
#         # Create MongoDB client with robust options
#         mongodb_client = AsyncIOMotorClient(
#             MONGO_URL,
#             serverSelectionTimeoutMS=10000,
#             connectTimeoutMS=10000,
#             socketTimeoutMS=10000,
#             maxPoolSize=10,
#             retryWrites=True,
#             retryReads=True
#         )
        
#         # Test connection
#         logger.info("Testing MongoDB connection...")
#         await mongodb_client.admin.command('ping')
        
#         # Get database
#         mongodb_db = mongodb_client.get_database('dietary_catering')
#         logger.info(f"Connected to database: {mongodb_db.name}")
        
#         # List and create collections if needed
#         collections = await mongodb_db.list_collection_names()
#         logger.info(f"Existing collections: {collections}")
        
#         required_collections = [
#             'users', 
#             'menu_items', 
#             'diet_plans', 
#         ]
        
#         # Create missing collections
#         for collection in required_collections:
#             if collection not in collections:
#                 logger.info(f"Creating collection: {collection}")
#                 await mongodb_db.create_collection(collection)
        
#         # Create indexes
#         logger.info("Creating indexes...")
#         await mongodb_db.users.create_index("email", unique=True)
#         await mongodb_db.menu_items.create_index("name")
#         await mongodb_db.diet_plans.create_index("user_id")
        
#         # Verify final state
#         final_collections = await mongodb_db.list_collection_names()
#         logger.info(f"Final collections in database: {final_collections}")
        
#         # Test write operation
#         test_result = await mongodb_db.command("ping")
#         logger.info(f"Database write test result: {test_result}")
        
#         logger.info("MongoDB initialization completed successfully!")
        
#     except Exception as e:
#         logger.error(f"Failed to initialize MongoDB: {str(e)}")
#         logger.error(f"Error type: {type(e)}")
#         logger.error("MongoDB initialization failed!")
#         raise e

@app.on_event("startup")
async def startup_event():
    logger.info("Application is starting up...")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info("Checking environment variables...")
    for key, value in os.environ.items():
        logger.info(f"{key}: {value}")

@app.on_event("shutdown")
async def shutdown_db_client():
    try:
        if mongodb_client:
            mongodb_client.close()
            logger.info("MongoDB connection closed successfully")
    except Exception as e:
        logger.error(f"Error closing MongoDB connection: {str(e)}")

@app.on_event("shutdown")
async def shutdown_db_client():
    if mongodb_client:
        mongodb_client.close()
        logger.info("MongoDB connection closed")

# Setup templates
templates = Jinja2Templates(directory="src/frontend")

# Add CORS middleware
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
        async with httpx.AsyncClient() as client:
            jwks_response = await client.get(f'https://{AUTH0_DOMAIN}/.well-known/jwks.json')
            jwks = jwks_response.json()

        header = jwt.get_unverified_header(token)
        key = None
        for jwk in jwks['keys']:
            if jwk['kid'] == header['kid']:
                key = RSAAlgorithm.from_jwk(json.dumps(jwk))
                break
        
        if not key:
            raise HTTPException(status_code=401, detail="Unable to find appropriate key")

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

async def get_current_user(request: Request):
    token = request.session.get('token')
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = await verify_token(token)
        return payload
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

# Routes


# @app.get("/")
# async def serve_home():
#     return FileResponse('src/frontend/index.html')

@app.get("/login")
async def login(request: Request):
    try:
        return await oauth.auth0.authorize_redirect(
            request,
            AUTH0_CALLBACK_URL, 
            prompt="login"
        )
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/callback")
async def callback(request: Request):
    try:
        token = await oauth.auth0.authorize_access_token(request)
        userinfo = await oauth.auth0.userinfo(token=token)
        request.session['token'] = token['access_token']
        request.session['user'] = dict(userinfo)
        return RedirectResponse(url='/dashboard', status_code=303)
    except Exception as e:
        logger.error(f"Callback error: {str(e)}")
        return RedirectResponse(url='/login')

@app.post("/update-profile")
async def update_profile(request: Request):
    try:
        # Get fresh database connection
        db = await get_database()
        logger.info("Database connection established for profile update")
        
        # Get user from session
        user = request.session.get('user')
        if not user:
            logger.error("No user in session")
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Get form data
        form = await request.form()
        
        # Validate form data
        try:
            user_data = {
                "name": user.get("name", ""),
                "email": user.get("email", ""),
                "phone": str(form.get("phone", "")),
                "health_profile": {
                    "age": int(form.get("age", 0)),
                    "weight": float(form.get("weight", 0)),
                    "height": float(form.get("height", 0)),
                    "medical_conditions": form.get("medical_conditions", "").split(",") if form.get("medical_conditions") else [],
                    "allergies": form.get("allergies", "").split(",") if form.get("allergies") else [],
                    "dietary_preferences": form.get("dietary_preferences", "").split(",") if form.get("dietary_preferences") else []
                },
                "updated_at": datetime.now()
            }
        except (ValueError, TypeError) as e:
            logger.error(f"Form data validation error: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid form data")
        
        # Update user profile
        try:
            result = await db.users.update_one(
                {"email": user.get("email")},
                {"$set": user_data},
                upsert=True
            )
            
            # Verify the update
            updated_user = await db.users.find_one({"email": user.get("email")})
            if not updated_user:
                raise HTTPException(status_code=500, detail="Failed to verify profile update")
                
            logger.info(f"Profile updated successfully for user: {user.get('email')}")
            return {
                "status": "success",
                "message": "Profile updated successfully",
                "modified_count": result.modified_count,
                "upserted_id": str(result.upserted_id) if result.upserted_id else None
            }
            
        except Exception as e:
            logger.error(f"Database update error: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to update profile in database")
            
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in update_profile: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    try:
        user = request.session.get('user')
        if not user:
            return RedirectResponse(url='/login')
            
        db = await get_database()
        user_profile = await db.users.find_one({"email": user.get("email")})
        
        # Render template dengan konteks
        return templates.TemplateResponse("dashboard.html", {
            "request": request, 
            "user": user,
            "user_profile": user_profile
        })
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        return RedirectResponse(url='/')
    
@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
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
        
    try:
        # Check if profile is complete
        if mongodb_db:
            db_user = await mongodb_db.users.find_one({"email": user.get("email")})
            if db_user and db_user.get('health_profile', {}).get('age', 0) > 0:
                return RedirectResponse(url='/dashboard')
        
        return FileResponse('src/frontend/dashboard.html')("complete_profile.html", {
            "request": request, 
            "user": user
        })
    except Exception as e:
        logger.error(f"Error in complete_profile: {str(e)}")
        return RedirectResponse(url='/dashboard')

@app.post("/users", response_model=User, tags=["users"])
async def create_user(user: User, current_user: dict = Depends(get_current_user)):
    """
    Create a new user.
    Requires authentication.
    """
    try:
        user_dict = user.dict()
        result = await mongodb_db.users.insert_one(user_dict)
        user_dict['id'] = str(result.inserted_id)
        return user_dict
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users", response_model=List[User], tags=["users"])
async def get_users(current_user: dict = Depends(get_current_user)):
    """
    Get all users.
    Requires authentication.
    """
    try:
        users = await mongodb_db.users.find().to_list(length=None)
        for user in users:
            user['id'] = str(user['_id'])
            del user['_id']
        return users
    except Exception as e:
        logger.error(f"Error fetching users: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/menu-items", response_model=List[MenuItem])
async def get_menu_items():
    """Get all menu items"""
    try:
        db = await get_database()
        menu_items = await db.menu_items.find().to_list(length=None)
        return menu_items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/menu-items", response_model=MenuItem)
async def create_menu_item(item: MenuItem, current_user: dict = Depends(get_current_user)):
    """Create new menu item (admin only)"""
    try:
        result = await mongodb_db.menu_items.insert_one(item.dict())
        return {**item.dict(), "id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/diet-plans", response_model=DietPlan)
async def create_diet_plan(plan: DietPlan, current_user: dict = Depends(get_current_user)):
    """Create a new diet plan for user"""
    try:
        plan_dict = plan.dict()
        plan_dict["user_id"] = current_user["sub"]
        result = await mongodb_db.diet_plans.insert_one(plan_dict)
        return {**plan_dict, "id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/diet-plans/{user_id}", response_model=List[DietPlan])
async def get_user_diet_plans(user_id: str):
    """Get diet plans for a specific user"""
    try:
        db = await get_database()
        plans = await db.diet_plans.find({"user_id": user_id}).to_list(length=None)
        return plans
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

@app.post("/recommendations")
async def get_recommendations(request: Request):
    try:
        user = request.session.get('user')
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        request_data = await request.json()
        db = await get_database()
        user_profile = await db.users.find_one({"email": user.get("email")})
        
        # Get AI recommendations
        prompt = construct_dietary_prompt(user_profile, request_data)
        response = await call_groq_api(prompt)
        ai_response = response['choices'][0]['message']['content']
        
        # Process recommendations dengan mengirimkan health_profile
        nutrition_goals = extract_nutrition_goals(
            ai_response,
            health_profile=user_profile.get('health_profile'),
            form_data=request_data
        )
        
        # Dapatkan total kalori dari nutrition_goals
        total_calories = int(nutrition_goals["Calories"].split()[0])  # "2000 kcal" -> 2000
        
        # Hitung distribusi kalori untuk setiap makanan
        breakfast_calories = int(total_calories * 0.3)  # 30% dari total
        lunch_calories = int(total_calories * 0.4)     # 40% dari total
        dinner_calories = int(total_calories * 0.3)    # 30% dari total
        
        # Update menu items dengan kalori yang sesuai
        menu_items = await extract_menu_items(
            db, 
            ['breakfast', 'lunch', 'dinner'],
            request_data.get('restrictions', [])
        )
        
        # Update kalori untuk setiap meal berdasarkan proporsi
        for item in menu_items:
            if "Breakfast" in item["name"]:
                item["calories"] = f"{breakfast_calories} calories"
            elif "Lunch" in item["name"]:
                item["calories"] = f"{lunch_calories} calories"
            elif "Dinner" in item["name"]:
                item["calories"] = f"{dinner_calories} calories"
        
        health_advice = extract_health_advice(ai_response)
        
        final_response = {
            "nutritionGoals": nutrition_goals,
            "menuItems": menu_items,
            "healthAdvice": health_advice,
            "generated_at": datetime.now().isoformat()
        }
        
        # Update atau insert diet plan
        await db.diet_plans.update_one(
            {"user_id": user.get('email')},
            {
                "$set": {
                    "recommendations": final_response,
                    "restrictions": request_data.get('restrictions', []),
                    "goals": request_data.get('goals', []),
                    "updated_at": datetime.now()
                }
            },
            upsert=True
        )
        
        return final_response
        
    except Exception as e:
        logger.error(f"Error in recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def construct_dietary_prompt(user_profile: dict, form_data: dict = None) -> str:
    """Construct a prompt focused on catering menu recommendations."""
    health_profile = user_profile.get('health_profile', {})
    
    prompt_parts = [
        "As a dietary catering service, please provide menu recommendations for a customer with the following profile:",
        f"Age: {health_profile.get('age', 'Not specified')}",
        f"Weight: {health_profile.get('weight', 'Not specified')} kg",
        f"Height: {health_profile.get('height', 'Not specified')} cm",
        f"Medical Conditions: {', '.join(health_profile.get('medical_conditions', ['None specified']))}",
        f"Allergies: {', '.join(health_profile.get('allergies', ['None specified']))}",
        f"Dietary Preferences: {', '.join(health_profile.get('dietary_preferences', ['None specified']))}"
    ]
    
    if form_data:
        if form_data.get('goals'):
            prompt_parts.append(f"Goals: {', '.join(form_data['goals'])}")
        if form_data.get('activity_level'):
            prompt_parts.append(f"Activity Level: {form_data['activity_level']}")
        if form_data.get('restrictions'):
            prompt_parts.append(f"Additional Restrictions: {', '.join(form_data['restrictions'])}")
        if form_data.get('health_conditions'):
            prompt_parts.append(f"Health Conditions: {form_data['health_conditions']}")
    
    prompt_parts.extend([
        "\nPlease provide:",
        "1. Daily nutritional targets (calories, protein, carbs, fat)",
        "2. Suggested menu items for each meal (breakfast, lunch, dinner) with brief descriptions",
        "3. General health recommendations",
        "\nNote: Provide menu names and brief descriptions only, no detailed recipes needed."
    ])
    
    return "\n".join(prompt_parts)

def extract_health_advice(ai_response: str) -> str:
    """Extract health advice from AI response."""
    try:
        # Find health advice section
        sections = ai_response.split('\n')
        health_advice = []
        in_advice_section = False
        
        for line in sections:
            if 'health advice' in line.lower():
                in_advice_section = True
                continue
            
            if in_advice_section and line.strip():
                if line.startswith('•') or line.startswith('-'):
                    health_advice.append(line.strip())
        
        return '\n'.join(health_advice) if health_advice else "• Maintain a balanced diet with regular meals\n• Stay hydrated\n• Exercise regularly"
        
    except Exception as e:
        logger.error(f"Error extracting health advice: {str(e)}")
        return "• Maintain a balanced diet with regular meals\n• Stay hydrated\n• Exercise regularly"
    
def process_ai_response(ai_response: str) -> dict:
    """Process and structure the AI response."""
    try:
        sections = {'menu': []}
        current_section = ''
        health_advice_points = []
        
        # Split response into lines
        lines = ai_response.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            lower_line = line.lower()
            if any(meal in lower_line for meal in ['breakfast:', 'lunch:', 'dinner:']):
                sections['menu'].append(line)
            elif any(header in lower_line for header in ['health advice', 'recommendations:']):
                current_section = 'advice'
                continue
            elif current_section == 'advice':
                if line.startswith('•') or line.startswith('-'):
                    health_advice_points.append(line.lstrip('•- ').strip())
        
        # Format health advice with bullet points
        formatted_advice = []
        for point in health_advice_points:
            if point and len(point.strip()) > 0:
                formatted_advice.append(f"• {point.strip()}")
        
        # If no health advice was found, use default advice
        if not formatted_advice:
            formatted_advice = [
                "• Maintain consistent meal timing for optimal metabolism",
                "• Stay hydrated by drinking at least 8 glasses of water daily",
                "• Consider moderate exercise 3-4 times per week",
                "• Monitor your portion sizes and eat mindfully"
            ]
        
        return {
            "nutritionGoals": extract_nutrition_goals(ai_response),
            "menuItems": extract_menu_items(sections.get('menu', [])),
            "healthAdvice": "\n".join(formatted_advice)
        }
        
    except Exception as e:
        logger.error(f"Error processing AI response: {str(e)}")
        # Return default recommendations directly instead of calling a separate function
        return {
            "nutritionGoals": {
                "Calories": "1800 kcal",
                "Protein": "70g",
                "Carbs": "220g",
                "Fat": "60g"
            },
            "menuItems": [
                {
                    "name": "Breakfast: Healthy Morning Bowl",
                    "calories": "350 calories",
                    "description": "A nutritious breakfast option with whole grains and fresh fruits"
                },
                {
                    "name": "Lunch: Fresh Garden Plate",
                    "calories": "450 calories",
                    "description": "A balanced mix of vegetables and lean protein"
                },
                {
                    "name": "Dinner: Light Evening Meal",
                    "calories": "400 calories",
                    "description": "Light and nutritious dinner option"
                }
            ],
            "healthAdvice": "• Maintain consistent meal timing\n• Stay hydrated\n• Exercise regularly"
        }

def calculate_nutrition_goals(health_profile: dict = None, form_data: dict = None) -> dict:
    """
    Calculate personalized nutrition goals based on user's health profile and goals.
    
    Parameters:
    - health_profile: dict containing age, weight (kg), height (cm), medical_conditions, etc
    - form_data: dict containing activity_level, goals, etc
    
    Returns:
    - dict with calculated daily nutritional goals
    """
    try:
        # Default values for average adult
        default_goals = {
            "Calories": "2000 kcal",
            "Protein": "75g",
            "Carbs": "250g",
            "Fat": "65g"
        }
        
        if not health_profile:
            return default_goals
            
        # Extract basic measurements
        weight = float(health_profile.get('weight', 0))
        height = float(health_profile.get('height', 0))
        age = int(health_profile.get('age', 25))
        
        # If essential measurements are missing, return default
        if not (weight and height and age):
            return default_goals
            
        # Calculate BMR using Mifflin-St Jeor Equation
        # Men: BMR = 10W + 6.25H - 5A + 5
        # Women: BMR = 10W + 6.25H - 5A - 161
        # Using male formula as default
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
        
        # Activity level multipliers
        activity_multipliers = {
            "sedentary": 1.2,  # Little or no exercise
            "light": 1.375,    # Light exercise 1-3 days/week
            "moderate": 1.55,  # Moderate exercise 3-5 days/week
            "active": 1.725,   # Heavy exercise 6-7 days/week
            "very_active": 1.9 # Very heavy exercise, physical job
        }
        
        # Get activity level from form data or default to light
        activity_level = form_data.get('activity_level', 'light').lower()
        activity_multiplier = activity_multipliers.get(activity_level, 1.375)
        
        # Calculate TDEE (Total Daily Energy Expenditure)
        tdee = bmr * activity_multiplier
        
        # Adjust calories based on goals
        goals = form_data.get('goals', [])
        calorie_adjustment = 0
        
        if 'weight_loss' in goals:
            calorie_adjustment = -500  # Create deficit for weight loss
        elif 'weight_gain' in goals:
            calorie_adjustment = 500   # Create surplus for weight gain
            
        total_calories = int(tdee + calorie_adjustment)
        
        # Calculate macronutrients
        # Protein: 1.6-2.2g per kg body weight for active individuals
        protein_per_kg = 2.0 if 'muscle_gain' in goals else 1.6
        protein_grams = int(weight * protein_per_kg)
        
        # Fat: 20-35% of total calories
        fat_calories = total_calories * 0.25  # 25% of calories from fat
        fat_grams = int(fat_calories / 9)  # 9 calories per gram of fat
        
        # Remaining calories from carbs
        protein_calories = protein_grams * 4  # 4 calories per gram of protein
        carb_calories = total_calories - protein_calories - fat_calories
        carb_grams = int(carb_calories / 4)  # 4 calories per gram of carbs
        
        return {
            "Calories": f"{total_calories} kcal",
            "Protein": f"{protein_grams}g",
            "Carbs": f"{carb_grams}g",
            "Fat": f"{fat_grams}g"
        }
        
    except Exception as e:
        # Return default goals if any calculation errors occur
        return default_goals

def extract_nutrition_goals(nutrition_text: str, health_profile: dict = None, form_data: dict = None) -> dict:
    """
    Extract nutrition goals from AI response or calculate based on profile.
    """
    try:
        # If we have health profile data, use calculated values
        if health_profile:
            return calculate_nutrition_goals(health_profile, form_data)
            
        # Otherwise try to extract from AI response or use defaults
        goals = {
            "Calories": "2000 kcal",
            "Protein": "75g",
            "Carbs": "250g",
            "Fat": "65g"
        }
        
        patterns = {
            'calories': r'(\d+)(?:\s*)?(?:kcal|calories)',
            'protein': r'(\d+)(?:\s*)?g(?:\s*)?(?:of)?(?:\s*)?protein',
            'carbs': r'(\d+)(?:\s*)?g(?:\s*)?(?:of)?(?:\s*)?(?:carbs|carbohydrates)',
            'fat': r'(\d+)(?:\s*)?g(?:\s*)?(?:of)?(?:\s*)?fat'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, nutrition_text.lower())
            if match:
                value = match.group(1)
                if key == 'calories':
                    goals["Calories"] = f"{value} kcal"
                elif key == 'protein':
                    goals["Protein"] = f"{value}g"
                elif key == 'carbs':
                    goals["Carbs"] = f"{value}g"
                elif key == 'fat':
                    goals["Fat"] = f"{value}g"
                    
        return goals
        
    except Exception as e:
        return create_default_nutrition_goals()

async def extract_menu_items(db, menu_categories: list, dietary_restrictions: list = None) -> list:
    """Extract menu items from database with proper calorie distribution."""
    try:
        menu_items = []
        default_items = {
            'breakfast': {
                "name": "Healthy Breakfast Bowl",
                "calories": "500 calories",  # Will be overridden by calculated values
                "description": "Nutritious breakfast with whole grains and fresh fruits"
            },
            'lunch': {
                "name": "Garden Fresh Plate",
                "calories": "700 calories",  # Will be overridden by calculated values
                "description": "Balanced lunch with lean protein and vegetables"
            },
            'dinner': {
                "name": "Grilled Fish with Vegetables",
                "calories": "600 calories",  # Will be overridden by calculated values
                "description": "Light and nutritious dinner option with lean protein"
            }
        }
        
        for category in ['breakfast', 'lunch', 'dinner']:
            try:
                # Get menu items for this category
                query = {"category": category}
                if dietary_restrictions:
                    # Add dietary restrictions to query
                    query["restrictions"] = {"$nin": dietary_restrictions}
                    
                cursor = db.menu_items.find(query)
                category_items = await cursor.to_list(length=None)
                
                if category_items:
                    # Select one item randomly
                    selected_item = random.choice(category_items)
                    menu_items.append({
                        "name": f"{category.title()}: {selected_item['name']}",
                        "calories": f"{selected_item['nutrition_info']['calories']} calories",
                        "description": selected_item['description']
                    })
                else:
                    # Use default item if no matching items found
                    default_item = default_items[category]
                    menu_items.append({
                        "name": f"{category.title()}: {default_item['name']}",
                        "calories": default_item['calories'],
                        "description": default_item['description']
                    })
            except Exception as e:
                logger.error(f"Error processing {category} menu items: {str(e)}")
                # Use default item on error
                default_item = default_items[category]
                menu_items.append({
                    "name": f"{category.title()}: {default_item['name']}",
                    "calories": default_item['calories'],
                    "description": default_item['description']
                })
    
        return menu_items
        
    except Exception as e:
        logger.error(f"Error extracting menu items: {str(e)}")
        raise e

def create_default_nutrition_goals() -> dict:
    """Create default nutrition goals."""
    return {
        "Calories": "1800 kcal",
        "Protein": "70g",
        "Carbs": "220g",
        "Fat": "60g"
    }


app.mount("/", StaticFiles(directory="src/frontend", html=True), name="frontend")