import logging
from datetime import datetime, date
from typing import Dict, List, Optional
import json
import os
from dataclasses import dataclass, asdict
from enum import Enum

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота (замените на свой)
BOT_TOKEN = "8087846730:AAF8QNxherHkkpLT2pKNwKJ295ZZaVJu5jQ"

# Состояния для ConversationHandler
class States(Enum):
    MENU = 0
    WAYBILL_CREATE = 1
    WAYBILL_DRIVER = 2
    WAYBILL_VEHICLE = 3
    WAYBILL_ROUTE = 4
    WAYBILL_MILEAGE = 5
    REPAIR_CREATE = 6
    REPAIR_VEHICLE = 7
    REPAIR_DESCRIPTION = 8
    REPAIR_COST = 9
    MATERIALS_ADD = 10
    MATERIALS_NAME = 11
    MATERIALS_QUANTITY = 12
    MATERIALS_COST = 13

# Модели данных
@dataclass
class Vehicle:
    id: str
    brand: str
    model: str
    license_plate: str
    year: int
    mileage: int
    status: str = "available"  # available, in_repair, on_route

@dataclass
class Driver:
    id: str
    name: str
    license_number: str
    phone: str
    status: str = "available"  # available, on_route

@dataclass
class Waybill:
    id: str
    driver_id: str
    vehicle_id: str
    route: str
    start_date: str
    end_date: Optional[str]
    start_mileage: int
    end_mileage: Optional[int]
    status: str = "active"  # active, completed

@dataclass
class Repair:
    id: str
    vehicle_id: str
    description: str
    cost: float
    date: str
    status: str = "completed"

@dataclass
class Material:
    id: str
    name: str
    quantity: int
    unit: str
    cost_per_unit: float
    total_cost: float
    date: str

# Класс для управления данными
class DataManager:
    def __init__(self):
        self.data_file = "autobase_data.json"
        self.load_data()
    
    def load_data(self):
        """Загрузка данных из файла"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.vehicles = [Vehicle(**v) for v in data.get('vehicles', [])]
                    self.drivers = [Driver(**d) for d in data.get('drivers', [])]
                    self.waybills = [Waybill(**w) for w in data.get('waybills', [])]
                    self.repairs = [Repair(**r) for r in data.get('repairs', [])]
                    self.materials = [Material(**m) for m in data.get('materials', [])]
            else:
                self.init_sample_data()
        except Exception as e:
            logger.error(f"Ошибка загрузки данных: {e}")
            self.init_sample_data()
    
    def save_data(self):
        """Сохранение данных в файл"""
        try:
            data = {
                'vehicles': [asdict(v) for v in self.vehicles],
                'drivers': [asdict(d) for d in self.drivers],
                'waybills': [asdict(w) for w in self.waybills],
                'repairs': [asdict(r) for r in self.repairs],
                'materials': [asdict(m) for m in self.materials]
            }
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения данных: {e}")
    
    def init_sample_data(self):
        """Инициализация тестовых данных"""
        self.vehicles = [
            Vehicle("1", "КАМАЗ", "65115", "А123БВ777", 2020, 45000),
            Vehicle("2", "ГАЗ", "3307", "В456ГД777", 2019, 38000),
            Vehicle("3", "МАЗ", "5440", "Г789ЕЖ777", 2021, 25000)
        ]
        
        self.drivers = [
            Driver("1", "Иванов Иван Иванович", "7712345678", "+7-900-123-45-67"),
            Driver("2", "Петров Петр Петрович", "7798765432", "+7-900-987-65-43"),
            Driver("3", "Сидоров Сидор Сидорович", "7755555555", "+7-900-555-55-55")
        ]
        
        self.waybills = []
        self.repairs = []
        self.materials = []
        self.save_data()

# Глобальный менеджер данных
data_manager = DataManager()

# Вспомогательные функции
def get_main_keyboard():
    keyboard = [
        [KeyboardButton("📋 Путевые листы"), KeyboardButton("🔧 Ремонт")],
        [KeyboardButton("📦 Расходные материалы"), KeyboardButton("📊 Отчеты")],
        [KeyboardButton("🚛 Транспорт"), KeyboardButton("👥 Водители")],
        [KeyboardButton("➕ Добавить ТС"), KeyboardButton("➕ Добавить водителя")],
        [KeyboardButton("❌ Удалить ТС"), KeyboardButton("❌ Удалить водителя")],
        [KeyboardButton("ℹ️ Справка")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_vehicle_inline_keyboard():
    """Создание inline-клавиатуры со списком транспорта"""
    vehicles = data_manager.vehicles
    keyboard = []
    for vehicle in vehicles:
        text = f"{vehicle.brand} {vehicle.model} ({vehicle.license_plate})"
        keyboard.append([InlineKeyboardButton(text, callback_data=f"vehicle_{vehicle.id}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_driver_select")])
    return InlineKeyboardMarkup(keyboard)

def get_driver_keyboard():
    """Создание клавиатуры со списком водителей"""
    drivers = data_manager.drivers
    keyboard = []
    for driver in drivers:
        keyboard.append([KeyboardButton(driver.name)])
    keyboard.append([KeyboardButton("🔙 Назад")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_driver_inline_keyboard():
    """Создание inline-клавиатуры со списком водителей"""
    drivers = data_manager.drivers
    keyboard = []
    for driver in drivers:
        keyboard.append([InlineKeyboardButton(driver.name, callback_data=f"driver_{driver.id}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_waybills")])
    return InlineKeyboardMarkup(keyboard)

# Основные команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    welcome_text = f"""
🚛 Добро пожаловать в ИС "Автобаза"!

