"""
Pydantic models for Travel Business RAG System
Entities: Customers, Trips, Destinations, Hotels, Bookings, Packages
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import date, datetime


class TripStatus(str, Enum):
    """Trip status states"""
    UPCOMING = "upcoming"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PaymentStatus(str, Enum):
    """Payment status"""
    PENDING = "pending"
    PARTIAL = "partial"
    PAID = "paid"
    REFUNDED = "refunded"


class RoomType(str, Enum):
    """Room types"""
    SINGLE = "single"
    DOUBLE = "double"
    TWIN = "twin"
    FAMILY = "family"
    SUITE = "suite"
    DELUXE = "deluxe"


class Hotel(BaseModel):
    """Hotel entity"""
    name: str = Field(description="Hotel name")
    city: str = Field(description="City where hotel is located")
    address: Optional[str] = None
    phone: Optional[str] = None
    room_type: Optional[str] = None
    amenities: List[str] = Field(default_factory=list)
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None


class Activity(BaseModel):
    """Activity/sightseeing item"""
    name: str = Field(description="Activity or place name")
    time: Optional[str] = None
    duration: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    entry_fee_included: bool = True
    tips: Optional[str] = None


class DayItinerary(BaseModel):
    """Single day itinerary"""
    day_number: int = Field(description="Day number (1, 2, 3...)")
    date: Optional[str] = None
    title: str = Field(description="Day title/description")
    cities: List[str] = Field(default_factory=list)
    hotel: Optional[Hotel] = None
    activities: List[Activity] = Field(default_factory=list)
    meals_included: List[str] = Field(default_factory=list, description="breakfast, lunch, dinner")
    notes: Optional[str] = None


class FlightDetails(BaseModel):
    """Flight information"""
    flight_number: str
    departure_city: str
    departure_airport: str
    departure_time: str
    arrival_city: str
    arrival_airport: str
    arrival_time: str
    duration: Optional[str] = None


class DriverDetails(BaseModel):
    """Driver/transport information"""
    name: str
    phone: str
    vehicle: Optional[str] = None
    vehicle_number: Optional[str] = None


class TripPackage(BaseModel):
    """Travel package details"""
    package_id: str = Field(description="Package code")
    name: str = Field(description="Package name")
    duration_days: int
    duration_nights: int
    destinations: List[str] = Field(default_factory=list)
    price_per_person: float
    single_supplement: Optional[float] = None
    inclusions: List[str] = Field(default_factory=list)
    exclusions: List[str] = Field(default_factory=list)
    best_season: Optional[str] = None
    day_itineraries: List[DayItinerary] = Field(default_factory=list)
    flights: List[FlightDetails] = Field(default_factory=list)


class Booking(BaseModel):
    """Booking entity"""
    booking_id: str = Field(description="Unique booking ID")
    package: Optional[TripPackage] = None
    package_name: Optional[str] = None
    booking_date: Optional[str] = None
    travel_start_date: str
    travel_end_date: str
    num_travelers: int = 1
    travelers: List[str] = Field(default_factory=list)
    room_type: Optional[str] = None
    total_amount: float
    payment_status: PaymentStatus = PaymentStatus.PENDING
    amount_paid: float = 0
    payment_mode: Optional[str] = None


class TripProgress(BaseModel):
    """Current trip progress for active travelers"""
    current_day: int = Field(description="Current day number")
    current_location: str = Field(description="Current city/location")
    current_hotel: Optional[str] = None
    current_activities: List[str] = Field(default_factory=list)
    status: TripStatus = TripStatus.UPCOMING
    completed_days: List[int] = Field(default_factory=list)


class CustomerPreferences(BaseModel):
    """Customer preferences"""
    food_preference: Optional[str] = None  # veg, non-veg, vegan, jain
    special_requirements: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    budget_category: Optional[str] = None  # standard, premium, luxury
    medical_conditions: List[str] = Field(default_factory=list)


class EmergencyContact(BaseModel):
    """Emergency contact details"""
    name: str
    phone: str
    relationship: Optional[str] = None


class Customer(BaseModel):
    """Customer entity"""
    customer_id: str = Field(description="Unique customer ID")
    name: str = Field(description="Full name")
    name_normalized: str = Field(description="Lowercase normalized name")
    phone: str
    email: Optional[str] = None
    address: Optional[str] = None
    dob: Optional[str] = None
    id_proof: Optional[str] = None
    booking: Optional[Booking] = None
    trip_progress: Optional[TripProgress] = None
    preferences: Optional[CustomerPreferences] = None
    emergency_contact: Optional[EmergencyContact] = None
    notes: Optional[str] = None


class Destination(BaseModel):
    """Destination/City information"""
    name: str = Field(description="City/destination name")
    state: Optional[str] = None
    description: Optional[str] = None
    famous_for: List[str] = Field(default_factory=list)
    best_time_to_visit: Optional[str] = None
    local_cuisine: List[str] = Field(default_factory=list)
    attractions: List[str] = Field(default_factory=list)
    tips: List[str] = Field(default_factory=list)


class BusinessSummary(BaseModel):
    """Overall business summary"""
    total_customers: int = 0
    total_bookings: int = 0
    total_travelers: int = 0
    total_revenue: float = 0
    active_trips: int = 0
    upcoming_trips: int = 0
    completed_trips: int = 0
    payment_pending_count: int = 0
    payment_pending_amount: float = 0


class ExtractedEntities(BaseModel):
    """Container for all extracted entities"""
    customers: List[Customer] = Field(default_factory=list)
    packages: List[TripPackage] = Field(default_factory=list)
    destinations: List[Destination] = Field(default_factory=list)
    hotels: List[Hotel] = Field(default_factory=list)
    business_summary: Optional[BusinessSummary] = None
    source_file: str = ""
