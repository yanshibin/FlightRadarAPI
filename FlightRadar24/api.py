# -*- coding: utf-8 -*-

from typing import Any, Dict, List, Optional, Tuple, Union

import dataclasses
import math

from .core import Core
from .entities.airport import Airport
from .entities.flight import Flight
from .errors import LoginError
from .request import APIRequest


@dataclasses.dataclass
class FlightTrackerConfig(object):
    """
    Data class with settings of the Real Time Flight Tracker.
    """
    faa: str = "1"
    satellite: str = "1"
    mlat: str = "1"
    flarm: str = "1"
    adsb: str = "1"
    gnd: str = "1"
    air: str = "1"
    vehicles: str = "1"
    estimated: str = "1"
    maxage: str = "14400"
    gliders: str = "1"
    stats: str = "1"
    limit: str = "5000"


class FlightRadar24API(object):
    """
    Main class of the FlightRadarAPI
    """

    def __init__(self, user: Optional[str] = None, password: Optional[str] = None):
        """
        Constructor of the FlightRadar24API class.

        :param user: Your email (optional)
        :param password: Your password (optional)
        """
        self.__flight_tracker_config = FlightTrackerConfig()
        self.__login_data: Optional[Dict] = None

        if user is not None and password is not None:
            self.login(user, password)

    def get_airlines(self) -> List[Dict]:
        """
        Return a list with all airlines.
        """
        response = APIRequest(Core.airlines_data_url, headers = Core.json_headers)
        return response.get_content()["rows"]

    def get_airline_logo(self, iata: str, icao: str) -> Optional[Tuple[bytes, str]]:
        """
        Download the logo of an airline from FlightRadar24 and return it as bytes.
        """
        first_logo_url = Core.airline_logo_url.format(iata, icao)

        # Try to get the image by the first URL option.
        response = APIRequest(first_logo_url, headers = Core.image_headers, exclude_status_codes=[403,])
        status_code = response.get_status_code()

        if not str(status_code).startswith("4"):
            return response.get_content(), first_logo_url.split(".")[-1]

        # Get the image by the second airline logo URL.
        second_logo_url = Core.alternative_airline_logo_url.format(icao)

        response = APIRequest(second_logo_url, headers = Core.image_headers)
        status_code = response.get_status_code()

        if not str(status_code).startswith("4"):
            return response.get_content(), second_logo_url.split(".")[-1]

    def get_airport(self, code: str) -> Airport:
        """
        Return information about a specific airport.

        :param code: ICAO or IATA of the airport
        """
        response = APIRequest(Core.airport_data_url.format(code), headers = Core.json_headers)
        return Airport(details=response.get_content()["details"])

    def get_airport_details(self, code: str, flight_limit: int = 100, page: int = 1) -> Dict:
        """
        Return the airport details from FlightRadar24.

        :param code: ICAO or IATA of the airport
        :param flight_limit: Limit of flights related to the airport
        :param page: page of result to display
        """
        request_params = {"format": "json"}

        if self.__login_data is not None:
            request_params["token"] = self.__login_data["cookies"]["_frPl"]

        # Insert the method parameters into the dictionary for the request.
        request_params["code"] = code
        request_params["limit"] = flight_limit
        request_params["page"] = page

        # Request details from the FlightRadar24.
        response = APIRequest(Core.api_airport_data_url, request_params, Core.json_headers, exclude_status_codes=[400,])
        content: Dict = response.get_content()

        if response.get_status_code() == 400 and isinstance(content, dict) and content.get("errors"):
            raise ValueError(content["errors"]["errors"]["parameters"]["limit"]["notBetween"])

        return content["result"]["response"]

    def get_airports(self) -> List[Airport]:
        """
        Return a list with all airports.
        """
        response = APIRequest(Core.airports_data_url, headers = Core.json_headers)

        airports: List[Airport] = list()

        for airport_data in response.get_content()["rows"]:
            airport = Airport(info = airport_data)
            airports.append(airport)

        return airports

    def get_bounds(self, zone: Dict[str, float]) -> str:
        """
        Convert coordinate dictionary to a string "y1, y2, x1, x2".

        :param zone: Dictionary containing the following keys: tl_y, tl_x, br_y, br_x
        """
        return "{},{},{},{}".format(zone["tl_y"], zone["br_y"], zone["tl_x"], zone["br_x"])

    def get_bounds_by_point(self, latitude: float, longitude: float, radius: float) -> str:
        """
        Convert a point coordinate and a radius to a string "y1, y2, x1, x2".

        :param latitude: Latitude of the point
        :param longitude: Longitude of the point
        :param radius: Radius in meters to create area around the point
        """
        half_side_in_km = abs(radius) / 1000

        lat = math.radians(latitude)
        lon = math.radians(longitude)

        approx_earth_radius = 6371
        hypotenuse_distance = math.sqrt(2 * (math.pow(half_side_in_km, 2)))

        lat_min = math.asin(
            math.sin(lat) * math.cos(hypotenuse_distance / approx_earth_radius)
            + math.cos(lat)
            * math.sin(hypotenuse_distance / approx_earth_radius)
            * math.cos(225 * (math.pi / 180)),
        )
        lon_min = lon + math.atan2(
            math.sin(225 * (math.pi / 180))
            * math.sin(hypotenuse_distance / approx_earth_radius)
            * math.cos(lat),
            math.cos(hypotenuse_distance / approx_earth_radius)
            - math.sin(lat) * math.sin(lat_min),
        )

        lat_max = math.asin(
            math.sin(lat) * math.cos(hypotenuse_distance / approx_earth_radius)
            + math.cos(lat)
            * math.sin(hypotenuse_distance / approx_earth_radius)
            * math.cos(45 * (math.pi / 180)),
        )
        lon_max = lon + math.atan2(
            math.sin(45 * (math.pi / 180))
            * math.sin(hypotenuse_distance / approx_earth_radius)
            * math.cos(lat),
            math.cos(hypotenuse_distance / approx_earth_radius)
            - math.sin(lat) * math.sin(lat_max),
        )

        rad2deg = math.degrees

        zone = {
            "tl_y": rad2deg(lat_max),
            "br_y": rad2deg(lat_min),
            "tl_x": rad2deg(lon_min),
            "br_x": rad2deg(lon_max)
        }
        return self.get_bounds(zone)

    def get_country_flag(self, country: str) -> Optional[Tuple[bytes, str]]:
        """
        Download the flag of a country from FlightRadar24 and return it as bytes.

        :param country: Country name
        """
        flag_url = Core.country_flag_url.format(country.lower().replace(" ", "-"))
        headers = Core.image_headers.copy()
        
        if "origin" in headers:
            headers.pop("origin")  # Does not work for this request.

        response = APIRequest(flag_url, headers = headers)
        status_code = response.get_status_code()

        if not str(status_code).startswith("4"):
            return response.get_content(), flag_url.split(".")[-1]

    def get_flight_details(self, flight: Union[Flight, str]) -> Dict[Any, Any]:
        """
        Return the flight details from Data Live FlightRadar24.

        :param flight: A Flight instance or the Flight ID (no longer recommended)
        """
        # TODO: Only accept Flight instance at a next version.
        flight_id: str = flight if isinstance(flight, str) else flight.id

        response = APIRequest(Core.flight_data_url.format(flight_id), headers = Core.json_headers)
        return response.get_content()

    def get_flights(
        self,
        airline: Optional[str] = None,
        bounds: Optional[str] = None,
        registration: Optional[str] = None,
        aircraft_type: Optional[str] = None,
        *,
        details: bool = False
    ) -> List[Flight]:
        """
        Return a list of flights. See more options at set_flight_tracker_config() method.

        :param airline: The airline ICAO. Ex: "DAL"
        :param bounds: Coordinates (y1, y2 ,x1, x2). Ex: "75.78,-75.78,-427.56,427.56"
        :param registration: Aircraft registration
        :param aircraft_type: Aircraft model code. Ex: "B737"
        :param details: If True, it returns flights with detailed information
        """
        request_params = dataclasses.asdict(self.__flight_tracker_config)

        if self.__login_data is not None:
            request_params["enc"] = self.__login_data["cookies"]["_frPl"]

        # Insert the method parameters into the dictionary for the request.
        if airline: request_params["airline"] = airline
        if bounds: request_params["bounds"] = bounds.replace(",", "%2C")
        if registration: request_params["reg"] = registration
        if aircraft_type: request_params["type"] = aircraft_type

        # Get all flights from Data Live FlightRadar24.
        response = APIRequest(Core.real_time_flight_tracker_data_url, request_params, Core.json_headers)
        response = response.get_content()

        flights: List[Flight] = list()

        for flight_id, flight_info in response.items():

            # Get flights only.
            if not flight_id[0].isnumeric():
                continue

            flight = Flight(flight_id, flight_info)
            flights.append(flight)

            # Set flight details.
            if details:
                flight_details = self.get_flight_details(flight_id)
                flight.set_flight_details(flight_details)

        return flights

    def get_flight_tracker_config(self) -> FlightTrackerConfig:
        """
        Return a copy of the current config of the Real Time Flight Tracker, used by get_flights() method.
        """
        return dataclasses.replace(self.__flight_tracker_config)

    def get_login_data(self) -> Dict[Any, Any]:
        """
        Return the user data.
        """
        if not self.is_logged_in():
            raise LoginError("You must log in to your account.")

        return self.__login_data["userData"].copy()

    def get_zones(self) -> Dict[str, Dict]:
        """
        Return all major zones on the globe.
        """
        response = APIRequest(Core.zones_data_url, headers = Core.json_headers)
        zones = response.get_content()

        if "version" in zones:
            zones.pop("version")

        return zones

    def search(self, query: str) -> Dict:
        """
        Return the search result
        """
        response = APIRequest(Core.search_data_url.format(query), headers = Core.json_headers)
        results = response.get_content().get("results", [])
        stats = response.get_content().get("stats", {})

        i = 0
        counted_total = 0
        data = {}
        for name, count in stats.get("count", {}).items():
            data[name] = []
            while i < counted_total + count and i < len(results):
                data[name].append(results[i])
                i += 1
            counted_total += count
        return data

    def get_most_tracked(self) -> Dict:
        """
        Return the most tracked data
        """
        response = APIRequest(Core.most_tracked_url, headers = Core.json_headers)
        return response.get_content()

    def is_logged_in(self) -> bool:
        """
        Check if the user is logged into the FlightRadar24 account.
        """
        return self.__login_data is not None

    def login(self, user: str, password: str) -> None:
        """
        Log in to a FlightRadar24 account.

        :param user: Your email.
        :param password: Your password.
        """
        data = {
            "email": user,
            "password": password,
            "remember": "true",
            "type": "web"
        }

        response = APIRequest(Core.user_login_url, headers = Core.json_headers, data = data)
        status_code = response.get_status_code()
        content = response.get_content()

        if not str(status_code).startswith("2") or not content.get("success"):
            if isinstance(content, dict): raise LoginError(content["message"])
            else: raise LoginError("Your email or password is incorrect")

        self.__login_data = {
            "userData": content["userData"],
            "cookies": response.get_cookies(),
        }

    def logout(self) -> bool:
        """
        Log out of the FlightRadar24 account.

        Return a boolean indicating that it successfully logged out of the server.
        """
        if self.__login_data is None: return True

        cookies = self.__login_data["cookies"]
        self.__login_data = None

        response = APIRequest(Core.user_login_url, headers = Core.json_headers, cookies = cookies)
        return str(response.get_status_code()).startswith("2")

    def set_flight_tracker_config(
        self,
        flight_tracker_config: Optional[FlightTrackerConfig] = None,
        **config: Union[int, str]
    ) -> None:
        """
        Set config for the Real Time Flight Tracker, used by get_flights() method.
        """
        if flight_tracker_config is not None:
            self.__flight_tracker_config = flight_tracker_config

        current_config_dict = dataclasses.asdict(self.__flight_tracker_config)

        for key, value in config.items():
            value = str(value)

            if key not in current_config_dict:
                raise KeyError(f"Unknown option: '{key}'")

            if not value.isdecimal():
                raise TypeError(f"Value must be a decimal. Got '{key}'")

            setattr(self.__flight_tracker_config, key, value)
