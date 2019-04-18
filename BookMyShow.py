#!/usr/bin/env python3

import requests
import pdb

from bs4 import BeautifulSoup
from sys import exit
from time import time
from re import sub as reSub
from datetime import datetime
from json import loads

def getObject():
    return type( '', (), {} ) # returns a simple object that can be used to add attributes

class BookMyShow( object ):

    def __init__( self, regionCode='BANG' ):
        regionCode = regionCode.upper()
        self.ss = requests.session()
        self.setRegionDetails( regionCode )

    def setRegionDetails( self, regionCode ):
        '''
        returns region codes required to form url
        '''
        curDate = datetime.now().strftime("%Y%m%d%H")
        regionData = self.ss.get( "https://in.bookmyshow.com/serv/getData/?cmd=GETREGIONS&t=" + curDate )
        assert regionData.status_code == 200
        regionData = regionData.text
        # extract data in json format from above javascript variables
        regionData = loads( regionData[ ( regionData.find( "=" ) + 1 ) : regionData.find( ";" ) ] )
        # TODO: one does not need to remember the city code, the city name should be good enough
        self.regionData = regionData.get( regionCode )[ 0 ]
        assert self.regionData

    def getSearchUrl( self, searchTerm ):
        curTime = int( round( time() * 1000 ) )
        url = "https://in.bookmyshow.com/quickbook-search.bms?d[mrs]=&d[mrb]=&cat=&_=" + str( curTime ) + "&q=" + searchTerm.replace( " ", "+" ) + "&sz=8&st=ON&em=&lt=&lg=&r=" + self.regionData.get( "code" ) + "&sr="
        return url

    def getUrl( self, movieData ):
        '''
        `movieData` is similar to below:

        {'ST': 'NS', 'GRP': 'Event', 'IS_NEW': False, 'L_URL': '', 'DESC': ['Chris Evans', ' Robert Downey Jr.'], 'CODE': 'EG00068832', 'REGION_SLUG': '', 'EVENTSTRTAGS': [], 'IS_TREND': False, 'RATING': '', 'WTS': '9,14,847', 'TITLE': 'Avengers: Endgame', 'ID': 'ET00090482', 'TYPE': 'MT', 'TYPE_NAME': 'Movies', 'CAT': ''}
        '''
        curDate = datetime.now().strftime("%Y%m%d")
        movieName = reSub('[^0-9a-zA-Z ]+', '', movieData.get('TITLE') ).lower().replace( " ", "-" )

        movieUrl = "https://in.bookmyshow.com/buytickets/"
        movieUrl += movieName
        movieUrl += "-" + self.regionData.get( 'alias' ) + "/movie-" + self.regionData.get( 'code' ).lower() + "-"
        movieUrl += movieData.get( 'ID' )
        movieUrl += "-MT/"
        movieUrl += curDate
        print( movieUrl )
        return movieUrl

    def search( self, searchTerm, typeName="Movies" ):
        url = self.getSearchUrl( searchTerm )
        headers = {
                'x-requested-from' : 'WEB',
        }
        data = self.ss.get( url, headers=headers )
        assert data.status_code == 200
        jsonResp = data.json()

        # return the first hit belonging to typeName
        movieData = {}
        for movieInfo in jsonResp[ 'hits' ]:
            if movieInfo.get( 'TYPE_NAME' ) == typeName:
                movieData = movieInfo
                break
        
        # Check if show is on
        if typeName == "Movies" and movieData.get( 'SHOWDATE' ) is None:
            print( "The show counters are yet to be opened!" )
            return None

        movieUrl = self.getUrl( movieData )
        return movieUrl
    
    def checkAvailability( self, movieLink ):
        '''
        movieLink refers to moviePage where we have information about the movie, the cast and other stuff
        '''
        pass

    def checkCinemaAvailability( self, movieName ):
        '''
        Rings a bell if a show is available in your requested cinema
        '''
        
    def checkMovie( self, name ):
        movieLink = self.search( name )
        if movieLink is None:
            exit( 0 )
        self.checkAvailability( movieLink )

    def checkCinema( self, name, movieName ):
        cinemaLink = self.search( name, typeName="Venues" )
        if cinemaLink is None:
            exit( 0 )
        self.checkCinemaAvailability( movieName )

if __name__ == "__main__":
    bms = BookMyShow( regionCode="BANG" )
    # bms.check( name="Avengers: Endgame" )
    bms.checkMovie( name="hellboy" )
