"""
Knowledge Graph using NetworkX for Travel Business
Entities: Customers, Trips, Destinations, Hotels, Bookings, Packages
"""
import networkx as nx
from typing import Dict, List, Optional, Any
from models import (
    Customer, TripPackage, Destination, Hotel, Booking,
    TripProgress, BusinessSummary, TripStatus
)
from difflib import SequenceMatcher
import re


class TravelKnowledgeGraph:
    """
    In-memory knowledge graph for travel entities.
    Stores customers, bookings, packages, destinations, and hotels as nodes with relationships.
    """

    def __init__(self):
        self.graph = nx.DiGraph()
        self.customer_index: Dict[str, str] = {}  # normalized_name -> node_id
        self.customer_phone_index: Dict[str, str] = {}  # phone -> node_id
        self.name_variations: Dict[str, str] = {}  # variations -> canonical name
        self.destination_index: Dict[str, str] = {}  # city_name -> node_id
        self.package_index: Dict[str, str] = {}  # package_id -> node_id
        self.hotel_index: Dict[str, str] = {}  # hotel_name -> node_id
        self.business_summary: Optional[BusinessSummary] = None

    def add_customer(self, customer: Customer) -> str:
        """Add a customer node to the graph"""
        node_id = f"customer:{customer.customer_id}"

        self.graph.add_node(
            node_id,
            type="customer",
            customer_id=customer.customer_id,
            name=customer.name,
            name_normalized=customer.name_normalized,
            phone=customer.phone,
            email=customer.email,
            address=customer.address,
            notes=customer.notes
        )

        # Index for fast lookup
        self.customer_index[customer.name_normalized] = node_id
        if customer.phone:
            # Normalize phone number
            normalized_phone = re.sub(r'[^0-9]', '', customer.phone)[-10:]
            self.customer_phone_index[normalized_phone] = node_id

        # Add name variations for fuzzy matching
        self._index_name_variations(customer.name, customer.name_normalized)

        # Add booking if exists
        if customer.booking:
            booking_id = self.add_booking(customer.booking, node_id)
            self.graph.add_edge(node_id, booking_id, relation="HAS_BOOKING")

        # Add trip progress if exists
        if customer.trip_progress:
            progress_id = self.add_trip_progress(customer.trip_progress, node_id)
            self.graph.add_edge(node_id, progress_id, relation="HAS_TRIP_PROGRESS")

        # Add preferences if exists
        if customer.preferences:
            self.graph.nodes[node_id]["preferences"] = customer.preferences.model_dump()

        # Add emergency contact if exists
        if customer.emergency_contact:
            self.graph.nodes[node_id]["emergency_contact"] = customer.emergency_contact.model_dump()

        return node_id

    def _index_name_variations(self, name: str, normalized: str):
        """Index various forms of the name for fuzzy matching"""
        self.name_variations[normalized] = normalized

        parts = name.split()
        if parts:
            # First name only
            self.name_variations[parts[0].lower()] = normalized

        if len(parts) >= 2:
            # First + Last name
            self.name_variations[f"{parts[0].lower()} {parts[-1].lower()}"] = normalized

        # Handle customer ID lookup
        if normalized.startswith("cust"):
            self.name_variations[normalized] = normalized

    def add_booking(self, booking: Booking, customer_id: str) -> str:
        """Add a booking node connected to a customer"""
        booking_id = f"booking:{booking.booking_id}"

        self.graph.add_node(
            booking_id,
            type="booking",
            booking_id=booking.booking_id,
            package_name=booking.package_name,
            booking_date=booking.booking_date,
            travel_start_date=booking.travel_start_date,
            travel_end_date=booking.travel_end_date,
            num_travelers=booking.num_travelers,
            travelers=booking.travelers,
            room_type=booking.room_type,
            total_amount=booking.total_amount,
            payment_status=booking.payment_status.value,
            amount_paid=booking.amount_paid,
            payment_mode=booking.payment_mode
        )

        return booking_id

    def add_trip_progress(self, progress: TripProgress, customer_id: str) -> str:
        """Add trip progress node"""
        progress_id = f"progress:{customer_id}"

        self.graph.add_node(
            progress_id,
            type="trip_progress",
            current_day=progress.current_day,
            current_location=progress.current_location,
            current_hotel=progress.current_hotel,
            current_activities=progress.current_activities,
            status=progress.status.value,
            completed_days=progress.completed_days
        )

        return progress_id

    def add_destination(self, destination: Destination) -> str:
        """Add a destination node"""
        node_id = f"destination:{destination.name.lower().replace(' ', '_')}"

        self.graph.add_node(
            node_id,
            type="destination",
            name=destination.name,
            state=destination.state,
            description=destination.description,
            famous_for=destination.famous_for,
            best_time_to_visit=destination.best_time_to_visit,
            local_cuisine=destination.local_cuisine,
            attractions=destination.attractions,
            tips=destination.tips
        )

        self.destination_index[destination.name.lower()] = node_id
        return node_id

    def add_package(self, package: TripPackage) -> str:
        """Add a package node"""
        node_id = f"package:{package.package_id}"

        self.graph.add_node(
            node_id,
            type="package",
            package_id=package.package_id,
            name=package.name,
            duration_days=package.duration_days,
            duration_nights=package.duration_nights,
            destinations=package.destinations,
            price_per_person=package.price_per_person,
            single_supplement=package.single_supplement,
            inclusions=package.inclusions,
            exclusions=package.exclusions,
            best_season=package.best_season
        )

        self.package_index[package.package_id] = node_id

        # Link package to destinations
        for dest_name in package.destinations:
            dest_normalized = dest_name.lower()
            if dest_normalized in self.destination_index:
                dest_id = self.destination_index[dest_normalized]
                self.graph.add_edge(node_id, dest_id, relation="INCLUDES_DESTINATION")

        return node_id

    def add_hotel(self, hotel: Hotel) -> str:
        """Add a hotel node"""
        node_id = f"hotel:{hotel.name.lower().replace(' ', '_')}"

        self.graph.add_node(
            node_id,
            type="hotel",
            name=hotel.name,
            city=hotel.city,
            address=hotel.address,
            phone=hotel.phone,
            room_type=hotel.room_type,
            amenities=hotel.amenities,
            check_in_time=hotel.check_in_time,
            check_out_time=hotel.check_out_time
        )

        self.hotel_index[hotel.name.lower()] = node_id

        # Link hotel to destination/city
        city_normalized = hotel.city.lower()
        if city_normalized in self.destination_index:
            dest_id = self.destination_index[city_normalized]
            self.graph.add_edge(node_id, dest_id, relation="LOCATED_IN")

        return node_id

    def set_business_summary(self, summary: BusinessSummary):
        """Set the overall business summary"""
        self.business_summary = summary

        self.graph.add_node(
            "business:summary",
            type="business_summary",
            total_customers=summary.total_customers,
            total_bookings=summary.total_bookings,
            total_travelers=summary.total_travelers,
            total_revenue=summary.total_revenue,
            active_trips=summary.active_trips,
            upcoming_trips=summary.upcoming_trips,
            completed_trips=summary.completed_trips,
            payment_pending_count=summary.payment_pending_count,
            payment_pending_amount=summary.payment_pending_amount
        )

    def find_customer(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Find a customer by name or phone using fuzzy matching.
        Returns customer data with booking and trip progress if found.
        """
        query_normalized = query.lower().strip()

        # Try phone lookup first (if query looks like a phone number)
        if re.match(r'^[\d\s\-\+]+$', query):
            normalized_phone = re.sub(r'[^0-9]', '', query)[-10:]
            if normalized_phone in self.customer_phone_index:
                return self._get_customer_data(self.customer_phone_index[normalized_phone])

        # Exact match on normalized name
        if query_normalized in self.customer_index:
            return self._get_customer_data(self.customer_index[query_normalized])

        # Check name variations
        if query_normalized in self.name_variations:
            canonical = self.name_variations[query_normalized]
            if canonical in self.customer_index:
                return self._get_customer_data(self.customer_index[canonical])

        # Fuzzy match on all variations
        best_match = None
        best_score = 0.0

        for variation, canonical in self.name_variations.items():
            score = SequenceMatcher(None, query_normalized, variation).ratio()
            if score > best_score and score > 0.6:
                best_score = score
                best_match = canonical

        if best_match and best_match in self.customer_index:
            return self._get_customer_data(self.customer_index[best_match])

        # Partial match on full names
        for normalized, node_id in self.customer_index.items():
            if query_normalized in normalized or normalized in query_normalized:
                return self._get_customer_data(node_id)

        return None

    def _get_customer_data(self, node_id: str) -> Dict[str, Any]:
        """Get full customer data including booking and trip progress"""
        customer_data = dict(self.graph.nodes[node_id])
        customer_data["node_id"] = node_id

        # Get booking
        for _, target, data in self.graph.out_edges(node_id, data=True):
            if data.get("relation") == "HAS_BOOKING":
                customer_data["booking"] = dict(self.graph.nodes[target])

            if data.get("relation") == "HAS_TRIP_PROGRESS":
                customer_data["trip_progress"] = dict(self.graph.nodes[target])

        return customer_data

    def get_customer_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Find customer by phone number"""
        normalized_phone = re.sub(r'[^0-9]', '', phone)[-10:]
        if normalized_phone in self.customer_phone_index:
            return self._get_customer_data(self.customer_phone_index[normalized_phone])
        return None

    def get_business_summary(self) -> Optional[Dict[str, Any]]:
        """Get the business summary"""
        if self.business_summary:
            return {
                "total_customers": self.business_summary.total_customers,
                "total_bookings": self.business_summary.total_bookings,
                "total_travelers": self.business_summary.total_travelers,
                "total_revenue": self.business_summary.total_revenue,
                "active_trips": self.business_summary.active_trips,
                "upcoming_trips": self.business_summary.upcoming_trips,
                "completed_trips": self.business_summary.completed_trips,
                "payment_pending_count": self.business_summary.payment_pending_count,
                "payment_pending_amount": self.business_summary.payment_pending_amount
            }
        return None

    def get_all_customers(self) -> List[str]:
        """Get list of all customer names"""
        return [
            self.graph.nodes[node_id]["name"]
            for node_id in self.customer_index.values()
        ]

    def get_active_travelers(self) -> List[Dict[str, Any]]:
        """Get customers who are currently traveling"""
        active = []
        for node_id in self.customer_index.values():
            customer_data = self._get_customer_data(node_id)
            trip_progress = customer_data.get("trip_progress")
            if trip_progress and trip_progress.get("status") == "in_progress":
                active.append(customer_data)
        return active

    def get_upcoming_travelers(self) -> List[Dict[str, Any]]:
        """Get customers with upcoming trips"""
        upcoming = []
        for node_id in self.customer_index.values():
            customer_data = self._get_customer_data(node_id)
            trip_progress = customer_data.get("trip_progress")
            if trip_progress and trip_progress.get("status") == "upcoming":
                upcoming.append(customer_data)
        return upcoming

    def get_customers_at_destination(self, destination: str) -> List[Dict[str, Any]]:
        """Get all customers currently at a specific destination"""
        dest_lower = destination.lower()
        customers = []

        for node_id in self.customer_index.values():
            customer_data = self._get_customer_data(node_id)
            trip_progress = customer_data.get("trip_progress")
            if trip_progress:
                current_location = (trip_progress.get("current_location") or "").lower()
                if dest_lower in current_location or current_location in dest_lower:
                    customers.append(customer_data)

        return customers

    def get_destination_info(self, destination: str) -> Optional[Dict[str, Any]]:
        """Get destination information"""
        dest_lower = destination.lower()

        # Exact match
        if dest_lower in self.destination_index:
            return dict(self.graph.nodes[self.destination_index[dest_lower]])

        # Partial match
        for name, node_id in self.destination_index.items():
            if dest_lower in name or name in dest_lower:
                return dict(self.graph.nodes[node_id])

        return None

    def get_hotel_info(self, hotel_name: str) -> Optional[Dict[str, Any]]:
        """Get hotel information"""
        hotel_lower = hotel_name.lower()

        # Exact match
        if hotel_lower in self.hotel_index:
            return dict(self.graph.nodes[self.hotel_index[hotel_lower]])

        # Partial match
        for name, node_id in self.hotel_index.items():
            if hotel_lower in name or name in hotel_lower:
                return dict(self.graph.nodes[node_id])

        return None

    def get_package_info(self, package_id: str) -> Optional[Dict[str, Any]]:
        """Get package information"""
        if package_id in self.package_index:
            return dict(self.graph.nodes[self.package_index[package_id]])
        return None

    def search_customers_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Find all customers with specific trip status"""
        status_lower = status.lower()
        customers = []

        for node_id in self.customer_index.values():
            customer_data = self._get_customer_data(node_id)
            trip_progress = customer_data.get("trip_progress")
            if trip_progress:
                trip_status = (trip_progress.get("status") or "").lower()
                if status_lower in trip_status:
                    customers.append(customer_data)

        return customers

    def get_customers_by_day(self, day_number: int) -> List[Dict[str, Any]]:
        """Get customers currently on a specific day of their trip"""
        customers = []

        for node_id in self.customer_index.values():
            customer_data = self._get_customer_data(node_id)
            trip_progress = customer_data.get("trip_progress")
            if trip_progress and trip_progress.get("current_day") == day_number:
                customers.append(customer_data)

        return customers

    def to_dict(self) -> Dict:
        """Serialize graph to dict for storage"""
        return {
            "nodes": dict(self.graph.nodes(data=True)),
            "edges": list(self.graph.edges(data=True)),
            "customer_index": self.customer_index,
            "destination_index": self.destination_index,
            "package_index": self.package_index,
            "hotel_index": self.hotel_index,
            "business_summary": self.business_summary.model_dump() if self.business_summary else None
        }

    def stats(self) -> Dict[str, int]:
        """Get graph statistics"""
        node_types = {}
        for _, data in self.graph.nodes(data=True):
            t = data.get("type", "unknown")
            node_types[t] = node_types.get(t, 0) + 1

        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "customers": node_types.get("customer", 0),
            "bookings": node_types.get("booking", 0),
            "destinations": node_types.get("destination", 0),
            "hotels": node_types.get("hotel", 0),
            "packages": node_types.get("package", 0),
            "trip_progress": node_types.get("trip_progress", 0)
        }
