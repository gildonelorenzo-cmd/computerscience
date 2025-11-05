from fastapi import FastAPI, APIRouter, HTTPException, Depends
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import bcrypt

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Define Models
class Student(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    barcode: str
    name: str
    student_class: str
    profile_pic: str = "https://ui-avatars.com/api/?name=Student&background=random"
    active: bool = True
    stars: int = 0
    badges: List[str] = []
    books_read: int = 0

class StudentCreate(BaseModel):
    barcode: str
    name: str
    student_class: str
    profile_pic: Optional[str] = None

class Book(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    barcode: str
    title: str
    author: str
    category: str
    cover_image: str = "https://via.placeholder.com/150x200/4a90e2/ffffff?text=Book"
    available: int = 1
    total_copies: int = 1

class BookCreate(BaseModel):
    barcode: str
    title: str
    author: str
    category: str
    cover_image: Optional[str] = None
    total_copies: int = 1

class Transaction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    student_barcode: str
    student_name: str
    book_barcode: str
    book_title: str
    borrow_date: str
    due_date: str
    return_date: Optional[str] = None
    status: str = "borrowed"  # borrowed, returned
    overdue_days: int = 0

class BorrowRequest(BaseModel):
    student_barcode: str
    book_barcode: str

class ReturnRequest(BaseModel):
    book_barcode: str
    student_barcode: str

class AdminLogin(BaseModel):
    username: str
    password: str

class StudentLogin(BaseModel):
    barcode: str

# Initialize mock data
async def initialize_mock_data():
    # Check if data already exists
    student_count = await db.students.count_documents({})
    if student_count > 0:
        return
    
    # Mock students
    students = [
        {"id": str(uuid.uuid4()), "barcode": "STU001", "name": "Emma Johnson", "student_class": "Grade 5A", "profile_pic": "https://ui-avatars.com/api/?name=Emma+Johnson&background=FF6B9D&color=fff", "active": True, "stars": 15, "badges": ["Bookworm", "Speed Reader"], "books_read": 8},
        {"id": str(uuid.uuid4()), "barcode": "STU002", "name": "Liam Smith", "student_class": "Grade 6B", "profile_pic": "https://ui-avatars.com/api/?name=Liam+Smith&background=4ECDC4&color=fff", "active": True, "stars": 10, "badges": ["Bookworm"], "books_read": 5},
        {"id": str(uuid.uuid4()), "barcode": "STU003", "name": "Olivia Brown", "student_class": "Grade 4C", "profile_pic": "https://ui-avatars.com/api/?name=Olivia+Brown&background=FFD93D&color=fff", "active": True, "stars": 20, "badges": ["Bookworm", "Speed Reader", "Star Reader"], "books_read": 12},
        {"id": str(uuid.uuid4()), "barcode": "STU004", "name": "Noah Davis", "student_class": "Grade 5B", "profile_pic": "https://ui-avatars.com/api/?name=Noah+Davis&background=95E1D3&color=fff", "active": True, "stars": 5, "badges": [], "books_read": 3},
        {"id": str(uuid.uuid4()), "barcode": "STU005", "name": "Ava Wilson", "student_class": "Grade 6A", "profile_pic": "https://ui-avatars.com/api/?name=Ava+Wilson&background=C7CEEA&color=fff", "active": True, "stars": 8, "badges": ["Bookworm"], "books_read": 4},
    ]
    await db.students.insert_many(students)
    
    # Mock books
    books = [
        {"id": str(uuid.uuid4()), "barcode": "BK001", "title": "Harry Potter and the Sorcerer's Stone", "author": "J.K. Rowling", "category": "Fantasy", "cover_image": "https://covers.openlibrary.org/b/id/10521270-M.jpg", "available": 1, "total_copies": 2},
        {"id": str(uuid.uuid4()), "barcode": "BK002", "title": "The Lion, The Witch and The Wardrobe", "author": "C.S. Lewis", "category": "Fantasy", "cover_image": "https://covers.openlibrary.org/b/id/8231682-M.jpg", "available": 2, "total_copies": 2},
        {"id": str(uuid.uuid4()), "barcode": "BK003", "title": "Charlotte's Web", "author": "E.B. White", "category": "Fiction", "cover_image": "https://covers.openlibrary.org/b/id/8235774-M.jpg", "available": 1, "total_copies": 1},
        {"id": str(uuid.uuid4()), "barcode": "BK004", "title": "Wonder", "author": "R.J. Palacio", "category": "Fiction", "cover_image": "https://covers.openlibrary.org/b/id/7894366-M.jpg", "available": 1, "total_copies": 1},
        {"id": str(uuid.uuid4()), "barcode": "BK005", "title": "Percy Jackson: The Lightning Thief", "author": "Rick Riordan", "category": "Adventure", "cover_image": "https://covers.openlibrary.org/b/id/8235664-M.jpg", "available": 0, "total_copies": 1},
        {"id": str(uuid.uuid4()), "barcode": "BK006", "title": "Matilda", "author": "Roald Dahl", "category": "Fiction", "cover_image": "https://covers.openlibrary.org/b/id/8231837-M.jpg", "available": 1, "total_copies": 1},
        {"id": str(uuid.uuid4()), "barcode": "BK007", "title": "The Secret Garden", "author": "Frances Hodgson Burnett", "category": "Classic", "cover_image": "https://covers.openlibrary.org/b/id/8235703-M.jpg", "available": 1, "total_copies": 1},
        {"id": str(uuid.uuid4()), "barcode": "BK008", "title": "Diary of a Wimpy Kid", "author": "Jeff Kinney", "category": "Humor", "cover_image": "https://covers.openlibrary.org/b/id/8235832-M.jpg", "available": 1, "total_copies": 1},
        {"id": str(uuid.uuid4()), "barcode": "BK009", "title": "The Hunger Games", "author": "Suzanne Collins", "category": "Adventure", "cover_image": "https://covers.openlibrary.org/b/id/8235798-M.jpg", "available": 1, "total_copies": 1},
        {"id": str(uuid.uuid4()), "barcode": "BK010", "title": "Alice in Wonderland", "author": "Lewis Carroll", "category": "Fantasy", "cover_image": "https://covers.openlibrary.org/b/id/8235725-M.jpg", "available": 1, "total_copies": 1},
    ]
    await db.books.insert_many(books)
    
    # Add one borrowed book transaction
    transaction = {
        "id": str(uuid.uuid4()),
        "student_barcode": "STU003",
        "student_name": "Olivia Brown",
        "book_barcode": "BK005",
        "book_title": "Percy Jackson: The Lightning Thief",
        "borrow_date": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat(),
        "due_date": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
        "return_date": None,
        "status": "borrowed",
        "overdue_days": 5
    }
    await db.transactions.insert_one(transaction)
    
    # Create admin account (username: admin, password: admin123)
    hashed_password = bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt())
    admin = {
        "id": str(uuid.uuid4()),
        "username": "admin",
        "password": hashed_password.decode('utf-8')
    }
    await db.admins.insert_one(admin)

@app.on_event("startup")
async def startup_event():
    await initialize_mock_data()

# Authentication endpoints
@api_router.post("/auth/student-login")
async def student_login(login: StudentLogin):
    student = await db.students.find_one({"barcode": login.barcode}, {"_id": 0})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"success": True, "student": student}

