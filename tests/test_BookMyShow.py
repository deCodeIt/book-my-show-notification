from BookMyShow import BMS

class MockParsedArgs:
  def __init__( self, **kwargs ):
    for key, value in kwargs.items():
      setattr( self, key, value )

def test_region():
  args = MockParsedArgs(
    movie='Random Movie',
    cinema= 'Random Cinema',
    regionCode= 'bang',
    date=None,
    format=None,
    alarm=None
  )
  bms = BMS( args )
  regions = bms.searchRegion( args.regionCode )
  assert any( [ True if region.RegionCode.lower() == args.regionCode else False for region in regions ] )
  
def test_venue():
  args = MockParsedArgs(
    movie='Random Movie',
    cinema= 'pvbn',
    regionCode= 'BANG',
    date=None,
    format=None,
    alarm=None
  )
  bms = BMS( args )
  regions = bms.searchRegion( args.regionCode )
  bms.setRegion( regions[ 0 ] )
  venues = bms.searchVenue( args.cinema )
  assert any( [ True if venue.VenueCode.lower() == args.cinema else False for venue in venues ] )