Привет, {user.first_name}!

Этот бот поможет вам управлять автотранспортным предприятием:
• Ведение путевых листов
• Учет ремонтных работ
• Управление расходными материалами
• Мониторинг транспорта и водителей
• Формирование отчетов

Выберите нужный раздел в меню ниже:
    """
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_keyboard()
    )
    return States.MENU

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда помощи"""
    help_text = """
🔧 Возможности бота:

1️⃣ Путевые листы:
   • Создание новых путевых листов
   • Просмотр активных маршрутов
   • Закрытие путевых листов

2️⃣ Ремонт:
   • Регистрация ремонтных работ
   • Учет затрат на ремонт
   • История ремонтов

3️⃣ Расходные материалы:
   • Добавление новых материалов
   • Учет расходов
   • Остатки на складе

4️⃣ Транспорт:
   • Список всех ТС
   • Статус транспорта
   • Пробег и состояние

5️⃣ Водители:
   • База данных водителей
   • Статус водителей
   • Контактная информация

6️⃣ Отчеты:
   • Отчет по транспорту
   • Отчет по ремонтам
   • Отчет по материалам

Для возврата в главное меню используйте /start
    """
    
    await update.message.reply_text(help_text)

async def waybills_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню путевых листов для callback"""
    keyboard = [
        [InlineKeyboardButton("➕ Создать путевой лист", callback_data="waybill_create")],
        [InlineKeyboardButton("📋 Активные путевые листы", callback_data="waybill_active")],
        [InlineKeyboardButton("✅ Закрыть путевой лист", callback_data="waybill_close")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text("📋 Управление путевыми листами:", reply_markup=reply_markup)

# Обработчики путевых листов
async def waybills_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню путевых листов"""
    keyboard = [
        [InlineKeyboardButton("➕ Создать путевой лист", callback_data="waybill_create")],
        [InlineKeyboardButton("📋 Активные путевые листы", callback_data="waybill_active")],
        [InlineKeyboardButton("✅ Закрыть путевой лист", callback_data="waybill_close")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📋 Управление путевыми листами:", reply_markup=reply_markup)

async def create_waybill_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало создания путевого листа"""
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "👤 Выберите водителя:",
        reply_markup=get_driver_inline_keyboard()
    )
    return States.WAYBILL_DRIVER

async def waybill_driver_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор водителя для путевого листа"""
    if update.callback_query:
        # Обработка callback от inline-кнопки
        await update.callback_query.answer()
        callback_data = update.callback_query.data
        
        if callback_data == "back_to_waybills":
            await waybills_menu(update, context)
            return States.MENU
        
        if callback_data.startswith("driver_"):
            driver_id = callback_data.replace("driver_", "")
            driver = next((d for d in data_manager.drivers if d.id == driver_id), None)
            
            if not driver:
                await update.callback_query.edit_message_text("❌ Водитель не найден. Попробуйте еще раз.")
                return States.WAYBILL_DRIVER
            
            context.user_data['waybill_driver_id'] = driver.id
            await update.callback_query.edit_message_text(
                f"✅ Выбран водитель: {driver.name}\n\n🚛 Теперь выберите транспортное средство:",
                reply_markup=get_vehicle_inline_keyboard()
            )
            return States.WAYBILL_VEHICLE
    
    # Обработка текстового сообщения (для совместимости)
    driver_name = update.message.text
    
    if driver_name == "🔙 Назад":
        await update.message.reply_text("Выберите действие:", reply_markup=get_main_keyboard())
        return States.MENU
    
    # Найти водителя по имени
    driver = next((d for d in data_manager.drivers if d.name == driver_name), None)
    if not driver:
        await update.message.reply_text("❌ Водитель не найден. Попробуйте еще раз.")
        return States.WAYBILL_DRIVER
    
    context.user_data['waybill_driver_id'] = driver.id
    await update.message.reply_text(
        f"✅ Выбран водитель: {driver_name}\n\n🚛 Теперь выберите транспортное средство:",
        reply_markup=get_vehicle_keyboard()
    )
    return States.WAYBILL_VEHICLE

async def waybill_vehicle_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор транспорта для путевого листа"""
    if update.callback_query:
        # Обработка callback от inline-кнопки
        await update.callback_query.answer()
        callback_data = update.callback_query.data
        
        if callback_data == "back_to_driver_select":
            await update.callback_query.edit_message_text(
                "👤 Выберите водителя:",
                reply_markup=get_driver_inline_keyboard()
            )
            return States.WAYBILL_DRIVER
        
        if callback_data.startswith("vehicle_"):
            vehicle_id = callback_data.replace("vehicle_", "")
            vehicle = next((v for v in data_manager.vehicles if v.id == vehicle_id), None)
            
            if not vehicle:
                await update.callback_query.edit_message_text("❌ Транспорт не найден. Попробуйте еще раз.")
                return States.WAYBILL_VEHICLE
            
            context.user_data['waybill_vehicle_id'] = vehicle.id
            vehicle_text = f"{vehicle.brand} {vehicle.model} ({vehicle.license_plate})"
            
            # Переключаемся на обычную клавиатуру для ввода маршрута
            await update.callback_query.edit_message_text(
                f"✅ Выбран транспорт: {vehicle_text}\n\n📍 Введите маршрут:"
            )
            await update.callback_query.message.reply_text(
                "Введите маршрут следования:",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Назад")]], resize_keyboard=True)
            )
            return States.WAYBILL_ROUTE
    
    # Обработка текстового сообщения (для совместимости)
    vehicle_text = update.message.text
    
    if vehicle_text == "🔙 Назад":
        await update.message.reply_text("👤 Выберите водителя:", reply_markup=get_driver_keyboard())
        return States.WAYBILL_DRIVER
    
    # Найти транспорт по тексту
    vehicle = None
    for v in data_manager.vehicles:
        if f"{v.brand} {v.model} ({v.license_plate})" == vehicle_text:
            vehicle = v
            break
    
    if not vehicle:
        await update.message.reply_text("❌ Транспорт не найден. Попробуйте еще раз.")
        return States.WAYBILL_VEHICLE
    
    context.user_data['waybill_vehicle_id'] = vehicle.id
    await update.message.reply_text(
        f"✅ Выбран транспорт: {vehicle_text}\n\n📍 Введите маршрут:",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Назад")]], resize_keyboard=True)
    )
    return States.WAYBILL_ROUTE

async def waybill_route_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод маршрута"""
    route = update.message.text
    
    if route == "🔙 Назад":
        await update.message.reply_text("🚛 Выберите транспортное средство:", reply_markup=get_vehicle_keyboard())
        return States.WAYBILL_VEHICLE
    
    context.user_data['waybill_route'] = route
    await update.message.reply_text(
        f"✅ Маршрут: {route}\n\n📏 Введите начальный пробег (км):",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Назад")]], resize_keyboard=True)
    )
    return States.WAYBILL_MILEAGE

async def waybill_mileage_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод пробега и создание путевого листа"""
    mileage_text = update.message.text
    vehicle.status = "on_route"
    driver.status = "on_route"
    
    if mileage_text == "🔙 Назад":
        await update.message.reply_text("📍 Введите маршрут:", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Назад")]], resize_keyboard=True))
        return States.WAYBILL_ROUTE
    
    try:
        mileage = int(mileage_text)
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите корректное число для пробега.")
        return States.WAYBILL_MILEAGE
    
    # Создать путевой лист
    waybill_id = str(len(data_manager.waybills) + 1)
    waybill = Waybill(
        id=waybill_id,
        driver_id=context.user_data['waybill_driver_id'],
        vehicle_id=context.user_data['waybill_vehicle_id'],
        route=context.user_data['waybill_route'],
        start_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        end_date=None,
        start_mileage=mileage,
        end_mileage=None,
        status="active"
    )
    
    data_manager.waybills.append(waybill)
    data_manager.save_data()
    
    # Получить данные водителя и транспорта
    driver = next(d for d in data_manager.drivers if d.id == waybill.driver_id)
    vehicle = next(v for v in data_manager.vehicles if v.id == waybill.vehicle_id)
    
    success_text = f"""
✅ Путевой лист №{waybill_id} создан!

👤 Водитель: {driver.name}
🚛 Транспорт: {vehicle.brand} {vehicle.model} ({vehicle.license_plate})
📍 Маршрут: {waybill.route}
📅 Дата выезда: {waybill.start_date}
📏 Начальный пробег: {waybill.start_mileage} км
    """
    
    await update.message.reply_text(success_text, reply_markup=get_main_keyboard())
    
    # Очистить данные
    context.user_data.clear()
    return States.MENU

# Обработчики транспорта
async def vehicles_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о транспорте"""
    if not data_manager.vehicles:
        await update.message.reply_text("📭 Список транспорта пуст.")
        return
    
    text = "🚛 Список транспортных средств:\n\n"
    for vehicle in data_manager.vehicles:
        status_emoji = "🟢" if vehicle.status == "available" else "🔴" if vehicle.status == "in_repair" else "🟡"
        text += f"{status_emoji} {vehicle.brand} {vehicle.model}\n"
        text += f"   📋 Гос. номер: {vehicle.license_plate}\n"
        text += f"   📅 Год: {vehicle.year}\n"
        text += f"   📏 Пробег: {vehicle.mileage:,} км\n"
        text += f"   📊 Статус: {vehicle.status}\n\n"
    
    await update.message.reply_text(text)

# Обработчики водителей
async def drivers_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о водителях"""
    if not data_manager.drivers:
        await update.message.reply_text("📭 Список водителей пуст.")
        return
    
    text = "👥 Список водителей:\n\n"
    for driver in data_manager.drivers:
        status_emoji = "🟢" if driver.status == "available" else "🔴"
        text += f"{status_emoji} {driver.name}\n"
        text += f"   📋 Удостоверение: {driver.license_number}\n"
        text += f"   📞 Телефон: {driver.phone}\n"
        text += f"   📊 Статус: {driver.status}\n\n"
    
    await update.message.reply_text(text)

# Обработчики ремонта
async def repairs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню ремонтных работ"""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить ремонт", callback_data="repair_create")],
        [InlineKeyboardButton("📋 История ремонтов", callback_data="repair_history")],
        [InlineKeyboardButton("💰 Статистика затрат", callback_data="repair_stats")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🔧 Управление ремонтными работами:", reply_markup=reply_markup)

async def repair_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """История ремонтов"""
    if not data_manager.repairs:
        text = "📭 История ремонтов пуста."
    else:
        text = "🔧 История ремонтных работ:\n\n"
        total_cost = 0
        for repair in data_manager.repairs:
            vehicle = next((v for v in data_manager.vehicles if v.id == repair.vehicle_id), None)
            vehicle_info = f"{vehicle.brand} {vehicle.model} ({vehicle.license_plate})" if vehicle else "Неизвестное ТС"
            text += f"🆔 Ремонт №{repair.id}\n"
            text += f"🚛 ТС: {vehicle_info}\n"
            text += f"🔧 Работы: {repair.description}\n"
            text += f"💰 Стоимость: {repair.cost:,.2f} ₽\n"
            text += f"📅 Дата: {repair.date}\n\n"
            total_cost += repair.cost
        
        text += f"💰 Общая сумма ремонтов: {total_cost:,.2f} ₽"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_repairs")]]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# Обработчики расходных материалов
async def materials_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню расходных материалов"""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить материал", callback_data="material_add")],
        [InlineKeyboardButton("📋 Список материалов", callback_data="material_list")],
        [InlineKeyboardButton("💰 Общие затраты", callback_data="material_costs")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📦 Управление расходными материалами:", reply_markup=reply_markup)

async def materials_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список расходных материалов"""
    if not data_manager.materials:
        text = "📭 Список материалов пуст."
    else:
        text = "📦 Расходные материалы:\n\n"
        total_cost = 0
        for material in data_manager.materials:
            text += f"📦 {material.name}\n"
            text += f"📊 Количество: {material.quantity} {material.unit}\n"
            text += f"💰 Цена за единицу: {material.cost_per_unit:,.2f} ₽\n"
            text += f"💰 Общая сумма: {material.total_cost:,.2f} ₽\n"
            text += f"📅 Дата: {material.date}\n\n"
            total_cost += material.total_cost
        
        text += f"💰 Общая стоимость материалов: {total_cost:,.2f} ₽"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_materials")]]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def create_repair_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало создания записи о ремонте"""
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "🚛 Выберите транспортное средство для ремонта:",
        reply_markup=get_vehicle_inline_keyboard()
    )
    return States.REPAIR_VEHICLE

async def repair_vehicle_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор транспорта для ремонта"""
    if update.callback_query:
        await update.callback_query.answer()
        callback_data = update.callback_query.data
        
        if callback_data == "back_to_repairs":
            await repairs_menu_callback(update, context)
            return States.MENU
        
        if callback_data.startswith("vehicle_"):
            vehicle_id = callback_data.replace("vehicle_", "")
            vehicle = next((v for v in data_manager.vehicles if v.id == vehicle_id), None)
            
            if not vehicle:
                await update.callback_query.edit_message_text("❌ Транспорт не найден. Попробуйте еще раз.")
                return States.REPAIR_VEHICLE
            
            context.user_data['repair_vehicle_id'] = vehicle.id
            vehicle_text = f"{vehicle.brand} {vehicle.model} ({vehicle.license_plate})"
            
            await update.callback_query.edit_message_text(
                f"✅ Выбран транспорт: {vehicle_text}\n\n🔧 Опишите выполненные работы:"
            )
            await update.callback_query.message.reply_text(
                "Введите описание ремонтных работ:",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Назад")]], resize_keyboard=True)
            )
            return States.REPAIR_DESCRIPTION

async def repair_description_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод описания ремонта"""
    description = update.message.text
    
    if description == "🔙 Назад":
        await update.message.reply_text("Выберите действие:", reply_markup=get_main_keyboard())
        return States.MENU
    
    context.user_data['repair_description'] = description
    await update.message.reply_text(
        f"✅ Описание: {description}\n\n💰 Введите стоимость ремонта (₽):",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Назад")]], resize_keyboard=True)
    )
    return States.REPAIR_COST

async def repair_cost_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод стоимости ремонта"""
    cost_text = update.message.text
    
    if cost_text == "🔙 Назад":
        await update.message.reply_text("Введите описание ремонтных работ:", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Назад")]], resize_keyboard=True))
        return States.REPAIR_DESCRIPTION
    
    try:
        cost = float(cost_text.replace(',', '.'))
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите корректную сумму.")
        return States.REPAIR_COST
    
    # Создать запись о ремонте
    repair_id = str(len(data_manager.repairs) + 1)
    repair = Repair(
        id=repair_id,
        vehicle_id=context.user_data['repair_vehicle_id'],
        description=context.user_data['repair_description'],
        cost=cost,
        date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        status="completed"
    )
    
    data_manager.repairs.append(repair)
    data_manager.save_data()
    
    # Получить данные транспорта
    vehicle = next(v for v in data_manager.vehicles if v.id == repair.vehicle_id)
    
    success_text = f"""
✅ Ремонт №{repair_id} зарегистрирован!

🚛 Транспорт: {vehicle.brand} {vehicle.model} ({vehicle.license_plate})
🔧 Работы: {repair.description}
💰 Стоимость: {repair.cost:,.2f} ₽
📅 Дата: {repair.date}
    """
    
    await update.message.reply_text(success_text, reply_markup=get_main_keyboard())
    
    # Очистить данные
    context.user_data.clear()
    return States.MENU

async def repairs_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню ремонта для callback"""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить ремонт", callback_data="repair_create")],
        [InlineKeyboardButton("📋 История ремонтов", callback_data="repair_history")],
        [InlineKeyboardButton("💰 Статистика затрат", callback_data="repair_stats")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text("🔧 Управление ремонтными работами:", reply_markup=reply_markup)

async def materials_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню материалов для callback"""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить материал", callback_data="material_add")],
        [InlineKeyboardButton("📋 Список материалов", callback_data="material_list")],
        [InlineKeyboardButton("💰 Общие затраты", callback_data="material_costs")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text("📦 Управление расходными материалами:", reply_markup=reply_markup)

# Обработчики отчетов
async def reports_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню отчетов"""
    keyboard = [
        [InlineKeyboardButton("🚛 Отчет по транспорту", callback_data="report_vehicles")],
        [InlineKeyboardButton("🔧 Отчет по ремонтам", callback_data="report_repairs")],
        [InlineKeyboardButton("📦 Отчет по материалам", callback_data="report_materials")],
        [InlineKeyboardButton("📋 Отчет по путевым листам", callback_data="report_waybills")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📊 Выберите тип отчета:", reply_markup=reply_markup)

# Обработчик callback-запросов
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    
    """Обработчик нажатий на inline-кнопки"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "waybill_create":
        return await create_waybill_start(update, context)
    elif query.data == "waybill_active":
        active_waybills = [w for w in data_manager.waybills if w.status == "active"]
        if not active_waybills:
            await query.edit_message_text("📭 Нет активных путевых листов.")
            return
        
        text = "📋 Активные путевые листы:\n\n"
        for waybill in active_waybills:
            driver = next(d for d in data_manager.drivers if d.id == waybill.driver_id)
            vehicle = next(v for v in data_manager.vehicles if v.id == waybill.vehicle_id)
            text += f"🆔 Путевой лист №{waybill.id}\n"
            text += f"👤 Водитель: {driver.name}\n"
            text += f"🚛 Транспорт: {vehicle.license_plate}\n"
            text += f"📍 Маршрут: {waybill.route}\n"
            text += f"📅 Дата: {waybill.start_date}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_waybills")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif query.data == "repair_create":
        return await create_repair_start(update, context)
    elif query.data == "repair_history":
        return await repair_history(update, context)
    elif query.data == "material_list":
        return await materials_list(update, context)
    elif query.data == "back_to_menu":
        await query.message.reply_text("Выберите раздел:", reply_markup=get_main_keyboard())
        await query.edit_message_text("Главное меню")
    elif query.data == "back_to_waybills":
        await waybills_menu_callback(update, context)
    elif query.data == "back_to_repairs":
        await repairs_menu_callback(update, context)
    elif query.data == "back_to_materials":
        await materials_menu_callback(update, context)

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    text = update.message.text
    
    if text == "📋 Путевые листы":
        await waybills_menu(update, context)
    elif text == "🔧 Ремонт":
        await repairs_menu(update, context)
    elif text == "📦 Расходные материалы":
        await materials_menu(update, context)
    elif text == "🚛 Транспорт":
        await vehicles_info(update, context)
    elif text == "👥 Водители":
        await drivers_info(update, context)
    elif text == "📊 Отчеты":
        await reports_menu(update, context)
    elif text == "ℹ️ Справка":
        await help_command(update, context)
    elif text.startswith("➕ Добавить водителя"):
        await update.message.reply_text("Введите ФИО, номер прав и телефон через запятую:")
        context.user_data["action"] = "add_driver"
    elif text.startswith("➕ Добавить ТС"):
        await update.message.reply_text("Введите марку, модель, номер, год и пробег через запятую:")
        context.user_data["action"] = "add_vehicle"
    elif text.startswith("❌ Удалить водителя"):
        await update.message.reply_text("Введите ФИО водителя для удаления:")
        context.user_data["action"] = "delete_driver"
    elif text.startswith("❌ Удалить ТС"):
        await update.message.reply_text("Введите номер ТС для удаления:")
        context.user_data["action"] = "delete_vehicle"
    elif "," in text:
        action = context.user_data.get("action")
        parts = [p.strip() for p in text.split(",")]

        if action == "add_driver" and len(parts) == 3:
            driver = Driver(id=str(len(data_manager.drivers)+1), name=parts[0], license_number=parts[1], phone=parts[2])
            data_manager.drivers.append(driver)
            data_manager.save_data()
            await update.message.reply_text(f"✅ Водитель {driver.name} добавлен.")
        elif action == "add_vehicle" and len(parts) == 5:
            try:
                vehicle = Vehicle(
                    id=str(len(data_manager.vehicles)+1),
                    brand=parts[0], model=parts[1],
                    license_plate=parts[2],
                    year=int(parts[3]), mileage=int(parts[4])
                )
                data_manager.vehicles.append(vehicle)
                data_manager.save_data()
                await update.message.reply_text(f"✅ Транспорт {vehicle.brand} {vehicle.model} добавлен.")
            except:
                await update.message.reply_text("❌ Ошибка при добавлении ТС.")
        else:
            await update.message.reply_text("❌ Неверный формат данных.")
        context.user_data.clear()
    elif context.user_data.get("action") == "delete_driver":
        name = text.strip()
        data_manager.drivers = [d for d in data_manager.drivers if d.name != name]
        data_manager.save_data()
        await update.message.reply_text(f"✅ Водитель {name} удалён (если найден).")
        context.user_data.clear()
    elif context.user_data.get("action") == "delete_vehicle":
        plate = text.strip()
        data_manager.vehicles = [v for v in data_manager.vehicles if v.license_plate != plate]
        data_manager.save_data()
        await update.message.reply_text(f"✅ Транспорт с номером {plate} удалён (если найден).")
        context.user_data.clear()

    else:
        await update.message.reply_text("❓ Команда не распознана. Используйте меню ниже или /help для справки.")

def main():
    """Основная функция запуска бота"""
    # Создание приложения
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Настройка ConversationHandler для путевых листов
    waybill_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(create_waybill_start, pattern="waybill_create")
        ],
        states={
            States.MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                CallbackQueryHandler(button_callback)
            ],
            States.WAYBILL_DRIVER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, waybill_driver_selected),
                CallbackQueryHandler(waybill_driver_selected)
            ],
            States.WAYBILL_VEHICLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, waybill_vehicle_selected),
                CallbackQueryHandler(waybill_vehicle_selected)
            ],
            States.WAYBILL_ROUTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, waybill_route_entered)
            ],
            States.WAYBILL_MILEAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, waybill_mileage_entered)
            ],
            States.REPAIR_VEHICLE: [
                CallbackQueryHandler(repair_vehicle_selected)
            ],
            States.REPAIR_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, repair_description_entered)
            ],
            States.REPAIR_COST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, repair_cost_entered)
            ],
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    # Добавление обработчиков
    application.add_handler(waybill_handler)
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CallbackQueryHandler(button_callback))
# Продолжение кода с функции main()

# Дополнительные функции для создания клавиатур
def get_vehicle_keyboard():
    """Создание клавиатуры со списком транспорта"""
    vehicles = data_manager.vehicles
    keyboard = []
    for vehicle in vehicles:
        text = f"{vehicle.brand} {vehicle.model} ({vehicle.license_plate})"
        keyboard.append([KeyboardButton(text)])
    keyboard.append([KeyboardButton("🔙 Назад")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Дополнительные обработчики для материалов
async def create_material_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления материала"""
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("📦 Введите название материала:")
    await update.callback_query.message.reply_text(
        "Введите название материала:",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Назад")]], resize_keyboard=True)
    )
    return States.MATERIALS_NAME

async def material_name_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод названия материала"""
    name = update.message.text
    
    if name == "🔙 Назад":
        await update.message.reply_text("Выберите действие:", reply_markup=get_main_keyboard())
        return States.MENU
    
    context.user_data['material_name'] = name
    await update.message.reply_text(
        f"✅ Название: {name}\n\n📊 Введите количество:",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Назад")]], resize_keyboard=True)
    )
    return States.MATERIALS_QUANTITY

async def material_quantity_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод количества материала"""
    quantity_text = update.message.text
    
    if quantity_text == "🔙 Назад":
        await update.message.reply_text("Введите название материала:", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Назад")]], resize_keyboard=True))
        return States.MATERIALS_NAME
    
    try:
        quantity = int(quantity_text)
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите корректное количество.")
        return States.MATERIALS_QUANTITY
    
    context.user_data['material_quantity'] = quantity
    await update.message.reply_text(
        f"✅ Количество: {quantity}\n\n💰 Введите стоимость за единицу (₽):",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Назад")]], resize_keyboard=True)
    )
    return States.MATERIALS_COST

async def material_cost_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод стоимости материала"""
    cost_text = update.message.text
    
    if cost_text == "🔙 Назад":
        await update.message.reply_text("📊 Введите количество:", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Назад")]], resize_keyboard=True))
        return States.MATERIALS_QUANTITY
    
    try:
        cost_per_unit = float(cost_text.replace(',', '.'))
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите корректную стоимость.")
        return States.MATERIALS_COST
    
    # Создать материал
    material_id = str(len(data_manager.materials) + 1)
    quantity = context.user_data['material_quantity']
    total_cost = quantity * cost_per_unit
    
    material = Material(
        id=material_id,
        name=context.user_data['material_name'],
        quantity=quantity,
        unit="шт",  # можно расширить для выбора единиц измерения
        cost_per_unit=cost_per_unit,
        total_cost=total_cost,
        date=datetime.now().strftime("%Y-%m-%d %H:%M")
    )
    
    data_manager.materials.append(material)
    data_manager.save_data()
    
    success_text = f"""
✅ Материал добавлен!

📦 Название: {material.name}
📊 Количество: {material.quantity} {material.unit}
💰 Цена за единицу: {material.cost_per_unit:,.2f} ₽
💰 Общая стоимость: {material.total_cost:,.2f} ₽
📅 Дата: {material.date}
    """
    
    await update.message.reply_text(success_text, reply_markup=get_main_keyboard())
    
    # Очистить данные
    context.user_data.clear()
    return States.MENU

# Дополнительные функции для отчетов
async def report_vehicles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отчет по транспорту"""
    if not data_manager.vehicles:
        text = "📭 Нет данных о транспорте."
    else:
        text = "🚛 ОТЧЕТ ПО ТРАНСПОРТУ\n\n"
        available_count = 0
        in_repair_count = 0
        on_route_count = 0
        total_mileage = 0
        
        for vehicle in data_manager.vehicles:
            if vehicle.status == "available":
                available_count += 1
            elif vehicle.status == "in_repair":
                in_repair_count += 1
            elif vehicle.status == "on_route":
                on_route_count += 1
            total_mileage += vehicle.mileage
        
        text += f"📊 СТАТИСТИКА:\n"
        text += f"• Общее количество ТС: {len(data_manager.vehicles)}\n"
        text += f"• Доступно: {available_count}\n"
        text += f"• В ремонте: {in_repair_count}\n"
        text += f"• На маршруте: {on_route_count}\n"
        text += f"• Общий пробег: {total_mileage:,} км\n"
        text += f"• Средний пробег: {total_mileage//len(data_manager.vehicles):,} км\n\n"
        
        text += "📋 ДЕТАЛИ:\n"
        for vehicle in data_manager.vehicles:
            status_emoji = "🟢" if vehicle.status == "available" else "🔴" if vehicle.status == "in_repair" else "🟡"
            text += f"{status_emoji} {vehicle.brand} {vehicle.model} ({vehicle.license_plate})\n"
            text += f"   📅 {vehicle.year} г., 📏 {vehicle.mileage:,} км\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_reports")]]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def report_repairs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отчет по ремонтам"""
    if not data_manager.repairs:
        text = "📭 Нет данных о ремонтах."
    else:
        text = "🔧 ОТЧЕТ ПО РЕМОНТАМ\n\n"
        total_cost = sum(repair.cost for repair in data_manager.repairs)
        avg_cost = total_cost / len(data_manager.repairs)
        
        text += f"📊 СТАТИСТИКА:\n"
        text += f"• Общее количество ремонтов: {len(data_manager.repairs)}\n"
        text += f"• Общая стоимость: {total_cost:,.2f} ₽\n"
        text += f"• Средняя стоимость: {avg_cost:,.2f} ₽\n\n"
        
        # Группировка по транспорту
        repairs_by_vehicle = {}
        for repair in data_manager.repairs:
            if repair.vehicle_id not in repairs_by_vehicle:
                repairs_by_vehicle[repair.vehicle_id] = []
            repairs_by_vehicle[repair.vehicle_id].append(repair)
        
        text += "📋 ПО ТРАНСПОРТУ:\n"
        for vehicle_id, repairs in repairs_by_vehicle.items():
            vehicle = next((v for v in data_manager.vehicles if v.id == vehicle_id), None)
            if vehicle:
                vehicle_cost = sum(r.cost for r in repairs)
                text += f"🚛 {vehicle.brand} {vehicle.model} ({vehicle.license_plate})\n"
                text += f"   Ремонтов: {len(repairs)}, Сумма: {vehicle_cost:,.2f} ₽\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_reports")]]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def report_materials(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отчет по материалам"""
    if not data_manager.materials:
        text = "📭 Нет данных о материалах."
    else:
        text = "📦 ОТЧЕТ ПО МАТЕРИАЛАМ\n\n"
        total_cost = sum(material.total_cost for material in data_manager.materials)
        total_items = len(data_manager.materials)
        
        text += f"📊 СТАТИСТИКА:\n"
        text += f"• Общее количество позиций: {total_items}\n"
        text += f"• Общая стоимость: {total_cost:,.2f} ₽\n"
        
        if total_items > 0:
            avg_cost = total_cost / total_items
            text += f"• Средняя стоимость позиции: {avg_cost:,.2f} ₽\n"
        
        text += "\n📋 САМЫЕ ДОРОГИЕ ПОЗИЦИИ:\n"
        sorted_materials = sorted(data_manager.materials, key=lambda x: x.total_cost, reverse=True)[:5]
        for material in sorted_materials:
            text += f"📦 {material.name}: {material.total_cost:,.2f} ₽\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_reports")]]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def report_waybills(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отчет по путевым листам"""
    if not data_manager.waybills:
        text = "📭 Нет данных о путевых листах."
    else:
        text = "📋 ОТЧЕТ ПО ПУТЕВЫМ ЛИСТАМ\n\n"
        active_count = len([w for w in data_manager.waybills if w.status == "active"])
        completed_count = len([w for w in data_manager.waybills if w.status == "completed"])
        
        text += f"📊 СТАТИСТИКА:\n"
        text += f"• Общее количество: {len(data_manager.waybills)}\n"
        text += f"• Активных: {active_count}\n"
        text += f"• Завершенных: {completed_count}\n\n"
        
        # Расчет общего пробега
        total_mileage = 0
        for waybill in data_manager.waybills:
            if waybill.end_mileage is not None and waybill.start_mileage is not None:
                total_mileage += waybill.end_mileage - waybill.start_mileage
        
        text += f"📏 Общий пробег по путевым листам: {total_mileage:,} км\n\n"
        
        # Группировка по водителям
        waybills_by_driver = {}
        for waybill in data_manager.waybills:
            if waybill.driver_id not in waybills_by_driver:
                waybills_by_driver[waybill.driver_id] = 0
            waybills_by_driver[waybill.driver_id] += 1
        
        text += "👥 ПО ВОДИТЕЛЯМ:\n"
        for driver_id, count in waybills_by_driver.items():
            driver = next((d for d in data_manager.drivers if d.id == driver_id), None)
            if driver:
                text += f"👤 {driver.name}: {count} путевых листов\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_reports")]]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# Обновленный обработчик callback-запросов
async def button_callback_extended(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Расширенный обработчик нажатий на inline-кнопки"""
    query = update.callback_query
    await query.answer()
    
    # Обработка отчетов
    if query.data == "report_vehicles":
        return await report_vehicles(update, context)
    elif query.data == "report_repairs":
        return await report_repairs(update, context)
    elif query.data == "report_materials":
        return await report_materials(update, context)
    elif query.data == "report_waybills":
        return await report_waybills(update, context)
    elif query.data == "back_to_reports":
        keyboard = [
            [InlineKeyboardButton("🚛 Отчет по транспорту", callback_data="report_vehicles")],
            [InlineKeyboardButton("🔧 Отчет по ремонтам", callback_data="report_repairs")],
            [InlineKeyboardButton("📦 Отчет по материалам", callback_data="report_materials")],
            [InlineKeyboardButton("📋 Отчет по путевым листам", callback_data="report_waybills")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("📊 Выберите тип отчета:", reply_markup=reply_markup)
    
    # Обработка материалов
    elif query.data == "material_add":
        return await create_material_start(update, context)
    elif query.data == "material_costs":
        if not data_manager.materials:
            text = "📭 Нет данных о материалах."
        else:
            total_cost = sum(material.total_cost for material in data_manager.materials)
            text = f"💰 Общие затраты на материалы: {total_cost:,.2f} ₽"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_materials")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # Обработка статистики ремонтов
    elif query.data == "repair_stats":
        if not data_manager.repairs:
            text = "📭 Нет данных о ремонтах."
        else:
            total_cost = sum(repair.cost for repair in data_manager.repairs)
            avg_cost = total_cost / len(data_manager.repairs)
            text = f"🔧 СТАТИСТИКА РЕМОНТОВ\n\n"
            text += f"💰 Общие затраты: {total_cost:,.2f} ₽\n"
            text += f"📊 Количество ремонтов: {len(data_manager.repairs)}\n"
            text += f"💰 Средняя стоимость: {avg_cost:,.2f} ₽"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_repairs")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # Обработка закрытия путевых листов
    elif query.data == "waybill_close":
        active_waybills = [w for w in data_manager.waybills if w.status == "active"]
        if not active_waybills:
            await query.edit_message_text("📭 Нет активных путевых листов для закрытия.")
            return
        
        keyboard = []
        for waybill in active_waybills:
            driver = next((d for d in data_manager.drivers if d.id == waybill.driver_id), None)
            vehicle = next((v for v in data_manager.vehicles if v.id == waybill.vehicle_id), None)
            text = f"№{waybill.id} - {driver.name if driver else 'Неизвестный'} ({vehicle.license_plate if vehicle else 'Неизвестное ТС'})"
            keyboard.append([InlineKeyboardButton(text, callback_data=f"close_waybill_{waybill.id}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_waybills")])
        await query.edit_message_text("Выберите путевой лист для закрытия:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # Обработка закрытия конкретного путевого листа
    elif query.data.startswith("close_waybill_"):
        waybill_id = query.data.replace("close_waybill_", "")
        waybill = next((w for w in data_manager.waybills if w.id == waybill_id), None)
        vehicle.status = "available"
        driver.status = "available"
        
        if waybill:
            # Здесь можно добавить запрос конечного пробега
            # Для упрощения просто закрываем с текущим временем
            waybill.status = "completed"
            waybill.end_date = datetime.now().strftime("%Y-%m-%d %H:%M")
            waybill.end_mileage = waybill.start_mileage + 100  # TODO: заменить на ввод пользователем
            # Обновление статусов
            vehicle.status = "available"
            driver.status = "available"
            waybill.end_date = datetime.now().strftime("%Y-%m-%d %H:%M")
            # Можно добавить логику для ввода конечного пробега
            
            data_manager.save_data()
            
            driver = next((d for d in data_manager.drivers if d.id == waybill.driver_id), None)
            vehicle = next((v for v in data_manager.vehicles if v.id == waybill.vehicle_id), None)
            
            success_text = f"""
✅ Путевой лист №{waybill.id} закрыт!

👤 Водитель: {driver.name if driver else 'Неизвестный'}
🚛 Транспорт: {vehicle.license_plate if vehicle else 'Неизвестное ТС'}
📅 Закрыт: {waybill.end_date}
            """
            
            keyboard = [[InlineKeyboardButton("🔙 К путевым листам", callback_data="back_to_waybills")]]
            await query.edit_message_text(success_text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.edit_message_text("❌ Путевой лист не найден.")

# Обновленная главная функция
def main():
    """Основная функция запуска бота"""
    # Создание приложения
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Настройка ConversationHandler
    conversation_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(create_waybill_start, pattern="waybill_create"),
            CallbackQueryHandler(create_repair_start, pattern="repair_create"),
            CallbackQueryHandler(create_material_start, pattern="material_add")
        ],
        states={
            States.MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                CallbackQueryHandler(button_callback),
                CallbackQueryHandler(button_callback_extended)
            ],
            States.WAYBILL_DRIVER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, waybill_driver_selected),
                CallbackQueryHandler(waybill_driver_selected)
            ],
            States.WAYBILL_VEHICLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, waybill_vehicle_selected),
                CallbackQueryHandler(waybill_vehicle_selected)
            ],
            States.WAYBILL_ROUTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, waybill_route_entered)
            ],
            States.WAYBILL_MILEAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, waybill_mileage_entered)
            ],
            States.REPAIR_VEHICLE: [
                CallbackQueryHandler(repair_vehicle_selected)
            ],
            States.REPAIR_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, repair_description_entered)
            ],
            States.REPAIR_COST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, repair_cost_entered)
            ],
            States.MATERIALS_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, material_name_entered)
            ],
            States.MATERIALS_QUANTITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, material_quantity_entered)
            ],
            States.MATERIALS_COST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, material_cost_entered)
            ],
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    # Добавление обработчиков
    application.add_handler(conversation_handler)
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(CallbackQueryHandler(button_callback_extended))
    
    # Запуск бота
    print("🚛 Бот ИС 'Автобаза' запущен...")
    print("Нажмите Ctrl+C для остановки")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()