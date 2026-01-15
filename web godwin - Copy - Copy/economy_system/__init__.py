from .db import init_db
from .economy_service import EconomyService
from .bank_service import BankService
from .game_service import GameService
from .shop_service import ShopService

# Initialize tables on package import
init_db()
