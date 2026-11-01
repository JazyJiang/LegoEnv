"""Mealie recipe and meal-planning registration, with neutral mealie prefix.

Use after importing packlib. The base preserves the original tool panel; helper
functions seed content only and never stand in for agent-side write tools.
"""
import json
import runtime
import packlib
from packlib import World, NS, SERVER, PFX, CONTENT, NOTES, OBS_CAP, SEL, F, AND, CNT

APP = 'mealie'
NEW_SERVER = {APP: 'recipes'}
NEW_CONTENT = {APP: [
    'UserToRecipe', 'CookBook', 'Recipe', 'RecipeIngredient', 'RecipeInstruction',
    'RecipeIngredientRefLink', 'Nutrition', 'RecipeComment', 'Note', 'RecipeAsset',
    'RecipeTimelineEvent', 'RecipeShareToken', 'ApiExtras', 'RecipeSettings',
    'Category', 'Tag', 'Tool', 'MultiPurposeLabel', 'Food', 'FoodAlias', 'Unit',
    'UnitAlias', 'RecipeCategoryLink', 'RecipeTagLink', 'RecipeToolLink',
    'HouseholdFoodLink', 'HouseholdToolLink', 'HouseholdToRecipe', 'GroupMealPlan',
    'GroupMealPlanRules', 'ShoppingList', 'ShoppingListItem',
    'ShoppingListRecipeReference', 'ShoppingListItemRecipeReference',
    'ShoppingListMultiPurposeLabel', 'Webhook', 'GroupEventNotifier',
    'GroupEventNotifierOptions', 'GroupRecipeAction', 'GroupDataExports',
    'Report', 'ReportEntry', 'ServerTask',
]}
NEW_NOTES = {APP: (
    '{p}__ is the recipe and meal-planning app. Sign in using '
    '{p}__auth_login(username=<your email>, password); you are user 1 in group 1, household 1. '
    'recipe_get_all(q) lists recipes, and recipe_get_one(slug) returns a recipe row. '
    'recipe_create(name, description, recipe_servings) creates a recipe; '
    'recipe_patch(slug, description, recipe_servings, rating) updates scalar recipe fields. '
    'recipecomment_search(recipe_id) reads comments; recipecomment_create(recipe_id, text) adds one. '
    'cookbook_search, food_search, unit_search, category_search, tag_search and tool_search accept '
    'optional q to filter names. Omit q to list rows; use a narrow q when a list is large. '
    'Their existing create/update/delete tools accept integer item_id values. '
    'groupmealplan_create(date, entry_type, title, text, recipe_id) creates a meal plan entry; '
    'groupmealplan_search(q) reads entries. shoppinglist_create(name), '
    'shoppinglistitem_create(shopping_list_id, note, quantity, food_id, unit_id) and '
    'shoppinglistitem_update(item_id, checked, quantity, note) manage shopping data. '
    'shoppinglist_search(q) lists shopping lists. Nested recipe ingredients, instructions, '
    'nutrition/settings and category/tag/tool links have no working child-write interface in '
    'this spec; use the supported scalar writes. Raw date/category/JSON search arguments are '
    'not implemented by this runtime; filter returned rows locally.'
)}
LOGIN = {APP: ('auth_login', 'username')}
SERVER.update(NEW_SERVER)
PFX[APP] = 'mealie'
CONTENT.update(NEW_CONTENT)
NOTES.update(NEW_NOTES)
packlib.LOGIN.update(LOGIN)

OBS_READS = [
    'recipe_get_all', 'cookbook_search', 'label_search', 'category_search',
    'tag_search', 'tool_search', 'food_search', 'unit_search',
    'groupmealplan_search', 'shoppinglist_search', 'household_list',
    'household_members', 'recipecomment_search',
]
_original_obs = World.obs_report

def _obs_report(self):
    rep, bad = _original_obs(self)
    if APP not in self.apps:
        return rep, bad
    env = runtime.Env(self.world)
    reply = env.call(NS(APP, 'auth_login'), {'username': self.persona, 'password': self.password})
    if not reply.get('ok'):
        raise RuntimeError(f'Mealie observation login failed: {reply}')
    for tool in OBS_READS:
        if tool == 'recipecomment_search':
            argsets = [{'recipe_id': r['id']} for r in env.state.get(NS(APP, 'Recipe'), [])]
        else:
            argsets = [{}]
        for args in argsets:
            reply = env.call(NS(APP, tool), args)
            if not reply.get('ok'):
                raise RuntimeError(f'Mealie observation read {tool} failed: {reply}')
            key = f"{APP} {tool}" + (f" {args['recipe_id']}" if args else '')
            rep[key] = len(json.dumps(reply, ensure_ascii=False, default=str))
    return rep, {k: v for k, v in rep.items() if v > OBS_CAP}

