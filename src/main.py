from fastapi import FastAPI, HTTPException, Depends, Request, Response, Security
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.config import Config
from motor.motor_asyncio import AsyncIOMotorClient
from authlib.integrations.starlette_client import OAuth
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import jwt
import logging
import json
from jwt.algorithms import RSAAlgorithm
import httpx
from bson import ObjectId
import asyncio

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load configuration from .env file
config = Config('.env')

# Configuration variables
MONGO_URL = config('MONGO_URL', cast=str)
AUTH0_CLIENT_ID = config('AUTH0_CLIENT_ID', cast=str)
AUTH0_CLIENT_SECRET = config('AUTH0_CLIENT_SECRET', cast=str)
AUTH0_DOMAIN = config('AUTH0_DOMAIN', cast=str)
AUTH0_CALLBACK_URL = config('AUTH0_CALLBACK_URL', cast=str)
AUTH0_AUDIENCE = config('AUTH0_AUDIENCE', cast=str)
SECRET_KEY = config('SECRET_KEY', cast=str)

# Pydantic Models
class HealthProfile(BaseModel):
    age: int = Field(0, ge=0, le=150)
    weight: float = Field(0.0, ge=0, le=500)
    height: float = Field(0.0, ge=0, le=300)
    medical_conditions: List[str] = []
    allergies: List[str] = []
    dietary_preferences: List[str] = []

class User(BaseModel):
    id: Optional[str] = None
    name: str
    email: str
    phone: Optional[str] = None
    health_profile: Optional[HealthProfile] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class NutritionInfo(BaseModel):
    calories: int
    protein: float
    carbs: float
    fat: float
    fiber: Optional[float] = None
    vitamins: Optional[Dict[str, float]] = None

class MenuItem(BaseModel):
    id: Optional[str] = None
    name: str
    description: str
    nutrition_info: NutritionInfo
    price: float = Field(ge=0)
    category: str
    image_url: Optional[str] = None
    available: bool = True
    preparation_time: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class MealPlanItem(BaseModel):
    menu_item_id: str
    quantity: int = Field(ge=1)
    meal_time: str  # breakfast, lunch, dinner, snack

class DailyMealPlan(BaseModel):
    date: datetime
    meals: List[MealPlanItem]
    total_calories: int
    total_protein: float
    total_carbs: float
    total_fat: float

class DietPlan(BaseModel):
    id: Optional[str] = None
    user_id: str
    start_date: datetime
    end_date: datetime
    daily_plans: List[DailyMealPlan]
    calories_target: int
    protein_target: int
    carbs_target: int
    fat_target: int
    special_instructions: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class Consultation(BaseModel):
    id: Optional[str] = None
    user_id: str
    consultation_date: datetime
    concerns: str
    diet_goals: List[str]
    preferred_contact_time: str
    status: str = "pending"  # pending, completed, cancelled
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

class Order(BaseModel):
    id: Optional[str] = None
    user_id: str
    diet_plan_id: str
    start_date: datetime
    duration_days: int
    meals_per_day: int
    total_amount: float
    payment_status: str = "pending"  # pending, paid, cancelled
    delivery_address: Dict[str, str]
    special_requests: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

# Database connection and utilities
mongodb_client = None
mongodb_db = None

async def init_mongodb():
    global mongodb_client, mongodb_db
    try:
        # Create MongoDB client with robust connection options
        mongodb_client = AsyncIOMotorClient(
            MONGO_URL,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=5000,
            maxPoolSize=10,
            retryWrites=True,
            retryReads=True
        )
        
        # Test connection
        await mongodb_client.admin.command('ping')
        logger.info("MongoDB connection test successful")
        
        # Get database
        mongodb_db = mongodb_client.dietary_catering
        
        # Ensure collections exist
        collections = await mongodb_db.list_collection_names()
        required_collections = [
            'users', 'menu_items', 'diet_plans', 
            'consultations', 'orders'
        ]
        
        for collection in required_collections:
            if collection not in collections:
                await mongodb_db.create_collection(collection)
                logger.info(f"Created collection: {collection}")
        
        # Create indexes
        await mongodb_db.users.create_index("email", unique=True)
        await mongodb_db.menu_items.create_index("name")
        await mongodb_db.menu_items.create_index([("category", 1), ("available", 1)])
        await mongodb_db.diet_plans.create_index("user_id")
        await mongodb_db.consultations.create_index([("user_id", 1), ("status", 1)])
        await mongodb_db.orders.create_index([("user_id", 1), ("created_at", -1)])
        await mongodb_db.orders.create_index([("diet_plan_id", 1)])
        
        logger.info("MongoDB initialization completed successfully")
        return mongodb_db
    except Exception as e:
        logger.error(f"MongoDB initialization error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Database connection failed: {str(e)}"
        )

async def get_database():
    if mongodb_db is None:
        await init_mongodb()
    return mongodb_db

