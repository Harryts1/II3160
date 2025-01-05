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

# Initialize Groq
groq_client = Groq(
    api_key="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"
)

async def call_groq_api(prompt: str) -> Dict[str, Any]:
    """
    Make an async call to the Groq API
    """
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "mixtral-8x7b-32768",
        "messages": [
            {
                "role": "system",
                "content": """You are a professional nutritionist and dietary consultant. 
                Provide specific, detailed menu recommendations based on the user's health profile 
                and preferences. Format your response in a structured way with clear sections for 
                nutritional goals, menu items, and health advice."""
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

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        required_collections = ['users', 'menu_items', 'diet_plans', 'consultations']
        
        for collection in required_collections:
            if collection not in collections:
                await db.create_collection(collection)
                
        # Create indexes if they don't exist
        await db.users.create_index("email", unique=True)
        await db.menu_items.create_index("name")
        await db.diet_plans.create_index("user_id")
        await db.consultations.create_index("user_id")
        
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
            ssl_cert_reqs='CERT_NONE',  # WARNING: Use this only for testing
            tls=True,
            tlsAllowInvalidCertificates=True  # WARNING: Use this only for testing
        )
        
        # Test connection with longer timeout
        await asyncio.wait_for(
            mongodb_client.admin.command('ping'),
            timeout=30.0
        )
        
        logger.info("MongoDB connection test successful")
        mongodb_db = mongodb_client.dietary_catering
        
        # Rest of your initialization code...
        
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

@app.on_event("startup")
async def startup_db_client():
    global mongodb_client, mongodb_db
    try:
        # Logging awal
        logger.info("Starting MongoDB connection initialization...")
        logger.info(f"Connecting to MongoDB at: {MONGO_URL[:20]}...")
        
        # Create MongoDB client with robust options
        mongodb_client = AsyncIOMotorClient(
            MONGO_URL,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=10000,
            maxPoolSize=10,
            retryWrites=True,
            retryReads=True
        )
        
        # Test connection
        logger.info("Testing MongoDB connection...")
        await mongodb_client.admin.command('ping')
        
        # Get database
        mongodb_db = mongodb_client.get_database('dietary_catering')
        logger.info(f"Connected to database: {mongodb_db.name}")
        
        # List and create collections if needed
        collections = await mongodb_db.list_collection_names()
        logger.info(f"Existing collections: {collections}")
        
        required_collections = [
            'users', 
            'menu_items', 
            'diet_plans', 
            'consultations'
        ]
        
        # Create missing collections
        for collection in required_collections:
            if collection not in collections:
                logger.info(f"Creating collection: {collection}")
                await mongodb_db.create_collection(collection)
        
        # Create indexes
        logger.info("Creating indexes...")
        await mongodb_db.users.create_index("email", unique=True)
        await mongodb_db.menu_items.create_index("name")
        await mongodb_db.diet_plans.create_index("user_id")
        await mongodb_db.consultations.create_index("user_id")
        
        # Verify final state
        final_collections = await mongodb_db.list_collection_names()
        logger.info(f"Final collections in database: {final_collections}")
        
        # Test write operation
        test_result = await mongodb_db.command("ping")
        logger.info(f"Database write test result: {test_result}")
        
        logger.info("MongoDB initialization completed successfully!")
        
    except Exception as e:
        logger.error(f"Failed to initialize MongoDB: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        logger.error("MongoDB initialization failed!")
        raise e

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
templates = Jinja2Templates(directory="frontend")

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
@app.get("/")
async def serve_home():
    return FileResponse('frontend/index.html')

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
        
        return FileResponse('frontend/dashboard.html')("complete_profile.html", {
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

@app.post("/menu_items", response_model=MenuItem)
async def create_menu_item(menu_item: MenuItem, current_user: dict = Depends(get_current_user)):
    """
    Create a new menu item.
    Requires authentication.
    """
    try:
        menu_dict = menu_item.dict()
        result = await mongodb_db.menu_items.insert_one(menu_dict)
        menu_dict['id'] = str(result.inserted_id)
        return menu_dict
    except Exception as e:
        logger.error(f"Error creating menu item: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/menu_items/{menu_item_id}", response_model=MenuItem)
async def get_menu_item(menu_item_id: str, current_user: dict = Depends(get_current_user)):
    """
    Get menu item by ID.
    Requires authentication.
    """
    try:
        item = await mongodb_db.menu_items.find_one({"_id": menu_item_id})
        if item:
            item['id'] = str(item['_id'])
            del item['_id']
            return item
        raise HTTPException(status_code=404, detail="Menu item not found")
    except Exception as e:
        logger.error(f"Error fetching menu item: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/diet-plans", response_model=DietPlan)
async def create_diet_plan(diet_plan: DietPlan, current_user: dict = Depends(get_current_user)):
    try:
        diet_plan_dict = diet_plan.dict()
        recommendation = recommendation(diet_plan)
        diet_plan_dict['recommended_by_ai'] = True
        result = await mongodb_db.diet_plans.insert_one(diet_plan_dict)
        diet_plan_dict['id'] = str(result.inserted_id)
        return diet_plan_dict
    except Exception as e:
        logger.error(f"Error creating diet plan: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/consultations/", response_model=Consultation)
async def create_consultation(consultation: Consultation):
    try:
        consultation_dict = consultation.dict()
        result = await mongodb_db.consultations.insert_one(consultation_dict)
        consultation_dict['id'] = str(result.inserted_id)
        return consultation_dict
    except Exception as e:
        logger.error(f"Error creating consultation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

@app.post("/recommendations")
async def get_recommendations(request: Request):
    """
    Generate personalized dietary recommendations using Groq AI.
    """
    try:
        # Get user from session
        user = request.session.get('user')
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Get request body
        request_data = await request.json()
        logger.info(f"Received request data: {request_data}")
        
        # Get user profile from database
        db = await get_database()
        user_profile = await db.users.find_one({"email": user.get("email")})
        
        if not user_profile:
            logger.warning(f"No profile found for user: {user.get('email')}")
            user_profile = {}
        
        # Construct prompt
        prompt = construct_dietary_prompt(user_profile, request_data)
        logger.info(f"Generated prompt: {prompt}")
        
        try:
            # Call Groq API using our async function
            response = await call_groq_api(prompt)
            
            # Extract AI response
            ai_response = response['choices'][0]['message']['content']
            logger.info(f"Received AI response: {ai_response[:200]}...")
            
            # Process response
            try:
                structured_response = process_ai_response(ai_response)
            except Exception as e:
                logger.error(f"Error processing AI response: {str(e)}")
                structured_response = create_default_recommendations()
            
            # Add metadata
            final_response = {
                **structured_response,
                "generated_at": datetime.now().isoformat(),
                "version": "1.0"
            }
            
            logger.info(f"Generated recommendations for user: {user.get('email')}")
            return final_response
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error calling AI service: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Groq API error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error generating recommendations: {str(e)}"
            )
            
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in get_recommendations: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )
            
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in get_recommendations: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )

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

def process_ai_response(ai_response: str) -> dict:
    """Process and structure the AI response into a standardized format."""
    try:
        # Split response into sections based on common headers
        sections = {}
        current_section = ''
        current_content = []
        
        for line in ai_response.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # Identify sections
            lower_line = line.lower()
            if 'nutritional goals' in lower_line or 'nutrition goals' in lower_line:
                current_section = 'nutrition'
                continue
            elif 'menu' in lower_line or 'meal plan' in lower_line or 'breakfast' in lower_line:
                current_section = 'menu'
                continue
            elif 'health advice' in lower_line or 'recommendations' in lower_line:
                current_section = 'advice'
                continue
                
            # Add content to current section
            if current_section:
                current_content.append(line)
                sections[current_section] = current_content

        # Process nutrition goals
        nutrition_goals = extract_nutrition_goals('\n'.join(sections.get('nutrition', [])))

        # Process menu items
        menu_items = extract_menu_items('\n'.join(sections.get('menu', [])))

        # Process health advice
        health_advice = '\n'.join(sections.get('advice', [])).strip()
        if not health_advice:
            health_advice = "Based on your profile, focus on regular meals and maintaining a balanced diet that aligns with your goals."

        return {
            "nutritionGoals": nutrition_goals,
            "menuItems": menu_items,
            "healthAdvice": health_advice
        }
        
    except Exception as e:
        logger.error(f"Error processing AI response: {str(e)}")
        return create_default_recommendations()

def extract_nutrition_goals(nutrition_text: str) -> dict:
    """Extract numerical nutrition goals from text."""
    try:
        # Default values
        goals = {
            "Calories": "2000 kcal",
            "Protein": "75g",
            "Carbs": "250g",
            "Fat": "65g"
        }
        
        # Look for specific patterns
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
        logger.error(f"Error extracting nutrition goals: {str(e)}")
        return create_default_nutrition_goals()

def extract_menu_items(menu_text: str) -> list:
    """Extract simplified menu items for catering service."""
    try:
        menu_items = []
        current_meal = None
        
        lines = menu_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check for meal headers
            lower_line = line.lower()
            if any(meal in lower_line for meal in ['breakfast:', 'lunch:', 'dinner:', 'snack:']):
                meal_name = line.split(':')[0].strip()
                meal_desc = line.split(':')[1].strip() if ':' in line else ''
                
                # Extract calories if present
                calories_match = re.search(r'(\d+)(?:\s*)?(?:kcal|calories)', lower_line)
                calories = calories_match.group(1) if calories_match else "400"
                
                menu_items.append({
                    "name": f"{meal_name}: {meal_desc}",
                    "calories": f"{calories} calories",
                    "description": "Balanced nutritional profile suitable for your dietary needs"
                })
        
        # If no items were found, use defaults
        if not menu_items:
            menu_items = create_default_menu_items()
            
        return menu_items
        
    except Exception as e:
        logger.error(f"Error extracting menu items: {str(e)}")
        return create_default_menu_items()

def create_default_recommendations() -> dict:
    """Create default recommendations."""
    return {
        "nutritionGoals": create_default_nutrition_goals(),
        "menuItems": create_default_menu_items(),
        "healthAdvice": "Focus on maintaining a balanced diet with regular meals throughout the day."
    }

def create_default_nutrition_goals() -> dict:
    """Create default nutrition goals."""
    return {
        "Calories": "1800 kcal",
        "Protein": "70g",
        "Carbs": "220g",
        "Fat": "60g"
    }

def create_default_menu_items() -> list:
    """Create default catering menu items."""
    return [
        {
            "name": "Breakfast: Wholesome Morning Bowl",
            "calories": "400 calories",
            "description": "A nutritious breakfast option with whole grains and fresh fruits"
        },
        {
            "name": "Lunch: Garden Fresh Plate",
            "calories": "500 calories",
            "description": "A balanced mix of vegetables and plant-based proteins"
        },
        {
            "name": "Dinner: Evening Wellness Meal",
            "calories": "450 calories",
            "description": "Light and nutritious dinner option"
        }
    ]

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")