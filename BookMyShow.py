#!/usr/bin/env python3

import requests
import pdb

from bs4 import BeautifulSoup
from sys import exit
from time import time
from re import sub as reSub
from datetime import datetime

def getObject():
    return type( '', (), {} ) # returns a simple object that can be used to add attributes

class BookMyShow( object ):

    def __init__( self ):
        self.ss = requests.session()

    def getSearchUrl( self, searchTerm ):
        curTime = int( round( time() * 1000 ) )
        url = "https://in.bookmyshow.com/quickbook-search.bms?d[mrs]=&d[mrb]=&cat=&_=" + str( curTime ) + "&q=" + searchTerm.replace( " ", "+" ) + "&sz=8&st=ON&em=&lt=&lg=&r=BANG&sr="
        return url

    def getMovieUrl( self, movieData ):
        '''
        `movieData` is similar to below:

        {'ST': 'NS', 'GRP': 'Event', 'IS_NEW': False, 'L_URL': '', 'DESC': ['Chris Evans', ' Robert Downey Jr.'], 'CODE': 'EG00068832', 'REGION_SLUG': '', 'EVENTSTRTAGS': [], 'IS_TREND': False, 'RATING': '', 'WTS': '9,14,847', 'TITLE': 'Avengers: Endgame', 'ID': 'ET00090482', 'TYPE': 'MT', 'TYPE_NAME': 'Movies', 'CAT': ''}
        '''
        curDate = datetime.now().strftime("%Y%m%d")
        movieName = reSub('[^0-9a-zA-Z ]+', '', movieData.get('TITLE') ).lower().replace( " ", "-" )

        movieUrl = "https://in.bookmyshow.com/buytickets/"
        movieUrl += movieName
        movieUrl += "-bengaluru/movie-bang-"
        movieUrl += movieData.get( 'ID' )
        movieUrl += "-MT/"
        movieUrl += curDate
        print( movieUrl )
        return movieUrl

    def search( self, searchTerm ):
        url = self.getSearchUrl( searchTerm )
        headers = {
                'x-requested-from' : 'WEB',
        }
        data = self.ss.get( url, headers=headers )
        assert data.status_code == 200

        jsonResp = data.json()
        movieData = jsonResp[ 'hits' ][ 0 ]
        
        # Check if show is on
        if movieData.get( 'SHOWDATE' ) is None:
            print( "The counters are yet to be opened!" )
            return None

        movieUrl = self.getMovieUrl( movieData )
        pdb.set_trace()

    def check( self, name ):
        movieLink = self.search( name )
        if movieLink is None:
            exit( 0 )

if __name__ == "__main__":
    bms = BookMyShow()
    # bms.check( name="Avengers: Endgame" )
    bms.check( name="captain marvel" )