@api_router.post("/auth/admin-login")
async def admin_login(login: AdminLogin):
    admin = await db.admins.find_one({"username": login.username})
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not bcrypt.checkpw(login.password.encode('utf-8'), admin['password'].encode('utf-8')):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    return {"success": True, "admin": {"username": admin['username']}}

# Student endpoints
@api_router.get("/students", response_model=List[Student])
async def get_students():
    students = await db.students.find({}, {"_id": 0}).to_list(1000)
    return students

@api_router.get("/students/{barcode}")
async def get_student(barcode: str):
    student = await db.students.find_one({"barcode": barcode}, {"_id": 0})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Get borrowed books
    transactions = await db.transactions.find(
        {"student_barcode": barcode, "status": "borrowed"}, 
        {"_id": 0}
    ).to_list(100)
    
    return {"student": student, "borrowed_books": transactions}

@api_router.post("/students")
async def create_student(student: StudentCreate):
    # Check if barcode exists
    existing = await db.students.find_one({"barcode": student.barcode})
    if existing:
        raise HTTPException(status_code=400, detail="Student barcode already exists")
    
    student_dict = student.model_dump()
    if not student_dict.get('profile_pic'):
        student_dict['profile_pic'] = f"https://ui-avatars.com/api/?name={student.name.replace(' ', '+')}&background=random"
    
    student_obj = Student(**student_dict)
    doc = student_obj.model_dump()
    await db.students.insert_one(doc)
    return student_obj

