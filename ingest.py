"""
Entity Extraction and Ingestion Module for Travel Business
Parses text files and populates the Knowledge Graph
"""
import os
import re
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from models import (
    Customer, Booking, TripProgress, TripPackage, Destination, Hotel,
    BusinessSummary, CustomerPreferences, EmergencyContact,
    TripStatus, PaymentStatus, DayItinerary, Activity, FlightDetails
)
from knowledge_graph import TravelKnowledgeGraph


class TravelEntityExtractor:
    """
    Extracts structured entities from travel data text files.
    Handles customer data and itinerary information.
    """

    def __init__(self):
        self.current_date = "17-December-2024"  # Simulated current date

    def extract_customers_from_text(self, content: str) -> List[Customer]:
        """Extract all customer entities from customers.txt"""
        customers = []

        # Split by customer sections
        customer_sections = re.split(r'={3,}\s*CUSTOMER\s+\d+:', content)

        for section in customer_sections[1:]:  # Skip header
            customer = self._parse_customer_section(section)
            if customer:
                customers.append(customer)

        return customers

    def _parse_customer_section(self, section: str) -> Optional[Customer]:
        """Parse a single customer section"""
        try:
            # Extract basic info
            name = self._extract_field(section, r'Full Name:\s*(.+)')
            customer_id = self._extract_field(section, r'Customer ID:\s*(\w+)')
            phone = self._extract_field(section, r'Phone:\s*([+\d\-\s]+)')
            email = self._extract_field(section, r'Email:\s*([\w\.\-]+@[\w\.\-]+)')
            address = self._extract_field(section, r'Address:\s*(.+)')
            dob = self._extract_field(section, r'Date of Birth:\s*(.+)')
            id_proof = self._extract_field(section, r'ID Proof:\s*(.+)')

            if not name or not customer_id:
                return None

            # Extract booking
            booking = self._extract_booking(section)

            # Extract trip progress
            trip_progress = self._extract_trip_progress(section)

            # Extract preferences
            preferences = self._extract_preferences(section)

            # Extract emergency contact
            emergency_contact = self._extract_emergency_contact(section)

            # Extract notes
            notes = self._extract_notes(section)

            return Customer(
                customer_id=customer_id,
                name=name,
                name_normalized=name.lower().strip(),
                phone=phone or "",
                email=email,
                address=address,
                dob=dob,
                id_proof=id_proof,
                booking=booking,
                trip_progress=trip_progress,
                preferences=preferences,
                emergency_contact=emergency_contact,
                notes=notes
            )

        except Exception as e:
            print(f"Error parsing customer section: {e}")
            return None

    def _extract_booking(self, section: str) -> Optional[Booking]:
        """Extract booking information"""
        booking_id = self._extract_field(section, r'Booking ID:\s*(\S+)')
        if not booking_id:
            return None

        package_name = self._extract_field(section, r'Package:\s*(.+?)(?:\n|Booking Date)')
        booking_date = self._extract_field(section, r'Booking Date:\s*(.+)')
        travel_dates = self._extract_field(section, r'Travel Dates:\s*(.+)')

        # Parse travel dates
        start_date = ""
        end_date = ""
        if travel_dates:
            dates = travel_dates.split(' to ')
            if len(dates) >= 2:
                start_date = dates[0].strip()
                end_date = dates[1].strip()

        num_travelers_match = re.search(r'Number of Travelers:\s*(\d+)', section)
        num_travelers = int(num_travelers_match.group(1)) if num_travelers_match else 1

        # Extract travelers list
        travelers_match = re.search(r'\((.+?)\)', section[section.find('Number of Travelers'):] if 'Number of Travelers' in section else "")
        travelers = []
        if travelers_match:
            travelers_text = travelers_match.group(1)
            if 'with' in travelers_text.lower():
                travelers = [t.strip() for t in re.split(r',|and', travelers_text.replace('with', '').strip())]

        room_type = self._extract_field(section, r'Room Type:\s*(.+)')

        # Extract amounts
        total_match = re.search(r'Total Amount:\s*Rs\s*([\d,]+)', section)
        total_amount = float(total_match.group(1).replace(',', '')) if total_match else 0

        payment_status_str = self._extract_field(section, r'Payment Status:\s*(\w+)')
        payment_status = PaymentStatus.PAID
        amount_paid = total_amount

        if payment_status_str:
            if 'partial' in payment_status_str.lower():
                payment_status = PaymentStatus.PARTIAL
                # Extract amount paid
                paid_match = re.search(r'Rs\s*([\d,]+)\s*paid', section)
                if paid_match:
                    amount_paid = float(paid_match.group(1).replace(',', ''))
            elif 'pending' in payment_status_str.lower():
                payment_status = PaymentStatus.PENDING
                amount_paid = 0

        payment_mode = self._extract_field(section, r'Payment Mode:\s*(.+)')

        return Booking(
            booking_id=booking_id,
            package_name=package_name,
            booking_date=booking_date,
            travel_start_date=start_date,
            travel_end_date=end_date,
            num_travelers=num_travelers,
            travelers=travelers,
            room_type=room_type,
            total_amount=total_amount,
            payment_status=payment_status,
            amount_paid=amount_paid,
            payment_mode=payment_mode
        )

    def _extract_trip_progress(self, section: str) -> Optional[TripProgress]:
        """Extract current trip progress"""
        # Check trip status section
        status_section = section

        current_day_match = re.search(r'Current Day:\s*(?:Day\s*)?(\d+)', status_section)
        if not current_day_match:
            # Check if trip hasn't started
            if 'Not Started' in section or 'Upcoming' in section:
                return TripProgress(
                    current_day=0,
                    current_location="Not Started",
                    status=TripStatus.UPCOMING
                )
            return None

        current_day = int(current_day_match.group(1))
        current_location = self._extract_field(section, r'Current Location:\s*(.+)')
        current_hotel = self._extract_field(section, r'Current Hotel:\s*(.+)')

        # Extract today's activities
        activities = []
        activities_match = re.search(r"Today's Activities:(.*?)(?:\n\n|\nITINERARY|\nPREFERENCES)", section, re.DOTALL)
        if activities_match:
            activity_lines = activities_match.group(1).strip().split('\n')
            for line in activity_lines:
                line = line.strip().lstrip('- ')
                if line:
                    activities.append(line)

        # Determine status
        status = TripStatus.IN_PROGRESS
        if 'DEPARTURE' in section or 'Last Day' in section:
            status = TripStatus.COMPLETED
        elif 'Not Started' in section:
            status = TripStatus.UPCOMING

        # Extract completed days from itinerary
        completed_days = []
        for i in range(1, current_day):
            if f'Day {i}' in section and '[COMPLETED]' in section:
                completed_days.append(i)

        return TripProgress(
            current_day=current_day,
            current_location=current_location or "",
            current_hotel=current_hotel,
            current_activities=activities,
            status=status,
            completed_days=completed_days
        )

    def _extract_preferences(self, section: str) -> Optional[CustomerPreferences]:
        """Extract customer preferences"""
        prefs_match = re.search(r'PREFERENCES\s*-+\s*(.*?)(?:\n\n[A-Z]|\nEMERGENCY)', section, re.DOTALL)
        if not prefs_match:
            return None

        prefs_text = prefs_match.group(1)
        lines = [l.strip().lstrip('- ') for l in prefs_text.split('\n') if l.strip() and l.strip().startswith('-')]

        food_preference = None
        special_requirements = []
        interests = []
        budget = None

        for line in lines:
            line_lower = line.lower()
            if 'vegetarian' in line_lower or 'non-veg' in line_lower or 'vegan' in line_lower or 'food' in line_lower:
                food_preference = line
            elif 'budget' in line_lower:
                budget = line.split(':')[-1].strip() if ':' in line else line
            elif 'interest' in line_lower or 'photography' in line_lower or 'shopping' in line_lower:
                interests.append(line)
            else:
                special_requirements.append(line)

        return CustomerPreferences(
            food_preference=food_preference,
            special_requirements=special_requirements,
            interests=interests,
            budget_category=budget
        )

    def _extract_emergency_contact(self, section: str) -> Optional[EmergencyContact]:
        """Extract emergency contact"""
        ec_match = re.search(r'EMERGENCY CONTACT\s*-+\s*(.*?)(?:\n\n[A-Z]|\nNOTES)', section, re.DOTALL)
        if not ec_match:
            return None

        ec_text = ec_match.group(1)
        name = self._extract_field(ec_text, r'Name:\s*(.+?)(?:\(|\n)')
        phone = self._extract_field(ec_text, r'Phone:\s*([+\d\-\s]+)')
        relationship = None

        rel_match = re.search(r'\(([^)]+)\)', ec_text)
        if rel_match:
            relationship = rel_match.group(1)

        if name and phone:
            return EmergencyContact(
                name=name.strip(),
                phone=phone.strip(),
                relationship=relationship
            )
        return None

    def _extract_notes(self, section: str) -> Optional[str]:
        """Extract notes section"""
        notes_match = re.search(r'NOTES\s*-+\s*(.*?)(?:\n={3,}|\Z)', section, re.DOTALL)
        if notes_match:
            notes_lines = [l.strip().lstrip('- ') for l in notes_match.group(1).split('\n') if l.strip().startswith('-')]
            if notes_lines:
                return '; '.join(notes_lines)
        return None

    def _extract_field(self, text: str, pattern: str) -> Optional[str]:
        """Extract a field using regex pattern"""
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    def extract_itinerary_from_text(self, content: str) -> Optional[TripPackage]:
        """Extract trip package from itinerary text file"""
        try:
            # Extract package info
            package_name = self._extract_field(content, r'^(.+?TOUR.*?)$') or "Rajasthan Royal Heritage Tour"
            duration_match = re.search(r'(\d+)\s*Days?\s*/\s*(\d+)\s*Nights?', content, re.IGNORECASE)
            days = int(duration_match.group(1)) if duration_match else 8
            nights = int(duration_match.group(2)) if duration_match else 7

            # Extract price
            price_match = re.search(r'Package Price:\s*Rs\s*([\d,]+)', content)
            price = float(price_match.group(1).replace(',', '')) if price_match else 45000

            single_supp_match = re.search(r'Single Supplement:\s*Rs\s*([\d,]+)', content)
            single_supp = float(single_supp_match.group(1).replace(',', '')) if single_supp_match else 12000

            # Extract inclusions
            inclusions = self._extract_list_section(content, 'INCLUSIONS')
            exclusions = self._extract_list_section(content, 'EXCLUSIONS')

            # Extract destinations
            destinations = ['Jaipur', 'Pushkar', 'Jodhpur', 'Udaipur']

            # Extract day itineraries
            day_itineraries = self._extract_day_itineraries(content)

            # Extract flights
            flights = self._extract_flights(content)

            return TripPackage(
                package_id="RAJ-HERITAGE-2024",
                name=package_name,
                duration_days=days,
                duration_nights=nights,
                destinations=destinations,
                price_per_person=price,
                single_supplement=single_supp,
                inclusions=inclusions,
                exclusions=exclusions,
                best_season="October to March",
                day_itineraries=day_itineraries,
                flights=flights
            )

        except Exception as e:
            print(f"Error extracting itinerary: {e}")
            return None

    def _extract_list_section(self, content: str, section_name: str) -> List[str]:
        """Extract a list section"""
        pattern = rf'{section_name}\s*-+\s*(.*?)(?:\n\n[A-Z]|={3,})'
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            lines = match.group(1).strip().split('\n')
            return [l.strip().lstrip('- ') for l in lines if l.strip().startswith('-')]
        return []

    def _extract_day_itineraries(self, content: str) -> List[DayItinerary]:
        """Extract daily itineraries"""
        days = []

        # Find all DAY sections
        day_pattern = r'DAY\s*(\d+):\s*(.+?)\n={3,}(.*?)(?=\n={3,}\s*DAY|\n={3,}\s*IMPORTANT|\Z)'
        matches = re.findall(day_pattern, content, re.DOTALL)

        for match in matches:
            day_num = int(match[0])
            title = match[1].strip()
            day_content = match[2]

            # Extract activities
            activities = []
            time_pattern = r'(\d{1,2}:\d{2}\s*(?:AM|PM))\s*-\s*(.+?)(?=\n\d{1,2}:\d{2}|\n\n|\Z)'
            activity_matches = re.findall(time_pattern, day_content, re.DOTALL)

            for time, desc in activity_matches:
                activities.append(Activity(
                    name=desc.split('\n')[0].strip(),
                    time=time.strip(),
                    description=desc.strip()
                ))

            # Extract hotel
            hotel_name = self._extract_field(day_content, r'Hotel:\s*(.+)')
            hotel = Hotel(name=hotel_name, city=title.split('-')[-1].strip() if '-' in title else "") if hotel_name else None

            days.append(DayItinerary(
                day_number=day_num,
                title=title,
                hotel=hotel,
                activities=activities
            ))

        return days

    def _extract_flights(self, content: str) -> List[FlightDetails]:
        """Extract flight details"""
        flights = []

        flight_pattern = r'Flight:\s*(\S+).*?Departure:\s*(.+?)\s+at\s+(\S+).*?Arrival:\s*(.+?)\s+at\s+(\S+)'
        matches = re.findall(flight_pattern, content, re.DOTALL)

        for match in matches:
            flights.append(FlightDetails(
                flight_number=match[0],
                departure_city=match[1].split('(')[0].strip(),
                departure_airport=match[1],
                departure_time=match[2],
                arrival_city=match[3].split('(')[0].strip(),
                arrival_airport=match[3],
                arrival_time=match[4]
            ))

        return flights

    def extract_destinations(self, content: str) -> List[Destination]:
        """Extract destination information"""
        destinations = []

        dest_pattern = r'([A-Z]+)\s*-\s*THE\s+(.+?)\n-+\n(.*?)(?=\n[A-Z]+\s*-\s*THE|\n={3,}|\Z)'
        matches = re.findall(dest_pattern, content, re.DOTALL)

        for match in matches:
            name = match[0].strip().title()
            title = match[1].strip()
            desc_content = match[2]

            famous_for_match = re.search(r'Famous For:\s*(.+?)(?:\n[A-Z]|\Z)', desc_content)
            famous_for = [f.strip() for f in famous_for_match.group(1).split(',')] if famous_for_match else []

            cuisine_match = re.search(r'Local Cuisine:\s*(.+?)(?:\n[A-Z]|\Z)', desc_content)
            cuisine = [c.strip() for c in cuisine_match.group(1).split(',')] if cuisine_match else []

            destinations.append(Destination(
                name=name,
                state="Rajasthan",
                description=f"The {title}",
                famous_for=famous_for,
                local_cuisine=cuisine
            ))

        # Default destinations if not found
        if not destinations:
            destinations = [
                Destination(name="Jaipur", state="Rajasthan", description="The Pink City",
                           famous_for=["Pink buildings", "Forts", "Palaces"],
                           local_cuisine=["Dal Baati Churma", "Ghewar"]),
                Destination(name="Pushkar", state="Rajasthan", description="The Sacred Town",
                           famous_for=["Brahma Temple", "Pushkar Lake"],
                           local_cuisine=["Malpua", "Vegetarian food"]),
                Destination(name="Jodhpur", state="Rajasthan", description="The Blue City",
                           famous_for=["Mehrangarh Fort", "Blue houses"],
                           local_cuisine=["Mirchi Bada", "Makhaniya Lassi"]),
                Destination(name="Udaipur", state="Rajasthan", description="The City of Lakes",
                           famous_for=["Lake Pichola", "City Palace"],
                           local_cuisine=["Dal Baati", "Gatte ki Sabzi"])
            ]

        return destinations

    def extract_hotels(self, content: str) -> List[Hotel]:
        """Extract hotel information"""
        hotels = []

        hotel_pattern = r'Hotel:\s*(.+?)\nAddress:\s*(.+?)(?:\nPhone:\s*([+\d\-\s]+))?'
        matches = re.findall(hotel_pattern, content)

        for match in matches:
            name = match[0].strip()
            address = match[1].strip()
            phone = match[2].strip() if len(match) > 2 and match[2] else None

            # Determine city from address or context
            city = ""
            for dest in ["Jaipur", "Pushkar", "Jodhpur", "Udaipur"]:
                if dest.lower() in address.lower():
                    city = dest
                    break

            if name and name not in [h.name for h in hotels]:
                hotels.append(Hotel(
                    name=name,
                    city=city,
                    address=address,
                    phone=phone
                ))

        return hotels


