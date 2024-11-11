from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

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
@app.get("/", status_code=200)
def root():
    return {
        "message": "Welcome to the Health Based Dietary Catering!",
        "endpoints": {
        "users": "/users/{user_id}",
        "menu_items": "/menu_items/{menu_item_id}",
        "diet_plans": "/diet_plans"}
    }

@app.post("/users", response_model=User)
def create_user(user: User):
    return user

@app.get("/users/{user_id}", response_model=User)
def get_user(user_id: int):
    pass

@app.post("/menu_items", response_model=MenuItem)
def create_menu_item(menu_item: MenuItem):
    return menu_item

@app.get("/menu_items/{menu_item_id}", response_model=MenuItem)
def get_menu_item(menu_item_id: int):
    pass

@app.post("/diet_plans", response_model=DietPlan)
def create_diet_plan(diet_plan: DietPlan):
    recommendation = generate_diet_recommendation(diet_plan)
    diet_plan.recommended_by_ai = True
    
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