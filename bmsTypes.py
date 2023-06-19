from pydantic import BaseModel
from typing import List, Union, Optional, Literal

class SubRegion(BaseModel):
    AllowSales: str
    Lat: str
    Long: str
    Seq: str
    SubRegionCode: str
    SubRegionName: str
    SubRegionSlug: str
    GeoHash: str

class City(BaseModel):
    Alias: List[str]
    AllowSales: str
    isOlaEnabled: str
    Lat: str
    Long: str
    RegionCallCenterNo: str
    RegionCode: str
    RegionName: str
    RegionSlug: str
    Seq: str
    HonourSubregionSlug: Union[bool, str]
    GeoHash: str
    SubRegions: List[SubRegion]

class BookMyShowCities(BaseModel):
    TopCities: List[City]
    OtherCities: List[City]

class BMSRegion(BaseModel):
    BookMyShow: BookMyShowCities
    
class ShowDate(BaseModel):
    ShowDateCode: str
    ShowDateDisplay: str

class Venue(BaseModel):
    VenueAddress: str
    CouponIsAllowed: Literal['Y','N']
    RegionCode: str
    CinemaIsNew: Literal['Y','N']
    PostalCode: str
    VenueLongitude: str
    VenueCode: str
    VenueLegends: str
    CinemaCodFlag: Literal['Y','N']
    SubRegionCode: str
    VenueName: str
    City: str
    CinemaUnpaidFlag: Literal['Y','N']
    CinemaCopFlag: Literal['Y','N']
    VenueLatitude: str
    MTicket: Literal['Y','N']
    CinemaAbout: str
    State: str
    VenueType: str
    Country: str
    FoodSales: Literal['Y','N']
    tag: Optional[str]
    isFavourite: bool
    isDown: bool
    CinemaIsOnlineNoTransactionMsg: str
    isRecommended: bool
    Distance: str
    distanceDouble: float
    distanceText: str
    mticket: Literal['Y','N']
    arrDates: List[ShowDate]

class BookMyShowVenues(BaseModel):
    arrVenue: List[Venue]

class BMSVenue(BaseModel):
    BookMyShow: BookMyShowVenues