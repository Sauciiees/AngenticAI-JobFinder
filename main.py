import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# 1. กำหนดโครงสร้างข้อมูล (Schema) ที่เราต้องการให้โมเดลตอบกลับมา
# โดยใช้ Pydantic BaseModel เพื่อให้ตรวจสอบชนิดข้อมูลได้ (Validation)
class Recipe(BaseModel):
    recipe_name: str = Field(description="ชื่อเมนูอาหาร")
    ingredients: list[str] = Field(description="รายการส่วนผสมที่ต้องใช้")
    prep_time_mins: int = Field(description="เวลาที่ใช้ในการเตรียมอาหาร (นาที)")

# 2. เริ่มต้นใช้งานโมเดล Gemini
llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")

# 3. บังคับให้โมเดลตอบกลับตามโครงสร้างที่เรากำหนด ด้วยคำสั่ง .with_structured_output()
structured_llm = llm.with_structured_output(Recipe)

# 4. ส่งคำสั่ง (Prompt) เข้าไปตามปกติ
response = structured_llm.invoke("ขอสูตรทำไข่เจียวหมูสับแบบง่ายๆ หน่อย")

# 5. ผลลัพธ์ที่ได้จะไม่ได้เป็น String ธรรมดาแล้ว แต่จะเป็น Object ของคลาส Recipe 
print(f"เมนู: {response.recipe_name}")
print(f"เวลาเตรียม: {response.prep_time_mins} นาที")
print(f"ส่วนผสม: {response.ingredients}")