World.obs_report = _obs_report

def _append(W, entity, rows, src=None):
    """Append integer-identity content and optionally record source provenance."""
    rows = [dict(row) for row in rows]
    for row in rows:
        if not isinstance(row.get('id'), int) or isinstance(row['id'], bool):
            raise ValueError(f'{entity} seed id must be an integer')
    W.spec[APP]['seed_state'].setdefault(entity, []).extend(rows)
    if src:
        W.bindings[NS(APP, entity)] = {'dataset': src, 'rows': len(rows)}
    return rows

def recipes(W, rows, src=None):
    """rows = [{id, slug, name, description?, recipe_servings?, ...}]."""
    return _append(W, 'Recipe', [{'group_id': 1, 'user_id': 1,
        'name_normalized': r['name'].casefold(), 'description_normalized': r.get('description', '').casefold(),
        'recipe_servings': 4, **r} for r in rows], src)

def cookbook(W, cookbook_id, name, description='', src=None):
    """A description can carry a discoverable meal-preparation policy."""
    return _append(W, 'CookBook', [{'id': cookbook_id, 'group_id': 1, 'household_id': 1,
        'name': name, 'slug': name.casefold().replace(' ', '-'), 'description': description,
        'position': 1, 'public': False, 'query_filter_string': ''}], src)

def ingredients(W, recipe_id, rows, src=None):
    """Seed existing ingredients; this is a builder helper, not an agent write API."""
    return _append(W, 'RecipeIngredient', [{'recipe_id': recipe_id, 'position': i+1, **r}
        for i, r in enumerate(rows)], src)

def shopping_list(W, list_id, name, items=(), src=None):
    _append(W, 'ShoppingList', [{'id': list_id, 'group_id': 1, 'user_id': 1, 'name': name}], src)
    return _append(W, 'ShoppingListItem', [{'shopping_list_id': list_id, 'checked': False,
        'position': i, 'quantity': 1, 'is_ingredient': True, **r} for i, r in enumerate(items)], src)

def meal_plan(W, rows, src=None):
    return _append(W, 'GroupMealPlan', [{'group_id': 1, 'user_id': 1, **r} for r in rows], src)

def smoke_seed(W):
    cookbook(W, 10, 'Kitchen operations',
        'Policy: keep nut-free dishes separate; annotate the reviewed lentil soup with its allergen check. '
        'Never alter the reserved dessert recipe during a soup review.')
    recipes(W, [
        {'id': 101, 'slug': 'lentil-soup', 'name': 'Lentil soup',
         'description': 'Weekday lunch; allergen review pending.'},
        {'id': 102, 'slug': 'herb-rice', 'name': 'Herb rice', 'description': 'Side dish for the lunch service.'},
        {'id': 103, 'slug': 'reserved-dessert', 'name': 'Reserved dessert', 'description': 'Reserved dessert; keep unchanged.'},
    ])
    ingredients(W, 101, [{'id': 201, 'title': 'Red lentils', 'quantity': 2, 'note': 'Rinse before cooking.'}])
    shopping_list(W, 20, 'Lunch supplies', [{'id': 301, 'note': 'Red lentils', 'quantity': 2}])
    steps = [
        (APP, 'recipe_patch', {'slug': 'lentil-soup', 'description': 'Weekday lunch; allergen review complete: nut-free.'}),
        (APP, 'recipecomment_create', {'recipe_id': 101, 'text': 'Allergen check complete: nut-free preparation confirmed.'}),
        (APP, 'shoppinglistitem_update', {'item_id': 301, 'checked': True}),
    ]
    preds = [
        ('reviewed', 'The lentil soup has its reviewed allergen description.',
         CNT(SEL(NS(APP, 'Recipe'), AND(F('id', 'eq', 101), F('description', 'eq',
             'Weekday lunch; allergen review complete: nut-free.')))), False),
        ('commented', 'A review comment is attached to the lentil soup by the persona.',
         CNT(SEL(NS(APP, 'RecipeComment'), AND(F('recipe_id', 'eq', 101), F('user_id', 'eq', 1),
             F('text', 'eq', 'Allergen check complete: nut-free preparation confirmed.')))), False),
        ('checked', 'The existing lentil shopping item is checked.',
         CNT(SEL(NS(APP, 'ShoppingListItem'), AND(F('id', 'eq', 301), F('checked', 'eq', True)))), False),
        ('dessert_unchanged', 'The reserved dessert retains its original description.',
         CNT(SEL(NS(APP, 'Recipe'), AND(F('id', 'eq', 103),
             F('description', 'eq', 'Reserved dessert; keep unchanged.')))), True),
    ]
    return steps, preds

__all__ = ['NEW_SERVER', 'recipes', 'cookbook', 'ingredients', 'shopping_list', 'meal_plan', 'smoke_seed']
