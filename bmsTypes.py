from pydantic import BaseModel
from typing import List, Union, Optional, Literal, Dict

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
    
# Shows
class Category(BaseModel):
    PriceCode: str
    AdditionalData: str
    CurPrice: str
    UpdatedPrice: str
    AreaCatCode: str
    AvailStatus: str
    BestAvailableSeats: str
    SeatLayout: str
    PriceDesc: str
    CategoryRange: str

class ShowTime(BaseModel):
    ShowDateTime: str
    CategoryRange: str
    Attributes: str
    ApplicableTimeFilters: List[str]
    MinPrice: str
    UpdatedMinPrice: str
    SessionCopQuota: str
    SessionCodFlag: str
    CutOffDateTime: str
    ChildSeats: str
    BestAvailableSeats: int
    CutOffFlag: str
    SessionCodQuota: str
    SessionId: str
    BestBuy: str
    SessionCopFlag: str
    AvailStatus: str
    ShowTime: str
    SessionPopUpDesc: str
    Categories: List[Category]
    ShowDateCode: str
    SessionUnpaidFlag: str
    CoupleSeats: str
    SessionUnpaidQuota: str
    IsAtmosEnabled: str
    MaxPrice: str
    UpdatedMaxPrice: str
    Offers: str
    ApplicablePriceFilters: List[str]
    ShowTimeCode: str
    SessionSubTitle: str
    SessionSubTitleAcronym: str

class EventGenre(BaseModel):
    Action: List[str]
    Adventure: List[str]
    Fantasy: List[str]
    GenreMeta: List[str]

class ChildEvent(BaseModel):
    Event_strIsDefault: Literal['Y', 'N']
    EventSyn: str
    EventRAT: str
    EventSEQ: str
    EventTrailer: str
    EventName: str
    EventGenre: EventGenre
    ApplicableTimeFilters: List[str]
    EventCensor: str
    EventGroup: str
    EventCode: str
    EventImageCode: str
    EventDimension: str
    ShowTimes: List[ShowTime]
    IsMovieClubEnabled: Literal['Y', 'N']
    EventIsAtmosEnabled: Literal['Y', 'N']
    Event_strPopUpDesc: str
    EventLanguage: str
    EventUrl: str
    ApplicablePriceFilters: List[str]

class Event(BaseModel):
    EventTitle: str
    EventDuration: str
    ChildEvents: List[ChildEvent]
    EventSynopsis: str
    EventGenre: str
    ApplicablePriceFilters: List[str]
    ApplicableTimeFilters: List[str]
    EventCensor: str
    EventGroup: str

class ShowDetail(BaseModel):
    Date: str
    BMSOffers: str
    Event: List[Event]

class CinemaPageApiResponse(BaseModel):
    ShowDetails: ShowDetail