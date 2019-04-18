#!/usr/bin/env python3

import requests
import pdb
import sys

from bs4 import BeautifulSoup
from sys import exit
from time import time
from re import sub as reSub
from datetime import datetime
from json import loads
from sys import stdout
from os import system
from random import randint
from random import randrange
from argparse import ArgumentParser

def getObject():
    return type( '', (), {} ) # returns a simple object that can be used to add attributes

class BookMyShow( object ):

    def __init__( self, regionCode='BANG', date=None ):
        regionCode = regionCode.upper()
        self.date = date
        self.ss = requests.session()
        self.setRegionDetails( regionCode )

    def ringBell( self ):
        totalDuration = 0.0
        while totalDuration < 10.0:
            duration = 1.0 / randint(5,10)  # seconds
            freq = randrange( 200, 2000, 200 )  # Hz
            system('play --no-show-progress --null --channels 1 synth {} sine {}'.format(duration, freq))
            totalDuration += duration

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

    def getMovieUrl( self, movieData ):
        '''
        `movieData` is similar to below:

        {'ST': 'NS', 'GRP': 'Event', 'IS_NEW': False, 'L_URL': '', 'DESC': ['Chris Evans', ' Robert Downey Jr.'], 'CODE': 'EG00068832', 'REGION_SLUG': '', 'EVENTSTRTAGS': [], 'IS_TREND': False, 'RATING': '', 'WTS': '9,14,847', 'TITLE': 'Avengers: Endgame', 'ID': 'ET00090482', 'TYPE': 'MT', 'TYPE_NAME': 'Movies', 'CAT': ''}
        '''

        curDate = datetime.now().strftime("%Y%m%d") if self.date is None else self.date
        movieName = reSub('[^0-9a-zA-Z ]+', '', movieData.get('TITLE') ).lower().replace( " ", "-" )

        movieUrl = "https://in.bookmyshow.com/buytickets/"
        movieUrl += movieName
        movieUrl += "-" + self.regionData.get( 'alias' ) + "/movie-" + self.regionData.get( 'code' ).lower() + "-"
        movieUrl += movieData.get( 'ID' )
        movieUrl += "-MT/"
        movieUrl += curDate
        return movieUrl

    def getCinemaUrl( self, cinemaData ):
        '''
        `cinemaData` is similar to below:

        {"CC":"PVR","ST":"NS","REGION_SLUG":"","GRP":"Venue","EVENTSTRTAGS":[],"RATING":"","L_URL":"","WTS":"","TITLE":"PVR: Forum Mall, Koramangala","ID":"PVBN","TYPE_NAME":"Venues","TYPE":"|MT|","CAT":""}
        '''

        curDate = datetime.now().strftime("%Y%m%d") if self.date is None else self.date
        cinemaName = reSub('[^0-9a-zA-Z ]+', '', cinemaData.get('TITLE') ).lower().replace( " ", "-" )

        cinemaUrl = "https://in.bookmyshow.com/buytickets/"
        cinemaUrl += cinemaName
        cinemaUrl += "/cinema-" + self.regionData.get( 'code' ).lower() + "-"
        cinemaUrl += cinemaData.get( 'ID' )
        cinemaUrl += "-MT/"
        cinemaUrl += curDate
        return cinemaUrl

    def getUrlDataJSON( self, searchTerm ):
        '''
        returns all matched results after searching on bms
        '''

        url = self.getSearchUrl( searchTerm )
        headers = {
                'x-requested-from' : 'WEB',
        }
        data = self.ss.get( url, headers=headers )
        assert data.status_code == 200
        jsonResp = data.json()
        return jsonResp

    def search( self, searchTerm, typeName="Movies" ):
        jsonResp = self.getUrlDataJSON( searchTerm )
        # return the first hit belonging to typeName
        data = {}
        for movieInfo in jsonResp[ 'hits' ]:
            if movieInfo.get( 'TYPE_NAME' ) == typeName:
                data = movieInfo
                break
        
        url = None
        if typeName == "Movies":
            if data.get( 'SHOWDATE' ) is None:
                # Check if show is on
                print( "The show counters are yet to be opened!" )
                return None
            url = self.getMovieUrl( data )
        elif typeName == "Venues":
            url = self.getCinemaUrl( data )

        return url
    
    def checkAvailability( self, movieLink ):
        '''
        movieLink refers to moviePage where we have information about the movie, the cast and other stuff
        '''
        pass

    def checkCinemaAvailability( self, cinemaLink, movieName ):
        '''
        Rings a bell if a show is available in your requested cinema
        '''
        cinemaDetails = self.ss.get( cinemaLink )
        assert cinemaDetails.status_code == 200
        cinemaSoup = BeautifulSoup( cinemaDetails.content, 'html5lib' )
        # get movie name
        jsonRespOfMovies = self.getUrlDataJSON( movieName )
        # return the first hit belonging to movieName
        data = {}
        for movieInfo in jsonRespOfMovies[ 'hits' ]:
            if movieInfo.get( 'TYPE_NAME' ) == "Movies":
                data = movieInfo
                break
        movieName = data.get( 'TITLE', movieName )

        # find if your requested cinema is in the list
        found = False
        for movieTitle in cinemaSoup.find_all( "strong" ):
            if movieTitle.getText().strip().lower() == movieName.lower():
                found = True
                break
        if found:
            # Movie tickets are now available
            print( "HURRAY! Movie tickets are now available" )
            self.ringBell()
        else:
            print( "Movie tickets aren't available yet" )
        
    def checkMovie( self, name ):
        movieLink = self.search( name )
        if movieLink is None:
            exit( 0 )
        self.checkAvailability( movieLink )

    def checkCinema( self, name, movieName ):
        cinemaLink = self.search( name, typeName="Venues" )
        if cinemaLink is None:
            exit( 0 )
        self.checkCinemaAvailability( cinemaLink, movieName )

def parser():
    parser = ArgumentParser( prog=sys.argv[ 0 ],
                                      description="A script to check if tickets are available for the movie in the specified cinema at a given date",
                                      epilog="And you will be the first one to be notified as soon as the show is available" )
    parser.add_argument( '-m', '--movie', required=True, action='store', type=str, help="The movie you're looking to book tickets for" )
    parser.add_argument( '-c', '--cinema', required=True, action='store', type=str, help="The cinema in which you want to watch the movie" )
    parser.add_argument( '-d', '--date', required=True, action='store', type=str, help="The date on which you want to book tickets. Format: YYYYMMDD" )
    parser.add_argument( '-r', '--regionCode', required=True, action='store', type=str, help="The region code of your area; BANG for Bengaluru" )
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    args = parser()
    retry = 0
    while retry < 5:
        try:
            bms = BookMyShow( regionCode=args.regionCode, date=args.date )
            bms.checkCinema( name=args.cinema, movieName=args.movie )
            break
        except AssertionError:
            print( "Seems like we lost the connection mid-way, will retry..." )
            retry += 1
        except:
            print( "Something unexpected happened; Recommended to re-run this script with correct values" )
            break
