
## Optional meal-plan recipe reference

Upstream CreatePlanEntry allows recipe_id=None when a title is provided. Restore nullable=true on GroupMealPlan.recipe_id; keep the existing foreign key and tools. Source: https://raw.githubusercontent.com/mealie-recipes/mealie/mealie-next/mealie/schema/meal_plan/new_meal.py
