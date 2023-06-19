from BookMyShow import BMS

def test_region():
  args = {
    'movie': 'Random Movie',
    'cinema': 'Random Cinema',
    'regionCode': 'bang',
  }
  bms = BMS( args )
  regions = bms.searchRegion( args.regionCode )
  assert len( regions ) >= 1

