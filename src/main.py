from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
import openai

openai.api_key = 'your_openai_api_key'

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

app = FastAPI()

users: List[User ] = [
    User(id=1, name="Alice Smith", email="alice@example.com", health_profile={"age": 30, "weight": 65, "height": 170, "medical_conditions": ["none"]}),
    User(id=2, name="Bob Johnson", email="bob@example.com", health_profile={"age": 45, "weight": 80, "height": 180, "medical_conditions": ["hypertension"]}),
]

menu_items: List[MenuItem] = [
    MenuItem(id=1, name="Salad", description="Fresh garden salad with mixed greens.", nutrition_info={"calories": 150, "protein": 5, "carbohydrates": 10, "fat": 7}),
    MenuItem(id=2, name="Grilled Chicken", description="Grilled chicken breast with herbs.", nutrition_info={"calories": 200, "protein": 30, "carbohydrates": 0, "fat": 5}),
]

diet_plans: List[DietPlan] = []

app = FastAPI()
@app.get("/", status_code=200)
def root():
    return {
        "message": {
            "Welcome to the Health Based Dietary Catering!",
            "valid user_id: 1, 2",
            "valid menu_item_id: 1, 2"
            "diet_plans is not integrated with openai api yet so it is still invalid"
        },
        "endpoints": {
            "users": "/users/{user_id}",
            "menu_items": "/menu_items/{menu_item_id}",
            "diet_plans": "/diet_plans"
        }
    }

@app.post("/users", response_model=User )
def create_user(user: User):
    users.append(user)
    return user

@app.get("/users/{user_id}", response_model=User )
def get_user(user_id: int):
    for user in users:
        if user.id == user_id:
            return user
    raise HTTPException(status_code=404, detail="User  not found")

@app.post("/menu_items", response_model=MenuItem)
def create_menu_item(menu_item: MenuItem):
    menu_items.append(menu_item)
    return menu_item

@app.get("/menu_items/{menu_item_id}", response_model=MenuItem)
def get_menu_item(menu_item_id: int):
    for item in menu_items:
        if item.id == menu_item_id:
            return item
    raise HTTPException(status_code=404, detail="Menu item not found")

@app.post("/diet_plans", response_model=DietPlan)
def create_diet_plan(diet_plan: DietPlan):
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