class TravelDataIngester:
    """
    Ingests data from text files into the Knowledge Graph
    """

    def __init__(self, knowledge_graph: TravelKnowledgeGraph):
        self.kg = knowledge_graph
        self.extractor = TravelEntityExtractor()

    def ingest_customer_file(self, file_path: str) -> Tuple[int, int]:
        """
        Ingest customer data from text file.
        Returns (success_count, error_count)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            customers = self.extractor.extract_customers_from_text(content)

            success = 0
            errors = 0

            for customer in customers:
                try:
                    self.kg.add_customer(customer)
                    success += 1
                    print(f"  Ingested customer: {customer.name}")
                except Exception as e:
                    errors += 1
                    print(f"  Failed to add customer: {e}")

            return success, errors

        except Exception as e:
            print(f"Error reading customer file: {e}")
            return 0, 1

    def ingest_itinerary_file(self, file_path: str) -> bool:
        """Ingest itinerary/package data from text file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract package
            package = self.extractor.extract_itinerary_from_text(content)
            if package:
                self.kg.add_package(package)
                print(f"  Ingested package: {package.name}")

            # Extract destinations
            destinations = self.extractor.extract_destinations(content)
            for dest in destinations:
                self.kg.add_destination(dest)
                print(f"  Ingested destination: {dest.name}")

            # Extract hotels
            hotels = self.extractor.extract_hotels(content)
            for hotel in hotels:
                self.kg.add_hotel(hotel)
                print(f"  Ingested hotel: {hotel.name}")

            return True

        except Exception as e:
            print(f"Error reading itinerary file: {e}")
            return False

    def compute_business_summary(self) -> BusinessSummary:
        """Compute and set business summary from all customers"""
        total_revenue = 0.0
        total_travelers = 0
        active_trips = 0
        upcoming_trips = 0
        completed_trips = 0
        payment_pending_count = 0
        payment_pending_amount = 0.0

        for node_id in self.kg.customer_index.values():
            customer_data = self.kg._get_customer_data(node_id)

            booking = customer_data.get("booking")
            if booking:
                total_revenue += booking.get("total_amount", 0)
                total_travelers += booking.get("num_travelers", 1)

                if booking.get("payment_status") in ["partial", "pending"]:
                    payment_pending_count += 1
                    payment_pending_amount += booking.get("total_amount", 0) - booking.get("amount_paid", 0)

            trip_progress = customer_data.get("trip_progress")
            if trip_progress:
                status = trip_progress.get("status", "")
                if status == "in_progress":
                    active_trips += 1
                elif status == "upcoming":
                    upcoming_trips += 1
                elif status == "completed":
                    completed_trips += 1

        total_customers = len(self.kg.get_all_customers())

        summary = BusinessSummary(
            total_customers=total_customers,
            total_bookings=total_customers,  # 1:1 in this case
            total_travelers=total_travelers,
            total_revenue=total_revenue,
            active_trips=active_trips,
            upcoming_trips=upcoming_trips,
            completed_trips=completed_trips,
            payment_pending_count=payment_pending_count,
            payment_pending_amount=payment_pending_amount
        )

        self.kg.set_business_summary(summary)
        return summary

    def ingest_all(self, data_dir: str) -> dict:
        """
        Complete ingestion pipeline.
        Returns statistics about the ingestion.
        """
        print(f"\n=== Starting Travel Data Ingestion ===")
        print(f"Source: {data_dir}")

        customer_success = 0
        customer_errors = 0
        itinerary_success = False

        # Ingest customer data
        customer_file = os.path.join(data_dir, "customers.txt")
        if os.path.exists(customer_file):
            print(f"\n[1/2] Ingesting customers from {customer_file}...")
            success, errors = self.ingest_customer_file(customer_file)
            customer_success = success
            customer_errors = errors

        # Ingest itinerary data
        itinerary_file = os.path.join(data_dir, "rajasthan_trip_itinerary.txt")
        if os.path.exists(itinerary_file):
            print(f"\n[2/2] Ingesting itinerary from {itinerary_file}...")
            itinerary_success = self.ingest_itinerary_file(itinerary_file)

        # Also check for any .txt files
        for filename in os.listdir(data_dir):
            if filename.endswith('.txt') and filename not in ["customers.txt", "rajasthan_trip_itinerary.txt"]:
                file_path = os.path.join(data_dir, filename)
                print(f"\n[Extra] Processing {filename}...")
                self.ingest_itinerary_file(file_path)

        # Compute summary
        summary = self.compute_business_summary()

        # Get stats
        stats = self.kg.stats()

        result = {
            "customers_ingested": customer_success,
            "customers_failed": customer_errors,
            "itinerary_ingested": itinerary_success,
            "total_revenue": summary.total_revenue,
            "total_travelers": summary.total_travelers,
            "active_trips": summary.active_trips,
            "upcoming_trips": summary.upcoming_trips,
            "graph_stats": stats
        }

        print(f"\n=== Ingestion Complete ===")
        print(f"Customers: {customer_success} success, {customer_errors} failed")
        print(f"Total Revenue: Rs {summary.total_revenue:,.0f}")
        print(f"Active Trips: {summary.active_trips}")
        print(f"Upcoming Trips: {summary.upcoming_trips}")
        print(f"Graph: {stats['total_nodes']} nodes, {stats['total_edges']} edges")

        return result


