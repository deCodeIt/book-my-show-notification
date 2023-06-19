from pydantic import BaseModel
from typing import List, Union

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

class BookMyShow(BaseModel):
    TopCities: List[City]
    OtherCities: List[City]

class Region(BaseModel):
    BookMyShow: BookMyShow