def format_object_id(obj):
    if isinstance(obj, dict):
        obj_copy = obj.copy()
        for k, v in obj_copy.items():
            if isinstance(v, ObjectId):
                obj[k] = str(v)
            elif isinstance(v, (dict, list)):
                obj[k] = format_object_id(v)
    elif isinstance(obj, list):
        return [format_object_id(item) if isinstance(item, (dict, list)) else str(item) if isinstance(item, ObjectId) else item for item in obj]
    return obj

# Initialize FastAPI app
app = FastAPI(
    title="Health Based Dietary Catering API",
    description="API for managing dietary plans with Auth0 authentication",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add middlewares
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="session",
    max_age=1800,
    same_site="lax",
    https_only=False  # Set to True in production
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://18222081-ii3160-fastapiproject.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
templates = Jinja2Templates(directory="frontend/templates")

# OAuth setup
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
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(request: Request):
    token = request.session.get('token')
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return await verify_token(token)

# Startup and shutdown events
@app.on_event("startup")
async def startup_db_client():
    await init_mongodb()

@app.on_event("shutdown")
async def shutdown_db_client():
    if mongodb_client:
        mongodb_client.close()
        logger.info("MongoDB connection closed")

# Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login")
async def login(request: Request):
    try:
        redirect_uri = AUTH0_CALLBACK_URL
        return await oauth.auth0.authorize_redirect(
            request,
            redirect_uri,
            audience=AUTH0_AUDIENCE
        )
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed")

@app.get("/callback")
async def callback(request: Request):
    try:
        token = await oauth.auth0.authorize_access_token(request)
        userinfo = await oauth.auth0.userinfo(token=token)
        request.session['token'] = token['access_token']
        request.session['user'] = dict(userinfo)
        
        # Create/update user in database
        db = await get_database()
        user_data = {
            "email": userinfo['email'],
            "name": userinfo.get('name', ''),
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        await db.users.update_one(
            {"email": userinfo['email']},
            {"$setOnInsert": user_data},
            upsert=True
        )
        
        return RedirectResponse(url='/dashboard')
    except Exception as e:
        logger.error(f"Callback error: {str(e)}")
        return RedirectResponse(url='/login')

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    try:
        user = request.session.get('user')
        if not user:
            return RedirectResponse(url='/login')
        
        db = await get_database()
        user_profile = await db.users.find_one({"email": user.get('email')})
        
        if user_profile:
            user_profile = format_object_id(user_profile)
            
            # Get active diet plan
            active_diet_plan = await db.diet_plans.find_one({
                "user_id": str(user_profile['_id']),
                "end_date": {"$gte": datetime.now()}
            })
            
            if active_diet_plan:
                active_diet_plan = format_object_id(active_diet_plan)
            
            # Get upcoming consultations
            upcoming_consultations = await db.consultations.find({
                "user_id": str(user_profile['_id']),
                "consultation_date": {"$gte": datetime.now()},
                "status": "pending"
            }).sort("consultation_date", 1).limit(5).to_list(length=5)
            
            upcoming_consultations = format_object_id(upcoming_consultations)
            
            # Get recent orders
            recent_orders = await db.orders.find({
                "user_id": str(user_profile['_id'])
            }).sort("created_at", -1).limit(5).to_list(length=5)
            
            recent_orders = format_object_id(recent_orders)
            
            return templates.TemplateResponse(
                "dashboard.html",
                {
                    "request": request,
                    "user": user,
                    "user_profile": user_profile,
                    "active_diet_plan": active_diet_plan,
                    "upcoming_consultations": upcoming_consultations,
                    "recent_orders": recent_orders
                }
            )
        else:
            logger.error(f"User profile not found for email: {user.get('email')}")
            return templates.TemplateResponse(
                "dashboard.html",
                {"request": request, "user": user, "error": "Profile not found"}
            )
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        return templates.TemplateResponse(
            "dashboard.html",
            {"request": request, "user": user, "error": "Failed to load dashboard"}
        )

@app.post("/update-profile")
async def update_profile(request: Request):
    try:
        db = await get_database()
        user = request.session.get('user')
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        form = await request.form()
        logger.info(f"Received form data: {dict(form)}")
        
        try:
            # Create health profile
            health_profile = HealthProfile(
                age=int(form.get("age", 0)),
                weight=float(form.get("weight", 0)),
                height=float(form.get("height", 0)),
                medical_conditions=form.get("medical_conditions", "").split(",") if form.get("medical_conditions") else [],
                allergies=form.get("allergies", "").split(",") if form.get("allergies") else [],
                dietary_preferences=form.get("dietary_preferences", "").split(",") if form.get("dietary_preferences") else []
            )
            
            # Update user data
            user_data = {
                "name": user.get("name", ""),
                "email": user.get("email", ""),
                "phone": str(form.get("phone", "")),
                "health_profile": health_profile.dict(),
                "updated_at": datetime.now()
            }
            
            # Update in database
            result = await db.users.update_one(
                {"email": user.get("email")},
                {"$set": user_data}
            )
            
            if result.modified_count == 0 and not result.upserted_id:
                # If no document was modified and no new document was created
                await db.users.insert_one(user_data)
            
            logger.info(f"Profile updated successfully for user: {user.get('email')}")
            return JSONResponse(
                content={
                    "status": "success",
                    "message": "Profile updated successfully"
                }
            )
            
        except ValueError as e:
            logger.error(f"Form data validation error: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid form data: {str(e)}")
            
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Profile update error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update profile")

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(
        url=f"https://{AUTH0_DOMAIN}/v2/logout?"
        f"client_id={AUTH0_CLIENT_ID}&"
        f"returnTo=https://18222081-ii3160-fastapiproject.vercel.app"
    )

# Menu Items endpoints
@app.get("/menu-items", response_model=List[MenuItem])
async def get_menu_items(
    request: Request,
    category: Optional[str] = None,
    available_only: bool = True
):
    try:
        user = await get_current_user(request)  # Get current user if needed
        db = await get_database()
        query = {}
        
        if category:
            query["category"] = category
        if available_only:
            query["available"] = True
            
        menu_items = await db.menu_items.find(query).to_list(length=100)
        return format_object_id(menu_items)
    except Exception as e:
        logger.error(f"Error fetching menu items: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch menu items")

@app.post("/menu-items", response_model=MenuItem)
async def create_menu_item(menu_item: MenuItem, request: Request):
    try:
        # Verify admin status (you should implement proper admin verification)
        user = await get_current_user(request)
        
        db = await get_database()
        menu_item_dict = menu_item.dict(exclude={"id"})
        result = await db.menu_items.insert_one(menu_item_dict)
        
        created_item = await db.menu_items.find_one({"_id": result.inserted_id})
        return format_object_id(created_item)
    except Exception as e:
        logger.error(f"Error creating menu item: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create menu item")

# Diet Plan endpoints
@app.post("/diet-plans", response_model=DietPlan)
async def create_diet_plan(diet_plan: DietPlan, request: Request):
    try:
        user = await get_current_user(request)
        db = await get_database()
        
        # Verify user exists
        user_doc = await db.users.find_one({"email": user.get("email")})
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
            
        diet_plan_dict = diet_plan.dict(exclude={"id"})
        diet_plan_dict["user_id"] = str(user_doc["_id"])
        
        # Insert diet plan
        result = await db.diet_plans.insert_one(diet_plan_dict)
        
        created_plan = await db.diet_plans.find_one({"_id": result.inserted_id})
        return format_object_id(created_plan)
    except Exception as e:
        logger.error(f"Error creating diet plan: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create diet plan")

@app.get("/diet-plans/{diet_plan_id}", response_model=DietPlan)
async def get_diet_plan(diet_plan_id: str, request: Request):
    try:
        user = await get_current_user(request)
        db = await get_database()
        
        diet_plan = await db.diet_plans.find_one({"_id": ObjectId(diet_plan_id)})
        if not diet_plan:
            raise HTTPException(status_code=404, detail="Diet plan not found")
            
        return format_object_id(diet_plan)
    except Exception as e:
        logger.error(f"Error fetching diet plan: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch diet plan")

# Consultation endpoints
@app.post("/consultations", response_model=Consultation)
async def create_consultation(consultation: Consultation, request: Request):
    try:
        user = await get_current_user(request)
        db = await get_database()
        
        user_doc = await db.users.find_one({"email": user.get("email")})
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
            
        consultation_dict = consultation.dict(exclude={"id"})
        consultation_dict["user_id"] = str(user_doc["_id"])
        
        result = await db.consultations.insert_one(consultation_dict)
        
        created_consultation = await db.consultations.find_one({"_id": result.inserted_id})
        return format_object_id(created_consultation)
    except Exception as e:
        logger.error(f"Error creating consultation: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create consultation")

@app.post("/orders", response_model=Order)
async def create_order(order: Order, request: Request):
    try:
        user = await get_current_user(request)
        db = await get_database()
        
        user_doc = await db.users.find_one({"email": user.get("email")})
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
            
        # Verify diet plan exists
        diet_plan = await db.diet_plans.find_one({"_id": ObjectId(order.diet_plan_id)})
        if not diet_plan:
            raise HTTPException(status_code=404, detail="Diet plan not found")
            
        order_dict = order.dict(exclude={"id"})
        order_dict["user_id"] = str(user_doc["_id"])
        
        result = await db.orders.insert_one(order_dict)
        
        created_order = await db.orders.find_one({"_id": result.inserted_id})
        return format_object_id(created_order)
    except Exception as e:
        logger.error(f"Error creating order: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create order")

@app.get("/orders/{order_id}", response_model=Order)
async def get_order(order_id: str, request: Request):
    try:
        user = await get_current_user(request)
        db = await get_database()
        
        # Get user document first
        user_doc = await db.users.find_one({"email": user.get("email")})
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Find order with user verification
        order = await db.orders.find_one({
            "_id": ObjectId(order_id),
            "user_id": str(user_doc["_id"])  # Ensure user can only access their own orders
        })
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
            
        return format_object_id(order)
    except Exception as e:
        logger.error(f"Error fetching order: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch order")

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

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