# Convenience function
def create_knowledge_graph(data_dir: str) -> TravelKnowledgeGraph:
    """Create and populate a knowledge graph from travel data"""
    kg = TravelKnowledgeGraph()
    ingester = TravelDataIngester(kg)
    ingester.ingest_all(data_dir)
    return kg


if __name__ == "__main__":
    import sys

    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data"

    kg = create_knowledge_graph(data_dir)

    # Test queries
    print("\n=== Testing Queries ===")

    # Test find customer
    test_names = ["amit", "sneha", "vikram singh"]
    for name in test_names:
        result = kg.find_customer(name)
        if result:
            print(f"\nFound '{name}': {result['name']}")
            if result.get('booking'):
                print(f"  Booking: {result['booking'].get('booking_id')}")
            if result.get('trip_progress'):
                print(f"  Status: {result['trip_progress'].get('status')}")
                print(f"  Location: {result['trip_progress'].get('current_location')}")
        else:
            print(f"\nNot found: '{name}'")

    # Test active travelers
    print("\n=== Active Travelers ===")
    active = kg.get_active_travelers()
    for traveler in active:
        print(f"  {traveler['name']} - Day {traveler.get('trip_progress', {}).get('current_day')} at {traveler.get('trip_progress', {}).get('current_location')}")