@api_router.put("/students/{barcode}")
async def update_student(barcode: str, student: StudentCreate):
    result = await db.students.update_one(
        {"barcode": barcode},
        {"$set": student.model_dump(exclude_unset=True)}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"success": True}

@api_router.delete("/students/{barcode}")
async def delete_student(barcode: str):
    result = await db.students.delete_one({"barcode": barcode})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"success": True}

# Book endpoints
@api_router.get("/books", response_model=List[Book])
async def get_books():
    books = await db.books.find({}, {"_id": 0}).to_list(1000)
    return books

@api_router.post("/books")
async def create_book(book: BookCreate):
    # Check if barcode exists
    existing = await db.books.find_one({"barcode": book.barcode})
    if existing:
        raise HTTPException(status_code=400, detail="Book barcode already exists")
    
    book_dict = book.model_dump()
    if not book_dict.get('cover_image'):
        book_dict['cover_image'] = "https://via.placeholder.com/150x200/4a90e2/ffffff?text=Book"
    book_dict['available'] = book.total_copies
    
    book_obj = Book(**book_dict)
    doc = book_obj.model_dump()
    await db.books.insert_one(doc)
    return book_obj

@api_router.put("/books/{barcode}")
async def update_book(barcode: str, book: BookCreate):
    result = await db.books.update_one(
        {"barcode": barcode},
        {"$set": book.model_dump(exclude_unset=True)}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Book not found")
    return {"success": True}

@api_router.delete("/books/{barcode}")
async def delete_book(barcode: str):
    result = await db.books.delete_one({"barcode": barcode})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Book not found")
    return {"success": True}

# Transaction endpoints
@api_router.post("/borrow")
async def borrow_book(request: BorrowRequest):
    # Get student
    student = await db.students.find_one({"barcode": request.student_barcode}, {"_id": 0})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Get book
    book = await db.books.find_one({"barcode": request.book_barcode}, {"_id": 0})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    if book['available'] <= 0:
        raise HTTPException(status_code=400, detail="Book is not available")
    
    # Create transaction
    borrow_date = datetime.now(timezone.utc)
    due_date = borrow_date + timedelta(days=15)
    
    transaction = {
        "id": str(uuid.uuid4()),
        "student_barcode": request.student_barcode,
        "student_name": student['name'],
        "book_barcode": request.book_barcode,
        "book_title": book['title'],
        "borrow_date": borrow_date.isoformat(),
        "due_date": due_date.isoformat(),
        "return_date": None,
        "status": "borrowed",
        "overdue_days": 0
    }
    
    await db.transactions.insert_one(transaction)
    
    # Update book availability
    await db.books.update_one(
        {"barcode": request.book_barcode},
        {"$inc": {"available": -1}}
    )
    
    return {"success": True, "message": "Book borrowed successfully!", "transaction": transaction}

@api_router.post("/return")
async def return_book(request: ReturnRequest):
    # Find the transaction
    transaction = await db.transactions.find_one(
        {"book_barcode": request.book_barcode, "student_barcode": request.student_barcode, "status": "borrowed"},
        {"_id": 0}
    )
    
    if not transaction:
        raise HTTPException(status_code=404, detail="No active borrow record found")
    
    # Calculate overdue days
    return_date = datetime.now(timezone.utc)
    due_date = datetime.fromisoformat(transaction['due_date'])
    overdue_days = max(0, (return_date - due_date).days)
    
    # Update transaction
    await db.transactions.update_one(
        {"id": transaction['id']},
        {"$set": {
            "return_date": return_date.isoformat(),
            "status": "returned",
            "overdue_days": overdue_days
        }}
    )
    
    # Update book availability
    await db.books.update_one(
        {"barcode": request.book_barcode},
        {"$inc": {"available": 1}}
    )
    
    # Update student stats
    student = await db.students.find_one({"barcode": request.student_barcode})
    if student:
        # Award stars if returned on time
        new_stars = student.get('stars', 0)
        new_books_read = student.get('books_read', 0) + 1
        new_badges = student.get('badges', [])
        
        if overdue_days == 0:
            new_stars += 2
        
        # Award badges
        if new_books_read >= 5 and "Bookworm" not in new_badges:
            new_badges.append("Bookworm")
        if new_books_read >= 10 and "Speed Reader" not in new_badges:
            new_badges.append("Speed Reader")
        if new_stars >= 20 and "Star Reader" not in new_badges:
            new_badges.append("Star Reader")
        
        await db.students.update_one(
            {"barcode": request.student_barcode},
            {"$set": {"stars": new_stars, "books_read": new_books_read, "badges": new_badges}}
        )
    
    return {
        "success": True, 
        "message": "Book returned successfully!" if overdue_days == 0 else f"Book returned! {overdue_days} days overdue.",
        "overdue_days": overdue_days
    }

@api_router.get("/transactions")
async def get_transactions():
    transactions = await db.transactions.find({}, {"_id": 0}).to_list(1000)
    return transactions

@api_router.get("/overdue")
async def get_overdue_books():
    # Get all borrowed books
    transactions = await db.transactions.find({"status": "borrowed"}, {"_id": 0}).to_list(1000)
    
    overdue_list = []
    current_time = datetime.now(timezone.utc)
    
    for transaction in transactions:
        due_date = datetime.fromisoformat(transaction['due_date'])
        if current_time > due_date:
            overdue_days = (current_time - due_date).days
            transaction['overdue_days'] = overdue_days
            overdue_list.append(transaction)
            
            # Update the transaction in DB
            await db.transactions.update_one(
                {"id": transaction['id']},
                {"$set": {"overdue_days": overdue_days}}
            )
    
    return overdue_list

@api_router.get("/statistics")
async def get_statistics():
    total_books = await db.books.count_documents({})
    total_students = await db.students.count_documents({"active": True})
    borrowed_count = await db.transactions.count_documents({"status": "borrowed"})
    
    # Calculate total available books
    books = await db.books.find({}, {"_id": 0, "available": 1}).to_list(1000)
    total_available = sum(book['available'] for book in books)
    
    # Get overdue count
    overdue_transactions = await db.transactions.find(
        {"status": "borrowed"}, 
        {"_id": 0, "due_date": 1}
    ).to_list(1000)
    
    current_time = datetime.now(timezone.utc)
    overdue_count = sum(
        1 for t in overdue_transactions 
        if datetime.fromisoformat(t['due_date']) < current_time
    )
    
    return {
        "total_books": total_books,
        "total_available": total_available,
        "borrowed_count": borrowed_count,
        "active_students": total_students,
        "overdue_count": overdue_count
    }

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()